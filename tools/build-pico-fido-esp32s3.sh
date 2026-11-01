#!/bin/sh
# Build pico-fido for the ESP32-S3 board (ST7735 80x160) and emit a merged image.
# Requires ESP-IDF v5.5.1 exported in the environment (idf.py on PATH).
#
# 上流版からの修正点:
#   - sdkconfig の書き換えを `set-target` の後ろへ移動。`set-target` は
#     sdkconfig を削除して作り直すため、前に書き換えても捨てられる
#     （ESP-IDF tools/idf_py_actions/core_ext.py の set_target() を参照）。
#     修正前は CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y が残り、TinyUSB と
#     GPIO19/20 を奪い合って USB が不安定になっていた。
#   - 結合を `merge-bin` から `merge_bin` に変更し、`esptool` ではなく
#     `python3 -m esptool` を呼ぶ。esptool 4.x にはどちらの名前も無い。
#   - ユーザープレゼンス（BOOT 押下）を既定で必須にする。未コミッショニングだと
#     phy.up_btn_present が偽でタイムアウト0になり、ボタンを待たずに承認される。
#     UP_BUTTON_SECONDS=0 で上流の挙動に戻せる。
set -e

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
SRC="$ROOT/vendor/pico-fido"
BUILD="$ROOT/build/pico-fido-esp32s3"

if [ ! -d "$SRC/pico-keys-sdk" ]; then
    echo "vendor/pico-fido is missing; clone it first (see README)." >&2
    exit 1
fi
if ! command -v idf.py >/dev/null 2>&1; then
    echo "idf.py not found; run '. ~/esp/esp-idf-v5.5.1/export.sh' first." >&2
    exit 1
fi

# Reproducible local patches: LCD status UI.
sh "$ROOT/tools/install-esp32-lcd.sh"

: "${FIDO_USB_VID:=0x2E8A}"
: "${FIDO_USB_PID:=0x10FE}"
: "${UP_BUTTON_SECONDS:=30}"

# set-target が sdkconfig を作り直すので、必ずこれより後に書き換える。
idf.py -B "$BUILD" -C "$SRC" -DUSB_VID="$FIDO_USB_VID" -DUSB_PID="$FIDO_USB_PID" set-target esp32s3

# On ESP32-S3 the USB Serial/JTAG console shares GPIO19/20 with USB-OTG.
# Leaving the secondary console enabled makes the firmware watchdog-loop
# before TinyUSB can enumerate the FIDO HID interface. DIO matches the
# upstream build and is the only mode verified on this board.
python3 "$ROOT/tools/patch-sdkconfig.py" "$SRC/sdkconfig"

if [ "$UP_BUTTON_SECONDS" != "0" ]; then
    python3 "$ROOT/tools/patch-up-button.py" --seconds "$UP_BUTTON_SECONDS" \
        "$SRC/pico-keys-sdk/src/button.c"
else
    echo "user presence: upstream default (no button wait until commissioned)"
fi

idf.py -B "$BUILD" -C "$SRC" -DUSB_VID="$FIDO_USB_VID" -DUSB_PID="$FIDO_USB_PID" build

python3 -m esptool --chip esp32s3 merge_bin \
    -o "$BUILD/pico_fido_full.bin" \
    --flash_mode dio --flash_freq 80m --flash_size 4MB \
    0x0 "$BUILD/bootloader/bootloader.bin" \
    0x8000 "$BUILD/partition_table/partition-table.bin" \
    0x20000 "$BUILD/pico_fido.bin"

echo "Merged image: $BUILD/pico_fido_full.bin"
echo "Flash: hold BOOT (GPIO0) while plugging in, then:"
echo "  python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write_flash \\"
echo "    --flash_mode dio --flash_freq 80m --flash_size 4MB \\"
echo "    0x0 $BUILD/bootloader/bootloader.bin \\"
echo "    0x8000 $BUILD/partition_table/partition-table.bin \\"
echo "    0x20000 $BUILD/pico_fido.bin"
echo "After flashing, release BOOT and replug."
