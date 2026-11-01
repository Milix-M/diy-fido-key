# 原因と切り分け

対象は ESP32-S3とST7735 80×160のLCDを載せたボードだけ。ほかのボードは扱わない。検証環境は ESP-IDF v5.5.1、esptool.py 4.12.0、WSL2 Ubuntu と usbipd-win、ホストは Windows 11。

焼き方は[README.md](README.md)にある。ここには、直した理由と、つまずいたときの手順を書く。

## 設定の書き換えが消える

元の `tools/build-pico-fido-esp32s3.sh` は次の順で動いていた。

1. 26〜55行目で `vendor/pico-fido/sdkconfig` を書き換える
2. 60行目で `idf.py set-target esp32s3` を実行する

`idf.py set-target` は既存の `sdkconfig` を削除して作り直す。根拠は ESP-IDF の実装で、`tools/idf_py_actions/core_ext.py` の `set_target()` が `ensure_build_directory(..., True, ...)` を呼ぶ。このとき idf.py は次を表示する。

```
Set Target to: esp32s3, new sdkconfig will be created.
```

そのため1の書き換えは2で消える。スクリプトを何回走らせても同じ。

結果として次の設定が入らない。

- `CONFIG_ESP_CONSOLE_SECONDARY_NONE=y` が入らず、USB-Serial/JTAG のセカンダリコンソールが TinyUSB と GPIO19/20 を取り合う
- `CONFIG_ESPTOOLPY_FLASHMODE_DIO=y` にならず QIO のまま
- PSRAM の設定が丸ごと入らない

症状は起動ループより先に、USB が不安定になって WebAuthn がタイムアウトする形で出る。`verify_flash` でダイジェストが一致していても、設定が不正なら動かない。

このリポジトリでは書き換えを `set-target` の後ろへ移し、`tools/patch-sdkconfig.py` に分けた。

## 最後の結合で落ちる

63行目で `esptool --chip esp32s3 merge-bin` を呼んでいる。esptool 4.12 のサブコマンドはアンダースコアのみで、実行ファイル名も `esptool.py`。

```
tools/build-pico-fido-esp32s3.sh: 63: esptool: not found
```

この行で落ちるが、ビルド自体は `Project build complete.` で終わっている。3つの bin を個別に書けば同じ結果になる。

このリポジトリでは `python3 -m esptool ... merge_bin` に変えた。

## ボタンを押すまで承認しない

pico-keys は `phy` レコードに `PHY_UP_BTN` が無いと、ボタン待ちをせずに即座に承認済みにする。`pico-keys-sdk/src/button.c` の `button_timeout_seconds()` が `phy_data.up_btn_present ? phy_data.up_btn : 0` を返し、待ち時間が 0 のときは `button_wait_start_timeout()` が `SIGNAL_USER_PRESENCE_COMPLETED` をすぐに発行するため。

本来は PicoKey App でコミッショニングして `phy` に書き込む。このリポジトリのパッチはファーム側の既定値を 30 秒に変える代替で、`phy` は空のまま。LED と VID/PID の設定は入らない。`tools/patch-up-button.py` が `button.c` の既定値を書き換える。

`UP_BUTTON_SECONDS=0` で元の挙動に戻せる。

## WSL2 で USB を渡す

WSL2 から書き込む場合だけ必要。Windows の管理者 PowerShell で実行する。

```
winget install --exact dorssel.usbipd-win
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID> --auto-attach
```

BOOT ボタンを押したまま USB を挿す。WSL 側で `sudo chmod 666 /dev/ttyACM0` を実行する。

Windows に戻すときは `usbipd detach --busid <BUSID>`。`--auto-attach` を付けているので、BOOT ボタンを押しながら挿し直すと自動で WSL に戻る。

WSL2 の前提パッケージは次のとおり。

```
sudo apt update
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

## 工場出荷フラッシュに戻す

退避したイメージを書き戻す。

```
esptool.py --chip esp32s3 -p /dev/ttyACM0 write_flash 0x0 ~/orig.bin
```

16MiB の退避は 20〜25 分かかることがある。`flash_id` で 16MB を確認しておく。

## 詰まりどころ

- `esptool: not found` と出る。ESP-IDF の venv には `esptool.py` という名前で入る。`export.sh` を読んでから `esptool.py` か `python3 -m esptool` を使う
- `merge-bin` が Unknown command になる。4.x はアンダースコアのみ
- HID として動いている間は `/dev/ttyACM*` が消える。再書き込みは毎回 BOOT ボタンを押しながら挿し直す
- BOOT ボタンを押したまま起動すると ROM ダウンロードモードに固定される。焼いた後は必ず離す
- `usbipd` がカーネル非対応と言う。`wsl --update` を実行する
- 液晶が真っ白になる、色が変、向きが違う。`LCD_CALIBRATION` / `LCD_COLOR_CAL` ビルドで校正する。BOOT ボタンを押すと候補が切り替わる
- pico-fido のコミットは `git -C vendor/pico-fido rev-parse HEAD` で記録しておく。更新でビルドが通らなくなったときの戻り先になる
- Flash Encryption を有効にすると Secure Download Mode になり `read_flash` が通らなくなる。退避は必ず最初に済ませる
