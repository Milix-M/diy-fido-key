# ESP32-S3 で動かす手順

このリポジトリは、元の ESP32-S3 向けビルド手順が clone しただけでは動かない問題を修正したもの。対象は ESP32-S3 + ST7735 80x160 LCD のボード。

検証環境は ESP-IDF v5.5.1、esptool.py 4.12.0、WSL2 Ubuntu + usbipd-win、ホストは Windows 11。

## 元の手順にあった2つの問題

### 1. `set-target` が sdkconfig を削除する

元の `tools/build-pico-fido-esp32s3.sh` は sdkconfig を書き換えてから `idf.py set-target` を呼んでいた。ところが `set-target` は既存の sdkconfig を削除して作り直す。

根拠は ESP-IDF の実装で、`tools/idf_py_actions/core_ext.py` の `set_target()` が `ensure_build_directory(..., True, ...)` を呼び、実行時に次を表示する。

```
Set Target to: esp32s3, new sdkconfig will be created.
```

つまり書き換えは毎回捨てられる。スクリプトを何回走らせても同じ。

結果として次が入らない。

- `CONFIG_ESP_CONSOLE_SECONDARY_NONE=y` が入らず、USB-Serial/JTAG のセカンダリコンソールが TinyUSB と GPIO19/20 を奪い合う
- `CONFIG_ESPTOOLPY_FLASHMODE_DIO=y` にならず QIO のまま
- PSRAM の設定が丸ごと入らない

症状は起動ループより先に「USB が不安定で WebAuthn がタイムアウトする」として出る。`verify_flash` でダイジェストが一致していても、設定が不正なら動かない。

### 2. `merge-bin` は esptool 4.x に無い

最後の結合が `esptool ... merge-bin` になっていた。esptool 4.12 のサブコマンドはアンダースコアのみで、実行ファイル名も `esptool.py`。

```
tools/build-pico-fido-esp32s3.sh: 63: esptool: not found
```

この行で落ちるが、ビルド自体は `Project build complete.` で終わっている。3つの bin を個別に書けば同じ結果になる。

## 修正内容

- sdkconfig の書き換えを `set-target` の後ろへ移動し、`tools/patch-sdkconfig.py` に分離
- 結合を `python3 -m esptool ... merge_bin` に変更
- ユーザープレゼンス（BOOT 押下）を既定で必須化。`tools/patch-up-button.py` を追加
- `UP_BUTTON_SECONDS=0` で元の挙動に戻せる

## 手順

### 0. ESP-IDF

```
sudo apt update
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0

mkdir -p ~/esp && cd ~/esp
git clone -b v5.5.1 --recursive https://github.com/espressif/esp-idf.git esp-idf-v5.5.1
cd esp-idf-v5.5.1 && ./install.sh esp32s3
```

### 1. USB を WSL に渡す

Windows の管理者 PowerShell で。

```
winget install --exact dorssel.usbipd-win
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID> --auto-attach
```

BOOT を押したまま USB を挿す。WSL 側で `sudo chmod 666 /dev/ttyACM0`。

### 2. 工場出荷フラッシュを退避

読み取りだけ先にやる。

```
. ~/esp/esp-idf-v5.5.1/export.sh
esptool.py --chip esp32s3 -p /dev/ttyACM0 flash_id
esptool.py --chip esp32s3 -p /dev/ttyACM0 read_flash 0x0 0x1000000 ~/orig.bin
sha256sum ~/orig.bin
```

16MiB なので 20〜25 分かかることがある。`flash_id` で 16MB を確認しておく。

戻すときは `esptool.py --chip esp32s3 -p /dev/ttyACM0 write_flash 0x0 ~/orig.bin`。

### 3. このリポジトリと pico-fido

```
cd ~
git clone https://github.com/Milix-M/diy-fido-key.git
cd diy-fido-key
git clone https://github.com/polhenarejos/pico-fido vendor/pico-fido
git -C vendor/pico-fido submodule update --init --recursive
git -C vendor/pico-fido rev-parse HEAD
```

最後の行で pico-fido のコミットを記録する。pico-fido が更新されてビルドが通らなくなったときの戻り先。

### 4. ビルド

```
. ~/esp/esp-idf-v5.5.1/export.sh
sh tools/build-pico-fido-esp32s3.sh
```

スクリプトが LCD パッチ、set-target、sdkconfig、ボタン必須化、ビルド、結合までやる。ボタン待ちの秒数は `UP_BUTTON_SECONDS` で変えられる（既定 30）。

### 5. 焼く

BOOT を押したまま USB を挿してから。

```
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 4MB \
  0x0 build/pico-fido-esp32s3/bootloader/bootloader.bin \
  0x8000 build/pico-fido-esp32s3/partition_table/partition-table.bin \
  0x20000 build/pico-fido-esp32s3/pico_fido.bin
```

`Hash of data verified.` が3回出れば成功。BOOT を離して挿し直す。

### 6. 確認

```
usbipd detach --busid <BUSID>
```

Windows のデバイスマネージャーに `Pico Key` が出ることを確認し、Chrome で https://webauthn.io に登録する。`PRESS / BOOT BUTTON` が出て、BOOT を押すと通る。

## ボタン押下が必須になる理由

pico-keys は `phy` レコードに `PHY_UP_BTN` が無いと、ボタン待ちをせず即座に承認済みにする。`pico-keys-sdk/src/button.c` の `button_timeout_seconds()` が `phy_data.up_btn_present ? phy_data.up_btn : 0` を返し、タイムアウト 0 のときは `button_wait_start_timeout()` が `SIGNAL_USER_PRESENCE_COMPLETED` を即発行するため。

本来は PicoKey App でコミッショニングして `phy` に書く。このフォークのパッチはファーム側の既定値を変える代替で、`phy` は空のまま。LED と VID/PID の設定は入らない。

## 詰まりどころ

- `esptool: not found` — ESP-IDF の venv には `esptool.py` という名前で入る。`export.sh` を読んでから `esptool.py` か `python3 -m esptool` を使う
- `merge-bin` が Unknown command — 4.x はアンダースコアのみ
- HID として動いている間は `/dev/ttyACM*` が消える。再書き込みは毎回 BOOT を押しながら挿し直す
- BOOT を押したまま起動すると ROM ダウンロードモードに固定される。焼いた後は必ず離す
- `usbipd` がカーネル非対応と言う — `wsl --update`
- 液晶が真っ白、色が変、向きが違う — `LCD_CALIBRATION` / `LCD_COLOR_CAL` ビルドで校正する。BOOT 押下で候補が切り替わる
- Flash Encryption を有効にすると Secure Download Mode になり `read_flash` が通らなくなる。退避は必ず最初に
