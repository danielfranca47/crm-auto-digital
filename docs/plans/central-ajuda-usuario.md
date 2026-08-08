# Central de Ajuda para Usuários (Documentação Educativa)

> Contexto: motivado pela investigação do Cenário 5 (queixa de saúde sem handoff confiável)
> em `docs/implementations/sessao-teste-corrente.md`. Decisão de produto: a filosofia do
> sistema é "cada negócio configura sua própria rede de segurança" via `custom_instructions`
> e Fluxo de Venda (Camada 7) — não um guardrail fixo no prompt da IA Mãe, para não competir
> com as prioridades já existentes (ver `docs/architecture/llm-architecture.md`). O gap real
> não é técnico, é de descoberta: nenhum dos dois mecanismos vem configurado por padrão
> (`custom_instructions` nasce `null`, Fluxo de Venda nasce com `blocks: []`) e a maioria dos
> usuários provavelmente não sabe que precisa configurá-los nem como fazê-lo. Em vez de um
> artigo isolado sobre esse caso, decisão do utilizador foi tratar isto como o primeiro caso
> de uso de uma central de ajuda mais ampla, cobrindo vários tópicos do produto.

---

## M1 — Central de Ajuda (documentação educativa geral para usuários)

**Prioridade: BAIXA**

**Problema:** o sistema não tem nenhuma documentação voltada ao usuário final (dono do
negócio configurando seu agente) explicando como tirar proveito das ferramentas de
personalização — `custom_instructions`, Fluxo de Venda, AI Profile em geral. Hoje o único
"onboarding" guiado é o wizard da Base de Conhecimento (ver `knowledge-base.md`); o resto do
produto não tem equivalente.

**O que construir:** uma central de ajuda dentro (ou anexa) do produto, estilo Central de
Ajuda do Meta Ads — artigos curtos e práticos, organizados por tópico, com exemplos prontos
para copiar/adaptar.

**Primeiro artigo já identificado (motivador desta entrada):** "Como configurar handoff para
queixas de saúde e pedidos de atendimento humano" — cobriria:
- Por que a IA não faz handoff automático por padrão (filosofia de personalização)
- Exemplo de texto pronto para `custom_instructions`
- Como configurar um `kw_trigger` no Fluxo de Venda para uma resposta determinística e segura
  nesses casos — e a limitação de que isso sozinho não notifica a equipe/pausa o bot (só a
  política de handoff real, `handoff_policy`, faz isso)

**Outros tópicos candidatos (não exaustivo — expandir quando o item for priorizado):**
- Diferença entre `custom_instructions`, campos de qualificação e Fluxo de Venda — quando
  usar cada um
- Como escrever `offer_description` e `custom_instructions` eficazes por nicho de negócio
- Como configurar o Fluxo de Venda (Camada 7) do zero
- LGPD e reativação — por que o sistema avisa "não configurado" e o que preencher

**Onde:** decisão de arquitetura em aberto (secção dentro do `frontend-crm`, ex.: link a
partir de `/ai-profile`, vs. site de documentação separado) — a decidir em Plan Mode quando
este item for priorizado.

**Fora do escopo desta entrada:** conteúdo escrito de qualquer artigo; qualquer mudança de
código em `decision_engine.py` ou outros serviços.
