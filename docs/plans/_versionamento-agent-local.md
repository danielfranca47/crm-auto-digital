# Versionamento do agent-local (vN)

> Guia permanente (prefixo `_`, nunca deletado). Aplica-se especificamente ao
> ciclo de vida do **agent-local** (app desktop de prospecção) — a única
> feature do repositório com numeração de versão própria (v2, v3, v4...),
> independente das etapas gerais do resto do sistema.

---

## O ciclo completo

```
Planeia vN            → docs/implementations/, Plan Mode, ciclo normal de
                         _guia-documentar-implementacao.md
Implementa vN          → fases do arquivo de implementação, uma a uma
Gradua vN               → _processo-graduacao-implementacao.md:
                         docs/architecture/agent-local-app.md passa a "vN"
                         Itens de "Ajustes Possíveis" (Passo 5b) viram M1..M(n-1)
                         em docs/plans/agent-local-melhorias-futuras-V(N+1).md,
                         rotulado "Versão-alvo: v(N+1)"
                         O último M-item desse arquivo é sempre
                         "Empacotamento v(N+1)" (ver regra abaixo)
Empacota vN             → o M-item "Empacotamento vN" já não precisa esperar
                         o resto do plano de v(N+1) — sai de
                         docs/plans/agent-local-melhorias-futuras-VN.md e
                         vira docs/implementations/agent-local-vN-empacotamento-exe.md
                         (Status: Aguardando Plan Mode), porque o único
                         pré-requisito (vN com todos os cenários validados)
                         já está cumprido
Planeia v(N+1)          → rascunho inicial a partir dos M-items restantes de
                         agent-local-melhorias-futuras-V(N+1).md
Complementa v(N+1)      → feedback de clientes reais que usaram o .exe
                         empacotado de vN é incorporado ao plano de v(N+1)
Implementa v(N+1)       → repete o ciclo
```

---

## Regra 1 — Empacotamento é sempre a última fase de uma versão

O empacotamento PyInstaller (`.exe`) de uma versão só faz sentido depois de
**todos** os cenários de teste dessa versão estarem validados — não há
motivo para gerar um binário distribuível de algo ainda instável.

Consequência prática:

- Todo arquivo `docs/plans/agent-local-melhorias-futuras-VN.md` **deve**
  terminar com um M-item `Empacotamento vN`, mesmo que o resto do conteúdo
  do arquivo ainda esteja incompleto ou em aberto. Isto evita esquecer o
  empacotamento no meio de outras prioridades.
- Assim que o arquivo de implementação da versão vN chegar a
  `**Status:** Todos os cenários validados` (e for graduado), o item
  "Empacotamento vN" já não é bloqueado por mais nada — pode ser promovido
  imediatamente para `docs/implementations/agent-local-vN-empacotamento-exe.md`
  (Status: Aguardando Plan Mode), **mesmo que o planeamento de v(N+1) ainda
  não tenha começado**. Não esperar o ciclo inteiro de v(N+1) para começar o
  empacotamento de vN.

## Regra 2 — Naming e nota de versão em cada arquivo

| Local | Nota obrigatória no topo |
|---|---|
| `docs/architecture/agent-local-app.md` | `**Versão documentada: vN.**` — a versão mais recente já graduada. Nunca "vN vs vN-1" no corpo — o doc é sempre um espelho da versão actual. |
| `docs/plans/agent-local-melhorias-futuras-V(N+1).md` | `**Versão-alvo: v(N+1).**` com link de volta ao doc de arquitectura vN. Nome do arquivo carrega o número da versão-alvo — quando o conteúdo for consumido e um novo arquivo nascer para v(N+2), o anterior é substituído (não acumular `-V3`, `-V4`, etc. simultaneamente vivos). |
| `docs/implementations/agent-local-vN-empacotamento-exe.md` | Referencia este guia + o doc de arquitectura da versão vN sendo empacotada. |

## Regra 3 — O que NÃO fazer

- Não implementar features de v(N+1) misturadas no mesmo arquivo de
  empacotamento de vN — são ciclos independentes que só coincidem
  temporariamente (empacotar vN pode acontecer em paralelo ao planeamento
  inicial de v(N+1), conforme o diagrama acima).
- Não pular o empacotamento de uma versão para "economizar" e ir direto
  para a próxima — cada versão empacotada é o que efectivamente chega ao
  utilizador final; sem isso, só quem tem o `.venv` local consegue usar a
  app.
- Não versionar nada além do agent-local com este esquema sem decisão
  explícita — o resto do sistema (backend-core/crm/executors, frontends)
  segue o processo normal de `docs/implementations/` + etapas, sem número de
  versão próprio.

---

## Estado actual (referência rápida — actualizar a cada graduação)

| Versão | Arquitectura | Empacotamento | Plano da próxima versão |
|---|---|---|---|
| v2 | [`agent-local-app.md`](../architecture/agent-local-app.md) — graduado | [`agent-local-v2-empacotamento-exe.md`](../implementations/agent-local-v2-empacotamento-exe.md) — Aguardando Plan Mode | [`agent-local-melhorias-futuras-V3.md`](agent-local-melhorias-futuras-V3.md) |
