import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearAdminToken } from "@/lib/admin-token";
import {
  LayoutDashboard,
  Wifi,
  Users,
  Bot,
  TrendingUp,
  DollarSign,
  Settings,
  LogOut,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/saas-admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/saas-admin/instancias", label: "Instâncias", icon: Wifi },
  { to: "/saas-admin/usuarios", label: "Usuários", icon: Users },
  { to: "/saas-admin/agentes", label: "Agentes e Prompts", icon: Bot },
  { to: "/saas-admin/crescimento", label: "Crescimento", icon: TrendingUp },
  { to: "/saas-admin/financeiro", label: "Financeiro", icon: DollarSign },
  { to: "/saas-admin/configuracoes", label: "Configurações", icon: Settings },
];

export default function AdminLayout() {
  const navigate = useNavigate();

  function logout() {
    clearAdminToken();
    navigate("/saas-admin/login");
  }

  return (
    <div className="min-h-screen flex bg-slate-900 text-slate-100">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col border-r border-slate-700 bg-slate-900">
        <div className="px-4 py-5 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm">
              SA
            </div>
            <span className="font-semibold text-sm text-slate-200">SaaS Admin</span>
          </div>
        </div>

        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-2 py-3 border-t border-slate-700">
          <button
            onClick={logout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-slate-800 hover:text-red-400 transition-colors"
          >
            <LogOut size={16} />
            Sair
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
