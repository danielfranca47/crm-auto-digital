import { useState } from 'react';
import { Link } from 'react-router-dom';
import { OrionShell } from '@/components/agente/OrionShell';

type Journey = 'in' | 'out';
type AgentId = 'a1' | 'a2' | 'a3';

interface QCard  { label: string; text: string }
interface TempCard { cls: 'hot' | 'warm' | 'cold' | 'done'; label: string; desc: string }
interface Bullet  { text: string }

interface Stage {
  icon: string;
  badge: 'in' | 'out' | 'both';
  title: string;
  who: 'bot' | 'human' | 'collab';
  variant?: 'inbound-start' | 'outbound-start' | 'inbound-only' | 'outbound-only' | 'human';
  desc: string;
  bullets?: Bullet[];
  qCards?: QCard[];
  tempCards?: TempCard[];
}

interface AgentData {
  id: AgentId;
  chip: string;
  title: string;
  subtitle: string;
  desc: string;
  useCases: string[];
  descIn: string;
  descOut: string;
  flowIn: Stage[];
  flowOut: Stage[];
}

// ─── Dados ──────────────────────────────────────────────────

const AGENTS: AgentData[] = [
  {
    id: 'a1',
    chip: 'Agente 01 · Robusto',
    title: 'SDR de Alto Ticket',
    subtitle: '+ Follow-up Pós-Apresentação',
    desc: 'Qualifica profundamente antes de acionar o humano. A jornada muda conforme a origem do lead: inbound entra pela dor já declarada; outbound entra pelo perfil presumido. Os Filtros 2 e 3 existem em ambos, mas em ordens diferentes.',
    useCases: ['Imóveis · Advocacia', 'Clínicas estéticas', 'Consultorias B2B', 'Ciclo longo · Alto ticket'],
    descIn: 'O lead chegou até você — clicou num anúncio, preencheu um formulário. Ele já sente uma dor. A primeira missão do agente é validar o <strong>Fit</strong> (Filtro 1), depois aprofundar a qualificação nos 4Ps (Filtro 3). A Dor está implícita — apenas refinamos ela.',
    descOut: 'O agente foi até o lead — lista prospectada, perfil selecionado. O lead tem <strong>Fit presumido</strong>, mas não necessariamente sente a dor. A missão inicial é despertar e confirmar a <strong>Dor</strong> (Filtro 2). Depois validamos o Fit antes dos 4Ps.',
    flowIn: [
      { icon: 'IN', badge: 'in', title: 'Entrada do Lead — Dor Declarada', who: 'bot', variant: 'inbound-start',
        desc: 'O lead chega via formulário, anúncio ou link direto. Demonstrou interesse — sinal de dor ativa.',
        bullets: [
          { text: '<strong>Mensagem de boas-vindas:</strong> tom consultivo — "Obrigado pelo interesse! Para entender melhor como posso ajudar..."' },
          { text: '<strong>Registro de origem:</strong> qual campanha, anúncio ou keyword trouxe o lead.' },
          { text: '<strong>Captura da dor inicial:</strong> se o formulário já trouxe essa info, usa sem repetir a pergunta.' },
        ]},
      { icon: 'F1', badge: 'in', title: 'Filtro 1 — Validação de Fit / Perfil', who: 'bot', variant: 'inbound-only',
        desc: 'Como a dor já existe, o primeiro passo é verificar se o lead tem o perfil certo. Sem fit, não adianta aprofundar. 2–3 perguntas rápidas.',
        bullets: [
          { text: '<strong>Dados binários:</strong> faturamento, setor, porte, localização — confirmação ou descarte imediato.' },
          { text: '<strong>Score de fit automático:</strong> abaixo do mínimo — encerra gentilmente ou encaminha para nurture.' },
          { text: '<strong>Sem detalhar a dor ainda:</strong> foco em elegibilidade — a dor será aprofundada no Filtro 3.' },
        ],
        qCards: [
          { label: 'Exemplo', text: '"Só para garantir que posso te ajudar da forma certa — sua empresa atua em qual setor?"' },
          { label: 'Exemplo', text: '"Vocês faturam acima de R$ 100 mil/mês atualmente?"' },
        ]},
      { icon: 'F3', badge: 'both', title: 'Filtro 3 — Poder, Prioridade, Preço, Timing', who: 'bot',
        desc: 'No inbound, o lead já tem dor e fit confirmado. O Filtro 3 aprofunda: existe poder de decisão? É prioridade agora? Tem verba? O timing bate?',
        qCards: [
          { label: 'Poder', text: '"Além de você, quem mais costuma participar da análise de soluções como essa?"' },
          { label: 'Prioridade', text: '"O que acontece com suas metas se esse problema não for resolvido nos próximos 60 dias?"' },
          { label: 'Preço', text: '"Vocês já separaram uma verba para isso, ou ainda está em definição?"' },
          { label: 'Timing', text: '"Existe alguma data ou evento que exige ter isso resolvido até lá?"' },
        ]},
      { icon: 'AG', badge: 'both', title: 'Agendamento + Handoff para Humano', who: 'collab',
        desc: 'Lead aprovado nos filtros. O bot agenda a reunião e monta o dossiê completo para o vendedor — dor relatada, score dos 4Ps, histórico da conversa.',
        bullets: [
          { text: '<strong>Calendário integrado:</strong> horários disponíveis em tempo real, confirmação automática.' },
          { text: '<strong>Dossiê automático:</strong> nome, empresa, dor declarada, score dos 4Ps, canal de origem.' },
          { text: '<strong>Lembretes ao lead:</strong> 24h e 1h antes da reunião para reduzir no-shows.' },
        ]},
      { icon: 'AP', badge: 'both', title: 'Apresentação Comercial', who: 'human', variant: 'human',
        desc: 'O vendedor conduz a reunião. O bot fica pausado. Após a apresentação, o vendedor registra a temperatura do lead no CRM — esse input ativa o fluxo certo de follow-up.',
        bullets: [
          { text: '<strong>Status pós-reunião:</strong> Quente / Morno / Frio / Perdido — cada status aciona um fluxo diferente.' },
          { text: '<strong>Proposta enviada?</strong> Flag que define se o follow-up referencia a proposta ou retoma a apresentação.' },
        ]},
      { icon: 'FU', badge: 'both', title: 'Follow-up Pós-Apresentação por Temperatura', who: 'bot',
        desc: 'O bot retoma o contato com cadência baseada na temperatura definida pelo vendedor.',
        bullets: [
          { text: '<strong>Escalada ao humano:</strong> se o lead responde com interesse alto no follow-up, notifica o vendedor imediatamente.' },
          { text: '<strong>Sinal de compra detectado:</strong> keywords como "quanto custa", "como funciona o contrato" acionam alerta.' },
        ],
        tempCards: [
          { cls: 'hot',  label: '🔥 Quente', desc: 'Follow-up em 24h. Mensagens curtas, senso de urgência. Facilitação direta para assinar ou pagar.' },
          { cls: 'warm', label: '🌡 Morno',  desc: 'Sequência 5–7 dias. Casos de sucesso, conteúdo de valor, remoção de objeções específicas.' },
          { cls: 'cold', label: '❄ Frio',   desc: 'Resgata a dor original. Propõe nova conversa. Verifica mudança no timing ou budget.' },
          { cls: 'done', label: '✓ Perdido', desc: 'Move para nurture de longo prazo. Reativação automática em 30–60 dias com novo gatilho.' },
        ]},
      { icon: 'FC', badge: 'both', title: 'Fechamento', who: 'human', variant: 'human',
        desc: 'Conduzido pelo humano. O bot prepara o terreno e avisa o vendedor quando o lead dá sinal de compra.',
        bullets: [
          { text: '<strong>Facilitação opcional:</strong> bot pode enviar link de contrato, boleto ou agendamento de call de fechamento.' },
        ]},
      { icon: 'PV', badge: 'both', title: 'Pós-Venda / Onboarding', who: 'collab',
        desc: 'Pagamento confirmado dispara onboarding automatizado: boas-vindas, checklist de início, kick-off com o time.',
        bullets: [
          { text: '<strong>Boas-vindas personalizada:</strong> nome, serviço contratado, próximos passos claros.' },
          { text: '<strong>Coleta de dados iniciais:</strong> formulário de onboarding enviado automaticamente.' },
          { text: '<strong>NPS automático:</strong> pesquisa de satisfação após período inicial definido.' },
        ]},
    ],
    flowOut: [
      { icon: 'OUT', badge: 'out', title: 'Prospecção Ativa — Fit Presumido', who: 'bot', variant: 'outbound-start',
        desc: 'O agente inicia contato com leads selecionados por perfil externo. O Fit básico já foi presumido na seleção.',
        bullets: [
          { text: '<strong>Abordagem contextualizada:</strong> usa dados do lead (setor, cargo, empresa) para criar relevância.' },
          { text: '<strong>Sequência multi-canal:</strong> WhatsApp → e-mail → LinkedIn com espaçamento de 2–3 dias.' },
          { text: '<strong>Limite de tentativas:</strong> máximo configurável (ex: 4 touchpoints) antes de arquivar.' },
        ]},
      { icon: 'F2', badge: 'out', title: 'Filtro 2 — Investigação de Dor', who: 'bot', variant: 'outbound-only',
        desc: 'O lead não estava procurando por você — precisamos identificar ou despertar a dor. Perguntas abertas que instigam reflexão.',
        bullets: [
          { text: '<strong>Perguntas de escavação:</strong> "Como vocês estão lidando com X hoje?" / "Esse problema já custou oportunidades?"' },
          { text: '<strong>Desvio de escopo:</strong> se a dor não bate com a oferta, encerra educadamente.' },
        ],
        qCards: [
          { label: 'Despertar dor', text: '"Empresas do seu setor costumam ter dificuldade com X — isso é algo que vocês também enfrentam?"' },
          { label: 'Escavar impacto', text: '"Quanto tempo ou recurso vocês gastam hoje tentando resolver isso manualmente?"' },
        ]},
      { icon: 'F1', badge: 'out', title: 'Filtro 1 — Reforço e Confirmação de Fit', who: 'bot', variant: 'outbound-only',
        desc: 'Dor confirmada. O agente valida o fit com precisão — os dados presumidos na lista podem estar desatualizados.',
        bullets: [
          { text: '<strong>Confirmação de dados:</strong> verifica faturamento, porte, tomador de decisão — de forma natural.' },
          { text: '<strong>Descarte tardio:</strong> leads que passaram da dor mas falham no fit real são descartados aqui.' },
        ]},
      { icon: 'F3', badge: 'both', title: 'Filtro 3 — Poder, Prioridade, Preço, Timing', who: 'bot',
        desc: 'No outbound, chegamos ao Filtro 3 com Dor e Fit confirmados. A qualificação profunda dos 4Ps define se vale avançar.',
        qCards: [
          { label: 'Poder',    text: '"Como funciona o processo de aprovação para investimentos desse tipo na empresa?"' },
          { label: 'Prioridade', text: '"Em uma escala de 1 a 10, qual a prioridade de resolver isso agora?"' },
          { label: 'Preço',   text: '"Já existe uma verba reservada ou ainda está em fase de aprovação?"' },
          { label: 'Timing',  text: '"Qual seria o prazo ideal para vocês terem isso funcionando?"' },
        ]},
      { icon: 'AG', badge: 'both', title: 'Agendamento + Handoff para Humano', who: 'collab',
        desc: 'Lead qualificado. No outbound, o dossiê inclui o histórico da prospecção — como o lead foi abordado e qual dor foi despertada.',
        bullets: [
          { text: '<strong>Dossiê outbound:</strong> canal de prospecção, touchpoints anteriores, dor despertada, script de abertura usado.' },
          { text: '<strong>Lembretes anti-no-show:</strong> 24h e 1h antes — leads outbound têm menor comprometimento inicial.' },
        ]},
      { icon: 'AP', badge: 'both', title: 'Apresentação Comercial', who: 'human', variant: 'human',
        desc: 'O vendedor conduz com o lead já qualificado. Registra temperatura ao final para acionar o follow-up correto.' },
      { icon: 'FU', badge: 'both', title: 'Follow-up Pós-Apresentação por Temperatura', who: 'bot',
        desc: 'No outbound, leads frios recebem reforço da dor despertada — mais importante reconectar com o problema do que com a oferta.',
        tempCards: [
          { cls: 'hot',  label: '🔥 Quente', desc: 'Empurrar ao fechamento. Urgência real. Facilitar pagamento/contrato.' },
          { cls: 'warm', label: '🌡 Morno',  desc: 'Nutrir com provas sociais e casos similares ao setor do lead.' },
          { cls: 'cold', label: '❄ Frio',   desc: 'Reconectar com a dor original despertada na prospecção. Propor nova conversa.' },
        ]},
      { icon: 'FC', badge: 'both', title: 'Fechamento', who: 'human', variant: 'human',
        desc: 'Conduzido pelo humano com apoio do bot para detecção de sinais de compra e envio de facilitadores.' },
      { icon: 'PV', badge: 'both', title: 'Pós-Venda / Onboarding', who: 'collab',
        desc: 'Boas-vindas, checklist de onboarding, coleta de dados iniciais e NPS automático após período inicial.' },
    ],
  },
  {
    id: 'a2',
    chip: 'Agente 02 · Direto',
    title: 'Vendedor Autônomo',
    subtitle: 'Low Ticket',
    desc: '100% automatizado. Qualifica, apresenta e fecha sem humano. A diferença entre inbound e outbound está na velocidade da qualificação e no tom da abordagem inicial.',
    useCases: ['Infoprodutos', 'E-commerce', 'Pedidos de lojas físicas', 'Cursos · Assinaturas'],
    descIn: 'Lead chegou via anúncio, link de bio, landing page. Já tem dor — clicar foi o sinal. O agente vai direto confirmar o <strong>fit</strong>. Com fit confirmado, apresenta e empurra ao fechamento imediato.',
    descOut: 'Lead foi prospectado por perfil. Não necessariamente sente a dor ainda. O agente abre com uma pergunta que toca na dor, valida se ela existe, e só então apresenta o produto como solução.',
    flowIn: [
      { icon: 'IN', badge: 'in', title: 'Entrada — Dor Implícita no Clique', who: 'bot', variant: 'inbound-start',
        desc: 'O lead clicou no anúncio ou link — sinal de dor ou interesse. Recepção rápida e encaminhamento para confirmação de fit.',
        bullets: [
          { text: '<strong>Recepção rápida:</strong> mensagem curta de boas-vindas com referência ao que o lead clicou.' },
          { text: '<strong>Registro de origem:</strong> campanha, anúncio, canal — usado para personalizar o pitch.' },
        ]},
      { icon: 'F1', badge: 'in', title: 'Qualificação de Fit — 1 a 2 Perguntas', who: 'bot', variant: 'inbound-only',
        desc: 'Para low ticket, o filtro de fit é mínimo. 1–2 perguntas para confirmar que o produto resolve o problema do lead.',
        bullets: [
          { text: '<strong>Pergunta de confirmação:</strong> "Você está procurando [resultado do produto] para [contexto]?" — sim/não já basta.' },
          { text: '<strong>Sem análise de budget:</strong> preço baixo elimina a necessidade de filtrar capacidade financeira.' },
        ],
        qCards: [
          { label: 'Exemplo fit', text: '"Você está buscando emagrecer de forma saudável sem dietas restritivas?"' },
          { label: 'Exemplo fit', text: '"Você já tem uma loja e quer automatizar os pedidos pelo WhatsApp?"' },
        ]},
      { icon: 'PT', badge: 'both', title: 'Pitch — Apresentação pelo Bot', who: 'bot',
        desc: 'No inbound, o pitch vai mais direto à solução. Estrutura: solução → benefícios → prova → oferta.',
        bullets: [
          { text: '<strong>Estrutura inbound:</strong> Solução direta → 3 benefícios concretos → prova social → oferta com urgência.' },
          { text: '<strong>Mídia rica:</strong> imagens, vídeo curto de demonstração, depoimentos em áudio/vídeo.' },
          { text: '<strong>FAQ automático:</strong> respostas para as 5 objeções mais comuns do produto.' },
        ]},
      { icon: 'OF', badge: 'both', title: 'Oferta + Link de Pagamento', who: 'bot',
        desc: 'Apresenta o preço e envia o link de pagamento com mínimo atrito.',
        bullets: [
          { text: '<strong>Preço âncora:</strong> mostra valor "cheio" antes do preço real.' },
          { text: '<strong>Link direto:</strong> Pix, cartão, boleto — integração Hotmart, Stripe, PagSeguro.' },
          { text: '<strong>Urgência real:</strong> vagas limitadas, oferta expira, bônus exclusivo com prazo.' },
          { text: '<strong>Garantia:</strong> menciona política de devolução para reduzir risco percebido.' },
        ]},
      { icon: 'CA', badge: 'both', title: 'Follow-up de Carrinho Abandonado', who: 'bot',
        desc: 'Lead recebeu o link mas não pagou. Sequência de 3 mensagens com abordagens diferentes.',
        bullets: [
          { text: '<strong>1ª tentativa (2h):</strong> lembrete simples — "Seu pedido ainda está reservado."' },
          { text: '<strong>2ª tentativa (24h):</strong> reforça benefício principal, remove objeção mais comum.' },
          { text: '<strong>3ª tentativa (48h):</strong> urgência máxima — "Últimas horas para garantir o preço especial."' },
          { text: '<strong>Sem resposta:</strong> move para lista de reativação de 30 dias.' },
        ]},
      { icon: 'PV', badge: 'both', title: 'Confirmação + Upsell + Onboarding', who: 'bot',
        desc: 'Pagamento confirmado dispara entrega, boas-vindas, upsell e NPS automático.',
        bullets: [
          { text: '<strong>Entrega automática:</strong> acesso ao produto digital ou confirmação do pedido.' },
          { text: '<strong>Upsell imediato:</strong> "Clientes que compraram X também levaram Y com desconto exclusivo."' },
          { text: '<strong>NPS automático:</strong> após 7 dias do uso/recebimento.' },
        ]},
    ],
    flowOut: [
      { icon: 'OUT', badge: 'out', title: 'Prospecção Ativa — Fit Presumido', who: 'bot', variant: 'outbound-start',
        desc: 'Contato com lista fria — seguidores, base de e-mail, retargeting. Perfil básico presumido. Abertura com curiosidade ou identificação com o problema.',
        bullets: [
          { text: '<strong>Abertura por dor:</strong> mensagem que toca no problema antes de mencionar o produto.' },
          { text: '<strong>Volume:</strong> centenas de contatos/dia — sem personalização profunda, mas com segmentação por lista.' },
        ],
        qCards: [
          { label: 'Abertura exemplo', text: '"Você também sente que perde tempo tentando controlar os pedidos manualmente todo dia?"' },
        ]},
      { icon: 'F2', badge: 'out', title: 'Confirmação de Dor — 1 Pergunta', who: 'bot', variant: 'outbound-only',
        desc: 'Uma única pergunta direta para confirmar que a dor existe. Qualquer confirmação avança ao pitch.',
        qCards: [
          { label: 'Confirmação', text: '"Esse é um problema que você enfrenta hoje?"' },
          { label: 'Alternativa',  text: '"Isso faz sentido para a sua situação atual?"' },
        ]},
      { icon: 'PT', badge: 'both', title: 'Pitch — Apresentação pelo Bot', who: 'bot',
        desc: 'No outbound, o pitch precisa primeiro validar a dor antes de apresentar a solução. Estrutura: dor confirmada → agitação → solução → prova → oferta.',
        bullets: [
          { text: '<strong>Estrutura outbound:</strong> Espelha a dor dita pelo lead → "E se houvesse uma forma de..." → produto como solução → prova → CTA.' },
          { text: '<strong>Personalização pela dor:</strong> usa o exato problema confirmado para personalizar o pitch.' },
        ]},
      { icon: 'OF', badge: 'both', title: 'Oferta + Link de Pagamento', who: 'bot',
        desc: 'Mesma lógica do inbound: preço âncora, link direto, urgência e garantia para eliminar atrito na decisão.' },
      { icon: 'CA', badge: 'both', title: 'Follow-up de Carrinho Abandonado', who: 'bot',
        desc: 'No outbound, a 2ª mensagem reconecta com a dor confirmada antes de reapresentar o produto.' },
      { icon: 'PV', badge: 'both', title: 'Confirmação + Upsell + Onboarding', who: 'bot',
        desc: 'Entrega automática, upsell imediato e NPS após 7 dias. Idêntico ao inbound.' },
    ],
  },
  {
    id: 'a3',
    chip: 'Agente 03 · Híbrido',
    title: 'Assistente Comercial',
    subtitle: 'com Agendamento Inteligente',
    desc: 'Funciona como recepcionista comercial inteligente. Qualifica, agenda e entrega o lead preparado para o profissional. Não apresenta nem fecha — mas faz tudo antes e cuida do follow-up depois.',
    useCases: ['Coaches · Terapeutas', 'Personal Trainers', 'Consultores solo', 'Serviços por hora'],
    descIn: 'Lead veio por indicação, anúncio ou bio do profissional. Dor presente — ele busca ativamente uma solução. O agente confirma o fit rápido e parte para o aquecimento e agendamento.',
    descOut: 'Profissional prospectando ativamente — lista de contatos, base de ex-clientes, seguidores frios. Fit presumido pelo perfil. O agente abre identificando e despertando a dor, valida se faz sentido e só então propõe o agendamento.',
    flowIn: [
      { icon: 'IN', badge: 'in', title: 'Entrada — Interesse Ativo Demonstrado', who: 'bot', variant: 'inbound-start',
        desc: 'O lead entrou em contato ou clicou em um link. O agente se apresenta como assistente do profissional e acolhe com tom próximo.',
        bullets: [
          { text: '<strong>Apresentação do bot:</strong> "Oi! Aqui é a assistente da [Nome do profissional]. Vi que você tem interesse em..."' },
          { text: '<strong>Captura da dor inicial:</strong> se o lead veio de formulário com campos, já usa essas informações sem repetir.' },
        ]},
      { icon: 'F1', badge: 'in', title: 'Qualificação de Perfil — Fit Rápido', who: 'bot', variant: 'inbound-only',
        desc: 'Com a dor implícita no contato, confirma que o lead é o público do profissional. 2–3 perguntas objetivas.',
        bullets: [
          { text: '<strong>Perguntas de contexto:</strong> situação atual do lead relevante para o serviço do profissional.' },
          { text: '<strong>Descarte gentil:</strong> leads fora do perfil são encaminhados a outra indicação — sem deixar no vazio.' },
        ],
        qCards: [
          { label: 'Coach exemplo',    text: '"Você está buscando desenvolvimento pessoal ou profissional no momento?"' },
          { label: 'Personal exemplo', text: '"Você treina atualmente ou está começando do zero?"' },
        ]},
      { icon: 'DOR', badge: 'both', title: 'Refinamento da Dor + Contexto', who: 'bot',
        desc: 'Com fit confirmado, o agente aprofunda a dor para personalizar o acolhimento e preparar o briefing do profissional.',
        bullets: [
          { text: '<strong>Pergunta aberta:</strong> "Qual é seu principal desafio hoje em relação a X?" — resposta livre, sem menu.' },
          { text: '<strong>Registro da dor:</strong> a resposta compõe o briefing enviado ao profissional antes da sessão.' },
          { text: '<strong>Escuta ativa:</strong> o bot faz uma breve validação empática antes de avançar — não vai direto ao agendamento.' },
        ]},
      { icon: 'AQ', badge: 'both', title: 'Aquecimento — Ancoragem de Valor', who: 'bot',
        desc: 'Antes de mostrar a agenda, o bot cria expectativa positiva. Aumenta taxa de comparecimento e engajamento na sessão.',
        bullets: [
          { text: '<strong>Social proof:</strong> resultado de cliente com perfil similar ao lead, citado naturalmente.' },
          { text: '<strong>Preview da sessão:</strong> explica o que vai acontecer na consulta — reduz ansiedade e aumenta expectativa.' },
          { text: '<strong>Conexão dor → profissional:</strong> "Exatamente esse tipo de situação é o que [Nome] trabalha."' },
        ]},
      { icon: 'AG', badge: 'both', title: 'Agendamento Automático', who: 'bot',
        desc: 'Bot apresenta horários disponíveis e confirma o agendamento sem envolver o profissional.',
        bullets: [
          { text: '<strong>Calendário em tempo real:</strong> lê disponibilidade e apresenta opções (Google Calendar, Calendly).' },
          { text: '<strong>Confirmação dupla:</strong> WhatsApp + e-mail com detalhes da sessão.' },
          { text: '<strong>Lembretes anti-no-show:</strong> 24h e 2h antes da sessão.' },
          { text: '<strong>Briefing ao profissional:</strong> dor relatada + histórico da conversa enviados antes da sessão.' },
        ]},
      { icon: 'SS', badge: 'both', title: 'Sessão / Consulta com o Profissional', who: 'human', variant: 'human',
        desc: 'O profissional conduz com o lead já aquecido e contextualizado. Apresenta, diagnostica e pode fechar na mesma sessão.',
        bullets: [
          { text: '<strong>Registro de resultado:</strong> Fechou / Não fechou / Reagendar — ativa o fluxo de follow-up correspondente.' },
        ]},
      { icon: 'FU', badge: 'both', title: 'Follow-up Pós-Sessão', who: 'bot',
        desc: 'Fluxo baseado no resultado registrado pelo profissional.',
        bullets: [
          { text: '<strong>Escalada ao humano:</strong> resposta com alto interesse aciona notificação imediata ao profissional.' },
        ],
        tempCards: [
          { cls: 'done', label: '✓ Fechou',     desc: 'Onboarding imediato: boas-vindas, link de pagamento/contrato, próximos passos.' },
          { cls: 'warm', label: '💬 Não fechou', desc: 'Sequência 2–3 dias reforçando valor, removendo objeções levantadas na sessão.' },
          { cls: 'cold', label: '📅 Reagendar',  desc: 'Oferece nova data automaticamente. Mantém lead aquecido entre sessões.' },
        ]},
      { icon: 'PV', badge: 'both', title: 'Pós-Venda / Retenção', who: 'collab',
        desc: 'Gerencia a jornada do cliente ativo: agendamentos recorrentes, materiais pré-sessão, check-ins e recompra.',
        bullets: [
          { text: '<strong>Agendamento recorrente:</strong> bot gerencia próximas sessões automaticamente.' },
          { text: '<strong>Materiais pré-sessão:</strong> formulários ou tarefas enviados automaticamente antes de cada encontro.' },
          { text: '<strong>Renovação de pacote:</strong> ao fim do pacote, inicia fluxo de recontratação sem o profissional precisar agir.' },
        ]},
    ],
    flowOut: [
      { icon: 'OUT', badge: 'out', title: 'Prospecção Ativa — Perfil Presumido', who: 'bot', variant: 'outbound-start',
        desc: 'Contato iniciado pelo profissional. Tom pessoal e próximo, como se o próprio profissional estivesse mandando uma mensagem.',
        bullets: [
          { text: '<strong>Tom pessoal:</strong> "Oi [Nome], o [Profissional] me pediu para entrar em contato — ele viu seu perfil e achou que poderia te ajudar muito com..."' },
          { text: '<strong>Abertura por situação:</strong> menciona uma situação comum do público antes de fazer qualquer pergunta.' },
        ]},
      { icon: 'F2', badge: 'out', title: 'Investigação + Despertar de Dor', who: 'bot', variant: 'outbound-only',
        desc: 'Lead não veio até você — o bot precisa tocar na ferida primeiro. Pergunta aberta que convida o lead a refletir sobre o problema.',
        bullets: [
          { text: '<strong>Pergunta de escavação leve:</strong> não intrusiva, convida à reflexão sem parecer venda.' },
          { text: '<strong>Sem mencionar serviço ainda:</strong> foco em identificar se a dor existe antes de qualquer oferta.' },
        ],
        qCards: [
          { label: 'Coach',    text: '"Como você está se sentindo em relação ao equilíbrio entre trabalho e vida pessoal ultimamente?"' },
          { label: 'Personal', text: '"Você sente que sua rotina de treino está te levando para onde você quer chegar?"' },
        ]},
      { icon: 'F1', badge: 'out', title: 'Confirmação de Fit com a Dor Ativa', who: 'bot', variant: 'outbound-only',
        desc: 'Dor identificada. Confirma se o perfil do lead condiz com quem o profissional atende. No outbound, ocorre de forma fluida durante a conversa.',
        bullets: [
          { text: '<strong>Validação contextual:</strong> confirma aspectos do perfil de forma natural dentro do diálogo sobre o problema.' },
          { text: '<strong>Reposicionamento:</strong> se o fit não bater 100%, ajusta o ângulo da oferta antes de avançar.' },
        ]},
      { icon: 'DOR', badge: 'both', title: 'Aprofundamento de Dor + Contexto', who: 'bot',
        desc: 'No outbound, a dor foi despertada — aqui ela é aprofundada para montar o briefing do profissional. Mesma lógica do inbound a partir deste ponto.' },
      { icon: 'AQ', badge: 'both', title: 'Aquecimento — Ancoragem de Valor', who: 'bot',
        desc: 'Social proof, preview da sessão e conexão da dor com o trabalho do profissional. Especialmente crítico no outbound para aumentar a taxa de comparecimento.' },
      { icon: 'AG', badge: 'both', title: 'Agendamento Automático', who: 'bot',
        desc: 'Calendário em tempo real, confirmação dupla, lembretes e briefing ao profissional. O lembrete de 2h é especialmente importante para leads prospectados friamente.' },
      { icon: 'SS', badge: 'both', title: 'Sessão / Consulta com o Profissional', who: 'human', variant: 'human',
        desc: 'Profissional conduz a sessão com o lead aquecido. Registra o resultado ao final para acionar o fluxo correto de follow-up.' },
      { icon: 'FU', badge: 'both', title: 'Follow-up Pós-Sessão', who: 'bot',
        desc: 'Fluxo por resultado: fechou → onboarding; não fechou → nutrição; reagendar → nova data automática. No outbound, leads que não fecharam recebem reforço da dor despertada originalmente.' },
      { icon: 'PV', badge: 'both', title: 'Pós-Venda / Retenção', who: 'collab',
        desc: 'Agendamentos recorrentes, materiais pré-sessão, check-ins periódicos e fluxo de renovação automático ao fim do pacote.' },
    ],
  },
];

// ─── Componente de stage ─────────────────────────────────────

function StageCard({ stage, stageKey }: { stage: Stage; stageKey: string }) {
  const [open, setOpen] = useState(false);

  const iconStyle: React.CSSProperties = {
    width: 44, height: 44, borderRadius: '50%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 500,
    flexShrink: 0, position: 'relative', zIndex: 2,
    border: '1px solid', background: 'var(--o-bg)',
  };

  const variantIconStyle: React.CSSProperties =
    stage.variant === 'inbound-start' || stage.variant === 'inbound-only'
      ? { color: '#60c890', borderColor: 'rgba(96,200,144,0.45)', background: 'rgba(96,200,144,0.08)' }
      : stage.variant === 'outbound-start' || stage.variant === 'outbound-only'
      ? { color: '#e07060', borderColor: 'rgba(224,112,96,0.45)', background: 'rgba(224,112,96,0.08)' }
      : stage.variant === 'human'
      ? { color: '#ff9a60', borderColor: 'rgba(255,154,96,0.4)', background: 'rgba(255,154,96,0.08)' }
      : { color: 'var(--o-active)', borderColor: 'rgba(80,216,200,0.35)' };

  const cardBorderLeft =
    stage.variant === 'inbound-start' || stage.variant === 'inbound-only' ? '3px solid #60c890'
    : stage.variant === 'outbound-start' || stage.variant === 'outbound-only' ? '3px solid #e07060'
    : stage.variant === 'human' ? '3px solid #ff9a60'
    : undefined;

  const badgeStyle: React.CSSProperties =
    stage.badge === 'in'
      ? { background: 'rgba(96,200,144,0.1)', color: '#60c890', border: '1px solid rgba(96,200,144,0.3)' }
      : stage.badge === 'out'
      ? { background: 'rgba(224,112,96,0.1)', color: '#e07060', border: '1px solid rgba(224,112,96,0.3)' }
      : { background: 'rgba(255,255,255,0.05)', color: 'var(--o-sub)', border: '1px solid var(--o-b1)' };

  const badgeLabel = stage.badge === 'in' ? 'Inbound' : stage.badge === 'out' ? 'Outbound' : 'Ambos';

  const whoStyle: React.CSSProperties =
    stage.who === 'bot'    ? { background: 'rgba(96,176,255,0.1)', color: '#60b0ff' }
    : stage.who === 'human' ? { background: 'rgba(255,154,96,0.1)',  color: '#ff9a60' }
    : { background: 'rgba(200,255,120,0.1)', color: '#c8ff78' };
  const whoLabel = stage.who === 'bot' ? 'BOT' : stage.who === 'human' ? 'HUMANO' : 'BOT + HUMANO';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '44px 1fr', gap: 14, alignItems: 'start', marginBottom: 6 }}>
      {/* Icon */}
      <div style={{ ...iconStyle, ...variantIconStyle }}>{stage.icon}</div>

      {/* Card */}
      <div
        onClick={() => setOpen(v => !v)}
        style={{
          background: 'var(--o-surface)',
          border: `1px solid var(--o-b1)`,
          borderLeft: cardBorderLeft,
          borderRadius: 8,
          cursor: 'pointer',
          overflow: 'hidden',
        }}
      >
        {/* Top row */}
        <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', padding: '2px 8px', borderRadius: 2, flexShrink: 0, ...badgeStyle }}>
              {badgeLabel}
            </span>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--o-text)' }}>{stage.title}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, letterSpacing: 1.5, textTransform: 'uppercase', padding: '3px 10px', borderRadius: 2, ...whoStyle }}>
              {whoLabel}
            </span>
            <span style={{ color: 'var(--o-dim)', fontSize: 11, transition: 'transform 0.2s', display: 'inline-block', transform: open ? 'rotate(180deg)' : 'none' }}>▾</span>
          </div>
        </div>

        {/* Details */}
        {open && (
          <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--o-b1)', animation: 'o-fade-in 0.2s ease' }}>
            <p style={{ fontSize: 12.5, color: 'var(--o-sub)', fontWeight: 300, lineHeight: 1.75, margin: '14px 0' }}>
              {stage.desc}
            </p>

            {stage.bullets && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: stage.qCards || stage.tempCards ? 14 : 0 }}>
                {stage.bullets.map((b, i) => (
                  <div key={i} style={{ display: 'flex', gap: 10, fontSize: 12.5, lineHeight: 1.6, color: 'var(--o-text)' }}>
                    <span style={{ color: 'var(--o-dim)', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, flexShrink: 0, paddingTop: 2 }}>→</span>
                    <span dangerouslySetInnerHTML={{ __html: b.text }} />
                  </div>
                ))}
              </div>
            )}

            {stage.qCards && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginTop: 12 }}>
                {stage.qCards.map((q, i) => (
                  <div key={i} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--o-b1)', borderRadius: 6, padding: 12 }}>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>{q.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--o-sub)', lineHeight: 1.6, fontStyle: 'italic' }}>{q.text}</div>
                  </div>
                ))}
              </div>
            )}

            {stage.tempCards && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, marginTop: 12 }}>
                {stage.tempCards.map((t, i) => {
                  const tempColor = t.cls === 'hot' ? '#ff6060' : t.cls === 'warm' ? '#ffaa40' : t.cls === 'cold' ? '#6090ff' : '#60c890';
                  return (
                    <div key={i} style={{ border: '1px solid var(--o-b1)', borderRadius: 6, padding: 12, background: 'rgba(255,255,255,0.02)' }}>
                      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: tempColor, marginBottom: 8 }}>{t.label}</div>
                      <div style={{ fontSize: 12, color: 'var(--o-sub)', lineHeight: 1.6, fontWeight: 300 }}>{t.desc}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Página principal ────────────────────────────────────────

export default function TiposAgentes() {
  const [activeAgent, setActiveAgent] = useState<AgentId>('a1');
  const [journeys, setJourneys] = useState<Record<AgentId, Journey>>({ a1: 'in', a2: 'in', a3: 'in' });

  const agent = AGENTS.find(a => a.id === activeAgent)!;
  const journey = journeys[activeAgent];
  const stages = journey === 'in' ? agent.flowIn : agent.flowOut;

  const agentColor: Record<AgentId, string> = {
    a1: '#f0c060',
    a2: '#50d8c8',
    a3: '#b87fff',
  };
  const color = agentColor[activeAgent];

  return (
    <OrionShell>
      {/* Topbar */}
      <header className="o-topbar">
        <div className="font-mono-orion" style={{ fontSize: 11, letterSpacing: 3, textTransform: 'uppercase', color: 'var(--o-sub)', paddingRight: 24, borderRight: '1px solid var(--o-b1)', marginRight: 20, whiteSpace: 'nowrap' }}>
          Orion CRM
        </div>
        <div className="font-mono-orion" style={{ fontSize: 10, letterSpacing: '1.5px', color: 'var(--o-dim)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>Identidade do Agente</span>
          <span>›</span>
          <span style={{ color: 'var(--o-text)' }}>Tipos de Agentes</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Link to="/ai-profile" className="o-btn" style={{ fontSize: 8 }}>← Configuração</Link>
        </div>
      </header>

      {/* Agent tabs */}
      <nav style={{ borderBottom: '1px solid var(--o-b1)', display: 'flex', padding: '0 48px', background: 'rgba(13,14,20,0.95)', backdropFilter: 'blur(24px)', position: 'sticky', top: 0, zIndex: 100 }}>
        {AGENTS.map(a => (
          <button
            key={a.id}
            onClick={() => setActiveAgent(a.id)}
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11, letterSpacing: 1.5, textTransform: 'uppercase',
              padding: '18px 28px', border: 'none', background: 'transparent',
              color: activeAgent === a.id ? agentColor[a.id] : 'var(--o-dim)',
              borderBottom: `2px solid ${activeAgent === a.id ? agentColor[a.id] : 'transparent'}`,
              cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.2s',
            }}
          >
            {a.chip}
          </button>
        ))}
      </nav>

      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '48px 48px 80px' }}>

        {/* Agent hero */}
        <div style={{ marginBottom: 48, paddingBottom: 36, borderBottom: '1px solid var(--o-b1)', display: 'grid', gridTemplateColumns: '1fr auto', gap: 32 }}>
          <div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, letterSpacing: 3, textTransform: 'uppercase', padding: '4px 12px', borderRadius: 3, marginBottom: 16, display: 'inline-block', color, background: `${color}18`, border: `1px solid ${color}66` }}>
              {agent.chip}
            </div>
            <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: 34, fontWeight: 400, lineHeight: 1.15, marginBottom: 12, color: 'var(--o-text)' }}>
              {agent.title}<br /><em style={{ fontStyle: 'italic', color: 'var(--o-sub)' }}>{agent.subtitle}</em>
            </h2>
            <p style={{ fontSize: 13.5, color: 'var(--o-sub)', lineHeight: 1.75, fontWeight: 300, maxWidth: 520 }}>{agent.desc}</p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
            {agent.useCases.map(uc => (
              <span key={uc} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--o-dim)', padding: '4px 12px', border: '1px solid var(--o-b1)', borderRadius: 3, whiteSpace: 'nowrap' }}>{uc}</span>
            ))}
          </div>
        </div>

        {/* Journey toggle */}
        <div style={{ display: 'flex', border: '1px solid var(--o-b1)', borderRadius: 6, overflow: 'hidden', marginBottom: 20, width: 'fit-content' }}>
          {(['in', 'out'] as Journey[]).map(j => (
            <button
              key={j}
              onClick={() => setJourneys(prev => ({ ...prev, [activeAgent]: j }))}
              style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: 11, letterSpacing: 1.5, textTransform: 'uppercase',
                padding: '12px 24px', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10,
                borderRight: j === 'in' ? '1px solid var(--o-b1)' : undefined,
                background: journey === j ? (j === 'in' ? 'rgba(96,200,144,0.1)' : 'rgba(224,112,96,0.1)') : 'transparent',
                color: journey === j ? (j === 'in' ? '#60c890' : '#e07060') : 'var(--o-dim)',
                transition: 'all 0.2s',
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: j === 'in' ? '#60c890' : '#e07060', display: 'inline-block' }} />
              {j === 'in' ? 'Inbound' : 'Outbound'}
            </button>
          ))}
        </div>

        {/* Journey description */}
        <div
          style={{
            background: 'var(--o-surface)',
            border: `1px solid var(--o-b1)`,
            borderLeft: `3px solid ${journey === 'in' ? '#60c890' : '#e07060'}`,
            borderRadius: 6, padding: '16px 20px', marginBottom: 32,
            fontSize: 13, fontWeight: 300, lineHeight: 1.7, color: 'var(--o-sub)',
          }}
          dangerouslySetInnerHTML={{ __html: `<strong style="color:var(--o-text)">${journey === 'in' ? 'Cenário Inbound:</strong> ' + agent.descIn : 'Cenário Outbound:</strong> ' + agent.descOut}` }}
        />

        {/* Pipeline */}
        <div style={{ position: 'relative' }}>
          {/* Vertical line */}
          <div style={{ position: 'absolute', left: 21, top: 22, bottom: 22, width: 1, background: 'var(--o-b1)', pointerEvents: 'none' }} />

          {stages.map((stage, i) => (
            <div key={`${activeAgent}-${journey}-${i}`}>
              <StageCard stage={stage} stageKey={`${activeAgent}-${journey}-${i}`} />
              {i < stages.length - 1 && (
                <div style={{ display: 'grid', gridTemplateColumns: '44px 1fr', gap: 14, marginBottom: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 24 }}>
                    <span style={{ fontSize: 12, color: 'var(--o-dim)', background: 'var(--o-bg)', padding: '0 2px', zIndex: 2, position: 'relative' }}>↓</span>
                  </div>
                  <div />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, marginTop: 48, paddingTop: 28, borderTop: '1px solid var(--o-b1)', paddingLeft: 58 }}>
          {[
            { color: '#60c890', label: 'Início Inbound' },
            { color: '#e07060', label: 'Início Outbound' },
            { color: '#60b0ff', label: 'Executado pelo BOT' },
            { color: '#ff9a60', label: 'Executado pelo HUMANO' },
            { color: '#c8ff78', label: 'Colaborativo' },
          ].map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--o-dim)', letterSpacing: 1 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: item.color, display: 'inline-block', flexShrink: 0 }} />
              {item.label}
            </div>
          ))}
        </div>

      </div>
    </OrionShell>
  );
}
