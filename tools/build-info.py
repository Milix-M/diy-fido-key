#!/usr/bin/env python3
"""Check the pinned ESP32 build inputs and record output checksums."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "vendor/pico-fido"
SDK = SOURCE / "pico-keys-sdk"


def revision(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                   text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, metavar="BUILD_DIRECTORY")
    args = parser.parse_args()
    lock = json.loads((ROOT / "tools/esp32-build-lock.json").read_text())
    idf_path = os.environ.get("IDF_PATH")
    if not idf_path:
        parser.error("Export ESP-IDF v5.5.1 before building.")
    actual = {
        "pico-fido": revision(SOURCE),
        "pico-keys-sdk": revision(SDK),
        "esp-idf": revision(Path(idf_path)),
        "esptool": importlib.metadata.version("esptool"),
    }
    for name, value in actual.items():
        if value != lock[name]:
            parser.error(f"{name}: expected {lock[name]}, found {value}")
    dependencies = {}
    for name, expected in lock["third-party"].items():
        path = SDK / "third-party" / name
        if path.exists():
            dependencies[name] = revision(path)
            if dependencies[name] != expected:
                parser.error(f"{name}: expected {expected}, found {dependencies[name]}")
        elif args.record:
            parser.error(f"Missing build dependency: {name}")
    component_lock = ROOT / "tools/esp32-dependencies.lock"
    installed_lock = SOURCE / "dependencies.lock"
    if installed_lock.exists() and installed_lock.read_bytes() != component_lock.read_bytes():
        parser.error("vendor/pico-fido/dependencies.lock differs from tools/esp32-dependencies.lock")
    if not installed_lock.exists():
        shutil.copyfile(component_lock, installed_lock)
    if args.record:
        build = args.record.resolve()
        binaries = list(build.glob("*.bin"))
        binaries += list((build / "bootloader").glob("*.bin"))
        binaries += list((build / "partition_table").glob("*.bin"))
        paths = binaries + [build / "sdkconfig"]
        input_names = subprocess.check_output([
            "git", "-C", str(ROOT), "ls-files", "--cached", "--others",
            "--exclude-standard", "tools", "patches", "esp32-lcd"], text=True).splitlines()
        report = {
            "repository_commit": revision(ROOT),
            "repository_diff_sha256": hashlib.sha256(subprocess.check_output(
                ["git", "-C", str(ROOT), "diff", "HEAD", "--", "."])).hexdigest(),
            "versions": actual,
            "third_party": dependencies,
            "python": sys.version,
            "compiler": subprocess.check_output(["xtensa-esp32s3-elf-gcc", "-dumpfullversion"], text=True).strip(),
            "inputs_sha256": {name: digest(ROOT / name) for name in sorted(set(input_names))},
            "vendor_diff_sha256": {name: hashlib.sha256(subprocess.check_output(
                ["git", "-C", str(path), "diff", "HEAD"])).hexdigest()
                for name, path in (("pico-fido", SOURCE), ("pico-keys-sdk", SDK))},
            "component_lock_sha256": digest(installed_lock),
            "outputs_sha256": {str(path.relative_to(build)): digest(path) for path in paths},
        }
        (build / "build-info.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Build record: {build / 'build-info.json'}")
    else:
        print("Pinned build inputs verified.")


if __name__ == "__main__":
    main()
