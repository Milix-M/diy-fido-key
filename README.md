# diy-fido-key

ESP32-S3とST7735 80×160のLCDを載せたボードを、USB FIDO2キーにするファームウェア。パスキーの登録と認証ができ、LCDには登録待ちや処理中といった状態を出す。

## 対象

| 区分 | デバイス |
|---|---|
| 対象 | ESP32-S3と0.96インチST7735S 80×160のLCDを載せたボード |
| 対象外 | LCDの無いボード、ESP32-C3、ESP32（無印）、ESP32-C6、ESP32-H2 |

このリポジトリは上の構成以外で動くことを確かめていない。対象外のチップにはUSB-OTGのデバイスモードが無いため、USBキーとしても認識されない。

## 変更点

元のリポジトリのままでは、設定が反映されないまま書き込みが終わる。3点を直した。

- 設定の書き換えが消える。`tools/build-pico-fido-esp32s3.sh` が `idf.py set-target` より先に `sdkconfig` を書き換えており、`set-target` が `sdkconfig` を作り直すため
- 最後の結合が `merge-bin` を呼んで落ちる。esptool 4.x にこの名前は無い
- ボタンを押さなくても認証が通る。設定を書き込んでいない基板では、ボタン待ちの時間が0になるため

原因と根拠は[SETUP.md](SETUP.md)に書いた。

## 必要なもの

### ハードウェア

| 項目 | 内容 |
|---|---|
| ボード | ESP32-S3。Flash 16MB、PSRAM 8MB、USB-OTGのデバイスモードに対応したもの |
| LCD | 0.96インチ ST7735S 80×160。この構成では必須 |
| USBケーブル | データ通信に対応したもの |

LCDとESP32-S3のピンは次のように接続する。

| LCDの信号 | ESP32-S3のピン |
|---|---|
| SCLK | GPIO10 |
| MOSI | GPIO11 |
| CS | GPIO12 |
| DC | GPIO13 |
| RST | GPIO14 |

BOOTボタンは基板の裏にある。GPIO0につながっている。

### ソフトウェア

| 項目 | 内容 |
|---|---|
| ESP-IDF | v5.5.1 |
| esptool | 4.x。ESP-IDFに同梱される |
| Python | 3.9以降 |

## 使い方

焼き方と環境の作り方は[SETUP.md](SETUP.md)にある。

## 注意

- `tools/security-profiles.sh secure`を実行する操作と、eFuseを焼く操作は戻せない。[docs/security-profiles.md](docs/security-profiles.md)を読んでから実施する
- Flash Encryptionを有効にするとSecure Download Modeになり、`read_flash`が通らなくなる。退避は最初に済ませる
- FIDO Allianceの認証は取得していない。セキュアエレメントも載せていない。個人用途、実験用、バックアップ鍵向けで、物理攻撃は守備範囲外
- バイナリを配布する場合はVID/PIDとライセンスの条件がある。[docs/distribution.md](docs/distribution.md)

## リンク

- [SETUP.md](SETUP.md) セットアップ手順、直した理由、詰まりどころ
- [docs/security-profiles.md](docs/security-profiles.md) 保護機能と不可逆な操作
- [docs/distribution.md](docs/distribution.md) 公開・配布の条件
- [docs/README.original.md](docs/README.original.md) 元のREADME
- ファームウェア本体 <https://github.com/polhenarejos/pico-fido>
- 元になった紹介記事 <https://www.makeuseof.com/made-own-yubikey-less-than-8/>
