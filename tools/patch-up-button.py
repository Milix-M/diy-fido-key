#!/usr/bin/env python3
"""ユーザープレゼンス（BOOT 押下）を未コミッショニングでも必須にする。

pico-keys は `phy` レコードに `PHY_UP_BTN` が無いと、ボタン待ちをせず即座に
承認済みにする。pico-keys-sdk/src/button.c の button_timeout_seconds() が
`phy_data.up_btn_present ? phy_data.up_btn : 0` を返し、タイムアウト 0 のときは
button_wait_start_timeout() が SIGNAL_USER_PRESENCE_COMPLETED を即発行するため。

本来は PicoKey App でコミッショニングして phy に書く。このスクリプトは
ファーム側のデフォルトを変える代替で、phy は空のまま。

    python3 patch-up-button.py vendor/pico-fido/pico-keys-sdk/src/button.c
    python3 patch-up-button.py --seconds 60 vendor/pico-fido/pico-keys-sdk/src/button.c
"""
import argparse
import sys

ORIGINAL = 'return phy_data.up_btn_present ? phy_data.up_btn : 0;'
TEMPLATE = 'return phy_data.up_btn_present ? phy_data.up_btn : %d;'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('button_c')
    ap.add_argument('--seconds', type=int, default=30,
                    help='ボタン待ちのタイムアウト秒（既定 30）')
    args = ap.parse_args()

    if args.seconds < 1 or args.seconds > 255:
        print('ERROR: seconds は 1〜255')
        return 1

    with open(args.button_c, encoding='utf-8') as fh:
        text = fh.read()

    target = TEMPLATE % args.seconds
    if target in text:
        print('already patched: %s' % target)
        return 0

    count = text.count(ORIGINAL)
    if count != 1:
        print('ERROR: 対象行が %d 個見つかった（1個であるべき）' % count)
        print('上流が変更された可能性がある。次で探すこと:')
        print('  grep -n "up_btn_present ? phy_data.up_btn" %s' % args.button_c)
        return 1

    with open(args.button_c, 'w', encoding='utf-8') as fh:
        fh.write(text.replace(ORIGINAL, target))

    print('patched: %s' % target)
    return 0


if __name__ == '__main__':
    sys.exit(main())
