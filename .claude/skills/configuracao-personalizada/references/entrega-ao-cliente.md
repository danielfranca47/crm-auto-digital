# Entrega ao cliente — exportar, importar e verificar

O agente foi montado e validado na **conta de trabalho**. A entrega passa-o para a **conta do
cliente** sem perder nada do que foi provado.

## O que a exportação leva e o que não leva

Ecrã do AI Profile → **Exportar / Importar** (`frontend-crm/src/components/agente/AgentExportImportPanel.tsx`):

| Vai no ficheiro | Não vai (é preciso refazer na conta do cliente) |
|---|---|
| AI Profile: tipo de agente, instruções, Fluxo de Venda, horários, follow-up, margem, handoff, … | **Base de Conhecimento** (itens, tabela de preços, informações do negócio, mídias) |
| **Com treinamento:** todos os exemplos da secção Treinamento da conta de trabalho | ligação de **WhatsApp** (QR na conta do cliente) |
| | **Google Calendar** (ligar com o Google do cliente e confirmar a permissão do calendário) |
| | número do operador (`operator_whatsapp`), webhook e segredo de pagamento |

Confirma esta tabela no código antes de cada entrega: a lista `EXPORT_EXCLUDE` e o payload em
`handleExport`. Se mudou, segue o código e corrige este ficheiro.

## Com ou sem treinamento: qual recomendar

| Situação | Recomenda |
|---|---|
| A bateria validada correu **com** exemplos de treinamento criados para este cliente | **Com treinamento**: o que foi provado inclui esses exemplos; sem eles, o agente entregue não é o mesmo |
| Não se criou nenhum exemplo nesta missão | **Sem treinamento** |
| A conta de trabalho tem exemplos que não são deste cliente (sobras) | primeiro **limpar** e voltar a correr a bateria; só depois exportar **com treinamento** |
| O cliente já tem na conta dele exemplos próprios que quer manter | **Com treinamento**, e na importação escolher "manter" os existentes. Avisa que, em "substituir", os dele são apagados |

Diz sempre o porquê numa frase. Por exemplo: "Com treinamento, porque os 4 exemplos de tom que
fizemos fazem parte do que passou nos testes."

## Passos (feitos pela pessoa, no ecrã)

A transferência faz-se sempre pelo ecrã, que é o caminho oficial. O Claude dá os passos já preenchidos
e verifica no fim.
1. Na conta de trabalho: AI Profile → Exportar → o modo recomendado → guardar o `.json`.
2. Criar a conta do cliente, se ainda não existir (registo normal e plano).
3. Na conta do cliente: AI Profile → Importar → escolher o ficheiro → confirmar.
4. Na conta do cliente: refazer o que a exportação não leva (ver a tabela acima). O Claude entrega o
   conteúdo pronto a colar: os itens da Base de Conhecimento da conta de trabalho, um a um, e a lista
   de ligações a fazer.
5. Dar ao Claude o **email da conta do cliente** para a verificação.

A exportação não levar a Base de Conhecimento é uma falha de produto registada em
`docs/plans/diagnostico-agentes-melhorias-futuras.md` (M6). Quando for corrigida, atualiza esta
secção.

## Verificar (só leitura, com o email da conta do cliente)

1. **Perfil:** compara o AI Profile do cliente com o da conta de trabalho, campo a campo, sem os
   campos excluídos e os próprios de cada conta (ids, datas, tokens). Se houver diferenças, lista-as.
2. **Treinamento:** o mesmo número de exemplos por fase, se se exportou com treinamento.
3. **Base de Conhecimento:** os itens de que os critérios dependem (preços, serviços, morada) existem
   na conta do cliente.
4. **Ligações:** o WhatsApp está conectado; o Google tem a permissão do calendário; o operador está
   preenchido, se o handoff precisar.
5. **Comportamento:** 1 cenário `--prod` na conta do cliente (o que melhor cobre o objetivo). Está
   coberto pela autorização da missão (item 4) e cria um lead de teste nessa conta. Compara-o com a última bateria da conta de
   trabalho e limpa as marcações e os leads de teste.

Só depois disto se diz **"entregue"**.

## Depois da entrega

- Guarda o `.json` exportado em `.claude/agentes/<slug>/entrega/<data>.json`.
- No README da bancada, regista: a data, a conta do cliente (o id), o modo de exportação, o resultado
  da verificação e o que ficou para o cliente fazer.
- Deixa a conta de trabalho como está até ao início da próxima missão, que a limpa depois do
  backup (fase 1). Assim, se o cliente precisar de um ajuste, a versão validada continua à mão.
