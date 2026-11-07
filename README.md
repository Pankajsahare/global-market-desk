# Global Market Desk

advisor4u.in साठी जागतिक बाजाराचा delayed डेटा feed. GitHub Actions दर 15 मिनिटांनी (सोम–शुक्र) डेटा बनवतो आणि GitHub Pages वर publish करतो.

**Data URL:** https://pankajsahare.github.io/global-market-desk/data/market.json

## Files

| File | काम |
|---|---|
| `config/symbols.json` | कोणते symbols आणायचे — 4 गट: `global`, `risk`, `sectors`, `funds` |
| `scripts/build_data.py` | Yahoo वरून डेटा आणून returns काढतो → `public/data/market.json` |
| `.github/workflows/update-data.yml` | Schedule + Pages deploy |
| `wordpress/dashboard-widget.html` | Elementor HTML widget (public + private दोन्ही पानांसाठी एकच code) |
| `tests/test_build_data.py` | Offline tests: `python -m unittest discover -s tests` |

## `symbols.json` fields (JSON मध्ये comments चालत नाहीत, म्हणून इथे)

- `symbol` — Yahoo Finance symbol (उदा. `^NSEI`)
- `name` — dashboard वर दिसणारं नाव (English)
- `region` — फक्त `global` गटासाठी: `India` / `US` / `Europe` / `Asia` (heatmap गट)
- `category` — फक्त `funds` गटासाठी: कोणत्या fund category चा proxy
- `decimals` — optional, default 2
- `minPoints` — optional: इतके daily points नसतील तर `fallbacks` मधला पुढचा symbol वापरा
- `fallbacks` — optional: `[{"symbol": ..., "name": ...}]` पर्यायी symbols, क्रमाने

नवीन symbol जोडायचा असल्यास योग्य गटात एक ओळ जोडा. Script बदलायची गरज नाही.

## `market.json` fields

- `updated` — डेटा बनल्याची वेळ (UTC)
- `last` — शेवटचा भाव; `r1d`/`r1w`/`r1m`/`r3m`/`r1y` — % बदल
- `d1d`/`d1w` — absolute बदल (US 10Y yield साठी उपयोगी)
- `spark` — शेवटचे ~66 daily closes (sparkline)
- `stale: true` — या वेळी fetch fail झाला, मागचा value दाखवला

## Safety

- 50% पेक्षा जास्त symbols fail → नवीन deploy होत नाही, site वर मागचा डेटा राहतो.
- काही symbols fail → त्यांचा मागचा value `stale: true` सह.
- Source: Yahoo Finance (unofficial, delayed). For information only; not investment advice.

## Telegram (S2 morning brief + S5 failure alert)

| File | काम |
|---|---|
| `scripts/signals.py` | Cue + mood rules (widget मधल्या JS ची Python प्रत — `tests/test_signals.py` दोन्ही जुळतात का तपासतो) |
| `scripts/morning_brief.py` | सोम–शुक्र ~8:40 IST ला brief (`.github/workflows/morning-brief.yml`) |
| `scripts/alert.py` | सलग 3 failed updates → alert; पुन्हा चालू झाल्यावर "recovered" |

Repo Secrets लागतात: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (फक्त तुमचा private chat — public channel नको).
Message न पाठवता preview: `python scripts/morning_brief.py --file tests/fixtures_market.json --dry-run`
