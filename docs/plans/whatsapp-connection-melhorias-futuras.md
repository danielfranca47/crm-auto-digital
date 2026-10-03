# WhatsApp Connection — Melhorias Futuras

> Contexto: itens deixados de fora da graduação de
> `docs/implementations/pareamento-codigo-whatsapp-login.md` (código de
> pareamento como alternativa ao QR).

## M1 — Paridade de código de pareamento no Agente Espião

**Prioridade: MÉDIA**

`backend-crm/routes/spy_agent.py` (endpoint `/api/spy-agent/reconnect`, linhas
581-649) tem um fluxo de reconexão WhatsApp duplicado e independente do de
`routes/whatsapp_connect.py` — helpers próprios de extração de QR
(`_QR_KEYS`, `_find_in_payload`, `_infer_qr_kind`, `_normalize_status_raw`),
sem reaproveitar os de `whatsapp_connect.py`. Não suporta telefone/código de
pareamento hoje — só QR.

Se fizer sentido oferecer o mesmo método alternativo por lá (útil para quem
está a configurar o Agente Espião com um único aparelho), seria uma
implementação separada. Ver [`docs/architecture/whatsapp-connection.md`](../architecture/whatsapp-connection.md#outros-consumidores-fora-deste-fluxo)
para o estado actual dos dois fluxos.

---

## M2 — Reconexão remota via palavra-chave num número de suporte dedicado

**Prioridade:** a definir com o utilizador

**Contexto:** surgiu durante a investigação de `alerta-desconexao-whatsapp.md`
e `aviso-sessao-dupla-whatsapp.md`. Hipótese principal para a queda de sessão
após ~1h: conflito de sessão quando o mesmo número tem o WhatsApp Web/Desktop
aberto em paralelo à ligação do CRM (payload real capturado:
`"401: logged out from another device"`). O aviso preventivo
(`aviso-sessao-dupla-whatsapp.md`) e os testes em curso devem confirmar isto
primeiro.

**Ideia proposta pelo utilizador:** dedicar um número de WhatsApp só para
suporte, usado pela Lara para contactar o cliente afectado. Se o cliente
responder com uma palavra-chave (ex.: "restabelecer conexão"), o sistema
tentaria automaticamente: (1) reativar a ligação/login do agente do cliente
na UazAPI, e (2) forçar a saída do WhatsApp Web/Desktop da máquina local do
cliente, para eliminar o conflito de sessão sem o cliente precisar de o fazer
manualmente.

**Não avaliado ainda — precisa de diagnóstico próprio em Plan Mode antes de
implementar:**
- Viabilidade técnica do ponto (2): não há confirmação de que a
  UazAPI/Baileys expõe alguma operação que permita a uma sessão vinculada
  (a do agente) forçar o logout de *outro* aparelho vinculado da mesma conta
  (o WhatsApp Web/Desktop do cliente) — isto normalmente só é possível a
  partir do aparelho principal (o telemóvel), via "Aparelhos conectados →
  Sair". Precisa de confirmação na documentação da UazAPI/Baileys antes de
  prometer esta funcionalidade ao cliente.
- Se (2) não for viável, a funcionalidade reduz-se a "reconectar o agente
  automaticamente por palavra-chave" (sem resolver a causa raiz se o cliente
  continuar a usar o WhatsApp Web/Desktop em paralelo).
- Custo de manter um número dedicado de suporte activo (nova instância
  UazAPI, novo fluxo de mensagens fora do pipeline normal de leads).

---

## M3 — Aviso dinâmico de sessão dupla (detetar múltiplos aparelhos vinculados)

**Prioridade:** BAIXA — depende de confirmação prévia

**Contexto:** surgiu como "Ajuste possível" na graduação de
`aviso-sessao-dupla-whatsapp.md`, que adicionou um aviso estático (texto fixo)
na página de Conexão sobre o risco de usar WhatsApp Web/Desktop no mesmo
número. Esse aviso é preventivo — ainda não há confirmação de que conflito de
sessão é de facto a causa da queda após ~1h (ver M2, acima, para o contexto
completo da investigação).

**Ideia:** se o teste em curso confirmar a causa, avaliar detetar
programaticamente múltiplos aparelhos vinculados via UazAPI (se o payload de
status expuser essa informação) e mostrar um aviso mais específico/dinâmico
em vez do texto estático actual — ex.: "Detetámos N aparelhos vinculados
além do agente" em vez de um aviso genérico sempre visível.

**Bloqueado por:** resultado do teste real (fechar WhatsApp Web/Desktop numa
conta afectada e confirmar se a queda pára de acontecer) — sem essa
confirmação, não faz sentido avançar para Plan Mode.

**Atualização (31/08/2026) — teste concluído, causa NÃO confirmada:** número
de teste (`+351 961649355`) ficou ligado ~90 minutos com o WhatsApp Web
aberto em paralelo (Opera) o tempo todo, incluindo uso ativo (envio de
ficheiro). Bot respondeu normalmente a mensagens de teste em pelo menos 3
verificações espaçadas ao longo desse período, sem nenhum evento de
desconexão nos logs. Conflito de sessão **não é** a causa principal do
problema original.

A causa principal encontrada foi outra: produção estava a apontar para o
servidor free da UazAPI em vez do pago (`UAZAPI_BASE_URL`/`UAZAPI_ADMIN_TOKEN`
no Railway nunca tinham sido atualizados após a migração documentada em
12/08/2026 — só o `.env` local tinha sido alterado). Corrigido diretamente
nas variáveis de ambiente do Railway (`backend-core` e `backend-crm`) em
30/08/2026 — essa é, com alta confiança, a explicação real do problema
relatado por todos os utilizadores.

**Consequência para M2 e M3:** ambos ficam **descartados/não-prioritários**
— nasceram de uma hipótese que o teste real não confirmou. O aviso estático
já publicado em produção (`ConexaoNumero.tsx`, ver
`docs/architecture/whatsapp-connection.md#deteção-de-queda-de-sessão`)
fica como está por agora (não é falso — usar vários aparelhos ainda é um
risco genérico documentado por terceiros — mas deixa de ser tratado como
a explicação provável para quedas futuras).

---

## M4 — `upsert_connection()` ainda grava status sem passar pela lógica de emails

**Prioridade: BAIXA**

**Contexto:** surgiu como "Ajuste possível" na graduação de
`feat-whatsapp-connection-health-check.md`. Todo status real vindo da
UazAPI passa por `apply_connection_status_change()`
(`backend-core/app/services/whatsapp_connections.py`), exceto
`upsert_connection()`/`upsert_connection_optional_token()`, chamados por
`/whatsapp-instances/init` e `/connect`. Eles gravam direto o status devolvido
pela UazAPI. Hoje isso só grava `connecting`/"Already connected", por isso o
risco é baixo. Um caso possível: uma conexão marcada como ativa, mas já morta
sem webhook, é sobrescrita com `connecting` quando o cliente clica "Reconectar
QR". A queda fica então sem email.

**Por que não foi feito junto:** passar esse caminho pela função central
dispararia um email de "desconectou" no exato momento em que o cliente clica
"Reconectar QR". Precisa de uma regra própria (ex.: não tratar `connecting`
como queda). Reavaliar só se aparecer algum email em falta ou trocado.

---

## M5 — Job de 6h não redescobre conexões que voltaram sozinhas

**Prioridade: BAIXA**

**Contexto:** surgiu como "Ajuste possível" na graduação de
`feat-whatsapp-connection-health-check.md`. `run_whatsapp_connection_check`
(`backend-core/app/jobs/whatsapp_connection_check_jobs.py`) só consulta
conexões com status normalizado `active`. Uma conexão marcada como
`disconnected` que volte a ficar viva na UazAPI sem webhook continua
"desligada" no banco até outro evento. Até hoje não causou problema real.
Se causar, basta alargar a query do job, com atenção ao custo de chamadas à
UazAPI e ao email de reconexão que isso dispararia.

---

## M6 — Validações ao vivo puladas na limpeza de instâncias da UazAPI

**Prioridade: BAIXA** — retomar só se surgir necessidade

**Contexto:** dois cenários de `fix-limpeza-instancias-uazapi-fantasmas.md`
foram pulados na graduação (03/10/2026) por decisão do utilizador. A
funcionalidade está descrita em
[`docs/architecture/whatsapp-connection.md`](../architecture/whatsapp-connection.md#capacidade-de-instâncias-na-uazapi).

- **Conexão viva sobrevive à limpeza:** nenhum WhatsApp estava conectado em
  produção nas limpezas já corridas, por isso não há prova ao vivo. Coberto
  por `backend-core/tests/test_uazapi_capacity.py` e pelo critério do código
  (só o status exato `disconnected` é apagável). Para validar: conectar um
  WhatsApp numa conta de teste, deixá-lo ligado durante a limpeza das 03:00
  UTC e conferir no log do `backend-core` que `event=uazapi_capacity` não o
  inclui em `deleted_orphans` e que o job das 06:00 UTC reporta `checked: 1,
  marked_dead: 0`.
- **Aviso na tela com o teto cheio:** o toast "Não foi possível gerar o QR
  code" de `ConexaoNumero.tsx` não foi visto ao vivo com a mensagem de limite
  atingido. O 503 do backend está coberto por teste. Para validar: encher o
  teto só com instâncias não apagáveis (conectadas / a ler QR) e provocar um
  init a partir do CRM.

---

## M7 — Alerta ativo ao admin quando a UazAPI estiver perto do teto de instâncias

**Prioridade: MÉDIA**

**Contexto:** surgiu como "Ajuste possível" na graduação de
`fix-limpeza-instancias-uazapi-fantasmas.md`. A ocupação só aparece no log
diário `event=uazapi_capacity` (`total_before`/`total_after`) do
`backend-core`, que ninguém lê por rotina. O reclaim por demanda evita o
bloqueio enquanto houver órfãs ou mortas para apagar; com o teto cheio só de
instâncias vivas, o cliente recebe 503 e a única saída é um plano UazAPI
maior. Um alerta (email ou painel admin) quando o total se aproximar do teto
daria essa informação com antecedência.

---

## M8 — Painel admin listar também as instâncias órfãs da UazAPI

**Prioridade: BAIXA**

**Contexto:** surgiu como "Ajuste possível" na graduação de
`fix-limpeza-instancias-uazapi-fantasmas.md`.
`frontend-admin/src/pages/AdminInstances.tsx` só mostra o que está no banco
do `backend-core`. Poderia cruzar com `uazapi_admin.list_instances()`
(`GET /instance/all`) para mostrar também as órfãs. A limpeza diária já as
apaga sozinha, por isso é só visibilidade.

---

## M9 — "Apagar" do painel admin remove a linha local mesmo quando a UazAPI falha

**Prioridade: BAIXA**

**Contexto:** surgiu como "Ajuste possível" na graduação de
`fix-limpeza-instancias-uazapi-fantasmas.md`. `DELETE /admin/instances/{id}`
(`backend-core`) apaga o registo local mesmo se o delete na UazAPI falhar, o
que deixa uma órfã do lado da UazAPI. A limpeza diária apanha-a em menos de
24h. Corrigir na origem seria só apagar a linha local depois de a UazAPI
confirmar (ou devolver 404).
