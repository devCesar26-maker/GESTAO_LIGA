/**
 * Read-only helpers for the cookies the API sets.
 *
 * The session itself lives in HttpOnly cookies, which JavaScript cannot read.
 * Only the CSRF token is readable, because axios has to echo it in the
 * X-CSRFToken header.
 */
const CSRF_COOKIE = "csrftoken";

export function readCookie(name) {
  const prefix = `${name}=`;
  const found = document.cookie
    .split("; ")
    .find((part) => part.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : "";
}

export function getCsrfToken() {
  return readCookie(CSRF_COOKIE);
}
