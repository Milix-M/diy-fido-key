#!/usr/bin/env python3
"""ESP32-S3 向けに sdkconfig を書き換える。

tools/build-pico-fido-esp32s3.sh は set-target の前に sdkconfig を書き換えるが、
set-target は sdkconfig を削除して作り直すため、その書き換えは必ず捨てられる。
このスクリプトは set-target の後に呼ぶ前提。

    python3 patch-sdkconfig.py vendor/pico-fido/sdkconfig
"""
import argparse
import sys

REPLACEMENTS = {
    '# CONFIG_ESP_CONSOLE_SECONDARY_NONE is not set': 'CONFIG_ESP_CONSOLE_SECONDARY_NONE=y',
    'CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y': '# CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG is not set',
    'CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED=y': '# CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED is not set',
    'CONFIG_ESPTOOLPY_FLASHMODE_QIO=y': '# CONFIG_ESPTOOLPY_FLASHMODE_QIO is not set',
    '# CONFIG_ESPTOOLPY_FLASHMODE_DIO is not set': 'CONFIG_ESPTOOLPY_FLASHMODE_DIO=y',
    'CONFIG_ESPTOOLPY_FLASHMODE="qio"': 'CONFIG_ESPTOOLPY_FLASHMODE="dio"',
}

# pico-fido は sdkconfig を同梱しないので、PSRAM は丸ごと追記する
SPIRAM = [
    'CONFIG_SPIRAM=y',
    'CONFIG_SPIRAM_MODE_OCT=y',
    'CONFIG_SPIRAM_SPEED_80M=y',
    'CONFIG_SPIRAM_USE_MALLOC=y',
    'CONFIG_SPIRAM_BOOT_INIT=y',
    'CONFIG_SPIRAM_IGNORE_NOTFOUND=y',
]
SPIRAM_PREFIXES = (
    'CONFIG_SPIRAM=',
    'CONFIG_SPIRAM_MODE_',
    'CONFIG_SPIRAM_SPEED_',
    'CONFIG_SPIRAM_USE_',
    'CONFIG_SPIRAM_BOOT_INIT=',
    'CONFIG_SPIRAM_IGNORE_NOTFOUND=',
)

REQUIRED = [
    'CONFIG_ESP_CONSOLE_SECONDARY_NONE=y',
    'CONFIG_ESPTOOLPY_FLASHMODE_DIO=y',
    'CONFIG_SPIRAM_SPEED_80M=y',
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sdkconfig')
    args = ap.parse_args()

    with open(args.sdkconfig, encoding='utf-8') as fh:
        text = fh.read()

    applied, missing = [], []
    for old, new in REPLACEMENTS.items():
        if old in text:
            text = text.replace(old, new)
            applied.append(new)
        elif new not in text:
            missing.append(old)

    lines = [l for l in text.splitlines() if not l.startswith(SPIRAM_PREFIXES)]
    lines.extend(SPIRAM)
    text = '\n'.join(lines) + '\n'

    with open(args.sdkconfig, 'w', encoding='utf-8') as fh:
        fh.write(text)

    print('applied: %d, already-set-or-absent: %d' % (len(applied), len(missing)))
    for m in missing:
        print('  not found: %s' % m)

    failed = [r for r in REQUIRED if r not in text]
    if failed:
        print('ERROR: 必須設定が入っていない:')
        for r in failed:
            print('  %s' % r)
        return 1

    print('OK: CONSOLE_SECONDARY_NONE / FLASHMODE_DIO / SPIRAM_SPEED_80M')
    return 0


if __name__ == '__main__':
    sys.exit(main())
