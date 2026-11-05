import hashlib
from pathlib import Path
import secrets
import tempfile
import unittest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fido2.cose import ES256
from fido2.utils import websafe_encode, websafe_decode
from fido2.webauthn import AttestedCredentialData, AuthenticatorData, AttestationObject, CollectedClientData
from webauthn_local_test import Verification

ORIGIN = "http://localhost:8787"
RP_HASH = hashlib.sha256(b"localhost").digest()


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.verification = Verification(Path(self.directory.name), ORIGIN)
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = secrets.token_bytes(32)
        credential = AttestedCredentialData.create(bytes(16), self.credential_id,
                                                   ES256.from_cryptography_key(self.key.public_key()))
        request = self.verification.begin("register")
        client = CollectedClientData.create("webauthn.create",
                    websafe_decode(request["options"]["publicKey"]["challenge"]), ORIGIN)
        auth = AuthenticatorData.create(RP_HASH, 0x45, 0, credential)
        response = {"id": websafe_encode(self.credential_id), "rawId": websafe_encode(self.credential_id),
                    "type": "public-key", "response": {"clientDataJSON": websafe_encode(client),
                    "attestationObject": websafe_encode(AttestationObject.create("none", auth, {}))}}
        self.verification.complete("register", {"token": request["token"], "credential": response})

    def assertion(self, flags=5, origin=ORIGIN, counter=1):
        request = self.verification.begin("authenticate")
        client = CollectedClientData.create("webauthn.get",
                    websafe_decode(request["options"]["publicKey"]["challenge"]), origin)
        auth = AuthenticatorData.create(RP_HASH, flags, counter)
        signature = self.key.sign(auth + client.hash, ec.ECDSA(hashes.SHA256()))
        return {"token": request["token"], "credential": {
            "id": websafe_encode(self.credential_id), "rawId": websafe_encode(self.credential_id),
            "type": "public-key", "response": {"clientDataJSON": websafe_encode(client),
            "authenticatorData": websafe_encode(auth), "signature": websafe_encode(signature),
            "userHandle": None}}}

    def test_saved_public_key_survives_restart(self):
        self.verification = Verification(Path(self.directory.name), ORIGIN)
        self.verification.complete("authenticate", self.assertion())
        self.assertEqual(self.verification.records[0]["counter"], 1)

    def test_modified_signature_is_rejected(self):
        body = self.assertion()
        body["credential"]["response"]["signature"] = websafe_encode(bytes(70))
        with self.assertRaises(ValueError):
            self.verification.complete("authenticate", body)
        self.assertEqual(self.verification.records[0]["counter"], 0)

    def test_replayed_response_is_rejected(self):
        body = self.assertion()
        self.verification.complete("authenticate", body)
        with self.assertRaises(KeyError):
            self.verification.complete("authenticate", body)

    def test_missing_presence_or_verification_is_rejected(self):
        for flags in (0, 1, 4):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                self.verification.complete("authenticate", self.assertion(flags=flags))

    def test_wrong_origin_is_rejected(self):
        with self.assertRaises(ValueError):
            self.verification.complete("authenticate", self.assertion(origin="http://example.com"))

    def test_counter_rollback_is_rejected(self):
        self.verification.complete("authenticate", self.assertion(counter=3))
        with self.assertRaises(ValueError):
            self.verification.complete("authenticate", self.assertion(counter=2))


if __name__ == "__main__":
    unittest.main()
