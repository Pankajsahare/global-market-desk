# Global Market Desk

advisor4u.in साठी जागतिक बाजाराचा delayed डेटा feed. GitHub Actions दर 15 मिनिटांनी (सोम–शुक्र) डेटा बनवतो आणि GitHub Pages वर publish करतो.

**Data URL:** https://pankajsahare.github.io/global-market-desk/data/market.json

## Files

| File | काम |
|---|---|
| `config/symbols.json` | कोणते symbols आणायचे — 4 गट: `global`, `risk`, `sectors`, `funds` |
| `scripts/build_data.py` | Yahoo वरून डेटा आणून returns काढतो → `public/data/market.json` |
| `.github/workflows/update-data.yml` | Schedule + Pages deploy |
| `public/widget/gmd.js`, `gmd.css` | Dashboard widget — GitHub Pages वरून WP वर load होतो (S1) |
| `wordpress/shortcode-snippet.php` | WP Code Snippets: `[gmd_dashboard]` / `[gmd_dashboard mode="private"]` |
| `scripts/summary.py` | S2: "What moved" वाक्यं (फक्त घडलेल्या घटना) |
| `scripts/snapshot.py`, `public/widget/snapshot.html` | S5: रोज 16:11 IST ला 1080×1350 PNG → private Telegram (`snapshot.yml`) |
| `scripts/weekly_recap.py`, `public/widget/weekly.html` | S5: दर शनिवारी 09:47 IST ला clients साठी 1 पानाचा Weekly Market Recap PDF → private Telegram (`weekly-recap.yml`) |
| `scripts/fall_alert.py` | S2: NIFTY −2/−3/−4% किंवा India VIX +15/+25% → private Telegram alert + client WhatsApp draft (`fall-alert.yml`, बाजार चालू असताना दर 30 मिनिटं) |
| `scripts/nse_source.py` | S3: Yahoo fail झाल्यास Indian indices साठी NSE `/api/allIndices` |
| `wordpress/recap-signup-forminator.md` | S1: Weekly recap signup form (Forminator — आधीच installed) |
| `data-in/index_proxies.json` | S6: invest-core कडून NSE index closes (Midcap 150 / Smallcap 250 / Nifty 100); 7 दिवसांपेक्षा जुना असल्यास Yahoo |
| `scripts/cue_tracker.py` | S3: सकाळचा cue vs NIFTY opening gap — `public/log/cue-log.json` |
| `scripts/build_macro.py`, `config/macro.json` | India Macro Snapshot: CPI + GDP (MoSPI API), forex reserves (RBI WSS), repo rate (config) → `public/log/macro.json`; रोज 07:23 IST (`macro.yml`); 10Y G-Sec (RBI home), CPI chart वर repo रेषा, नवीन CPI/GDP वर Telegram draft, MPC/FD reminders, weekly recap PDF मध्ये macro पट्टी |
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
| `scripts/signals.py` | Cue + mood rules (`public/widget/gmd.js` मधल्या JS ची Python प्रत — `tests/test_signals.py` दोन्ही जुळतात का तपासतो) |
| `scripts/morning_brief.py` | सोम–शुक्र ~8:40 IST ला brief (`.github/workflows/morning-brief.yml`) |
| `scripts/alert.py` | सलग 3 failed updates → alert; पुन्हा चालू झाल्यावर "recovered" |

Repo Secrets लागतात: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (फक्त तुमचा private chat — public channel नको).
Message न पाठवता preview: `python scripts/morning_brief.py --file tests/fixtures_market.json --dry-run`

## India Macro Snapshot

- **Repo rate बदलणे (प्रत्येक RBI MPC नंतर):** GitHub → `config/macro.json` → ✏️ → `value`, `as_of` (YYYY-MM-DD) बदला आणि `history` मध्ये `["तारीख", दर]` जोडा → Commit. दर न बदलल्यास फक्त `as_of`. `mpc_decisions` यादी पुढच्या वर्षासाठी RBI calendar प्रमाणे वाढवा. Push झाल्यावर `macro.yml` आपोआप चालतो आणि site update होते.
- **FD दर बदलणे (S2, Real FD Return कार्ड):** `config/macro.json` → `fd_rate.value` / `as_of` (SBI च्या साइटवर दर बदलल्यावर). `fd_rate` काढल्यास कार्ड दिसत नाही.
- CPI chart: 2026 पासून base 2024; त्याआधीचे महिने base 2012 series मधून (S1) — note मध्ये लिहिलेलं असतं.
- एखादा source बंद असल्यास त्याचा मागचा आकडा `*` सह दिसतो; तिन्ही बंद असल्यास Telegram alert आणि site वर जुनी file.
- Widget card "What Moved" खाली आहे; `public/widget/gmd.js` मधील `renderMacro`.
