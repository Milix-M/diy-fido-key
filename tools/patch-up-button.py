#!/usr/bin/env python3
"""Set the fallback BOOT-button timeout in the pinned Pico Keys SDK."""
import argparse
from pathlib import Path
import re

PATTERN = re.compile(
    r"return phy_data\.up_btn_present(?: && phy_data\.up_btn > 0)?"
    r" \? phy_data\.up_btn : [0-9]+;"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("button_c", type=Path)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--require-presence", action="store_true",
                        help="Use the fallback when a stored configuration specifies zero seconds.")
    args = parser.parse_args()
    minimum = 1 if args.require_presence else 0
    if not minimum <= args.seconds <= 255:
        parser.error(f"--seconds must be between {minimum} and 255")
    original = args.button_c.read_text()
    if len(PATTERN.findall(original)) != 1:
        parser.error("Expected exactly one supported button timeout expression.")
    condition = "phy_data.up_btn_present"
    if args.require_presence:
        condition += " && phy_data.up_btn > 0"
    target = f"return {condition} ? phy_data.up_btn : {args.seconds};"
    updated = PATTERN.sub(target, original)
    if updated != original:
        args.button_c.write_text(updated)
    print(target)


if __name__ == "__main__":
    main()
