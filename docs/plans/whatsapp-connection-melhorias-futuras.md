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

## M4 — Instâncias antigas/desconectadas acumulam-se na UazAPI sem limpeza

**Prioridade:** BAIXA (a confirmar se é urgente)

**Contexto:** descoberto em 30/08/2026, durante a correção do
`UAZAPI_BASE_URL` de produção (ver M3, acima). O fluxo de reconexão
(`backend-crm/routes/whatsapp_connect.py::connect_whatsapp`) — quando a
instância existente falha (5xx), cria automaticamente uma **instância nova**
via `init_core_whatsapp_instance` + `_generate_instance_id`, mas nunca apaga
a antiga na UazAPI. Confirmado que não existe, em todo o repositório,
nenhuma chamada a um endpoint de "apagar/logout de instância" da UazAPI.

O painel da UazAPI (agora visível, porque produção passou a apontar para o
servidor pago) já mostra 4 instâncias registadas para o mesmo número/conta
de teste, 3 delas `disconnected` — todas geradas pelo mesmo padrão de
auto-recuperação. Como **todos** os utilizadores em produção vão passar por
este mesmo fluxo de reconexão (efeito da correção do M3), é esperado que o
número de instâncias "fantasma" cresça rapidamente.

**Risco a confirmar:** o plano pago mostra "Limite de dispositivos (instâncias)
que podem ser conectados: 3" separado de "N total de instâncias" — não está
confirmado se esse limite de 3 é só sobre ligações *simultaneamente
conectadas*, ou se há também um teto sobre o total de instâncias
*registadas* (mesmo desconectadas) que, uma vez atingido, bloquearia novas
reconexões para toda a conta (não só um utilizador). Se for o segundo caso,
isto torna-se urgente rapidamente à medida que mais utilizadores reconectam.

**Ideia de correção (a avaliar em Plan Mode):** antes de criar uma instância
nova, tentar apagar/desligar a antiga na UazAPI (se existir endpoint para
isso), ou pelo menos confirmar junto do suporte da UazAPI se instâncias
`disconnected` contam para algum limite.

---

## M5 — Verificação periódica de status das conexões (health-check)

**Prioridade:** BAIXA — rebaixada de "Urgente" em 31/08/2026

**Contexto:** movido de `docs/implementations/whatsapp-status-healthcheck.md`
(nasceu como "Ajuste possível" na graduação de `alerta-desconexao-whatsapp.md`).
Motivação original: o alerta por email de desconexão depende inteiramente do
webhook `event="connection"` da UazAPI chegar — se a entrega falhar
(instabilidade de rede, `CRM_PUBLIC_BASE_URL` fora do ar, etc.), o status
volta a ficar "congelado" sem ninguém ser avisado. Este item propunha uma
rede de segurança independente: um job periódico a consultar
`GET /instance/status` diretamente, sem depender do webhook.

**Por que a prioridade baixou:** a causa raiz que motivava o "Urgente"
original (utilizadores a ficar sem saber que o WhatsApp caiu) já está
resolvida por outro caminho — ver M3, acima (produção apontava para o
servidor free da UazAPI, corrigido em 30/08/2026). Durante os testes reais
desta investigação, o caminho do webhook funcionou de forma consistente em
todas as reconexões — sem nenhuma falha de entrega observada. O risco que
este item protege continua real em teoria (rede pode falhar), mas deixou de
ser a explicação provável de um problema atual.

**Ainda vale a pena no futuro:** sim, como rede de segurança de baixo custo
— mas sem necessidade de avançar para Plan Mode agora. Reavaliar se algum
caso real de "status congelado sem aviso" voltar a acontecer apesar da
correção do M3.

**Diagnóstico já levantado (reaproveitar quando for avaliado):**
- Definir a frequência do health-check (ex.: a cada N minutos por conexão
  ativa) — balancear deteção rápida vs. carga extra na UazAPI.
- Decidir onde roda: novo job em `backend-executors` (mesmo padrão de
  `whatsapp.followup.tick`), ou um cron simples no `backend-core`.
- Reaproveitar `uazapi_admin.get_status` + a lógica de transição
  active→inactive + `render_whatsapp_disconnected_email` já criadas em
  `alerta-desconexao-whatsapp.md` — extrair para função partilhada entre o
  endpoint do webhook e este health-check, evitar duplicar o disparo do
  email.
- Confirmar se a consulta corre para todas as conexões ou só as marcadas
  como "active" no banco.
