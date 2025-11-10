# Agente Local de Automação

Este diretório contém o MVP do agente local responsável por executar jobs de automação (ex.: envios via WhatsApp) utilizando o Chrome instalado na máquina do usuário.

## Requisitos

- Python 3.10+
- Google Chrome instalado
- ChromeDriver gerenciado automaticamente pelo [webdriver-manager](https://github.com/SergeyPirogov/webdriver_manager)

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Variáveis de ambiente

| Variável | Descrição | Valor padrão |
| --- | --- | --- |
| `BACKEND_URL` | URL base do backend FastAPI | `http://localhost:8000` |
| `AGENT_ID` | Identificador único do agente | `local-agent` |
| `AGENT_TOKEN` | Token compartilhado com o backend | `changeme` |
| `JOB_TYPES` | Lista separada por vírgula com tipos de job aceitos | `whatsapp_send` |
| `POLL_INTERVAL` | Intervalo (segundos) entre polls ao backend | `5` |
| `CHROME_PROFILE_PATH` | Caminho para reutilizar o perfil do Chrome (mantém login do WhatsApp) | vazio |
| `HEADLESS` | Se `true`, abre o Chrome em modo headless | `false` |

Crie um arquivo `.env` ao lado de `main.py` para facilitar a configuração:

```env
BACKEND_URL=http://localhost:8000
AGENT_ID=meu-agente
AGENT_TOKEN=token-super-secreto
JOB_TYPES=whatsapp_send
POLL_INTERVAL=5
CHROME_PROFILE_PATH=C:\\Users\\usuario\\AppData\\Local\\Google\\Chrome\\User Data\\AgentProfile
HEADLESS=false
```

## Execução

```bash
python main.py
```

O agente irá:

1. Registrar-se no backend (`POST /api/agents/register`).
2. Entrar em loop buscando jobs (`GET /api/agents/next-job`).
3. Abrir o Chrome local via Selenium, reutilizando o perfil indicado.
4. Reportar o resultado da execução (`POST /api/agents/report`).

Os logs são gravados tanto no console quanto no arquivo `agent.log`.

## Empacotamento em `.exe`

Exemplo utilizando [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --name auto_digital_agent main.py
```

Inclua o arquivo `.env` e o `agent.log` (se necessário) no mesmo diretório do executável.

## Fluxo de dados

1. O CRM/Frontend enfileira um job de WhatsApp no backend.
2. O backend registra o job na tabela `jobs` com status `pending`.
3. O agente local busca o job, prepara o envio no WhatsApp Web e reporta o resultado.
4. O backend atualiza o status do job e da fila (`prospection_whatsapp_queue`), liberando o CRM para atualizar o lead.

## Texto pronto para repositório independente

```
# Agente Local AutoDigital

## Dependências
-- Python 3.10+
-- Google Chrome + ChromeDriver (gerenciado automaticamente)
-- Bibliotecas: python-dotenv, requests, selenium, webdriver-manager

## Variáveis de ambiente
- BACKEND_URL: URL da API FastAPI (ex.: https://api.suaempresa.com)
- AGENT_ID: identificador único do agente/instalação
- AGENT_TOKEN: token gerado no backend
- JOB_TYPES: tipos de job aceitos (ex.: whatsapp_send,email_send)
- POLL_INTERVAL: intervalo em segundos entre polls
- CHROME_PROFILE_PATH: caminho do perfil do Chrome para reutilizar login do WhatsApp
- HEADLESS: `true` para executar o Chrome sem interface

## Endpoints utilizados
- POST /api/agents/register
- GET  /api/agents/next-job
- POST /api/agents/report
- GET  /api/agents/overview (monitoramento opcional)

### Exemplo de payload whatsapp_send
```json
{
  "queue_id": 123,
  "lead_id": 42,
  "message_id": 88,
  "phone": "5531999990000",
  "body": "Olá! Podemos conversar sobre sua proposta?"
}
```

## Como executar
```bash
pip install -r requirements.txt
python main.py
```

## Empacotar com PyInstaller
```bash
pyinstaller --onefile --name auto_digital_agent main.py
```
```
