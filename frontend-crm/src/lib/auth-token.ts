const TOKEN_KEY = "crm_token";
const LEGACY_KEYS = ["crm-auth-token", "auth_token", "token", "core_token"];

function getStorages(): Storage[] {
  const storages: Storage[] = [];
  if (typeof localStorage !== "undefined") storages.push(localStorage);
  if (typeof sessionStorage !== "undefined") storages.push(sessionStorage);
  return storages;
}

export function persistAuthToken(token: string) {
  const storages = getStorages();
  if (!storages.length) return;

  for (const storage of storages) {
    try {
      storage.setItem(TOKEN_KEY, token);
    } catch (e) {
      console.warn("Falha ao persistir token", e);
    }
  }
}

export function clearAuthToken() {
  const storages = getStorages();
  if (!storages.length) return;

  for (const storage of storages) {
    try {
      storage.removeItem(TOKEN_KEY);
      for (const legacy of LEGACY_KEYS) {
        storage.removeItem(legacy);
      }
    } catch (e) {
      console.warn("Falha ao limpar token", e);
    }
  }
}

export function readAuthToken(): string | null {
  const storages = getStorages();
  if (!storages.length) return null;

  let found: string | null = null;

  for (const storage of storages) {
    const primary = storage.getItem(TOKEN_KEY);
    if (primary) return primary;

    for (const legacy of LEGACY_KEYS) {
      const value = storage.getItem(legacy);
      if (value) {
        found = value;
        // migra para a key padrão para os próximos usos
        try {
          storage.setItem(TOKEN_KEY, value);
        } catch (e) {
          console.warn("Falha ao migrar token legada", e);
        }
        break;
      }
    }

    if (found) break;
  }

  return found;
}

export { TOKEN_KEY, LEGACY_KEYS };
