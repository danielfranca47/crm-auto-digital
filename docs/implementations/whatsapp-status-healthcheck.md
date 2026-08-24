# Verificação periódica de status das conexões WhatsApp (health-check)

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode
**Prioridade:** Urgente — fazer logo após `alerta-desconexao-whatsapp.md`

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/alerta-desconexao-whatsapp.md`. Aquela implementação
resolve o caso em que a UazAPI consegue entregar o webhook `event="connection"`
para `backend-crm/routes/webhooks.py` — mas depende inteiramente desse webhook
chegar. Se a entrega falhar (instabilidade de rede, `CRM_PUBLIC_BASE_URL`
temporariamente fora do ar, etc.), o `WhatsappConnection.status`
(backend-core) volta a ficar "congelado" e ninguém é avisado — exatamente o
sintoma original reportado pelos usuários gabrielsmith.original@gmail.com e
aydebarbaraqod@gmail.com.

Este item cria uma rede de segurança independente do webhook: verificar
periodicamente, em segundo plano, se o status registrado bate com a realidade
da UazAPI.

---

## Problemas Identificados (estado anterior)

1. **Nenhum job/cron consulta `GET /instance/status` periodicamente** — o
   único caminho que atualiza `WhatsappConnection.status` a partir de uma
   consulta viva à UazAPI é `GET /whatsapp-instances/status`
   (`backend-core/app/api/whatsapp_instances.py`), chamado hoje só sob
   demanda (tela de Conexão com QR pendente, polling de 3s).
2. **Sem essa rede de segurança, o alerta por email (`alerta-desconexao-whatsapp.md`)
   depende 100% da entrega do webhook** — um único ponto de falha.

---

## Diagnóstico (a fazer em Plan Mode)

- Definir a frequência do health-check (ex.: a cada N minutos por conexão
  ativa) — balancear detecção rápida vs. carga extra na UazAPI (rate-limit).
- Decidir onde roda: novo job em `backend-executors` (mesmo padrão de
  `whatsapp.followup.tick`), ou um cron simples no `backend-core` (mais perto
  do dado, evita round-trip extra).
- Reaproveitar `uazapi_admin.get_status` + a mesma lógica de transição
  active→inactive + `render_whatsapp_disconnected_email` já criada em
  `alerta-desconexao-whatsapp.md` (evitar duplicar o disparo do email — talvez
  extrair a lógica de "detectar transição + notificar" para uma função
  compartilhada entre o endpoint do webhook e este health-check).
- Confirmar se dispara consulta para TODAS as conexões ou só as marcadas como
  "active" no banco (a maioria não deveria precisar de verificação se já sabe
  que está inativa).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
