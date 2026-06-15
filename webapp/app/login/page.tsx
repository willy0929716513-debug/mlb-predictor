'use client'

import { useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { createClient } from '@/lib/supabase'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const searchParams = useSearchParams()
  const next = searchParams.get('next') || '/'
  const supabase = createClient()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/api/auth/callback?next=${next}` },
    })
    if (error) {
      setError(error.message)
    } else {
      setSent(true)
    }
    setLoading(false)
  }

  return (
    <div className="max-w-sm mx-auto mt-16">
      <div className="text-center mb-8">
        <span className="text-4xl">⚾</span>
        <h1 className="text-2xl font-bold text-white mt-3">登入 MLB Predictor</h1>
        <p className="text-gray-400 text-sm mt-1">輸入 Email，我們寄送一次性登入連結</p>
      </div>

      {sent ? (
        <div className="bg-green-950/50 border border-green-800 rounded-xl p-6 text-center">
          <p className="text-green-300 font-medium">✉️ 登入連結已寄出！</p>
          <p className="text-sm text-gray-400 mt-2">請檢查 <strong>{email}</strong> 的收件匣，點擊連結即可登入。</p>
        </div>
      ) : (
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="your@email.com"
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-green-600"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition"
          >
            {loading ? '寄送中...' : '寄送登入連結'}
          </button>
        </form>
      )}
    </div>
  )
}
