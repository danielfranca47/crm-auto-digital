# Guia — Testar o instalador do agent-local com um cliente novo (chamada guiada)

Script para usar numa chamada (vídeo/telefone) guiando um cliente **não-técnico**
passo a passo, instalando e testando o Gerador de Leads — Digital Pro no PC
dele pela primeira vez, via instalador (`DigitalPro-GeradorDeLeads-Setup.exe`,
gerado por `agent-local/build-installer.bat`) — não mais o `.exe` avulso.

Serve dois propósitos:
1. Onboarding real de um cliente novo.
2. Fecha os Cenários **C2** (executável abre sem Python instalado), **C4**
   (fluxo Selenium/WhatsApp funciona) e **C6** (instalador cria atalhos e
   desinstala limpo, num PC de verdade — não só na máquina de dev) em
   [`docs/implementations/agent-local-v2-empacotamento-exe.md`](../implementations/agent-local-v2-empacotamento-exe.md).

Este arquivo **não é temporário** — fica para reutilizar em todo onboarding
futuro (ao contrário dos `guia-testes-*.md` de sessão única, que são
apagados depois de usados).

---

## Antes da call — checklist rápido (sozinho, sem o cliente)

- [ ] Instalador mais recente gerado:
      `agent-local/installer_output/DigitalPro-GeradorDeLeads-Setup.exe`
      (rodar `agent-local/build-installer.bat` se não tiveres a certeza que
      está actualizado — ele já chama o `build.bat` do `.exe` primeiro)
- [ ] Arquivo disponível num link de download — **não enviar por anexo de
      email**: o instalador tem ~37 MB e o Gmail bloqueia anexos acima de 25 MB.
      Usar Google Drive ou WeTransfer e mandar o link por WhatsApp/email.
- [ ] Confirmar com o cliente, antes da call, que o PC dele tem o
      **Google Chrome instalado** — é pré-requisito do envio WhatsApp
      (Selenium abre o Chrome de verdade); sem isso o Cenário C4 falha por
      motivo alheio ao empacotamento, não vale a pena descobrir isso já
      a meio da call.
- [ ] Ter a conta de teste/credenciais do cliente à mão — nunca pedir a
      senha por chat; a autenticação é passwordless (email + código), então
      nem se aplica pedir senha.

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

Transcrever o resultado directamente para os Cenários **C2**, **C4** e
**C6** em
[`docs/implementations/agent-local-v2-empacotamento-exe.md`](../implementations/agent-local-v2-empacotamento-exe.md)
(`[x]` + data + o que foi observado — ex.: "testado no PC do cliente X,
Windows 11, sem Python instalado; instalador não pediu senha admin, criou
atalho na Área de Trabalho; SmartScreen apareceu e foi resolvido
normalmente; QR code escaneado e mensagem chegou").

Se algo falhar: **não marcar `[x]`**, anotar o que aconteceu no arquivo de
implementação, e voltar a Plan Mode se for preciso corrigir alguma coisa no
código antes de repetir o teste.

---

## O que esperar (não são bugs)

| Situação | É esperado porquê |
|---|---|
| Aviso "Windows protegeu o computador" | Instalador sem assinatura digital — acontece com qualquer `.exe` novo baixado da internet, não só este |
| Antivírus marca falso positivo | Comum em builds PyInstaller/Inno Setup (binário empacotado/comprimido, heurística confunde com malware) |
| Primeira abertura demora alguns segundos a mais | Build `--onefile` extrai tudo para uma pasta temporária a cada execução |
| Envio WhatsApp não funciona | Confirmar primeiro se o PC tem Google Chrome instalado — é pré-requisito, não falha do empacotamento |
| Instalador pede pasta/idioma antes de instalar | Normal, é o assistente padrão do Windows — só seguir "Avançar" |
