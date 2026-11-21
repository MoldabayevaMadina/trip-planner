/** Label + input + hint or error under it. */
export default function Field({ label, hint, error, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {error
        ? <span className="field-error">{error}</span>
        : hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}