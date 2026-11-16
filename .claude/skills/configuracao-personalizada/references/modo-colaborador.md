# Modo colaborador — sem Railway, sem `.env`, sem depender de ninguém

Vale quando `verificar_ambiente.py` diz `MODO=colaborador`. A pessoa tem o projeto (via GitHub, com
permissão de escrita), o Claude Code e a sua conta de teste de produção. **Nunca lhe pedir** o Railway,
um `.env`, chaves de API ou acesso ao servidor. O que faltar no PC (Python, pacotes, nome no git), o
Claude instala ou configura com a autorização da pessoa.

Scripts: `.claude/skills/diagnosticar-agente/scripts/` (abaixo `S`). O transporte é o `http`
(`prod_http.py`): rotas públicas com o login da conta de teste.

## 1. Acesso e PC (fase 0, uma vez por PC)

1. Corre `python $S/verificar_ambiente.py` e resolve cada ❌ pela ordem:
   - **Python em falta:** `winget install -e --id Python.Python.3.13` (com a autorização da pessoa);
     depois abrir um terminal novo.
   - **Pacotes em falta:** `python -m pip install requests pytest` e, para os testes do backend,
     `python -m pip install -r backend-crm/requirements.txt` (e do serviço que for mexer).
   - **Nome/email no git em falta:** `git config --global user.name "<nome>"` e
     `user.email "<email do GitHub>"`.
   - **Sem permissão de push:** a conta do GitHub da pessoa tem de ser colaboradora do repositório com
     escrita; o login do git faz-se na primeira publicação (janela do GitHub no browser).
   - **Projeto atrás:** atualizar o projeto (`git pull` na pasta) com a autorização da pessoa.
2. Pede **o email e a senha da conta de teste** (a de login no CRM). Explica numa frase que ficam só
   neste PC, num ficheiro fora do repositório, e servem para o Claude configurar e testar essa conta.
3. Grava `.claude/agentes/_acesso.json` = `{"email": "...", "senha": "..."}`. **Nunca repitas a senha**
   na conversa nem a escrevas noutro sítio.
4. Volta a correr `verificar_ambiente.py` até ficar tudo ✅.

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
| Commit em produção de cada serviço | `--prod-acao versao` |

Em `http`, o `simular.py` corre sempre no Playground de produção da conta de trabalho (não há bancada
local) e o cliente simulado é gerado pelo servidor. O `--prod` é desnecessário, mas não faz mal.

## 4. O que muda em cada fase

- **Fase 1:** a conta do cliente não se lê diretamente. Se o cliente já tiver conta e a pessoa tiver o
  login dela, pede-lhe que exporte o agente no ecrã do cliente (AI Profile → Exportar, sem treinamento)
  e te dê o ficheiro. É o snapshot do cliente. Sem isso, parte do preset do tipo de agente.
- **Fase 2:** as conversas de referência vêm do WhatsApp Web aberto no PC da pessoa
  (`extrair-conversas.md`, secção 2) ou de prints.
- **Fase 4–5:** a linha de base e as versões correm direto no Playground de produção da conta de
  trabalho. Uma bateria demora (≈ 30 s por turno): corre-a em segundo plano.
- **Fase 6:** corrigir código (abaixo).
- **Fase 7:** sem logs do servidor. Vê o lead e as mensagens da conta de trabalho pelas ações
  `mensagens` e `perfil`, e a marcação pelo resultado do turno.
- **Fase 8:** a verificação compara o ficheiro exportado da conta de trabalho com o exportado da conta
  do cliente depois da importação (a pessoa exporta e dá-te os dois). Diz campo a campo o que diverge.

## 5. Corrigir código (fase 6)

O mesmo fluxo de implementação do CLAUDE.md e de `codigo-sem-regressao.md` (ficheiro em
`docs/implementations/`, worktree, fases com commit, graduação, merge, push). O deploy é automático: o
push no `main` publica os serviços. Como não há bancada local, a prova de que nada piora para as outras
contas muda assim:

1. **Opt-in por omissão.** A correção fica atrás de um campo do AI Profile cujo valor por omissão é o
   comportamento de hoje, e liga-se só na conta de trabalho. Só um bug que é bug em qualquer conta (ex.:
   comparar horas como texto) pode valer para todos, e então tem de ter um teste automático que o
   prove.
2. **Testes antes e depois, no PC.** Corre `python -m pytest tests/ -q` em cada serviço tocado, primeiro
   no `main` (sem a correção) e depois na worktree. Sem `.env` há falhas que já existem antes (o core
   pede `SECRET_KEY`: corre-o com `SECRET_KEY=teste-local`). A regra é **0 falhas novas**: compara a
   lista de testes que falham nos dois casos.
3. **Teste novo** para o comportamento corrigido (com o campo ligado e desligado).
4. **"Sim" de quem corre a sessão** se `python scripts/fila/categorias_que_sobem.py` disser que sobe:
   uma frase simples (o que muda, para quem, resultado dos testes). Sem "sim", não se publica.
5. **Publicar e confirmar o deploy:** merge no `main`, push, e espera até `--prod-acao versao` mostrar o
   commit novo nos serviços tocados.
6. **Validar em produção:** liga o campo na conta de trabalho e corre a bateria do cliente. Corre também
   2 cenários numa conta de teste de **outro** tipo de agente, se a pessoa tiver acesso a uma (com o
   campo desligado: tem de se comportar como antes).
7. **Se algo piorar:** `git revert` do merge + push imediato, confirma com `versao`, e regista no
   README o que aconteceu. Nunca deixes uma regressão publicada à espera.

## 6. Pedido de correção (só o que exige um dono do sistema)

Vira pedido de correção apenas o que nenhum colaborador pode fazer: mudar segredos ou variáveis do
servidor, contratar ou configurar serviços pagos, apagar dados de clientes, mexer em contas de outras
pessoas.

```bash
python $S/simular.py <pasta> --prod-acao pedido '{"titulo": "<o que é preciso, em 1 linha>",
  "sintoma": "<o que o cliente final vê de errado ou o que fica bloqueado>",
  "evidencia": "<o que se mediu e porque precisa de um dono do sistema>",
  "cenarios_json": "<o cenarios.json dos cenários afetados, como texto>",
  "bancada": "<slug>"}'
```

- Sem dados pessoais de clientes finais: nomes e telefones anonimizados.
- `--prod-acao pedidos` mostra o estado (`novo`, `em_curso`, `feito`, `descartado`) e a nota.
- Regista o número do pedido no README da bancada, na secção "Itens de código registados".
