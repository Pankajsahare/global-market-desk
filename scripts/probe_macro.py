"""तात्पुरती तपासणी: macro sources runner वरून चालतात का. नंतर काढून टाकायची."""
import json
import re
import ssl
import urllib.parse
import urllib.request

# TLS verification चालू; फक्त जुन्या server साठी legacy renegotiation परवानगी
CTX = ssl.create_default_context()
CTX.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)


def get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as exc:
        return "ERR", f"{type(exc).__name__}: {exc}"


B = "https://api.mospi.gov.in"
TESTS = [
    ("wss list", "https://www.rbi.org.in/Scripts/BS_ViewWssExtract.aspx", None),
    ("wss 63777", "https://www.rbi.org.in/Scripts/BS_ViewWssExtractdetails.aspx", {"id": "63777"}),
]

for name, url, params in TESTS:
    status, body = get(url, params)
    print(f"### {name} -> {status} len={len(body)}")
    print("links:", sorted(set(re.findall(r"WssExtractdetails\.aspx\?id=(\d+)", body, re.I)))[-8:])
    for m in re.finditer(r"Foreign Exchange Reserves", body, re.I):
        text = re.sub(r"<[^>]+>", " ", body[m.start():m.start() + 4000])
        print(re.sub(r"\s+", " ", text)[:900])
        break
    titles = re.findall(r"<title>(.*?)</title>", body, re.S | re.I)
    print("title:", titles[:1])
