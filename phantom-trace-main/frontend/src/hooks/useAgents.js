import { useState, useEffect } from 'react'

export function useAgents(threadId = 'default') {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch(
          `http://localhost:8000/api/agents?thread_id=${threadId}`
        )
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`)
        }
        const data = await response.json()
        setAgents(data.agents || [])
      } catch (err) {
        console.error('Error fetching agents:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchAgents()
  }, [threadId])

  return { agents, loading, error }
}
