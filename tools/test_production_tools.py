import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cryptography.exceptions import InvalidTag

TOOLS = Path(__file__).resolve().parent


class ButtonTimeoutTests(unittest.TestCase):
    def test_repeated_configuration_and_required_presence(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "button.c"
            source.write_text("return phy_data.up_btn_present ? phy_data.up_btn : 0;\n")
            for seconds, required in [(30, False), (60, False), (30, True), (30, True), (0, False)]:
                command = [sys.executable, str(TOOLS / "patch-up-button.py"), str(source), "--seconds", str(seconds)]
                if required:
                    command.append("--require-presence")
                subprocess.run(command, check=True, capture_output=True)
                self.assertIn(f": {seconds};", source.read_text())
                self.assertEqual("&& phy_data.up_btn > 0" in source.read_text(), required)
            before = source.read_bytes()
            result = subprocess.run(command + ["--require-presence"], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_bytes(), before)

    def test_unexpected_source_is_not_modified(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "button.c"
            source.write_text("return 0;\n")
            result = subprocess.run([sys.executable, str(TOOLS / "patch-up-button.py"), str(source)],
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_text(), "return 0;\n")


class KeyBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("key_backup", TOOLS / "security-key-backup.py")
        cls.backup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.backup)

    def test_round_trip_and_tampering(self):
        keys = {name: b"test-only-key-material" for name in self.backup.NAMES}
        encrypted = self.backup.pack(keys, "test-only-password")
        self.assertEqual(self.backup.unpack(encrypted, "test-only-password"), keys)
        with self.assertRaises(InvalidTag):
            self.backup.unpack(encrypted, "wrong-password")
        corrupted = encrypted[:-1] + bytes([encrypted[-1] ^ 1])
        with self.assertRaises(InvalidTag):
            self.backup.unpack(corrupted, "test-only-password")


if __name__ == "__main__":
    unittest.main()
