# Entregas — plans, implementations, prompts, relatório, retomada

## Registar em docs/plans

1. Procura duplicados: `grep -rn -i "<palavras-chave>" docs/plans/`. Se o item já existe, **atualiza-o**
   com a medição nova (data, conta anonimizada ou id, taxa) e revê a prioridade. Não cries um duplicado.
2. Se não existe, acrescenta-o ao ficheiro temático certo (lê `docs/plans/README.md`) com o próximo `Mn`:
   ```
   ## Mn — <o que corre mal, em linguagem simples>
   **Prioridade: ALTA|MÉDIA|BAIXA** (<porquê, em termos de dano ao cliente final>)
   **Medição (<data>, <conta: id prod>, <ambiente>):** <taxa, ex.: 6 de 15 marcações no dia errado>; exemplos anonimizados.
   **Estado atual:** <o que o código faz hoje — funções/ficheiros>; <o que já se tentou em configuração e não resolveu>.
   **O que construir:** <direção, não o plano>.
   ```
3. Atualiza a linha do ficheiro na tabela de `docs/plans/README.md`.

## Promover para docs/implementations

Promove quando o item causa dano ao cliente final (dia errado, cobrança errada, bot desligado,
promessa falsa) ou quando o utilizador o pede. O ficheiro é
`docs/implementations/<fix|feat>-<slug>.md`, no formato dos ficheiros "Aguardando Plan Mode"
existentes, com:
- `**Status:** Aguardando Plan Mode`, `**Autonomia:** manual` e `**Origem:**` (o item de plans e a
  data);
- Motivação, evidência medida e os cenários da bancada que expõem o problema;
- checks propostos, incluindo um **C1 de produção**: "`simular.py --bateria … --prod` com 0
  ocorrências".

Retira o item de plans, porque passa a viver em implementations.

## Quando várias correções tocam o mesmo código: investigar primeiro

Não entregues logo os prompts de implementação. Entrega um prompt de investigação:

```
Ler CLAUDE.md, docs/implementations/_guia-documentar-implementacao.md, docs/discovery/_guia-discovery.md
e .claude/agentes/<slug>/README.md (secção "<bateria>" — evidência; transcrições em tentativas/*<bateria>*).

Missão: INVESTIGAR (só leitura de código e de produção; nenhuma alteração de código) N problemas do agente
<Agente 0X — nome da página> da conta <id prod>, descobrir onde se sobrepõem, e deixar em docs/implementations/ pelo menos um
ficheiro por problema (Status: Aguardando Plan Mode, Autonomia: manual), os prompts de início e a ordem.

Problemas:
A) <sintoma> — <evidência: cenário, turno, o que foi gravado vs. pedido> — <hipótese de onde está a causa>
B) ...

Para cada problema: causa confirmada no código, ficheiros/funções tocados, opções com a recomendada, risco,
como validar (cenários da bancada; criar novos em cenarios.json se preciso).
Obrigatório: QUADRO DE SOBREPOSIÇÃO (ficheiro/função × correção), incluindo as worktrees em curso
(git worktree list) e os fixes recentes em main. Se duas soluções tocam o mesmo código, juntá-las num só
ficheiro ou fixar a ordem.
O que for só configuração não vira implementação: listar as alterações propostas para a conversa principal.

Entrega (linguagem simples): resumo por problema, ficheiros criados (commit local, sem push), ordem com o
porquê e o que corre em paralelo, um prompt de início por implementação (ficheiro a ler, dependências,
cenários para validar, e "toca instruções da IA → merge só com o meu sim").
```

## Prompt de implementação (um por ficheiro)

```
Lê CLAUDE.md, docs/implementations/_guia-documentar-implementacao.md e docs/implementations/<ficheiro>.md
(diagnóstico pronto — ponto de partida do Plan Mode). [Se tocar prompts: ler
docs/architecture/prompt-engineering-principles.md e docs/prompts_llms.md.]
Depende de: <outra implementação em main | nada>. Se ainda não estiver, avisa-me antes de começar.
Segue o Passo 0 (Plan Mode) e espera a minha aprovação.
Validar com a bancada .claude/agentes/<slug> (README.md): python .claude/skills/diagnosticar-agente/scripts/simular.py
.claude/agentes/<slug> --bateria <cenários> <rótulo>; para testar o código da worktree:
preparar_bancada.py <slug> --codigo-de <branch>. Depois do deploy, os mesmos com --prod.
[Atenção ao branch: commits só no main local (<hashes>) → criar a worktree a partir do main local.]
<Categoria que sobe (instruções da IA / envio real / base de dados / pagamento)>: merge só com o meu "sim".
```

## Commit

Faz um commit só com os ficheiros de `docs/` alterados (`git add` ficheiro a ficheiro), na pasta
principal, com uma mensagem `docs: …` e o corpo conforme o CLAUDE.md. Sem push. Indica os hashes no
relatório e nos prompts.

## Relatório ao utilizador (linguagem simples)

1. Uma frase com o estado: está em produção ou não, e se cumpre o roteiro.
2. **O que funciona**, como critérios com a taxa.
3. **Porque estava a correr mal**: 1 a 4 causas, cada uma com o que se mudou.
4. **O que fica a faltar**: o que precisa de código, com o risco em termos de dano ao cliente e onde
   ficou registado.
5. **Decisões tuas**, numeradas, cada uma com uma opção recomendada.
6. **Onde está tudo**: a pasta da bancada, a versão recomendada, como reverter e os commits.

## Retomada

Escreve-a no fim de cada sessão, no README (secções "Estado atual" e "Onde retomamos") e na resposta:

```
Retomar o diagnóstico do agente <nome> (conta <email>, prod user_id <n>, ai_profile <m>, Agente 0X — <nome da página>) com a skill
diagnosticar-agente. Bancada e histórico: .claude/agentes/<slug>/README.md.
Estado: em produção está a <cNN> (<o essencial>). <Fixes já validados>.
Desde então foram feitos noutras conversas: [preencher — <itens pendentes, um por linha>].
Retomar assim:
1. Confirmar que as correções novas estão ativas em produção e correr a bateria completa --prod
   (<cenários>). Medir: <critérios críticos>.
2. <próximo teste específico — ex.: ocupação real, pagamento de teste, follow-up>.
3. Teste de ponta a ponta no WhatsApp real (feito pelo utilizador, de um número que nunca falou com a conta).
4. Rever com o utilizador os itens de plans criados nesta missão e decidir quais ainda fazem falta: <lista>.
```

E diz explicitamente **"Onde retomamos"**: o passo e o porquê.
