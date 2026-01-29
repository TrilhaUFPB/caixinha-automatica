# Plan: PIX Payment Automation - Caixinha do Trilha

## Overview

Automated system to charge R$40/month from members via PIX, using Efí (Gerencianet) as the payment gateway.

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Google Sheets  │◄────►│  GitHub Actions │─────►│     Efí API     │
│   (database)    │      │   (cron jobs)   │      │  (PIX/QR Code)  │
└─────────────────┘      └─────────────────┘      └─────────────────┘
        ▲                        │                        │
        │                        ▼                        │
        │                ┌─────────────────┐              │
        │                │      Email      │              │
        │                │  (notifications)│              │
        │                └─────────────────┘              │
        │                                                 ▼
        │                ┌─────────────────┐      ┌─────────────────┐
        └────────────────│     Vercel      │◄─────│     Webhook     │
                         │   (endpoint)    │      │  (confirmation) │
                         └─────────────────┘      └─────────────────┘
```

---

## Tech Stack

| Component | Technology | Cost |
|-----------|------------|------|
| PIX Gateway | Efí (Gerencianet) | ~1% per transaction |
| Database | Google Sheets | Free |
| Cron Jobs | GitHub Actions | Free |
| Webhook | Vercel (Serverless Python) | Free |
| Notifications | Email (Resend) | Free up to 3k/month |
| Language | Python 3.11+ | - |

---

## Spreadsheet Structure

The spreadsheet needs this structure:

| A (Name) | B (Email) | C (JAN) | D (FEB) | ... | N (DEC) |
|----------|-----------|---------|---------|-----|---------|
| Beatriz | beatriz@email.com | Paid | Paid | ... | |
| Clara | clara@email.com | Paid | | ... | |

**Required change:** Add column B with member emails.

---

## Automated Flows

### 1. Charge Generation (5th business day of month)

```
GitHub Actions (cron)
    ↓
Read spreadsheet via Google Sheets API
    ↓
For each member without "Paid" in current month:
    ↓
Create PIX charge on Efí (dynamic QR Code)
    ↓
Send email with:
  - QR Code image
  - PIX copy-paste code
  - Amount: R$40.00
  - Due date: end of month
```

### 2. Payment Confirmation (real-time)

```
Member pays PIX
    ↓
Efí sends webhook to Vercel
    ↓
Vercel validates webhook signature
    ↓
Updates spreadsheet: month cell → "Paid"
    ↓
(Optional) Send confirmation email
```

### 3. Reminders for Defaulters (daily)

```
GitHub Actions (daily cron, 10am)
    ↓
Read spreadsheet
    ↓
Filter members without "Paid" in current month
    ↓
Send reminder email with QR Code
```

---

## Project Structure

```
caixinha-automatica/
├── .github/
│   └── workflows/
│       ├── generate-charges.yml    # Cron: 5th business day
│       └── daily-reminder.yml      # Cron: every day 10am
├── api/
│   └── webhook.py                  # Vercel serverless function
├── src/
│   ├── services/
│   │   ├── efi.py                  # Efí API integration
│   │   ├── sheets.py               # Google Sheets integration
│   │   └── email.py                # Email sending
│   ├── jobs/
│   │   ├── generate_charges.py     # Main charging job
│   │   └── send_reminders.py       # Reminder job
│   └── utils/
│       ├── business_days.py        # Business day calculation
│       └── config.py               # Environment config
├── requirements.txt
├── vercel.json
├── pyproject.toml
└── .env.example
```

---

## Required Setup

### 1. Efí (Gerencianet)

- [ ] Create account at [Efí](https://sejaefi.com.br)
- [ ] Generate API credentials (Client ID + Client Secret)
- [ ] Generate `.p12` certificate for authentication
- [ ] Register PIX key
- [ ] Configure webhook URL: `https://your-project.vercel.app/api/webhook`

### 2. Google Sheets API

- [ ] Create project in Google Cloud Console
- [ ] Enable Google Sheets API
- [ ] Create Service Account
- [ ] Download JSON credentials
- [ ] Share spreadsheet with Service Account email

### 3. GitHub Secrets

```
EFI_CLIENT_ID=xxx
EFI_CLIENT_SECRET=xxx
EFI_CERTIFICATE_BASE64=xxx  # .p12 certificate in base64
EFI_PIX_KEY=xxx             # your PIX key
GOOGLE_CREDENTIALS=xxx       # service account JSON in base64
SPREADSHEET_ID=xxx          # spreadsheet ID
RESEND_API_KEY=xxx          # email service
```

### 4. Vercel

- [ ] Create project on Vercel
- [ ] Connect to GitHub repository
- [ ] Set environment variables (same as GitHub)

---

## Implementation Timeline

### Phase 1: Setup (1-2 days)
- [ ] Configure accounts (Efí, Google Cloud, Vercel)
- [ ] Obtain all credentials
- [ ] Setup Python project with dependencies

### Phase 2: Core Integrations (2-3 days)
- [ ] Google Sheets integration (read/write)
- [ ] Efí integration (generate PIX, check status)
- [ ] Email integration (Resend)

### Phase 3: Jobs and Webhook (1-2 days)
- [ ] Charge generation job
- [ ] Daily reminder job
- [ ] Webhook for payment confirmation

### Phase 4: Deploy and Testing (1 day)
- [ ] Deploy webhook on Vercel
- [ ] Configure GitHub Actions
- [ ] Test complete flow with R$0.01 PIX

---

## GitHub Actions Cron Schedule

### Charge Generation
```yaml
# Every day 1-7 at 9am, script checks if it's 5th business day
on:
  schedule:
    - cron: '0 12 1-7 * *'  # 9am BRT (12pm UTC)
```

### Daily Reminders
```yaml
# Every day at 10am
on:
  schedule:
    - cron: '0 13 * * *'  # 10am BRT (1pm UTC)
```

---

## Email Templates

### Initial Charge
```
Subject: 💰 Trilha Monthly Fee - {MONTH}/{YEAR}

Hi {NAME}!

Time to contribute to this month's fund.

Amount: R$ 40.00
Due date: {LAST_DAY_OF_MONTH}

[PIX QR CODE]

Or copy the code: {PIX_COPY_PASTE}

Questions? Just reach out!
```

### Reminder
```
Subject: ⏰ Reminder: {MONTH} payment pending

Hi {NAME}!

We haven't received your payment for this month yet.

[PIX QR CODE]

PIX code: {PIX_COPY_PASTE}
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Webhook doesn't arrive | Daily polling as fallback to verify payments |
| Email goes to spam | Use custom domain + Resend (good reputation) |
| Manual spreadsheet edits break logic | Robust validation + logging |
| Google API rate limits | Caching + batch updates |

---

## Next Steps

1. **You:** Add email column to spreadsheet
2. **You:** Create Efí account and obtain credentials
3. **Me:** Implement base code
4. **Together:** Test with real R$0.01 transaction
