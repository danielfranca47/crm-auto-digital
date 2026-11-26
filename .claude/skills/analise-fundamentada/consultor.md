# Consultar o agente consultor

O consultor é o projeto **Arquiteto de Soluções de IA** em `C:\projetos\modelos-agents` (skill própria e
revisor independente, o `revisor-critico`). Corre como outra sessão, que não conhece esta conversa.

## Briefing

Um ficheiro na pasta temporária da sessão, autossuficiente:
- pedido: decidir entre as opções, tentando primeiro refutar a recomendação com o revisor;
- passos 1 a 6 da análise, com taxas, `ficheiro:linha` e as passagens lidas das fontes;
- o utilizador está ausente: o que faltar fica registado como premissa;
- contas de clientes sem nome nem dados pessoais;
- formato da resposta: decisão por item, onde discorda, o que o faria mudar, e o que é escolha de negócio
  do utilizador.

## Correr

Em segundo plano (cada ronda demora vários minutos e gasta da assinatura), em Bash:

```bash
cd /c/projetos/modelos-agents && env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT claude -p --output-format json --permission-mode acceptEdits --allowedTools "Read,Glob,Grep,Write,WebSearch,WebFetch,Agent,Task,Skill" --max-budget-usd 6 < briefing.md > resposta.json
```

Ronda seguinte, para contrapor com um facto novo: o mesmo comando com `--resume <session_id>` (vem no
`resposta.json`). Ele guarda o caso em `briefings/` da pasta dele; essa pasta só recebe ficheiros novos.

## Sem consultor

Se a pasta não existir neste computador ou o comando falhar, passa a análise pela skill
`doubt-driven-development` e leva a recomendação ao utilizador, dizendo que o consultor não foi ouvido.
