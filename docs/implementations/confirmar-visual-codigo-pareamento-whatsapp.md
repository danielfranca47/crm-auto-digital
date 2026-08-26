# Confirmar visual do código de pareamento na UI

**Branch:** `fix/confirmar-visual-codigo-pareamento-whatsapp-2`
**Status:** Todos os cenários validados

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/pareamento-codigo-whatsapp-login.md` (código de
pareamento como alternativa ao QR).

A Fase 2 dessa implementação (bloco de exibição do código em
`frontend-crm/src/components/agente/ConexaoNumero.tsx`) foi validada por
type-check e por teste ao vivo da mecânica (toggle, input, geração) — mas
sempre contra uma instância já conectada, então o bloco estilizado que
renderiza `qrPayload.pair_code` como texto grande (com o CSS/layout real)
nunca chegou a ser visto na tela com um código populado de verdade.

O objetivo aqui é só a checagem visual — a lógica já está implementada e
validada; não é esperado nenhum código novo, só confirmar (e ajustar CSS se
necessário) na próxima vez que a usuária precisar reconectar o WhatsApp de
verdade.

---

## O que checar

Bloco relevante: `frontend-crm/src/components/agente/ConexaoNumero.tsx:291-304`.

```tsx
<div className="font-mono-orion" style={{ fontSize: 28, letterSpacing: 4,
  color: 'var(--o-text)', background: '#fff', padding: '12px 20px', borderRadius: 8 }}>
  {qrPayload.pair_code}
</div>
```

Pontos de atenção ao ver um `pair_code` real populado:
- O texto cabe na caixa branca sem quebrar de forma estranha ou vazar do
  `borderRadius` — `letterSpacing: 4` + `fontSize: 28` pode estourar a
  largura dependendo do tamanho real da string retornada pela UazAPI.
- Contraste/legibilidade do texto sobre o fundo branco fixo (`#fff`) — o
  resto da UI usa tokens de tema (`var(--o-text)`, `var(--o-s1)` etc.), esse
  bloco é o único com fundo hardcoded.
- Comportamento em telas menores (a página é usada em `AiProfile.tsx`, aba
  "Conexão" — checar responsividade se possível).
- O aviso "Expira em 5 minutos" e a mensagem de expiração (`qrExpired`), se
  der tempo, deixar o código expirar e conferir o estado "Código expirado" /
  botão "Novo código" também.

---

## Passos

1. Aguardar o utilizador precisar reconectar o WhatsApp de verdade (evento
   externo, fora do controlo desta sessão). Quando acontecer:
   - Utilizador abre AiProfile → Conexão → modo "pareamento" → gera código.
   - Claude observa a tela (screenshot via chrome-devtools MCP, se a sessão
     tiver acesso ao browser nesse momento, ou o utilizador descreve/envia
     print).
2. Se o visual estiver correto: marcar o check como validado, sem alteração
   de código.
3. Se algo estiver errado (overflow, contraste, quebra de linha): ajustar
   só o CSS inline do bloco (linhas 291-304), sem tocar na lógica.
4. Fechar a fase: commit (se houve mudança de CSS) + relatório em linguagem
   simples + graduação seguindo `_processo-graduacao-implementacao.md`.

---

## Resultado

Testado ao vivo em 26/08/2026 com a conta de teste local (`user_id=15`,
instância desconectada — sem risco de derrubar sessão real), gerando um
`pair_code` real via UazAPI (`LRBM-48NL`) através de `AiProfile → Conexão →
modo pareamento`.

- Modo claro: texto cabe na caixa, legível, sem overflow — conforme esperado.
- Modo escuro: **bug real encontrado** — `color: 'var(--o-text)'` resolve
  para uma cor clara no tema escuro, renderizada sobre o fundo branco
  hardcoded (`background: '#fff'`) do bloco, deixando o código quase
  ilegível (baixíssimo contraste).
- Corrigido: `color: 'var(--o-text)'` → `color: '#111'` (fixo, já que o
  fundo do bloco também é fixo e não segue o tema) em
  `frontend-crm/src/components/agente/ConexaoNumero.tsx:295`. Reconfirmado
  visualmente nos dois temas após a correção — legível em ambos.

## Checks de Validação

- [x] Código de pareamento real visto na tela, visual conferido — 26/08/2026
- [x] Ajuste de CSS aplicado (contraste no modo escuro) e reconfirmado com
      novo código real — 26/08/2026
