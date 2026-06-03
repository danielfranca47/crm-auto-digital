# Guia de Testes Manuais — agent-local v2

Este guia explica, passo a passo, como executar os testes que não foram possíveis de automatizar.
Não é necessário conhecimento técnico avançado — segue o guia na ordem indicada.

---

## Antes de começar

### O que tens de ter a correr
Antes de abrir o app, certifica-te que o backend-core está ativo. Para verificar, abre o browser e acede a:
```
http://localhost:8001/
```
Deves ver `{"status":"ok"}`. Se não aparecer, inicia o backend-core primeiro:
```
cd backend-core
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
```

### Como abrir o app
```
cd agent-local
.venv\Scripts\python.exe main.py
```
Uma janela com o título **"Gerador de Leads — Digital Pro"** deve aparecer no ecrã.

---

## Cenário C4 — Reenvio de código com countdown

**O que testa:** o botão "Reenviar código" na tela de verificação de email desabilita-se por 60 segundos depois de clicado (para evitar spam de emails).

### Passos

1. Abre o app → aparece o ecrã **"O seu email"**
2. Escreve o teu email e clica **Continuar →**
   - Se já tens conta: passas direto para o ecrã de código
   - Se não tens: preenches o registo → passas para o ecrã de código
3. Estás agora no ecrã **"Verifique o seu email"** com o campo de 6 dígitos
4. **Não insiras o código ainda**
5. Clica no botão **"Reenviar código"** (azul claro, abaixo do botão principal)

### O que deves ver
- O botão muda para **"Reenviar (60s)"** e fica cinzento/desabilitado
- A cada segundo, o número decresce: 59, 58, 57...
- Ao chegar a 0, o botão volta a ficar azul com o texto **"Reenviar código"**
- Deves receber um segundo email com um novo código (o primeiro ainda funciona até expirar)

### O que confirmar
- [x] Botão desabilita imediatamente após o clique
- [x] Contagem decrescente visível (60s → 0s)
- [x] Botão volta ao normal após 60 segundos
- [x] Novo email recebido na caixa de entrada
- **Validado em:** 03/06/2026 — comportamento confirmado pelo utilizador

---

## Cenário B1 — Pesquisa como Assinante

**O que testa:** a pesquisa de leads usando a chave Google Maps da Digital Pro (sem precisar de chave própria).

**Pré-requisito:** a variável `GOOGLE_MAPS_API_KEY` tem de estar preenchida no ficheiro `backend-core/.env`.

### Passos

1. Abre o app e faz login com a tua conta de **assinante ativo**
   - Se aparecer o ecrã de onboarding, clica **Continuar →**
2. Estás no ecrã principal. Verifica que o cabeçalho mostra **"✓ Assinante"** (verde)
3. Preenche o formulário de pesquisa:
   - **Nicho:** `dentistas`
   - **Cidade:** `São Paulo, SP`
   - **Limite:** `10`
4. Clica **🔍 Pesquisar**

### O que deves ver
- A barra de progresso aparece imediatamente e avança
- Mensagens de progresso como "Conectando ao servidor...", "10 leads encontrados"
- Abaixo do formulário, surge uma tabela com os resultados (nome, telefone, website, avaliação)
- No rodapé do formulário aparece: **"Modo: Assinante — chave API incluída"**
- Botão **"📥 Exportar Excel"** aparece no cabeçalho da tabela

### O que confirmar
- [ ] Barra de progresso visível durante a pesquisa
- [ ] Resultados aparecem na tabela com os campos corretos
- [ ] Badge "Modo: Assinante — chave API incluída" visível
- [ ] Botão "📥 Exportar Excel" aparece

---

## Cenário B2 — Pesquisa com chave API própria (não-assinante)

**O que testa:** um utilizador sem assinatura que configurou a sua própria chave Google Maps consegue pesquisar.

**Pré-requisito:** precisas de uma chave API Google Maps válida.
> Como obter: https://console.cloud.google.com → Criar projeto → Ativar "Places API" → Criar credencial → Copiar chave `AIza...`

### Passos

1. Faz login com uma conta **sem assinatura ativa** (badge "Gratuito" no cabeçalho)
2. Clica no botão **⚙** (configurações) no canto superior direito
3. No campo **"Chave Google Maps API"**, cola a tua chave `AIza...`
4. Clica **Guardar**
5. Volta ao ecrã principal → preenche o formulário → clica **🔍 Pesquisar**

### O que deves ver
- No rodapé do formulário: **"Modo: Chave API própria configurada"**
- A pesquisa corre normalmente, resultados aparecem
- A chave fica guardada para próximas sessões

### O que confirmar
- [ ] Campo de chave API aparece nas configurações (só visível para não-assinantes)
- [ ] Após guardar, o modo muda para "Chave API própria configurada"
- [ ] Pesquisa retorna resultados

---

## Cenário B3 — Pesquisa em modo Selenium (sem chave)

**O que testa:** o fallback gratuito para utilizadores sem assinatura e sem chave própria — usa o Chrome para fazer scraping do Google Maps.

**Atenção:** este modo é mais lento (30-90 segundos) e menos fiável que os modos com API.

### Passos

1. Faz login com uma conta **sem assinatura** e **sem chave API configurada**
   - Se tiveres chave configurada, vai às ⚙ Configurações e apaga-a
2. O rodapé deve mostrar: **"Modo: Gratuito (Selenium) — configure a sua chave API em ⚙"**
3. Preenche o formulário:
   - **Nicho:** `pizzarias`
   - **Cidade:** `Lisboa`
   - **Limite:** `5`
4. Clica **🔍 Pesquisar**

### O que deves ver
- A barra de progresso aparece com a mensagem **"Iniciando Chrome (modo gratuito)"**
- Uma janela do Chrome **abre automaticamente** e navega para o Google Maps
- O Chrome faz a pesquisa e fecha automaticamente ao terminar
- Resultados aparecem na tabela (pode ter menos resultados que o limite pedido)
- O processo demora mais que os modos com API (normal)

### O que confirmar
- [x] Chrome abre com o Google Maps visível
- [x] Resultados aparecem na tabela (pelo menos 1 resultado)
- [x] Chrome fecha sozinho após terminar
- **Validado em:** 04/06/2026 — nicho="dentista", cidade="sao paulo", limite=10 → 10 leads retornados (Dental Company, IBEM Odontologia, etc.)

---

## Cenário B4 — Export Excel (parte do filedialog)

**O que testa:** o diálogo de guardar ficheiro aparece e o Excel é criado no local escolhido.

### Passos (executar após B1 ou B2 com resultados)

1. Após uma pesquisa com resultados, clica **"📥 Exportar Excel"**
2. Aparece a janela de **guardar ficheiro** do Windows
3. Escolhe uma pasta (ex: Ambiente de Trabalho) e confirma o nome do ficheiro (ex: `leads_20260603_120000.xlsx`)
4. Clica **Guardar**

### O que deves ver
- Aparece uma janela de confirmação: **"✅ Ficheiro guardado!"** com o nome do ficheiro
- Clica **OK**
- O ficheiro está na pasta escolhida
- Abre o ficheiro no Excel — deves ver:
  - Linha 1: texto da pesquisa (ex: `Pesquisa: dentistas em São Paulo, SP`)
  - Linha 2: contagem (ex: `Total: 10 leads`)
  - Linha 4: cabeçalhos em azul (Nome, Telefone, Website, Endereço, Avaliação, Nº Avaliações, Link Google Maps)
  - Linhas 5+: os dados dos leads

### O que confirmar
- [x] Janela de guardar ficheiro aparece
- [x] Popup de confirmação "Ficheiro guardado!" aparece após guardar
- [x] Ficheiro .xlsx abre corretamente no Excel com formatação correta
- **Validado em:** 04/06/2026 — ficheiro descarregado e dados dos leads visualizados no Excel

---

## Registo dos resultados

Depois de fazer os testes, abre o ficheiro:
```
docs/implementations/agent-local-v2-app-standalone.md
```

Para cada cenário validado, marca o check com `[x]` e adiciona uma linha:
```
- **Validado em:** DD/MM/AAAA — descrição breve do que observaste
```

Exemplo:
```markdown
- [x] Botão desabilita imediatamente após o clique
- **Validado em:** 04/06/2026 — countdown de 60s visível, novo email recebido
```
