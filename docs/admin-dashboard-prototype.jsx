import { useState, useEffect, useRef } from "react";

const FONT_LINK = "https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=JetBrains+Mono:wght@400;500&display=swap";

// —— Mock Data ——
const MOCK_STATS = {
  totalUsers: 247,
  activeInstances: 189,
  disconnected: 12,
  mrr: 18750,
  churnRate: 4.2,
  avgTokensDay: 342000,
  onboardingCompletion: 67,
  trialConversion: 38,
};

const MOCK_INSTANCES = [
  { id: 1, user: "Carlos Mendes", phone: "+55 11 98765-4321", plan: "Pro", status: "connected", lastPing: "agora", msgs24h: 1240, tokensUsed: 48200 },
  { id: 2, user: "Ana Beatriz", phone: "+55 21 99876-5432", plan: "Business", status: "connected", lastPing: "2min", msgs24h: 3420, tokensUsed: 112300 },
  { id: 3, user: "Roberto Silva", phone: "+55 31 97654-3210", plan: "Starter", status: "disconnected", lastPing: "47min", msgs24h: 0, tokensUsed: 0 },
  { id: 4, user: "Julia Costa", phone: "+55 41 96543-2109", plan: "Pro", status: "connected", lastPing: "1min", msgs24h: 890, tokensUsed: 31400 },
  { id: 5, user: "Fernando Lima", phone: "+55 51 95432-1098", plan: "Business", status: "warning", lastPing: "15min", msgs24h: 210, tokensUsed: 8900 },
  { id: 6, user: "Mariana Souza", phone: "+55 61 94321-0987", plan: "Starter", status: "disconnected", lastPing: "2h", msgs24h: 0, tokensUsed: 0 },
  { id: 7, user: "Pedro Alves", phone: "+55 71 93210-9876", plan: "Pro", status: "connected", lastPing: "agora", msgs24h: 2100, tokensUsed: 67500 },
  { id: 8, user: "Larissa Nunes", phone: "+55 81 92109-8765", plan: "Business", status: "connected", lastPing: "30s", msgs24h: 4560, tokensUsed: 156000 },
];

const MOCK_AGENTS = [
  {
    name: "Agente de vendas",
    color: "#2D9CDB",
    users: 156,
    stages: [
      { label: "Qualificação", prompt: "Identificar necessidade do lead...", users: 156 },
      { label: "Apresentação", prompt: "Apresentar solução personalizada...", users: 142 },
      { label: "Negociação", prompt: "Negociar condições e responder objeções...", users: 118 },
      { label: "Fechamento", prompt: "Conduzir ao fechamento da venda...", users: 89 },
    ],
  },
  {
    name: "Agente de suporte",
    color: "#27AE60",
    users: 198,
    stages: [
      { label: "Triagem", prompt: "Classificar tipo de problema...", users: 198 },
      { label: "Resolução L1", prompt: "Resolver problemas comuns com FAQ...", users: 174 },
      { label: "Escalação", prompt: "Escalar para atendimento humano...", users: 56 },
    ],
  },
  {
    name: "Agente de agendamento",
    color: "#F2994A",
    users: 91,
    stages: [
      { label: "Captação", prompt: "Captar interesse e coletar dados...", users: 91 },
      { label: "Disponibilidade", prompt: "Verificar horários disponíveis...", users: 78 },
      { label: "Confirmação", prompt: "Confirmar e enviar lembrete...", users: 72 },
    ],
  },
];

const MOCK_MRR_HISTORY = [
  { month: "Nov", value: 12400 },
  { month: "Dez", value: 13800 },
  { month: "Jan", value: 14200 },
  { month: "Fev", value: 15900 },
  { month: "Mar", value: 17100 },
  { month: "Abr", value: 18750 },
];

const MOCK_ALERTS = [
  { type: "critical", msg: "2 instâncias desconectadas há mais de 30min", time: "3min atrás" },
  { type: "warning", msg: "Fernando Lima com latência alta (15min sem ping)", time: "15min atrás" },
  { type: "info", msg: "5 novos usuários completaram onboarding hoje", time: "1h atrás" },
  { type: "info", msg: "Uazapi API respondendo normalmente — latência 42ms", time: "2h atrás" },
];

// —— Styles ——
const css = `
@import url('${FONT_LINK}');

* { margin:0; padding:0; box-sizing:border-box; }

:root {
  --bg-deep: #0B0E14;
  --bg-card: #111621;
  --bg-card-hover: #161C2A;
  --bg-surface: #1A2030;
  --border: rgba(255,255,255,0.06);
  --border-hover: rgba(255,255,255,0.12);
  --text-primary: #E8ECF4;
  --text-secondary: #8B95A8;
  --text-muted: #5A6478;
  --accent: #3B82F6;
  --accent-dim: rgba(59,130,246,0.12);
  --green: #22C55E;
  --green-dim: rgba(34,197,94,0.12);
  --red: #EF4444;
  --red-dim: rgba(239,68,68,0.12);
  --amber: #F59E0B;
  --amber-dim: rgba(245,158,11,0.12);
  --purple: #A855F7;
  --purple-dim: rgba(168,85,247,0.12);
  --font: 'DM Sans', -apple-system, sans-serif;
  --mono: 'JetBrains Mono', monospace;
  --radius: 10px;
  --radius-lg: 14px;
}

body, html {
  font-family: var(--font);
  background: var(--bg-deep);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
}

.layout {
  display: flex;
  min-height: 100vh;
}

/* —— Sidebar —— */
.sidebar {
  width: 240px;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-brand {
  padding: 0 20px 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
}

.sidebar-brand h1 {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.sidebar-brand span {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 400;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-top: 2px;
  display: block;
}

.nav-section {
  padding: 12px 12px 4px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 16px;
  margin: 1px 8px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 400;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.nav-item:hover {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--accent-dim);
  color: var(--accent);
  font-weight: 500;
}

.nav-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  opacity: 0.7;
}

.nav-item.active .nav-icon { opacity: 1; }

.nav-badge {
  margin-left: auto;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 10px;
  background: var(--red-dim);
  color: var(--red);
}

.sidebar-footer {
  margin-top: auto;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}

.health-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.health-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.health-dot.ok { background: var(--green); box-shadow: 0 0 6px rgba(34,197,94,0.4); }
.health-dot.warn { background: var(--amber); box-shadow: 0 0 6px rgba(245,158,11,0.4); }

/* —— Main Content —— */
.main {
  flex: 1;
  padding: 24px 28px;
  overflow-y: auto;
  min-width: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.header-time {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--mono);
}

/* —— Stat Cards —— */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  transition: border-color 0.2s;
}

.stat-card:hover { border-color: var(--border-hover); }

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
  letter-spacing: 0.02em;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
}

.stat-sub {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-up { color: var(--green); }
.stat-down { color: var(--red); }

/* —— Section —— */
.section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.section-action {
  font-size: 11px;
  color: var(--accent);
  cursor: pointer;
  font-weight: 500;
}

/* —— Alerts —— */
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.alert-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 12px;
  transition: border-color 0.2s;
}

.alert-row:hover { border-color: var(--border-hover); }

.alert-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.alert-dot.critical { background: var(--red); box-shadow: 0 0 8px rgba(239,68,68,0.3); }
.alert-dot.warning { background: var(--amber); box-shadow: 0 0 8px rgba(245,158,11,0.3); }
.alert-dot.info { background: var(--accent); }

.alert-msg { flex:1; color: var(--text-secondary); }
.alert-time { color: var(--text-muted); font-family: var(--mono); font-size: 10px; white-space: nowrap; }

/* —— Two Column Layout —— */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

/* —— Instances Table —— */
.table-wrap {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.table-inner {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th {
  text-align: left;
  padding: 10px 14px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
  white-space: nowrap;
}

tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-card-hover); }

.user-cell {
  color: var(--text-primary);
  font-weight: 500;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
}

.status-badge.connected { background: var(--green-dim); color: var(--green); }
.status-badge.disconnected { background: var(--red-dim); color: var(--red); }
.status-badge.warning { background: var(--amber-dim); color: var(--amber); }

.status-pulse {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.plan-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.plan-tag.starter { background: rgba(139,149,168,0.12); color: var(--text-secondary); }
.plan-tag.pro { background: var(--accent-dim); color: var(--accent); }
.plan-tag.business { background: var(--purple-dim); color: var(--purple); }

.mono { font-family: var(--mono); font-size: 11px; }

.action-btn {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  font-family: var(--font);
  transition: all 0.15s;
}

.action-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-dim);
}

.action-btn.reconnect {
  border-color: rgba(239,68,68,0.3);
  color: var(--red);
}

.action-btn.reconnect:hover {
  background: var(--red-dim);
  border-color: var(--red);
}

/* —— Pipeline / Agents —— */
.pipeline-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 18px;
  margin-bottom: 12px;
}

.pipeline-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.pipeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.pipeline-name {
  font-size: 14px;
  font-weight: 600;
}

.pipeline-users {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--mono);
}

.pipeline-stages {
  display: flex;
  gap: 8px;
}

.stage-block {
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}

.stage-block:hover {
  border-color: var(--border-hover);
  transform: translateY(-1px);
}

.stage-block::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
}

.stage-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.stage-prompt {
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 8px;
}

.stage-users-count {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.stage-users-label {
  font-size: 9px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stage-bar {
  height: 3px;
  border-radius: 2px;
  background: rgba(255,255,255,0.06);
  margin-top: 8px;
  overflow: hidden;
}

.stage-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s ease;
}

/* —— MRR Chart —— */
.chart-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 18px;
}

.chart-area {
  position: relative;
  height: 160px;
  margin-top: 12px;
}

.chart-svg {
  width: 100%;
  height: 100%;
}

/* —— Growth Metrics —— */
.growth-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 18px;
}

.funnel-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.funnel-bar-bg {
  flex: 1;
  height: 28px;
  background: var(--bg-surface);
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}

.funnel-bar-fill {
  height: 100%;
  border-radius: 6px;
  display: flex;
  align-items: center;
  padding-left: 10px;
  font-size: 11px;
  font-weight: 500;
  color: rgba(255,255,255,0.9);
  transition: width 0.8s ease;
  white-space: nowrap;
}

.funnel-pct {
  font-size: 12px;
  font-weight: 600;
  font-family: var(--mono);
  color: var(--text-secondary);
  min-width: 38px;
  text-align: right;
}

/* —— Tabs —— */
.tabs {
  display: flex;
  gap: 2px;
  margin-bottom: 16px;
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 3px;
}

.tab {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.tab:hover { color: var(--text-secondary); }
.tab.active { background: var(--bg-card); color: var(--text-primary); box-shadow: 0 1px 3px rgba(0,0,0,0.2); }

/* —— Animations —— */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-in {
  animation: fadeUp 0.4s ease forwards;
  opacity: 0;
}

.delay-1 { animation-delay: 0.05s; }
.delay-2 { animation-delay: 0.1s; }
.delay-3 { animation-delay: 0.15s; }
.delay-4 { animation-delay: 0.2s; }
.delay-5 { animation-delay: 0.25s; }
.delay-6 { animation-delay: 0.3s; }
.delay-7 { animation-delay: 0.35s; }
.delay-8 { animation-delay: 0.4s; }
`;

// —— Icons (simple SVG paths) ——
const Icon = ({ name, size = 18 }) => {
  const icons = {
    dashboard: <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" fill="currentColor"/>,
    instances: <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z" fill="currentColor"/>,
    users: <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" fill="currentColor"/>,
    agents: <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>,
    growth: <path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z" fill="currentColor"/>,
    finance: <path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z" fill="currentColor"/>,
    settings: <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94L14.4 2.81c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41L9.25 5.35c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" fill="currentColor"/>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {icons[name]}
    </svg>
  );
};

// —— MRR Mini Chart ——
const MrrChart = ({ data }) => {
  const max = Math.max(...data.map((d) => d.value));
  const min = Math.min(...data.map((d) => d.value)) * 0.85;
  const w = 400;
  const h = 140;
  const padX = 30;
  const padY = 10;
  const pts = data.map((d, i) => ({
    x: padX + (i / (data.length - 1)) * (w - padX * 2),
    y: padY + (1 - (d.value - min) / (max - min)) * (h - padY * 2),
  }));
  const line = pts.map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`)).join(" ");
  const area = `${line} L${pts[pts.length - 1].x},${h} L${pts[0].x},${h} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h + 20}`} className="chart-svg">
      <defs>
        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#areaGrad)" />
      <path d={line} fill="none" stroke="#3B82F6" strokeWidth="2" strokeLinejoin="round" />
      {pts.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r="3" fill="#3B82F6" />
          <text x={p.x} y={h + 14} textAnchor="middle" fill="#5A6478" fontSize="10" fontFamily="'DM Sans', sans-serif">
            {data[i].month}
          </text>
        </g>
      ))}
    </svg>
  );
};

// —— Main Component ——
export default function AdminDashboard() {
  const [activeNav, setActiveNav] = useState("dashboard");
  const [activeTab, setActiveTab] = useState("all");
  const [expandedAgent, setExpandedAgent] = useState(0);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(t);
  }, []);

  const filteredInstances = MOCK_INSTANCES.filter((inst) => {
    if (activeTab === "all") return true;
    return inst.status === activeTab;
  });

  const navItems = [
    { key: "dashboard", label: "Dashboard", icon: "dashboard" },
    { key: "instances", label: "Instâncias", icon: "instances", badge: MOCK_STATS.disconnected },
    { key: "users", label: "Usuários", icon: "users" },
    { key: "agents", label: "Agentes e prompts", icon: "agents" },
    { key: "growth", label: "Crescimento", icon: "growth" },
    { key: "finance", label: "Financeiro", icon: "finance" },
    { key: "settings", label: "Configurações", icon: "settings" },
  ];

  return (
    <>
      <style>{css}</style>
      <div className="layout">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-brand">
            <h1>SaaS Admin</h1>
            <span>Painel de controle</span>
          </div>

          <div className="nav-section">Principal</div>
          {navItems.slice(0, 4).map((item) => (
            <div
              key={item.key}
              className={`nav-item ${activeNav === item.key ? "active" : ""}`}
              onClick={() => setActiveNav(item.key)}
            >
              <span className="nav-icon"><Icon name={item.icon} /></span>
              {item.label}
              {item.badge && <span className="nav-badge">{item.badge}</span>}
            </div>
          ))}

          <div className="nav-section">Analytics</div>
          {navItems.slice(4, 6).map((item) => (
            <div
              key={item.key}
              className={`nav-item ${activeNav === item.key ? "active" : ""}`}
              onClick={() => setActiveNav(item.key)}
            >
              <span className="nav-icon"><Icon name={item.icon} /></span>
              {item.label}
            </div>
          ))}

          <div className="nav-section">Sistema</div>
          {navItems.slice(6).map((item) => (
            <div
              key={item.key}
              className={`nav-item ${activeNav === item.key ? "active" : ""}`}
              onClick={() => setActiveNav(item.key)}
            >
              <span className="nav-icon"><Icon name={item.icon} /></span>
              {item.label}
            </div>
          ))}

          <div className="sidebar-footer">
            <div className="health-row">
              <span className="health-dot ok" />
              Uazapi API — 42ms
            </div>
            <div className="health-row">
              <span className="health-dot ok" />
              Banco de dados — ok
            </div>
            <div className="health-row">
              <span className="health-dot warn" />
              Fila de mensagens — 89%
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="main">
          <div className="page-header">
            <h2>Dashboard</h2>
            <span className="header-time">
              {now.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" })}
              {" · "}
              {now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>

          {/* Stats */}
          <div className="stats-grid">
            <div className="stat-card animate-in delay-1">
              <div className="stat-label">Usuários ativos</div>
              <div className="stat-value">{MOCK_STATS.totalUsers}</div>
              <div className="stat-sub stat-up">↑ 12% vs mês anterior</div>
            </div>
            <div className="stat-card animate-in delay-2">
              <div className="stat-label">Instâncias online</div>
              <div className="stat-value" style={{ color: "var(--green)" }}>{MOCK_STATS.activeInstances}</div>
              <div className="stat-sub">de {MOCK_STATS.activeInstances + MOCK_STATS.disconnected} total</div>
            </div>
            <div className="stat-card animate-in delay-3">
              <div className="stat-label">MRR</div>
              <div className="stat-value">R$ {MOCK_STATS.mrr.toLocaleString("pt-BR")}</div>
              <div className="stat-sub stat-up">↑ 9.6% vs mês anterior</div>
            </div>
            <div className="stat-card animate-in delay-4">
              <div className="stat-label">Churn rate</div>
              <div className="stat-value" style={{ color: MOCK_STATS.churnRate > 5 ? "var(--red)" : "var(--amber)" }}>
                {MOCK_STATS.churnRate}%
              </div>
              <div className="stat-sub stat-down">↑ 0.8% vs mês anterior</div>
            </div>
          </div>

          {/* Alerts */}
          <div className="section animate-in delay-5">
            <div className="section-header">
              <span className="section-title">Alertas ativos</span>
              <span className="section-action">Ver todos →</span>
            </div>
            <div className="alerts-list">
              {MOCK_ALERTS.map((a, i) => (
                <div className="alert-row" key={i}>
                  <span className={`alert-dot ${a.type}`} />
                  <span className="alert-msg">{a.msg}</span>
                  <span className="alert-time">{a.time}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Instances Table */}
          <div className="section animate-in delay-6">
            <div className="section-header">
              <span className="section-title">Instâncias WhatsApp — Uazapi</span>
              <span className="section-action">Exportar CSV →</span>
            </div>
            <div className="tabs">
              {[
                { key: "all", label: `Todas (${MOCK_INSTANCES.length})` },
                { key: "connected", label: `Online (${MOCK_INSTANCES.filter((i) => i.status === "connected").length})` },
                { key: "disconnected", label: `Offline (${MOCK_INSTANCES.filter((i) => i.status === "disconnected").length})` },
                { key: "warning", label: `Alerta (${MOCK_INSTANCES.filter((i) => i.status === "warning").length})` },
              ].map((tab) => (
                <div key={tab.key} className={`tab ${activeTab === tab.key ? "active" : ""}`} onClick={() => setActiveTab(tab.key)}>
                  {tab.label}
                </div>
              ))}
            </div>
            <div className="table-wrap">
              <div className="table-inner">
                <table>
                  <thead>
                    <tr>
                      <th>Usuário</th>
                      <th>Telefone</th>
                      <th>Plano</th>
                      <th>Status</th>
                      <th>Último ping</th>
                      <th>Msgs 24h</th>
                      <th>Tokens</th>
                      <th>Ação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredInstances.map((inst) => (
                      <tr key={inst.id}>
                        <td className="user-cell">{inst.user}</td>
                        <td className="mono">{inst.phone}</td>
                        <td>
                          <span className={`plan-tag ${inst.plan.toLowerCase()}`}>{inst.plan}</span>
                        </td>
                        <td>
                          <span className={`status-badge ${inst.status}`}>
                            <span className="status-pulse" />
                            {inst.status === "connected" ? "Online" : inst.status === "disconnected" ? "Offline" : "Alerta"}
                          </span>
                        </td>
                        <td className="mono">{inst.lastPing}</td>
                        <td className="mono">{inst.msgs24h.toLocaleString("pt-BR")}</td>
                        <td className="mono">{inst.tokensUsed.toLocaleString("pt-BR")}</td>
                        <td>
                          {inst.status === "disconnected" ? (
                            <button className="action-btn reconnect">Reconectar</button>
                          ) : (
                            <button className="action-btn">Detalhes</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Agents Pipeline */}
          <div className="section animate-in delay-7">
            <div className="section-header">
              <span className="section-title">Pipeline de agentes — Visão de prompts</span>
              <span className="section-action">Ver por usuário →</span>
            </div>
            {MOCK_AGENTS.map((agent, ai) => (
              <div
                className="pipeline-card"
                key={ai}
                style={{ cursor: "pointer" }}
                onClick={() => setExpandedAgent(expandedAgent === ai ? -1 : ai)}
              >
                <div className="pipeline-header">
                  <span className="pipeline-dot" style={{ background: agent.color }} />
                  <span className="pipeline-name">{agent.name}</span>
                  <span className="pipeline-users">{agent.users} usuários</span>
                </div>
                <div className="pipeline-stages">
                  {agent.stages.map((stage, si) => (
                    <div className="stage-block" key={si} style={{ borderTopColor: agent.color }}>
                      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: agent.color, opacity: 0.7 }} />
                      <div className="stage-label">{stage.label}</div>
                      {expandedAgent === ai && <div className="stage-prompt">{stage.prompt}</div>}
                      <div className="stage-users-count" style={{ color: agent.color }}>{stage.users}</div>
                      <div className="stage-users-label">usuários</div>
                      <div className="stage-bar">
                        <div
                          className="stage-bar-fill"
                          style={{
                            width: `${Math.round((stage.users / agent.stages[0].users) * 100)}%`,
                            background: agent.color,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Two columns: MRR Chart + Growth Funnel */}
          <div className="two-col animate-in delay-8">
            <div className="chart-card">
              <div className="section-header" style={{ marginBottom: 0 }}>
                <span className="section-title">Evolução MRR</span>
                <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-muted)" }}>últimos 6 meses</span>
              </div>
              <div className="chart-area">
                <MrrChart data={MOCK_MRR_HISTORY} />
              </div>
            </div>

            <div className="growth-card">
              <div className="section-header" style={{ marginBottom: 4 }}>
                <span className="section-title">Funil de onboarding</span>
              </div>
              {[
                { label: "Cadastro", pct: 100, color: "#3B82F6" },
                { label: "Conectou WhatsApp", pct: 78, color: "#2D9CDB" },
                { label: "Configurou agente", pct: 61, color: "#27AE60" },
                { label: "Primeiro teste", pct: 48, color: "#F2994A" },
                { label: "Em produção", pct: 34, color: "#A855F7" },
              ].map((step, i) => (
                <div className="funnel-step" key={i}>
                  <div className="funnel-bar-bg">
                    <div className="funnel-bar-fill" style={{ width: `${step.pct}%`, background: step.color }}>
                      {step.label}
                    </div>
                  </div>
                  <span className="funnel-pct">{step.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>
    </>
  );
}
