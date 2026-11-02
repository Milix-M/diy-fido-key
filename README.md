# diy-fido-key

ESP32-S3とST7735 80×160のLCDを載せたボードを、USB FIDO2キーにするファームウェア。パスキーの登録と認証ができ、LCDには登録待ちや処理中といった状態を出す。

## 対象

| 区分 | デバイス |
|---|---|
| 対象 | ESP32-S3と0.96インチST7735S 80×160のLCDを載せたボード |
| 対象外 | LCDの無いボード、ESP32-C3、ESP32（無印）、ESP32-C6、ESP32-H2 |

このリポジトリは上の構成以外で動くことを確かめていない。対象外のチップにはUSB-OTGのデバイスモードが無いため、USBキーとしても認識されない。

## 元のリポジトリからの変更

- 設定の書き換えが消える。`tools/build-pico-fido-esp32s3.sh` が `idf.py set-target` より先に `sdkconfig` を書き換えており、`set-target` が `sdkconfig` を作り直すため
- 最後の結合が `merge-bin` を呼んで落ちる。esptool 4.x にこの名前は無い
- ボタンを押さなくても認証が通る。設定を書き込んでいない基板では、ボタン待ちの時間が0になるため

## 必要なもの

### ハードウェア

| 項目 | 内容 |
|---|---|
| ボード | ESP32-S3。Flash 16MB、PSRAM 8MB、USB-OTGのデバイスモード対応。0.96インチST7735S 80×160のLCD付き |
| USBケーブル | データ通信に対応したもの |

### ソフトウェア

| 項目 | 内容 |
|---|---|
| ESP-IDF | v5.5.1 |
| esptool | 4.x。ESP-IDFに同梱される |
| Python | 3.9以降 |

検証環境は ESP-IDF v5.5.1、esptool.py 4.12.0、WSL2 Ubuntu と usbipd-win、ホストは Windows 11。

## 手順

### 1. ESP-IDF

```
mkdir -p ~/esp && cd ~/esp
git clone -b v5.5.1 --recursive https://github.com/espressif/esp-idf.git esp-idf-v5.5.1
cd esp-idf-v5.5.1 && ./install.sh esp32s3
```

WSL2 の場合は、先に前提パッケージを入れる。

```
sudo apt update
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

### 2. USB を WSL2 に渡す

WSL2 から書き込む場合だけ必要。Windows の管理者 PowerShell で実行する。

```
winget install --exact dorssel.usbipd-win
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID> --auto-attach
```

BOOT ボタンを押したまま USB を挿す。WSL 側で `sudo chmod 666 /dev/ttyACM0` を実行する。

Windows に戻すときは `usbipd detach --busid <BUSID>`。`--auto-attach` を付けているので、BOOT ボタンを押しながら挿し直すと自動で WSL に戻る。

### 3. 工場出荷フラッシュの退避

読み取りだけを先に済ませる。ここを飛ばすと元のイメージに戻せなくなる。

```
. ~/esp/esp-idf-v5.5.1/export.sh
esptool.py --chip esp32s3 -p /dev/ttyACM0 flash_id
esptool.py --chip esp32s3 -p /dev/ttyACM0 read_flash 0x0 0x1000000 ~/orig.bin
sha256sum ~/orig.bin
```

16MiB なので 20〜25 分かかることがある。`flash_id` で 16MB を確認しておく。

### 4. リポジトリのclone

```
cd ~
git clone https://github.com/Milix-M/diy-fido-key.git
cd diy-fido-key
git clone https://github.com/polhenarejos/pico-fido vendor/pico-fido
git -C vendor/pico-fido submodule update --init --recursive
git -C vendor/pico-fido rev-parse HEAD
```

最後の行で pico-fido のコミットを記録する。更新でビルドが通らなくなったときの戻り先になる。

### 5. ビルド

```
. ~/esp/esp-idf-v5.5.1/export.sh
sh tools/build-pico-fido-esp32s3.sh
```

スクリプトが LCD パッチ、set-target、sdkconfig、ボタン待ちの設定、ビルド、結合まで行う。待ち時間は `UP_BUTTON_SECONDS` で変えられる。既定は 30 秒。

### 6. 書き込み

BOOT ボタンを押したまま USB を挿してから実行する。

```
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 4MB \
  0x0 build/pico-fido-esp32s3/bootloader/bootloader.bin \
  0x8000 build/pico-fido-esp32s3/partition_table/partition-table.bin \
  0x20000 build/pico-fido-esp32s3/pico_fido.bin
```

`Hash of data verified.` が3回出れば成功。BOOT ボタンを離して挿し直す。

### 7. 確認

Windows のデバイスマネージャーや `lsusb` に `Pico Key` が出ることを確かめ、Chrome で <https://webauthn.io> に登録する。液晶に `PRESS / BOOT BUTTON` が出たら BOOT ボタンを押す。

### 工場出荷フラッシュに戻す

退避したイメージを書き戻す。

```
esptool.py --chip esp32s3 -p /dev/ttyACM0 write_flash 0x0 ~/orig.bin
```

## 詰まりどころ

- `esptool: not found` と出る。ESP-IDF の venv には `esptool.py` という名前で入る。`export.sh` を読んでから `esptool.py` か `python3 -m esptool` を使う
- `merge-bin` が Unknown command になる。4.x はアンダースコアのみ
- HID として動いている間は `/dev/ttyACM*` が消える。再書き込みは毎回 BOOT ボタンを押しながら挿し直す
- BOOT ボタンを押したまま起動すると ROM ダウンロードモードに固定される。焼いた後は必ず離す
- `usbipd` がカーネル非対応と言う。`wsl --update` を実行する
- 液晶が真っ白になる、色が変、向きが違う。`LCD_CALIBRATION` / `LCD_COLOR_CAL` ビルドで校正する。BOOT ボタンを押すと候補が切り替わる

## セキュリティプロファイル

`tools/security-profiles.sh` で保護レベルを切り替える。スクリプトは eFuse を焼かない。ビルドと、実行するコマンドの表示だけをする。

| プロファイル | Secure Boot | Flash Encryption | 用途 |
|---|---|---|---|
| `backup` | なし | なし | 開発・検証（再書き込み自由） |
| `encrypted` | RSA-3072で署名（eFuseは焼かない） | development | 暗号化の試行 |
| `encrypted-release` | なし | release | 暗号化の試行用。SDMでは署名が無いため起動しない（実測） |
| `secure` | RSA-3072（署名） | release | 実機で動作確認した構成 |

### Secure BootとFlash Encryptionの制約

- ESP32-S3のSecure Boot v2はRSA-3072のみ。ECDSAは非対応で、ECDSA鍵では起動時の署名検証に失敗する
- Flash Encryptionを有効にするとSecure Download Mode (SDM) になる。SDMでは `read-flash`、`chip-id`、eFuseの読み出しができず、署名済みブートローダが要る。書き込みは `--force` と事前暗号化イメージを使う
- pico-fidoは `part0` をmmapするが、暗号化が有効だとmmapが復号するため平文のFSと一致しない。`patches/pico-fido-psram-shadow.patch` でPSRAM上のシャドウに置き換え、`esp_flash_read/write`（平文）で読み書きする。`part0` には暗号化フラグを付けない
- PSRAMは40MHz、`CONFIG_SPIRAM_IGNORE_NOTFOUND=y`（未搭載でも起動する）
- 署名付きブートローダは32KBを超える。Secure Bootを含むプロファイルはパーティションテーブルを0x10000へ移す。`encrypted-release` は0x9000

### 鍵

- 署名鍵（RSA-3072）: `~/.config/diy-fido-key/secure-boot/secure-boot-rsa3072.pem`
- フラッシュ暗号化鍵: `~/.config/diy-fido-key/secure-boot/flash-encryption-key.bin`
- どちらもオフラインで2箇所に保管する。失うと更新できなくなる

### SDM有効後の焼き方

```
sh tools/security-profiles.sh secure
esptool --port /dev/cu.usbmodemXXXX write-flash --force 0x0 build/pico-fido-secure/pico_fido_secure.enc.bin
```

書き込み後はBOOTボタンを離してUSBを挿し直す。`part0` のレイアウトを変えたときだけ、`esptool --port ... erase-region 0x200000 0x100000` で保存領域を作り直す。

### 再書き込み不可にする操作

完成したイメージで十分に動作確認してから、最後に実施する。どれも戻せない。

| 操作 | 効果 | 戻せるか |
|---|---|---|
| `SECURE_BOOT_EN` + digest | 署名済みイメージのみ起動（更新には署名鍵が要る） | 不可 |
| `DIS_DOWNLOAD_MODE` | ROMダウンロードモードを無効化し、再書き込み不可にする | 不可 |
| `DIS_USB_JTAG` / `DIS_PAD_JTAG` | JTAG経路を無効化 | 不可 |
| pico-fido Secure Lock | MKEKをOTPに固定し、資格情報を端末に紐付ける | 不可 |

```
# 最後に実行する。事前に署名済みイメージでの起動確認と鍵の退避を済ませる
espefuse.py --port /dev/cu.usbmodemXXXX burn_efuse DIS_DOWNLOAD_MODE
espefuse.py --port /dev/cu.usbmodemXXXX burn_efuse DIS_USB_JTAG
```

### 焼く前の注意

- `DIS_DOWNLOAD_MODE` を焼くと二度と書き込めなくなる。失敗したら基板ごと交換になる
- 署名鍵と暗号化鍵の控えが無い状態で焼かない
- 現行機は未実施。`DIS_DOWNLOAD_MODE` は焼いていないので、まだ更新できる
- 書き込み経路を残す限り、`SECURE_BOOT_EN` が無くてもSDMと暗号化で「読み出し不可・任意ファームの書き込み不可」までは達成できる。署名検証はされない

### 動作確認の記録

- `GetInfo`（CTAP 2.3 / max 1024）、登録（packed / UP+AT）、認証（署名71B / counter）、再起動後の永続化、LCD表示
- eFuseの状態。`BLOCK_KEY0` にXTS鍵、`SPI_BOOT_CRYPT_CNT = 0b001`、`SECURE_BOOT_EN` は未焼（署名はSDMの要求のために付与）
- 実機で実行したeFuse操作（一方通行）

```
espefuse.py --port /dev/cu.usbmodemXXXX burn_key BLOCK_KEY0 flash-encryption-key.bin XTS_AES_128_KEY
espefuse.py --port /dev/cu.usbmodemXXXX burn_efuse SPI_BOOT_CRYPT_CNT 0x1
```

## 注意

- Flash Encryptionを有効にするとSecure Download Modeになり、`read_flash`が通らなくなる。退避は最初に済ませる
- FIDO Allianceの認証は取得していない。セキュアエレメントも載せていない。個人用途、実験用、バックアップ鍵向けで、物理攻撃は守備範囲外
