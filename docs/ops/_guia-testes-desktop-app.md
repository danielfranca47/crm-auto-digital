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

## Preparação — manter o PC acordado durante a sessão

Testes de app desktop costumam ter esperas longas e sem interação directa do
utilizador (pesquisas Selenium a demorar minutos, diálogos a aguardar
resposta da IA, etc.). Se o Windows suspender ou o ecrã bloquear a meio, a
sessão de automação fica presa até alguém desbloquear manualmente.

Antes de começar, correr num terminal dedicado (deixar a correr durante toda
a sessão de testes, não fechar):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\keep_awake.ps1
```

- Não altera nenhuma definição global de energia — usa `SetThreadExecutionState`
  do Windows só enquanto o processo estiver vivo.
- Ao terminar os testes, fechar a janela (`Ctrl+C` ou fechar o terminal) devolve
  o comportamento normal de suspensão.
- Ver `scripts/keep_awake.ps1` para o código.

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

### ⚠️ Não repetir `open_application` às cegas — causa raiz confirmada

Se `computer-use` (`open_application` + `screenshot`) mostrar só o ambiente de
trabalho, sem qualquer rasto da janela alvo (nem sequer mascarada a preto),
**não voltar a chamar `open_application` várias vezes seguidas à espera que
"pegue".** Causa raiz confirmada nesta sessão: quando o app pedido no
`request_access`/`open_application` é o launcher genérico **"Python 3.13
(64-bit)"** (usado para apps sem atalho próprio, como o `agent-local`), cada
chamada repetida **não traz a janela existente para a frente** — em vez disso
abre uma instância nova de `python.exe -m pydoc -b` (um mini-servidor HTTP de
documentação, cada um numa porta aleatória e num separador de terminal
próprio). Ao fim de várias tentativas, isto:
- acumula vários separadores "Python 3.13 Module Docs (64-bit)" no Windows
  Terminal (um por chamada repetida) — nunca fica só numa tentativa, o padrão
  observado foi 6-7 acumulados numa única sessão de testes
- ocupa portas TCP aleatórias desnecessariamente (uma por instância)
- pode empurrar a janela real da app (`agent-local`) para **minimizada**,
  ficando invisível tanto no `computer-use` como à primeira vista

**Como diagnosticar antes de repetir a chamada:**
1. `mcp__Windows-MCP__Snapshot` — olhar para "Opened Windows": se a app alvo
   aparece como `Minimized` (tamanho 0×0), não é um problema de foco, é só
   estado de janela.
2. Se aparecerem vários `Python 3.13 Module Docs (64-bit)`, é sinal de que
   `open_application` já foi chamado a mais vezes do que devia.

**Como restaurar a janela certa (sem repetir `open_application`):**
1. `mcp__Windows-MCP__Click` no botão da app na barra de tarefas (id da lista
   de elementos interactivos) — restaura a janela minimizada para `Normal`
2. Voltar ao `computer-use` (`screenshot`) para confirmar e continuar a
   interagir normalmente

As duas ferramentas são complementares aqui: `Windows-MCP` só para
restaurar/inspeccionar estado de janela a alto nível; `computer-use` para toda
a interacção (cliques, scroll, digitação) dentro da app.

**Como limpar as instâncias `pydoc` acumuladas** (se isto já aconteceu):

```powershell
# Encontrar todos os processos pydoc -b órfãos
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*pydoc*' } |
  Select-Object ProcessId, CommandLine

# Terminar cada um (os separadores de terminal fecham sozinhos, as portas libertam-se sozinhas)
Stop-Process -Id <PID1>,<PID2>,... -Force
```

Não é preciso fechar os separadores de terminal manualmente nem libertar as
portas à parte — ambos acontecem automaticamente assim que o processo
`pydoc` morre.

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
