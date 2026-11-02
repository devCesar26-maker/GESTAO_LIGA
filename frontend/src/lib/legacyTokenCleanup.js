/**
 * One-off cleanup of session material left behind by older builds.
 *
 * The JWT session used to be kept in localStorage, where any XSS could read and
 * exfiltrate it. Tokens now travel only in HttpOnly cookies, so every leftover
 * copy in the browser is a liability and is removed at boot.
 *
 * This is the only module allowed to touch web storage for token keys.
 */
const LEGACY_TOKEN_KEYS = [
  "liga.access",
  "liga.refresh",
  "liga.tokens",
  "token",
  "tokens",
  "access",
  "refresh",
  "access_token",
  "refresh_token",
  "accessToken",
  "refreshToken",
  "jwt",
  "id_token",
  "auth",
];

function purgeFrom(storage) {
  if (!storage) return;
  for (const key of LEGACY_TOKEN_KEYS) {
    try {
      storage.removeItem(key);
    } catch {
      // Storage may be unavailable (private mode / disabled cookies).
    }
  }
}

export function purgeLegacyAuthStorage() {
  if (typeof window === "undefined") return;
  try {
    purgeFrom(window.localStorage);
    purgeFrom(window.sessionStorage);
  } catch {
    // Nothing to clean when storage access is denied.
  }
}
