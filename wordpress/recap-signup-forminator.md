# S1 — Weekly Market Recap signup (Forminator — आधीच installed, मोफत)

Dashboard वरचं "Subscribe free" बटण `#recap-signup` या भागावर नेतं. तिथे हा form ठेवायचा.
Forminator प्रत्येक signup WordPress मध्येच साठवतो → CSV export (हीच तुमची opt-in यादी).

## 1. Form बनवा

Forminator → Forms → **+ Create** → Blank → नाव: `Weekly Recap Signup`.

| # | Field (Insert Fields मधून) | Label (English) | Settings |
|---|---|---|---|
| 1 | Name | `Your name` | Required ✔ |
| 2 | Phone | `WhatsApp number (with country code)` | Required ✔, Validation: International |
| 3 | Email | `Email (optional)` | Required ✘ |
| 4 | Radio | `Send the recap on` | Options: `WhatsApp`, `Email`, `Both`; Default: WhatsApp |
| 5 | Consent | (खालचा मजकूर) | Required ✔ |

Consent field चा मजकूर:

```
I agree to receive the Weekly Market Recap and occasional market updates from Sahare Wealth (AMFI-registered Mutual Fund Distributor, ARN-151469) on WhatsApp or email. I can unsubscribe at any time by replying STOP. This is market information, not investment advice.
```

Submit बटणाचं नाव: `Get the Weekly Recap`.

## 2. Behaviour आणि Email

- **Behaviour** → After submission: Inline message →
  `Thank you! You'll receive the Weekly Market Recap every Saturday.`
- **Email Notifications** → Admin Email → Recipient: `info@advisor4u.in`,
  Subject: `New Weekly Recap signup: {name-1}` (बाकी default ठेवा — सगळे fields email मध्ये येतात).
- **Settings → Security** → Honeypot protection **चालू** करा (spam bots रोखतो).
- Publish → वर दिसणारा shortcode copy करा, उदा. `[forminator_form id="123"]`.

## 3. पानावर ठेवा

Pages → Global Markets → Edit with Elementor:

1. Dashboard shortcode च्या **खाली** नवीन Container जोडा.
2. त्या Container चं Advanced → **CSS ID** = `recap-signup` (हे नाव बदलू नका — बटण इथेच येतं).
3. आत **Shortcode** widget → Forminator चा shortcode paste → Update.

## 4. रोजचं काम

- नवीन signups: Forminator → **Submissions** → form निवडा → Export (CSV).
- कोणी STOP पाठवला: त्याची submission Delete करा आणि पाठवण्याच्या यादीतून काढा.
- Spam वाढला तर: form मध्ये **Turnstile / reCAPTCHA** field जोडा (Forminator → Settings → CAPTCHA).
