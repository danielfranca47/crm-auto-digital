# Guia — Testar o agent-local.exe com um cliente novo (chamada guiada)

Script para usar numa chamada (vídeo/telefone) guiando um cliente **não-técnico**
passo a passo, testando o `agent-local.exe` no PC dele pela primeira vez.

Serve dois propósitos:
1. Onboarding real de um cliente novo.
2. Fecha os Cenários **C2** (executável abre sem Python instalado) e **C4**
   (fluxo Selenium/WhatsApp funciona) em
   [`docs/implementations/agent-local-v2-empacotamento-exe.md`](../implementations/agent-local-v2-empacotamento-exe.md) —
   testes que só fazem sentido numa máquina real de terceiro, não na máquina
   de desenvolvimento.

Este arquivo **não é temporário** — fica para reutilizar em todo onboarding
futuro (ao contrário dos `guia-testes-*.md` de sessão única, que são
apagados depois de usados).

---

## Antes da call — checklist rápido (sozinho, sem o cliente)

- [ ] `.exe` mais recente gerado: `agent-local/dist/agent-local.exe`
      (rodar `agent-local/build.bat` se não tiveres a certeza que está actualizado)
- [ ] Arquivo disponível num link de download — **não enviar por anexo de
      email**: o `.exe` tem ~36 MB e o Gmail bloqueia anexos acima de 25 MB.
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

### 1. Baixar e abrir o arquivo

- Manda o link de download (Drive/WeTransfer) por WhatsApp ou email.
- Pede para clicar no link, baixar, e depois **duplo clique** no
  `agent-local.exe` baixado.

> *"Vai aparecer um arquivo chamado agent-local — pode dar dois cliques nele."*

### 2. Aviso do Windows ("Windows protegeu o computador")

**Quase certo de aparecer** — o executável não tem assinatura digital
(certificado de editor reconhecido), então o Windows SmartScreen avisa por
padrão em qualquer programa novo baixado da internet. Não é um bug, é
esperado. Orientar:

1. Clicar em **"Mais informações"**
2. Clicar em **"Executar assim mesmo"**

> *"Isso é normal, o Windows avisa assim para qualquer programa novo que
> ainda não conhece — pode clicar em 'Mais informações' e depois em
> 'Executar assim mesmo'."*

Se o antivírus do PC bloquear ou colocar em quarentena: também é normal —
programas empacotados desta forma (PyInstaller) às vezes são sinalizados
por engano por heurística de antivírus. Orientar a permitir/restaurar o
arquivo na ferramenta de antivírus.

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

---

## Depois da call — o que registar

Transcrever o resultado directamente para os Cenários **C2** e **C4** em
[`docs/implementations/agent-local-v2-empacotamento-exe.md`](../implementations/agent-local-v2-empacotamento-exe.md)
(`[x]` + data + o que foi observado — ex.: "testado no PC do cliente X,
Windows 11, sem Python instalado; SmartScreen apareceu e foi resolvido
normalmente; QR code escaneado e mensagem chegou").

Se algo falhar: **não marcar `[x]`**, anotar o que aconteceu no arquivo de
implementação, e voltar a Plan Mode se for preciso corrigir alguma coisa no
código antes de repetir o teste.

---

## O que esperar (não são bugs)

| Situação | É esperado porquê |
|---|---|
| Aviso "Windows protegeu o computador" | Executável sem assinatura digital — acontece com qualquer `.exe` novo baixado da internet, não só este |
| Antivírus marca falso positivo | Comum em builds PyInstaller (binário empacotado/comprimido, heurística confunde com malware) |
| Primeira abertura demora alguns segundos a mais | Build `--onefile` extrai tudo para uma pasta temporária a cada execução |
| Envio WhatsApp não funciona | Confirmar primeiro se o PC tem Google Chrome instalado — é pré-requisito, não falha do empacotamento |
