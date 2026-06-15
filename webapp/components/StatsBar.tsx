import type { Stats } from '@/types'

export default function StatsBar({ stats }: { stats: Stats }) {
  const { settled, wins, win_rate, roi, by_type } = stats
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex flex-wrap gap-6 justify-center text-center">
        <Stat label="總記錄" value={`${wins}勝/${settled}場`} />
        <Stat label="勝率" value={`${win_rate.toFixed(1)}%`} highlight={win_rate >= 60} />
        <Stat label="ROI" value={`${roi > 0 ? '+' : ''}${roi.toFixed(1)}%`} highlight={roi > 0} />
        {by_type.ML && <Stat label="ML" value={`${by_type.ML.win_rate.toFixed(0)}%`} sub={`ROI ${by_type.ML.roi > 0 ? '+' : ''}${by_type.ML.roi.toFixed(0)}%`} />}
        {by_type.RL && <Stat label="RL(讓分)" value={`${by_type.RL.win_rate.toFixed(0)}%`} sub={`ROI ${by_type.RL.roi > 0 ? '+' : ''}${by_type.RL.roi.toFixed(0)}%`} />}
        {by_type.TOT && <Stat label="大小分" value={`${by_type.TOT.win_rate.toFixed(0)}%`} sub={`ROI ${by_type.TOT.roi > 0 ? '+' : ''}${by_type.TOT.roi.toFixed(0)}%`} />}
      </div>
    </div>
  )
}

function Stat({ label, value, sub, highlight }: {
  label: string; value: string; sub?: string; highlight?: boolean
}) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={`text-lg font-bold ${highlight ? 'text-green-400' : 'text-white'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
    </div>
  )
}
