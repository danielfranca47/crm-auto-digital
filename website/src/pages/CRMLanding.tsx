import { useState } from 'react';
import {
  ArrowRight, Bot, Zap, Clock, Users, TrendingUp,
  CheckCircle, MessageSquare, Phone, ChevronDown, Star,
  BarChart2, BellRing, Volume2, ImageIcon, Plug,
  Play, Check, X, ChevronRight, ArrowUp, Mail, Kanban,
} from 'lucide-react';

/* ─── Data ──────────────────────────────────────────────────── */

const sectors = [
  {
    label: 'Infoprodutos', icon: '📚',
    description:
      'A Lara recupera alunos que abandonaram o checkout, qualifica leads de cursos e envia provas sociais automaticamente. Ela conduz o lead do anúncio ao pagamento — sem você tocar.',
  },
  {
    label: 'Serviços', icon: '🛠️',
    description:
      'A Lara agenda consultas, confirma horários e faz follow-up de clientes que pediram orçamento mas sumiram. Ela nunca deixa um agendamento escapar.',
  },
  {
    label: 'E-commerce', icon: '🛒',
    description:
      'A Lara recupera carrinhos abandonados, envia rastreamento de pedido e responde dúvidas com fotos e vídeos do produto — tudo no automático.',
  },
  {
    label: 'Saúde & Estética', icon: '💆',
    description:
      'Triagem, agendamento, confirmação e follow-up pós-consulta. A Lara reduz faltas e mantém sua agenda sempre cheia — sem precisar de recepcionista.',
  },
  {
    label: 'Imóveis', icon: '🏠',
    description:
      'A Lara qualifica compradores com perguntas estratégicas, envia fotos automaticamente e agenda visitas — entregando apenas leads quentes pro corretor fechar.',
  },
  {
    label: 'Educação', icon: '🎓',
    description:
      'Matrículas, cobranças, dúvidas de alunos e lembretes de aula. A Lara atua como assistente acadêmica disponível 24h, sem custo de equipe.',
  },
];

const steps = [
  { num: '01', title: 'Conecte seu WhatsApp', desc: 'Via QR Code em segundos. Sem código, sem técnico.' },
  { num: '02', title: 'Apresente seu negócio à Lara', desc: 'Ela aprende sobre sua empresa, seus produtos e como você gosta de atender.' },
  { num: '03', title: 'Leads entram no funil', desc: 'Importe contatos ou receba leads direto do WhatsApp — a Lara assume na hora.' },
  { num: '04', title: 'A Lara qualifica e conversa', desc: 'Faz as perguntas certas, identifica intenção de compra e avança o lead no pipeline.' },
  { num: '05', title: 'A Lara faz o follow-up', desc: 'Quem não respondeu? A Lara retoma no momento certo, sem parecer chato.' },
  { num: '06', title: 'Você fecha as vendas quentes', desc: 'Receba apenas os leads prontos para fechar. A Lara já fez o trabalho pesado.' },
];

const features = [
  { Icon: MessageSquare, title: 'Atendimento 24/7', desc: 'A Lara responde dúvidas, status e suporte enquanto você dorme — sem perder nenhum lead.' },
  { Icon: Kanban,        title: 'CRM com Pipeline Kanban', desc: 'Visualize onde está cada lead no funil. Mova, filtre e acompanhe em tempo real.' },
  { Icon: BellRing,      title: 'Follow-up que nunca esquece', desc: 'A Lara retoma conversas paradas no momento certo, sem parecer spam.' },
  { Icon: Users,         title: 'Qualificação de Leads', desc: 'A Lara identifica intenção de compra e entrega apenas oportunidades quentes.' },
  { Icon: Volume2,       title: 'Áudio na Voz da Lara', desc: 'Grave uma vez. A Lara envia como mensagem de voz nova para cada cliente.' },
  { Icon: ImageIcon,     title: 'Imagens e Vídeos', desc: 'A Lara envia catálogos, provas sociais e materiais de venda automaticamente.' },
  { Icon: BarChart2,     title: 'Modos de Venda', desc: 'Consultivo, agendamento ou direto — configure o jeito que a Lara deve vender.' },
  { Icon: Plug,          title: 'Integrações via API', desc: 'Hotmart, Kiwify e mais — a Lara conectada com as ferramentas que você já usa. (Em breve)' },
];

const differentials = [
  {
    Icon: Kanban, tag: 'Exclusivo', title: 'CRM nativo — tudo num lugar só',
    desc: 'Todos os seus leads organizados em um pipeline visual. Veja em qual etapa cada cliente está, o histórico completo da conversa e qual é a próxima ação — sem abrir outra ferramenta.',
  },
  {
    Icon: BellRing, tag: 'Diferencial', title: 'A Lara nunca esquece um follow-up',
    desc: 'Se o lead não respondeu, a Lara retoma automaticamente no melhor momento. Ela recupera vendas que pareciam perdidas — sem você fazer absolutamente nada.',
  },
  {
    Icon: Volume2, tag: 'Único', title: 'Áudio como se fosse na hora',
    desc: 'Grave seu áudio uma vez. A Lara envia para cada cliente como mensagem de voz nova, humanizando o atendimento. Voz clonada em tempo real disponível no plano Growth.',
  },
  {
    Icon: BarChart2, tag: 'Flexível', title: 'A Lara vende do seu jeito',
    desc: 'Consultivo (aprofunda qualificação), agendamento (foca em marcar reunião) ou direto (vai reto ao fechamento). Você define a estratégia, a Lara executa.',
  },
];

const testimonials = [
  {
    name: 'Fernanda Costa', role: 'Proprietária de Clínica Estética', stars: 5,
    text: 'A Lara responde, agenda e faz follow-up sozinha. Antes eu perdia leads por demorar a responder — hoje minha taxa de fechamento dobrou em 45 dias.',
  },
  {
    name: 'Ricardo Mendes', role: 'CEO de E-commerce', stars: 5,
    text: 'O CRM embutido mudou tudo. Antes meus leads ficavam perdidos no WhatsApp. Agora a Lara organiza tudo no pipeline e eu sei exatamente o que está acontecendo.',
  },
  {
    name: 'Camila Rocha', role: 'Personal Trainer', stars: 5,
    text: 'A Lara recuperou 3 alunos que eu tinha "perdido". Ela fez o follow-up no momento certo — foram vendas que nunca teriam acontecido sem ela.',
  },
];

const plans = [
  {
    name: 'Starter', price: '197', highlight: false,
    features: [
      '1.000 conversas/mês',
      '1 WhatsApp conectado',
      'CRM com pipeline Kanban',
      'Envio de áudio personalizado',
      'Envio de imagens e vídeos',
      'Suporte por chat',
    ],
    cta: 'Conhecer a Lara',
  },
  {
    name: 'Growth', price: '397', highlight: true, badge: 'MAIS POPULAR',
    features: [
      'Conversas ilimitadas',
      '1 WhatsApp conectado',
      'CRM com pipeline Kanban',
      'Follow-up automático',
      'Envio de áudio personalizado',
      'Envio de imagens e vídeos',
      '✦ Voz clonada em tempo real',
      'Prospecção automática',
      'Suporte prioritário',
    ],
    cta: 'Conhecer a Lara',
  },
  {
    name: 'Scale', price: '997', highlight: false,
    features: [
      'Conversas ilimitadas',
      'Até 3 WhatsApps',
      'Multi-empresa',
      'CRM completo + relatórios',
      'Voz clonada em tempo real',
      'Prospecção automática avançada',
      'Integrações via API (em breve)',
      'Gestor de conta dedicado',
    ],
    cta: 'Falar com consultor',
  },
];

const comparisonRows = [
  { label: 'Responde no WhatsApp 24/7',        ours: true,  theirs: true  },
  { label: 'CRM nativo embutido',              ours: true,  theirs: false },
  { label: 'Follow-up automático de inativos', ours: true,  theirs: false },
  { label: 'Recuperação de vendas perdidas',   ours: true,  theirs: false },
  { label: 'Pipeline visual de leads',         ours: true,  theirs: false },
  { label: 'Envio de áudio personalizado',     ours: true,  theirs: false },
  { label: 'Envio de imagens e vídeos',        ours: true,  theirs: false },
  { label: 'Múltiplos modos de venda',         ours: true,  theirs: false },
  { label: 'Prospecção automática',            ours: true,  theirs: false },
];

const faqs = [
  { q: 'A Lara precisa de WhatsApp Business API?', a: 'Não obrigatoriamente. Você começa com o WhatsApp Business comum via QR Code. A API oficial fica disponível para volumes maiores.' },
  { q: 'Quanto tempo para a Lara estar ativa?', a: 'Em menos de 30 minutos a Lara já está atendendo. Conecte o WhatsApp, apresente seu negócio a ela e ative.' },
  { q: 'A Lara soa natural ou parece robô?', a: 'A Lara é configurada com a personalidade da sua marca. Você controla o tom, as respostas e o fluxo — ela soa como alguém da sua equipe.' },
  { q: 'O que acontece quando o cliente precisa de humano?', a: 'A Lara transfere automaticamente com o contexto completo da conversa. Quem assumir já sabe tudo que foi discutido.' },
  { q: 'A Lara funciona para qualquer tipo de negócio?', a: 'Sim. Infoprodutos, serviços, e-commerce, saúde, imóveis, educação — a Lara se adapta ao seu setor.' },
  { q: 'Posso cancelar quando quiser?', a: 'Sim. Sem fidelidade, sem multa. Cancele com 1 clique a qualquer momento.' },
];

const waveformHeights = [3, 5, 7, 4, 6, 8, 3, 5, 7, 4, 6, 3, 5, 8, 4, 6, 5, 3];

/* ─── Component ─────────────────────────────────────────────── */

export default function CRMLanding() {
  const [activeSector, setActiveSector] = useState(0);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  return (
    <div className="min-h-screen bg-background text-foreground font-montserrat">

      {/* ── NAVBAR ── */}
      <header className="fixed top-0 inset-x-0 z-50 bg-background/95 backdrop-blur-md border-b border-border">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <a href="#home" className="flex items-center">
              <div className="w-10 h-10 rounded-xl accent-gradient flex items-center justify-center mr-3">
                <div className="w-6 h-6 bg-background rounded-sm" />
              </div>
              <span className="text-xl font-bold">DigitalPro</span>
            </a>

            <nav className="hidden md:flex items-center space-x-7 text-sm">
              <a href="#funcionalidades" className="text-muted-foreground hover:text-foreground transition-smooth">Funcionalidades</a>
              <a href="#como-funciona"   className="text-muted-foreground hover:text-foreground transition-smooth">Como funciona</a>
              <a href="#planos"          className="text-muted-foreground hover:text-foreground transition-smooth">Planos</a>
              <a href="#faq"             className="text-muted-foreground hover:text-foreground transition-smooth">FAQ</a>
            </nav>

            <div className="flex items-center gap-3">
              <a href="#" className="hidden md:inline text-sm text-muted-foreground hover:text-foreground transition-smooth">Entrar</a>
              <a href="#planos" className="btn-hero text-sm px-5 py-2.5">Começar grátis →</a>
            </div>
          </div>
        </div>
      </header>

      {/* ── HERO ── */}
      <section
        id="home"
        className="relative min-h-screen flex items-center pt-16 overflow-hidden"
        style={{
          backgroundImage: 'url(/hero-mascot.jpeg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center right',
          backgroundRepeat: 'no-repeat',
        }}
      >
        {/* overlay gradiente — escurece da esquerda para a direita para o texto ser legível */}
        <div className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(to right, #0D0A17 30%, rgba(13,10,23,0.85) 55%, rgba(13,10,23,0.2) 100%)',
          }} />
        {/* overlay gradiente — escurece base da secção */}
        <div className="absolute bottom-0 inset-x-0 h-32 pointer-events-none"
          style={{ background: 'linear-gradient(to top, #0D0A17, transparent)' }} />

        <div className="container mx-auto px-4 lg:px-8 py-20 relative z-10">
          <div className="max-w-xl">

            {/* badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-medium mb-7 animate-fade-in"
              style={{ background: 'rgba(77,212,255,0.1)', borderColor: 'rgba(77,212,255,0.3)', color: '#4DD4FF' }}>
              <Bot className="w-4 h-4" />
              Conheça a Lara — IA + CRM + Follow-up
            </div>

            {/* H1 */}
            <h1 className="text-hero mb-6 animate-fade-in animate-delay-100">
              A Lara cuida dos seus leads{' '}
              <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
                enquanto você faz o resto.
              </span>
            </h1>

            {/* sub */}
            <p className="text-xl text-muted-foreground mb-10 max-w-lg leading-relaxed animate-fade-in animate-delay-200">
              A Lara atende, qualifica e faz follow-up pelo WhatsApp — com CRM nativo e recuperação de vendas. Tudo no mesmo lugar, sem ferramenta extra.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-4 mb-14 animate-fade-in animate-delay-300">
              <a href="#planos" className="btn-hero flex items-center justify-center gap-2">
                Conhecer a Lara <ArrowRight className="w-4 h-4" />
              </a>
              <a href="#como-funciona"
                className="flex items-center justify-center gap-2 px-8 py-4 rounded-xl font-semibold border border-white/20 hover:bg-white/10 transition-smooth">
                <Play className="w-4 h-4" /> Ver como funciona
              </a>
            </div>

            {/* stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 animate-fade-in animate-delay-400">
              {[
                { value: '10k+', label: 'Leads qualificados' },
                { value: '94%',  label: 'Taxa de resposta'   },
                { value: '3×',   label: 'Mais conversões'    },
                { value: '24/7', label: 'Atendimento ativo'  },
              ].map(s => (
                <div key={s.label}>
                  <div className="text-2xl font-extrabold text-accent">{s.value}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* scroll hint */}
        <div className="absolute bottom-8 inset-x-0 flex justify-center animate-bounce text-muted-foreground z-10">
          <ChevronDown className="w-5 h-5" />
        </div>
      </section>

      {/* ── LOGO BAR ── */}
      <section className="py-8 border-y border-border bg-card/40">
        <div className="container mx-auto px-4 lg:px-8">
          <p className="text-center text-xs text-muted-foreground mb-5 uppercase tracking-widest font-semibold">
            + DE 10.000 EMPRESAS JÁ TÊM UMA LARA ATENDENDO PARA ELAS
          </p>
          <div className="flex flex-wrap justify-center items-center gap-6 opacity-50">
            {['Infoprodutos', 'E-commerce', 'Saúde', 'Imóveis', 'Educação', 'Serviços', 'Beleza'].map(s => (
              <span key={s}
                className="text-xs font-bold text-muted-foreground px-5 py-2 rounded-full border border-border uppercase tracking-wide">
                {s}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── SECTOR TABS ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Qualquer setor</span>
            <h2 className="text-heading mt-2">Se você vende pelo WhatsApp, a Lara trabalha por você</h2>
          </div>

          <div className="flex flex-wrap justify-center gap-2 mb-10">
            {sectors.map((s, i) => (
              <button key={s.label} onClick={() => setActiveSector(i)}
                className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-smooth border"
                style={activeSector === i
                  ? { background: 'rgba(77,212,255,0.15)', borderColor: '#4DD4FF', color: '#4DD4FF' }
                  : { borderColor: 'hsl(var(--border))', color: 'hsl(var(--muted-foreground))' }}>
                <span>{s.icon}</span> {s.label}
              </button>
            ))}
          </div>

          <div className="portfolio-card p-10 text-center max-w-2xl mx-auto">
            <div className="text-5xl mb-4">{sectors[activeSector].icon}</div>
            <h3 className="text-xl font-bold mb-3">{sectors[activeSector].label}</h3>
            <p className="text-muted-foreground leading-relaxed">{sectors[activeSector].description}</p>
            <a href="#planos" className="btn-hero inline-flex items-center gap-2 mt-7 text-sm px-6 py-3">
              Quero automatizar <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section id="como-funciona" className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Simples assim</span>
            <h2 className="text-heading mt-2">Do primeiro contato ao fechamento — a Lara no comando</h2>
            <p className="text-muted-foreground mt-3">Configure uma vez. A Lara trabalha para sempre.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {steps.map((step, i) => (
              <div key={step.num} className="portfolio-card relative">
                <div className="text-5xl font-extrabold mb-4 select-none leading-none"
                  style={{ color: '#4DD4FF', opacity: 0.25 }}>
                  {step.num}
                </div>
                <h3 className="text-base font-bold mb-2">{step.title}</h3>
                <p className="text-muted-foreground text-sm leading-relaxed">{step.desc}</p>
                {i < steps.length - 1 && (
                  <ChevronRight className="absolute -right-3 top-1/2 -translate-y-1/2 text-accent hidden lg:block w-5 h-5" />
                )}
              </div>
            ))}
          </div>

          <div className="text-center mt-10">
            <a href="#planos" className="btn-hero inline-flex items-center gap-2">
              Automatizar meu WhatsApp agora <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </section>

      {/* ── FEATURES GRID ── */}
      <section id="funcionalidades" className="py-20 px-4">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">⚡ O que a Lara faz</span>
            <h2 className="text-heading mt-2">Tudo que a Lara faz pelo seu negócio</h2>
            <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
              A Lara atende, vende e acompanha leads 24/7 — enquanto você foca no que realmente importa.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map(({ Icon, title, desc }) => (
              <div key={title} className="portfolio-card text-center">
                <div className="w-14 h-14 rounded-2xl accent-gradient flex items-center justify-center mx-auto mb-4 shadow-hero">
                  <Icon className="w-6 h-6 text-accent-foreground" />
                </div>
                <h3 className="font-bold mb-2 text-sm">{title}</h3>
                <p className="text-muted-foreground text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── DIFFERENTIALS ── */}
      <section className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">O diferencial</span>
            <h2 className="text-heading mt-2">A Lara não é só um chatbot. É sua melhor vendedora.</h2>
            <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
              Outros bots respondem mensagens. A Lara gerencia o processo de venda de ponta a ponta — e nunca esquece um follow-up.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {differentials.map(({ Icon, tag, title, desc }) => (
              <div key={title} className="portfolio-card flex gap-5">
                <div className="w-12 h-12 rounded-xl accent-gradient flex items-center justify-center flex-shrink-0 mt-0.5 shadow-hero">
                  <Icon className="w-5 h-5 text-accent-foreground" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-bold">{title}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                      style={{ background: 'rgba(77,212,255,0.15)', color: '#4DD4FF' }}>
                      {tag}
                    </span>
                  </div>
                  <p className="text-muted-foreground text-sm leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="text-center mt-10">
            <a href="#planos" className="btn-hero inline-flex items-center gap-2">
              Quero testar grátis <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </section>

      {/* ── AUDIO SECTION ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-4xl">
          <div className="portfolio-card p-10 text-center relative overflow-hidden">
            <div className="absolute inset-0 pointer-events-none"
              style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(77,212,255,0.06), transparent 70%)' }} />

            <div className="relative">
              <span className="text-accent text-sm font-semibold uppercase tracking-widest">✦ A Voz da Lara</span>
              <h2 className="text-heading mt-3 mb-4">
                A Lara fala com cada cliente{' '}
                <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
                  como se fosse na hora.
                </span>
              </h2>
              <p className="text-muted-foreground max-w-xl mx-auto mb-10 leading-relaxed">
                Grave seu áudio uma vez. A Lara envia para cada cliente como mensagem de voz nova, no momento certo da conversa — humanizando o atendimento sem você precisar estar lá.
              </p>

              {/* audio mock */}
              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                <div className="portfolio-card px-6 py-4 flex items-center gap-3 w-full sm:w-auto">
                  <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
                    <Volume2 className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div className="text-left">
                    <div className="text-xs text-muted-foreground mb-1">Áudio gravado pelo você</div>
                    <div className="flex gap-px items-end" style={{ height: 24 }}>
                      {waveformHeights.map((h, i) => (
                        <div key={i} className="w-1 rounded-full bg-muted-foreground opacity-50"
                          style={{ height: `${h * 3}px` }} />
                      ))}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">01:24</div>
                  </div>
                </div>

                <ArrowRight className="w-6 h-6 text-accent hidden sm:block flex-shrink-0" />

                <div className="portfolio-card px-6 py-4 flex items-center gap-3 w-full sm:w-auto border"
                  style={{ borderColor: 'rgba(77,212,255,0.4)' }}>
                  <div className="w-10 h-10 rounded-full accent-gradient flex items-center justify-center flex-shrink-0">
                    <Volume2 className="w-4 h-4 text-accent-foreground" />
                  </div>
                  <div className="text-left">
                    <div className="text-xs mb-1" style={{ color: '#4DD4FF' }}>Enviado ao cliente</div>
                    <div className="flex gap-px items-end" style={{ height: 24 }}>
                      {waveformHeights.map((h, i) => (
                        <div key={i} className="w-1 rounded-full"
                          style={{ height: `${h * 3}px`, background: '#4DD4FF' }} />
                      ))}
                    </div>
                    <div className="text-xs mt-1" style={{ color: '#4DD4FF' }}>01:24 ✓✓</div>
                  </div>
                </div>
              </div>

              <p className="text-xs text-muted-foreground mt-8">
                ✦ Voz clonada da Lara em tempo real disponível a partir do{' '}
                <strong style={{ color: '#4DD4FF' }}>Lara Growth</strong>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── COMPARISON TABLE ── */}
      <section className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-3xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Comparativo</span>
            <h2 className="text-heading mt-2">Por que somos diferentes</h2>
          </div>

          <div className="portfolio-card overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-6 py-4 text-muted-foreground font-medium">Funcionalidade</th>
                  <th className="px-6 py-4 text-center">
                    <span className="font-bold text-accent">Lara</span>
                  </th>
                  <th className="px-6 py-4 text-center text-muted-foreground">Bot genérico</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map(({ label, ours, theirs }, i) => (
                  <tr key={label} className={i % 2 === 0 ? 'bg-muted/10' : ''}>
                    <td className="px-6 py-3">{label}</td>
                    <td className="px-6 py-3 text-center">
                      {ours
                        ? <Check className="w-4 h-4 text-accent inline" />
                        : <X    className="w-4 h-4 text-destructive inline" />}
                    </td>
                    <td className="px-6 py-3 text-center">
                      {theirs
                        ? <Check className="w-4 h-4 text-muted-foreground inline" />
                        : <X    className="w-4 h-4 text-destructive inline" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── SUPPORT ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Suporte completo</span>
            <h2 className="text-heading mt-2">A Lara não vem sozinha — você tem suporte real</h2>
            <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
              Da primeira configuração ao dia a dia, tem alguém do lado pra te ajudar a tirar o máximo da Lara.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon: Zap,           title: 'Onboarding guiado',     desc: 'Reunião de boas-vindas para configurar seus primeiros fluxos.' },
              { icon: Clock,         title: 'Suporte diário ao vivo', desc: 'Sessão diária às 15h para tirar dúvidas e ver demos rápidas.' },
              { icon: MessageSquare, title: 'Chat na plataforma',     desc: 'Atendimento direto no produto, sem sair do seu fluxo de trabalho.' },
              { icon: TrendingUp,    title: 'Base de conhecimento',   desc: 'Aulas práticas de todas as áreas do produto, do básico ao avançado.' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="portfolio-card text-center">
                <div className="w-14 h-14 rounded-2xl accent-gradient flex items-center justify-center mx-auto mb-4 shadow-hero">
                  <Icon className="w-6 h-6 text-accent-foreground" />
                </div>
                <h3 className="font-bold mb-2 text-sm">{title}</h3>
                <p className="text-muted-foreground text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TESTIMONIALS ── */}
      <section className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">✦ Prova Social</span>
            <h2 className="text-heading mt-2">O que dizem quem já tem a Lara</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {testimonials.map(t => (
              <div key={t.name} className="portfolio-card flex flex-col">
                <div className="flex gap-0.5 mb-4">
                  {Array.from({ length: t.stars }).map((_, i) => (
                    <Star key={i} className="w-4 h-4 fill-current text-accent" />
                  ))}
                </div>
                <p className="text-muted-foreground text-sm leading-relaxed flex-1 italic">"{t.text}"</p>
                <div className="flex items-center gap-3 mt-5 pt-5 border-t border-border">
                  <div className="w-9 h-9 rounded-full accent-gradient flex items-center justify-center text-accent-foreground font-bold text-sm flex-shrink-0">
                    {t.name.charAt(0)}
                  </div>
                  <div>
                    <div className="font-semibold text-sm">{t.name}</div>
                    <div className="text-xs text-muted-foreground">{t.role}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── PLANS ── */}
      <section id="planos" className="py-20 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">✦ Planos da Lara</span>
            <h2 className="text-heading mt-2">Escolha o plano e a Lara começa hoje</h2>
            <p className="text-muted-foreground mt-3">Sem fidelidade. Cancele quando quiser.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map(plan => (
              <div key={plan.name}
                className={`portfolio-card flex flex-col relative ${plan.highlight ? 'ring-2' : ''}`}
                style={plan.highlight ? { '--tw-ring-color': '#4DD4FF' } as React.CSSProperties : {}}>
                {plan.badge && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap"
                    style={{ background: '#4DD4FF', color: '#0D0A17' }}>
                    {plan.badge}
                  </div>
                )}

                <div className="mb-6">
                  <h3 className="text-lg font-bold mb-1">{plan.name}</h3>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-extrabold text-accent">R${plan.price}</span>
                    <span className="text-muted-foreground text-sm">/mês</span>
                  </div>
                </div>

                <ul className="space-y-3 flex-1 mb-8">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <Check className="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
                      <span className={f.startsWith('✦') ? 'font-medium' : 'text-muted-foreground'}
                        style={f.startsWith('✦') ? { color: '#4DD4FF' } : {}}>
                        {f}
                      </span>
                    </li>
                  ))}
                </ul>

                <a href="#"
                  className={`text-center text-sm ${plan.highlight ? 'btn-hero' : 'btn-primary'}`}>
                  {plan.cta}
                </a>
                <p className="text-xs text-muted-foreground text-center mt-3">✓ Sem fidelidade • Cancele quando quiser</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section id="faq" className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-3xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Dúvidas frequentes</span>
            <h2 className="text-heading mt-2">FAQ</h2>
          </div>

          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <div key={i} className="portfolio-card cursor-pointer"
                onClick={() => setActiveFaq(activeFaq === i ? null : i)}>
                <div className="flex items-center justify-between gap-4">
                  <span className="font-semibold text-sm">{faq.q}</span>
                  <ChevronDown
                    className="w-4 h-4 text-accent flex-shrink-0 transition-smooth"
                    style={{ transform: activeFaq === i ? 'rotate(180deg)' : 'rotate(0deg)' }} />
                </div>
                {activeFaq === i && (
                  <p className="text-muted-foreground text-sm mt-3 leading-relaxed">{faq.a}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section className="py-28 px-4 hero-gradient relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(77,212,255,0.08), transparent 70%)' }} />

        <div className="container mx-auto max-w-3xl text-center relative">
          <h2 className="text-heading mb-4">
            O seu concorrente já está{' '}
            <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
              automatizando o WhatsApp.
            </span>
          </h2>
          <p className="text-muted-foreground text-lg mb-10 max-w-xl mx-auto leading-relaxed">
            A Lara atende quando você não pode, faz follow-up quando você esquece e recupera vendas que você daria como perdidas. Comece hoje.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="#planos" className="btn-hero flex items-center justify-center gap-2 text-lg px-10 py-5">
              Conhecer a Lara agora <ArrowRight className="w-5 h-5" />
            </a>
            <a href="#" className="flex items-center justify-center gap-2 px-8 py-5 rounded-xl font-semibold border border-white/20 hover:bg-white/10 transition-smooth">
              <MessageSquare className="w-4 h-4" /> Falar no WhatsApp
            </a>
          </div>
          <p className="text-muted-foreground text-sm mt-6 opacity-70">
            ✓ Sem cartão de crédito &nbsp;·&nbsp; ✓ Sem fidelidade &nbsp;·&nbsp; ✓ Suporte incluído
          </p>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="bg-primary text-primary-foreground py-16">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mb-12">
            {/* brand */}
            <div>
              <div className="flex items-center mb-4">
                <div className="w-10 h-10 rounded-xl accent-gradient flex items-center justify-center mr-3">
                  <div className="w-6 h-6 bg-primary rounded-sm" />
                </div>
                <span className="text-xl font-bold">DigitalPro</span>
              </div>
              <p className="text-primary-foreground/70 text-sm leading-relaxed max-w-xs">
                A Lara é a IA da DigitalPro que atende, qualifica e faz follow-up pelo WhatsApp — para quem quer vender mais sem depender de uma equipe grande.
              </p>
            </div>

            {/* links */}
            <div>
              <h4 className="font-semibold mb-4">Produto</h4>
              <ul className="space-y-2 text-sm text-primary-foreground/70">
                {['Funcionalidades', 'Planos', 'FAQ', 'Blog'].map(l => (
                  <li key={l}><a href="#" className="hover:text-accent transition-smooth">{l}</a></li>
                ))}
              </ul>
            </div>

            {/* contact */}
            <div>
              <h4 className="font-semibold mb-4">Contato</h4>
              <div className="space-y-2 text-sm text-primary-foreground/70">
                <div className="flex items-center gap-2"><Mail  className="w-4 h-4 text-accent" /> contato@digitalpro.com</div>
                <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-accent" /> +55 11 9 9999-9999</div>
              </div>
            </div>
          </div>

          <div className="border-t border-primary-foreground/20 pt-6 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-primary-foreground/60">© 2025 DigitalPro. Todos os direitos reservados.</p>
            <div className="flex items-center gap-6 text-sm text-primary-foreground/60">
              <a href="#" className="hover:text-accent transition-smooth">Privacidade</a>
              <a href="#" className="hover:text-accent transition-smooth">Termos</a>
              <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                className="w-8 h-8 rounded-full bg-accent text-accent-foreground flex items-center justify-center hover:scale-110 transition-bounce">
                <ArrowUp className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}
