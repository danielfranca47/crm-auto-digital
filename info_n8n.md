# Esclarecimento: "n8n" no Código

**Data:** 2026-03-23

---

## Resumo

O nome **n8n** aparece em alguns lugares do código (tipos de job, comentários, nomes de variáveis), mas é apenas um **artefato histórico** de uma ideia inicial de arquitetura que foi descartada.

**n8n nunca foi implantado. Nenhum workflow n8n opera em nenhum fluxo do sistema.**

---

## Por que o nome aparece?

Na concepção original do projeto, o plano era usar a plataforma n8n (ferramenta de automação low-code) como orquestrador externo dos fluxos de IA. Esse plano foi abandonado antes da implementação, mas alguns identificadores já tinham sido criados no código e permaneceram como nomes "legados".

---

## Onde o nome aparece e o que realmente é

| Onde aparece | Nome com "n8n" | O que é na prática |
|---|---|---|
| `backend-crm/services/jobs_service.py` | `TYPE_WHATSAPP_INBOUND_N8N = "whatsapp.inbound.n8n"` | Tipo de job inbound processado pelo `backend-executors` |
| `backend-crm/routes/executor.py` | `TYPE_WHATSAPP_INBOUND_N8N` | Identificador de job — sem relação com a plataforma n8n |
| `backend-crm/services/followup_channel_context.py` | `expand_type_variants(TYPE_WHATSAPP_INBOUND_N8N)` | Resolução de canal para jobs de follow-up |
| `backend-crm/services/followup_reconciler.py` | Comentários antigos | Reconciliador interno — não depende de n8n |

---

## Quem realmente faz o trabalho de "executor"

O substituto real do n8n é o **`backend-executors`** — um serviço Python interno do próprio projeto.

### Estrutura do backend-executors

```
backend-executors/
├── app/
│   ├── main.py                        # FastAPI com rota de health check apenas
│   ├── workers/
│   │   └── whatsapp_worker.py         # Processo de polling — consome a fila de jobs
│   ├── runners/
│   │   └── whatsapp.py                # Executa cada job: contexto → LLM → WhatsApp
│   ├── services/
│   │   ├── decision_engine.py         # Motor de decisão + builder de prompts LLM
│   │   ├── llm_service.py             # Chamada HTTP ao LLM (Claude/OpenAI)
│   │   ├── fast_path.py               # Decisões sem LLM (handoff imediato, bot desabilitado)
│   │   ├── handoff_policy.py          # Política de handoff humano
│   │   ├── meeting_scheduler.py       # Agendamento de reuniões pós-decisão
│   │   └── field_extractor.py         # Extração de campos de qualificação
│   └── clients/
│       ├── crm_client.py              # HTTP para backend-crm (jobs, contexto, confirmação)
│       └── core_client.py             # HTTP para backend-core (envio WhatsApp via UazAPI)
```

### Como funciona

1. `whatsapp_worker.py` roda como processo separado (não como servidor HTTP)
2. Faz polling em `GET /internal/jobs/next` no `backend-crm` a cada 0.5–30s
3. Processa jobs dos tipos:
   - `whatsapp.inbound.n8n` — mensagem inbound recebida (lead enviou mensagem)
   - `whatsapp.followup.tick` — follow-up agendado (bot envia mensagem proativamente)
4. Para cada job: busca contexto → roda LLM → envia via backend-core → confirma

---

## O que ainda precisa de atenção

Mesmo com o `backend-executors` funcionando, o **reconciliador de follow-up** ainda precisa ser acionado periodicamente. O reconciliador é quem cria os jobs `whatsapp.followup.tick` na fila. Sem ele ser chamado, o worker do `backend-executors` nunca recebe esses jobs.

Ver seção 4.1 do [diagnostico_followup.md](diagnostico_followup.md) para detalhes e solução recomendada.

---

## Onde renomear (quando houver oportunidade)

Não é urgente, mas para clareza futura, estes identificadores poderiam ser renomeados:

| Atual | Sugerido |
|-------|---------|
| `TYPE_WHATSAPP_INBOUND_N8N` | `TYPE_WHATSAPP_INBOUND` |
| `"whatsapp.inbound.n8n"` (string do tipo de job) | `"whatsapp.inbound"` |

> Atenção: renomear o **valor string do tipo de job** exige migração de dados (jobs pendentes no banco com o tipo antigo deixariam de ser encontrados pelo worker). Renomear apenas a **constante Python** é seguro sem migração.
