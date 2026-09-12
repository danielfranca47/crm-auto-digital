# Plano de Sprint — Correções de Segurança e Confiabilidade

> Gerado em 12/09/2026 a partir da auditoria técnica de `/statusplans-verificar` sobre a
> lista sugerida por `/statusplans`. Todas as classificações abaixo foram confirmadas
> pelo utilizador nesta mesma sessão.

**Data de geração:** 12/09/2026
**Arquivos analisados:** `cancelamento-reagendamento-melhorias-futuras.md` ·
`kiwify-checkout-melhorias-pos-etapa-9-7.md` · `jobs-conclusao-database-locked-melhorias-futuras.md` ·
`followup-auto-trigger-melhorias-futuras.md` · `plano-sprint-2026-06-11.md` ·
`seguranca-melhorias-futuras.md`
**Status:** Aguardando início da implementação

---

## Diagnóstico — Todos os itens auditados

| # | Item | Arquivo de origem | Prioridade declarada | Status no sistema |
|---|---|---|---|---|
| — | Rotas de agenda sem autenticação | cancelamento-reagendamento (M4) | MÉDIA | ✅ Já implementado — `backend-crm/routes/appointments.py:326,431,454,533` já exigem `require_crm_access` |
| — | Plano `crm_scale` ausente / mapeamento Kiwify | kiwify-checkout (M1) | ALTA | 🗑️ Obsoleto — mapeamento Kiwify não existe mais; problema de fundo já rastreado em `scale-enterprise-roadmap.md`/`plano-sprint-2026-06-11.md` |
| — | Retries/alertas de falha de webhook | kiwify-checkout (M5) | MÉDIA | 🗑️ Obsoleto (duplicado) — já coberto por `confiabilidade-integracoes-externas-melhorias-futuras.md` (M2), que já cita `/webhooks/efi` |
| — | Fluxo de upgrade confuso (sem proration) | kiwify-checkout (M6) | BAIXA | 🗑️ Obsoleto — Efí já cancela automaticamente a sub antiga ao activar uma nova (`backend-core/app/api/subscriptions.py:339-343`) |
| — | Página `/welcome`, forçar troca de senha, email de confirmação de upgrade | kiwify-checkout (M2, M3, M4) | ALTA/ALTA/MÉDIA | ❌ Ainda válidos, migrados para `pos-checkout-efi-melhorias-futuras.md` (não seleccionados para este sprint) |
| P1 | Bug de concorrência "database is locked" (3 pontos) | jobs-conclusao-database-locked (M1) + followup-auto-trigger (M2) + cancelamento-reagendamento (M5) | ALTA (nos 3) | ❌ Confirmado ainda activo — `backend-crm/routes/executor.py:922-1015`, `backend-crm/services/followup_state.py:340,595`, `backend-crm/database.py:44,142` |
| — | Meta Cloud Client + webhook inbound | plano-sprint-2026-06-11 (P1) | ALTA | ❌ Zero progresso desde 11/06/2026 — sem `meta_cloud_client.py` em `backend-core/app/providers/` |
| P2 | OTP sem contador de tentativas | seguranca (M1) | ALTA | ❌ Confirmado — `backend-core/app/api/auth.py:351-372` sem rate limit |
| P3 | Upload de planilhas sem autenticação | seguranca (M2) | ALTA | ❌ Confirmado — `backend-crm/routes/uploads.py:46` sem `Depends(require_crm_access)` |

**Correlações identificadas:**
- P1 combina 3 itens de 3 arquivos diferentes porque tocam o mesmo padrão de bug (conexão
  SQLite aberta dentro de outra transacção) e os mesmos arquivos-base
  (`followup_state.py`, `executor.py`, `database.py`) — resolver em conjunto evita 3
  implementações separadas tocando praticamente o mesmo código.
- P2 e P3 são independentes entre si e de P1 — nenhuma sinergia de arquivos, mas ambos são
  quick wins de segurança da mesma auditoria de 15/07/2026.

---

## Perguntas respondidas pelo admin

Nenhuma pergunta de produto/negócio foi necessária para os 3 itens seleccionados — são
correcções técnicas e de segurança sem decisão comercial envolvida. O limite exacto de
tentativas do OTP e o tempo de bloqueio (P2) ficam a critério do Plan Mode da
implementação (detalhe técnico, não decisão de produto).

---

## Sprint — Itens selecionados

### P1 — Corrigir bug de concorrência "database is locked" na fila de jobs

**Origem:** `docs/plans/jobs-conclusao-database-locked-melhorias-futuras.md` (M1) ·
`docs/plans/followup-auto-trigger-melhorias-futuras.md` (M2) ·
`docs/plans/cancelamento-reagendamento-melhorias-futuras.md` (M5)
**Prioridade:** ALTA — bug activo em produção, afecta utilizadores actuais
**Esforço estimado:** médio (toca 3 pontos distintos, mesmo padrão de correcção)
**Dependências:** nenhuma

**Contexto:**
Três pontos diferentes da fila de jobs sofrem do mesmo padrão de bug de concorrência do
SQLite: uma função abre uma nova conexão e tenta escrever enquanto outra conexão ainda
segura um bloqueio de escrita numa transacção em andamento, ou usa um valor de status que
a tabela não aceita. Confirmado por leitura directa do código nesta auditoria (12/09/2026)
que os 3 casos continuam sem correcção — incluindo um caso já com risco confirmado de
enviar uma segunda resposta duplicada a um lead real.

**Entrega esperada:**
- Concluir um job com reenfileiramento automático não falha mais por bloqueio de banco
- Progredir um follow-up automático após o envio não falha mais pelo mesmo motivo
- Cancelar/pausar follow-up de um lead não falha mais silenciosamente por causa de um
  valor de status inválido

**Prompt para o processo de implementations:**
```
Gostaria de corrigir um bug de concorrência no banco de dados que afecta a fila de jobs
em três pontos: conclusão de job com reenfileiramento automático, progressão de
follow-up automático após um envio, e cancelamento de jobs pendentes de follow-up.

Motivação: já confirmado como bug activo em produção — pode atrasar a resposta ao lead,
causar uma segunda resposta duplicada enviada de verdade a um lead real, e fazer o
cancelar/pausar de follow-up falhar silenciosamente (o operador vê "sucesso" na tela mas
o job pendente continua agendado e dispara na mesma).

Comportamento actual: em alguns pontos, uma função abre uma nova conexão ao banco SQLite
e tenta escrever enquanto outra conexão ainda segura um bloqueio de escrita numa
transacção em andamento — a segunda falha imediatamente em vez de esperar. Noutro ponto,
uma actualização de status usa um valor que a tabela de jobs não aceita, e a operação
falha sem nenhum aviso visível ao operador.

Comportamento desejado: nenhuma das três situações falha mais — a conclusão/reenfileiramento
e a progressão de follow-up não colidem entre conexões, e o cancelamento de jobs
pendentes de follow-up usa um valor de status realmente aceite pela tabela.

Área do sistema: backend-crm (fila de jobs, follow-up automático).
Não há decisão de produto envolvida — é puramente correcção técnica de concorrência.

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

---

### P2 — Proteger o código de verificação (OTP) contra força bruta

**Origem:** `docs/plans/seguranca-melhorias-futuras.md` (M1)
**Prioridade:** ALTA — caminho directo para tomar conta de uma conta, sem mais nenhuma falha
**Esforço estimado:** baixo-médio
**Dependências:** nenhuma

**Contexto:**
O código de verificação (OTP) de 6 dígitos vale por 15 minutos e nada impede que alguém
tente todas as combinações possíveis nesse intervalo — sem nenhum contador de tentativas
falhas nem limite por IP/conta. Achado da auditoria de segurança de 15/07/2026, confirmado
ainda sem correcção nesta sessão (12/09/2026).

**Entrega esperada:**
- Depois de um número razoável de tentativas erradas, novas tentativas ficam bloqueadas
  (por conta e/ou por IP) pelo tempo que fizer sentido
- Um script não consegue mais testar todas as combinações dentro da janela de validade do
  código

**Prompt para o processo de implementations:**
```
Gostaria de proteger o login por código de verificação (OTP) contra força bruta.

Motivação: hoje o código de 6 dígitos vale por 15 minutos e nada impede que alguém tente
todas as combinações possíveis nesse intervalo — é um caminho directo para tomar conta de
qualquer conta de utilizador, sem precisar de mais nenhuma falha. Achado de auditoria de
segurança (15/07/2026), confirmado ainda sem correcção nesta sessão (12/09/2026).

Comportamento actual: o sistema valida o código contra o valor guardado sem contar
quantas vezes uma tentativa falhou, e sem nenhum limite por IP ou por conta.
Comportamento desejado: depois de um número razoável de tentativas erradas, o sistema
bloqueia novas tentativas (por conta e/ou por IP) pelo tempo que fizer sentido, evitando
que um script consiga testar todas as combinações dentro da janela de validade do código.

Área do sistema: backend-core (autenticação).

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

---

### P3 — Exigir login para upload de planilhas de leads

**Origem:** `docs/plans/seguranca-melhorias-futuras.md` (M2)
**Prioridade:** ALTA — superfície de negação de serviço num serviço exposto à internet
**Esforço estimado:** baixo
**Dependências:** nenhuma

**Contexto:**
O endpoint que recebe arquivos Excel/CSV para importar leads aceita qualquer chamada
anónima, sem limite de tamanho nem de quantidade. Achado da mesma auditoria de segurança
(15/07/2026), confirmado ainda sem correcção nesta sessão (12/09/2026).

**Entrega esperada:**
- Só um utilizador autenticado do CRM consegue enviar arquivos para importação
- Os arquivos ficam associados/isolados por utilizador

**Prompt para o processo de implementations:**
```
Gostaria de exigir autenticação no endpoint de upload de planilhas de leads.

Motivação: hoje qualquer pessoa na internet pode enviar arquivos para o servidor sem
nenhum login, sem limite de tamanho nem de quantidade — superfície de negação de serviço
num serviço exposto publicamente. Achado da auditoria de segurança (15/07/2026),
confirmado ainda sem correcção nesta sessão (12/09/2026).

Comportamento actual: o endpoint de upload aceita qualquer chamada, autenticada ou não, e
processa o arquivo sem limite de tamanho nem cota por utilizador.
Comportamento desejado: só um utilizador autenticado do CRM pode enviar arquivos, e os
arquivos ficam isolados/associados a esse utilizador.

Área do sistema: backend-crm (importação de leads).

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

---

## Tracking de absorção

> Atualizado pelo Claude de implementations durante o ciclo de vida do sprint.
> Cada item é marcado ✅ na graduação da sua implementação. Quando todos estiverem ✅,
> a limpeza de `docs/plans/*` e deste arquivo é feita no mesmo commit de graduação.

| # | Item | Arquivo de implementação | Status | Commit de graduação |
|---|---|---|---|---|
| P1 | Bug de concorrência "database is locked" | `docs/implementations/fix-concorrencia-database-locked-fila-jobs.md` | ⏳ Aguardando Plan Mode | — |
| P2 | OTP sem contador de tentativas | `docs/implementations/fix-otp-forca-bruta.md` | ⏳ Aguardando Plan Mode | — |
| P3 | Upload de planilhas sem autenticação | `docs/implementations/fix-upload-planilhas-sem-auth.md` | ⏳ Aguardando Plan Mode | — |

---

## Itens fora deste sprint

| Item | Motivo de exclusão |
|---|---|
| Meta Cloud Client + webhook inbound (`plano-sprint-2026-06-11.md`, P1) | Já tem sprint próprio em aberto, com bloqueio externo (credenciais/verificação Meta) e esforço muito maior que os itens deste sprint — trazê-lo para cá duplicaria o planeamento já existente |
| Página `/welcome`, forçar troca de senha, email de confirmação de upgrade (`pos-checkout-efi-melhorias-futuras.md`, M1-M3) | Continuam válidos mas sem urgência de segurança/produção comparável aos 3 itens seleccionados — candidatos ao próximo sprint |

---

## Manutenção dos arquivos docs/plans/*

> Executada automaticamente pelo Claude de implementations no Passo 6b da graduação,
> quando o Tracking de absorção estiver completo (todos ✅).

| Arquivo plans/* | Condição para deletar |
|---|---|
| `jobs-conclusao-database-locked-melhorias-futuras.md` | Apagar o arquivo inteiro quando P1 for absorvido (só tem o item M1) |
| `followup-auto-trigger-melhorias-futuras.md` | Remover apenas a seção M2 quando P1 for absorvido (M1, M3, M4 continuam pendentes) |
| `cancelamento-reagendamento-melhorias-futuras.md` | Remover apenas a seção M5 quando P1 for absorvido (M1, M2, M3 continuam pendentes) |
| `seguranca-melhorias-futuras.md` | Remover apenas as seções M1 e M2 quando P2 e P3 forem absorvidos (M3-M14 continuam pendentes) |
