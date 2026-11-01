# ファームウェアを公開・配布する場合

このリポジトリのファームウェアはpico-fido（AGPLv3）を改変したもの。バイナリを配るなら次の条件を満たす。

## 配布するときの条件

1. 対応するソースの提供（AGPLv3 §4-6）
   - 本リポジトリのコードと、`tools/install-esp32-lcd.sh`が当てるパッチ
   - pico-fido `ade7702`、pico-keys-sdk `a2f0a51`、ESP-IDF `v5.5.1`
   - ビルド手順（`tools/build-pico-fido-esp32s3.sh`）
2. LICENSE（AGPL-3.0）とNOTICEを同梱する。どちらもこのリポジトリにある
3. 変更したファイルを明示する。著作権表示は削除しない
4. VID/PIDを自分のものに変更する

## VID/PID

`2E8A:10FE`はpico-fido用にRaspberry Piが付与したID。pico-fidoのREADMEは、自分が所有していないVID/PIDでバイナリを配布する権利は無いとしている。

- ソースのみ公開する場合は既定の`2E8A:10FE`のままでよい。利用者が自分の環境でビルドするので、個人利用の範囲にとどまる
- ビルド済みバイナリを配布する場合は、Raspberry PiのIDを同梱することになるため自分のVID/PIDに変更する
- 個人開発なら[pid.codes](https://pid.codes/)でVID `0x1209`と固有PIDの割当を受ける
- ビルド時に環境変数で差し替えられる（確認済み）

```sh
FIDO_USB_VID=0x1209 FIDO_USB_PID=0x0001 sh tools/build-pico-fido-esp32s3.sh
```

VID/PIDを変えるとOpenSCとykmanの互換設定が変わるので、配布物のREADMEに注記する。

## キャラクター画像

`esp32-lcd/mascot_80x80.h`は画像そのものを埋め込んでいる。著作者は`NOTICE`に記載している。

## 免責

FIDO Allianceの認証が無いこと、セキュアエレメントを載せていないこと、個人用途と実験用で保証しないことを明記する。`YubiKey`や`Pico`を製品名に使わない。
