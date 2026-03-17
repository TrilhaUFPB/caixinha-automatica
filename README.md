# Caixinha Automática

Sistema automatizado de cobrança mensal para o Trilha UFPB. Envia cobranças PIX por email, processa comprovantes via Google Form, e registra pagamentos no Google Sheets.

## Como Funciona

1. **Cobrança (5º dia útil):** Envia email com chave PIX e link do Google Form para membros inadimplentes
2. **Comprovante:** Membro faz o PIX e envia comprovante pelo Google Form
3. **Processamento (diário):** Job lê respostas do form, valida e marca como "Pago" na planilha
4. **Lembrete (diário):** Após o 5º dia útil, envia lembretes para quem ainda não pagou

## Arquitetura

```
src/
  jobs/           # Tarefas agendadas (send_charges, process_receipts, send_reminders)
  services/       # Integrações (Google Sheets, SMTP email)
  templates/      # Templates de email HTML
  utils/          # Cálculo de dias úteis, configurações
```

## Tech Stack

| Componente     | Tecnologia           | Custo |
|----------------|----------------------|-------|
| Database       | Google Sheets        | Free  |
| Formulário     | Google Forms         | Free  |
| Cron Jobs      | GitHub Actions       | Free  |
| Notificações   | Email (SMTP / Gmail) | Free  |
| Linguagem      | Python 3.12+         | —     |

## Setup

1. Instalar dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Configurar variáveis de ambiente (veja `.env.example`):
   - `GOOGLE_CREDENTIALS_BASE64`, `SPREADSHEET_ID`
   - `PIX_KEY`, `PIX_KEY_TYPE`, `PIX_BENEFICIARY_NAME`
   - `GOOGLE_FORM_URL`
   - `SMTP_EMAIL`, `SMTP_PASSWORD`

3. Criar Google Form com campos: Email, Nome Completo, Mês de Referência, Valor, Comprovante
4. Conectar respostas do form à mesma planilha do `SPREADSHEET_ID`

## Jobs Agendados

Jobs rodam via GitHub Actions:

| Job | Schedule | Descrição |
|-----|----------|-----------|
| `send-charges` | 5º dia útil, 9h BRT | Envia email de cobrança com chave PIX |
| `process-receipts` | Diário, 8h BRT | Processa comprovantes do Google Form |
| `send-reminders` | Diário, 10h BRT | Envia lembretes para inadimplentes |

## GitHub Secrets Necessários

```
GOOGLE_CREDENTIALS_BASE64
SPREADSHEET_ID
SMTP_EMAIL
SMTP_PASSWORD
PIX_KEY
GOOGLE_FORM_URL
```

## License

MIT
