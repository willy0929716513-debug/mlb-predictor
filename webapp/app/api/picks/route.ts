import { NextResponse } from 'next/server'
import { createClient, createServiceClient } from '@/lib/supabase-server'

export async function GET() {
  try {
    const supabase = await createClient()
    const serviceSupabase = await createServiceClient()

    // 從 Supabase Storage 取得最新推薦
    const { data, error } = await serviceSupabase.storage
      .from('picks')
      .download('picks_latest.json')

    if (error || !data) {
      return NextResponse.json({ error: 'No picks data' }, { status: 404 })
    }

    const text = await data.text()
    const picks = JSON.parse(text)

    // 檢查用戶訂閱狀態
    const { data: { user } } = await supabase.auth.getUser()
    let hasAccess = false

    if (user) {
      const { data: sub } = await serviceSupabase
        .from('subscriptions')
        .select('status, expires_at')
        .eq('user_id', user.id)
        .eq('status', 'active')
        .gt('expires_at', new Date().toISOString())
        .limit(1)
        .single()
      hasAccess = !!sub
    }

    // 未訂閱用戶：隱藏推薦敏感欄位
    if (!hasAccess && picks.picks) {
      picks.picks = picks.picks.map((p: Record<string, unknown>) => ({
        home: p.home,
        away: p.away,
        home_cn: p.home_cn,
        away_cn: p.away_cn,
        game_time: p.game_time,
        home_sp: p.home_sp,
        away_sp: p.away_sp,
        home_sp_era: p.home_sp_era,
        away_sp_era: p.away_sp_era,
        // 以下欄位隱藏
        bet_type: '???',
        label: '',
        price: null,
        edge: null,
        conf: null,
        stake: null,
        book: null,
      }))
    }

    return NextResponse.json(picks)
  } catch (e) {
    console.error('picks route error:', e)
    return NextResponse.json({ error: 'Internal error' }, { status: 500 })
  }
}
