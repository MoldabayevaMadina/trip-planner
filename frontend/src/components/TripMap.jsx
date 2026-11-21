import { useEffect } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'

/** A round pin with a number. divIcon = a marker drawn with our own HTML and CSS. */
function numberIcon(number, visited) {
  return L.divIcon({
    className: '',                                     // remove Leaflet's white square
    html: `<div class="pin ${visited ? 'done' : ''}">${number}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],                              // the center of the circle is the point
  })
}

const pickIcon = L.divIcon({
  className: '',
  html: '<div class="pin pick">+</div>',
  iconSize: [30, 30],
  iconAnchor: [15, 15],
})

/** Moves the map to the places of the day (or to the city when the day is empty). */
function FitToPoints({ points, center }) {
  const map = useMap()
  // a text key: the map moves only when the points really change, not on every render
  const key = JSON.stringify({ points, center })

  useEffect(() => {
    const { points: pts, center: c } = JSON.parse(key)
    if (pts.length > 1) map.fitBounds(pts, { padding: [40, 40], maxZoom: 16 })
    else if (pts.length === 1) map.setView(pts[0], 15)
    else map.setView(c, 12)
  }, [map, key])

  return null
}

/** Reports a click on the map. */
function ClickToPick({ onPick }) {
  useMapEvents({
    click(event) {
      onPick([event.latlng.lat, event.latlng.lng])
    },
  })
  return null
}

export default function TripMap({ center, visits, picked, onPick }) {
  const points = visits.map((visit) => [visit.latitude, visit.longitude])

  return (
    <div className="map-wrap">
      <MapContainer center={center} zoom={12} className="map" scrollWheelZoom>
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
          className="dark-tiles"
        />
        <FitToPoints points={points} center={center} />
        <ClickToPick onPick={onPick} />

        {points.length > 1 && (
          <Polyline
            positions={points}
            pathOptions={{ color: '#a78bfa', weight: 4, opacity: 0.85, dashArray: '6 10' }}
          />
        )}

        {visits.map((visit, index) => (
          <Marker key={visit.id} position={[visit.latitude, visit.longitude]} icon={numberIcon(index + 1, visit.visited)}>
            <Popup>
              <b>{visit.name}</b>
              {visit.time && <><br />{visit.time.slice(0, 5)}</>}
              {visit.address && <><br /><small>{visit.address}</small></>}
            </Popup>
          </Marker>
        ))}

        {picked && <Marker position={picked} icon={pickIcon} />}
      </MapContainer>
      <p className="map-hint">Click on the map to add a point by coordinates: a hotel, a meeting place…</p>
    </div>
  )
}