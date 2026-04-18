import type React from 'react';

function onTabFill<T extends HTMLInputElement | HTMLTextAreaElement>(
  e: React.KeyboardEvent<T>,
  onChange?: React.ChangeEventHandler<T>,
  onKeyDown?: React.KeyboardEventHandler<T>,
) {
  if (e.key === 'Tab') {
    const el = e.currentTarget;
    if (!el.value && el.placeholder) {
      e.preventDefault();
      onChange?.({ target: { value: el.placeholder } } as React.ChangeEvent<T>);
      requestAnimationFrame(() => el.select());
      return;
    }
  }
  onKeyDown?.(e);
}

export function SuggestInput({ onKeyDown, onChange, ...rest }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      onChange={onChange}
      onKeyDown={e => onTabFill(e, onChange as React.ChangeEventHandler<HTMLInputElement>, onKeyDown as React.KeyboardEventHandler<HTMLInputElement>)}
    />
  );
}

export function SuggestTextarea({ onKeyDown, onChange, ...rest }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...rest}
      onChange={onChange}
      onKeyDown={e => onTabFill(e, onChange as React.ChangeEventHandler<HTMLTextAreaElement>, onKeyDown as React.KeyboardEventHandler<HTMLTextAreaElement>)}
    />
  );
}
