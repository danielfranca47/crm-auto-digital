# Guia Pai — Testes WhatsApp Real e Playground

Guia de processo para criar e executar arquivos de teste de validação. Leia este
arquivo antes de criar qualquer arquivo em `docs/ops/` para testes.

Para o guia de implementação (criar features), ver
[`docs/implementations/_guia-documentar-implementacao.md`](../implementations/_guia-documentar-implementacao.md).

---

## Quando usar este guia

Use este guia quando:
- Um ou mais arquivos em `docs/implementations/` têm checks `[ ]` que exigem
  WhatsApp real ou Playground para serem validados
- O utilizador pede para "fazer os testes pendentes" ou "validar no WhatsApp"
- Uma feature foi implementada e precisa de validação end-to-end antes de graduar

---

## Passo 0 — Mapear os testes pendentes

Antes de criar o arquivo filho, ler **todos** os arquivos em `docs/implementations/`
(exceto os prefixados com `_`) e identificar checks de validação pendentes.

Para cada arquivo com checks `[ ]`:
1. Classificar o check por tipo:
   - **P** (Playground) — testável sem WhatsApp, só na UI/API
   - **W** (WhatsApp real) — exige enviar mensagem via celular real
   - **C** (WhatsApp real com configuração específica) — exige setup antes de testar
2. Identificar as dependências entre grupos (ex.: conexão WhatsApp deve funcionar antes de testar buffer)
3. Ordenar os grupos por dependência — testes mais básicos de infraestrutura primeiro

**Resultado esperado:** lista de grupos ordenados, cada um vinculado ao arquivo de
implementação de origem.

---

## Passo 1 — Criar o arquivo filho

**Nomenclatura:** `docs/ops/guia-testes-<slug>-<data>.md`

Exemplos:
- `guia-testes-etapa-9-1-2026-06-15.md`
- `guia-testes-audio-followup-2026-06-20.md`

**Estrutura do arquivo filho** (template a preencher):

```markdown
# Guia de Testes — <Descrição>

**Última atualização:** DD/MM/AAAA
**Objetivo:** validar no WhatsApp real/playground os testes pendentes de <lista de features>.

---

## ▶ Estado actual e próximos passos

**<Pendente / Em andamento / Concluído>**

### Contexto
- `user_id=N` (email do utilizador de teste)
- Agente: **NomeDoAgente** (`template_key`), empresa NomeDaEmpresa
- Número do bot: **+XXX XXX XXX XXX**
- Número do lead de teste: **+XXX XXX XXX XXX**
- Lead activo: **ID NNN**
- A API UazAPI é a tier gratuita: expira ~30min. **Sempre verificar conexão.**

---

## Como usar este guia

1. Execute os grupos em **ordem sequencial** — cada grupo pode depender do anterior.
2. Marque `[x]` em cada cenário assim que validado, com data e observação.
3. Se um cenário falhar → adicionar nova fase ao arquivo de implementação de origem
   (não criar arquivo novo), seguindo o padrão de diagnóstico do guia de implementação.
4. Após corrigir, revalidar o cenário antes de avançar.
5. Cenários com ⚠️ requerem participação do utilizador (enviar mensagem, escanear QR, etc.).

### Verificação obrigatória antes de pedir mensagem ao utilizador

Antes de solicitar qualquer envio do número do lead, verificar conexão WhatsApp:

```python
import sqlite3
conn = sqlite3.connect('backend-core/core.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT instance_id, status FROM whatsapp_connections WHERE user_id = N ORDER BY id DESC LIMIT 1")
print(dict(c.fetchone()))
conn.close()
```

- **CONECTADO / active** → prosseguir
- **DESCONECTADO** → avisar o utilizador para reconectar QR antes de continuar

> Motivo: UazAPI gratuita expira; reinícios do backend também podem quebrar a sessão.
> Falha silenciosa — o webhook simplesmente não recebe as mensagens.

---

## Pré-requisitos

- [ ] `backend-core` na porta 8001
- [ ] `backend-crm` na porta 8000
- [ ] `backend-executors` na porta 8002
- [ ] `frontend-crm` na porta 5173
- [ ] Variáveis de ambiente: `OPENAI_API_KEY`, `CRM_PUBLIC_BASE_URL`, `CRM_WEBHOOK_SECRET`, `UAZAPI_BASE_URL`
- [ ] Número WhatsApp de teste disponível

---

## Grupo N — <Nome da Feature>

**Referência:** [`docs/implementations/<arquivo>.md`](../implementations/<arquivo>.md)
**Dependências:** <Nenhuma / Grupo X (motivo)>
**Participação do utilizador:** ⚠️ <quais cenários exigem>

### Por que este grupo está aqui (posição na ordem)

<Justificativa: o que valida e por que deve ser feito nesta posição na sequência>

### Pré-requisito específico (se houver)

<Setup necessário antes de iniciar — configuração de AI Profile, reset de lead, etc.>

Script de reset do lead de teste (adaptar lead_id e tabelas conforme necessário):
```python
import sqlite3
conn = sqlite3.connect('backend-crm/database/crm.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for t in ['messages','lead_qualification_state','orion_conversations','notifications','outbound_events','prospection_logs']:
    cur.execute(f'DELETE FROM {t} WHERE lead_id=NNN')
cur.execute("UPDATE leads SET category='qualification', bot_disabled=0, bot_disabled_reason=NULL, phases_triggered=NULL, triggers_fired=NULL WHERE id=NNN")
conn.commit()
conn.close()
```

### Cenários

| # | Descrição | Exige participação | Validado |
|---|---|---|---|
| W1 | <descrição do cenário> | ⚠️ Lead envia mensagem | [ ] |
| W2 | <descrição do cenário> | ⚠️ Lead envia mensagem | [ ] |
| P1 | <descrição playground> | Não | [ ] |

**Condição de avanço:** W1 obrigatório. W2 e P1 confirmam comportamentos secundários.

---

## Resumo do estado de validação

| Grupo | Feature | Status |
|---|---|---|
| N — <Nome> | `<arquivo>.md` | ⏳ Pendente |

---

## Protocolo quando precisar de ajuda do utilizador

> "Para validar **[nome do cenário]**, preciso que envie uma mensagem para o número
> conectado no sistema. Quando estiver pronto, me avise."

Aguardar confirmação antes de marcar como validado.

---

## Protocolo de correção

Se um cenário falhar:
1. Identificar o arquivo de origem na coluna "Referência"
2. Adicionar nova fase ao final desse arquivo (não criar arquivo novo):
   ```markdown
   ## Fase N+1 — Diagnóstico + Correção (DD/MM/AAAA)
   ### Problema identificado
   <Causa raiz>
   ### Correção
   | Arquivo | Mudança |
   |---|---|
   | ... | ... |
   ```
3. Commitar a correcção
4. Revalidar o cenário antes de avançar
```

---

## Passo 2 — Durante os testes

### Como observar o resultado de cada mensagem

**DB (verificar estado do lead):**
```python
import sqlite3, json
conn = sqlite3.connect('backend-crm/database/crm.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('SELECT id, category, bot_disabled, triggers_fired, phases_triggered FROM leads WHERE id=NNN')
print(dict(c.fetchone()))
# Últimos jobs do lead:
c.execute("""SELECT id, type, status, json_extract(payload,'$.message_text') as msg, result
FROM jobs WHERE json_extract(payload,'$.lead_id')=NNN ORDER BY id DESC LIMIT 4""")
for r in c.fetchall():
    d = dict(r); res = json.loads(d['result'] or '{}') if d['result'] else {}
    print(f"job {d['id']} status={d['status']} msg={str(d['msg'])[:60]}")
    print(f"  system_actions={res.get('system_actions',[])} suppress={res.get('suppress_llm_response')}")
conn.close()
```

**WhatsApp (via MCP Chrome DevTools):**
- Usar `take_screenshot()` para ver a conversa
- Usar `type_text()` + Enter para enviar mensagem como lead (se WhatsApp Web estiver aberto)

**Logs do backend-crm (Bash):**
```bash
# Últimas linhas de log (se executando com output visível)
# Procurar por: event=, job_id=, inbound_event, bot_disabled, media_fallback
```

### Critério de validação mínima por tipo de cenário

| Tipo | O que verificar |
|---|---|
| **W — inbound processado** | `inbound_event` no DB + job completado + resposta chegou no WhatsApp |
| **W — bot desabilitado** | status `ignored/bot_disabled` no log + zero jobs criados |
| **W — audio transcrito** | job com `message_text="[Áudio]: ..."` + bot respondeu ao conteúdo |
| **W — media_fallback** | `media_fallback_msg` enviada via `send_whatsapp_direct` + estado correcto do lead |
| **W — trigger disparado** | `system_actions` ou `triggers_fired` actualizado no DB |
| **W — fire_once** | `triggers_fired` com 1 entry após 1º disparo; entry não aumenta no 2º |
| **P — playground** | bolha correta na UI + trace button mostra route correcto |

---

## Passo 3 — Após concluir todos os testes

Quando todos os grupos tiverem os cenários obrigatórios marcados `[x]`:

### 3.1 — Actualizar os arquivos de implementação de origem

Para cada grupo validado, abrir o arquivo `docs/implementations/` referenciado e:
- Marcar `[x]` nos checks correspondentes com data e observação
- Actualizar o `**Status:**` se todos os checks obrigatórios estiverem validados

### 3.2 — Deletar o arquivo filho de testes

```bash
git rm docs/ops/guia-testes-<slug>-<data>.md
```

O histórico fica preservado no git log. O arquivo de testes é um documento de
trabalho temporário — não é necessário mantê-lo após a validação estar registada
nos arquivos de implementação.

### 3.3 — Sugerir próximos passos ao utilizador

Após deletar, apresentar as opções disponíveis:

**Opção A — Graduar arquivo(s) completo(s):**
Se algum arquivo de implementação ficou com todos os checks validados, seguir
[`_processo-graduacao-implementacao.md`](../implementations/_processo-graduacao-implementacao.md)
para migrar o conteúdo relevante para `docs/architecture/` e deletar o arquivo.

> Dizer ao utilizador: "O arquivo `<nome>.md` está completo. Posso graduar agora —
> actualizar os docs de arquitectura e remover o arquivo."

**Opção B — Continuar arquivo próximo do fim:**
Se algum arquivo de implementação tem poucos checks `[ ]` restantes (1-2 fases),
sugerir continuar esse arquivo.

> Dizer ao utilizador: "O arquivo `<nome>.md` tem apenas N checks pendentes
> (`<lista dos checks>`). Quer continuar?"
> Seguir: [`_guia-documentar-implementacao.md`](../implementations/_guia-documentar-implementacao.md)
> (secção "Ciclo de vida do arquivo" — adicionar nova fase ou continuar da existente)

**Opção C — Iniciar nova implementação:**
Se não há arquivos próximos do fim, o utilizador escolhe uma nova feature.

> Dizer ao utilizador: "Todos os arquivos actuais estão completos ou em início de
> etapa. O que quer implementar a seguir?"
> Seguir: [`_guia-documentar-implementacao.md`](../implementations/_guia-documentar-implementacao.md)
> (Passo 0 — Plan Mode)

---

## Prefixos de cenário

| Prefixo | Significado |
|---|---|
| `P` | Playground — testável sem WhatsApp real |
| `W` | WhatsApp real — exige envio via celular |
| `C` | WhatsApp real com configuração específica necessária antes do teste |

---

## Convenções de estado nos cenários

| Marcação | Significado |
|---|---|
| `[ ]` | Pendente |
| `[x] DD/MM/AAAA` | Validado (com data e observação) |
| `[⏭️]` | Pulado intencionalmente (edge case ou requer infra indisponível) |

---

## Dicas de eficiência

- **Ordenar por dependência:** testes de conexão/infraestrutura antes de testes de feature
- **Resetar o lead antes de cada grupo** quando há risco de estado residual do grupo anterior
- **Um lead de teste dedicado por sessão:** evita conflitos com conversas reais
- **WhatsApp Web aberto no MCP:** permite enviar mensagens pelo Chrome DevTools sem precisar do telemóvel a cada mensagem
- **Verificar a instância antes de cada grupo**, não só no início — a UazAPI gratuita pode expirar a meio dos testes
- **Marcar o resultado imediatamente** após cada cenário — não esperar pelo final do grupo
- **Se um bug aparecer:** não parar os testes; registar o bug no arquivo de implementação de origem e continuar — o bug pode ser irrelevante para os grupos seguintes
