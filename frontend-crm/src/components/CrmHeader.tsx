import { Button } from "./ui/button";
import { Plus, BarChart3, Sun, Moon, Pause, Play } from "lucide-react";
import { useTheme } from "../contexts/ThemeContext";
import { SearchAutocomplete } from "./SearchAutocomplete";
import { KanbanColumn } from "../types/crm";
interface CrmHeaderProps {
  onNewLead: () => void;
  onDashboard: () => void;
  searchTerm: string;
  onSearchChange: (term: string) => void;
  allColumns: KanbanColumn[];
  onLeadSelect?: (leadId: string) => void;
  botGlobalPaused?: boolean;
  onTogglePause?: () => void;
}
export function CrmHeader({
  onNewLead,
  onDashboard,
  searchTerm,
  onSearchChange,
  allColumns,
  onLeadSelect,
  botGlobalPaused = false,
  onTogglePause
}: CrmHeaderProps) {
  const {
    theme,
    toggleTheme
  } = useTheme();
  return <header className="crm-header px-6 py-4 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center space-x-4">
        <h1 className="text-2xl font-bold gradient-primary bg-clip-text text-transparent">CRM Comercial - Auto Digital</h1>
      </div>
      
      {/* Search field with autocomplete */}
      <SearchAutocomplete
        searchTerm={searchTerm}
        onSearchChange={onSearchChange}
        allColumns={allColumns}
        onLeadSelect={onLeadSelect}
      />
      
      <div className="flex items-center space-x-3">
        {onTogglePause && (
          <Button
            onClick={onTogglePause}
            variant="ghost"
            size="sm"
            className={`border transition-smooth ${botGlobalPaused ? "border-destructive/40 text-destructive hover:bg-destructive/10" : "border-border hover:bg-muted"}`}
            title={botGlobalPaused ? "Bot pausado — clique para retomar" : "Pausar bot para todos os leads"}
          >
            {botGlobalPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
          </Button>
        )}

        <Button onClick={toggleTheme} variant="ghost" size="sm" className="border border-border hover:bg-muted transition-smooth" title={theme === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro'}>
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </Button>

        <Button onClick={onNewLead} className="gradient-primary text-white hover:shadow-glow transition-smooth" size="sm">
          <Plus className="w-4 h-4 mr-2" />
          Novo Lead
        </Button>
        
        <Button onClick={onDashboard} variant="outline" className="border-primary/20 text-primary hover:bg-primary/10 transition-smooth" size="sm">
          <BarChart3 className="w-4 h-4 mr-2" />
          Dashboard de Métricas
        </Button>
      </div>
    </header>;
}