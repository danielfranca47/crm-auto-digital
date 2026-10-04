# Fila automática — melhorias futuras

> Contexto: itens deixados de fora da graduação do contrato da fila automática
> (04/10/2026). As regras em vigor estão em
> [`docs/ops/fila-automatica.md`](../ops/fila-automatica.md); o programa que
> decide o que sobe sempre é `scripts/fila/categorias_que_sobem.py`.

## M1 — Pacotes novos sobem sempre

**Prioridade: ALTA**

Hoje uma branch que acrescente ou altere dependências (`requirements.txt`,
`package.json`, lockfiles) não sobe para o utilizador: nenhuma das cinco
categorias olha para esses ficheiros. Um pacote novo é código de terceiros a
correr dentro do servidor que tem as chaves do WhatsApp e do pagamento.

Exemplo: o item "exportar leads para Excel" instala uma biblioteca; o resto do
código não toca em nada sensível, por isso o avaliador poderia mandá-lo para
produção sozinho.

**A fazer:** sexta categoria em `scripts/fila/categorias_que_sobem.py`
(dependências), com os casos na bateria de `scripts/fila/tests/`, e a linha
correspondente na tabela "O que sobe sempre" de `docs/ops/fila-automatica.md` e
na secção "Fila automática" do `CLAUDE.md`.

**Por que é ALTA:** convém estar feito antes de ligar o poder de merge do
avaliador (`docs/implementations/feat-fila-poder-de-merge.md`).

## M2 — Reconhecer instruções da IA em ficheiros novos

**Prioridade: MÉDIA**

O script reconhece instruções da IA pelo nome do ficheiro (lista fixa) e por
linhas alteradas com `prompt… =`, "Você é" ou "You are". Um ficheiro novo com o
texto de instruções guardado noutro nome de variável e a começar de outra forma
não é reconhecido; o mesmo vale para uma linha alterada a meio de um texto
longo num ficheiro fora da lista.

Exemplo: o item "mensagem de reativação para leads parados" cria um ficheiro
novo com as instruções em `INSTRUCOES = """Escreve uma mensagem curta…"""`.

Os ficheiros que hoje têm instruções estão todos na lista — o risco só nasce
quando aparece um ficheiro novo.

**A fazer:** decidir entre alargar os padrões de linha (texto longo passado a
uma chamada ao modelo), olhar para o ficheiro inteiro quando ele chama o
modelo, ou manter a lista e obrigar a atualizá-la no mesmo commit que cria o
ficheiro.

## M3 — Um push só de documentação em `main` reinicia produção?

**Prioridade: ALTA**

Sim, pelo que o GitHub regista: em 04/10/2026 o push `db1e175`, que só tinha
`CLAUDE.md`, `docs/` e `scripts/`, criou um deploy no ambiente de produção do
Railway (`gh api repos/danielfranca47/crm-auto-digital/deployments`), tal como
os pushes com código. No repositório não há nenhuma configuração que o evite
(não existe `railway.json` nem "watch paths" versionados).

Porque importa: no modo sombra, cada veredito do avaliador acrescenta uma linha
ao placar de `docs/ops/fila-automatica.md` e faz push para `main`; as
graduações também. São vários reinícios por dia em horário de trabalho.

**A fazer** (precisa do Railway — não é trabalho para o turno da noite):
confirmar no Railway quais dos serviços reiniciam de facto num push desses, e
configurar em cada serviço os caminhos que disparam o deploy (cada backend só
com a sua pasta), com o "sim" do utilizador. Convém estar feito antes de ligar
o turno do dia (`docs/implementations/feat-fila-turno-do-dia-avaliador.md`).
