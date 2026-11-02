const listeners = new Set();
let pending = [];

let counter = 0;

function makeToast(message, variant) {
  counter += 1;
  return { id: `toast-${Date.now()}-${counter}`, message, variant };
}

/** Show a toast from anywhere (including the axios interceptor). */
export function pushToast(message, variant = "error") {
  if (!message) return;
  const toast = makeToast(message, variant);
  if (listeners.size === 0) {
    pending.push(toast);
    return;
  }
  listeners.forEach((listener) => listener(toast));
}

/** Subscribe the ToastProvider; flushes messages queued before mount. */
export function subscribeToasts(listener) {
  listeners.add(listener);
  if (pending.length > 0) {
    const queued = pending;
    pending = [];
    queued.forEach((toast) => listener(toast));
  }
  return () => listeners.delete(listener);
}
