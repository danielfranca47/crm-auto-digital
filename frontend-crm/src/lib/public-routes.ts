// Rotas sem sessão do CRM: páginas de autenticação e o painel admin (que tem token próprio).
// Nelas não se pedem dados do utilizador (leads, pausa do bot, assinatura).
const PUBLIC_PATHS = ["/login", "/register", "/forgot-password", "/reset-password"];
const PUBLIC_PREFIXES = ["/saas-admin"];

export function isPublicPath(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (PUBLIC_PATHS.includes(path)) return true;
  return PUBLIC_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}
