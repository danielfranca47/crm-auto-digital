# Limite de tamanho de upload também na camada de proxy/infra

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-upload-planilhas-sem-auth.md`. Naquela implementação, o limite de tamanho de
upload (`MAX_UPLOAD_BYTES`, 10MB) foi aplicado só na camada da aplicação
(`backend-crm/routes/uploads.py`, leitura em streaming com corte por chunk) — não
existe nenhum limite de tamanho de request configurado em nenhuma camada de
proxy/infra (nginx, Railway, ou equivalente) na frente do processo Python.

Comportamento desejado: um corpo de request muito grande é rejeitado antes mesmo
de chegar ao processo Python, reforçando a proteção contra DoS por upload — hoje
o processo Python ainda precisa receber e contar os bytes até `MAX_UPLOAD_BYTES`
antes de cortar.

---

## Área do sistema

Infra/deploy do `backend-crm` (Railway ou proxy equivalente) — fora do escopo de
código da aplicação.

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o
contexto acima como ponto de partida (levantar como a Railway/proxy actual está
configurada, se suporta `client_max_body_size` ou equivalente), responder as 3
perguntas do Passo 0, e só depois de aprovado seguir para a criação de branch +
worktree (Passo 1).
