# セキュリティプロファイル（ESP32-S3）

`tools/security-profiles.sh` で保護レベルを切り替える。**スクリプトはeFuseを焼かない**。ビルドと手順書だけを出す。実機では下記のeFuseが焼かれている。

| プロファイル | Secure Boot | Flash Encryption | 用途 |
|---|---|---|---|
| `backup` | なし | なし | 開発・検証（再書き込み自由） |
| `encrypted` | RSA-3072で署名（eFuseは焼かない） | development | 暗号化の試行 |
| `encrypted-release` | なし | release | 暗号化の試行用。SDMでは署名が無いため起動しない（実測） |
| `secure` | RSA-3072（署名） | release | 実機で動作確認した構成 |

## 実機で確定した構成（2026-10-23）

- ESP32-S3のSecure Boot v2はRSA-3072のみ。ECDSAは非対応で、ECDSA鍵では起動時の署名検証に失敗する
- Flash Encryptionを有効にするとSecure Download Mode (SDM) になる。SDMでは`read-flash`、`chip-id`、eFuseの読み出しができず、署名済みブートローダが要る。書き込みは`--force`と事前暗号化イメージを使う
- pico-fidoは`part0`をmmapするが、暗号化が有効だとmmapが復号するため平文のFSと一致しない。`patches/pico-fido-psram-shadow.patch`でPSRAM上のシャドウに置き換え、`esp_flash_read/write`（平文）で読み書きする。`part0`には暗号化フラグを付けない
- PSRAMは40MHz、`CONFIG_SPIRAM_IGNORE_NOTFOUND=y`（未搭載でも起動する）
- 署名付きブートローダは32KBを超える。Secure Bootを含むプロファイルはパーティションテーブルを0x10000へ移す。`encrypted-release`は0x9000

## 鍵

- 署名鍵（RSA-3072）: `~/.config/diy-fido-key/secure-boot/secure-boot-rsa3072.pem`
- フラッシュ暗号化鍵: `~/.config/diy-fido-key/secure-boot/flash-encryption-key.bin`
- どちらもオフラインで2箇所に保管する。失うと更新できなくなる

## SDM有効後の焼き方

```sh
# ビルド（事前暗号化まで）
sh tools/security-profiles.sh secure
# 書き込み（SDM では --force、スタブなし）
esptool --port /dev/cu.usbmodemXXXX write-flash --force 0x0 build/pico-fido-secure/pico_fido_secure.enc.bin
```

書き込み後はBOOTを離してUSBを挿し直す。`part0`のレイアウトを変えたときだけ、`esptool --port ... erase-region 0x200000 0x100000`で保存領域を作り直す。

## 再書き込み不可にする操作

完成したイメージで十分に動作確認してから、最後に実施する。**どれも戻せない。**

| 操作 | 効果 | 戻せる |
|---|---|---|
| `SECURE_BOOT_EN` + digest | 署名済みイメージのみ起動（更新には署名鍵が要る） | 不可 |
| `DIS_DOWNLOAD_MODE` | ROMダウンロードモードを無効化し、再書き込み不可にする | 不可 |
| `DIS_USB_JTAG` / `DIS_PAD_JTAG` | JTAG経路を無効化 | 不可 |
| pico-fido Secure Lock | MKEKをOTPに固定し、資格情報を端末に紐付ける | 不可 |

```sh
# 最後に実行する。事前に署名済みイメージでの起動確認と鍵の退避を済ませること
espefuse.py --port /dev/cu.usbmodemXXXX burn_efuse DIS_DOWNLOAD_MODE
espefuse.py --port /dev/cu.usbmodemXXXX burn_efuse DIS_USB_JTAG
```

注意。

- `DIS_DOWNLOAD_MODE`を焼くと二度と書き込めなくなる。失敗したら基板ごと交換になる
- 署名鍵と暗号化鍵の控えが無い状態で焼かない
- 現行機は未実施。`DIS_DOWNLOAD_MODE`は焼いていないので、まだ更新できる
- 書き込み経路を残す限り、`SECURE_BOOT_EN`が無くてもSDMと暗号化で「読み出し不可・任意ファームの書き込み不可」までは達成できる。署名検証はされない

## 実機で確認できたこと

- `GetInfo`（CTAP 2.3 / max 1024）、登録（packed / UP+AT）、認証（署名71B / counter）、再起動後の永続化、LCD表示
- eFuseの状態。`BLOCK_KEY0`にXTS鍵、`SPI_BOOT_CRYPT_CNT = 0b001`、`SECURE_BOOT_EN`は未焼（署名はSDMの要求のために付与）
- 実機で実行したeFuse操作（一方通行）

```sh
espefuse.py --port /dev/cu.usbmodemXXXX burn_key BLOCK_KEY0 flash-encryption-key.bin XTS_AES_128_KEY
espefuse.py --port /dev/cu.usbmodemXXXX burn_efuse SPI_BOOT_CRYPT_CNT 0x1
```
