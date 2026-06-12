## Informações atuais:

1- Página Pesquisa-
temos atualmente na página de /pesquisa no frontend uma "Pesquisa de Empresas" , onde o usuário seleciona uma proposta - atualmente com as opções de site, automações, trafego pago e produção de conteúdo. E seleciona também outras especificações que deseja para sua pesquisa como país, província, cidade, bairro, setor ou empresas  e quantidade desejada.

Após clicar em pesquisar aciona a api do google maps para realizar a pesquisa por ele.

No passado, a principal vantagem que era considerada para este tipo de pesquisa é mais do que somente pesquisar no google maps, mas acionar formas de coleta de informações personalizadas.

por exemplo:
atualmente só a proposta "site" tem a configuração de pesquisa definida, nela automação acionada além de achar a empresa no google maps, vai conferir se o perfil tem site e , caso tiver vai fazer um webscraping fazendo relatórios de pontos de melhoria no website e, se não tiver, ja registra. Essas informações vao para uma planilha e podem ser exportadas pelo usuário que ele pode utilizar na próxima página - Assistente IA.


Em relação aos outros meios de proposta e também canais de pesquisa eu ainda haveria que desenvolver para instagram, LinkedIn, facebook etc. e desenvolver também meios de coletas de informações para automações, trafego etc. O que resultaria em alto trabalho.

Para estes meios de pesquisa mais avançados como webscrap do site e pesquisas em outras plataformas sensíveis a bots como redes sociais criei um recurso chamado agent-local em C:\crm-auto-digital\agent-local . Ele irá funcionar como um programa que o usuário irá ter em sua máquina e seja capaz de executar operações mais personalizadas de pesquisas com selenium no chrome do usuário.

2- Página Assistente IA
Essa página tem como objetivo ser a geradora de leads via outbound, criar/atualizar leads (se existentes) e criar copys de prospecção.

Essa página no momento se comporta da seguinte maneira:
O usuário insere a planilha que foi exportada na página de pesquisa e preenche as opções. para gerar leads, gerar copys de prospecção, criar cards/ atualizar , se existentes e tipos de copys que quer gerar.

Problema desta página que não havia ai-profile quando foi desenvolvida, então ela não tem acesso as informações, caso necessário . Outro problema é que ela também so está compatível com o único método de pesquisa que era para nicho de site, qualquer planilha fora do formato aceito ignora.

Sobre a visão da plataforma:
No início , essa plataforma era para atender apenas ao público de profissionais de marketing digital. Hoje ela tem a visão de se tornar um sistema crm que vende sozinho. Capaz de atender múltiplos negócios de vários nichos diferentes.


A principal reflexão é: 
Atualmente, essas páginas estão adaptativas para qualquer usuário em qualquer nicho? 

## Objetivo
Nosso objetivo agora é analisar os as soluções atuais das seguintes páginas e pensar melhorias para elas.
Páginas: 
- Pesquisa
- Assistente IA

Eu pensei em conseguir atualizar para oferecer 2 formas de soluções:

1- Um forma de pesquisa e assistente geral, que conseguisse atender múltiplos nichos de uma forma democrática e padrão do sistema nos principais canais.
2- Oferecer UPSELLs para que o usuário entre em contato comigo e solicite extensões personalizadas de pesquisas. Pois para alguns pode ser interessante e evita trabalho antecipado desnecessário. 

Daí a ideia seria para o usuário que comprou o upsell de uma automação de pesquisa ela ficar disponível no frontend para ele.

Como podemos fazer isto?

---

## Análise Estratégica — Claude Code (2026-04-18)

### Diagnóstico

O estado atual tem três problemas centrais:

1. **Acoplamento de nicho** — A página Pesquisa assume a proposta "site" como padrão. O Assistente IA aceita só o formato de planilha gerado por essa proposta. Qualquer outro nicho fica de fora.
2. **Ausência de AI Profile no Assistente IA** — As configurações de persona, produto e estilo de copy que o usuário definiu no AI Profile são ignoradas na geração de leads outbound.
3. **Escalabilidade de pesquisas avançadas** — Implementar coleta para cada canal (Instagram, LinkedIn, etc.) antecipadamente é trabalho de alto custo com retorno incerto por usuário.

---

### Arquitetura proposta: dois trilhos paralelos

#### Trilho 1 — Pesquisa & Assistente IA Genérico (produto base, todos os planos)

**Objetivo:** funcionar para qualquer nicho, sem depender de canais externos.

**Como fazer:**

**A. Pesquisa Genérica (Google Maps universal)**
- Remover a validação implícita de proposta "site". A busca no Google Maps já retorna: nome, endereço, telefone, site (quando existe), categoria, avaliações.
- Tornar o campo "proposta" descritivo livre (texto + sugestões), não um enum fechado. O usuário descreve o que vende; isso vai para o AI Profile no contexto da pesquisa.
- Gerar a planilha de saída com colunas padronizadas e universais:

| empresa | telefone | site | categoria | cidade | tem_site | notas |
|---|---|---|---|---|---|---|

- A coluna `notas` fica livre para dados extras (ex.: resultado de webscraping se disponível).
- Manter o webscraping de site como enriquecimento opcional, ativado só se o lead tiver site.

**B. Assistente IA Genérico**
- Aceitar **qualquer planilha** com mapeamento de colunas pelo usuário (ele indica qual coluna é nome, qual é contato, qual é observação). Interface de "de-para" simples.
- Integrar o AI Profile: ao gerar copys, buscar `ai_profile` do usuário (via `CORE_API_BASE/me/ai-profile`) e injetar no prompt: produto, público-alvo, tom de voz, proposta de valor.
- Geração de copy multiformat: WhatsApp, e-mail frio, DM Instagram — o usuário escolhe o canal e o sistema adapta o tom.
- Criar/atualizar leads no Kanban com os dados mapeados.

**Vantagens:**
- Qualquer nicho funciona sem nenhuma configuração extra.
- AI Profile já existente — reaproveitamento de infraestrutura zero custo.
- O usuário vê valor imediato mesmo sem comprar upsell.

---

#### Trilho 2 — Extensões de Pesquisa (Upsell / Add-ons)

**Objetivo:** oferecer enriquecimento avançado por canal sob demanda, sem trabalho antecipado desnecessário.

**Como fazer:**

**A. Modelo de extensões (plugin pattern)**
Cada extensão é um módulo independente que:
1. Define um `source_type` único (ex.: `instagram_profile`, `linkedin_company`, `google_maps_reviews`).
2. Recebe a lista de empresas da pesquisa base e retorna colunas extras.
3. É executado pelo `agent-local` (Selenium na máquina do usuário) para canais sensíveis a bot, ou via API direta para canais abertos.

Estrutura sugerida no `agent-local`:
```
agent-local/
  extensions/
    instagram_profile.py   # coleta seguidores, bio, últimos posts
    linkedin_company.py    # coleta tamanho, setor, vagas abertas
    google_reviews.py      # coleta avaliações e comentários
    website_audit.py       # já existe — webscraping de site
```

**B. Controle de acesso por plano**
No `backend-core`, adicionar campo `enabled_extensions: list[str]` ao modelo `Subscription` ou `ai_profiles`. Ao fazer login, o frontend recebe quais extensões estão ativas.

No frontend (página Pesquisa), cada extensão aparece como um card com um cadeado se não comprada — ao clicar, abre modal de upsell com CTA para contato/compra.

**C. Fluxo de ativação de upsell**
1. Usuário clica no card bloqueado → modal explica o que a extensão faz + botão "Quero contratar".
2. Botão abre link/formulário de contato com o nicho pré-preenchido (pode ser WhatsApp do dono da plataforma).
3. Após contrato manual, o dono ativa a extensão no painel admin (`SaaSAdmin/`) setando `enabled_extensions` para aquele usuário.
4. Na próxima sessão do usuário, o card aparece desbloqueado.

**Vantagens:**
- Zero custo de desenvolvimento das extensões antes de ter demanda real.
- Receita incremental por usuário sem aumentar o preço base.
- O agent-local já existe — só adicionar os módulos de extensão conforme vendas.

---

### Estrutura técnica necessária (resumo de mudanças)

| Componente | Mudança necessária |
|---|---|
| `frontend-crm/src/pages/Pesquisa.tsx` | Campo proposta livre; UI de extensões com lock/unlock |
| `frontend-crm/src/pages/AssistenteIA.tsx` | Mapeamento de colunas; injeção de AI Profile nos prompts |
| `backend-crm/routes/assistente_ia.py` | Aceitar payload genérico; buscar AI Profile do core |
| `backend-crm/routes/prospeccao.py` | Remover validação de proposta fixa |
| `backend-core/app/models/` | Campo `enabled_extensions` em Subscription ou AIProfile |
| `backend-core/app/routes/ai_profiles.py` | Expor `enabled_extensions` no GET do perfil |
| `agent-local/extensions/` | Criar estrutura de plugins; cada extensão é um arquivo |
| `frontend-crm/src/components/SaaSAdmin/` | UI para ativar extensões por usuário |

---

### Ordem de execução recomendada

1. **Fase 1 (base):** Tornar Pesquisa e Assistente IA agnósticos de nicho + integrar AI Profile no Assistente IA.
2. **Fase 2 (upsell UI):** Criar cards de extensões bloqueadas na página Pesquisa + modal de CTA de contato.
3. **Fase 3 (admin):** Painel SaaSAdmin para ativar extensões por usuário + campo `enabled_extensions` no core.
4. **Fase 4 (extensões):** Desenvolver módulos no agent-local conforme demanda real dos upsells vendidos.

Essa ordem entrega valor ao usuário final rapidamente (fase 1) e estrutura a monetização (fases 2–3) antes de gastar tempo em extensões que talvez nunca sejam solicitadas (fase 4).