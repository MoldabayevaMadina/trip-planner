import { useEffect, useState } from 'react'
import { api } from '../api'

/**
 * Loads `path` from the API and loads it again when the path changes
 * (for example when a filter changes the query string).
 * Returns { data, error, loading, reload }.
 */
export function useApi(path) {
  const [result, setResult] = useState({ path: null, data: null, error: null })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let ignore = false   // an old, slow answer must not overwrite a newer one
    api(path)
      .then((data) => { if (!ignore) setResult({ path, data, error: null }) })
      .catch((error) => { if (!ignore) setResult({ path, data: null, error }) })
    return () => { ignore = true }
  }, [path, version])

  const isCurrent = result.path === path   // the result belongs to the path we show now
  return {
    data: isCurrent ? result.data : null,
    error: isCurrent ? result.error : null,
    loading: !isCurrent,
    reload: () => setVersion((v) => v + 1),   // load again after a change (delete, save...)
  }
}