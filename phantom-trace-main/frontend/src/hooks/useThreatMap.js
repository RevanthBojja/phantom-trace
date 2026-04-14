import { useState, useEffect } from 'react'

export function useThreatMap(threadId = 'default', timeFilter = '24h') {
  const [locations, setLocations] = useState([])
  const [threats, setThreats] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchThreatMap = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch(
          `http://localhost:8000/api/threat-map?thread_id=${threadId}&time_filter=${timeFilter}`
        )
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`)
        }
        const data = await response.json()
        setLocations(data.locations || [])
        setThreats(data.threats || [])
      } catch (err) {
        console.error('Error fetching threat map:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchThreatMap()
  }, [threadId, timeFilter])

  return { locations, threats, loading, error }
}
