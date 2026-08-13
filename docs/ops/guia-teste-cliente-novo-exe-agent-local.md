# Guia — Testar o instalador do agent-local com um cliente novo (chamada guiada)

Script para usar numa chamada (vídeo/telefone) guiando um cliente **não-técnico**
passo a passo, instalando e testando o Gerador de Leads — Digital Pro no PC
dele pela primeira vez. Este guia é para **você** (não-técnico também) seguir
sozinho, sem precisar entender nada de código.

Serve dois propósitos:
1. Onboarding real de um cliente novo.
2. Confirma em hardware real três coisas que só foram testadas em máquina de
   dev até agora: o executável abre sem Python instalado, o fluxo
   Selenium/WhatsApp funciona, e o instalador cria atalhos e desinstala
   limpo — ver
   [`agent-local-app.md`](../architecture/agent-local-app.md#empacotamento-e-distribuição-exe).

Este arquivo **não é temporário** — fica para reutilizar em todo onboarding
futuro (ao contrário dos `guia-testes-*.md` de sessão única, que são
apagados depois de usados).

---

## O que você precisa saber antes de começar

**"Instalador"** = o arquivo que, quando o cliente dá dois cliques nele,
instala o programa no computador dele — igual a quando você baixa e instala
qualquer outro programa (Chrome, Zoom, etc.). Esse arquivo já está pronto,
gerado pelo Claude — você não precisa criar nada nem mexer em código.
Termos como "`.exe`", "`build.bat`" são coisas técnicas usadas só nos
bastidores (pelo Claude, ao gerar o arquivo) — você não precisa entender
nem usar isso, só precisa do arquivo final pronto (passo 1 abaixo).

---

## Antes da call — passo a passo (sozinho, sem o cliente)

### 1. Pega o arquivo mais recente pra enviar

Peça ao Claude, nesta conversa: **"gera o instalador mais recente do
agent-local"**. Quando terminar, o arquivo pronto para enviar estará em:

```
C:\crm-auto-digital\agent-local\installer_output\
```

Pra abrir essa pasta sem digitar nada: peça ao Claude **"abre a pasta do
instalador pra mim"** — ele abre o Explorador de Arquivos direto no lugar
certo. (Se preferir manualmente: abre o Explorador de Arquivos, cola o
caminho acima na barra de endereço lá em cima, e aperta Enter.)

O arquivo se chama **`DigitalPro-GeradorDeLeads-Setup.exe`** — é esse
arquivo, e só esse, que você vai enviar ao cliente no passo 2 abaixo.

### 2. Sobe o arquivo pra um link e manda pro cliente

Esse arquivo é grande (~37 MB) — **não dá pra mandar por anexo de email**
(o Gmail recusa anexos acima de 25 MB). Precisa subir pra um serviço de
armazenamento e mandar o link:

- **Google Drive** (se já usa): abre [drive.google.com](https://drive.google.com),
  arrasta o arquivo pra dentro, clica com o botão direito nele → "Compartilhar"
  → "Copiar link". Manda esse link pro cliente por WhatsApp ou email.
- **WeTransfer** (mais simples, não precisa de conta): abre
  [wetransfer.com](https://wetransfer.com), arrasta o arquivo, coloca o
  email do cliente, envia — ele recebe um link por email automaticamente.

### 3. Confirma se o PC do cliente tem o Google Chrome

Manda uma mensagem pro cliente antes da call perguntando se ele tem o
**Google Chrome** instalado no computador (não precisa ser o navegador
padrão, só precisa estar instalado). É esse programa que abre sozinho na
hora de mandar mensagem no WhatsApp durante o teste (passo 6 da call). Se
ele não tiver, é só pedir pra instalar antes — evita perder tempo da call
nisso.

### 4. Confirma o email que o cliente vai usar pra entrar

Não existe senha — o login é só com o **email que o cliente já usou pra
assinar**. Confirma com ele qual email foi, pra não perder tempo da call
tentando adivinhar. Na hora, ele recebe um código por email/SMS e digita
esse código — é só isso, sem senha nenhuma pra lembrar ou compartilhar.

---

## Durante a call — passo a passo com o cliente

### 1. Baixar e instalar

- Manda o link de download (Drive/WeTransfer) por WhatsApp ou email.
- Pede para clicar no link, baixar, e depois **duplo clique** no
  `DigitalPro-GeradorDeLeads-Setup.exe` baixado.

> *"Vai aparecer um arquivo de instalação chamado DigitalPro-GeradorDeLeads-Setup — pode dar dois cliques nele."*

### 2. Aviso do Windows ("Windows protegeu o computador")

**Quase certo de aparecer** — o instalador não tem assinatura digital
(certificado de editor reconhecido), então o Windows SmartScreen avisa por
padrão em qualquer programa novo baixado da internet. Não é um bug, é
esperado. Orientar:

1. Clicar em **"Mais informações"**
2. Clicar em **"Executar assim mesmo"**

> *"Isso é normal, o Windows avisa assim para qualquer programa novo que
> ainda não conhece — pode clicar em 'Mais informações' e depois em
> 'Executar assim mesmo'."*

Se o antivírus do PC bloquear ou colocar em quarentena: também é normal —
programas empacotados desta forma (PyInstaller/Inno Setup) às vezes são
sinalizados por engano por heurística de antivírus. Orientar a
permitir/restaurar o arquivo na ferramenta de antivírus.

**Não deve pedir senha de administrador** — o instalador foi configurado
para instalar só para o utilizador actual (`PrivilegesRequired=lowest`).
Se aparecer um pedido de senha admin mesmo assim, é sinal de algo errado —
anotar e não marcar o Cenário C6 como validado.

O assistente de instalação é em português — só acompanhar "Avançar" até o
fim. Na tela de tarefas adicionais, a opção **"Criar atalho na Área de
Trabalho"** já vem marcada por padrão (pode deixar como está). No fim,
oferece abrir o app automaticamente — pode deixar marcado.

> *"Agora é só clicar em Avançar até o fim — no final ele já abre o
> programa sozinho."*

**Confirmação visual rápida:** depois de instalado, o atalho (Área de
Trabalho e Menu Iniciar, dentro da pasta "Gerador de Leads — Digital Pro")
mostra um ícone quadrado azul com a marca Digital Pro — se o cliente
compartilhar a tela, é fácil confirmar que instalou certo só de bater o
olho no ícone.

### 3. Login (passwordless)

- Pede o email do cliente.
- Chega um código — orientar a digitar o código de 6 dígitos na tela.

### 4. Onboarding (primeira vez)

3 passos (assinante) ou 4 passos (gratuito) — só acompanhar o cliente
clicando em "Avançar"/"Continuar" até chegar na tela principal.

### 5. Testar Pesquisa (Google Maps)

- Pedir para preencher nicho + cidade (ex.: "dentistas", "São Paulo, SP")
  e clicar **Pesquisar**.
- Confirmar: aparecem resultados na lista.

### 6. Testar envio WhatsApp (Selenium)

- Pré-requisito: Chrome instalado (confirmado antes da call).
- Ao pedir o primeiro envio/prospecção, o **Chrome abre sozinho** e mostra o
  WhatsApp Web pedindo para escanear o QR code.
- Orientar o cliente a abrir o WhatsApp no celular dele e escanear o QR code
  na tela do Chrome.

> *"Agora vai abrir uma janela do Chrome com um QR code — é só abrir o
> WhatsApp no seu celular, ir em Aparelhos conectados e escanear esse
> código, igual quando você usa o WhatsApp Web normalmente."*

- Confirmar: a mensagem de teste chega no WhatsApp de destino.

### 7. Como abrir de novo depois da call

Não precisa reinstalar nem procurar o arquivo baixado de novo — o
instalador já deixou dois atalhos prontos:
- Ícone na **Área de Trabalho** ("Gerador de Leads — Digital Pro")
- Pasta **"Gerador de Leads — Digital Pro"** no Menu Iniciar (também tem o
  atalho para desinstalar, se precisar)

> *"Da próxima vez é só clicar no ícone azul que ficou na Área de
> Trabalho — não precisa baixar de novo."*

---

## Depois da call — o que registar

Se tudo correu bem (executável abriu sem Python, WhatsApp/Selenium
funcionou, instalador ficou limpo): nada a fazer — o empacotamento já está
graduado em
[`agent-local-app.md`](../architecture/agent-local-app.md#empacotamento-e-distribuição-exe),
esta call só confirma em hardware real o que já foi documentado.

Se algo falhar: abrir Plan Mode e criar um novo arquivo em
`docs/implementations/` para corrigir o problema, referenciando esta call e
a secção "Empacotamento e Distribuição" de `agent-local-app.md`.

---

## O que esperar (não são bugs)

| Situação | É esperado porquê |
|---|---|
| Aviso "Windows protegeu o computador" | Instalador sem assinatura digital — acontece com qualquer `.exe` novo baixado da internet, não só este |
| Antivírus marca falso positivo | Comum em builds PyInstaller/Inno Setup (binário empacotado/comprimido, heurística confunde com malware) |
| Primeira abertura demora alguns segundos a mais | Build `--onefile` extrai tudo para uma pasta temporária a cada execução |
| Envio WhatsApp não funciona | Confirmar primeiro se o PC tem Google Chrome instalado — é pré-requisito, não falha do empacotamento |
| Instalador pede pasta/idioma antes de instalar | Normal, é o assistente padrão do Windows — só seguir "Avançar" |
