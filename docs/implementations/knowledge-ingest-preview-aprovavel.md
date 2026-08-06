# Ingestão de conhecimento — preview aprovável antes de gravar

**Branch:** *(a definir)*
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/camada4-ingestao-conhecimento.md`.

Hoje, quando o worker de ingestão (`backend-crm/services/knowledge_ingest/ingest_worker.py`)
classifica os textos extraídos, ele já grava os itens `ai_extracted` diretamente em
`knowledge_items` (função `_insert_ai_item`) — sem passo de revisão humana antes da gravação.
Isso é seguro porque nunca sobrescreve categoria já preenchida pelo utilizador, mas significa que
conteúdo mal classificado ou impreciso só é corrigido depois de já estar ativo na base (visível ao
agente).

A ideia é introduzir um estado intermédio "draft": o job termina com os itens propostos mas ainda
não gravados, e o utilizador aprova (grava) ou descarta cada um antes de entrar na base — via um
novo endpoint `POST /ingest/{job_id}/apply`.

---

## Problemas Identificados (estado anterior)

1. **Gravação direta sem revisão:** `ingest_worker.py:_process_ingest_job` chama `_insert_ai_item`
   assim que a classificação retorna conteúdo para uma categoria — não há passo de confirmação.
2. **Sem endpoint de apply/descarte:** `routes/knowledge_ingest.py` só tem `POST /ingest` e
   `GET /ingest/{job_id}` — não existe rota para aprovar ou descartar itens propostos.

---

## Próximos passos

Este arquivo nasce como stub — a implementação real só começa depois do diagnóstico normal
(Plan Mode) ser feito e aprovado pelo utilizador, seguindo
`docs/implementations/_guia-documentar-implementacao.md`.
