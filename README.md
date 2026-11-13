# diy-fido-key

ESP32-S3とST7735 80×160のLCDを載せたボードをUSB FIDO2キーにするファームウェア。パスキーの登録・認証と、LCDでの状態表示ができる。

## 対象

| 区分 | デバイス |
|---|---|
| 対象 | ESP32-S3と0.96インチST7735S 80×160のLCDを載せたボード |
| 対象外 | LCDの無いボード、ESP32-C3、ESP32（無印）、ESP32-C6、ESP32-H2 |

以下の手順はWindows 11とWSL2 Ubuntu向け。

## 元のリポジトリからの変更

- **ビルド設定の修正**
  - `tools/build-pico-fido-esp32s3.sh` では `set-target` が書き換え済みの `sdkconfig` を作り直していたため、設定の書き換えを後ろへ移した
- **結合コマンドの修正**
  - esptool 4.xに無い `merge-bin` で止まっていたため、`python3 -m esptool merge_bin` に変えた
- **BOOTボタンでの承認**
  - `button.c` の `button_timeout_seconds()` が未設定時に0秒を返し、ボタンを待たずに承認していたため、既定を30秒に変えた

## 必要なもの

### ハードウェア

| 項目 | 内容 |
|---|---|
| ボード | [AliExpressのESP32-S3 LCD付きボード](https://ja.aliexpress.com/item/1005009024098181.html)。Flash 16MB、PSRAM 8MB |
| USBケーブル | データ通信ができるもの |

### ソフトウェア

| 項目 | 内容 |
|---|---|
| ESP-IDF | ビルド環境。v5.5.1 |
| esptool | 書き込みツール。4.12.0。ESP-IDFのPython環境で使う |
| Python | ESP-IDFのインストール用。3.9以降 |

ESP-IDFとesptoolは手順1で、WindowsのUSBをWSL2へ渡すusbipd-winは手順2で入れる。

## 手順

まず手順1〜7で通常のファームウェアを動かす。本番用の保護設定はそのあとに[本番用にセットアップする](#本番用にセットアップする)で進める。

### 1. ESP-IDFをインストールする

WSL2 の場合は、先に前提パッケージを入れる。

```
sudo apt update
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

```
mkdir -p ~/esp && cd ~/esp
git clone -b v5.5.1 --recursive https://github.com/espressif/esp-idf.git esp-idf-v5.5.1
cd esp-idf-v5.5.1 && ./install.sh esp32s3
```

### 2. USBデバイスをWSL2にattachする

WSL2から書き込む場合だけ必要。BOOTボタンを押したままUSBを挿してから、Windowsの管理者PowerShellで次を実行する。`<BUSID>` は `usbipd list` のこのボードの行に表示されるBUSIDに置き換える。

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

元に戻すためのイメージを保存する。`flash_id` でFlashが16MBであることを確認してから、`read_flash` で16MiBを読み取る。

```
. ~/esp/esp-idf-v5.5.1/export.sh
esptool.py --chip esp32s3 -p /dev/ttyACM0 flash_id
esptool.py --chip esp32s3 -p /dev/ttyACM0 read_flash 0x0 0x1000000 ~/orig.bin
sha256sum ~/orig.bin
```

### 4. リポジトリのclone

```
cd ~
git clone https://github.com/Milix-M/diy-fido-key.git
cd diy-fido-key
git clone https://github.com/polhenarejos/pico-fido vendor/pico-fido
git -C vendor/pico-fido checkout 99337e1204348921452a3ce6613e8e17617d4c7d
git -C vendor/pico-fido submodule update --init --recursive
git -C vendor/pico-fido rev-parse HEAD
```

バージョンは [esp32-build-lock.json](tools/esp32-build-lock.json) と [esp32-dependencies.lock](tools/esp32-dependencies.lock) で固定。バージョンを上げるときは固定する設定も更新し、ビルドと実機試験をやり直す。

### 5. ビルド

```
. ~/esp/esp-idf-v5.5.1/export.sh
sh tools/build-pico-fido-esp32s3.sh
```

BOOTボタンの待ち時間は `UP_BUTTON_SECONDS` で変えられる。既定30秒。

### 6. 書き込み

[USB接続の手順](#2-usbデバイスをwsl2にattachする)で接続したまま実行する。USBを抜いていた場合は、BOOTボタンを押したまま挿し直す。

```
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 4MB \
  0x0 build/pico-fido-esp32s3/bootloader/bootloader.bin \
  0x8000 build/pico-fido-esp32s3/partition_table/partition-table.bin \
  0x20000 build/pico-fido-esp32s3/pico_fido.bin
```

`Hash of data verified.` が3回出れば成功。BOOT ボタンを離して挿し直す。

### 7. 確認

Windows のデバイスマネージャーや `lsusb` に `Pico Key` が出ることを確かめ、Chromeで <https://webauthn.io> にテスト用のキーを登録し、認証する。LCD に `PRESS / BOOT BUTTON` が出たら BOOT ボタンを押す。

### 工場出荷フラッシュに戻す

保護設定前の基板に限り、退避したイメージを書き戻せる。登録済みのキーは失われる。

```
esptool.py --chip esp32s3 -p /dev/ttyACM0 write_flash 0x0 ~/orig.bin
```

## ドット絵を変える

80×96のPNGから、LCD描画用のヘッダ `esp32-lcd/mascot_80x80.h` を作る。

### 1. PNGを用意する

80×96のPNGを用意する。背景は白でよい。外周の白は抜き、絵の内側の白は残す。

### 2. ヘッダに変換する

ESP-IDFのPython環境で実行する。`絵.png` は用意したPNGファイルのパスに置き換える。

```
python3 -m pip install Pillow
python3 tools/make-lcd-image.py 絵.png esp32-lcd/mascot_80x80.h --crop --width 80 --height 96
```

`--crop` は絵の範囲まで切り抜く。同じフォルダの `mascot_80x80.preview.png` で仕上がりを確認する。

### 3. ビルドして焼き直す

PNGを変更したら、この節の「2. ヘッダに変換する」の変換コマンドをもう一度実行する。

`secure` の設定後は[本番用ファームウェアを更新する](#本番用ファームウェアを更新する)の手順でビルドして書き込む。保護設定前なら「手順」の次の3つをやり直す。

1. [5. ビルド](#5-ビルド)
2. [6. 書き込み](#6-書き込み)
3. [7. 確認](#7-確認)。認証とLCDの絵を確かめる。

### 絵を消す

```
rm esp32-lcd/mascot_80x80.h
```

ヘッダを消して焼き直すと、標準の顔に変わる。

### 文字を変える

状態の文字は `esp32-lcd/fido_status_lcd.c` の `label` と `hint` にある。色は `accent` で決めている。

## 詰まりどころ

| 現象 | 対処 |
|---|---|
| `esptool: not found` と出る | ESP-IDFのPython環境を読み込む `. ~/esp/esp-idf-v5.5.1/export.sh` を実行し、`python3 -m esptool` を使う |
| `merge-bin` が Unknown command になる | esptool 4.xでは `merge_bin` を使う |
| HID として動いている間、`/dev/ttyACM*` が消える | 書き込むときはBOOTボタンを押しながらUSBを挿し直す |
| 書き込み後もファームウェアが起動しない | BOOTボタンを離してUSBを挿し直す |
| `usbipd` がWSLのカーネルに関するエラーを出す | Windowsで `wsl --update` を実行する |
| LCD が真っ白になる、色が変、向きが違う | `LCD_CALIBRATION` / `LCD_COLOR_CAL` ビルドで校正する。BOOT ボタンを押すと候補が切り替わる |

## セキュリティプロファイル

署名検証は許可した鍵で署名したファームウェアだけを起動し、暗号化はフラッシュの読み取りを防ぐ。暗号化には次の2モードがある。

- [Developmentモード](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#development-mode)は開発用。USB更新時に基板側で暗号化でき、PCに暗号化鍵がなくても更新できる。
- [Releaseモード](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#release-mode)は本番用。USB書き込み時の基板側の暗号化を停止する。USB更新はPCで同じ鍵を使って暗号化してから行う。Developmentモードには戻せない。

`tools/security-profiles.sh` で次の設定を選ぶ。本番では署名検証も行う `secure` を使う。ビルドだけでは基板の保護設定は変わらない。

| プロファイル | 保護 | 更新用の鍵 | 解除できない設定 |
|---|---|---|---|
| `backup` | なし | 不要 | 新たな保護設定なし |
| `encrypted` | 署名検証と暗号化（Development） | 署名鍵 | 署名検証、JTAG停止 |
| `encrypted-release` | 暗号化のみ（Release） | 暗号化鍵 | 暗号化、JTAG停止、Secure Download Mode |
| `secure` | 署名検証と暗号化（Release） | 署名鍵と暗号化鍵 | 署名検証、暗号化、JTAG停止、Secure Download Mode |

表は未保護の基板に適用した場合。JTAGはデバッグ機能。Secure Download Modeは書き込みを残し、USBからの読み出しなどを制限する。

`encrypted` の暗号化解除は、設定回数のカウンターが書き込み禁止でなく、残り回数がある場合に1回だけ可能。署名検証とJTAG停止は残る。[署名検証の制約](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/secure-boot-v2.html#restrictions-after-secure-boot-is-enabled)と[暗号化の解除条件](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#disabling-flash-encryption)も参照。

## 本番用にセットアップする

以下は保護設定前の基板に `secure` を設定してサービスに登録する手順。共通の手順1〜7で登録・認証できることを確かめてから、リポジトリのフォルダで実行する。すでに `secure` を設定した基板は[更新手順](#本番用ファームウェアを更新する)を使う。

### 1. 基板の保護設定を確認する

BOOTボタンを押しながらUSBを挿し、[USB接続の手順](#2-usbデバイスをwsl2にattachする)でWSL2に接続する。

```sh
. ~/esp/esp-idf-v5.5.1/export.sh
python3 -m esptool --chip esp32s3 --no-stub -p /dev/ttyACM0 get_security_info
python3 -m espefuse --chip esp32s3 -p /dev/ttyACM0 summary \
  BLOCK_KEY0 BLOCK_KEY1 KEY_PURPOSE_0 KEY_PURPOSE_1
```

次のすべてを満たす場合だけ、この初回手順を進める。異なる場合は既存の設定と鍵を確認し、新しい鍵を上書きしない。

- `Secure Boot` と `Flash Encryption` がともに `Disabled`、`SPI_BOOT_CRYPT_CNT` が `0x0`、`Flags` が `0x00000000`。
- `Key Purposes` がすべて `USER`。`BLOCK_KEY0` と `BLOCK_KEY1` は全バイト `00` で `R/W`。
- `KEY_PURPOSE_0` と `KEY_PURPOSE_1` も `USER R/W`。

### 2. 署名鍵と暗号化鍵を作る

既存の鍵は作り直さない。暗号化鍵と保存先は基板ごとに分け、検証用の一時鍵は使わない。

```sh
umask 077
key_dir="$HOME/.config/diy-fido-key/secure-boot"
mkdir -p "$key_dir"
test -e "$key_dir/secure-boot-rsa3072.pem" || \
  python3 -m espsecure generate_signing_key --version 2 --scheme rsa3072 "$key_dir/secure-boot-rsa3072.pem"
test -e "$key_dir/flash-encryption-key.bin" || \
  python3 -m espsecure generate_flash_encryption_key --keylen 256 "$key_dir/flash-encryption-key.bin"
```

既存ファイルは上書きせず、作った鍵は所有者だけが読める権限で保存する。

### 3. 鍵の控えを別の媒体に保管する

次の `/mnt/d` と `/mnt/e` は別々のUSBメモリなどの保存先に置き換える。パスワードはコマンドの実行後に入力し、媒体とは別に保管する。

```sh
backup_a="/mnt/d/diy-fido-keys.enc"
backup_b="/mnt/e/diy-fido-keys.enc"
python3 tools/security-key-backup.py create --key-dir "$key_dir" --backup "$backup_a"
cp -i "$backup_a" "$backup_b"
python3 tools/security-key-backup.py verify --key-dir "$key_dir" --backup "$backup_a"
python3 tools/security-key-backup.py verify --key-dir "$key_dir" --backup "$backup_b"
```

両方で `Backup matches both current keys.` が出たら、媒体をPCから外して保管する。2つの控えを用意できるまでは次へ進まない。この控えは更新用の鍵であり、サービスに登録したパスキーは復元できない。

### 4. 本番用ファームウェアをビルドする

```sh
export FIDO_KEY_DIR="$key_dir"
sh tools/security-profiles.sh secure
```

出力先は `build/pico-fido-secure/`。初回は `.bin`、更新は `.enc.bin` を使う。

### 5. 暗号化鍵とファームウェアを基板に書き込む

**ここからは元に戻せない。** 基板の設定を保存するeFuseに暗号化鍵を書き込む。続く初回起動で署名検証・暗号化・JTAG停止・Secure Download Modeが設定される。`backup` に変えても解除できず、工場出荷状態にも戻せない。この手順では署名鍵と暗号化鍵も交換できない。

手順1の接続状態で、PCで作った暗号化鍵を初回起動前に保存する。基板が自動生成した鍵は取り出せない。確認画面で対象と用途を確認して承認する。

```sh
python3 -m espefuse --chip esp32s3 -p /dev/ttyACM0 burn_key \
  BLOCK_KEY0 "$key_dir/flash-encryption-key.bin" XTS_AES_128_KEY
```

成功したら次の3ファイルを書き込む。書き込み後は起動せずに待機する。

```sh
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 --after no_reset write_flash \
  0x0 build/pico-fido-secure/bootloader/bootloader.bin \
  0x10000 build/pico-fido-secure/partition_table/partition-table.bin \
  0x20000 build/pico-fido-secure/pico_fido.bin
```

書き込みが成功したらBOOTボタンを離してUSBを挿し直し、電源を抜かずにLCDの待機画面まで待つ。初回起動で暗号化と署名検証の設定が進む。[ESP-IDFの説明](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#using-host-generated-key)も参照。

`BLOCK_KEY3` と `BLOCK_KEY4` はFIDOキーの保存に使う端末内の鍵の領域なので、書き換えたり読み取り禁止にしたりしない。`DIS_DOWNLOAD_MODE` も書き込まない。書くとUSB経由の更新ができなくなる。

### 6. 保護設定とFIDO認証を確認する

BOOTボタンを押しながらUSBを挿し直し、手順1の `get_security_info` をもう一度実行する。`Secure Boot: Enabled`、`Flash Encryption: Enabled`、`SPI_BOOT_CRYPT_CNT: 0x7`、`JTAG: Permanently Disabled` と、接続時の `Secure Download Mode` の表示を確認する。どれかが異なる場合は、サービスへの登録に進まない。

BOOTボタンを押さずに挿し直し、[USB接続の手順](#2-usbデバイスをwsl2にattachする)の `usbipd detach` でWindowsに戻す。Windowsの「設定 → アカウント → サインイン オプション → セキュリティ キー → 管理」で、このキーのPINを設定する。操作は[Microsoftの案内](https://support.microsoft.com/ja-jp/accounts-billing/work-school/set-up-a-security-key-as-your-verification-method)も参照。

[認証と更新の試験](#認証と更新を確かめる)で、抜き差し・更新後も同じキーで認証できることと、ボタンを押さない場合・キャンセルした場合に認証が成功しないことを確認する。

### 7. 利用するサービスに登録する

1. 登録先で別のログイン方法を使えることを確認し、復旧コードがあれば保管する。
2. サービスのセキュリティ設定からパスキーまたはセキュリティキーを追加し、保存先にUSBのセキュリティキーを選ぶ。
3. キーのPINを入力し、LCDに `PRESS / BOOT BUTTON` が出たらBOOTボタンを押す。
4. 現在のログイン画面は残し、別のブラウザープロファイルなどで、このキーを使ってログインできることを確認する。別のログイン方法も残しておく。

認証済み製品だけを受け付けるサービスには登録できない。以後の書き換えには次の更新手順を使う。

## 本番用ファームウェアを更新する

`secure` を設定済みの基板向け。初回と同じ署名鍵・暗号化鍵を用意し、リポジトリのフォルダで実行する。

```sh
. ~/esp/esp-idf-v5.5.1/export.sh
export FIDO_KEY_DIR="$HOME/.config/diy-fido-key/secure-boot"
sh tools/security-profiles.sh secure
```

BOOTボタンを押しながらUSBを挿し、[USB接続の手順](#2-usbデバイスをwsl2にattachする)でWSL2に接続する。アプリだけを書き換える。

```sh
python3 -m esptool --chip esp32s3 --no-stub -p /dev/ttyACM0 write_flash \
  --force 0x20000 build/pico-fido-secure/pico_fido.enc.bin
```

`--force` はesptool 4.12.0の暗号化済み基板への書き込み制限を越える指定。このコマンドでは同じ鍵で署名・暗号化した `.enc.bin` に限って使う。書き込み後はBOOTボタンを押さずに挿し直し、Windowsに戻して登録済みのキーで認証する。

キーの保存領域 `part0` は `0x200000` から1MiB。位置と形式を保ち、消去しない。FIDOリセット、フラッシュ全消去、`part0` の消去、工場出荷フラッシュの書き戻しでは登録済みのキーを失う。

バージョンを上げる前に[pico-fido](https://github.com/polhenarejos/pico-fido/security/advisories)と[ESP-IDF](https://github.com/espressif/esp-idf/security/advisories)のセキュリティ情報を確認し、更新後に次の手順で認証を試す。

### 認証と更新を確かめる

```sh
python3 -m venv build/webauthn-venv
build/webauthn-venv/bin/python -m pip install -r tools/requirements-webauthn.txt
build/webauthn-venv/bin/python tools/webauthn_local_test.py
```

キーをWindowsで使える状態にし、ブラウザで `http://localhost:8787/` を開く。

1. 「テスト用キーを登録」でPINを入力してBOOTボタンを押し、「初回」→「認証を確認」を選ぶ。
2. 抜き差し後は「抜き差し後」、上の手順で更新した後は「更新後」で認証する。キーは登録し直さない。
3. BOOTボタンを押さずに待つ場合と、ブラウザでキャンセルした場合は認証が成功しないことを確かめる。

## 本番設定後にキーの設定を変える

### Windowsでキーの管理画面を開く

BOOTボタンを押さずにUSBを挿し、WSL2に接続中なら[USB接続の手順](#2-usbデバイスをwsl2にattachする)の `usbipd detach` でWindowsに戻す。Windowsの「設定 → アカウント → サインイン オプション → セキュリティ キー → 管理」を開き、本人確認を求められたらBOOTボタンを押す。

Windowsの操作は[Microsoftの案内](https://support.microsoft.com/ja-jp/accounts-billing/work-school/set-up-a-security-key-as-your-verification-method)も参照。

### PINを変更する

登録済みのキーは残る。現在のPINを忘れた場合は、キーも消える[FIDOリセット](#fidoリセットで登録済みのキーとpinを消す)が必要。

1. [キーの管理画面](#windowsでキーの管理画面を開く)を開き、「セキュリティ キー PIN」の「変更」を選ぶ。
2. 現在のPINと新しいPINを入力し、画面に従って確定する。
3. 登録済みのサービスで、新しいPINを使って認証できることを確かめる。

### FIDOリセットで登録済みのキーとPINを消す

**登録済みのキーとPINは消え、元に戻せない。** ファームウェアと署名検証・暗号化の保護設定は残る。既定ではUSBを挿し直してから10秒以内にリセットを開始する必要がある。

1. 各サービスに別の方法でログインできることを確認し、復旧コードがあれば保管する。
2. [キーの管理画面](#windowsでキーの管理画面を開く)を開き、「セキュリティ キーのリセット」の「リセット」を選ぶ。
3. 画面に従ってUSBを抜き差しし、リセットを開始する。挿し直すときはBOOTボタンを押さない。時間切れなら抜き差しからやり直す。
4. 承認を求められたらBOOTボタンを押し、画面にリセット完了が出るまで待つ。
5. 「本番用にセットアップする」の[手順6](#6-保護設定とfido認証を確認する)のPIN設定を済ませ、[手順7](#7-利用するサービスに登録する)で各サービスに登録し直す。各サービスに残った古いキーの登録も削除する。

### BOOTボタンを押すまでの待ち時間を変える

ファームウェアの既定値を変える。基板に設定を書き込むツールのPicoKey Appで0より大きい待ち時間を保存済みなら、そちらが優先されるためApp側で変える。

指定できる範囲は1〜255秒。ビルドのたびに指定し、省略時は30秒になる。

次は待ち時間を60秒にする例。[本番用ファームウェアを更新する](#本番用ファームウェアを更新する)の手順でESP-IDFと鍵の保存先を設定し、ビルドコマンドを次に置き換える。

```sh
UP_BUTTON_SECONDS=60 sh tools/security-profiles.sh secure
```

ビルドが終わったら、同じ更新手順で書き込み、認証できることを確かめる。

## 注意

- FIDO Allianceの認証は取得していない。セキュアエレメントも載せていない。個人用途、実験用、バックアップ鍵向けで、物理攻撃への耐性は保証しない

端末内での不正なコード実行や、過去のフラッシュ内容への巻き戻しに対する保護も保証しない。
