import React, { useCallback, useEffect, useRef, useState } from 'react';
import { VariableDef } from '@/types/variables';

interface VariablePickerProps {
  variables: VariableDef[];
  filterText: string;
  position: { top: number; left: number };
  onSelect: (v: VariableDef) => void;
  onAddCustom?: () => void;
  onClose: () => void;
}

function GroupHeader({ label }: { label: string }) {
  return (
    <div
      style={{
        padding: '4px 12px 2px',
        fontSize: 10,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        color: 'var(--o-sub, #888)',
      }}
    >
      {label}
    </div>
  );
}

function PickerItem({
  variable,
  isSelected,
  onMouseEnter,
  onClick,
}: {
  variable: VariableDef;
  isSelected: boolean;
  onMouseEnter: () => void;
  onClick: () => void;
}) {
  return (
    <div
      onMouseEnter={onMouseEnter}
      onMouseDown={(e) => {
        e.preventDefault(); // evita blur no textarea
        onClick();
      }}
      style={{
        padding: '5px 12px',
        cursor: 'pointer',
        background: isSelected ? 'var(--o-b1, rgba(255,255,255,0.06))' : 'transparent',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 500,
            color: 'var(--o-purple, #a78bfa)',
            background: 'rgba(167,139,250,0.12)',
            borderRadius: 3,
            padding: '1px 5px',
            fontFamily: 'monospace',
            flexShrink: 0,
          }}
        >
          {`{{${variable.key}}}`}
        </span>
        <span style={{ fontSize: 12, color: 'var(--o-text, #e2e8f0)' }}>
          {variable.label}
        </span>
      </div>
      {variable.example && (
        <span style={{ fontSize: 11, color: 'var(--o-sub, #888)', paddingLeft: 2 }}>
          ex: {variable.example}
        </span>
      )}
    </div>
  );
}

export function VariablePicker({
  variables,
  filterText,
  position,
  onSelect,
  onAddCustom,
  onClose,
}: VariablePickerProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = variables.filter((v) => {
    if (!filterText) return true;
    const q = filterText.toLowerCase();
    return v.key.includes(q) || v.label.toLowerCase().includes(q);
  });

  const grouped = {
    system: filtered.filter((v) => v.category === 'system'),
    custom: filtered.filter((v) => v.category === 'custom'),
  };

  // Reset selected index quando filtro muda
  useEffect(() => {
    setSelectedIndex(0);
  }, [filterText]);

  // Scroll item selecionado para visível
  useEffect(() => {
    if (!containerRef.current) return;
    const selected = containerRef.current.querySelector('[data-selected="true"]');
    selected?.scrollIntoView({ block: 'nearest' });
  }, [selectedIndex]);

  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (filtered[selectedIndex]) onSelect(filtered[selectedIndex]);
      } else if (e.key === 'Escape') {
        onClose();
      }
    },
    [filtered, selectedIndex, onSelect, onClose]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKey, true);
    return () => document.removeEventListener('keydown', handleKey, true);
  }, [handleKey]);

  return (
    <div
      ref={containerRef}
      data-variable-picker
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        zIndex: 9999,
        background: 'var(--o-bg, #0f1117)',
        border: '1px solid var(--o-b1, rgba(255,255,255,0.08))',
        borderRadius: 8,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        minWidth: 260,
        maxWidth: 340,
        maxHeight: 320,
        overflowY: 'auto',
        padding: '4px 0',
      }}
    >
      {/* Dica de uso */}
      <div
        style={{
          padding: '5px 12px 3px',
          fontSize: 10,
          color: 'var(--o-sub, #888)',
          borderBottom: '1px solid var(--o-b1, rgba(255,255,255,0.06))',
          marginBottom: 2,
        }}
      >
        ↑↓ navegar · Enter inserir · Esc fechar
      </div>

      {/* Grupo sistema */}
      {grouped.system.length > 0 && (
        <>
          <GroupHeader label="Variáveis do sistema" />
          {grouped.system.map((v) => {
            const idx = filtered.indexOf(v);
            return (
              <PickerItem
                key={v.key}
                variable={v}
                isSelected={idx === selectedIndex}
                onMouseEnter={() => setSelectedIndex(idx)}
                onClick={() => onSelect(v)}
              />
            );
          })}
        </>
      )}

      {/* Grupo personalizadas */}
      {grouped.custom.length > 0 && (
        <>
          <GroupHeader label="Minhas variáveis" />
          {grouped.custom.map((v) => {
            const idx = filtered.indexOf(v);
            return (
              <PickerItem
                key={v.key}
                variable={v}
                isSelected={idx === selectedIndex}
                onMouseEnter={() => setSelectedIndex(idx)}
                onClick={() => onSelect(v)}
              />
            );
          })}
        </>
      )}

      {/* Nenhum resultado */}
      {filtered.length === 0 && (
        <div
          style={{ padding: '10px 12px', fontSize: 12, color: 'var(--o-sub, #888)' }}
        >
          Nenhuma variável encontrada
        </div>
      )}

      {/* Adicionar nova */}
      {onAddCustom && (
        <>
          <div
            style={{
              height: 1,
              background: 'var(--o-b1, rgba(255,255,255,0.06))',
              margin: '4px 0',
            }}
          />
          <button
            onMouseDown={(e) => {
              e.preventDefault();
              onAddCustom();
            }}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '7px 12px',
              fontSize: 12,
              color: 'var(--o-purple, #a78bfa)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
            Adicionar variável personalizada
          </button>
        </>
      )}
    </div>
  );
}
