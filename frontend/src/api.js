/**
 * Calls our Django API: api('/trips/'), api('/trips/', { method: 'POST', body: {...} }).
 * Returns the JSON, or throws an Error with a readable message and the status code.
 */
export async function api(path, { method = 'GET', body } = {}) {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })

  if (response.status === 204) return null          // DELETE: no content

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(errorText(data) || response.statusText)
    error.status = response.status                  // 400, 404, 409...
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