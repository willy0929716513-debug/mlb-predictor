'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import type { User } from '@supabase/supabase-js'

export default function Header() {
  const [user, setUser] = useState<User | null>(null)
  const supabase = createClient()

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user))
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_, session) => {
      setUser(session?.user ?? null)
    })
    return () => subscription.unsubscribe()
  }, [])

  const signOut = async () => {
    await supabase.auth.signOut()
    window.location.href = '/'
  }

  return (
    <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-bold text-white">
          <span className="text-xl">⚾</span>
          <span>MLB Predictor</span>
        </Link>
        <nav className="flex items-center gap-4">
          <Link href="/pricing" className="text-sm text-gray-400 hover:text-white transition">
            方案
          </Link>
          {user ? (
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-400 hidden sm:block">{user.email}</span>
              <button
                onClick={signOut}
                className="text-sm text-gray-400 hover:text-white transition"
              >
                登出
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="text-sm bg-green-600 hover:bg-green-500 text-white px-3 py-1.5 rounded-md transition"
            >
              登入
            </Link>
          )}
        </nav>
      </div>
    </header>
  )
}
