"""Telegram वर message पाठवण्याचा छोटा helper (standard library)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
PHOTO_URL = "https://api.telegram.org/bot{token}/sendPhoto"
MAX_LEN = 4000  # Telegram limit 4096


def private_chat_id(raw: str) -> str | None:
    """फक्त धन पूर्णांक (private chat) चालतो; @channel किंवा -100... (group/channel) नाकारले जातात."""
    value = raw.strip()
    return value if value.isdigit() and int(value) > 0 else None


def _credentials() -> tuple[str, str] | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    raw_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not raw_chat:
        print("WARN: Telegram secrets not set; message not sent", file=sys.stderr)
        return None
    chat_id = private_chat_id(raw_chat)
    if chat_id is None:
        # Cue/mood चुकून public channel वर जाऊ नयेत
        print("ERROR: TELEGRAM_CHAT_ID is not a private chat; message blocked", file=sys.stderr)
        return None
    return token, chat_id


def send_telegram(text: str) -> bool:
    """TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID secrets वापरून private chat वर पाठवा."""
    creds = _credentials()
    if creds is None:
        return False
    token, chat_id = creds

    body = json.dumps({
        "chat_id": chat_id,
        "text": text[:MAX_LEN],
        "disable_web_page_preview": True,
    }).encode("utf-8")
    request = urllib.request.Request(
        TELEGRAM_URL.format(token=token), data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            ok = json.loads(response.read().decode("utf-8")).get("ok", False)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        # token कधीच log मध्ये छापू नका — फक्त error प्रकार
        print(f"ERROR: Telegram send failed: {type(exc).__name__}", file=sys.stderr)
        return False
    print("Telegram message sent" if ok else "ERROR: Telegram returned ok=false")
    return bool(ok)


def send_photo(path: str, caption: str) -> bool:
    """S5: PNG private chat वर पाठवा (multipart, standard library)."""
    creds = _credentials()
    if creds is None:
        return False
    token, chat_id = creds
    boundary = "----gmd" + os.urandom(8).hex()
    with open(path, "rb") as handle:
        image = handle.read()
    parts = []
    for name, value in (("chat_id", chat_id), ("caption", caption[:1000])):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="snapshot.png"\r\n'
                 f"Content-Type: image/png\r\n\r\n".encode() + image + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        PHOTO_URL.format(token=token), data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            ok = json.loads(response.read().decode("utf-8")).get("ok", False)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"ERROR: Telegram photo failed: {type(exc).__name__}", file=sys.stderr)
        return False
    print("Telegram photo sent" if ok else "ERROR: Telegram returned ok=false")
    return bool(ok)
