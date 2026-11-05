#!/usr/bin/env python3
"""Verify a physical FIDO key before and after reconnecting or updating it."""
import argparse
import json
import os
from pathlib import Path
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from fido2.server import Fido2Server
from fido2.utils import websafe_decode, websafe_encode
from fido2.webauthn import AttestedCredentialData, AuthenticationResponse

PAGE = """<!doctype html><meta charset="utf-8"><title>FIDOキーの動作確認</title>
<style>body{font:18px system-ui;max-width:42em;margin:4em auto;padding:0 1em}
button,select{font:inherit;padding:.6em;margin:.3em}pre{white-space:pre-wrap}</style>
<h1>FIDOキーの動作確認</h1>
<button onclick="perform('register')">テスト用キーを登録</button>
<select id="stage"><option>初回</option><option>抜き差し後</option><option>更新後</option></select>
<button onclick="perform('authenticate')">認証を確認</button>
<pre id="result">PINはブラウザの画面で入力し、キーのBOOTボタンで承認してください。</pre>
<script>
const result = document.getElementById('result');
const encode = b => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
const decode = s => Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')), c => c.charCodeAt(0));
async function post(path, data) {
  const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error);
  return body;
}
async function perform(kind) {
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  try {
    result.textContent = 'PINの入力とBOOTボタンでの承認を待っています。';
    const request = await post('/' + kind + '/begin', {});
    const publicKey = request.options.publicKey;
    publicKey.challenge = decode(publicKey.challenge);
    if (publicKey.user) publicKey.user.id = decode(publicKey.user.id);
    for (const name of ['allowCredentials', 'excludeCredentials']) {
      if (publicKey[name]) publicKey[name].forEach(c => c.id = decode(c.id));
    }
    const credential = kind === 'register'
      ? await navigator.credentials.create({publicKey})
      : await navigator.credentials.get({publicKey});
    const response = {clientDataJSON:encode(credential.response.clientDataJSON)};
    if (kind === 'register') {
      response.attestationObject = encode(credential.response.attestationObject);
    } else {
      response.authenticatorData = encode(credential.response.authenticatorData);
      response.signature = encode(credential.response.signature);
      response.userHandle = credential.response.userHandle ? encode(credential.response.userHandle) : null;
    }
    const complete = await post('/' + kind + '/complete', {
      token:request.token, stage:document.getElementById('stage').value,
      credential:{id:credential.id, rawId:encode(credential.rawId), type:credential.type,
                  response, clientExtensionResults:credential.getClientExtensionResults()}
    });
    result.textContent = complete.message;
  } catch (error) {
    result.textContent = '未完了: ' + error.message;
  } finally {
    document.querySelectorAll('button').forEach(b => b.disabled = false);
  }
}
</script>"""


class Verification:
    def __init__(self, output, origin):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.path = self.output / "credentials.json"
        self.records = json.loads(self.path.read_text()) if self.path.exists() else []
        self.pending = {}
        self.rp = Fido2Server({"id": "localhost", "name": "DIY FIDO Verification"},
                            verify_origin=lambda value: value == origin)

    def credentials(self):
        return [AttestedCredentialData(websafe_decode(record["data"])) for record in self.records]

    def begin(self, kind):
        credentials = self.credentials()
        if kind == "register":
            options, state = self.rp.register_begin(
                {"id": b"diy-fido-verification", "name": "verification@localhost",
                 "displayName": "FIDO Verification"}, credentials,
                resident_key_requirement="required", user_verification="required",
                authenticator_attachment="cross-platform")
        else:
            if not credentials:
                raise ValueError("先にテスト用キーを登録してください。")
            options, state = self.rp.authenticate_begin(credentials, user_verification="required")
        now = time.monotonic()
        self.pending = {token: entry for token, entry in self.pending.items() if entry[2] > now}
        token = secrets.token_urlsafe(32)
        self.pending[token] = (kind, state, now + 120)
        return {"token": token, "options": dict(options)}

    def complete(self, kind, body):
        saved_kind, state, expiry = self.pending.pop(body["token"])
        if saved_kind != kind or time.monotonic() > expiry:
            raise ValueError("確認要求が期限切れです。もう一度操作してください。")
        if kind == "register":
            data = self.rp.register_complete(state, body["credential"])
            credential = data.credential_data
            if any(item.credential_id == credential.credential_id for item in self.credentials()):
                raise ValueError("このテスト用キーは登録済みです。")
            self.records.append({"data": websafe_encode(credential), "counter": data.counter})
            message = "登録を確認しました。続けて認証を確認してください。"
        else:
            credential = self.rp.authenticate_complete(state, self.credentials(), body["credential"])
            data = AuthenticationResponse.from_dict(body["credential"]).response.authenticator_data
            record = next(item for item in self.records if item["data"] == websafe_encode(credential))
            if (record["counter"] or data.counter) and data.counter <= record["counter"]:
                raise ValueError("認証カウンターが増えていません。")
            record["counter"] = data.counter
            message = "署名・確認要求・PINによる本人確認・ボタン承認を検証しました。"
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.records, indent=2) + "\n")
        os.replace(temporary, self.path)
        report = {"time": time.time(), "operation": kind, "stage": body.get("stage"),
                  "credential_id": websafe_encode(credential.credential_id),
                  "counter": data.counter, "verified": True}
        with (self.output / "report.jsonl").open("a") as stream:
            stream.write(json.dumps(report) + "\n")
        print(json.dumps(report), flush=True)
        return {"message": message}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body, content_type="application/json"):
        encoded = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/":
            self.reply(200, PAGE, "text/html; charset=utf-8")
        else:
            self.reply(404, {"error": "Not found"})

    def do_POST(self):
        if self.headers.get("Origin") != self.server.origin:
            self.reply(403, {"error": "Invalid origin"})
            return
        routes = {"/register/begin", "/register/complete", "/authenticate/begin", "/authenticate/complete"}
        if self.path not in routes:
            self.reply(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("Invalid request length")
            body = json.loads(self.rfile.read(length))
            _, kind, action = self.path.split("/")
            result = (self.server.verification.begin(kind) if action == "begin"
                      else self.server.verification.complete(kind, body))
            self.reply(200, result)
        except (ValueError, KeyError, TypeError) as error:
            self.reply(400, {"error": str(error)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent.parent / "build/webauthn-verification")
    args = parser.parse_args()
    os.umask(0o077)
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.origin = f"http://localhost:{args.port}"
    server.verification = Verification(args.output, server.origin)
    print(f"Open {server.origin}/", flush=True)
    server.serve_forever()
