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
    ("rbi meta 47", B + "/api/rbi/getRbiMetaData", {"sub_indicator_code": 47}),
    ("rbi 47 2026", B + "/api/rbi/getRbiRecords", {"sub_indicator_code": 47, "year": "2026", "limit": 50}),
    ("rbi 47 any", B + "/api/rbi/getRbiRecords", {"sub_indicator_code": 47, "limit": 5}),
    ("cpi filters 2024", B + "/api/cpi/getCpiFilterByLevelAndBaseYear",
     {"base_year": "2024", "level": "null", "series_code": "Current"}),
    ("cpi data 2024", B + "/api/cpi/getCPIData",
     {"base_year": "2024", "series": "Current", "year": "2026", "state_code": "99", "Format": "JSON", "limit": 20}),
    ("cpi index 2012", B + "/api/cpi/getCPIIndex",
     {"base_year": "2012", "series": "Current", "year": "2025", "state_code": "99", "sector_code": "3",
      "Format": "JSON", "limit": 20}),
    ("nas filters q22", B + "/api/nas/getNasFilterByIndicatorId",
     {"base_year": "2022-23", "series": "Current", "frequency_code": 2, "indicator_code": 22}),
    ("nas data q22", B + "/api/nas/getNASData",
     {"base_year": "2022-23", "series": "Current", "frequency_code": "Quarterly", "indicator_code": 22, "limit": 20}),
    ("fred cpi", "https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": "INDCPIALLMINMEI"}),
    ("fred fx", "https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": "TRESEGINM052N"}),
]

for name, url, params in TESTS:
    status, body = get(url, params)
    print(f"### {name} -> {status} len={len(body)}")
    print(body[-200:] if name.startswith("fred") else body[:1500])
