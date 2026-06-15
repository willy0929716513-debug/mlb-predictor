'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { PLANS } from '@/lib/plans'

export default function PaywallModal({ onClose }: { onClose: () => void }) {
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
        router.push('/login?next=pricing')
      }
    } catch {
      alert('結帳發生錯誤，請稍後再試')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl max-w-md w-full p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-500 hover:text-white transition"
        >✕</button>

        <div className="text-center mb-6">
          <span className="text-3xl">⚾</span>
          <h2 className="text-xl font-bold text-white mt-2">解鎖今日推薦</h2>
          <p className="text-sm text-gray-400 mt-1">選擇方案後立即查看完整預測</p>
        </div>

        <div className="space-y-3">
          {/* 月訂閱 */}
          <button
            onClick={() => handleCheckout('monthly')}
            disabled={!!loading || !agreed}
            className="w-full bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed border border-green-600 rounded-xl p-4 text-left transition group"
          >
            <div className="flex justify-between items-start">
              <div>
                <p className="text-white font-bold">{PLANS.monthly.name}</p>
                <p className="text-xs text-green-300 mt-0.5">{PLANS.monthly.description}</p>
                <ul className="mt-2 space-y-0.5">
                  {PLANS.monthly.features.map(f => (
                    <li key={f} className="text-xs text-gray-300">✓ {f}</li>
                  ))}
                </ul>
              </div>
              <div className="text-right shrink-0 ml-4">
                <p className="text-2xl font-bold text-white">NT${PLANS.monthly.price}</p>
                <p className="text-xs text-gray-400">/月</p>
                {loading === 'monthly' && <p className="text-xs text-green-300 mt-1">處理中...</p>}
              </div>
            </div>
          </button>

          {/* 單日券 */}
          <button
            onClick={() => handleCheckout('day_pass')}
            disabled={!!loading || !agreed}
            className="w-full bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed border border-gray-700 rounded-xl p-4 text-left transition"
          >
            <div className="flex justify-between items-start">
              <div>
                <p className="text-white font-bold">{PLANS.day_pass.name}</p>
                <p className="text-xs text-gray-400 mt-0.5">{PLANS.day_pass.description}</p>
                <ul className="mt-2 space-y-0.5">
                  {PLANS.day_pass.features.map(f => (
                    <li key={f} className="text-xs text-gray-400">✓ {f}</li>
                  ))}
                </ul>
              </div>
              <div className="text-right shrink-0 ml-4">
                <p className="text-2xl font-bold text-white">NT${PLANS.day_pass.price}</p>
                <p className="text-xs text-gray-500">/天</p>
                {loading === 'day_pass' && <p className="text-xs text-gray-300 mt-1">處理中...</p>}
              </div>
            </div>
          </button>
        </div>

        {/* 免責聲明同意 */}
        <label className="flex items-start gap-2.5 mt-4 cursor-pointer group">
          <input
            type="checkbox"
            checked={agreed}
            onChange={e => setAgreed(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-green-500 cursor-pointer"
          />
          <span className="text-xs text-gray-500 group-hover:text-gray-400 transition leading-relaxed">
            我已閱讀並同意<span className="text-gray-300">免責聲明</span>——本服務推薦僅供參考，不構成財務建議，運動投注涉及風險，本人自行承擔所有投注決策責任
          </span>
        </label>

        <p className="text-xs text-center text-gray-600 mt-3">
          透過 Stripe 安全付款 · 隨時取消
        </p>
      </div>
    </div>
  )
}
