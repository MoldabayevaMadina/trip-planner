import { formatDay } from '../utils/dates'

/** Cards of the trip days with weather; click selects a day. */
export default function DayStrip({ days, selectedId, onSelect }) {
  return (
    <div className="day-strip">
      {days.map((day, index) => {
        const weather = day.weather
        return (
          <button
            key={day.id}
            type="button"
            className={`day-card ${day.id === selectedId ? 'active' : ''}`}
            onClick={() => onSelect(day.id)}
          >
            <span className="day-num">Day {index + 1}</span>
            <span className="day-date">{formatDay(day.date)}</span>
            <span className="day-icon">{weather?.icon ?? '·'}</span>
            <span className="day-temp">
              {weather?.temp_max != null
                ? `${Math.round(weather.temp_max)}° / ${Math.round(weather.temp_min)}°`
                : 'no data'}
            </span>
            <span className="day-count">
              {day.visits.length} place{day.visits.length === 1 ? '' : 's'}
            </span>
          </button>
        )
      })}
    </div>
  )
}