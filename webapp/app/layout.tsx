import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Header from '@/components/Header'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'MLB Predictor — 每日 MLB 投注推薦',
  description: '量化模型驅動的 MLB 每日推薦，勝率 70%+，含 Edge、Kelly 注額計算',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body className={`${inter.className} bg-gray-950 text-white min-h-screen`}>
        <Header />
        <main className="max-w-5xl mx-auto px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  )
}
