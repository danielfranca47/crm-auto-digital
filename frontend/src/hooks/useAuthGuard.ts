import { useEffect } from "react";
import { api } from "../services/api";

export function useAuthGuard() {
  useEffect(() => {
    (async () => {
      try {
        await api.auth.me(); // ok: segue
      } catch {
        if (location.pathname !== "/login") location.href = "/login";
      }
    })();
  }, []);
}
