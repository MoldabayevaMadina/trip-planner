/**
 * Where the JWT tokens live: localStorage, so a page reload keeps the user logged in.
 * Every access is wrapped in try/catch: storage can be unavailable (private mode, blocked site data).
 */
const ACCESS = 'tp_access'
const REFRESH = 'tp_refresh'

function read(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    if (value) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
  } catch {
    // storage is unavailable: the user stays logged in only until the page is reloaded
  }
}

export const getAccessToken = () => read(ACCESS)
export const getRefreshToken = () => read(REFRESH)

/** setTokens({ access, refresh }) — either of them can be left out */
export function setTokens({ access, refresh }) {
  if (access !== undefined) write(ACCESS, access)
  if (refresh !== undefined) write(REFRESH, refresh)
}

export function clearTokens() {
  write(ACCESS, null)
  write(REFRESH, null)
}