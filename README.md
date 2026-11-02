# diy-fido-key

ESP32-S3とST7735 80×160のLCDを載せたボードを、USB FIDO2キーにするファームウェア。パスキーの登録と認証ができ、LCDには登録待ちや処理中といった状態を出す。

## 対象

| 区分 | デバイス |
|---|---|
| 対象 | ESP32-S3と0.96インチST7735S 80×160のLCDを載せたボード |
| 対象外 | LCDの無いボード、ESP32-C3、ESP32（無印）、ESP32-C6、ESP32-H2 |

このリポジトリは上の構成以外で動くことを確かめていない。対象外のチップにはUSB-OTGのデバイスモードが無いため、USBキーとしても認識されない。

## 元のリポジトリからの変更

- sdkconfig書き換えバグの修正。`tools/build-pico-fido-esp32s3.sh` は `sdkconfig` を書き換えたあとに `idf.py set-target` を実行していた。`set-target` は `sdkconfig` を削除して作り直すので、書き換えた設定は消えていた。書き換えを `set-target` のあとに移した
- 結合コマンドの修正。スクリプトは最後に `esptool` の `merge-bin` を呼んでいた。esptool 4.x にこのサブコマンドは無いので、そこでエラーになって止まっていた。`python3 -m esptool merge_bin` に変えた
- BOOTボタン押下の必須化。`pico-keys-sdk/src/button.c` の `button_timeout_seconds()` は、ボタンの設定が空の基板では待ち時間に0を返していた。0のときファームはボタンを待たずに承認するので、BOOTボタンを押さなくても認証が通っていた。既定を30秒に変え、押すまで承認しないようにした

## 必要なもの

### ハードウェア

| 項目 | 内容 |
|---|---|
| ボード | [AliExpressのESP32-S3 LCD付きボード](https://ja.aliexpress.com/item/1005009024098181.html)。Flash 16MB、PSRAM 8MB、USB-OTGのデバイスモード対応。0.96インチST7735S 80×160のLCD付き |
| USBケーブル | データ通信に対応したもの |

### ソフトウェア

| 項目 | 内容 |
|---|---|
| ESP-IDF | v5.5.1 |
| esptool | 4.x。手順1で入れるESP-IDFに同梱される |
| Python | 3.9以降。手順1のinstall.shが使う |

実施環境は ESP-IDF v5.5.1、esptool.py 4.12.0、WSL2 Ubuntu、usbipd-win、Windows 11。ESP-IDFとesptoolは手順1で、usbipd-winは手順2で入る。

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

### 2. USBデバイスをWSL2にattachする

WSL2から書き込む場合だけ必要。BOOTボタンを押したままUSBを挿してから、Windowsの管理者PowerShellで次を実行する。

```
winget install --exact dorssel.usbipd-win
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID> --auto-attach
```

WSL2側で、デバイスファイルの権限を変える。

```
sudo chmod 666 /dev/ttyACM0
```

Windowsに戻すときは `usbipd detach --busid <BUSID>` を実行する。`--auto-attach` を付けてあるので、BOOTボタンを押しながら挿し直すと、usbipdがそのUSBデバイスを自動でWSL2にattachする。

### 3. 工場出荷フラッシュの退避

読み取りだけを先に済ませる。ここを飛ばすと元のイメージに戻せなくなる。

```
. ~/esp/esp-idf-v5.5.1/export.sh
esptool.py --chip esp32s3 -p /dev/ttyACM0 flash_id
esptool.py --chip esp32s3 -p /dev/ttyACM0 read_flash 0x0 0x1000000 ~/orig.bin
sha256sum ~/orig.bin
```

16MiB の読み取りには 20〜25 分かかることがある。`flash_id` で 16MB あることを確認しておく。

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

スクリプトは LCD のパッチ適用、set-target、sdkconfig の書き換え、ボタン待ちの設定、ビルド、イメージの結合までをまとめて行う。BOOTボタンを押すまでの待ち時間は `UP_BUTTON_SECONDS` で変えられる。既定は 30 秒。

### 6. 書き込み

手順2で接続したまま実行する。USBを抜いていた場合は、BOOTボタンを押したまま挿し直す。

```
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 4MB \
  0x0 build/pico-fido-esp32s3/bootloader/bootloader.bin \
  0x8000 build/pico-fido-esp32s3/partition_table/partition-table.bin \
  0x20000 build/pico-fido-esp32s3/pico_fido.bin
```

`Hash of data verified.` が3回出れば成功。BOOT ボタンを離して挿し直す。

### 7. 確認

Windows のデバイスマネージャーや `lsusb` に `Pico Key` が出ることを確かめ、Chrome で <https://webauthn.io> に登録する。LCD に `PRESS / BOOT BUTTON` が出たら BOOT ボタンを押す。

### 工場出荷フラッシュに戻す

退避したイメージを書き戻す。

```
esptool.py --chip esp32s3 -p /dev/ttyACM0 write_flash 0x0 ~/orig.bin
```

## 詰まりどころ

| 現象 | 対処 |
|---|---|
| `esptool: not found` と出る | ESP-IDF の venv には `esptool.py` という名前で入る。`export.sh` を読んでから、`esptool.py` か `python3 -m esptool` を使う |
| `merge-bin` が Unknown command になる | esptool 4.x のサブコマンドはアンダースコアのみ。`merge_bin` を使う |
| HID として動いている間、`/dev/ttyACM*` が消える | 再書き込みのたびに、BOOT ボタンを押しながら挿し直す |
| BOOT ボタンを押したまま起動して ROM ダウンロードモードに固定される | 焼いたあとに BOOT ボタンを離す |
| `usbipd` がカーネル非対応と言う | `wsl --update` を実行する |
| LCD が真っ白になる、色が変、向きが違う | `LCD_CALIBRATION` / `LCD_COLOR_CAL` ビルドで校正する。BOOT ボタンを押すと候補が切り替わる |

## セキュリティプロファイル

`tools/security-profiles.sh` で保護レベルを切り替える。スクリプトは eFuse を焼かない。ビルドと、実行するコマンドの表示だけをする。

| プロファイル | Secure Boot | Flash Encryption | 用途 |
|---|---|---|---|
| `backup` | なし | なし | 開発・検証（再書き込み自由） |
| `encrypted` | RSA-3072で署名（eFuseは焼かない） | development | 暗号化の試行 |
| `encrypted-release` | なし | release | 暗号化の試行用。Secure Download Modeでは署名が無いため起動しない（実測） |
| `secure` | RSA-3072（署名） | release | 実機で動作確認した構成 |

### Secure BootとFlash Encryptionの制約

- ESP32-S3のSecure Boot v2はRSA-3072のみ。ECDSAは非対応で、ECDSA鍵では起動時の署名検証に失敗する
- Flash Encryptionを有効にするとSecure Download Mode になる。このモードでは `read-flash`、`chip-id`、eFuseの読み出しができない。署名済みのブートローダが要り、書き込みには `--force` と事前暗号化イメージを使う
- 暗号化を有効にすると、`part0` をmmapしても平文のFSと一致しない。mmapが復号するため。`patches/pico-fido-psram-shadow.patch` でPSRAM上のシャドウに置き換え、`esp_flash_read/write`（平文）で読み書きする。`part0` には暗号化フラグを付けない
- PSRAMは40MHz、`CONFIG_SPIRAM_IGNORE_NOTFOUND=y`（未搭載でも起動する）
- 署名付きブートローダは32KBを超える。Secure Bootを含むプロファイルはパーティションテーブルを0x10000へ移す。`encrypted-release` は0x9000

### 鍵

- 署名鍵（RSA-3072）: `~/.config/diy-fido-key/secure-boot/secure-boot-rsa3072.pem`
- フラッシュ暗号化鍵: `~/.config/diy-fido-key/secure-boot/flash-encryption-key.bin`
- どちらもオフラインで2箇所に保管する。失うと更新できなくなる

### Secure Download Modeを有効にしたあとの焼き方

```
sh tools/security-profiles.sh secure
esptool --port /dev/cu.usbmodemXXXX write-flash --force 0x0 build/pico-fido-secure/pico_fido_secure.enc.bin
```

書き込み後はBOOTボタンを離してUSBを挿し直す。`part0` のレイアウトを変えたときだけ、`esptool --port ... erase-region 0x200000 0x100000` で保存領域を作り直す。

### 再書き込み不可にする操作

完成したイメージで十分に動作確認してから、次を焼く。どれも戻せない。

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
- いま使っている基板では `DIS_DOWNLOAD_MODE` を焼いていない。まだ更新できる
- 書き込み経路を残す限り、`SECURE_BOOT_EN` が無くてもSecure Download Modeと暗号化で「読み出し不可・任意ファームの書き込み不可」までは達成できる。署名検証はされない

## 注意

- FIDO Allianceの認証は取得していない。セキュアエレメントも載せていない。個人用途、実験用、バックアップ鍵向けで、物理攻撃は守備範囲外
