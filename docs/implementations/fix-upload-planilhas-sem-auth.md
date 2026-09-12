# Exigir login para upload de planilhas de leads

**Status:** Aguardando Plan Mode
**Sprint:** `docs/plans/plano-sprint-2026-09-12.md` (item P3)
**Origem:** `docs/plans/seguranca-melhorias-futuras.md` (M2)

---

## Motivação

O endpoint que recebe arquivos Excel/CSV para importar leads aceita qualquer chamada
anónima, sem limite de tamanho nem de quantidade. Achado da auditoria de segurança de
15/07/2026, confirmado ainda sem correção na auditoria de 12/09/2026.

Comportamento actual: `POST /api/uploads` (`backend-crm/routes/uploads.py:46`) não tem
`Depends(require_crm_access)`. O arquivo é gravado em disco
(`data/uploads/ai/{uuid}.ext`) e processado com `pandas.read_excel`/`read_csv` sem
limite de tamanho nem cota por utilizador.

Comportamento desejado: só um utilizador autenticado do CRM consegue enviar arquivos
para importação, e os arquivos ficam associados/isolados por utilizador.

Risco concreto: superfície de negação de serviço num serviço exposto à internet — um
atacante pode mandar arquivos grandes ou em quantidade repetida até esgotar o disco do
servidor, ou explorar uma falha futura do parser do pandas, sem precisar de nenhuma
credencial.

---

## Área do sistema

`backend-crm` — importação de leads (`routes/uploads.py`).

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o
contexto acima como ponto de partida, responder as 3 perguntas do Passo 0, e só depois
de aprovado seguir para a criação de branch + worktree (Passo 1).
