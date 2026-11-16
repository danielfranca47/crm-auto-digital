# Modo colaborador — sem Railway, sem `.env`, sem código

Vale quando `verificar_ambiente.py` diz `MODO=colaborador`. A pessoa só tem o projeto (via GitHub), o
Claude Code e a sua conta de teste de produção. **Nunca lhe pedir** o Railway, um `.env`, chaves de API,
acesso ao servidor ou que instale ferramentas.

Scripts: `.claude/skills/diagnosticar-agente/scripts/` (abaixo `S`). O transporte é o `http`
(`prod_http.py`): rotas públicas com o login da conta de teste.

## 1. Acesso (fase 0, uma vez por PC)

1. Pede **o email e a senha da conta de teste** (a de login no CRM). Explica numa frase que ficam só
   neste PC, num ficheiro fora do git, e que servem para o Claude configurar e testar a conta dela.
2. Grava `.claude/agentes/_acesso.json` = `{"email": "...", "senha": "..."}`. **Nunca repitas a senha**
   na conversa nem a escrevas noutro sítio.
3. Volta a correr `verificar_ambiente.py` até aparecer ✅ no login e no plano.

Se o checklist disser "projeto atrás": pede à pessoa para escrever `git pull` no terminal do Claude
Code, ou corre-o tu com a autorização dela. Se faltar o plano: "pede ao Daniel o plano Interno para a
conta X".

## 2. Bancada (fase 4)

```bash
python $S/preparar_bancada.py <slug> --colaborador --agente "<nome>" --negocio "<o que a empresa faz>" \
    --idioma "<idioma>" --agente-tipo <01-sdr-alto-ticket|02-vendedor-autonomo|03-assistente-comercial>
```

Cria `.claude/agentes/<slug>/` com `bancada.json` em `"transporte": "http"` e a conta do login, e tira
logo o snapshot do perfil e da Base de Conhecimento. Se a conta ainda não tiver AI Profile, o primeiro
`--aplicar-prod` cria-o.

A trava recusa qualquer bancada cujo `prod_user_id` não seja o da conta do login. **Não a
contornes:** a conta do cliente só se toca pela importação no ecrã (`entrega-ao-cliente.md`).

## 3. Comandos

| Para quê | Comando |
|---|---|
| Uma conversa de teste (Playground de produção da conta de trabalho) | `python $S/simular.py <pasta> <cenário> <rótulo>` |
| Bateria + tabela | `python $S/simular.py <pasta> --bateria c1,c2 <rótulo>` / `--resumo <rótulo>` |
| Aplicar uma versão `cNN` (backup automático em `ambiente/`) | `python $S/simular.py <pasta> --aplicar-prod configs/cNN.json` |
| Perfil, Base de Conhecimento | `python $S/simular.py <pasta> --prod-acao perfil` / `conhecimento` |
| Treinamento | `--prod-acao treino '{"op":"listar"}'`, `'{"op":"adicionar","item":{"phase":"qualification","lead_message":"…","bot_message":"…","rating":"excelente"}}'`, `'{"op":"zerar"}'` |
| Mensagens de um lead (fase 7) | `--prod-acao mensagens '{"lead_id": N}'` |
| Sincronizar o Google da conta | `--prod-acao sync` |
| Limpar marcações de teste de leads | `--prod-acao limpar '{"lead_ids":[N]}'` |

Em `http`, o `simular.py` corre sempre no Playground de produção da conta de trabalho (não há bancada
local) e o cliente simulado é gerado pelo servidor. O `--prod` é desnecessário, mas não faz mal.

## 4. O que muda em cada fase

- **Fase 1:** a conta do cliente não se lê diretamente. Se o cliente já tiver conta e a pessoa tiver o
  login dela, pede-lhe que exporte o agente no ecrã do cliente (AI Profile → Exportar, sem treinamento)
  e te dê o ficheiro. É o snapshot do cliente. Sem isso, parte do preset do tipo de agente.
- **Fase 2:** as conversas de referência vêm do WhatsApp Web aberto no PC da pessoa
  (`extrair-conversas.md`, secção 2) ou de prints. O CRM de produção de outras contas não está
  acessível.
- **Fase 4–5:** a linha de base e as versões correm direto no Playground de produção da conta de
  trabalho. Uma bateria demora (≈ 30 s por turno): corre-a em segundo plano.
- **Fase 6:** pedido de correção (abaixo), sem código.
- **Fase 7:** sem logs do servidor. Vê o lead e as mensagens da conta de trabalho pelas ações
  `mensagens` e `perfil`, e a marcação pelo resultado do turno.
- **Fase 8:** a verificação compara o ficheiro exportado da conta de trabalho com o exportado da conta
  do cliente depois da importação (a pessoa exporta e dá-te os dois). Diz campo a campo o que diverge.

## 5. Pedido de correção (fase 6)

Quando a triagem prova que é código (ou 3 formulações falharam), envia o pedido:

```bash
python $S/simular.py <pasta> --prod-acao pedido '{"titulo": "<o que corre mal, em 1 linha>",
  "sintoma": "<o que o cliente final vê de errado e quantas vezes (taxa)>",
  "evidencia": "<cenário, turno, o que foi pedido vs. gravado/dito; o que já se tentou em configuração>",
  "cenarios_json": "<o cenarios.json dos cenários que expõem o problema, como texto>",
  "bancada": "<slug>"}'
```

- Sem dados pessoais de clientes finais: nomes e telefones anonimizados.
- Um pedido por problema. Até 20 abertos por conta.
- `--prod-acao pedidos` mostra o estado (`novo`, `em_curso`, `feito`, `descartado`) e a nota do Daniel.
- Regista o número do pedido no README da bancada, na secção "Itens de código registados".

O Daniel vê o pedido no frontend-admin (**Pedidos de correção**), copia o prompt pronto e trata-o pelo
fluxo de implementação. Quando o pedido passar a `feito`, a skill do colaborador volta a correr a
bateria e continua a missão.
