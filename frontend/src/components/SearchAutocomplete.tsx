import { useState, useEffect, useRef } from "react";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "./ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Input } from "./ui/input";
import { Search, Phone, MapPin } from "lucide-react";
import { Lead, KanbanColumn } from "../types/crm";

interface SearchAutocompleteProps {
  searchTerm: string;
  onSearchChange: (term: string) => void;
  allColumns: KanbanColumn[];
  onLeadSelect?: (leadId: string) => void;
}

export function SearchAutocomplete({
  searchTerm,
  onSearchChange,
  allColumns,
  onLeadSelect
}: SearchAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<Array<{ lead: Lead; columnTitle: string; columnColor: string }>>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!searchTerm.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    const term = searchTerm.toLowerCase();
    const matchingLeads: Array<{ lead: Lead; columnTitle: string; columnColor: string }> = [];

    allColumns.forEach(column => {
      column.leads.forEach(lead => {
        const matches = 
          lead.contactName.toLowerCase().includes(term) ||
          lead.companyName.toLowerCase().includes(term) ||
          lead.phone.toLowerCase().includes(term) ||
          lead.origin.toLowerCase().includes(term) ||
          (lead.observations && lead.observations.toLowerCase().includes(term));

        if (matches) {
          matchingLeads.push({
            lead,
            columnTitle: column.title,
            columnColor: column.color
          });
        }
      });
    });

    setSuggestions(matchingLeads.slice(0, 8)); // Limit to 8 suggestions
    
    // Only auto-open if there are suggestions and input is focused
    if (matchingLeads.length > 0 && document.activeElement === inputRef.current) {
      setOpen(true);
    } else if (matchingLeads.length === 0) {
      setOpen(false);
    }
  }, [searchTerm, allColumns]);

  const handleLeadSelect = (leadId: string) => {
    setOpen(false);
    onLeadSelect?.(leadId);
  };

  const handleInputFocus = () => {
    if (suggestions.length > 0) {
      setOpen(true);
    }
  };

  const handleInputBlur = () => {
    // Delay closing to allow item selection
    setTimeout(() => setOpen(false), 150);
  };

  const highlightMatch = (text: string, searchTerm: string) => {
    if (!searchTerm.trim()) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    const parts = text.split(regex);
    
    return parts.map((part, index) => 
      regex.test(part) ? 
        <span key={index} className="bg-primary/20 text-primary font-medium">{part}</span> : 
        part
    );
  };

  return (
    <div className="flex-1 max-w-md mx-8 relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={inputRef}
          type="text"
          placeholder="Pesquisar leads por nome, telefone ou origem..."
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-10 bg-background/50 backdrop-blur-sm border-border focus:border-primary/50"
          onFocus={handleInputFocus}
          onBlur={handleInputBlur}
        />
      </div>
      
      {open && (
        <div className="absolute top-full left-0 right-0 mt-1 z-50">
          <div className="rounded-md border bg-popover p-0 text-popover-foreground shadow-md outline-none animate-in fade-in-0 zoom-in-95 slide-in-from-top-2">
            <Command>
              <CommandList>
                {suggestions.length === 0 ? (
                  <CommandEmpty>Nenhum lead encontrado.</CommandEmpty>
                ) : (
                  <CommandGroup heading="Leads encontrados">
                    {suggestions.map(({ lead, columnTitle, columnColor }) => (
                      <CommandItem
                        key={lead.id}
                        value={lead.id}
                        onSelect={() => handleLeadSelect(lead.id)}
                        className="flex flex-col items-start gap-1 p-3 cursor-pointer"
                      >
                        <div className="flex items-center justify-between w-full">
                          <span className="font-medium text-foreground">
                            {highlightMatch(lead.contactName, searchTerm)}
                          </span>
                          <div 
                            className="px-2 py-1 rounded-md text-xs font-medium text-white"
                            style={{ backgroundColor: columnColor }}
                          >
                            {columnTitle}
                          </div>
                        </div>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Phone className="h-3 w-3" />
                            {highlightMatch(lead.phone, searchTerm)}
                          </div>
                          <div className="flex items-center gap-1">
                            <MapPin className="h-3 w-3" />
                            {highlightMatch(lead.origin, searchTerm)}
                          </div>
                        </div>
                        {lead.observations && (
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                            {highlightMatch(lead.observations, searchTerm)}
                          </p>
                        )}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
              </CommandList>
            </Command>
          </div>
        </div>
      )}
    </div>
  );
}