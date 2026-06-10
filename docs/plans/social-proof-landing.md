# Plano — Social Proof na Landing da Lara

**Status:** Aguardando conteúdo (bloqueio de produto, não de código)
**Área:** `website/src/pages/CRMLanding.tsx` — seção Social Proof

---

## O que já existe no código

A estrutura está pronta. A landing já tem:
- Uma seção "Quem já usa a Lara" com o depoimento placeholder da "Mariana S."
- Um segundo slot vazio com o texto "Mais resultados a caminho"
- Layout de estrelas, nome, cargo e cidade pronto para receber dados reais

**O código não precisa de alteração para os primeiros 2 depoimentos.** Só precisa de conteúdo.

---

## Por que isso importa

A landing está em Perceived Likelihood (confiança de que funciona) ~5.5/10.
Cada camada de prova real sobe essa pontuação:

| O que você entrega | Impacto |
|---|---|
| 1 depoimento real | → 6.5/10 |
| Número agregado ("X leads qualificados") | → 7/10 |
| Print de conversa real (sem dados pessoais) | → 7.5/10 |
| 3+ depoimentos de setores diferentes | → 8/10 |

Com 5.5/10, a garantia dupla está compensando parcialmente — mas sem prova real há um teto. Nenhuma mudança de copy ou código resolve isso.

---

## O que você precisa reunir

### Depoimento 1 (mínimo viável — 1 pessoa já basta pra começar)

Para cada pessoa que usar a Lara, peça as seguintes informações:

**a) Um resultado concreto** — o mais específico possível:
- Qual foi o resultado? (leads recuperados, vendas fechadas, dinheiro recebido, tempo economizado)
- Tem um número? ("3 leads", "R$1.800", "2 vendas na primeira semana")
- Em quanto tempo aconteceu? ("na primeira semana", "nos primeiros 30 dias")

**b) Uma frase no estilo deles** — pode ser reformulada por você, mas o núcleo deve ser deles:
- O que acharam da Lara?
- O que mudou no dia a dia deles?
- Tem alguma situação específica que ficou marcada?

**c) Dados de identificação** (para mostrar que é pessoa real):
- Primeiro nome + inicial do sobrenome (ex.: "Mariana S.")
- O que fazem / qual é o negócio (ex.: "infoprodutora", "clínica de estética", "corretor de imóveis")
- Cidade e estado (ex.: "São Paulo, SP")

**d) Opcional mas poderoso:**
- Uma foto de perfil (pode ser a do WhatsApp mesmo — não precisa ser profissional)
- Um print da conversa da Lara com o lead (apague dados pessoais do lead antes de enviar)

---

### Número agregado (opcional, mas vale muito)

Se você tiver acesso ao banco de dados da Lara após 2–3 semanas de beta, posso te ajudar a extrair:
- Total de conversas iniciadas
- Total de leads qualificados
- Total de follow-ups enviados

Esses números viram uma linha na landing: *"X leads qualificados nos primeiros 30 dias de beta"* — mesmo sendo números pequenos, qualquer número real é mais poderoso que nenhum.

---

## Checklist de coleta

Marque quando tiver cada item:

**Depoimento 1:**
- [ ] Resultado concreto com número
- [ ] Frase do usuário (pode ser editada por você)
- [ ] Nome, segmento e cidade
- [ ] Foto de perfil (opcional)
- [ ] Print de conversa (opcional)

**Depoimento 2 (de um setor diferente do primeiro):**
- [ ] Resultado concreto com número
- [ ] Frase do usuário
- [ ] Nome, segmento e cidade
- [ ] Foto de perfil (opcional)

**Número agregado:**
- [ ] Pediu a extração do banco ao Claude

---

## Prompt pronto para implementação

Quando tiver pelo menos o Depoimento 1 preenchido, cole este prompt no chat e substitua os campos em `[COLCHETES]`:

```
Quero atualizar a seção Social Proof da landing da Lara com depoimentos reais.

A seção já existe em website/src/pages/CRMLanding.tsx — atualmente tem um
placeholder ("Mariana S.") e um slot vazio. Preciso substituir pelo conteúdo real.

DEPOIMENTO 1:
- Frase: "[cole a frase aqui]"
- Nome: "[Primeiro Nome + Inicial do Sobrenome]"
- Segmento: "[o que a pessoa faz]"
- Cidade/Estado: "[cidade, estado]"
- Foto: [tem foto? sim/não — se sim, qual o caminho do arquivo ou URL]

DEPOIMENTO 2 (se tiver):
- Frase: "[cole a frase aqui]"
- Nome: "[Primeiro Nome + Inicial do Sobrenome]"
- Segmento: "[o que a pessoa faz]"
- Cidade/Estado: "[cidade, estado]"
- Foto: [tem foto? sim/não]

NÚMERO AGREGADO (se tiver):
- "[ex.: 47 leads qualificados nos primeiros 30 dias de beta]"

Se tiver print de conversa real da Lara com lead (sem dados pessoais do lead),
me diz e combinamos como exibir na seção.

Substitua o placeholder da Mariana S. pelo Depoimento 1.
Se tiver Depoimento 2, preencha o slot vazio.
Se tiver número agregado, adicione acima dos cards como stat de destaque.
```

---

## Manutenção

Este arquivo pode ser deletado quando:
- A seção Social Proof estiver com pelo menos 1 depoimento real implementado
- E o placeholder "Mariana S." tiver sido substituído

Após a implementação, não há arquivo de arquitectura a atualizar — social proof é conteúdo, não lógica de sistema.
