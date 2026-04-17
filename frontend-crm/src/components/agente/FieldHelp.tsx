import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

export function FieldHelp({ text }: { text: string }) {
  return (
    <Tooltip delayDuration={150}>
      <TooltipTrigger asChild>
        <span style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 13, height: 13, borderRadius: '50%',
          border: '1px solid var(--o-dim)', color: 'var(--o-dim)',
          fontSize: 8, fontFamily: 'DM Mono, monospace', fontWeight: 600,
          cursor: 'help', marginLeft: 5, verticalAlign: 'middle',
          flexShrink: 0, lineHeight: 1, userSelect: 'none',
        }} onClick={e => e.stopPropagation()}>?</span>
      </TooltipTrigger>
      <TooltipContent style={{ maxWidth: 280, fontSize: 11.5, lineHeight: 1.5 }}>
        {text}
      </TooltipContent>
    </Tooltip>
  );
}
