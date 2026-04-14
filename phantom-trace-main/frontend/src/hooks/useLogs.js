// ThreatSense — useLogs Hook
// Fetches raw logs from MongoDB backend for LogExplorer

import { useState, useEffect } from 'react'

export function useLogs(threadId = 'default') {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        setLoading(true)
        setError(null)

        const response = await fetch(
          `http://localhost:8000/api/logs?thread_id=${threadId}&limit=100`
        )
        if (!response.ok) {
          throw new Error(`Failed to fetch logs: ${response.statusText}`)
        }
        const data = await response.json()
        setLogs(data.logs || [])

      } catch (err) {
        console.error('Error fetching logs:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchLogs()
  }, [threadId])

  return { logs, loading, error }
}
