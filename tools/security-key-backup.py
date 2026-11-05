#!/usr/bin/env python3
"""Create, verify, or restore a password-encrypted backup of the firmware keys."""
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from flash_backup import private_write

MAGIC = b"DIYFIDO-KEYS-1\n"
NAMES = ("secure-boot-rsa3072.pem", "flash-encryption-key.bin")


def derive(password, salt):
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(password.encode())


def pack(keys, password):
    salt, nonce = os.urandom(16), os.urandom(12)
    payload = json.dumps({name: base64.b64encode(data).decode() for name, data in keys.items()}).encode()
    header = MAGIC + salt + nonce
    return header + AESGCM(derive(password, salt)).encrypt(nonce, payload, header)


def unpack(blob, password):
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 44:
        raise ValueError("Invalid backup format")
    salt = blob[len(MAGIC):len(MAGIC) + 16]
    nonce = blob[len(MAGIC) + 16:len(MAGIC) + 28]
    header = blob[:len(MAGIC) + 28]
    payload = AESGCM(derive(password, salt)).decrypt(nonce, blob[len(header):], header)
    values = json.loads(payload)
    if set(values) != set(NAMES):
        raise ValueError("Unexpected key names in backup")
    return {name: base64.b64decode(values[name], validate=True) for name in NAMES}


def read_keys(directory):
    return {name: (directory / name).read_bytes() for name in NAMES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create", "verify", "restore"])
    parser.add_argument("--key-dir", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    password = getpass.getpass("Backup password: ")
    if not password:
        parser.error("A non-empty password is required.")
    if args.command == "create":
        if password != getpass.getpass("Repeat password: "):
            parser.error("Passwords differ.")
        keys = read_keys(args.key_dir)
        encrypted = pack(keys, password)
        if unpack(encrypted, password) != keys:
            raise ValueError("Backup round-trip failed")
        private_write(args.backup, encrypted)
        print("Encrypted backup written and verified.")
    else:
        keys = unpack(args.backup.read_bytes(), password)
        if args.command == "verify":
            if read_keys(args.key_dir) != keys:
                raise ValueError("Backup does not match the current keys")
            print("Backup matches both current keys.")
        else:
            if args.key_dir.exists():
                raise FileExistsError("Restore requires a new directory")
            args.key_dir.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=args.key_dir.parent) as temporary:
                for name, data in keys.items():
                    private_write(Path(temporary) / name, data)
                os.rename(temporary, args.key_dir)
            print("Keys restored to a new directory.")


if __name__ == "__main__":
    main()
