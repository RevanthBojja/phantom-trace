// ThreatSense — useAlerts Hook
// Fetches alerts from MongoDB backend and provides loading/error states

import { useState, useEffect } from 'react'

export function useAlerts(threadId = 'default') {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    const fetchAlertsAndSummary = async () => {
      try {
        setLoading(true)
        setError(null)

        // Fetch alerts
        const alertsResponse = await fetch(
          `http://localhost:8000/api/alerts?thread_id=${threadId}&limit=50`
        )
        if (!alertsResponse.ok) {
          throw new Error(`Failed to fetch alerts: ${alertsResponse.statusText}`)
        }
        const alertsData = await alertsResponse.json()
        setAlerts(alertsData.alerts || [])

        // Fetch summary
        const summaryResponse = await fetch(
          `http://localhost:8000/api/alerts/summary?thread_id=${threadId}`
        )
        if (!summaryResponse.ok) {
          throw new Error(`Failed to fetch summary: ${summaryResponse.statusText}`)
        }
        const summaryData = await summaryResponse.json()
        setSummary(summaryData)

      } catch (err) {
        console.error('Error fetching alerts:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchAlertsAndSummary()
  }, [threadId])

  return { alerts, loading, error, summary }
}
