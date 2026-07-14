# Agent-Local — Melhorias Futuras

**Versão-alvo: v3.** A v2 do agent-local está documentada em
[`docs/architecture/agent-local-app.md`](../architecture/agent-local-app.md).
Os itens abaixo, quando implementados, formam a v3.

> Contexto: itens deixados de fora na graduação de `agent-local-v2-app-standalone.md`
> e `agentlocal-assistente-ia.md` (ver `docs/architecture/agent-local-app.md` para a
> arquitectura actual). Nenhum destes itens é bloqueante — todos os cenários de teste
> das duas implementações originais foram validados.

## M1 — Timeout agressivo no cliente gera falsos "erros"

**Prioridade: ALTA**

Em pelo menos dois pontos (enfileiramento de WhatsApp via Kanban — Fase 10/K2/G2 —
e "Guardar todos no CRM" da Pesquisa — J6), o backend responde `200 OK` mas o
cliente HTTP do agent-local desiste antes por um timeout curto (observado como
"Read timed out (read timeout=1)" nalguns casos) e reporta erro ou contagem de
progresso desatualizada ao utilizador, mesmo com a operação já concluída com
sucesso no servidor. Isto já levou a subestimar sucessos reais (ex.: "3 erros"
reportados quando 20/20 chamadas tinham retornado 200 OK). Rever/aumentar o
timeout do cliente HTTP nestes fluxos (`agent-local/app/crm_client.py`).

## M2 — Falta de guarda contra duplo-clique em "Enfileirar"

**Prioridade: ALTA**

Clicar "📤 Enfileirar" duas vezes seguidas no Kanban (assinante) cria jobs
duplicados (2 leads seleccionados → 4 jobs em vez de 2). Adicionar debounce ou
desabilitar o botão durante a chamada em `agent-local/app/ui/main_screen.py`.

## M3 — Falta de debounce/cancelamento de pedidos ao navegar entre painéis

**Prioridade: MÉDIA**

Navegação rápida entre painéis (Pesquisar → Assistente IA → Prospectar →
Histórico, em sequência) dispara múltiplos pedidos HTTP concorrentes sem
cancelar os anteriores, causando timeouts de rede reais
(`HTTPConnectionPool ... Read timed out`) e glitches visuais transitórios
(nomes de leads em branco, contadores cobertos, colunas ausentes por alguns
segundos, auto-corrigindo-se sozinhos). Cancelar/descartar requests obsoletos
ao trocar de painel em `main_screen.py`.

## M4 — Botão "Guardar todos no CRM" cortado no tamanho padrão da janela

**Prioridade: MÉDIA**

No tamanho de janela por omissão (793px de largura), o botão "💾 Guardar todos
no CRM" no header dos resultados de Pesquisa fica cortado/invisível — só
aparece depois de maximizar. É um problema de layout responsivo em
`agent-local/app/ui/main_screen.py`, não de lógica (o botão funciona quando
visível).

## M5 — Integração directa com resultados do agente Instagram/Maps

**Prioridade: MÉDIA**

Hoje o fluxo de importação exige exportar/importar ficheiro entre agentes.
Uma integração directa com os resultados dos agentes de Instagram/Maps
eliminaria esse passo manual no painel Assistente IA.

## M6 — Checkbox "Gerar copys com IA" não se activa sozinho quando o canal já vem pré-marcado

**Prioridade: BAIXA**

O fix da Fase 5.1 (`_ai_sync_generate_copys_with_channels`) só liga
automaticamente `_ai_generate_copys_var` quando o utilizador *marca* um canal
manualmente — não cobre o caso em que um canal (ex.: WhatsApp) já vem
pré-marcado por defeito no primeiro render do Passo 4 e o utilizador nunca
toca nele. Risco baixo, mas pode levar a processar sem gerar copy sem o
utilizador perceber.

## M7 — Gaps gramaticais na copy gerada quando o AI Profile está vazio

**Prioridade: BAIXA**

Com `brand_name`/`niche`/`offer_description` vazios, o texto gerado por
`generate-copy` (backend-crm) fica com gaps gramaticais tipo "Sou da ." ou
"Obrigado, , ." — não insere placeholders (correcto), mas também não omite
separadores (vírgulas/pontos) quando o campo está vazio. Condicionar a
inclusão de pontuação de fecho à presença do valor.

## M8 — Badge "WhatsApp Conectado/Desconectado" nunca implementado

**Prioridade: BAIXA**

O plano original da Fase 10 (automação do Kanban) previa um badge de estado
da sessão WhatsApp Web (verde "Conectado" / vermelho "Desconectado") na barra
de estado do Kanban. Só os badges "Agente Online/Offline" e "Pendentes: N"
foram construídos. Decidir se vale implementar o badge de conexão WA ou
remover definitivamente do escopo.

## M9 — Pré-preencher tom de voz a partir do AI Profile do utilizador

**Prioridade: BAIXA**

No painel Assistente IA (Passo 4 — opções de processamento), o campo "Tom de
voz" é um entry livre em vez de vir pré-preenchido a partir de
`GET /ai-profiles/me` (backend-core), como já acontece com nicho/oferta na
geração de copy.
