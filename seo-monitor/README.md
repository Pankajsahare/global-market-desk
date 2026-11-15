# SEO monitor — advisor4u.in

दर रविवारी रात्री 21:13 (IST) GitHub Actions हे script चालवतं आणि advisor4u.in ची SEO तपासणी करतं.

## काय तपासतं
- `sitemap.xml` आणि `local-sitemap.xml` मधली **सगळी** पानं, आणि `bond-sitemap.xml` मधली दर आठवड्याला वेगळी **100** पानं (काही आठवड्यांत सगळी bond पानं तपासून होतात).
- प्रत्येक पानावर: HTTP status, redirect, response time, `<title>` (SVG icons मधले सोडून), meta description, H1, canonical, robots (noindex), JSON-LD schema valid आहे का, आणि alt नसलेल्या images.
- प्रत्येक पानानंतर 1 सेकंद विराम, म्हणजे Hostinger server वर भार येत नाही. 5xx किंवा timeout आला तर एकदाच पुन्हा प्रयत्न होतो.

## Issue codes (CSV मधल्या `issues` column मध्ये)
| code | अर्थ |
|---|---|
| `http_404`, `http_500`… | पान उघडत नाही |
| `redirected` | sitemap मधला URL दुसऱ्या पत्त्यावर जातो |
| `noindex_in_sitemap` | पान noindex आहे पण sitemap मध्ये आहे (अशा पानांचे title/alt/H1 तपासले जात नाहीत) |
| `missing_title` / `duplicate_title_tag` / `title_too_long` | title नाही / 2 title tags / 65 पेक्षा जास्त अक्षरं |
| `missing_description` / `duplicate_description_tag` / `description_length` | description नाही / दोनदा / 70–170 अक्षरांच्या बाहेर |
| `missing_h1` | H1 नाही |
| `missing_canonical` / `canonical_mismatch` | canonical नाही / दुसऱ्याच पानाकडे |
| `invalid_jsonld` | schema चं JSON बिघडलेलं |
| `img_missing_alt` | alt नसलेली image |
| `slow` | 3 सेकंदांपेक्षा जास्त |
| `suspicious_url` | नावात `_old`, `copy`, `test`, `-2/` इ. |

## अहवाल कुठे मिळतो
- **Telegram (फक्त private chat):** एकूण आकडे + या आठवड्यातल्या **नवीन** चुका + पूर्ण CSV file. `TELEGRAM_CHAT_ID` हा public channel असेल तर `scripts/notify.py` message पाठवत नाही.
- **Repo मध्ये:** `seo-monitor/reports/latest.csv` (पूर्ण तक्ता) आणि `issues.json` (मागच्या आठवड्याशी तुलना करण्यासाठी). हा repo public आहे, त्यामुळे हा अहवाल GitHub वर कुणालाही दिसू शकतो. यात फक्त साईटची public माहिती असते.

## हाताने चालवायचं असेल तर
GitHub → repo → **Actions** टॅब → डावीकडे **SEO audit** → उजवीकडे **Run workflow**.

## बदल करायचे असतील तर
`seo_audit.py` च्या सुरुवातीला: `SAMPLED_SITEMAPS` (bond पानांचा नमुना), `DELAY_SECONDS`, `SLOW_SECONDS`, `TITLE_MAX`, `DESC_MIN/DESC_MAX`, `SUSPICIOUS`.
