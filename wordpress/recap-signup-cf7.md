# S1 — Weekly Market Recap signup (Contact Form 7 + Flamingo, दोन्ही मोफत)

Dashboard वरचं "Subscribe free" बटण `#recap-signup` या भागावर नेतं. तिथे हा form ठेवायचा.
Flamingo प्रत्येक signup WordPress मध्येच साठवतो → CSV export करता येतो (हीच तुमची opt-in यादी).

## 1. Plugins

Plugins → Add New → **Contact Form 7** (Install → Activate) आणि **Flamingo** (Install → Activate).

## 2. Form (Contact → Add New → Title: `Weekly Recap Signup`)

**Form tab** — सगळं काढून हे paste करा:

```
<label> Your name
    [text* your-name autocomplete:name] </label>

<label> WhatsApp number (with country code)
    [tel* your-whatsapp placeholder "+91 98xxxxxxxx"] </label>

<label> Email (optional)
    [email your-email autocomplete:email] </label>

<label> Send the recap on
    [radio recap-channel use_label_element default:1 "WhatsApp" "Email" "Both"] </label>

[acceptance recap-consent] I agree to receive the Weekly Market Recap and occasional market updates from Sahare Wealth (AMFI-registered Mutual Fund Distributor, ARN-151469) on WhatsApp or email. I can unsubscribe at any time by replying STOP. This is market information, not investment advice. [/acceptance]

[submit "Get the Weekly Recap"]
```

**Mail tab:**

| Field | Value |
|---|---|
| To | `info@advisor4u.in` |
| From | `[_site_title] <wordpress@advisor4u.in>` |
| Subject | `New Weekly Recap signup: [your-name]` |
| Additional headers | `Reply-To: [your-email]` |

Message body:

```
Name: [your-name]
WhatsApp: [your-whatsapp]
Email: [your-email]
Send on: [recap-channel]
Consent: given ([_date] [_time])
Page: [_url]
```

**Messages tab** → "Sender's message was sent successfully":
`Thank you! You'll receive the Weekly Market Recap every Saturday.`

Save → वर दिसणारा shortcode copy करा, उदा. `[contact-form-7 id="abc123" title="Weekly Recap Signup"]`.

## 3. पानावर ठेवा

Pages → Global Markets → Edit with Elementor:

1. Dashboard shortcode च्या **खाली** नवीन Container/Section जोडा.
2. त्या Container चं Advanced → **CSS ID** = `recap-signup` (हे नाव बदलू नका — बटण इथेच येतं).
3. आत **Shortcode** widget → CF7 चा shortcode paste → Update.

## 4. रोजचं काम

- नवीन signups: Dashboard → **Flamingo → Inbound Messages** (Export → CSV).
- कोणी STOP पाठवला: Flamingo मध्ये ती नोंद Trash करा आणि तुमच्या पाठवण्याच्या यादीतून काढा.
- Spam वाढला तर: **Simple Cloudflare Turnstile** (मोफत) plugin → Contact Form 7 साठी चालू करा.
