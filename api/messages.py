import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)


def call_gemini(text, max_tokens):
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is empty (env not set for this environment)")
    url = GEMINI_ENDPOINT.format(model=MODEL, key=API_KEY)
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens or 1000,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError("No candidates: " + json.dumps(body)[:300])
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, code, obj):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req_body = json.loads(raw.decode("utf-8"))
            messages = req_body.get("messages", [])
            user_text = ""
            for m in messages:
                if m.get("role") == "user":
                    c = m.get("content")
                    user_text += c if isinstance(c, str) else json.dumps(c)
            max_tokens = req_body.get("max_tokens", 1000)
            text_out = call_gemini(user_text, max_tokens)
            self._send(200, {"content": [{"type": "text", "text": text_out}]})
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:500]
            self._send(200, {"content": [{"type": "text", "text": f"[診断] Gemini HTTPError {e.code}: {detail}"}]})
        except Exception as e:
            self._send(200, {"content": [{"type": "text", "text": f"[診断] {type(e).__name__}: {e}"}]})

    def log_message(self, fmt, *args):
        print(fmt % args)
