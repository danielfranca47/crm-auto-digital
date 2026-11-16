---
description: Audita no código/arquitetura se os itens de docs/plans/ selecionados já foram feitos, estão obsoletos, ou ainda precisam ser implementados — pede confirmação antes de qualquer mudança. Passo 2 do fluxo, depois de /statusplans
---

**Pré-requisito:** uma lista de itens a verificar. Se o usuário não indicou quais nesta
mensagem, use a "ordem sugerida de ataque" da última resposta de `/statusplans` nesta
conversa. Se não houver nenhuma, peça para rodar `/statusplans` primeiro ou informar os
itens manualmente. **Limite a no máximo 6 itens por vez** — se a lista tiver mais,
verifique só os 6 de maior prioridade e avise quais ficaram de fora.

Para cada item, siga o **Passo 2 (Auditoria técnica)** de
[`docs/plans/_guia-analise-planos.md`](../../docs/plans/_guia-analise-planos.md): ler os
`docs/architecture/` relevantes e buscar no código os arquivos/comportamentos citados —
não confiar apenas na descrição do plano, ela pode estar desatualizada.

Classifique cada item em uma destas categorias, **citando arquivo:linha ou doc de
arquitetura como evidência** (nunca sem evidência):

- ✅ **Já implementado** — o comportamento descrito já existe no sistema tal como o
  plano pedia
- 🟡 **Parcialmente implementado** — existe estrutura, mas incompleta ou com gap
  relevante
- ❌ **Não implementado** — precisa ser construído do zero
- 🗑️ **Obsoleto** — o problema/contexto que originou o item não existe mais (ex.: o
  item cita um provedor, fluxo ou decisão que foi substituído por outro — ex.: melhoria
  de checkout de um provedor de pagamento quando o checkout já migrou para outro).
  Justifique dizendo o que mudou e, se souber, desde quando (commit ou doc de
  arquitetura que documenta a mudança).

Monte uma tabela: **Item | Classificação | Evidência | Ação proposta**

Ação proposta por classificação:
- ✅ ou 🗑️ → remover o item do arquivo de plans (ou apagar o arquivo inteiro se ele
  ficar sem nenhum item pendente)
- 🟡 ou ❌ → manter como candidato para avançar para implementations no próximo comando

**Não altere nenhum arquivo nesta resposta.** Apresente a tabela e peça confirmação
explícita do usuário — em especial:
- cada 🗑️ (a leitura de obsolescência pode estar errada — confirme o motivo com o
  usuário antes de descartar o item)
- cada ✅ (pode ter sido implementado parcialmente, num contexto diferente do que o
  plano pedia)

Feche perguntando se pode prosseguir para `/statusplans-avancar` com essa confirmação,
ou se algum item precisa de reclassificação.
