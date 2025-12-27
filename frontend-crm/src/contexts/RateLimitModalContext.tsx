import React, { createContext, useCallback, useContext, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface RateLimitModalContextValue {
  openModal: (detail?: string) => void;
  closeModal: () => void;
}

const RateLimitModalContext = createContext<RateLimitModalContextValue | undefined>(undefined);

export function RateLimitModalProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [detail, setDetail] = useState<string>("Limite do plano atingido. Atualize seu plano ou reveja seus limites.");

  const openModal = useCallback((nextDetail?: string) => {
    setDetail(nextDetail?.trim() || "Limite do plano atingido. Atualize seu plano ou reveja seus limites.");
    setIsOpen(true);
  }, []);

  const closeModal = useCallback(() => setIsOpen(false), []);

  const value = useMemo(
    () => ({ openModal, closeModal }),
    [closeModal, openModal]
  );

  return (
    <RateLimitModalContext.Provider value={value}>
      {children}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader className="space-y-3">
            <div className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              <DialogTitle className="text-lg font-semibold text-destructive">Limite do plano atingido</DialogTitle>
            </div>
            <DialogDescription className="text-base text-foreground">
              {detail}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Button asChild className="w-full" onClick={closeModal}>
              <Link to="/assinatura">Ver planos</Link>
            </Button>
            <Button asChild variant="outline" className="w-full" onClick={closeModal}>
              <Link to="/minha-conta">Ver limites</Link>
            </Button>
            <Button variant="ghost" className="w-full" onClick={closeModal}>
              Fechar
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </RateLimitModalContext.Provider>
  );
}

export function useRateLimitModal() {
  const ctx = useContext(RateLimitModalContext);
  if (!ctx) {
    throw new Error("useRateLimitModal deve ser usado dentro de RateLimitModalProvider");
  }
  return ctx;
}
