# Agente Local de Automação

Este diretório contém o MVP do **Agente Local** responsável por consumir jobs do backend e executar as automações utilizando o Chrome instalado no computador do usuário. O agente foi pensado para rodar em Windows, mas funciona igualmente em macOS/Linux desde que os requisitos estejam atendidos.

## Requisitos

- Python 3.10+ (testado com 3.11)
- Google Chrome instalado
- Acesso aos endpoints do backend (FastAPI)
- Ambiente com `pip` disponível

## Instalação

```bash
python -m venv .venv
.venv\\Scripts\\activate           # Windows
# ou source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

## Variáveis de ambiente

O agente lê as configurações automaticamente a partir de um arquivo `.env` no diretório `agent-local/` (recomendado) ou, caso não exista, diretamente das variáveis de ambiente do sistema operacional. Principais chaves:

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `BACKEND_URL` | URL base do backend FastAPI | `http://localhost:8000` |
| `AGENT_ID` | Identificador único do agente (copiado do provisionamento no CRM) | `local-agent` |
| `AGENT_TOKEN` | Token simples usado para autenticação do agente (copiado do provisionamento no CRM) | `change-me` |
| `JOB_TYPES` | Lista (separada por vírgula) de tipos de job aceitos | `whatsapp_send` |
| `POLL_INTERVAL` | Intervalo em segundos entre buscas consecutivas quando há jobs disponíveis | `5` |
| `IDLE_INTERVAL` | Intervalo em segundos quando a fila está vazia ou em caso de erro | `15` |
| `CHROME_USER_DATA` | Caminho do diretório de perfil reutilizado pelo Chrome (mantém login do WhatsApp) | `%USERPROFILE%\.agent-local\chrome-profile` |
| `CHROME_BINARY` | Caminho do executável do Chrome (opcional) | Detectado automaticamente |
| `CHROME_HEADLESS` | Define `1`/`true` para executar em modo headless | `0` |
| `AGENT_LOG` | Caminho do arquivo de log (apêndice) | `./agent.log` |

Exemplo de `.env` (preencha `AGENT_ID`/`AGENT_TOKEN` com o par retornado pelo endpoint `/api/agents/provision` do backend-CRM):

```env
BACKEND_URL=http://localhost:8000
AGENT_ID=workstation-01
AGENT_TOKEN=super-secreto
JOB_TYPES=whatsapp_send
POLL_INTERVAL=4
IDLE_INTERVAL=12
CHROME_USER_DATA=C:\\Users\\user\\AppData\\Local\\AgentLocal\\profile
```

## Execução

Com o ambiente virtual ativado e o `.env` configurado:

```bash
python main.py
```

O agente registra-se no backend (`/api/agents/register`), busca jobs (`/api/agents/next-job`), executa as automações e reporta o resultado (`/api/agents/report`). Logs ficam disponíveis tanto no console quanto no arquivo definido em `AGENT_LOG`.

### Empacotamento (PyInstaller)

```bash
pyinstaller --onefile --name agent-local main.py
```

O executável gerado (por exemplo, `dist/agent-local.exe`) pode ser distribuído para usuários finais. Certifique-se de copiar o arquivo `.env` e a pasta de perfil (`CHROME_USER_DATA`) junto com o executável quando necessário.

## Estrutura

```
agent-local/
├── main.py
├── requirements.txt
├── README.md
└── agent/
    ├── __init__.py
    ├── config.py
    ├── jobs_client.py
    └── whatsapp_runner.py
```

## Observações

- O agente reutiliza a sessão do Chrome através do parâmetro `--user-data-dir`. Execute o WhatsApp Web manualmente na primeira vez para validar o login.
- Em caso de falha de conexão com o backend, o agente aplica um backoff simples e tenta novamente automaticamente.
- Futuras automações (e-mail, integrações externas, etc.) podem ser adicionadas criando novos runners e estendendo `process_job` em `main.py`.
