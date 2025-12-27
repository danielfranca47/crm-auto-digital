import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { ApiError } from "@/lib/api-client";
import { useRateLimitModal } from "@/contexts/RateLimitModalContext";

let sessionToastDisplayed = false;

type HandleErrorOptions = {
  silent?: boolean;
  fallbackMessage?: string;
};

type HandleErrorResult = {
  status?: number;
  message: string;
};

function extractDetail(error: ApiError, fallback: string) {
  const dataDetail = (error.data as any)?.detail;
  if (typeof dataDetail === "string" && dataDetail.trim()) return dataDetail;
  if (typeof error.message === "string" && error.message.trim()) return error.message;
  return fallback;
}

export function useApiErrorHandler() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { openModal } = useRateLimitModal();

  const handleError = useCallback(
    (error: unknown, options?: HandleErrorOptions): HandleErrorResult => {
      const fallback = options?.fallbackMessage ?? "Ocorreu um erro ao processar sua solicitação.";

      if (error instanceof ApiError) {
        const status = error.status;
        const detail = extractDetail(error, fallback);

        if (status === 429) {
          openModal(detail);
          return { status, message: detail };
        }

        if (status === 401 || status === 403) {
          if (!sessionToastDisplayed) {
            toast({
              title: "Sessão expirada",
              description: "Faça login novamente.",
              variant: "destructive",
            });
            sessionToastDisplayed = true;
          }
          navigate("/login");
          return { status, message: "Sessão expirada" };
        }

        if (!options?.silent) {
          const title = status === 404 ? "Recurso não encontrado" : status === 422 ? "Dados inválidos" : "Erro ao processar";
          toast({
            title,
            description: detail,
            variant: "destructive",
          });
        }

        return { status, message: detail };
      }

      const genericMessage = (error as Error)?.message ?? fallback;
      if (!options?.silent) {
        toast({
          title: "Erro",
          description: genericMessage,
          variant: "destructive",
        });
      }
      return { message: genericMessage };
    },
    [navigate, openModal, toast]
  );

  return { handleError } as const;
}
