import { useEffect, useState } from "react";
import { useBusinessTimezone, browserTimezone } from "@/hooks/useBusinessTimezone";

type TimezoneMode = "browser" | "business";

const STORAGE_KEY = "agenda_grid_timezone_mode";

function readStoredMode(): TimezoneMode {
  try {
    return localStorage.getItem(STORAGE_KEY) === "business" ? "business" : "browser";
  } catch {
    return "browser";
  }
}

/**
 * Controla em qual fuso a grade visual da Agenda (WeekView/DayView) é exibida, quando o
 * fuso do negócio difere do navegador. Por defeito mostra o fuso do navegador; o
 * utilizador pode alternar para o fuso do negócio quantas vezes quiser, e a escolha
 * persiste entre sessões (localStorage). Sem mismatch, sempre resolve para o mesmo fuso
 * dos dois lados — replica o comportamento actual sem excepções.
 */
export function useAgendaTimezoneMode() {
  const businessTimezone = useBusinessTimezone();
  const mismatched = businessTimezone !== browserTimezone;
  const [mode, setMode] = useState<TimezoneMode>(readStoredMode);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // localStorage indisponível (modo privado etc.) — preferência não persiste, sem quebrar a tela
    }
  }, [mode]);

  function toggle() {
    setMode((m) => (m === "browser" ? "business" : "browser"));
  }

  const activeTimezone = mismatched && mode === "business" ? businessTimezone : browserTimezone;

  return { mode, toggle, mismatched, activeTimezone, businessTimezone, browserTimezone };
}
