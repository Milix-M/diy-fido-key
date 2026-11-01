# diy-fido-key

市販のESP32-S3ボードをUSB FIDO2キーにするファームウェアと、それを焼くための手順。ST7735のLCDを載せたボードなら、登録待ちや処理中といった状態を画面に出せる。

## このforkの変更

上流のビルドスクリプトは素のクローンから通らない。2か所を直した。

- `idf.py set-target`はsdkconfigを削除して作り直す。上流はその前に設定を書き換えていたため、変更が毎回捨てられていた。結果としてUSB-Serial/JTAGのセカンダリコンソールがTinyUSBとGPIO19/20を奪い合い、WebAuthnがタイムアウトしていた
- 結合コマンド`merge-bin`はesptool 4.xに無い。`merge_bin`に直した

あわせて、未コミッショニングでもBOOT押下を必須にした。上流は`phy`レコードが空だとボタンを待たずに承認する。

経緯と詳しい手順は[SETUP.md](SETUP.md)にある。

## 必要なもの

- ESP32-S3ボード。Flash 16MB、PSRAM 8MB、native USB
- USB-OTGのデバイスモードが要る。ESP32-C3、無印ESP32、C6、H2では動かない
- LCDは任意。0.96インチST7735S 80×160を使う場合の配線はSCLK=10、MOSI=11、CS=12、DC=13、RST=14
- ESP-IDF v5.5.1
- esptool 4.x

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

ボタン待ちの秒数は`UP_BUTTON_SECONDS`で変える。既定は30。

### 5. 書き込み

BOOT（GPIO0）を押したままUSBを挿してから実行する。

```
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 4MB \
  0x0 build/pico-fido-esp32s3/bootloader/bootloader.bin \
  0x8000 build/pico-fido-esp32s3/partition_table/partition-table.bin \
  0x20000 build/pico-fido-esp32s3/pico_fido.bin
```

焼き終わったらBOOTを離して挿し直す。

### 6. 確認

デバイスマネージャーや`lsusb`に`Pico Key`が出ることを確かめ、Chromeで<https://webauthn.io>に登録する。液晶に`PRESS / BOOT BUTTON`が出たらBOOTを押す。

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
- [docs/README.original.md](docs/README.original.md) 上流のREADME
- ファームウェア本体 <https://github.com/polhenarejos/pico-fido>
- 元になった紹介記事 <https://www.makeuseof.com/made-own-yubikey-less-than-8/>
