# Guia Pai — Testes de Apps Desktop (fora do browser)

Guia de processo para quando um cenário de validação exige controlar uma
aplicação desktop nativa (ex.: `agent-local`, uma janela CustomTkinter/Tkinter)
que **não é acessível via Chrome DevTools MCP** porque não corre num browser.

Para testes dentro do browser (CRM, playground, admin), continuar a usar o MCP
Chrome DevTools normalmente — este guia não se aplica a esses casos.

---

## Quando usar este guia

Use este guia quando:
- O cenário de validação envolve uma janela desktop nativa (Tkinter/CustomTkinter,
  Electron fora do browser, etc.) — ex.: `agent-local`
- Não é possível validar via `chrome-devtools` MCP porque a app não é uma página web
- O utilizador pede para "testar o agent-local" ou "testar [app desktop] no meu PC"

---

## Ferramenta a usar: `computer-use`, não `Windows-MCP`

Nesta sessão (08/07/2026) testámos as duas ferramentas de automação de desktop
disponíveis e há uma diferença prática relevante:

| Ferramenta | Resultado |
|---|---|
| `mcp__Windows-MCP__*` | ❌ **Não confiável neste ambiente.** `App` (modo `switch`) e cliques na barra de tarefas reportam sucesso, mas o foco volta sempre para a janela do próprio cliente Claude antes da próxima ação — o `Snapshot` seguinte continua a listar só os elementos da janela do Claude, nunca os da app alvo. Testado com múltiplas abordagens (switch, clique na barra de tarefas, clique no ícone "a pedir atenção") — nenhuma manteve o foco de forma consistente. |
| `mcp__computer-use__*` | ✅ **Funciona de forma fiável.** Depois de `request_access` à app e `open_application`, os `screenshot`/`left_click`/`type` interagem correctamente com a janela, mesmo sem "roubar" o foco do cliente Claude da mesma forma que o Windows-MCP tenta fazer. |

**Recomendação:** para qualquer teste de app desktop, ir directo a `computer-use`
— não perder tempo a tentar o Windows-MCP primeiro.

---

## Passo a passo

### 1. Conceder acesso à app

```
request_access({
  apps: ["<nome exacto no menu Iniciar>"],
  reason: "<explicação curta da tarefa>"
})
```

- O nome tem de corresponder ao que aparece no **menu Iniciar do Windows**, não ao
  título da janela nem ao caminho do executável.
- Para apps Python sem atalho próprio (caso do `agent-local`, que corre a partir
  de um `.venv` específico) — usar o launcher genérico **"Python 3.13 (64-bit)"**
  (ou a versão instalada equivalente). O `request_access` mapeia isto para o
  `bundleId` `c:\python313\python.exe`, mas mesmo assim a janela real da app
  (executada a partir de um `.venv` noutro caminho) fica acessível — a
  correspondência parece ser por nome de processo (`python.exe`), não pelo
  caminho exacto.
- Só pedir os apps que a tarefa precisa (evitar pedir "Google Chrome" aqui —
  browsers só são concedidos em modo `read`; para interagir com o browser usar
  sempre a extensão `claude-in-chrome`, nunca `computer-use`).

### 2. Trazer a app para primeiro plano

```
open_application({ app: "<mesmo nome do request_access>" })
```

### 3. Confirmar visualmente

```
screenshot()
```

Se a janela alvo não aparecer, esperar 2-3s (`wait`) e tirar novo screenshot —
apps desktop podem demorar a inicializar ou a repintar após navegação interna.

### 4. Interagir

Usar `left_click` / `type` / `zoom` com as coordenadas do último `screenshot`.
Preferir `computer_batch` quando a sequência de acções é previsível (evita
round-trips).

---

## Armadilhas conhecidas (encontradas na sessão de 08/07/2026)

1. **Diálogos nativos (Tkinter `Toplevel`) podem não aparecer no primeiro clique
   visível no screenshot seguinte.** Se um botão que deveria abrir um popup não
   mostrar nada, tentar clicar de novo antes de assumir falha — por vezes o
   diálogo só renderiza no screenshot seguinte.
2. **Janelas de apps não concedidas aparecem como rectângulos pretos sólidos**
   no screenshot (mascaradas). Não confundir isto com um bug visual da app —
   verificar primeiro se a janela em causa está na lista de `request_access`.
3. **Arrastar bordas para redimensionar não é fiável por coordenadas.** A área
   de "hit" da borda de uma janela Tkinter é demasiado fina para acertar de
   forma consistente via `left_click_drag`. Preferir testar `maximize`/`restore`
   (clique no botão do título) para validar layout responsivo — exercita o
   mesmo código de redimensionamento sem depender de precisão de pixel na borda.
4. **Botões no cabeçalho podem ficar cortados/invisíveis em janela estreita**
   (ex.: "Guardar todos no CRM" só apareceu depois de maximizar a janela).
   Antes de reportar um botão como "ausente", maximizar a janela e confirmar.
5. **Progresso reportado na UI pode atrasar-se significativamente face ao
   progresso real no backend** (ex.: diálogo de progresso mostrava "3/20"
   quando o backend já tinha processado 7 pedidos com sucesso). Não confiar só
   no texto do popup para julgar velocidade — confirmar no log do backend se a
   discrepância for grande.

---

## Registo dos resultados

Segue a mesma regra dos outros guias de teste: os resultados vão sempre para os
`docs/implementations/<arquivo>.md` de origem (checkbox `[x]` + data + evidência),
nunca ficam só neste guia. Este arquivo é processo, não resultado.
