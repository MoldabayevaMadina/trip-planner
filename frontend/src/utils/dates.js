const DAY = 86_400_000
const short = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
const full = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

/** "2026-11-20" → a Date at local midnight (without "T00:00" it would be UTC) */
const parse = (value) => new Date(`${value}T00:00`)

export const formatDate = (value) => full.format(parse(value))

export const formatRange = (start, end) => `${short.format(parse(start))} – ${full.format(parse(end))}`

export const tripDays = (start, end) => Math.round((parse(end) - parse(start)) / DAY) + 1

/** "In 5 days" / "Tomorrow" / "Now" / "Finished" */
export function countdown(start, end) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  if (parse(end) < today) return 'Finished'
  const toStart = Math.round((parse(start) - today) / DAY)
  if (toStart > 1) return `In ${toStart} days`
  if (toStart === 1) return 'Tomorrow'
  return 'Now'
}

const dayShort = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
const dayLong = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

/** "Fri 20 Nov" */
export const formatDay = (value) => dayShort.format(parse(value))

/** "Friday, 20 November" */
export const formatDayLong = (value) => dayLong.format(parse(value))