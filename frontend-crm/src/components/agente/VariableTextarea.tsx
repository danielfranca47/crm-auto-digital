import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { VariableDef } from '@/types/variables';
import { VariablePicker } from './VariablePicker';

interface VariableTextareaProps {
  value: string;
  onChange: (value: string) => void;
  variables: VariableDef[];
  maxLength?: number;
  placeholder?: string;
  minHeight?: number;
  className?: string;
  onAddCustomVariable?: () => void;
}

// Regex para detectar {{tokens}} no texto (para o preview)
const TOKEN_RE = /(\{\{[\w.]+\}\})/g;

/** Renderiza o texto com tokens como badges coloridos (preview somente-leitura) */
function TokenPreview({
  text,
  variables,
}: {
  text: string;
  variables: VariableDef[];
}) {
  if (!text || !TOKEN_RE.test(text)) return null;
  TOKEN_RE.lastIndex = 0; // reset após test()

  const varMap = Object.fromEntries(variables.map((v) => [v.key, v.label]));
  const parts = text.split(TOKEN_RE);

  return (
    <div
      style={{
        marginTop: 6,
        fontSize: 12,
        color: 'var(--o-sub, #888)',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '2px 0',
        lineHeight: 1.6,
      }}
    >
      <span style={{ marginRight: 4, opacity: 0.6 }}>Preview:</span>
      {parts.map((part, i) => {
        if (i % 2 === 0) {
          return (
            <span key={i} style={{ whiteSpace: 'pre-wrap' }}>
              {part}
            </span>
          );
        }
        // é um token {{chave}}
        const key = part.slice(2, -2); // remove {{ e }}
        const label = varMap[key];
        return (
          <span
            key={i}
            title={label ? `${label} · {{${key}}}` : `{{${key}}}`}
            style={{
              display: 'inline-block',
              background: 'rgba(167,139,250,0.18)',
              color: 'var(--o-purple, #a78bfa)',
              borderRadius: 3,
              padding: '0 5px',
              fontSize: 11,
              fontWeight: 500,
              fontFamily: 'monospace',
              lineHeight: '1.7',
              cursor: 'default',
              userSelect: 'none',
            }}
          >
            {label || key}
          </span>
        );
      })}
    </div>
  );
}

export function VariableTextarea({
  value,
  onChange,
  variables,
  maxLength,
  placeholder,
  minHeight = 90,
  className,
  onAddCustomVariable,
}: VariableTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [showPicker, setShowPicker] = useState(false);
  const [pickerPos, setPickerPos] = useState({ top: 0, left: 0 });
  const [filterText, setFilterText] = useState('');
  // Posição no valor string onde o "/" foi digitado
  const triggerPosRef = useRef<number>(-1);

  /** Calcula posição aproximada do picker perto do cursor */
  function _updatePickerPos(ta: HTMLTextAreaElement, cursorPos: number) {
    const rect = ta.getBoundingClientRect();
    // Usar getComputedStyle para lineHeight real
    const cs = window.getComputedStyle(ta);
    const lineHeight = parseFloat(cs.lineHeight) || 20;
    const paddingTop = parseFloat(cs.paddingTop) || 8;
    const linesUntilCursor = ta.value.slice(0, cursorPos).split('\n').length;
    const estimatedTop =
      rect.top +
      paddingTop +
      linesUntilCursor * lineHeight -
      ta.scrollTop +
      lineHeight;

    // Garantir que não saia da tela verticalmente
    const pickerHeight = 300;
    const top =
      estimatedTop + pickerHeight > window.innerHeight
        ? rect.top + paddingTop + (linesUntilCursor - 1) * lineHeight - ta.scrollTop - pickerHeight
        : estimatedTop;

    setPickerPos({
      top,
      left: Math.min(rect.left + 12, window.innerWidth - 360),
    });
  }

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newVal = e.target.value;
      onChange(newVal);

      const cursor = e.target.selectionStart ?? newVal.length;

      if (showPicker) {
        const triggerPos = triggerPosRef.current;
        if (triggerPos < 0) return;
        const query = newVal.slice(triggerPos + 1, cursor);
        // Fechar se digitou espaço, quebra de linha, ou voltou antes do trigger
        if (query.includes(' ') || query.includes('\n') || cursor <= triggerPos) {
          setShowPicker(false);
          triggerPosRef.current = -1;
          return;
        }
        setFilterText(query);
        return;
      }

      // Detectar "/"
      if (newVal[cursor - 1] === '/') {
        triggerPosRef.current = cursor - 1;
        setFilterText('');
        setShowPicker(true);
        _updatePickerPos(e.target, cursor - 1);
      }
    },
    [showPicker, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (!showPicker) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowPicker(false);
        triggerPosRef.current = -1;
      }
      if (e.key === 'Backspace') {
        const ta = textareaRef.current;
        if (ta && ta.selectionStart <= triggerPosRef.current) {
          setShowPicker(false);
          triggerPosRef.current = -1;
        }
      }
      // Enter/Tab são tratados pelo VariablePicker via keydown capture
    },
    [showPicker]
  );

  function insertVariable(v: VariableDef) {
    const ta = textareaRef.current;
    if (!ta) return;
    const triggerPos = triggerPosRef.current;
    if (triggerPos < 0) return;

    const cursor = ta.selectionStart ?? value.length;
    const before = value.slice(0, triggerPos);
    const after = value.slice(cursor);
    const token = `{{${v.key}}}`;
    const newValue = before + token + after;
    onChange(newValue);

    const newCursor = before.length + token.length;
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(newCursor, newCursor);
    });

    setShowPicker(false);
    triggerPosRef.current = -1;
    setFilterText('');
  }

  function handleAddCustom() {
    setShowPicker(false);
    triggerPosRef.current = -1;
    onAddCustomVariable?.();
  }

  // Fechar picker ao clicar fora (sem onMouseDown no picker para não bloquear seleção)
  useEffect(() => {
    if (!showPicker) return;
    function onClickOutside(e: MouseEvent) {
      if (!(e.target as Element).closest('[data-variable-picker]')) {
        setShowPicker(false);
        triggerPosRef.current = -1;
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [showPicker]);

  const hasTokens = TOKEN_RE.test(value);
  TOKEN_RE.lastIndex = 0;

  return (
    <div style={{ position: 'relative' }}>
      <textarea
        ref={textareaRef}
        className={className ?? 'o-textarea'}
        style={{ minHeight, width: '100%', resize: 'vertical' }}
        value={value}
        maxLength={maxLength}
        placeholder={placeholder}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
      />

      {/* Contador de caracteres */}
      {maxLength !== undefined && (
        <div className="o-char-count" style={{ textAlign: 'right', marginTop: 2 }}>
          {value.length}/{maxLength}
        </div>
      )}

      {/* Dica de variáveis */}
      {!value && (
        <div
          style={{
            fontSize: 11,
            color: 'var(--o-sub, #888)',
            marginTop: 3,
            opacity: 0.7,
          }}
        >
          Dica: digite <kbd style={{ fontFamily: 'monospace', padding: '0 3px', borderRadius: 2, background: 'var(--o-b1)', fontSize: 10 }}>/</kbd> para inserir variáveis dinâmicas
        </div>
      )}

      {/* Preview de tokens */}
      {hasTokens && <TokenPreview text={value} variables={variables} />}

      {/* Picker de variáveis */}
      {showPicker && (
        <VariablePicker
          variables={variables}
          filterText={filterText}
          position={pickerPos}
          onSelect={insertVariable}
          onAddCustom={onAddCustomVariable ? handleAddCustom : undefined}
          onClose={() => {
            setShowPicker(false);
            triggerPosRef.current = -1;
          }}
        />
      )}
    </div>
  );
}
