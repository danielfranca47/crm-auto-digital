import '@/styles/orion.css';

interface OrionShellProps {
  children: React.ReactNode;
}

/**
 * Wrapper de escopo visual Orion.
 * Aplica a classe .orion-shell que ativa o design system via CSS variables.
 * As páginas de agente ficam fora do AppShell — têm topbar e subnav próprios.
 */
export function OrionShell({ children }: OrionShellProps) {
  return (
    <div className="orion-shell">
      {children}
    </div>
  );
}
