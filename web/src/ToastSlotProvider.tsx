import { useMemo, useState, type ReactNode } from 'react';
import { AlertSlotContext } from './alertSlot';

// Holds the alert slot (see `alertSlot.ts`). Mounted once, in the app root.
export function ToastSlotProvider({ children }: { children: ReactNode }) {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const value = useMemo(() => ({ node, setNode }), [node]);
  return <AlertSlotContext.Provider value={value}>{children}</AlertSlotContext.Provider>;
}
