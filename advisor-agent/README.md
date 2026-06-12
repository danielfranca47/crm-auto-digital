# CRM Advisor Agent

Colaborador de desenvolvimento pessoal. Lê automaticamente o teu histórico de trabalho com o Claude Code, analisa o projecto e entrega um relatório diário no browser — sem precisares de escrever nada.

---

## Pré-requisitos

| Requisito | Como verificar |
|---|---|
| Python 3.10+ | `python --version` |
| Claude Code instalado e autenticado | `claude --version` |
| PC com acesso à internet | — |

---

## Arrancar pela primeira vez

### 1. Abrir um terminal na pasta do advisor

```
cd c:\crm-auto-digital\advisor-agent
```

### 2. Correr o script de arranque

```
start.bat
```

O script faz automaticamente:
- Verifica se o `claude` está disponível
- Cria o `.env` a partir do `.env.example` (sem necessidade de editar)
- Cria o ambiente virtual Python (`.venv`)
- Instala as dependências
- Arranca o servidor na porta 8005

### 3. Abrir o dashboard no browser

```
http://localhost:8005
```

---

## Arranques seguintes

A partir da segunda vez, basta correr `start.bat` de novo. O ambiente virtual e as dependências já existem — o arranque é rápido.

Se quiseres manter o advisor sempre a correr em segundo plano, podes:
- Deixar a janela do terminal aberta
- Ou adicionar o `start.bat` ao arranque automático do Windows (ver secção avançada abaixo)

---

## O que o dashboard mostra

Quando abres `http://localhost:8005`, vês 5 secções:

### Linha do Tempo
Cada sessão de trabalho dos últimos 7 dias, com:
- Data e hora
- Resumo do que foi pedido e feito
- Áreas do projecto afectadas (Backend CRM, Frontend, etc.)
- Branch em que estavas a trabalhar

### Avaliação Técnica
Texto de 2-4 parágrafos com:
- Qualidade geral do código e das decisões tomadas
- Consistência com a arquitectura definida no CLAUDE.md
- Progressão em relação aos objectivos do produto

### Pontos Fortes
O que estás a fazer bem, com evidências concretas das sessões. Útil para perceber padrões de trabalho que funcionam e devem continuar.

### Áreas de Melhoria
Lista de problemas técnicos identificados, ordenados por prioridade:
- **HIGH** (vermelho) — riscos ou problemas que afectam o produto
- **MEDIUM** (amarelo) — melhorias importantes mas não urgentes
- **LOW** (verde) — refinamentos de qualidade

Cada item tem a área afectada, o problema identificado e uma sugestão concreta.

### Próximas Prioridades
Top 3 do que fazer a seguir, com a justificação de porquê é prioritário neste momento do projecto.

---

## Quando a análise é gerada

| Momento | O que acontece |
|---|---|
| Arranque do servidor | Se o cache tiver mais de 18h, gera análise automaticamente |
| Todos os dias às 08:00 | Análise diária automática (enquanto o servidor estiver a correr) |
| Botão "Actualizar Agora" | Força uma nova análise imediatamente |

A análise demora entre 30 e 90 segundos. O dashboard actualiza-se sozinho enquanto a análise está em curso.

---

## O que o advisor lê para gerar a análise

O advisor nunca lê o conteúdo dos teus ficheiros de código directamente. Lê apenas:

1. **Histórico de sessões do Claude Code** — os ficheiros `.jsonl` em `~/.claude/projects/c--crm-auto-digital/`
   - O primeiro pedido de cada sessão (o que pediste ao Claude)
   - As ferramentas usadas (quais ficheiros foram editados, que comandos correram)
   - A branch em que estavas
   - A data e hora

2. **CLAUDE.md** — a visão geral do projecto (arquitectura, convenções)

3. **`docs/architecture/`** — lista dos documentos de arquitectura disponíveis

4. **Git log** — commits dos últimos 14 dias

Tudo isto é montado num prompt estruturado e enviado ao Claude via `claude --print`.

---

## Configuração opcional

O ficheiro `.env` (criado automaticamente a partir de `.env.example`) tem estes parâmetros:

```env
# Caminho para os históricos do Claude Code
# (por defeito aponta para o teu projecto nesta máquina)
TRANSCRIPTS_DIR=C:\Users\Daniel França\.claude\projects\c--crm-auto-digital

# Caminho raiz do projecto CRM
PROJECT_DIR=c:\crm-auto-digital

# Hora da análise diária (formato HH:MM)
DAILY_ANALYSIS_TIME=08:00

# Porta do servidor
PORT=8005
```

Para mudar a hora da análise automática, edita `DAILY_ANALYSIS_TIME`. Para mudar a porta, edita `PORT`.

---

## Solução de problemas

### "Comando 'claude' não encontrado"
O Claude Code não está no PATH. Tenta:
1. Fechar e reabrir o terminal
2. Reinstalar o Claude Code
3. Verificar com `where claude` se está instalado

### "Análise falhou" no log
O advisor tentou correr mas houve um erro. Causas comuns:
- **Sem internet** — o `claude --print` precisa de estar online
- **Sessão expirada** — corre `claude login` num terminal e tenta de novo
- **Timeout** — contexto muito longo, aguarda e tenta de novo

### O dashboard mostra análise antiga
Clica em **Actualizar Agora** para forçar nova análise.

---

## Arranque automático com o Windows (opcional)

Para o advisor arrancar automaticamente quando ligares o PC:

1. Abre o **Gestor de Tarefas Agendadas** do Windows (`taskschd.msc`)
2. Cria uma nova tarefa básica
3. Gatilho: "Ao iniciar sessão"
4. Acção: Iniciar programa → `c:\crm-auto-digital\advisor-agent\start.bat`

Ou via PowerShell:
```powershell
$action = New-ScheduledTaskAction -Execute "c:\crm-auto-digital\advisor-agent\start.bat"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "CRM Advisor" -Action $action -Trigger $trigger
```

---

## Estrutura de ficheiros

```
advisor-agent/
├── main.py                  # Servidor FastAPI (porta 8005) + scheduler
├── start.bat                # Script de arranque Windows
├── requirements.txt         # Dependências Python
├── .env                     # Configuração local (gerado automaticamente)
├── .env.example             # Template de configuração
├── readers/
│   ├── transcript_reader.py  # Lê históricos de sessão do Claude Code
│   ├── session_parser.py     # Extrai resumo de cada sessão
│   └── project_reader.py     # Lê CLAUDE.md + git log
├── services/
│   ├── analyzer.py           # Monta contexto e chama claude --print
│   └── cache.py              # Persiste análise em JSON
├── templates/
│   └── index.html            # Dashboard web
└── data/
    └── analysis_cache.json   # Cache da última análise (gerado automaticamente)
```
