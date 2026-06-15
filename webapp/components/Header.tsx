'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import type { User } from '@supabase/supabase-js'

export default function Header() {
  const [user, setUser] = useState<User | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const supabase = createClient()

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user))
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_, s) => {
      setUser(s?.user ?? null)
    })
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => { subscription.unsubscribe(); window.removeEventListener('scroll', onScroll) }
  }, [])

  const signOut = async () => {
    await supabase.auth.signOut()
    window.location.href = '/'
  }

  return (
    <header
      className="sticky top-0 z-50 transition-all duration-300"
      style={{
        background: scrolled
          ? 'rgba(2, 6, 23, 0.92)'
          : 'rgba(2, 6, 23, 0.7)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderBottom: scrolled
          ? '1px solid rgba(0,229,255,0.12)'
          : '1px solid rgba(0,229,255,0.06)',
        boxShadow: scrolled ? '0 4px 32px rgba(0,0,0,0.4)' : 'none',
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">

        {/* Logo */}
        <Link
          href="/"
          className="flex items-center gap-2.5 group"
          style={{ textDecoration: 'none' }}
        >
          <div className="relative w-8 h-8 flex items-center justify-center">
            <div
              className="absolute inset-0 rounded-full opacity-60"
              style={{
                background: 'radial-gradient(circle, rgba(0,229,255,0.3), transparent)',
                animation: 'pulse-ring 2.5s ease-out infinite',
              }}
            />
            <span style={{ fontSize: 20 }}>⚾</span>
          </div>
          <div>
            <span
              className="font-bold tracking-tight"
              style={{ fontSize: 16, color: 'var(--text-1)' }}
            >
              MLB{' '}
              <span className="neon-cyan" style={{ fontSize: 16 }}>AI</span>
            </span>
            <span
              className="hidden sm:inline font-medium"
              style={{ fontSize: 16, color: 'var(--text-2)', marginLeft: 4 }}
            >
              Predictions
            </span>
          </div>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1">
          <NavLink href="/">Dashboard</NavLink>
          <NavLink href="/pricing">Pricing</NavLink>
          <div
            className="ml-2 h-5"
            style={{ width: 1, background: 'var(--border)' }}
          />
          {user ? (
            <div className="flex items-center gap-3 ml-2">
              <span
                className="text-sm font-mono truncate max-w-[160px]"
                style={{ color: 'var(--text-2)' }}
              >
                {user.email}
              </span>
              <button
                onClick={signOut}
                className="btn-ghost"
                style={{ minHeight: 36, padding: '0 16px', fontSize: 13 }}
              >
                Sign Out
              </button>
            </div>
          ) : (
            <Link href="/login" className="btn-primary ml-2" style={{ minHeight: 36, padding: '0 18px', fontSize: 13 }}>
              Sign In
            </Link>
          )}
        </nav>

        {/* Mobile menu toggle */}
        <button
          className="md:hidden flex flex-col gap-1.5 p-2 rounded-lg"
          style={{ border: '1px solid var(--border)', minHeight: 40, minWidth: 40, justifyContent: 'center', alignItems: 'center' }}
          onClick={() => setMenuOpen(o => !o)}
          aria-label="Menu"
        >
          <span
            className="block h-0.5 w-5 transition-all duration-200"
            style={{
              background: 'var(--cyan)',
              transform: menuOpen ? 'rotate(45deg) translate(4px, 4px)' : 'none',
            }}
          />
          <span
            className="block h-0.5 w-5 transition-all duration-200"
            style={{
              background: 'var(--cyan)',
              opacity: menuOpen ? 0 : 1,
            }}
          />
          <span
            className="block h-0.5 w-5 transition-all duration-200"
            style={{
              background: 'var(--cyan)',
              transform: menuOpen ? 'rotate(-45deg) translate(4px, -4px)' : 'none',
            }}
          />
        </button>
      </div>

      {/* Mobile Menu */}
      {menuOpen && (
        <div
          className="md:hidden border-t"
          style={{
            background: 'rgba(2, 6, 23, 0.97)',
            borderColor: 'var(--border)',
          }}
        >
          <div className="max-w-7xl mx-auto px-4 py-4 flex flex-col gap-2">
            <MobileNavLink href="/" onClick={() => setMenuOpen(false)}>Dashboard</MobileNavLink>
            <MobileNavLink href="/pricing" onClick={() => setMenuOpen(false)}>Pricing</MobileNavLink>
            <div className="divider-neon my-2" />
            {user ? (
              <>
                <p className="text-xs font-mono px-3 py-1" style={{ color: 'var(--text-2)' }}>
                  {user.email}
                </p>
                <button
                  onClick={() => { setMenuOpen(false); signOut() }}
                  className="btn-ghost"
                  style={{ justifyContent: 'flex-start', padding: '0 12px' }}
                >
                  Sign Out
                </button>
              </>
            ) : (
              <Link
                href="/login"
                className="btn-primary"
                onClick={() => setMenuOpen(false)}
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  )
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200"
      style={{ color: 'var(--text-2)', textDecoration: 'none' }}
      onMouseEnter={e => {
        const el = e.currentTarget
        el.style.color = 'var(--text-1)'
        el.style.background = 'rgba(0,229,255,0.06)'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget
        el.style.color = 'var(--text-2)'
        el.style.background = 'transparent'
      }}
    >
      {children}
    </Link>
  )
}

function MobileNavLink({ href, onClick, children }: { href: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium"
      style={{
        color: 'var(--text-1)',
        textDecoration: 'none',
        border: '1px solid var(--border)',
      }}
    >
      {children}
    </Link>
  )
}
