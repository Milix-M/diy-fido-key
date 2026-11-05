# diy-fido-key

ESP32-S3とST7735 80×160のLCDを載せたボードを、USB FIDO2キーにするファームウェア。パスキーの登録と認証ができ、LCDには登録待ちや処理中といった状態を出す。

## 対象

| 区分 | デバイス |
|---|---|
| 対象 | ESP32-S3と0.96インチST7735S 80×160のLCDを載せたボード |
| 対象外 | LCDの無いボード、ESP32-C3、ESP32（無印）、ESP32-C6、ESP32-H2 |

このリポジトリは上の構成以外で動くことを確かめていない。対象外のチップにはUSB-OTGのデバイスモードが無いため、USBキーとしても認識されない。

## 元のリポジトリからの変更

- **sdkconfig書き換えバグの修正**
  - `tools/build-pico-fido-esp32s3.sh` は `sdkconfig` を書き換えたあとに `idf.py set-target` を実行していた
  - `set-target` は `sdkconfig` を削除して作り直すので、書き換えた設定は消えていた
  - 書き換えを `set-target` のあとに移した
- **結合コマンドの修正**
  - スクリプトは最後に `esptool` の `merge-bin` を呼んでいた
  - esptool 4.x にこのサブコマンドは無いので、そこでエラーになって止まっていた
  - `python3 -m esptool merge_bin` に変えた
- **BOOTボタン押下の必須化**
  - `pico-keys-sdk/src/button.c` の `button_timeout_seconds()` は、ボタンの設定が空の基板では待ち時間に0を返していた
  - 0のときファームはボタンを待たずに承認するので、BOOTボタンを押さなくても認証が通っていた
  - 既定を30秒に変え、押すまで承認しないようにした

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
| esptool | 4.12.0。手順1で入れるESP-IDFのPython環境で使う |
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
| `esptool: not found` と出る | ESP-IDF の venv には `esptool.py` という名前で入る。`export.sh` を読んでから、`esptool.py` か `python3 -m esptool` を使う |
| `merge-bin` が Unknown command になる | esptool 4.x のサブコマンドはアンダースコアのみ。`merge_bin` を使う |
| HID として動いている間、`/dev/ttyACM*` が消える | 再書き込みのたびに、BOOT ボタンを押しながら挿し直す |
| BOOT ボタンを押したまま起動して ROM ダウンロードモードに固定される | 焼いたあとに BOOT ボタンを離す |
| `usbipd` がカーネル非対応と言う | `wsl --update` を実行する |
| LCD が真っ白になる、色が変、向きが違う | `LCD_CALIBRATION` / `LCD_COLOR_CAL` ビルドで校正する。BOOT ボタンを押すと候補が切り替わる |

## セキュリティプロファイル

`tools/security-profiles.sh` で署名・暗号化したファームウェアを作る。表は未保護の基板に各設定を適用した後の違い。ビルドだけでは実機の設定は変わらない。

| プロファイル | 保護機能 | できる更新 | 戻せなくなること |
|---|---|---|---|
| `backup` | 署名検証・暗号化なし | 通常の書き込み | 保護設定は追加しない |
| `encrypted` | 署名検証＋Developmentモードの暗号化 | 署名済みファームウェアを基板側で暗号化して書き込める | 署名検証とJTAG停止は解除できない |
| `encrypted-release` | Releaseモードの暗号化。署名検証なし | 暗号化鍵を使い、PCで暗号化してから書き込める | 暗号化・JTAG停止・Secure Download Modeを解除できない |
| `secure` | 署名検証＋Releaseモードの暗号化 | 署名鍵と暗号化鍵を使い、署名・暗号化してから書き込める | 署名検証・暗号化・JTAG停止・Secure Download Modeを解除できない |

JTAGはデバッグ用の接続機能。Secure Download Modeは書き込みを残し、読み出しなどを制限するモード。`encrypted` の暗号化解除は、設定回数のカウンターが書き込み禁止でなく、残り回数がある場合に1回だけ可能。ただし署名検証とJTAG停止は残る。[署名検証の制約](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/secure-boot-v2.html#restrictions-after-secure-boot-is-enabled)と[暗号化の解除条件](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/security/flash-encryption.html#disabling-flash-encryption)も参照。

`backup` を選び直しても、実機に書いた保護設定は元に戻らない。実機に書き込んで保護した暗号化鍵も消去・交換できない。`secure` は本番向けの候補で、設定後の実機試験が必要。

暗号化鍵を基板が自動生成した場合はPCへ取り出せない。ReleaseモードでPCから更新するには、PCで作った鍵を初回起動前に基板へ設定し、その控えを保管しておく。

### 鍵を作る（初回のみ）

`secure` 用に署名鍵（RSA-3072）と暗号化鍵（32バイト）を作る。すでに鍵がある場合は作り直さない。

1. BOOTボタンを押しながらUSBを挿し、手順2でWSL2に接続して実機の設定を読む。署名・暗号化済みなら、その基板に使った鍵を用意し、2・3は行わない。

   ```sh
   . ~/esp/esp-idf-v5.5.1/export.sh
   python3 -m esptool --chip esp32s3 --no-stub -p /dev/ttyACM0 get_security_info
   ```

2. 所有者だけが読める権限でファイルを作るようにし、保存先を用意する。

   ```sh
   umask 077
   key_dir="$HOME/.config/diy-fido-key/secure-boot"
   mkdir -p "$key_dir"
   ```

3. 署名鍵と暗号化鍵を作る。次のコマンドは既存ファイルを上書きしない。

   ```sh
   test -e "$key_dir/secure-boot-rsa3072.pem" || \
     python3 -m espsecure generate_signing_key --version 2 --scheme rsa3072 "$key_dir/secure-boot-rsa3072.pem"
   test -e "$key_dir/flash-encryption-key.bin" || \
     python3 -m espsecure generate_flash_encryption_key --keylen 256 "$key_dir/flash-encryption-key.bin"
   ```

作成後は「本番で使う前に」に沿って鍵を退避する。ここまでの操作は実機に鍵を書き込まない。暗号化鍵は基板ごとに別のものを使う。

### ビルドする

```sh
. ~/esp/esp-idf-v5.5.1/export.sh
sh tools/security-profiles.sh secure
```

生成物とビルドの記録（`build-info.json`）は `build/pico-fido-secure/` に保存する。BOOTボタンの待ち時間は既定30秒で、`UP_BUTTON_SECONDS` に1〜255秒を指定できる。

### 本番で使う前に

- 実機の保護設定を読み、使う鍵と書き込み位置を確認する。署名・暗号化済みの基板には既存の鍵を使う。
- 署名鍵と暗号化鍵を [security-key-backup.py](tools/security-key-backup.py) の `create` でパスワードを付けて暗号化し、退避する。PCから切り離して保管する2つの媒体にコピーし、それぞれで `verify` を通す。パスワードは別に保管する。
- 各サービスに別のログイン方法を用意し、復旧コードを保管する。この退避ファイルから、サービスに登録したパスキーは復元できない。
- 鍵の退避と次節の試験を済ませてから、[ESP-IDFの手順](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/security/security-features-enablement-workflows.html)で保護設定を進める。設定後も認証・更新を確かめる。検証用の一時鍵は本番に使わない。

保護設定を保存するeFuseは一度書くと元に戻せない。セキュリティ用のブートローダは初回起動時にeFuseを書き換えることがある。`DIS_DOWNLOAD_MODE` を書くとUSB経由で更新できなくなる。

### 更新後も同じキーで認証できるか確かめる

```sh
python3 -m venv build/webauthn-venv
build/webauthn-venv/bin/python -m pip install -r tools/requirements-webauthn.txt
build/webauthn-venv/bin/python tools/webauthn_local_test.py
```

WSL2に接続中のキーは手順2の `usbipd detach` でWindowsに戻す。ブラウザで `http://localhost:8787/` を開く。

1. 「テスト用キーを登録」を押し、PINを入力してBOOTボタンで承認する。「初回」を選び、「認証を確認」を押す。
2. キーを抜き差しし、「抜き差し後」を選んで認証する。
3. 実機の保護設定に合うファームウェアへ更新し、「更新後」を選んで認証する。キーは登録し直さない。
4. BOOTボタンを押さずに待つ場合と、ブラウザでキャンセルした場合に認証が成功しないことを確かめる。

試験記録は `build/webauthn-verification/` に残る。更新ではアプリ（`0x20000`）だけを書き換える方法を基本とし、キーの保存領域 `part0`（`0x200000`から1MiB）の位置と形式を保つ。

FIDOリセット、フラッシュ全消去、`part0` の消去、工場出荷フラッシュの書き戻しでは、登録済みのキーを失う。端末内の鍵がある `BLOCK_KEY3` と `BLOCK_KEY4` も読み取り禁止にしない。

バージョンを更新する前に[pico-fido](https://github.com/polhenarejos/pico-fido/security/advisories)と[ESP-IDF](https://github.com/espressif/esp-idf/security/advisories)のセキュリティ情報を確認し、更新後に同じ試験をやり直す。端末内のコード実行、物理的な故障注入、過去のフラッシュ内容への巻き戻しに対する耐性は未検証。

## 注意

- FIDO Allianceの認証は取得していない。セキュアエレメントも載せていない。個人用途、実験用、バックアップ鍵向けで、物理攻撃は守備範囲外
