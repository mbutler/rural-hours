import { useState, useEffect, useRef, useMemo } from 'react'
import maplibregl from 'maplibre-gl'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

const OTSEGO_BOUNDS = [[-75.3, 42.4], [-74.6, 42.9]]
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json'

function App() {
  const [observations, setObservations] = useState([])
  const [occurrences, setOccurrences] = useState({ type: 'FeatureCollection', features: [] })
  const [selectedSpecies, setSelectedSpecies] = useState(null)
  const [loading, setLoading] = useState(true)
  const mapContainer = useRef(null)
  const map = useRef(null)
  const [mapReady, setMapReady] = useState(false)

  // Fetch data
  useEffect(() => {
    Promise.all([
      fetch('/data/observations.json').then(r => r.json()),
      fetch('/data/occurrences.geojson').then(r => r.json()),
    ])
      .then(([obs, occ]) => {
        setObservations(obs)
        setOccurrences(occ)
      })
      .catch(err => console.error('Failed to load data:', err))
      .finally(() => setLoading(false))
  }, [])

  // Unique species with taxonomy (prefer those with GBIF linkage)
  const speciesList = useMemo(() => {
    const seen = new Map()
    for (const o of observations) {
      const name = o.plant_name_mentioned
      if (!seen.has(name)) {
        seen.set(name, {
          name,
          scientific: o.accepted_scientific_name,
          family: o.family,
          hasGbif: !!o.gbif_usage_key,
        })
      }
    }
    return Array.from(seen.values()).sort((a, b) => a.name.localeCompare(b.name))
  }, [observations])

  // Selected species context: first observation (quote, date, citation)
  const selectedContext = useMemo(() => {
    if (!selectedSpecies) return null
    const obs = observations.filter(o => o.plant_name_mentioned === selectedSpecies)
    if (!obs.length) return null
    const first = obs[0]
    return {
      quote: first.quote,
      chunkSource: first.chunk_source,
      observationDate: first.observation_date,
      scientific: first.accepted_scientific_name,
      family: first.family,
      citation: first.citation,
      entryDate: first.entry_date,
      allQuotes: obs.map(o => o.quote),
    }
  }, [selectedSpecies, observations])

  // Filtered occurrences for map (by selected species)
  const filteredOccurrences = useMemo(() => {
    const feats = occurrences.features || []
    if (!selectedSpecies) return { ...occurrences, features: feats }
    return {
      type: 'FeatureCollection',
      features: feats.filter(f => f.properties?.plant_name === selectedSpecies),
    }
  }, [occurrences, selectedSpecies])

  // Phenology chart data: DOY on x-axis, source band on y (0=Susan, 1=historical, 2=midcentury, 3=modern)
  const phenologyData = useMemo(() => {
    const susanPoints = observations
      .filter(o => o.plant_name_mentioned === selectedSpecies && o.day_of_year)
      .map(o => ({
        day_of_year: o.day_of_year,
        y: 0,
        source: "Susan",
        phenological_event: o.phenological_event,
        label: o.quote?.slice(0, 50) + (o.quote?.length > 50 ? '…' : ''),
      }))
    const histPoints = (occurrences.features || [])
      .filter(f => f.properties?.plant_name === selectedSpecies && f.properties?.day_of_year && f.properties?.record_type === 'historical')
      .map(f => ({
        day_of_year: f.properties.day_of_year,
        y: 1,
        source: 'Historical',
        year: f.properties.year,
      }))
    const midPoints = (occurrences.features || [])
      .filter(f => f.properties?.plant_name === selectedSpecies && f.properties?.day_of_year && f.properties?.record_type === 'midcentury')
      .map(f => ({
        day_of_year: f.properties.day_of_year,
        y: 2,
        source: 'Midcentury',
        year: f.properties.year,
      }))
    const modPoints = (occurrences.features || [])
      .filter(f => f.properties?.plant_name === selectedSpecies && f.properties?.day_of_year && f.properties?.record_type === 'modern')
      .map(f => ({
        day_of_year: f.properties.day_of_year,
        y: 3,
        source: 'Modern',
        year: f.properties.year,
      }))
    return { susan: susanPoints, historical: histPoints, midcentury: midPoints, modern: modPoints }
  }, [observations, occurrences, selectedSpecies])

  // MapLibre init and update
  useEffect(() => {
    if (!mapContainer.current || loading) return
    if (map.current) return

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
      bounds: OTSEGO_BOUNDS,
      fitBoundsOptions: { padding: 40 },
    })
    map.current.addControl(new maplibregl.NavigationControl(), 'top-right')

    map.current.on('load', () => {
      const m = map.current
      m.resize()
      setMapReady(true)
      if (!m.getSource('occurrences')) {
        m.addSource('occurrences', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      }
      if (!m.getLayer('occ-historical')) {
        m.addLayer({
          id: 'occ-historical',
          type: 'circle',
          source: 'occurrences',
          filter: ['==', ['get', 'record_type'], 'historical'],
          paint: {
            'circle-radius': 6,
            'circle-color': '#c17f59',
            'circle-stroke-width': 1,
            'circle-stroke-color': '#fff',
          },
        })
      }
      if (!m.getLayer('occ-midcentury')) {
        m.addLayer({
          id: 'occ-midcentury',
          type: 'circle',
          source: 'occurrences',
          filter: ['==', ['get', 'record_type'], 'midcentury'],
          paint: {
            'circle-radius': 6,
            'circle-color': '#a67c52',
            'circle-stroke-width': 1,
            'circle-stroke-color': '#fff',
          },
        })
      }
      if (!m.getLayer('occ-modern')) {
        m.addLayer({
          id: 'occ-modern',
          type: 'circle',
          source: 'occurrences',
          filter: ['==', ['get', 'record_type'], 'modern'],
          paint: {
            'circle-radius': 6,
            'circle-color': '#8b7355',
            'circle-stroke-width': 1,
            'circle-stroke-color': '#fff',
          },
        })
      }

      const popup = new maplibregl.Popup({ offset: 15 })
      const recordTypeLabel = (t) => ({ historical: 'Historical', midcentury: 'Midcentury (1900–1980)', modern: 'Modern' }[t] || t)
      m.on('click', e => {
        const features = m.queryRenderedFeatures(e.point, {
          layers: ['occ-historical', 'occ-midcentury', 'occ-modern'],
        })
        if (features.length > 0) {
          const f = features[0]
          const p = f.properties || {}
          if (p.plant_name) setSelectedSpecies(p.plant_name)
          const html = `
            <div style="font-size:13px;min-width:180px">
              <p style="font-weight:600;color:#2C5530;margin:0">${p.plant_name || '—'}</p>
              ${p.scientific_name ? `<p style="color:#4b5563;font-style:italic;margin:4px 0 0">${p.scientific_name}</p>` : ''}
              <p style="margin:6px 0 0">${recordTypeLabel(p.record_type)} record</p>
              ${p.event_date ? `<p style="margin:2px 0 0">${String(p.event_date).slice(0, 10)}</p>` : ''}
              ${p.year ? `<p style="margin:2px 0 0">Year: ${p.year}</p>` : ''}
            </div>
          `
          popup.setLngLat(e.lngLat).setHTML(html).addTo(m)
        }
      })
      m.on('mouseenter', ['occ-historical', 'occ-midcentury', 'occ-modern'], () => { m.getCanvas().style.cursor = 'pointer' })
      m.on('mouseleave', ['occ-historical', 'occ-midcentury', 'occ-modern'], () => { m.getCanvas().style.cursor = '' })
    })
  }, [loading])

  // Update map source when data or map ready; fit bounds to filtered points when species selected
  useEffect(() => {
    if (!mapReady) return
    const m = map.current
    if (!m?.getSource) return
    m.resize()
    const src = m.getSource('occurrences')
    if (src) src.setData(filteredOccurrences)
    const feats = filteredOccurrences.features || []
    if (feats.length > 0) {
      const bbox = feats.reduce(
        ([minLng, minLat, maxLng, maxLat], f) => {
          const [lng, lat] = f.geometry?.coordinates || [0, 0]
          return [
            Math.min(minLng, lng),
            Math.min(minLat, lat),
            Math.max(maxLng, lng),
            Math.max(maxLat, lat),
          ]
        },
        [Infinity, Infinity, -Infinity, -Infinity]
      )
      if (bbox[0] !== Infinity) {
        m.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 50, maxZoom: 14 })
      }
    } else if (selectedSpecies) {
      m.fitBounds(OTSEGO_BOUNDS, { padding: 40 })
    }
  }, [filteredOccurrences, mapReady, selectedSpecies])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA]">
        <p className="text-[#2C5530] font-medium">Loading data…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-[320px_1fr] grid-rows-[auto_1fr] lg:grid-rows-[auto_minmax(0,1fr)]">
      {/* Header */}
      <header className="col-span-full bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-xl font-semibold text-[#2C5530]">Rural Hours</h1>
        <p className="text-sm text-gray-600 mt-1 max-w-2xl">
          An Extended Specimen Network linking Susan Fenimore Cooper&apos;s 19th-century phenological observations
          from <em>Rural Hours</em> (Cooperstown, NY) with historical and modern herbarium records from GBIF.
        </p>
      </header>

      {/* Sidebar */}
      <aside className="lg:col-span-1 border-b lg:border-b-0 lg:border-r border-gray-200 bg-white p-6 flex flex-col gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Species</label>
          <select
            value={selectedSpecies ?? ''}
            onChange={e => setSelectedSpecies(e.target.value || null)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-[#2C5530] focus:border-[#2C5530]"
          >
            <option value="">All species</option>
            {speciesList.map(s => (
              <option key={s.name} value={s.name}>
                {s.name}
                {s.scientific ? ` (${s.scientific})` : ''}
              </option>
            ))}
          </select>
        </div>

        {selectedContext && (
          <div className="space-y-3">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Susan&apos;s observation</p>
              <blockquote
                className="mt-2 text-[#4A4A4A] italic"
                style={{ fontFamily: 'var(--font-serif)' }}
              >
                &ldquo;{selectedContext.quote}&rdquo;
              </blockquote>
              <p className="text-xs text-gray-500 mt-2">
                {selectedContext.entryDate && (
                  <span>Entry: {selectedContext.entryDate}</span>
                )}
                {selectedContext.citation && (
                  <span className="block mt-0.5 text-gray-400">
                    {selectedContext.citation}
                  </span>
                )}
              </p>
            </div>
            <div className="pt-2 border-t border-gray-100">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Modern taxonomy</p>
              <p className="mt-1 text-sm font-medium">
                {selectedContext.scientific || '—'}
              </p>
              {selectedContext.family && (
                <p className="text-xs text-gray-500">{selectedContext.family}</p>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* Main: Map + Chart */}
      <main className="lg:col-span-1 flex flex-col min-h-[600px]">
        <div className="h-[400px] flex-shrink-0 relative bg-gray-100">
          <div ref={mapContainer} className="absolute inset-0 w-full h-full" />
          <div className="absolute bottom-4 left-4 flex flex-wrap gap-2 text-xs">
            <span className="bg-white/90 px-2 py-1 rounded shadow-sm">
              <span className="inline-block w-2 h-2 rounded-full bg-[#c17f59] mr-1.5" />
              Historical (1840–1900)
            </span>
            <span className="bg-white/90 px-2 py-1 rounded shadow-sm">
              <span className="inline-block w-2 h-2 rounded-full bg-[#a67c52] mr-1.5" />
              Midcentury (1900–1980)
            </span>
            <span className="bg-white/90 px-2 py-1 rounded shadow-sm">
              <span className="inline-block w-2 h-2 rounded-full bg-[#8b7355] mr-1.5" />
              Modern (1980+)
            </span>
          </div>
        </div>

        <div className="border-t border-gray-200 bg-white p-6">
          <h2 className="text-sm font-medium text-gray-700 mb-4">
            Phenology: Day of Year — {selectedSpecies ? selectedSpecies : 'Select a species'}
          </h2>
          {selectedSpecies && (phenologyData.susan.length + phenologyData.historical.length + phenologyData.midcentury.length + phenologyData.modern.length) > 0 ? (
            <div className="w-full min-h-[256px] h-64">
              <ResponsiveContainer width="100%" height={256}>
                <ScatterChart margin={{ top: 10, right: 20, left: 130, bottom: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    type="number"
                    dataKey="day_of_year"
                    name="Day of Year"
                    domain={[1, 365]}
                    tick={{ fontSize: 11 }}
                    label={{ value: 'Day of Year', position: 'bottom', fontSize: 11 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    domain={[-0.5, 3.5]}
                    ticks={[0, 1, 2, 3]}
                    tickFormatter={(v) => ['Susan (1850)', 'GBIF Historical', 'GBIF Midcentury', 'GBIF Modern'][v] ?? ''}
                    tick={{ fontSize: 11 }}
                    width={120}
                    interval={0}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    contentStyle={{ fontSize: 12 }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const susanItems = payload.filter(p => p.payload?.source === 'Susan')
                      const others = payload.filter(p => p.payload?.source !== 'Susan')
                      const doy = payload[0]?.payload?.day_of_year
                      return (
                        <div style={{ padding: '4px 8px', minWidth: 140 }}>
                          <div style={{ fontWeight: 600, marginBottom: 4 }}>Day {doy}</div>
                          {susanItems.length > 0 && (
                            <div style={{ marginBottom: 4 }}>
                              <div style={{ fontSize: 10, color: '#6b7280', marginBottom: 2 }}>Susan</div>
                              <div>{susanItems[0].payload.label}</div>
                              {susanItems.length > 1 && (
                                <div style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>
                                  +{susanItems.length - 1} more observation{susanItems.length > 2 ? 's' : ''}
                                </div>
                              )}
                            </div>
                          )}
                          {others.map((p, i) => (
                            <div key={i} style={{ fontSize: 10, color: '#6b7280' }}>
                              {p.payload.source}: {p.payload.year || '—'}
                            </div>
                          ))}
                        </div>
                      )
                    }}
                  />
                  <Legend layout="horizontal" align="center" verticalAlign="bottom" wrapperStyle={{ paddingTop: 8 }} />
                  <Scatter name="Susan (1850)" data={phenologyData.susan} fill="#2C5530" shape="circle" />
                  <Scatter name="GBIF Historical" data={phenologyData.historical} fill="#c17f59" shape="circle" />
                  <Scatter name="GBIF Midcentury" data={phenologyData.midcentury} fill="#a67c52" shape="circle" />
                  <Scatter name="GBIF Modern" data={phenologyData.modern} fill="#8b7355" shape="circle" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-gray-500 py-8 text-center">
              {selectedSpecies
                ? 'No phenology data for this species.'
                : 'Select a species to compare Susan\'s phenological observations with GBIF records.'}
            </p>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
