// ThreatSense — Dashboard
// Main landing page after login
// Shows stats, alert feed, and charts
// Now fetches real data from MongoDB backend

import { motion } from 'framer-motion'
import { AlertTriangle, AlertOctagon, Activity, Cpu } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { useAlerts } from '../hooks/useAlerts'
import { DUMMY_STATS } from '../data/dummyData'
import { AlertFeed } from '../components/alerts/AlertFeed'
import { SeverityGauge } from '../components/charts/SeverityGauge'
import { AlertsOverTime } from '../components/charts/AlertsOverTime'
import { ThreatTypeBar } from '../components/charts/ThreatTypeBar'

export default function Dashboard() {
  const { client } = useAuth()
  
  // Fetch alerts from MongoDB backend
  const { alerts, loading, error, summary } = useAlerts('default')

  // Use real data from MongoDB if available, otherwise fall back to dummy data
  const counts = summary?.counts || DUMMY_STATS.counts
  const logsToday = summary?.logs_today || DUMMY_STATS.logs_today

  const statCards = [
    {
      title: 'Critical Alerts',
      count: counts.critical || 0,
      icon: AlertTriangle,
      color: 'bg-red-100',
      textColor: 'text-red-600',
      trend: `${counts.critical > 0 ? '↑' : '↓'} ${Math.abs(counts.critical)} from yesterday`,
      trendColor: counts.critical > 0 ? 'text-red-600' : 'text-green-600',
    },
    {
      title: 'High Alerts',
      count: counts.high || 0,
      icon: AlertOctagon,
      color: 'bg-orange-100',
      textColor: 'text-orange-600',
      trend: `${counts.high > 0 ? '↑' : '↓'} ${Math.abs(counts.high)} from yesterday`,
      trendColor: counts.high > 0 ? 'text-orange-600' : 'text-green-600',
    },
    {
      title: 'Logs Processed',
      count: logsToday ? logsToday.toLocaleString() : '0',
      icon: Activity,
      color: 'bg-blue-100',
      textColor: 'text-blue-600',
      trend: '↑ 12% from yesterday',
      trendColor: 'text-blue-600',
    },
    {
      title: 'Agents Active',
      count: '5/5',
      icon: Cpu,
      color: 'bg-green-100',
      textColor: 'text-green-600',
      trend: 'All systems operational',
      trendColor: 'text-green-600',
    },
  ]

  return (
    <div>
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brown-primary">Dashboard</h1>
        <p className="text-brown-secondary text-sm mt-1">
          Welcome back, {client?.website_name}
        </p>
      </div>

      {/* Stats cards row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((stat, idx) => {
          const Icon = stat.icon
          return (
            <motion.div
              key={stat.title}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="card"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="text-sm text-brown-secondary font-medium mb-2">{stat.title}</p>
                  <p className={`text-3xl font-bold ${stat.textColor}`}>
                    {stat.count}
                  </p>
                  <p className={`text-xs mt-2 ${stat.trendColor}`}>
                    {stat.trend}
                  </p>
                </div>
                <div className={`p-3 rounded-lg ${stat.color}`}>
                  <Icon className={`w-6 h-6 ${stat.textColor}`} />
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Middle row - Alert feed and gauge */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-8">
        {/* Alert feed (3 columns) */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-3"
        >
          <AlertFeed alerts={alerts} loading={loading} error={error} />
        </motion.div>

        {/* Right column - Gauge and chart */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-2 space-y-6"
        >
          <SeverityGauge />
          <AlertsOverTime />
        </motion.div>
      </div>

      {/* Bottom row - Threat types */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <ThreatTypeBar />
      </motion.div>
    </div>
  )
}
