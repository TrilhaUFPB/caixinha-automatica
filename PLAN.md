# Plan: Refactor — PIX com Google Form + Comprovante

## Contexto

O sistema atual usa a Efí (Gerencianet) como gateway PIX para gerar cobranças dinâmicas (QR Codes individuais), processar pagamentos via webhook/polling, e reconciliar automaticamente. Isso funciona, mas adiciona complexidade (certificados mTLS, API da Efí, webhook na Vercel, txid mappings) e custo (~1% por transação).

**Nova abordagem:** enviar a chave PIX estática por email, membro paga manualmente, e envia o comprovante via Google Form. Um job processa as respostas e atualiza a planilha.

---

## Arquitetura Nova

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Google Sheets  │◄────►│  GitHub Actions  │─────►│   Email (SMTP)  │
│   (membros)     │      │   (cron jobs)    │      │  chave PIX +    │
│                 │      │                  │      │  link do Form   │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                 │
                                 ▼
                         ┌─────────────────┐
                         │  Google Form     │
                         │  (comprovante)   │
                         └────────┬────────┘
                                  │ respostas vão pra
                                  ▼
                         ┌─────────────────┐
                         │  Sheet Respostas │──► Job processa
                         │  (automática)    │    e marca "Pago"
                         └─────────────────┘
```

### O que muda

| Antes (Efí)                          | Depois (Google Form)                        |
|--------------------------------------|---------------------------------------------|
| Efí API + certificado mTLS           | Chave PIX estática no email                 |
| QR Code dinâmico por membro          | Chave PIX única pra todos                   |
| Webhook na Vercel                    | Google Form + sheet de respostas             |
| Polling diário na Efí como fallback  | Job lê respostas do form                    |
| txid mapping sheet                   | Respostas do form já identificam o membro   |
| ~1% por transação                    | R$ 0,00                                     |

---

## Tech Stack

| Componente     | Tecnologia                  | Custo |
|----------------|-----------------------------|-------|
| Database       | Google Sheets               | Free  |
| Formulário     | Google Forms                | Free  |
| Cron Jobs      | GitHub Actions              | Free  |
| Notificações   | Email (SMTP / Gmail)        | Free  |
| Linguagem      | Python 3.12+                | —     |

**Removido:** Efí (efipay), Vercel, Resend, webhook.

---

## Estrutura da Planilha

### Aba principal — `2026` (já existe)

| A (Pessoas) | B (Email)           | C (Janeiro) | D (Fevereiro) | ... | N (Dezembro) |
|-------------|---------------------|-------------|---------------|-----|--------------|
| Beatriz     | beatriz@email.com   | Pago        | Pago          | ... |              |
| Clara       | clara@email.com     | Pago        |               | ... |              |

### Aba de respostas do form — `Respostas` (criada automaticamente pelo Google Forms)

| Timestamp           | Email            | Nome Completo | Valor Pago (R$) | Mês que estou pagando    | Comprovante (link Drive) |
|---------------------|------------------|---------------|-----------------|--------------------------|--------------------------|
| 2026-03-15 10:30:00 | clara@email.com  | Clara         | 40              | Março                    | https://drive.google.com/... |
| 2026-03-20 14:00:00 | joao@email.com   | João          | 200             | Janeiro;Fevereiro;Março;Abril;Maio | https://drive.google.com/... |

> **Nota:** quando você conecta um Google Form a uma spreadsheet, o Google cria essa aba automaticamente. Para caixas de seleção (multi-select), o Google salva os valores separados por `;` numa única célula. O job precisa fazer split por `;` e marcar cada mês como "Pago".

---

## Google Form — Estrutura

Criar um Google Form com os seguintes campos:

| Campo                  | Tipo                   | Obrigatório | Opções / Validação                                         |
|------------------------|------------------------|-------------|-------------------------------------------------------------|
| Email                  | Coletar email (config) | Sim         | Automático do Google Forms                                  |
| Nome Completo          | Resposta curta         | Sim         | —                                                           |
| Valor Pago (R$)        | Resposta curta         | Sim         | Validação: número (permite valor total, ex: 200 pra 5 meses)|
| Mês que estou pagando  | Caixas de seleção      | Sim         | Janeiro, Fevereiro, ..., Dezembro (multi-select)            |
| Comprovante do PIX     | Upload de arquivo      | Sim         | Tipos: imagem (png, jpg) ou PDF                             |

**Setup manual (uma vez):**
1. Criar o Google Form no Google Drive
2. Ir em "Respostas" → ícone do Sheets → "Criar nova planilha" → selecionar a planilha existente (`caixinha-automatica`)
3. O Google vai criar uma aba nova (ex: `Respostas do formulário 1`) dentro da mesma spreadsheet
4. Copiar a URL do form pra colocar na env `GOOGLE_FORM_URL`

---

## Fluxos Automatizados

### 1. Envio de Cobrança (5º dia útil do mês)

```
GitHub Actions (cron, dias 1-10, 9h BRT)
    ↓
Verifica se hoje é o 5º dia útil
    ↓
Lê planilha "2026" via Google Sheets API
    ↓
Para cada membro sem "Pago" no mês atual:
    ↓
Envia email com:
  - Chave PIX (estática)
  - Valor: R$ 40,00 (ou R$ 25,00 para TECPRED)
  - Link do Google Form para enviar comprovante
  - Prazo: último dia do mês
```

### 2. Processamento de Comprovantes (diário)

```
GitHub Actions (cron diário, 8h BRT)
    ↓
Lê aba "Respostas" da planilha
    ↓
Para cada resposta ainda não processada:
    ↓
Cruza nome/email da resposta com aba "2026"
    ↓
Valida (nome existe, mês válido, valor correto)
    ↓
Marca membro como "Pago" na aba "2026"
    ↓
Marca resposta como "Processado" (nova coluna na aba Respostas)
    ↓
Envia email de confirmação
```

### 3. Lembrete para Inadimplentes (diário, após 5º dia útil)

```
GitHub Actions (cron, dias 8-31, 10h BRT)
    ↓
Verifica se é dia útil
    ↓
Lê planilha "2026"
    ↓
Filtra membros sem "Pago" no mês atual
    ↓
Envia email lembrete com:
  - Chave PIX
  - Link do Google Form
  - Valor pendente
```

---

## Estrutura do Projeto (após refactor)

```
caixinha-automatica/
├── .github/
│   └── workflows/
│       ├── send-charges.yml          # Cron: 5º dia útil (REESCRITO)
│       ├── process-receipts.yml      # Cron: diário 8h (NOVO, substitui process-payments)
│       └── send-reminders.yml        # Cron: diário 10h (REESCRITO, renomeado)
├── src/
│   ├── jobs/
│   │   ├── send_charges.py           # Envia email de cobrança (REESCRITO, sem Efí)
│   │   ├── process_receipts.py       # Processa respostas do form (NOVO)
│   │   └── send_reminders.py         # Envia lembretes (SIMPLIFICADO, sem Efí)
│   ├── services/
│   │   ├── sheets.py                 # Google Sheets (SIMPLIFICADO)
│   │   └── email.py                  # SMTP email (SIMPLIFICADO, sem QR code)
│   ├── templates/
│   │   ├── charge_email.html         # REESCRITO (chave PIX + link form)
│   │   ├── reminder_email.html       # REESCRITO (chave PIX + link form)
│   │   └── confirmation_email.html   # Mantém (pequenos ajustes)
│   └── utils/
│       ├── business_days.py          # Mantém como está
│       └── config.py                 # SIMPLIFICADO (remove Efí config)
├── requirements.txt                  # SIMPLIFICADO
├── pyproject.toml                    # SIMPLIFICADO
├── .env.example                      # ATUALIZADO
└── README.md                         # ATUALIZADO
```

### Arquivos REMOVIDOS

| Arquivo                            | Motivo                                 |
|------------------------------------|----------------------------------------|
| `src/services/efi.py`             | Toda integração com Efí removida       |
| `src/services/payment_processor.py`| Substituído por `process_receipts.py`  |
| `src/jobs/generate_charges.py`    | Substituído por `send_charges.py`      |
| `src/jobs/process_payments.py`    | Substituído por `process_receipts.py`  |
| `src/jobs/register_webhook.py`    | Webhook não existe mais                |
| `src/jobs/debug_payments.py`      | Debug da Efí, não relevante            |
| `api/webhook.py`                  | Vercel endpoint removido               |
| `vercel.json`                     | Sem Vercel                             |
| `certificado.pem`                 | Certificado da Efí                     |
| `Trilha Certificate.p12`          | Certificado da Efí                     |

---

## Variáveis de Ambiente

### Novas (`.env.example`)

```env
# Google Sheets
GOOGLE_CREDENTIALS_BASE64=base64_encoded_service_account_json
SPREADSHEET_ID=your_spreadsheet_id
FORM_RESPONSES_SHEET_NAME=Respostas do formulário 1

# PIX
PIX_KEY=email@trilha.com
PIX_KEY_TYPE=email
PIX_BENEFICIARY_NAME=Trilha UFPB

# Google Form
GOOGLE_FORM_URL=https://docs.google.com/forms/d/e/xxx/viewform

# Email (SMTP / Gmail)
SMTP_EMAIL=caixinha@trilha.ufpb.br
SMTP_PASSWORD=your_app_password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
EMAIL_FROM_NAME=Caixinha Trilha

# Valores
DEFAULT_CHARGE_AMOUNT=40.00
TECPRED_CHARGE_AMOUNT=25.00
```

### Removidas

```
EFI_CLIENT_ID
EFI_CLIENT_SECRET
EFI_CERTIFICATE_BASE64
EFI_PIX_KEY
EFI_SANDBOX
RESEND_API_KEY
EMAIL_FROM (Resend)
WEBHOOK_SECRET
```

### GitHub Secrets (atualizados)

```
GOOGLE_CREDENTIALS_BASE64
SPREADSHEET_ID
SMTP_EMAIL
SMTP_PASSWORD
PIX_KEY
GOOGLE_FORM_URL
```

---

## Detalhes de Implementação

### 1. `src/services/sheets.py` — Mudanças

**Mantém:** `get_members()`, `get_unpaid_members()`, `mark_as_paid()`, `Member` dataclass.

**Remove:** `save_txid_mapping()`, `get_txid_mappings()` (não precisa mais de txid).

**Adiciona:**

```python
@dataclass
class FormResponse:
    timestamp: str
    email: str
    name: str
    amount: str
    months: list[str]  # ["Março"] ou ["Janeiro", "Fevereiro", "Março", ...]
    receipt_url: str
    processed: bool

def get_unprocessed_responses(self, sheet_name: str = "Respostas do formulário 1") -> list[FormResponse]:
    """Lê respostas do Google Form que ainda não foram processadas."""
    ...

def mark_response_as_processed(self, sheet_name: str, row: int, status: str = "Processado") -> None:
    """Marca uma resposta do form como processada (adiciona coluna extra)."""
    ...
```

### 2. `src/services/email.py` — Mudanças

**Simplifica:** remove toda lógica de QR code inline (`_extract_image_data`, `MIMEImage`).

**Mantém:** `_load_template()`, `_render_template()`, `_send_email()`.

**Atualiza assinaturas:**

```python
def send_charge_email(self, to, name, pix_key, pix_key_type, beneficiary_name, form_url, due_date, amount):
    """Envia email com chave PIX e link do form."""

def send_reminder_email(self, to, name, pix_key, form_url, amount):
    """Envia lembrete com chave PIX e link do form."""

def send_confirmation_email(self, to, name, amount, month):
    """Mantém igual (sem QR code, já não tinha)."""
```

### 3. `src/jobs/send_charges.py` — Novo (substitui `generate_charges.py`)

```python
def run_send_charges(force=False, send_email=True, member_filter=None) -> dict:
    """
    1. Verifica se é 5º dia útil (ou force=True)
    2. Lê membros não pagos da planilha
    3. Para cada um, envia email com chave PIX + link do form
    4. Retorna resumo
    """
```

**Diferença principal:** não cria cobrança na Efí, não gera QR code, não salva txid. Só envia email.

### 4. `src/jobs/process_receipts.py` — Novo (substitui `process_payments.py`)

```python
def run_process_receipts() -> dict:
    """
    1. Lê respostas não processadas do Google Form (aba Respostas)
    2. Para cada resposta:
       a. Valida: nome existe na planilha? meses são válidos? valor bate?
       b. Cruza email/nome da resposta com aba "2026"
       c. Faz split dos meses (separados por ";") 
       d. Marca como "Pago" na aba "2026" para CADA mês selecionado
       e. Marca resposta como "Processado"
       f. Envia email de confirmação (listando os meses pagos)
    3. Retorna resumo (processados, erros, já pagos)
    """
```

**Lógica de matching membro:**
1. Match por email exato (mais confiável)
2. Fallback: match por nome (case-insensitive, strip)
3. Se não encontrar → loga warning, marca como "Não encontrado"

**Validações:**
- Valor informado bate com `qtd_meses × valor_do_membro` (40 ou 25 por mês)
- Cada mês é válido e corresponde a uma coluna na planilha
- Membro existe na planilha
- Membro não está já marcado como "Pago" naquele mês (idempotência, pula meses já pagos)

### 5. `src/jobs/send_reminders.py` — Simplificado

Remove toda dependência da Efí. Não gera mais QR code. Envia email com chave PIX estática + link do form.

### 6. Templates de Email — Reescritos

**`charge_email.html`:** remove seção do QR Code e PIX copia-e-cola. Adiciona:
- Chave PIX estática com tipo (email/telefone/CPF)
- Nome do beneficiário (pra conferência)
- Botão "Enviar Comprovante" com link pro Google Form

**`reminder_email.html`:** mesma estrutura, tom de lembrete.

**`confirmation_email.html`:** mantém como está (já não tem QR code).

### 7. GitHub Actions Workflows

**`send-charges.yml`** (renomeado de `generate-charges.yml`):
- Remove steps de certificado Efí
- Remove envs da Efí
- Adiciona envs: `PIX_KEY`, `GOOGLE_FORM_URL`
- Roda `python -m src.jobs.send_charges`

**`process-receipts.yml`** (renomeado de `process-payments.yml`):
- Remove steps de certificado Efí
- Remove envs da Efí
- Roda `python -m src.jobs.process_receipts`
- Cron: diário 10h BRT 

**`send-reminders.yml`** (renomeado de `daily-reminder.yml`):
- Remove steps de certificado Efí
- Remove envs da Efí
- Adiciona envs: `PIX_KEY`, `GOOGLE_FORM_URL`
- Roda `python -m src.jobs.send_reminders`

### 8. `requirements.txt` / `pyproject.toml` — Simplificados

**Remove:** `efipay`, `resend`, `vercel`, `requests` (se não usar mais).

**Mantém:** `gspread`, `google-auth`, `holidays`.

```
google-auth>=2.48.0
gspread>=6.2.1
holidays>=0.40
```

---

## Setup Manual (Uma Vez)

### 1. Google Form
- [ ] Criar Google Form com os campos definidos acima
- [ ] Nas configurações do form: marcar "Coletar endereços de email"
- [ ] Conectar respostas à planilha existente (mesma do `SPREADSHEET_ID`)
- [ ] Copiar URL do form

### 2. Aba de Respostas
- [ ] Verificar o nome exato da aba criada pelo Google Forms (geralmente "Respostas do formulário 1")
- [ ] Garantir que o service account do Google tem acesso de edição à planilha (já tem, se não mudou)

### 3. GitHub Secrets
- [ ] Remover secrets antigos: `EFI_CLIENT_ID`, `EFI_CLIENT_SECRET`, `EFI_CERTIFICATE_BASE64`, `EFI_PIX_KEY`
- [ ] Adicionar novos: `PIX_KEY`, `GOOGLE_FORM_URL`
- [ ] Manter: `GOOGLE_CREDENTIALS_BASE64`, `SPREADSHEET_ID`, `SMTP_EMAIL`, `SMTP_PASSWORD`

### 4. Chave PIX
- [ ] Definir qual chave PIX usar (email, telefone, CPF, ou aleatória)
- [ ] Anotar o nome do beneficiário que aparece na hora do PIX

---

## Plano de Implementação

### Fase 1: Limpeza e Setup (criar form + atualizar configs)
- [ ] Criar Google Form e conectar à planilha
- [ ] Atualizar `.env.example` com novas variáveis
- [ ] Atualizar `requirements.txt` e `pyproject.toml` (remover `efipay`, `resend`, `vercel`)
- [ ] Atualizar `src/utils/config.py` (remover config da Efí)

### Fase 2: Services (sheets + email)
- [ ] Simplificar `src/services/sheets.py` (remover txid, adicionar form responses)
- [ ] Simplificar `src/services/email.py` (remover QR code, usar chave PIX + link form)
- [ ] Reescrever templates de email

### Fase 3: Jobs
- [ ] Criar `src/jobs/send_charges.py` (substituir `generate_charges.py`)
- [ ] Criar `src/jobs/process_receipts.py` (substituir `process_payments.py`)
- [ ] Simplificar `src/jobs/send_reminders.py`

### Fase 4: Workflows + Cleanup
- [ ] Reescrever `.github/workflows/send-charges.yml`
- [ ] Reescrever `.github/workflows/process-receipts.yml`
- [ ] Reescrever `.github/workflows/send-reminders.yml`
- [ ] Remover workflow `test-e2e.yml` (se era específico da Efí)
- [ ] Remover arquivos: `api/webhook.py`, `vercel.json`, `src/services/efi.py`, `src/services/payment_processor.py`, `src/jobs/generate_charges.py`, `src/jobs/process_payments.py`, `src/jobs/register_webhook.py`, `src/jobs/debug_payments.py`, `certificado.pem`, `Trilha Certificate.p12`
- [ ] Atualizar `README.md`

### Fase 5: Teste
- [ ] Testar envio de email de cobrança (workflow_dispatch manual)
- [ ] Preencher o Google Form como teste
- [ ] Rodar job de processamento e verificar se marca "Pago" na planilha
- [ ] Testar lembrete
- [ ] Verificar idempotência (submeter form 2x pro mesmo mês)

---

## Futuro: Dashboard

Com os dados agora estruturados (aba principal + aba de respostas do form), um dashboard pode facilmente calcular:

| Métrica                        | Fonte                      |
|--------------------------------|----------------------------|
| Taxa de pagamento por mês      | Aba "2026"                 |
| Tempo médio pra pagar          | Timestamp do form vs dia 5 |
| Membros inadimplentes          | Aba "2026" (sem "Pago")    |
| Total arrecadado por mês       | Aba Respostas (soma valor) |
| Histórico de pagamento/membro  | Aba "2026" (linha inteira) |
| Comprovantes (auditoria)       | Links do Drive na aba      |

Opções de dashboard: Google Looker Studio (grátis, conecta direto ao Sheets), Streamlit, ou Metabase.
