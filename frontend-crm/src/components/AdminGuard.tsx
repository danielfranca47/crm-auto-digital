import { useEffect, useState } from "react";
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
    return <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400">Verificando acesso…</div>;
  }

  if (!ok) {
    window.location.replace("/saas-admin/login");
    return null;
  }

  return <>{children}</>;
}
