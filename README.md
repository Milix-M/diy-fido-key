# diy-fido-key

市販のESP32-S3ボードをUSB FIDO2キーにするファームウェアと、それを焼くための手順。ST7735のLCDを載せたボードなら、登録待ちや処理中といった状態を画面に出せる。

## 変更点

元のリポジトリのままでは、設定が反映されないまま書き込みが終わる。原因は2つある。あわせて、ボタンを押さなくても認証が通ってしまう問題を直した。

### 設定の書き換えが消える

`tools/build-pico-fido-esp32s3.sh` は次の順で動く。

1. 26〜55行目で `vendor/pico-fido/sdkconfig` を書き換える
2. 60行目で `idf.py set-target esp32s3` を実行する

`idf.py set-target` は既存の `sdkconfig` を削除して作り直す。ESP-IDFの `tools/idf_py_actions/core_ext.py` にある `set_target()` が `ensure_build_directory(..., True, ...)` を呼び、実行時に「Set Target to: esp32s3, new sdkconfig will be created.」と表示する。

そのため1の書き換えは2で消える。残るのは既定値で、次の3つが入らない。

- `CONFIG_ESP_CONSOLE_SECONDARY_NONE=y`
- `CONFIG_ESPTOOLPY_FLASHMODE_DIO=y`
- PSRAM関連の設定

1つ目が入らないと、ESP32-S3のUSB Serial/JTAGコンソールがTinyUSBと同じGPIO19/20を使う。USBの通信が不安定になり、Chromeからパスキーを登録するとタイムアウトする。

このリポジトリでは設定の書き換えを `set-target` の後ろへ移した。

### 最後の結合で落ちる

63行目が `esptool --chip esp32s3 merge-bin` を呼ぶ。esptool 4.xには `esptool` という実行ファイルも `merge-bin` というサブコマンドもない。正しくは `python3 -m esptool merge_bin`。

ここで落ちてもビルド自体は終わっている。3つのbinを個別に書き込めば同じ結果になる。

### BOOTボタンを押すまで承認しない

pico-fidoは設定を書き込んでいない基板ではボタン待ちをしない。`pico-keys-sdk/src/button.c` の `button_timeout_seconds()` が `phy_data.up_btn_present ? phy_data.up_btn : 0` を返し、待ち時間が0のときはボタンを押さなくても押されたものとして扱う。`phy`レコードはPicoKey Appで書き込む設定で、買ったままの基板では空になる。

このままだと、キーを挿したままPCが遠隔操作された場合、手元で押さなくても認証が通る。このリポジトリでは待ち時間の既定を30秒にした。基板のBOOTボタン（GPIO0）を押すまで承認しない。

秒数は `UP_BUTTON_SECONDS` で変えられる。0にすると元の動作に戻る。

## 必要なもの

### ハードウェア

| 項目 | 内容 |
|---|---|
| ボード | ESP32-S3。Flash 16MB、PSRAM 8MB、USB-OTGのデバイスモードに対応したもの |
| LCD | 任意。0.96インチST7735S 80×160 |
| USBケーブル | データ通信に対応したもの |

LCDを載せる場合、ESP32-S3のピンと次のように接続する。

| LCDの信号 | ESP32-S3のピン |
|---|---|
| SCLK | GPIO10 |
| MOSI | GPIO11 |
| CS | GPIO12 |
| DC | GPIO13 |
| RST | GPIO14 |

BOOTボタンは基板の裏にある。GPIO0につながっている。

### 対象デバイス

| 区分 | デバイス |
|---|---|
| 対象 | ESP32-S3 |
| 対象外 | ESP32-C3、ESP32（無印）、ESP32-C6、ESP32-H2 |

対象外のチップにはUSB-OTGのデバイスモードが無いため、USBキーとして認識されない。

### ソフトウェア

| 項目 | 内容 |
|---|---|
| ESP-IDF | v5.5.1 |
| esptool | 4.x。ESP-IDFに同梱される |
| Python | 3.9以降 |

## 手順

### 1. ESP-IDF

```
mkdir -p ~/esp && cd ~/esp
git clone -b v5.5.1 --recursive https://github.com/espressif/esp-idf.git esp-idf-v5.5.1
cd esp-idf-v5.5.1 && ./install.sh esp32s3
```

### 2. 工場出荷フラッシュの退避

読み取りだけを先に済ませる。

```
. ~/esp/esp-idf-v5.5.1/export.sh
esptool.py --chip esp32s3 -p /dev/ttyACM0 flash_id
esptool.py --chip esp32s3 -p /dev/ttyACM0 read_flash 0x0 0x1000000 ~/orig.bin
```

### 3. 取得

```
git clone https://github.com/Milix-M/diy-fido-key.git
cd diy-fido-key
git clone https://github.com/polhenarejos/pico-fido vendor/pico-fido
git -C vendor/pico-fido submodule update --init --recursive
```

### 4. ビルド

```
. ~/esp/esp-idf-v5.5.1/export.sh
sh tools/build-pico-fido-esp32s3.sh
```

### 5. 書き込み

BOOTボタンを押したままUSBを挿してから実行する。

```
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 4MB \
  0x0 build/pico-fido-esp32s3/bootloader/bootloader.bin \
  0x8000 build/pico-fido-esp32s3/partition_table/partition-table.bin \
  0x20000 build/pico-fido-esp32s3/pico_fido.bin
```

焼き終わったらBOOTボタンを離して挿し直す。

### 6. 確認

デバイスマネージャーや`lsusb`に`Pico Key`が出ることを確かめ、Chromeで<https://webauthn.io>に登録する。液晶に`PRESS / BOOT BUTTON`が出たらBOOTボタンを押す。

## 注意

- `tools/security-profiles.sh secure`とeFuseを焼く操作は戻せない。[docs/security-profiles.md](docs/security-profiles.md)を読んでから実施する
- Flash Encryptionを有効にするとSecure Download Modeになり、`read_flash`が通らなくなる。退避は最初に済ませる
- FIDO認証もセキュアエレメントも無い。個人用途、実験用、バックアップ鍵向けで、物理攻撃は守備範囲外
- バイナリを配布する場合はVID/PIDとライセンスの条件がある。[docs/distribution.md](docs/distribution.md)

## そのほか

- [SETUP.md](SETUP.md) 詳しい手順と切り分け
- [docs/security-profiles.md](docs/security-profiles.md) 保護機能と不可逆な操作
- [docs/distribution.md](docs/distribution.md) 公開・配布の条件
- [docs/c3-ble.md](docs/c3-ble.md) C3とBLEの試作
- [docs/README.original.md](docs/README.original.md) 元のREADME
- ファームウェア本体 <https://github.com/polhenarejos/pico-fido>
- 元になった紹介記事 <https://www.makeuseof.com/made-own-yubikey-less-than-8/>
