'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'

export default function SuccessPage() {
  const [countdown, setCountdown] = useState(5)
  const searchParams = useSearchParams()
  const plan = searchParams.get('plan')

  useEffect(() => {
    const t = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { clearInterval(t); window.location.href = '/'; return 0 }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="max-w-sm mx-auto mt-20 text-center">
      <div className="text-6xl mb-4">🎉</div>
      <h1 className="text-2xl font-bold text-white">付款成功！</h1>
      <p className="text-gray-400 mt-2">
        {plan === 'monthly' ? '月訂閱已啟用' : '單日券已啟用'}，現在可以查看完整推薦了。
      </p>
      <p className="text-sm text-gray-600 mt-6">{countdown} 秒後自動跳轉...</p>
      <Link
        href="/"
        className="mt-4 inline-block bg-green-600 hover:bg-green-500 text-white px-6 py-2.5 rounded-xl transition"
      >
        立即查看推薦
      </Link>
    </div>
  )
}
