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
status, body = get("https://www.rbi.org.in/Scripts/BS_ViewWssExtract.aspx")
hrefs = re.findall(r"href=[\"']([^\"']+)", body, re.I)
print("n", len(hrefs))
for h in hrefs:
    if "aspx" in h.lower() and ("wss" in h.lower() or "id=" in h.lower()):
        print(h)
i = body.lower().find("oct")
print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", body[body.lower().find("<form"):]))[:3000])
