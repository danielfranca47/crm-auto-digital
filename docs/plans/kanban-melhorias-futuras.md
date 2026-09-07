# Kanban — Melhorias Futuras

> Contexto: item deixado de fora da graduação do fix
> `fix-leadcard-obs-url-overflow.md` (07/09/2026).

## M1 — Overflow horizontal residual do Toaster (app-shell)

**Prioridade: BAIXA**

Durante os testes do fix de overflow do campo Obs, foi identificado que o
`<ol>` do Toaster (`fixed top-0 ... w-full`, componente de notificações
compartilhado por todo o app, não específico do Kanban) mede alguns pixels
(~13px observado) a mais que o viewport em certos momentos, mesmo sem
nenhum toast visível — causando um overflow horizontal mínimo e quase
imperceptível em telas estreitas.

Não investigado a fundo (fora do escopo do fix do campo Obs). Ao investigar,
começar por `frontend-crm/src/components/ui/toaster.tsx` (ou onde o
`<Toaster />`/`ToastViewport` estiver montado) e a hierarquia de containers
até `<body>`.
