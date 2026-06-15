'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import PickCard from '@/components/PickCard'
import StatsBar from '@/components/StatsBar'
import PaywallModal from '@/components/PaywallModal'
import type { PicksData, Subscription } from '@/types'

export default function HomePage() {
  const [data, setData] = useState<PicksData | null>(null)
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(true)
  const [showPaywall, setShowPaywall] = useState(false)
  const supabase = createClient()

  const isActive = subscription?.status === 'active' &&
    new Date(subscription.expires_at) > new Date()

  useEffect(() => {
    async function load() {
      // 取推薦資料
      const res = await fetch('/api/picks')
      if (res.ok) setData(await res.json())

      // 取訂閱狀態
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        const { data: sub } = await supabase
          .from('subscriptions')
          .select('*')
          .eq('user_id', user.id)
          .eq('status', 'active')
          .gt('expires_at', new Date().toISOString())
          .order('expires_at', { ascending: false })
          .limit(1)
          .single()
        if (sub) setSubscription(sub)
      }
      setLoading(false)
    }
    load()
  }, [])

  if (loading) return <LoadingSkeleton />

  return (
    <div className="space-y-6">
      {/* 標題 */}
      <div>
        <h1 className="text-2xl font-bold text-white">⚾ 今日 MLB 推薦</h1>
        {data?.generated_at && (
          <p className="text-sm text-gray-500 mt-1">更新時間：{data.generated_at}</p>
        )}
      </div>

      {/* 歷史統計 */}
      {data?.stats && <StatsBar stats={data.stats} />}

      {/* 未訂閱提示 */}
      {!isActive && (
        <div className="bg-green-950/40 border border-green-800/50 rounded-xl px-4 py-3 flex items-center justify-between gap-4">
          <p className="text-sm text-green-300">
            🔒 推薦方向、賠率、注額已隱藏。訂閱後立即查看完整內容。
          </p>
          <button
            onClick={() => setShowPaywall(true)}
            className="shrink-0 text-sm bg-green-600 hover:bg-green-500 text-white px-4 py-1.5 rounded-lg transition"
          >
            解鎖
          </button>
        </div>
      )}

      {/* 推薦列表 */}
      {data?.picks?.length ? (
        <div className="space-y-3">
          {data.picks.map((pick, i) => (
            <PickCard key={i} pick={pick} locked={!isActive || pick.bp === null} />
          ))}
        </div>
      ) : (
        <div className="text-center py-16 text-gray-500">
          <p className="text-4xl mb-3">⚾</p>
          <p>今日尚無推薦，請稍後再查看</p>
        </div>
      )}

      {/* 歷史記錄 */}
      {data?.recent_history?.length ? (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3">近期戰績</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-gray-400 border-collapse">
              <thead>
                <tr className="border-b border-gray-800 text-xs text-gray-600 uppercase">
                  <th className="text-left py-2 pr-4">日期</th>
                  <th className="text-left py-2 pr-4">場次</th>
                  <th className="text-left py-2 pr-4">類型</th>
                  <th className="text-right py-2 pr-4">賠率</th>
                  <th className="text-right py-2">結果</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_history.map((r, i) => (
                  <tr key={i} className="border-b border-gray-900 hover:bg-gray-900/50">
                    <td className="py-2 pr-4 whitespace-nowrap">{r.date}</td>
                    <td className="py-2 pr-4">{r.away_cn} @ {r.home_cn}</td>
                    <td className="py-2 pr-4">{r.bet_type} {r.label}</td>
                    <td className="py-2 pr-4 text-right">{r.price?.toFixed(2)}</td>
                    <td className="py-2 text-right">
                      <span className={
                        r.result === 'W' ? 'text-green-400 font-bold' :
                        r.result === 'L' ? 'text-red-400' :
                        r.result === 'P' ? 'text-yellow-400' : 'text-gray-600'
                      }>
                        {r.result === 'W' ? '✓ 贏' :
                         r.result === 'L' ? '✗ 輸' :
                         r.result === 'P' ? '－平' : '待定'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {showPaywall && <PaywallModal onClose={() => setShowPaywall(false)} />}
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 w-48 bg-gray-800 rounded" />
      <div className="h-24 bg-gray-900 rounded-xl" />
      {[1, 2, 3].map(i => (
        <div key={i} className="h-28 bg-gray-900 rounded-xl" />
      ))}
    </div>
  )
}
