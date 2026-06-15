import type { Pick } from '@/types'

interface PickCardProps {
  pick: Pick
  locked: boolean
}

const BET_LABEL: Record<string, string> = {
  '獨贏': 'ML',
  '讓分': 'RL',
  '大小分': 'TOT',
}

export default function PickCard({ pick, locked }: PickCardProps) {
  const betShort = BET_LABEL[pick.bet_type] || pick.bet_type
  const direction = pick.label || (pick.bet_type === '獨贏' ? '獨贏' : pick.label)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden hover:border-gray-700 transition">
      {/* 場次標題 */}
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div>
          <span className="text-white font-semibold">{pick.away_cn}</span>
          <span className="text-gray-500 mx-2">@</span>
          <span className="text-white font-semibold">{pick.home_cn}</span>
        </div>
        <span className="text-xs text-gray-500">{pick.game_time}</span>
      </div>

      {/* 先發投手 */}
      <div className="px-4 py-2 text-xs text-gray-500 border-b border-gray-800 flex justify-between">
        <span>{pick.away_sp || 'TBD'} {pick.away_sp_era != null ? `(${pick.away_sp_era.toFixed(2)})` : ''}</span>
        <span>vs</span>
        <span>{pick.home_sp || 'TBD'} {pick.home_sp_era != null ? `(${pick.home_sp_era.toFixed(2)})` : ''}</span>
      </div>

      {/* 推薦內容 */}
      <div className="px-4 py-3 relative">
        {locked ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="bg-gray-800 text-gray-400 text-xs px-2 py-0.5 rounded">{betShort}</span>
              <div className="h-5 w-24 bg-gray-800 rounded animate-pulse" />
              <div className="h-5 w-12 bg-gray-800 rounded animate-pulse" />
            </div>
            <div className="flex gap-4 text-xs">
              <div className="h-4 w-16 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 w-16 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 w-16 bg-gray-800 rounded animate-pulse" />
            </div>
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900/60 backdrop-blur-sm rounded">
              <span className="text-sm text-gray-300 flex items-center gap-1">
                🔒 <span>訂閱後查看完整推薦</span>
              </span>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="bg-green-900/50 text-green-400 text-xs px-2 py-0.5 rounded font-medium">{betShort}</span>
              <span className="text-white font-bold">{direction}</span>
              {pick.price && (
                <span className="text-green-400 font-bold">@ {pick.price.toFixed(2)}</span>
              )}
              {pick.book && (
                <span className="text-xs text-gray-500">({pick.book})</span>
              )}
            </div>
            <div className="flex gap-4 text-xs text-gray-400 flex-wrap">
              {pick.edge != null && (
                <span>Edge <span className="text-yellow-400">+{(pick.edge * 100).toFixed(1)}%</span></span>
              )}
              {pick.conf != null && (
                <span>信心 <span className="text-blue-400">{(pick.conf * 100).toFixed(0)}%</span></span>
              )}
              {pick.stake != null && (
                <span>建議注額 <span className="text-white">${pick.stake.toFixed(0)}</span></span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
