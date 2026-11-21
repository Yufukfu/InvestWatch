import { createContext, useContext } from 'react';

export type AlertSlot = { node: HTMLElement | null; setNode: (node: HTMLElement | null) => void };

// Where the alert toasts are drawn. Normally none: they sit in the header. While the detail dialog is
// open, the dialog registers its own element here, so the toasts sit inside the modal (the page behind
// it is inert, and the toasts must stay reachable and announced). Provided by `ToastSlotProvider`.
export const AlertSlotContext = createContext<AlertSlot>({ node: null, setNode: () => undefined });

export function useAlertSlot(): AlertSlot {
  return useContext(AlertSlotContext);
}
