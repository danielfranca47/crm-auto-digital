# Backup da base de dados de produção (os dois volumes do Railway)

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** pré-requisito levantado no Plan Mode de `feat-fila-automatica.md` (04/10/2026)

---

## Motivação

Os dados de produção vivem em dois ficheiros SQLite, cada um num volume do
Railway: `backend-core-volume` (51 MB) e `backend-crm-volume` (53 MB), ambos
montados em `/data`. Em 04/10/2026 não havia nenhuma rotina de backup — nem no
código dos backends, nem documentada em `docs/ops/`.

Hoje isso significa que uma alteração errada à estrutura da base de dados, um
ficheiro corrompido ou um volume apagado é perda de dados de clientes sem
volta.

Comportamento desejado: existe uma cópia recente das duas bases de dados
**fora** do volume onde vivem, feita sozinha todos os dias, e está escrito e
testado como se repõe uma cópia.

É também a condição que falta para o agente avaliador da fila automática poder
mandar trabalho para produção sem o utilizador (ver
[`docs/ops/fila-automatica.md`](../ops/fila-automatica.md), "Estado atual").

## Área do sistema

- Railway, ambiente `production`: os dois volumes e os serviços `backend-core`
  e `backend-crm`.
- Possivelmente um job agendado num dos backends, e um destino de
  armazenamento fora do Railway.
- `docs/ops/` — procedimento de reposição.

## Próximo passo

Este ficheiro ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. A decidir nesse passo:

- Backup nativo de volumes do Railway (o que o plano atual do Railway permite e
  quanto custa) ou cópia feita pela própria aplicação para fora do Railway.
- Com que frequência e quantas cópias se guardam.
- Como se testa uma reposição sem tocar em produção.

`Autonomia: manual` porque mexe em dados de clientes e em configuração do
Railway que pede confirmação do utilizador.
