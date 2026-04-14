// ThreatSense — ThreatMap
// Geographic visualization of threat sources using MongoDB-backed threat events

import { useState } from 'react'
import { motion } from 'framer-motion'
import { useThreatMap } from '../hooks/useThreatMap'

export default function ThreatMap() {
  const [selectedMarker, setSelectedMarker] = useState(null)
  const [timeFilter, setTimeFilter] = useState('24h')
  const { locations, threats, loading, error } = useThreatMap('default', timeFilter)

  const mostActiveLocation = locations[0]

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brown-primary">Threat Map</h1>
        <p className="text-brown-secondary text-sm mt-1">Geographic origin of threats</p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="inline-block w-8 h-8 border-4 border-orange-200 border-t-orange-DEFAULT rounded-full animate-spin mb-3"></div>
            <p className="text-brown-secondary">Loading threat map data...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
          <p className="text-sm font-semibold">Error loading threat map</p>
          <p className="text-xs mt-1">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3 mb-6 flex-wrap"
          >
            {['1h', '6h', '24h', '7d'].map((time) => (
              <button
                key={time}
                onClick={() => setTimeFilter(time)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  timeFilter === time
                    ? 'bg-orange-DEFAULT text-white'
                    : 'bg-white border border-border text-brown-primary hover:bg-beige'
                }`}
              >
                {time}
              </button>
            ))}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="card p-0 overflow-hidden rounded-card mb-6 h-80 bg-gradient-to-br from-gray-100 to-gray-200 relative flex items-center justify-center"
          >
            <div className="text-center p-6">
              <p className="text-brown-secondary text-lg font-semibold">World Threat Map</p>
              <p className="text-brown-secondary text-sm mt-2">MongoDB-backed threat locations</p>
              <div className="mt-6 space-y-2 flex flex-wrap justify-center gap-2">
                {locations.map((loc) => (
                  <motion.button
                    key={loc.country}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    onClick={() => setSelectedMarker(selectedMarker === loc.country ? null : loc.country)}
                    className="px-4 py-2 bg-white rounded-lg border border-border cursor-pointer hover:border-orange-DEFAULT transition-colors"
                  >
                    <p className="text-xs font-semibold text-brown-primary">
                      {loc.country} ({loc.count})
                    </p>
                  </motion.button>
                ))}
              </div>
            </div>
          </motion.div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="card"
            >
              <p className="text-brown-secondary text-xs mb-1">Source Countries</p>
              <p className="text-3xl font-bold text-orange-DEFAULT">{locations.length}</p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="card"
            >
              <p className="text-brown-secondary text-xs mb-1">Total Flagged IPs</p>
              <p className="text-3xl font-bold text-orange-DEFAULT">{threats.length}</p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="card col-span-2"
            >
              <p className="text-brown-secondary text-xs mb-1">Most Active Origin</p>
              <p className="text-lg font-bold text-orange-DEFAULT">
                {mostActiveLocation ? `${mostActiveLocation.country} (${mostActiveLocation.count})` : 'N/A'}
              </p>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mt-6"
          >
            <h3 className="font-semibold text-brown-primary mb-4">Threat Locations</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {locations.map((location) => (
                <motion.div
                  key={location.country}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="card cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => setSelectedMarker(selectedMarker === location.country ? null : location.country)}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h4 className="font-semibold text-brown-primary text-lg">{location.country}</h4>
                      <p className="text-sm text-brown-secondary">Detected threats</p>
                    </div>
                    <span className="text-xs px-2 py-1 rounded bg-orange-50 text-orange-700">Multiple</span>
                  </div>
                  <p className="text-sm text-brown-primary">
                    <span className="font-semibold text-orange-DEFAULT">{location.count}</span> threats
                  </p>

                  {selectedMarker === location.country && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      className="mt-4 pt-4 border-t border-border"
                    >
                      <p className="text-xs text-brown-secondary mb-3 font-semibold">Related Events:</p>
                      {threats
                        .filter((threat) => threat.country === location.country)
                        .slice(0, 2)
                        .map((threat) => (
                          <div
                            key={threat._id}
                            className="text-xs text-brown-primary mb-2 p-2 bg-beige rounded"
                          >
                            {threat.log_type} - {threat.source_ip}
                          </div>
                        ))}
                    </motion.div>
                  )}
                </motion.div>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </div>
  )
}
