"""Telegram वर message पाठवण्याचा छोटा helper (standard library)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 4000  # Telegram limit 4096


def send_telegram(text: str) -> bool:
    """TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID secrets वापरून पाठवा. Secret नसल्यास skip."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("WARN: Telegram secrets not set; message not sent", file=sys.stderr)
        return False

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
