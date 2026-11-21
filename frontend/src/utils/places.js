export const CATEGORIES = [
  ['sight', '🏛 Sight'],
  ['museum', '🖼 Museum'],
  ['food', '🍽 Food'],
  ['walk', '🚶 Walk'],
  ['shopping', '🛍 Shopping'],
  ['other', '📍 Other'],
]

/** {sight: "🏛", museum: "🖼", ...} */
export const CATEGORY_ICONS = Object.fromEntries(
  CATEGORIES.map(([value, label]) => [value, label.split(' ')[0]]),
)