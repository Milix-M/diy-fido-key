#!/bin/sh
# Build signed/encrypted ESP32-S3 images. Device provisioning is a separate step.
set -eu

MODE=${1:-}
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
SRC="$ROOT/vendor/pico-fido"
BUILD="$ROOT/build/pico-fido-$MODE"
KEYDIR=${FIDO_KEY_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/diy-fido-key/secure-boot}
SB_KEY="$KEYDIR/secure-boot-rsa3072.pem"
FE_KEY="$KEYDIR/flash-encryption-key.bin"

case "$MODE" in
    backup) exec sh "$ROOT/tools/build-pico-fido-esp32s3.sh" ;;
    encrypted|encrypted-release|secure) ;;
    *) echo "usage: sh tools/security-profiles.sh [backup|encrypted|encrypted-release|secure]" >&2; exit 2 ;;
esac

if ! command -v idf.py >/dev/null 2>&1; then
    echo "Export ESP-IDF v5.5.1 before building." >&2
    exit 1
fi
python3 "$ROOT/tools/build-info.py"

# Require existing keys so a missing backup cannot silently create a new identity.
python3 - "$MODE" "$SB_KEY" "$FE_KEY" <<'PY'
from pathlib import Path
import stat
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

mode, signing_path, encryption_path = sys.argv[1:]
paths = []
if mode != "encrypted-release":
    paths.append(Path(signing_path))
if mode != "encrypted":
    paths.append(Path(encryption_path))
for path in paths:
    if not path.is_file():
        raise SystemExit(f"Required key is missing: {path}. Restore the existing key or follow README for a new device.")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise SystemExit(f"Key permissions must exclude group and others: {path}")
if mode != "encrypted-release":
    key = serialization.load_pem_private_key(Path(signing_path).read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 3072:
        raise SystemExit("Secure Boot requires an RSA-3072 signing key.")
if mode != "encrypted" and len(Path(encryption_path).read_bytes()) != 32:
    raise SystemExit("XTS_AES_128 requires a 32-byte flash encryption key.")
PY

: "${UP_BUTTON_SECONDS:=30}"
sh "$ROOT/tools/install-esp32-lcd.sh"
python3 "$ROOT/tools/patch-up-button.py" --require-presence --seconds "$UP_BUTTON_SECONDS" \
    "$SRC/pico-keys-sdk/src/button.c"

umask 077
mkdir -p "$BUILD"
SDKCONFIG="$BUILD/sdkconfig"
idf.py -B "$BUILD" -C "$SRC" -DSDKCONFIG="$SDKCONFIG" set-target esp32s3
python3 "$ROOT/tools/patch-sdkconfig.py" "$SDKCONFIG"
python3 - "$SDKCONFIG" "$MODE" "$SB_KEY" <<'PY'
import json
from pathlib import Path
import sys

path, mode, signing_key = sys.argv[1:]
config = Path(path)
text = config.read_text()
settings = {
    "CONFIG_SECURE_BOOT": "y" if mode != "encrypted-release" else None,
    "CONFIG_SECURE_BOOT_V2_ENABLED": "y" if mode != "encrypted-release" else None,
    "CONFIG_SECURE_BOOT_BUILD_SIGNED_BINARIES": "y" if mode != "encrypted-release" else None,
    "CONFIG_SECURE_BOOT_SIGNING_KEY": json.dumps(signing_key) if mode != "encrypted-release" else None,
    "CONFIG_SECURE_SIGNED_APPS_RSA_SCHEME": "y" if mode != "encrypted-release" else None,
    "CONFIG_SECURE_FLASH_ENC_ENABLED": "y",
    "CONFIG_SECURE_FLASH_ENCRYPTION_MODE_DEVELOPMENT": "y" if mode == "encrypted" else None,
    "CONFIG_SECURE_FLASH_ENCRYPTION_MODE_RELEASE": "y" if mode != "encrypted" else None,
    "CONFIG_SPIRAM_SPEED_80M": None,
    "CONFIG_SPIRAM_SPEED_40M": "y",
    "CONFIG_SPIRAM_IGNORE_NOTFOUND": None,
    "CONFIG_PARTITION_TABLE_OFFSET": "0x10000",
}
for name, value in settings.items():
    text = "\n".join(line for line in text.splitlines()
                     if not line.startswith(name + "=") and line != f"# {name} is not set")
    text += "\n" + (f"{name}={value}" if value is not None else f"# {name} is not set") + "\n"
config.write_text(text)
PY

idf.py -B "$BUILD" -C "$SRC" -DSDKCONFIG="$SDKCONFIG" build

if [ "$MODE" != encrypted-release ]; then
    python3 -m espsecure verify_signature --version 2 --keyfile "$SB_KEY" "$BUILD/bootloader/bootloader.bin"
    python3 -m espsecure verify_signature --version 2 --keyfile "$SB_KEY" "$BUILD/pico_fido.bin"
fi

# Encrypt each image at its own address, leaving the intervening data regions untouched.
if [ "$MODE" != encrypted ]; then
    python3 -m espsecure encrypt_flash_data --aes_xts --keyfile "$FE_KEY" --address 0x0 \
        --output "$BUILD/bootloader/bootloader.enc.bin" "$BUILD/bootloader/bootloader.bin"
    python3 -m espsecure encrypt_flash_data --aes_xts --keyfile "$FE_KEY" --address 0x10000 \
        --output "$BUILD/partition_table/partition-table.enc.bin" "$BUILD/partition_table/partition-table.bin"
    python3 -m espsecure encrypt_flash_data --aes_xts --keyfile "$FE_KEY" --address 0x20000 \
        --output "$BUILD/pico_fido.enc.bin" "$BUILD/pico_fido.bin"
fi

python3 "$ROOT/tools/build-info.py" --record "$BUILD"
echo "Images built in $BUILD. Follow README for device inspection and provisioning."
echo "A security bootloader can burn eFuses on first boot. Confirm the device state before flashing."
