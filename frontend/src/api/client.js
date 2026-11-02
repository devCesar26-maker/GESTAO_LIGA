import axios from "axios";

import { pushToast } from "../lib/toastBus";
import { getCsrfToken } from "../lib/session";

// Same origin in production (Django serves the React build) and through the
// Vite proxy in development, so no CORS is involved at all.
const API_URL = import.meta.env.VITE_API_URL || "/api";

const DEFAULT_ERROR = "Não foi possível concluir a ação. Tente novamente em instantes.";
const NETWORK_ERROR =
  "Não consegui falar com o servidor. Verifique se o backend está rodando e tente de novo.";
export const SESSION_EXPIRED_MESSAGE = "Sua sessão expirou. Entre novamente para continuar.";

export const api = axios.create({
  baseURL: API_URL,
  // The session cookie must travel with every API call.
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
  timeout: 20000,
});

const WRITE_METHODS = new Set(["post", "put", "patch", "delete"]);
const NO_RETRY_PATHS = [
  "/auth/login/",
  "/auth/register/",
  "/auth/refresh/",
  "/auth/logout/",
];

let refreshPromise = null;
let sessionExpiredHandler = null;

/** Registered by AuthProvider to reset local state / redirect to login. */
export function setSessionExpiredHandler(handler) {
  sessionExpiredHandler = handler;
}

let csrfPromise = null;

function ensureCsrfToken() {
  if (!csrfPromise) {
    // Only reached when the cookie is missing (e.g. Django started after the
    // page loaded, or the boot request failed). GET is a safe method, so this
    // cannot recurse into itself.
    csrfPromise = api
      .get("/auth/csrf/", { __silent: true })
      .finally(() => {
        csrfPromise = null;
      });
  }
  return csrfPromise;
}

function refreshSession() {
  if (!refreshPromise) {
    // Single-flight: simultaneous 401s share one rotation request, because the
    // refresh token is single use (rotation + blacklist of the previous one).
    refreshPromise = api
      .post("/auth/refresh/", {}, { __skipAuthRetry: true, __silent: true })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

api.interceptors.request.use(async (config) => {
  const method = String(config.method || "get").toLowerCase();
  if (!WRITE_METHODS.has(method)) return config;

  let token = getCsrfToken();
  if (!token) {
    try {
      await ensureCsrfToken();
    } catch {
      // Without a token the server answers 403 CSRF_FAILED with a friendly
      // message; nothing else to do here.
    }
    token = getCsrfToken();
  }

  if (token) {
    config.headers = config.headers || {};
    config.headers["X-CSRFToken"] = token;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config || {};
    const response = error.response;
    const code = response?.data?.code;
    const url = String(config.url || "");

    const canRetry =
      response?.status === 401 &&
      !config.__isRetry &&
      !config.__skipAuthRetry &&
      !NO_RETRY_PATHS.some((path) => url.includes(path));

    if (canRetry) {
      try {
        // Renew once and replay the original request with the new cookie.
        await refreshSession();
        config.__isRetry = true;
        return api(config);
      } catch {
        // Fall through: the session is really gone.
      }
    }

    error.apiCode = code;

    if (response?.status === 401) {
      const isBadCredentials = code === "INVALID_CREDENTIALS";
      const message = isBadCredentials
        ? response?.data?.message || DEFAULT_ERROR
        : SESSION_EXPIRED_MESSAGE;
      error.friendlyMessage = message;

      // A silent request (session probe) must not nag visitors on public pages.
      if (!config.__silent) {
        pushToast(message, "error");
        if (!isBadCredentials) sessionExpiredHandler?.(message, code);
      }
      return Promise.reject(error);
    }

    // No response at all means the request never reached the API (backend down
    // or wrong origin) — say that instead of a generic failure.
    const message = response
      ? response.data?.message || DEFAULT_ERROR
      : NETWORK_ERROR;
    error.friendlyMessage = message;
    if (!config.__silent) pushToast(message, "error");
    return Promise.reject(error);
  },
);

export { API_URL };
