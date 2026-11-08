"""तात्पुरती तपासणी. नंतर काढून टाकायची."""
import json
import re
import sys

sys.path.insert(0, "scripts")
import build_macro as bm  # noqa: E402

for year in ("2025", "2026"):
    for page in (None, "2", "3"):
        params = {"base_year": "2024", "series": "Current", "year": year, "state_code": "1", "Format": "JSON", "limit": 100}
        if page:
            params["page"] = page
        try:
            body = json.loads(bm.http_get(bm.MOSPI + "/api/cpi/getCPIData", params))
            rows = body.get("data") or []
            print("cpi", year, page, body.get("meta_data"), sorted({r.get("month") for r in rows}),
                  sorted({r.get("division") for r in rows})[:4])
        except Exception as exc:
            print("cpi", year, page, "ERR", exc)
params = {"base_year": "2024", "series": "Current", "year": "2026", "state_code": "1", "Format": "JSON", "limit": 100,
          "division_code": "0"}
for extra in ({}, {"sector_code": "3"}, {"month_code": "1"}):
    try:
        body = json.loads(bm.http_get(bm.MOSPI + "/api/cpi/getCPIData", {**params, **extra}))
        print("cpi filt", extra, body.get("meta_data"), [(r.get("month"), r.get("sector"), r.get("division"), r.get("inflation")) for r in (body.get("data") or [])[:4]])
    except Exception as exc:
        print("cpi filt", extra, "ERR", exc)
for d in ("07/10/2026", "07/09/2026", "08/14/2026", "06/26/2026"):
    page = bm.http_get(bm.RBI_WSS, {"SelectedDate": d})
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    i = text.find("As on")
    print("wss", d, len(page), bm.parse_wss(page), text[i:i + 80] if i >= 0 else text[:200])
