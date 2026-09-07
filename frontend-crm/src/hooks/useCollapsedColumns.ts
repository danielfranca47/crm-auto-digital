import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "kanban:collapsedColumns";

function readStoredIds(): Set<string> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? new Set(parsed) : new Set();
  } catch {
    return new Set();
  }
}

function writeStoredIds(ids: Set<string>) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(ids)));
  } catch {
    // localStorage indisponível (ex.: modo privado) — colapso vira session-only
  }
}

export function useCollapsedColumns() {
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(() => readStoredIds());

  useEffect(() => {
    writeStoredIds(collapsedIds);
  }, [collapsedIds]);

  const isCollapsed = useCallback(
    (columnId: string) => collapsedIds.has(columnId),
    [collapsedIds]
  );

  const toggle = useCallback((columnId: string) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(columnId)) {
        next.delete(columnId);
      } else {
        next.add(columnId);
      }
      return next;
    });
  }, []);

  const expand = useCallback((columnId: string) => {
    setCollapsedIds((prev) => {
      if (!prev.has(columnId)) return prev;
      const next = new Set(prev);
      next.delete(columnId);
      return next;
    });
  }, []);

  return { isCollapsed, toggle, expand };
}
