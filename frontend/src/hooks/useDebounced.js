import { useEffect, useState } from 'react'

/**
 * Returns `value`, but only after it has not changed for `delay` ms.
 * Typing "starbucks" sends one request instead of nine.
 */
export function useDebounced(value, delay) {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)      // a new letter cancels the previous timer
  }, [value, delay])

  return debounced
}