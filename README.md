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

pico-fidoとpico-keys-sdkのコミット、ESP-IDF、esptoolは `tools/esp32-build-lock.json` に固定している。ビルド時に違いがあれば停止する。ESP-IDFの追加ライブラリは `tools/esp32-dependencies.lock` を使う。

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

`tools/security-profiles.sh` は署名・暗号化したファームウェアを作るスクリプト。生成するファームウェアと実機の保護設定は別々に確認する。セキュリティ用のブートローダは初回起動時にeFuseを書き換えることがある。eFuseはチップ内の、一度書くと元に戻せない設定領域。

| プロファイル | Secure Boot | Flash Encryption | 用途 |
|---|---|---|---|
| `backup` | なし | なし | 通常ビルドと同じ。開発・更新試験用 |
| `encrypted` | RSA-3072の署名 | Developmentモード | 開発用。平文のファームウェアを書ける |
| `encrypted-release` | なし | Releaseモード | 暗号化の検証用 |
| `secure` | RSA-3072の署名 | Releaseモード | 本番向けの候補。実機の設定と試験結果を確認して使う |

各ビルドの設定は `build/pico-fido-<プロファイル>/sdkconfig` に保存する。通常ビルドは `build/pico-fido-esp32s3/sdkconfig` を使う。バージョンと生成物のSHA-256は各ビルド先の `build-info.json` に記録する。

セキュリティ用ビルドはPSRAMを40MHzで使い、見つからない場合は停止する。署名付きブートローダを置く領域を確保するため、パーティションテーブルは `0x10000` に置く。アプリとキーの保存領域の位置は通常ビルドと同じ。

### 実機の保護設定を確認する

BOOTボタンを押しながらUSBを挿し、手順2でWSL2に接続してから読む。

```
. ~/esp/esp-idf-v5.5.1/export.sh
python3 -m esptool --chip esp32s3 --no-stub -p /dev/ttyACM0 get_security_info
```

Secure Boot、Flash Encryption、Secure Download Modeと、鍵を置くeFuse領域の用途を記録する。すでに署名や暗号化が設定されている基板を更新する場合は、その基板に使った鍵が必要になる。新しい鍵を作って代用すると起動できなくなる。

ESP-IDFは本番用のフラッシュ暗号化にReleaseモードを指定している。Secure Bootは起動するファームウェアの署名を検証する。設定する順序と、その後の更新制約は[ESP-IDFのセキュリティ設定手順](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/security/security-features-enablement-workflows.html)で確認する。

### 新しい基板に使う署名鍵と暗号化鍵を用意する

実機の設定を読み、既存の鍵を使う必要がないと確認してから行う。すでにあるファイルは上書きしない。

```
umask 077
mkdir -p ~/.config/diy-fido-key/secure-boot
test -e ~/.config/diy-fido-key/secure-boot/secure-boot-rsa3072.pem || \
  python3 -m espsecure generate_signing_key --version 2 --scheme rsa3072 \
  ~/.config/diy-fido-key/secure-boot/secure-boot-rsa3072.pem
test -e ~/.config/diy-fido-key/secure-boot/flash-encryption-key.bin || \
  python3 -m espsecure generate_flash_encryption_key \
  ~/.config/diy-fido-key/secure-boot/flash-encryption-key.bin
```

署名鍵はRSA-3072、フラッシュ暗号化鍵は32バイト。ビルドスクリプトは鍵が無い場合や、鍵を他の利用者が読める権限になっている場合に停止する。保存先を変えるときは `FIDO_KEY_DIR` にそのフォルダを指定する。

### 鍵を暗号化して退避する

`tools/security-key-backup.py` は、署名鍵とフラッシュ暗号化鍵をパスワードで暗号化した1つのファイルに保存する。Scryptでパスワードから暗号鍵を作り、AES-256-GCMで暗号化し、改ざんを検出する。パスワードは端末の入力欄に入れる。

```
python3 tools/security-key-backup.py create \
  --key-dir ~/.config/diy-fido-key/secure-boot \
  --backup /退避先/security-keys.enc
python3 tools/security-key-backup.py verify \
  --key-dir ~/.config/diy-fido-key/secure-boot \
  --backup /退避先/security-keys.enc
```

PCから切り離して保管する2つの媒体へコピーし、それぞれで `verify` を通す。パスワードはバックアップファイルと別に保管する。復旧時は `restore` を使い、`--key-dir` にまだ存在しないフォルダを指定する。

ここで退避するのはファームウェアの署名鍵と暗号化鍵。サービスに登録したパスキーの復旧には、そのサービスの別のログイン方法や復旧コードを用意する。工場出荷時の `orig.bin` には、退避後に登録したパスキーは入っていない。

### 署名・暗号化したファームウェアを作る

```
. ~/esp/esp-idf-v5.5.1/export.sh
sh tools/security-profiles.sh secure
```

BOOTボタンの待ち時間は既定30秒。`UP_BUTTON_SECONDS` で1〜255秒を指定できる。セキュリティ用ビルドでは、基板に保存された設定が0秒でも既定の待ち時間を使う。

ブートローダとアプリの署名を検証してから、次の3つをそれぞれの書き込み位置に合わせて暗号化する。

| ファイル | 書き込み位置 |
|---|---|
| `build/pico-fido-secure/bootloader/bootloader.enc.bin` | `0x0` |
| `build/pico-fido-secure/partition_table/partition-table.enc.bin` | `0x10000` |
| `build/pico-fido-secure/pico_fido.enc.bin` | `0x20000` |

実機への初回書き込みは、読み取ったeFuseの状態、使用する鍵、書き込むファイルと位置を照合してから行う。署名や暗号化の設定を始める前に、前節の鍵の退避と、次節の実機試験を済ませる。検証用の一時鍵で作ったファームウェアは、実機へ書く候補から外す。

### 登録したキーが更新後も使えることを確かめる

試験用のPython環境を作り、ローカルの試験ページを起動する。

```
python3 -m venv build/webauthn-venv
build/webauthn-venv/bin/python -m pip install -r tools/requirements-webauthn.txt
build/webauthn-venv/bin/python tools/webauthn_local_test.py
```

Windowsのブラウザで `http://localhost:8787/` を開き、次の順に確かめる。WSL2にキーを接続している場合は、手順2の `usbipd detach` でWindowsに戻す。

1. 「テスト用キーを登録」を押し、PINを入力してBOOTボタンで承認する。
2. 「初回」を選び、「認証を確認」を押す。
3. キーを抜き差しし、「抜き差し後」を選んで同じキーで認証する。
4. 実機の保護設定に合う更新用ファームウェアを書き込み、「更新後」を選んで同じキーで認証する。
5. BOOTボタンを押さずに待つ場合と、ブラウザでキャンセルした場合に、認証が成功しないことを確かめる。

ページはサーバー側で署名、認証ごとの確認要求、接続元、本人確認とボタン承認のフラグを検証する。公開鍵と試験記録は `build/webauthn-verification/` に残る。更新試験が終わるまでこのフォルダを保管する。PINを間違える試験はロックの原因になるため、通常の保持試験には含めない。

### 保存領域と更新時の条件

資格情報は `part0`（`0x200000`から1MiB）に保存する。この領域にはハードウェア暗号化のフラグを付けていない。pico-fidoは端末の秘密鍵をソフトウェア側で暗号化し、端末内のeFuseにある鍵から復号用の鍵を作る。鍵の内容はファームウェアから読める設計なので、Secure Bootとデバッグ経路の制限も合わせて確認する。

eFuseの `BLOCK_KEY3` と `BLOCK_KEY4` はPico Keys SDKが使う。この2つを読み取り禁止にすると、現在の実装は鍵を取り出せなくなる。読み取りエラーや用途の不一致を検出した場合は、空の鍵で処理を続けず停止する。保存領域やPSRAMの確保・読み書きの失敗も停止させる。

更新では、同じ保存領域の位置と形式、同じ端末内の鍵を使う。保存領域に重ならないアプリを `0x20000` に書く方法を基本とし、署名・暗号化済みの実機には、その実機に合う署名・暗号化済みのアプリを使う。ブートローダやパーティションテーブルを変える場合は、通常のアプリ更新と分けて確認する。

FIDOリセット、フラッシュ全消去、`part0` の消去、工場出荷時イメージの書き戻しは、登録済みのキーを失う操作になる。保存領域の移動や形式変更には移行手順が必要。

### 本番で使い始める前と、その後の確認

- 各サービスに別のログイン方法を登録し、復旧コードを保管する。登録済みサービスが無い場合は、本番のキーを登録するときに用意する。
- 実機の保護設定、署名鍵の公開情報、使った `build-info.json`、初回・抜き差し後・更新後の試験記録を保管する。
- 署名鍵と暗号化鍵の退避を2箇所で確かめてから、eFuseの設定を進める。USB経由で更新するこの構成では、`DIS_DOWNLOAD_MODE` を書くと更新経路が閉じる。
- 更新前に[pico-fidoのセキュリティ情報](https://github.com/polhenarejos/pico-fido/security/advisories)と[ESP-IDFのセキュリティ情報](https://github.com/espressif/esp-idf/security/advisories)を確認する。固定バージョンを変えたら、ビルドとキー保持の試験をやり直す。

固定したpico-fidoのコミットには、2026年11月2日までに公開されたPIN入力長、PINロック、ボタン承認、バックアップ復元、OTP処理に関する5件の修正を含む。コードに修正が入っていることを確認した結果であり、すべての攻撃への耐性を保証するものではない。

ソフトウェアの脆弱性で端末内のコードを実行される攻撃や、物理的な故障注入、過去のフラッシュ内容への巻き戻しへの耐性は未検証。これらを防ぐことが運用条件に含まれる場合は、追加の評価が終わるまで本番利用の条件を満たさない。

## 注意

- FIDO Allianceの認証は取得していない。セキュアエレメントも載せていない。個人用途、実験用、バックアップ鍵向けで、物理攻撃は守備範囲外
