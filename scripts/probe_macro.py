"""तात्पुरती तपासणी: macro sources runner वरून चालतात का. नंतर काढून टाकायची."""
import json
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
    ("rbi 47 2025", B + "/api/rbi/getRbiRecords", {"sub_indicator_code": 47, "year": "2025", "limit": 100}),
    ("cpi24 a", B + "/api/cpi/getCPIData", {"base_year": "2024", "series": "Current", "year": "2026", "state_code": "1", "Format": "JSON", "limit": 10}),
    ("cpi24 b", B + "/api/cpi/getCPIData", {"base_year": "2024", "series": "Current", "year": "2026", "Format": "JSON", "limit": 10}),
    ("cpi24 c", B + "/api/cpi/getCPIData", {"base_year": "2024", "series_code": "Current", "year": "2026", "state_code": "1", "Format": "JSON", "limit": 10}),
    ("cpi24 d", B + "/api/cpi/getCPIData", {"base_year": "2024", "year": "2026", "Format": "JSON", "limit": 10}),
    ("cpi24 e", B + "/api/cpi/getCPIIndex", {"base_year": "2024", "series": "Current", "year": "2026", "state_code": "1", "Format": "JSON", "limit": 10}),
]

for name, url, params in TESTS:
    status, body = get(url, params)
    print(f"### {name} -> {status} len={len(body)}")
    print(body[:2500])
