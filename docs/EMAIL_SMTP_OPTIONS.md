# Email / SMTP options (no Microsoft credentials)

The app sends email for reports, password resets, and MMR. Configure `.env` (or Render env vars).

**Render free web services block outbound SMTP** (ports 25, 465, 587). Gmail SMTP will **time out** there. Use the **Brevo HTTP API** instead: set **`BREVO_API_KEY`** and **`MAIL_DEFAULT_SENDER`** (sender verified in Brevo). The app uses HTTPS and does not open SMTP. On a **paid** Render instance, normal SMTP usually works again.

---

## Recommended: **Brevo** (free, no credit card)

- **Free:** 300 emails/day, no time limit.
- **Sign up:** [brevo.com](https://www.brevo.com) → create account.
- **Get SMTP key:**  
  **SMTP & API** (left menu) → **SMTP** tab → create an **SMTP key** (not the main API key).  
  Use your **login email** as username and this **SMTP key** as password.

Add to `.env`:

```env
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-login-email@injaaz.ae
MAIL_PASSWORD=your-brevo-smtp-key
MAIL_DEFAULT_SENDER=noreply@injaaz.ae
```

You may need to verify your sender (noreply@injaaz.ae) in Brevo before sending.

### Brevo API (HTTPS — use on Render free tier)

Get an **API key**: Brevo → **SMTP & API** → **API keys** → create a key with **Send emails** permission.

```env
BREVO_API_KEY=xkeysib-...
MAIL_DEFAULT_SENDER=noreply@injaaz.ae
```

You do **not** need `MAIL_SERVER` when `BREVO_API_KEY` is set; the app sends via `https://api.brevo.com/v3/smtp/email`.

---

## SendGrid (free trial, then paid)

- **Free:** 100 emails/day for 60 days.
- **Sign up:** [sendgrid.com](https://sendgrid.com) → **Settings** → **API Keys** → **Create API Key** (scope: **Mail Send**).
- **Username is the literal word** `apikey`; **password** is the API key you created.

```env
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=apikey
MAIL_PASSWORD=your-sendgrid-api-key
MAIL_DEFAULT_SENDER=noreply@injaaz.ae
```

Verify your sender/domain in SendGrid.

---

## Mailjet (free tier)

- **Free tier** available; see [mailjet.com](https://www.mailjet.com) for limits.
- **Sign up** → **Account settings** → **SMTP and SEND API** → use **API Key** as username and **Secret Key** as password.

```env
MAIL_SERVER=in-v3.mailjet.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-mailjet-api-key
MAIL_PASSWORD=your-mailjet-secret-key
MAIL_DEFAULT_SENDER=noreply@injaaz.ae
```

---

## Personal Gmail (@gmail.com)

You can use your **personal Gmail** (e.g. you@gmail.com). Emails are sent **from** that address. Recipients stay restricted to @injaaz.ae in the app.

**Steps:**

1. **Turn on 2-Step Verification:** [myaccount.google.com/security](https://myaccount.google.com/security) → **2-Step Verification** → turn it on.
2. **Create an App Password:** [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) → App: **Mail**, Device: **Other** (e.g. "Injaaz") → **Generate**. Copy the 16-character password (no spaces in `.env`).
3. In **`.env`** set:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=yourname@gmail.com
MAIL_PASSWORD=your-16-char-app-password
MAIL_DEFAULT_SENDER=yourname@gmail.com
```

Restart the app and try **Send Email**.

---

## Google Workspace (if @injaaz.ae is on Google)

If your organisation uses Google for **@injaaz.ae**:

1. Use the mailbox you want to send from (e.g. `noreply@injaaz.ae`).
2. In that Google account: **Security** → **2-Step Verification** (must be on) → **App passwords** → create one for “Mail”.
3. Use that **app password** (not your normal login password).

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=noreply@injaaz.ae
MAIL_PASSWORD=your-16-char-app-password
MAIL_DEFAULT_SENDER=noreply@injaaz.ae
```

---

## Summary

| Provider        | Free tier        | Best for                          |
|-----------------|------------------|------------------------------------|
| **Brevo**       | 300/day, no card | Easiest long-term free option      |
| **Personal Gmail** | With 2-Step + App pwd | Quick setup with your @gmail.com |
| SendGrid        | 100/day, 60 days | Short-term trial                   |
| Mailjet         | Free tier        | Alternative free SMTP              |
| Google Workspace| With your domain | If injaaz.ae uses Google           |

After editing `.env`, restart the Flask app. On Render, set the same variables in the dashboard and redeploy.
