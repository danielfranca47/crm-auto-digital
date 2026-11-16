# Ler as conversas de referência e escrever o comportamento esperado

## 1. Procurar primeiro no CRM (mais barato)

As conversas feitas pelo agente estão no `crm.db` de produção. Lê-as só em leitura, via `railway ssh`
ao serviço `backend-crm`, com `sqlite3` aberto com `mode=ro`. Procura o lead pelo telefone (só os
dígitos, com e sem indicativo) na tabela de leads, e as mensagens desse lead. Confirma os nomes de
tabelas e colunas com `PRAGMA table_info` antes da consulta. Não assumas o schema de memória.

As conversas feitas **à mão** no WhatsApp normalmente não estão no CRM. Nesse caso, vai ao WhatsApp
Web.

## 2. WhatsApp Web (só leitura)

Ferramenta: chrome-devtools MCP ou claude-in-chrome. Nunca o controlo do desktop (ver memória
`feedback-browser-testing-tool-scope`).

1. Abre `https://web.whatsapp.com`. Se aparecer o QR, pára e pede ao utilizador para o ler com o
   telemóvel do número da conta. Explica de que número se trata.
2. Abre cada conversa pela pesquisa ou por `https://web.whatsapp.com/send?phone=<dígitos>`. A
   segunda forma abre a conversa sem enviar nada; **não carregues em enviar**.
3. Corre `scripts/wa_extract.js` (cola a função em `evaluate_script`). O script:
   - faz scroll até ao início, porque o WhatsApp só desenha as mensagens visíveis;
   - percorre a conversa de cima para baixo e junta as mensagens pelo `data-id`;
   - identifica o lado de cada mensagem pelo alinhamento: `flex-end` é a empresa, o resto é o
     cliente;
   - escreve `[hora, data] texto`, ou `<IMAGEM>` / `<AUDIO>` nas mensagens sem texto.
   - termina com `--- N/M mensagens lidas`. Se N < M, volta a correr.
4. Grava cada conversa em `.claude/agentes/<slug>/referencias/<dígitos>.txt` (fica no gitignore).
5. Ignora as mensagens de sistema (criptografia, mensagens temporárias). A saudação automática de
   anúncio ("Anúncio do Instagram…") é contexto: indica a **origem do lead**.

Se a conversa abrir só com 1 mensagem, confirma que é o contacto certo (nome no topo) antes de
extrair.

## 3. Escrever o comportamento esperado

No README da bancada, nesta ordem:

```
## Conversas de referência
| Conversa | Origem | Como acabou | Nº mensagens |

## Roteiro observado
1. <passo> — frase(s) exata(s) do atendente: "..."
   (variações: em 2 de 4 conversas fez X sem perguntar)
...

## Factos do negócio
<preços, durações, horários, morada, profissionais, pagamento, políticas>

## Limites
<o que foi recusado e com que frase>

## Divergências (perguntar ao utilizador)
<ex.: preço citado na conversa ≠ Base de Conhecimento ≠ site>

## Critérios de sucesso
- [ ] <verificável numa transcrição; ex.: "envia o catálogo quando o cliente aceita">
```

Regras para os critérios:
- Cada critério verifica-se lendo a transcrição ou o `.json` (rota, evento, mídia enviada). Um
  critério como "o tom é simpático" não se verifica assim; escreve antes "≤ 2 frases por resposta".
- Junta-lhes os critérios-padrão da skill do agente.
- Marca quais são **críticos**, ou seja, os que causam dano ao cliente final: dia errado, cobrança
  errada, promessa falsa, bot desligado. Uma falha crítica nunca se aceita "por agora".

## 4. Fontes externas da conta

Se o utilizador apontar o site ou o catálogo da conta: os sites em SPA não abrem com WebFetch; usa o
browser e lê o texto. Usa-os para resolver divergências, nunca para inventar factos que as conversas
não mostram.
