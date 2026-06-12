# Guia: Análise de Planos e Geração de Sprint

Este arquivo é um guia de instrução para o Claude. Leia-o quando o utilizador pedir para analisar
os planos pendentes e gerar um sprint de implementação.

---

## Quando este guia se aplica

O utilizador pediu algo como:
- "Analisa os plans e monta o sprint"
- "Faz análise de planejamento"
- "O que devemos implementar agora?"
- "Revisa os docs/plans e prioriza"

---

## Passo 1 — Inventário

Ler todos os arquivos em `docs/plans/`. Para cada arquivo, listar os itens/melhorias
identificados com:
- Nome do item (ex.: M1, seção, título)
- Prioridade declarada no arquivo (se existir)
- Arquivo de origem e seção

**Resultado esperado:** tabela consolidada com todos os itens pendentes de todos os arquivos.

---

## Passo 2 — Auditoria técnica

Para cada item inventariado, verificar o estado real no sistema:

1. Ler os docs de arquitectura relevantes (`docs/architecture/`) para entender o estado
   documentado
2. Buscar no código os arquivos e linhas citados no item — não confiar apenas na documentação
3. Classificar cada item:
   - ✅ **Já existe** — comportamento descrito já está implementado
   - 🟡 **Parcialmente existe** — estrutura existe mas incompleta
   - ❌ **Não existe** — precisa ser construído do zero

Citar arquivo e linha para cada classificação.

---

## Passo 3 — Correlação e dependências

Depois de auditar todos os itens, identificar:
- **Dependências diretas:** item B só pode ser implementado depois de item A
- **Sinergias:** itens que convém implementar juntos (tocam os mesmos arquivos)
- **Bloqueios externos:** itens que dependem de decisão do administrador (preço,
  estratégia, configuração externa que o Claude não tem acesso)

---

## Passo 4 — Diagnóstico e perguntas ao admin

Apresentar ao utilizador, **antes de gerar o sprint:**

1. **Tabela de auditoria** — todos os itens com status e observações
2. **Mapa de dependências** — o que bloqueia o quê
3. **Perguntas ao admin** — apenas quando encontrar uma decisão que só o fundador pode
   responder. Três categorias:

   ### a) Experiência desejada (utilizador final / plataforma)
   O que o utilizador deve conseguir fazer e como o sistema deve se comportar naquela situação.

   **FARIA:**
   - "Quando o lead atinge o limite de leads do plano, o sistema deve bloquear a criação
     de novos leads imediatamente ou apenas mostrar um aviso e permitir que continue?"
   - "Na página de boas-vindas para novos compradores, queres um checklist de próximos
     passos ou simplesmente um botão de acesso com uma frase de instrução?"
   - "Se o utilizador desactivar o bot manualmente, o follow-up automático deve parar
     também ou continuar a enviar?"

   **NÃO FARIA:**
   - "Devo usar redirect 301 ou 302 para a página /welcome?" → decisão técnica, o
     operacional decide
   - "O toast de sucesso deve aparecer antes ou depois do redirect?" → detalhe UI sem
     impacto no comportamento desejado

   ### b) Estratégia de negócio e produto
   Decisões comerciais, de preço, de acesso por plano, ou de timing de lançamento.

   **FARIA:**
   - "O Plano Scale vai à venda via Kiwify neste sprint ou apenas na Fase 2?"
   - "O playground com limite de 5 testes/mês deve aparecer bloqueado no plano Start
     (com CTA de upgrade visível) ou simplesmente não aparecer para esse plano?"
   - "O trial de 7 dias é activado automaticamente para qualquer registo ou apenas para
     leads seleccionados que fizeram call com o fundador?"

   **NÃO FARIA:**
   - "Devo criar o seed do crm_scale agora mesmo?" → a decisão já está registada nos
     plans — criar no seed é o que fazer, não é uma pergunta
   - "Devo usar Kiwify ou Stripe para cobrança de excedentes?" → já decidido nos plans

   ### c) Configurações externas
   Valores que o Claude não consegue verificar: painel de terceiro, link real, dado não
   acessível no código.

   **FARIA:**
   - "Qual é o nome exato do produto no painel Kiwify para o Plano Scale?"
   - "O redirect pós-compra no Kiwify está configurado para qual URL actualmente?"

   **NÃO FARIA:**
   - "Qual é o campo plan_code na tabela plans?" → verificável no código
   - "O email de boas-vindas tem logo da marca?" → verificável no template de email

   ---
   **Regra geral:** se a dúvida pode ser resolvida lendo o código, os docs/architecture/
   ou os próprios docs/plans/, não é uma pergunta para o admin.

**Aguardar as respostas antes de avançar para a priorização.**

---

## Passo 5 — Priorização

Com o diagnóstico completo e as respostas do admin, selecionar **2–3 itens** para o
sprint seguindo estes critérios em ordem de peso:

1. **Bloqueia receita ou utilizadores actuais** → prioridade máxima
2. **Alta prioridade declarada + baixo esforço** → quick wins
3. **Dependências já resolvidas** → itens cujos pré-requisitos já existem no sistema
4. **Sinergia de arquivos** → itens que tocam os mesmos arquivos (reduz risco de conflito)

Definir: 1 item principal (P1), 1–2 secundários (P2, P3).

Justificar brevemente **por que os restantes ficaram de fora** deste sprint.

---

## Passo 6 — Proposta e geração do arquivo

Apresentar a proposta de sprint ao utilizador (itens P1/P2/P3 com justificativa de ordem).
**Aguardar aprovação ou ajuste de escopo antes de criar o arquivo.**

Após aprovação, criar `docs/plans/plano-sprint-YYYY-MM-DD.md` seguindo o
template `_template-plano-semanal.md`.

---

## Divisão de responsabilidades: analítico vs. operacional

| | Claude Analítico | Claude Operacional |
|---|---|---|
| Responsabilidade | O QUÊ + PORQUÊ + ONDE (nível de serviço) | COMO (arquivos, padrões, abordagem, lógica) |
| Fonte | docs/plans/ + auditoria de alto nível + admin | Plan Mode com leitura precisa do código |
| Precisão esperada | Comportamento desejado, serviço envolvido | Arquivo exacto, linha, abordagem técnica |

O analítico **não deve** prescrever:
- Qual arquivo alterar ou qual linha tocar (pode estar errado após análise de muitos itens)
- Qual abordagem técnica seguir ("usar o fluxo X em vez do Y")
- Como estruturar o código, migration ou padrão interno
- Detalhes de convenção interna que só aparecem relendo o código com foco

Esses pontos são competência do Plan Mode do operacional, que investiga o código
com o foco de quem está a implementar apenas aquele item.

---

## Formato do prompt pronto (por item)

O prompt entrega O QUÊ e PORQUÊ com contexto suficiente para o Plan Mode do
operacional fazer a investigação precisa. Não prescreve o COMO.

Estrutura:
1. O pedido em linguagem natural (O QUÊ)
2. A motivação: por que agora, o que está em risco ou a ganhar (PORQUÊ)
3. Comportamento actual vs. comportamento desejado
4. Área do sistema envolvida (serviço/componente, sem prescrever arquivos ou abordagem)
5. Contexto de produto confirmado pelo admin (se houver)
6. A instrução para seguir o processo

Modelo:
```
Gostaria de implementar [título].
[Motivação — por que agora, o que está em risco ou a ganhar.]

Comportamento actual: [o que acontece hoje].
Comportamento desejado: [o que deve acontecer depois].

Área do sistema: [backend-core / backend-crm / frontend-crm / etc.].
[Contexto de produto confirmado pelo admin, se relevante.]

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

O operacional vai ao Plan Mode, lê o código com foco naquele item e decide COMO fazer.

---

## Ciclo de vida dos arquivos docs/plans/*

A limpeza dos `plans/*` é responsabilidade do **Claude de implementations**, executada
automaticamente no Passo 6b do processo de graduação — não é tarefa do analítico.

O sprint plan (`plano-sprint-YYYY-MM-DD.md`) tem duas seções que conduzem este processo:
- **Tracking de absorção** — o operacional marca cada item ✅ ao graduar a implementação
- **Manutenção** — lista exatamente quais `plans/*` deletar e sob que condição

Quando o último item do sprint for graduado e marcado ✅, o operacional executa a
limpeza do `plans/*` e do próprio sprint plan no mesmo commit de graduação.

O analítico não precisa acompanhar este processo — ele já está delegado ao operacional
via o sprint plan gerado.

---

## Sequência completa de trabalho

```
Utilizador: "Analisa os plans e monta o próximo sprint."

Claude:
  1. Lê este guia
  2. Lê todos os docs/plans/*.md → inventário
  3. Audita cada item no código + docs/architecture/
  4. Mapeia dependências e identifica perguntas

Claude apresenta:
  → Tabela de auditoria
  → Mapa de dependências
  → Perguntas ao admin (experiência desejada / produto / estratégia / externo)

Utilizador responde às perguntas

Claude:
  5. Prioriza P1/P2/P3 com justificativa
  6. Apresenta proposta de sprint e aguarda aprovação

Utilizador: "Aprovado" (ou ajusta escopo)

Claude:
  7. Cria docs/plans/plano-sprint-YYYY-MM-DD.md

--- Ciclo de implementations ---

Utilizador copia o prompt pronto do item P1 e inicia implementação:
  → Claude de implementations lê _guia-documentar-implementacao.md
  → Segue o processo normal (Plan Mode → código → commit → validação)
  → Na graduação: executa Passo 6b — marca P1 ✅ no tracking do sprint plan
  → Se todos os itens ✅: limpa plans/* e deleta sprint plan no mesmo commit

Repetir para P2, P3 — o operacional fecha o sprint automaticamente.
```

---

## Regras de escrita do arquivo de sprint

1. **Não duplicar o que está nos plans/*.** O prompt pronto já tem o contexto — a seção
   de contexto no sprint é um resumo executivo, não uma cópia.
2. **Sem histórico de deliberação.** O sprint mostra o resultado da análise, não o processo
   de como chegou lá.
3. **Perguntas respondidas ficam no arquivo.** As respostas do admin são registadas no
   sprint para referência do Claude de implementations.
4. **Itens excluídos têm justificativa em 1 frase.** Não deixar implícito o porquê de
   cada item ter ficado de fora.
