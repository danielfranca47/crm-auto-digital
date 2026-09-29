# Limpar instâncias mortas na UazAPI antes que o limite bloqueie novas conexões

**Branch:** (a criar)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`feat-whatsapp-connection-health-check.md`. Antes disso, estava em
`docs/plans/whatsapp-connection-melhorias-futuras.md` como M4, com prioridade
BAIXA "a confirmar se é urgente". Foi promovido a urgente porque o risco se
confirmou em produção.

**Incidente real (28/09/2026):** nenhum utilizador conseguia conectar o
WhatsApp. `POST /instance/init` na UazAPI devolvia 429 com o corpo
`{"error":"Maximum number of instances reached","info":"Cannot create more
than 6 instances (current: 6, limit: 3)","max_instances":3,"double_limit":6}`.
Isto confirma que o plano UazAPI tem **dois** limites: 3 conectadas ao mesmo
tempo e **6 registadas no total, mesmo desconectadas**. As 6 existentes
estavam todas `disconnected` e sem número (4 `crm-2-*`, 1 `collab-2-*`,
1 `spy-6-*`, todas de contas de teste). O nosso banco já não conhecia as
`crm-2-*`. O utilizador apagou-as à mão no painel da UazAPI para
desbloquear.

Com clientes reais, poucas quedas e reconexões voltam a encher o limite. O
bloqueio atinge **a conta inteira** (todos os clientes), não só quem caiu.

## Área do sistema

- Criação de instância nova sem apagar a antiga:
  `backend-crm/routes/whatsapp_connect.py::connect_whatsapp` (reinit em 5xx
  já chama `delete_core_whatsapp_instance` para a antiga, ver
  `docs/architecture/whatsapp-connection.md` → "Apagar instância / limpeza
  de fantasmas"). Confirmar que outros caminhos (ex.: token 401 → reinit,
  instância cujo registo local foi apagado) não deixam órfãs.
- `backend-core/app/jobs/whatsapp_connection_check_jobs.py`: marca como
  `disconnected` no banco, mas não apaga na UazAPI.
- `backend-core/app/services/uazapi_admin.py`: `GET /instance/all`
  (admintoken) lista tudo o que existe na UazAPI; ainda não tem wrapper.
- Painel admin: `frontend-admin/src/pages/AdminInstances.tsx` só vê o que
  está no nosso banco, não os fantasmas.

Ideias a avaliar no Plan Mode:
- Reconciliação periódica que compare `/instance/all` com o banco e apague
  instâncias órfãs ou mortas há mais de N dias.
- Alerta ao admin quando o total estiver perto do limite.
- Mensagem clara ao cliente (hoje o botão "Reconectar QR" simplesmente não
  faz nada visível quando dá 429).

Diagnóstico (Plan Mode) ainda não feito. O próximo passo é seguir o Passo 0
de `_guia-documentar-implementacao.md`.
