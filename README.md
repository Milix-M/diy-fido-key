# diy-fido-key

ESP32-S3とST7735 80×160のLCDを載せたボードを、USB FIDO2キーにするファームウェア。パスキーの登録と認証ができ、LCDには登録待ちや処理中といった状態を出す。

## 対象

| 区分 | デバイス |
|---|---|
| 対象 | ESP32-S3と0.96インチST7735S 80×160のLCDを載せたボード |
| 対象外 | LCDの無いボード、ESP32-C3、ESP32（無印）、ESP32-C6、ESP32-H2 |

このREADMEでは上のボードをWindows 11とWSL2 Ubuntuで使う手順を説明する。

## 元のリポジトリからの変更

- **sdkconfig書き換えバグの修正**
  - `tools/build-pico-fido-esp32s3.sh` は `sdkconfig` を書き換えたあとに `idf.py set-target` を実行していた
  - `set-target` は `sdkconfig` を削除して作り直すので、書き換えた設定は消えていた
  - 書き換えを `set-target` のあとに移した
- **結合コマンドの修正**
  - スクリプトは最後に `esptool` の `merge-bin` を呼んでいた
  - esptool 4.x にこのサブコマンドは無いので、そこでエラーになって止まっていた
  - `python3 -m esptool merge_bin` に変えた
- **BOOTボタンでの承認**
  - `pico-keys-sdk/src/button.c` の `button_timeout_seconds()` は、ボタンの設定が空の基板では待ち時間に0を返していた
  - 0のときファームはボタンを待たずに承認するので、BOOTボタンを押さなくても認証が通っていた
  - 既定を30秒に変え、押すまで承認しないようにした

## 必要なもの

### ハードウェア

| 項目 | 内容 |
|---|---|
| ボード | [AliExpressのESP32-S3 LCD付きボード](https://ja.aliexpress.com/item/1005009024098181.html)。Flash 16MB、PSRAM 8MB。0.96インチST7735S 80×160のLCD付き |
| USBケーブル | データ通信ができるもの |

### ソフトウェア

| 項目 | 内容 |
|---|---|
| ESP-IDF | v5.5.1 |
| esptool | 4.12.0。手順1で入れるESP-IDFのPython環境で使う |
| Python | 3.9以降。手順1のinstall.shが使う |

ESP-IDFはファームウェアをビルドする開発環境、esptoolは基板に書き込むツール。手順1でインストールする。WindowsのUSBをWSL2へ渡すusbipd-winは[USB接続の手順](#2-usbデバイスをwsl2にattachする)でインストールする。

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

`flash_id` でFlashの容量が16MBであることを確認してから、16MiBを読み取る。

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

ビルドに使うバージョンは [esp32-build-lock.json](tools/esp32-build-lock.json) と [esp32-dependencies.lock](tools/esp32-dependencies.lock) で固定している。更新するときは設定も変更し、ビルドと実機試験をやり直す。

### 5. ビルド

```
. ~/esp/esp-idf-v5.5.1/export.sh
sh tools/build-pico-fido-esp32s3.sh
```

スクリプトは LCD のパッチ適用、set-target、sdkconfig の書き換え、ボタン待ちの設定、ビルド、イメージの結合までをまとめて行う。BOOTボタンを押すまでの待ち時間は `UP_BUTTON_SECONDS` で変えられる。既定は 30 秒。

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

LCDの絵は `esp32-lcd/mascot_80x80.h` に入っている。画面の上から4px下に80×96で置き、状態の文字はその下に描く。

### 1. PNGを用意する

80×96ちょうどの大きさにする。それ以外の大きさだと縮小されてドットがぼける。背景は白でよい。外周から白を塗りつぶして抜くので、絵の内側の白は残る。

### 2. ヘッダに変換する

```
python3 -m pip install Pillow
python3 tools/make-lcd-image.py 絵.png esp32-lcd/mascot_80x80.h --crop --width 80 --height 96
```

`--crop` は絵の範囲まで切り抜く。余白を足すときは `--padding 4` を付ける。同じフォルダに `mascot_80x80.preview.png` が出る。黒地に4倍で描いた確認用の画像。

### 3. ビルドして焼き直す

`secure` の設定後は[本番用ファームウェアを更新する](#本番用ファームウェアを更新する)の手順でビルドして書き込む。以下は保護設定前の手順。

PNGを変更したら、この節の「2. ヘッダに変換する」の変換コマンドをもう一度実行し、続けて「手順」の次の3つをやり直す。

1. [5. ビルド](#5-ビルド)で、新しいヘッダを含むファームウェアを作る。
2. [6. 書き込み](#6-書き込み)で、ボードに書き込む。
3. [7. 確認](#7-確認)で、認証とLCDの絵を確かめる。

ビルドスクリプトが `tools/install-esp32-lcd.sh` を呼ぶので、ヘッダは `vendor/pico-fido/pico-keys-sdk/src/lcd/` に入る。

### 絵を消す

```
rm esp32-lcd/mascot_80x80.h
```

`install-esp32-lcd.sh` がヘッダの有無を見て、簡単な顔のプレースホルダに切り替える。

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

`tools/security-profiles.sh` は、署名・暗号化の設定を選んでファームウェアを作る。署名検証は許可した鍵で署名したファームウェアだけを起動し、フラッシュ暗号化は保存したファームウェアの読み取りを防ぐ。ビルドだけでは基板の設定は変わらない。

DevelopmentとReleaseはフラッシュ暗号化のモードで、更新時に使える暗号化機能が異なる。

- [Developmentモード](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#development-mode)は開発・検証用。USBで送ったファームウェアを基板側で暗号化しながら書き込めるため、PCに暗号化鍵がなくても更新できる。
- [Releaseモード](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#release-mode)は本番用。USB書き込み時に基板側で暗号化する機能を停止する。USB経由の更新にはその基板と同じ暗号化鍵でPC側で暗号化したファイルを使う。設定後はDevelopmentモードに戻せない。

署名検証の有無は暗号化モードとは別に決まる。このリポジトリでは本番用に署名検証も組み合わせた `secure` を使う。

| プロファイル | 保護の内容 | 更新に必要なもの | 解除できない設定 |
|---|---|---|---|
| `backup` | 署名検証・暗号化なし | 通常のファームウェア | 新たな保護設定なし |
| `encrypted` | 署名検証とDevelopmentモードの暗号化 | 署名鍵。基板側で暗号化して書き込む | 署名検証、JTAG停止 |
| `encrypted-release` | Releaseモードの暗号化 | 暗号化鍵。PCで暗号化して書き込む | 暗号化、JTAG停止、Secure Download Mode |
| `secure` | 署名検証とReleaseモードの暗号化 | 署名鍵と暗号化鍵。PCで署名・暗号化して書き込む | 署名検証、暗号化、JTAG停止、Secure Download Mode |

表は保護設定前の基板に各設定を適用した場合の違い。JTAGはデバッグ用の接続機能。Secure Download Modeは書き込みを残し、読み出しなどを制限するモード。

`encrypted` の暗号化解除は、設定回数のカウンターが書き込み禁止でなく、残り回数がある場合に1回だけ可能。署名検証とJTAG停止は残る。`encrypted-release` は署名を検証しない。[署名検証の制約](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/secure-boot-v2.html#restrictions-after-secure-boot-is-enabled)と[暗号化の解除条件](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#disabling-flash-encryption)も参照。

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

署名鍵はファームウェアの署名に使い、暗号化鍵はフラッシュの暗号化に使う。既存の鍵があれば、その鍵を使う。暗号化鍵は基板ごとに別のものを用意し、保存先も分ける。検証用の一時鍵は本番に使わない。

```sh
umask 077
key_dir="$HOME/.config/diy-fido-key/secure-boot"
mkdir -p "$key_dir"
test -e "$key_dir/secure-boot-rsa3072.pem" || \
  python3 -m espsecure generate_signing_key --version 2 --scheme rsa3072 "$key_dir/secure-boot-rsa3072.pem"
test -e "$key_dir/flash-encryption-key.bin" || \
  python3 -m espsecure generate_flash_encryption_key --keylen 256 "$key_dir/flash-encryption-key.bin"
```

RSA-3072の署名鍵と32バイトの暗号化鍵を、所有者だけが読めるファイルとして保存する。既存ファイルは上書きしない。

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

`build/pico-fido-secure/` にファームウェアとビルド記録を作る。初回は `.bin`、保護設定後の更新は `.enc.bin` を使う。BOOTボタンの待ち時間は既定30秒で、ビルド時に `UP_BUTTON_SECONDS` で1〜255秒に変えられる。

### 5. 暗号化鍵とファームウェアを基板に書き込む

**ここからは元に戻せない。** 基板の設定を保存するeFuseに暗号化鍵を書き込む。続く初回起動で署名検証・暗号化・JTAG停止・Secure Download Modeが設定される。`backup` に変えても解除できず、工場出荷状態にも戻せない。この手順では署名鍵と暗号化鍵も交換できない。

暗号化鍵を基板が自動生成するとPCへ取り出せないため、初回起動前にPCで作った鍵を保存する。手順1の接続状態で、暗号化鍵を `BLOCK_KEY0` に書き込む。ツールの確認画面で対象と用途を確認してから承認する。

```sh
python3 -m espefuse --chip esp32s3 -p /dev/ttyACM0 burn_key \
  BLOCK_KEY0 "$key_dir/flash-encryption-key.bin" XTS_AES_128_KEY
```

成功した場合だけ、次を実行する。初回用の署名済みファイルを3か所に書き込み、書き込み後は起動させずに待機する。

```sh
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 --after no_reset write_flash \
  0x0 build/pico-fido-secure/bootloader/bootloader.bin \
  0x10000 build/pico-fido-secure/partition_table/partition-table.bin \
  0x20000 build/pico-fido-secure/pico_fido.bin
```

3ファイルの書き込みが成功したら、BOOTボタンを離してUSBを挿し直す。初回起動では基板がフラッシュを暗号化し、署名検証用の公開鍵のハッシュを `BLOCK_KEY1` に保存する。起動処理中は電源を抜かず、LCDに待機画面が出るまで待つ。[PCで作った暗号化鍵を使う手順](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#using-host-generated-key)に基づく。

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

サービスが認証済み製品だけを受け付ける場合、このキーは登録できない。設定が終わったら、次回以降は以下の更新手順を使う。

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

1. 「テスト用キーを登録」でPINを入力し、BOOTボタンで承認する。「初回」を選び、「認証を確認」を押す。
2. キーを抜き差しし、「抜き差し後」を選んで認証する。
3. 上の更新手順でアプリを書き換え、「更新後」を選んで認証する。キーは登録し直さない。
4. BOOTボタンを押さずに待つ場合と、ブラウザでキャンセルした場合に認証が成功しないことを確かめる。

試験記録は `build/webauthn-verification/` に保存する。

## 本番設定後にキーの設定を変える

### Windowsでキーの管理画面を開く

1. BOOTボタンを押さずにUSBを挿す。WSL2に接続中なら、[USB接続の手順](#2-usbデバイスをwsl2にattachする)の `usbipd detach` でWindowsに戻す。
2. Windowsの「設定 → アカウント → サインイン オプション → セキュリティ キー → 管理」を開く。本人確認を求められたらBOOTボタンを押す。

Windowsの操作は[Microsoftの案内](https://support.microsoft.com/ja-jp/accounts-billing/work-school/set-up-a-security-key-as-your-verification-method)も参照。

### PINを変更する

1. 上の手順でキーの管理画面を開き、「セキュリティ キー PIN」の「変更」を選ぶ。
2. 現在のPINと新しいPINを入力し、画面に従って確定する。
3. 登録済みのサービスで、新しいPINを使って認証できることを確かめる。

PINの変更では登録済みのキーは消えない。現在のPINを忘れた場合は、次のFIDOリセットで登録済みのキーも消して設定し直す必要がある。

### FIDOリセットで登録済みのキーとPINを消す

**登録済みのキーとPINは消え、元に戻せない。** ファームウェアと署名検証・暗号化の保護設定は残る。

1. 各サービスに別の方法でログインできることを確認し、復旧コードがあれば保管する。
2. [キーの管理画面](#windowsでキーの管理画面を開く)を開き、「セキュリティ キーのリセット」の「リセット」を選ぶ。
3. 画面に従ってUSBを抜き差しし、リセットを開始する。挿し直すときはBOOTボタンを押さない。既定では挿し直してから10秒以内にリセットを開始する必要がある。時間切れなら抜き差しからやり直す。
4. 承認を求められたらBOOTボタンを押し、画面にリセット完了が出るまで待つ。
5. 「本番用にセットアップする」の[手順6](#6-保護設定とfido認証を確認する)でPINを設定し、[手順7](#7-利用するサービスに登録する)で各サービスに登録し直す。各サービスに残った古いキーの登録も削除する。

### BOOTボタンを押すまでの待ち時間を変える

次は待ち時間を60秒にする例。[本番用ファームウェアを更新する](#本番用ファームウェアを更新する)の手順でESP-IDFと鍵の保存先を設定し、ビルドコマンドを次に置き換える。

```sh
UP_BUTTON_SECONDS=60 sh tools/security-profiles.sh secure
```

そのあと、同じ更新手順の書き込みと認証確認を行う。指定できる範囲は1〜255秒。この指定はビルドのたびに必要で、省略すると既定の30秒になる。

この値はファームウェアの既定値。基板の設定を書き込むツールPicoKey Appで、0より大きい待ち時間を保存している場合はそちらが優先される。その場合はPicoKey App側の値を変更する。

## 注意

- FIDO Allianceの認証は取得していない。セキュアエレメントも載せていない。個人用途、実験用、バックアップ鍵向けで、物理攻撃への耐性は保証しない

端末内での不正なコード実行や、過去のフラッシュ内容への巻き戻しに対する保護も保証しない。
