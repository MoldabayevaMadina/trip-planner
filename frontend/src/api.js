import { clearTokens, getAccessToken, getRefreshToken, setTokens } from './auth/tokens'

let refreshing = null   // one refresh request at a time, even if several requests got 401 together

/** Gets a new access token with the refresh token. Returns it, or null if the refresh token is bad. */
async function refreshAccess() {
  const refresh = getRefreshToken()
  if (!refresh) return null
  if (!refreshing) {
    refreshing = fetch('/api/auth/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
      .then(async (response) => {
        if (!response.ok) return null
        const data = await response.json()
        setTokens({ access: data.access })
        return data.access
      })
      .catch(() => null)
      .finally(() => { refreshing = null })
  }
  return refreshing
}

/**
 * Calls our Django API: api('/trips/'), api('/trips/', { method: 'POST', body: {...} }).
 * Adds "Authorization: Bearer <access>" automatically. If the server answers 401,
 * gets a new access token with the refresh token and repeats the request once.
 * auth: false — for login and sign up (no token; 401 there means a wrong password).
 * Returns the JSON, or throws an Error with a readable message and the status code.
 */
export async function api(path, { method = 'GET', body, auth = true } = {}) {
  const send = (token) => fetch(`/api${path}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  let response = await send(getAccessToken())

  if (response.status === 401 && auth && getRefreshToken()) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      response = await send(newAccess)            // the same request with the new token
    } else {
      clearTokens()                               // the refresh token expired too: log out
      window.dispatchEvent(new Event('auth:logout'))
    }
  }

  if (response.status === 204) return null          // DELETE: no content

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(errorText(data) || response.statusText)
    error.status = response.status                  // 400, 401, 404, 409...
    error.data = data                               // {"end_date": ["..."]} for form errors
    throw error
  }
  return data
}

/** {"detail": "..."} or {"field": ["msg"]} → one line of text */
function errorText(data) {
  if (!data) return ''
  if (data.detail) return data.detail
  return Object.entries(data)
    .map(([field, messages]) => `${field}: ${[].concat(messages).join(' ')}`)
    .join('; ')
}