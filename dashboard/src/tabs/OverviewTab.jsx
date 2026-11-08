import { useMemo } from 'react'
import LiveStatus from '../components/LiveStatus'
import HistoricalExplorer from '../components/HistoricalExplorer'
import { zipColumns } from '../lib/data'

export default function OverviewTab({ data }) {
  const history = useMemo(() => zipColumns(data.history), [data.history])
  return (
    <>
      <LiveStatus dailySlim={data.latest || []} />
      <HistoricalExplorer history={history} era1Monthly={data.era1Monthly || []} era2CorridorCorr={data.era2CorridorCorr || []} />
    </>
  )
}
