import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { isAdminTokenValid } from "@/lib/admin-token";

interface AdminGuardProps {
  children: React.ReactNode;
}

export default function AdminGuard({ children }: AdminGuardProps) {
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    setOk(isAdminTokenValid());
  }, []);

  if (ok === null) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400">
        Verificando acesso…
      </div>
    );
  }

  if (!ok) {
    return <Navigate replace to="/login" />;
  }

  return <>{children}</>;
}
