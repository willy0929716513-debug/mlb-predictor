export interface Pick {
  home: string
  away: string
  home_cn: string
  away_cn: string
  bet_type: string      // "獨贏" | "讓分" | "大小分"
  label: string         // "" | "+1.5" | "-1.5" | "OVER" | "UNDER"
  price: number
  edge: number
  conf: number
  stake: number
  game_time: string     // ISO 或台灣時間字串
  home_sp: string
  away_sp: string
  home_sp_era?: number
  away_sp_era?: number
  model_p?: number
  market_p?: number
  park_factor?: number
  weather_factor?: number
  book?: string         // 最優賠率來源
  strength?: string     // "💎 強注" | "⭐ 穩定"
}

export interface Stats {
  settled: number
  wins: number
  win_rate: number
  total_pnl: number
  roi: number
  by_type: {
    ML?: TypeStat
    RL?: TypeStat
    TOT?: TypeStat
  }
}

export interface TypeStat {
  settled: number
  wins: number
  win_rate: number
  roi: number
}

export interface HistoryRecord {
  date: string
  home: string
  away: string
  home_cn: string
  away_cn: string
  bet_type: string
  label: string
  price: number
  stake: number
  edge: number
  result: 'W' | 'L' | 'P' | null
}

export interface PicksData {
  picks: Pick[]
  stats: Stats
  recent_history: HistoryRecord[]
  updated_at: string
}

export interface Subscription {
  plan_type: 'monthly' | 'day_pass'
  status: 'active' | 'expired' | 'cancelled'
  expires_at: string
}
