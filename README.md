# Caixinha Automatica

Automated monthly fee collection system for Trilha UFPB. Generates PIX charges, sends email notifications, and reconciles payments via Google Sheets.

## Features

- **PIX Charge Generation**: Creates PIX charges via Efi (Gerencianet) API on the 5th business day of each month
- **Email Notifications**: Sends QR codes and copy-paste PIX codes to members via Resend
- **Payment Processing**: Reconciles received PIX payments with pending charges
- **Payment Reminders**: Sends reminder emails for overdue payments
- **Google Sheets Integration**: Tracks member payment status in a spreadsheet

## Architecture

```
src/
  jobs/           # Scheduled tasks (generate_charges, process_payments, send_reminders)
  services/       # External integrations (Efi, Resend, Google Sheets)
  templates/      # Email templates
  utils/          # Business day calculations
api/
  webhook.py      # Vercel serverless function for PIX webhooks
```

## Requirements

- Python 3.9+
- Efi (Gerencianet) account with PIX API access
- Google Cloud service account with Sheets API enabled
- Resend account for transactional emails

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables (see `.env.example`):
   - `EFI_CLIENT_ID`, `EFI_CLIENT_SECRET`, `EFI_PIX_KEY`, `EFI_CERTIFICATE_BASE64`
   - `GOOGLE_CREDENTIALS_BASE64`, `SPREADSHEET_ID`
   - `RESEND_API_KEY`, `EMAIL_FROM`

3. Deploy webhook to Vercel:
   ```bash
   vercel deploy
   ```

## Scheduled Jobs

Jobs run via GitHub Actions:

| Job | Schedule | Description |
|-----|----------|-------------|
| `generate-charges` | 5th business day, 9am BRT | Creates PIX charges for unpaid members |
| `process-payments` | Daily, 6am BRT | Reconciles received payments |
| `daily-reminder` | Daily, 10am BRT | Sends payment reminders |

## License

MIT
