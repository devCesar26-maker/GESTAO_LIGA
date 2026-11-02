import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { pushToast, subscribeToasts } from "../lib/toastBus";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const remove = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeToasts((toast) => {
      setToasts((current) => [...current, toast]);
      window.setTimeout(() => remove(toast.id), 5500);
    });
    return unsubscribe;
  }, [remove]);

  const notify = useCallback((message, variant = "success") => {
    pushToast(message, variant);
  }, []);

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" role="status" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.variant}`}>
            <span className="toast-icon" aria-hidden="true">
              {toast.variant === "success" ? "✓" : "!"}
            </span>
            <p>{toast.message}</p>
            <button
              type="button"
              className="toast-close"
              onClick={() => remove(toast.id)}
              aria-label="Fechar aviso"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
