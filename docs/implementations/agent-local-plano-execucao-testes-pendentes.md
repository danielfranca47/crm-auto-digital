# Plano de Execução — Testes Pendentes do agent-local (via automação de desktop/browser)

> **O que é este arquivo:** guia de execução — só a ordem cronológica dos cenários
> e o estado `[x]`/`[ ]` de cada um. **Não conter anotações, evidências ou achados
> aqui** — isso vive sempre nos arquivos de implementação de origem
> (`agent-local-v2-app-standalone.md` e `agentlocal-assistente-ia.md`), que são a
> fonte única de verdade. Este ficheiro existe só porque os dois documentos de
> origem intercalam cenários entre conta paga e gratuita — aqui ficam separados em
> dois blocos, na ordem em que serão executados, porque a **conta de teste vai
> mudar de plano a meio do processo** (assinante → gratuita).
>
> **Ao concluir um cenário:** marcar `[x]` aqui (só o estado) **e** escrever a
> evidência/data/achados no arquivo de origem correspondente. Este arquivo é
> descartável depois de tudo validado.

---

## Preparação (uma vez, antes do Bloco A)

- [x] `backend-core` a correr (porta 8001)
- [x] `backend-crm` a correr (porta 8000)
- [ ] `backend-executors` a correr (porta 8002), se necessário para polling/fila
- [x] `agent-local` aberto, login feito com a conta de teste
- [x] Conta de teste confirmada **assinante activo**
- [ ] Chrome com acesso concedido ao Claude (computer-use / claude-in-chrome)
- [ ] **WhatsApp Web:** sessão não autenticada nesta máquina — utilizador vai
      escanear o QR code manualmente no primeiro cenário que exigir envio real
- [x] Número de teste para WhatsApp confirmado: +55 47 99216-3692

---

## Bloco A — Conta Paga (assinante) — executar primeiro

> Não trocar o plano da conta antes de terminar este bloco inteiro.

### A.1 — Fase 8 (refresh token) — validação manual "ao vivo" ✅
*Fonte: `agent-local-v2-app-standalone.md`, nota "I1-live"*
- [x] Concluído — ver detalhe no ficheiro de origem

### A.2 — Fluxo principal: Pesquisar → Assistente IA → Prospectar (assinante) ✅
*Fonte: `agentlocal-assistente-ia.md`, Sessão 2*
- [x] A7 — Entrada via Pesquisar → Assistente IA
- [⏭️] A1 — Upload manual de ficheiro (pulado — mesmo motor de A2/A7)
- [x] A2 — Fallback: usar resultados de pesquisa dentro do Assistente IA
- [x] A3 — Mapeamento de colunas + preview
- [x] A4 — Processamento — criar cards sem copy
- [x] A5 + A8 — Processamento com geração de copy + prévia no Passo 5
- [x] A9 — Detalhe do lead com copy editável no Kanban CRM
- [x] A12 — Copy ciente do nicho/oferta do utilizador
- [x] A10 + A11 — Gerar copys para leads existentes sem copy
- [x] A6 (parcial) — Fluxo Pesquisar→AssistenteIA→Prospectar ponta a ponta
- [ ] A6 (item restante) — Seleccionar leads em massa → enfileirar WhatsApp → confirmar jobs (requer envio real, ver A.7/K2)

> ✅ Investigação da lentidão em A10+A11 concluída e corrigida (07/07/2026) — causa
> raiz era N+1 client-side, resolvido com JOIN agregado no backend. Ver nota em
> `agentlocal-assistente-ia.md` (secção A10+A11).

### A.3 — Fase 5 (prospecção WhatsApp individual, assinante) ✅
*Fonte: `agent-local-v2-app-standalone.md`, Fase 5. ⚠️ Envolve envio real de WhatsApp.*
- [x] F1 — Botão "📱" visível na tabela de resultados
- [x] F3 — Envio como assinante (com rastreio no CRM) — bug de duplicação de código de país encontrado e corrigido, ver detalhe no ficheiro de origem
- [x] F4 — Idempotência: lead já existe no CRM
- [x] F5 — Falha no WhatsApp (número inválido) — bug de deteção nunca disparava, encontrado e corrigido, ver detalhe no ficheiro de origem
- [x] G4 — Copy IA (assinante) *(validado fora de ordem, junto com F1)*

### A.4 — Fase 6 (lote, histórico, conta, copy IA)
*Fonte: `agent-local-v2-app-standalone.md`, Fase 6*
- [x] G1 — Prospecção em lote (UI validada ao vivo; loop de envio validado por leitura de código — ver nota de segurança no ficheiro de origem)
- [x] G2 — Lote assinante + CRM (validado indirectamente via K2 + bug de duplo-clique encontrado, ver ficheiro de origem)
- [x] G3 — Histórico (bug no "Exportar CSV" encontrado e corrigido, ver ficheiro de origem)
- [x] G5 — Gestão de conta

> Nota: K2 (Fase 10) foi validado antecipadamente durante o teste de G2 — ver A.7.

### A.5 — Fase 7 (CRM "Leads do Agente") ✅
*Fonte: `agent-local-v2-app-standalone.md`, Fase 7*
- [x] H1

### A.6 — Fase 9 (Kanban manual, assinante)
*Fonte: `agent-local-v2-app-standalone.md`, Fase 9*
- [ ] J1 — Kanban assinante com leads
- [ ] J2 — Kanban assinante sem leads
- [ ] J4 — Refresh
- [ ] J5 — Guardar no CRM (individual)
- [ ] J6 — Guardar todos no CRM
- [ ] J7 — Janela redimensionável
- [ ] J8 — Estabilidade ao navegar (race condition)

> Nota: J1 será parcialmente substituído pelos checks K1–K4 (botões "→
> Iniciar"/"→ Qualificar"/"📱" nos cards do Kanban foram removidos na Fase 10).

### A.7 — Fase 10 (automação do Kanban)
*Fonte: `agent-local-v2-app-standalone.md`, Fase 10*
- [ ] K1 — Barra de estado
- [x] K2 — Selecção e enfileiramento *(validado antecipadamente durante A.4/G2 — ver ficheiro de origem)*
- [ ] K3 — Refluxo automático por resultado
- [ ] K4 — Remoção dos botões manuais

### A.8 — Prompt de copy personalizado (assinante)
*Fonte: `agentlocal-assistente-ia.md`, A17b*
- [x] A17b completo (bug encontrado e corrigido — ver ficheiro de origem)

### A.9 — Regressões (confirmar assinante não foi afectado)
*Fonte: `agentlocal-assistente-ia.md`, secção "Regressões"*
- [ ] Repetir A14 com conta assinante
- [ ] Repetir A15 com conta assinante

---

## ⚠️ Ponto de mudança — trocar a assinatura da conta de teste para GRATUITA

Só avançar para o Bloco B depois de:
1. Todos os itens do Bloco A marcados `[x]` (ou explicitamente adiados com motivo)
2. Assinatura da conta de teste alterada para plano gratuito/inactivo
3. Confirmar no agent-local que o badge mudou para "Gratuito" após reiniciar sessão

---

## Bloco B — Conta Gratuita — executar depois da troca de plano

### B.1 — Fase 5 (prospecção individual, não-assinante)
*Fonte: `agent-local-v2-app-standalone.md`, Fase 5. ⚠️ Envolve envio real de WhatsApp.*
- [ ] F2 — Envio como não-assinante (sem rastreio)

### B.2 — Fase 9 (Kanban não-assinante)
*Fonte: `agent-local-v2-app-standalone.md`, Fase 9*
- [ ] J3 — Kanban não-assinante

### B.3 — Assistente IA / Kanban local — itens restantes da Sessão 1
*Fonte: `agentlocal-assistente-ia.md`, Sessão 1 (A14–A17)*
- [ ] A14 — Kanban local (itens restantes)
- [ ] Fase 14 — Editar dados do lead (itens restantes)
- [ ] A15 — Geração de copies em lote a partir da Pesquisa (itens restantes)
- [ ] A16 — Eliminar leads do Kanban local (itens restantes)
- [ ] A17 — Personalizar prompt de copy (itens restantes)
