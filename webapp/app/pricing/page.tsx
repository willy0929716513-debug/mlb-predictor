'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { PLANS } from '@/lib/plans'

export default function PricingPage() {
  const router = useRouter()
  const [loading, setLoading] = useState<string | null>(null)
  const [agreed, setAgreed] = useState(false)

  const handleCheckout = async (plan: 'monthly' | 'day_pass') => {
    setLoading(plan)
    try {
      const res = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan }),
      })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else if (res.status === 401) {
        router.push('/login?next=/pricing')
      }
    } catch {
      alert('結帳發生錯誤，請稍後再試')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="max-w-2xl mx-auto mt-8">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-white">方案選擇</h1>
        <p className="text-gray-400 mt-2">解鎖量化模型每日 MLB 推薦</p>
      </div>

      {/* 免責聲明 */}
      <div className="bg-yellow-950/30 border border-yellow-800/40 rounded-xl px-4 py-3 text-xs text-gray-500 mb-6">
        <p className="font-semibold text-yellow-500/80 mb-1">⚠️ 免責聲明</p>
        <p>
          本網站提供之 MLB 投注推薦<strong className="text-gray-400">僅供參考</strong>，不構成任何財務或投資建議。
          過去績效不代表未來表現，運動投注本質上涉及本金虧損風險。
          請確認您所在地區合法進行體育投注，並量力而為、理性下注。
          使用本服務即代表您已充分了解上述風險，並自行承擔所有相關投注決策責任。
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        {/* 月訂閱 */}
        <div className="bg-gray-900 border-2 border-green-700 rounded-2xl p-6 relative">
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-green-600 text-white text-xs px-3 py-0.5 rounded-full">
            推薦
          </div>
          <h2 className="text-xl font-bold text-white">{PLANS.monthly.name}</h2>
          <div className="mt-3 mb-4">
            <span className="text-4xl font-bold text-white">NT${PLANS.monthly.price}</span>
            <span className="text-gray-400 text-sm">/月</span>
          </div>
          <p className="text-sm text-gray-400 mb-4">{PLANS.monthly.description}</p>
          <ul className="space-y-2 mb-6">
            {PLANS.monthly.features.map(f => (
              <li key={f} className="flex items-center gap-2 text-sm text-gray-300">
                <span className="text-green-400">✓</span> {f}
              </li>
            ))}
          </ul>
          <button
            onClick={() => handleCheckout('monthly')}
            disabled={!!loading || !agreed}
            className="w-full bg-green-600 hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-xl transition"
          >
            {loading === 'monthly' ? '處理中...' : '立即訂閱'}
          </button>
        </div>

        {/* 單日券 */}
        <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
          <h2 className="text-xl font-bold text-white">{PLANS.day_pass.name}</h2>
          <div className="mt-3 mb-4">
            <span className="text-4xl font-bold text-white">NT${PLANS.day_pass.price}</span>
            <span className="text-gray-400 text-sm">/天</span>
          </div>
          <p className="text-sm text-gray-400 mb-4">{PLANS.day_pass.description}</p>
          <ul className="space-y-2 mb-6">
            {PLANS.day_pass.features.map(f => (
              <li key={f} className="flex items-center gap-2 text-sm text-gray-300">
                <span className="text-green-400">✓</span> {f}
              </li>
            ))}
          </ul>
          <button
            onClick={() => handleCheckout('day_pass')}
            disabled={!!loading || !agreed}
            className="w-full bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-xl transition"
          >
            {loading === 'day_pass' ? '處理中...' : '購買單日券'}
          </button>
        </div>
      </div>

      {/* 免責聲明同意 */}
      <label className="flex items-start gap-2.5 mt-6 cursor-pointer group">
        <input
          type="checkbox"
          checked={agreed}
          onChange={e => setAgreed(e.target.checked)}
          className="mt-0.5 h-4 w-4 shrink-0 accent-green-500 cursor-pointer"
        />
        <span className="text-xs text-gray-500 group-hover:text-gray-400 transition leading-relaxed">
          我已閱讀並同意上方<span className="text-gray-300">免責聲明</span>——本服務推薦僅供參考，不構成財務建議，運動投注涉及風險，本人自行承擔所有投注決策責任
        </span>
      </label>

      <p className="text-center text-xs text-gray-600 mt-4">
        透過 Stripe 安全付款 · 月訂閱可隨時取消 · 如有問題請聯繫客服
      </p>
    </div>
  )
}
