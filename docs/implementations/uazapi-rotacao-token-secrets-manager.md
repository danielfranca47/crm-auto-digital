# Rotação do UAZAPI_ADMIN_TOKEN + secrets manager

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`etapa-uazapi-migracao-plano-pago.md`. O `UAZAPI_ADMIN_TOKEN` é a credencial
mestre que controla todas as instâncias WhatsApp da conta paga na UazAPI.
Hoje vive em texto plano em `backend-core/.env` (local) e no equivalente em
produção, sem rotação periódica. Se vazar (commit acidental, log, máquina
comprometida), concede acesso administrativo total às instâncias até ser
revogado manualmente no painel da UazAPI.

Com clientes reais conectados, o custo de um vazamento deixa de ser teórico.

---

## Diagnóstico (a fazer em Plan Mode)

- Confirmar onde o token vive hoje em produção (Railway env vars) e se há
  outros lugares com cópia do valor.
- Avaliar opções de secrets manager compatíveis com a stack atual (Doppler,
  variável protegida no Railway, AWS Secrets Manager) — custo, esforço de
  integração, quem mais na equipe precisa de acesso.
- Definir processo de rotação (frequência, quem executa, como propagar sem
  downtime — trocar token não pode derrubar instâncias já conectadas).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
