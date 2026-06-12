const ADMIN_TOKEN_KEY = "crm_admin_token";

export function persistAdminToken(token: string) {
  try {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
  } catch (e) {
    console.warn("Falha ao persistir token admin", e);
  }
}

export function readAdminToken(): string | null {
  try {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function clearAdminToken() {
  try {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch (e) {
    console.warn("Falha ao limpar token admin", e);
  }
}

export function isAdminTokenValid(): boolean {
  const token = readAdminToken();
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.role === "admin" && payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}
