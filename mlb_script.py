import requests
import os
from datetime import datetime

# ===== 環境變數 =====
API_KEY = os.getenv("ODDS_API_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

if not API_KEY or not WEBHOOK_URL:
    raise ValueError("請確保環境變數已設定")

BASE_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"

TEAM_CN = {
    "Arizona Diamondbacks": "響尾蛇", "Atlanta Braves": "勇士", "Baltimore Orioles": "金鶯",
    "Boston Red Sox": "紅襪", "Chicago Cubs": "小熊", "Chicago White Sox": "白襪",
    "Cincinnati Reds": "紅人", "Cleveland Guardians": "守護者", "Colorado Rockies": "洛磯",
    "Detroit Tigers": "老虎", "Houston Astros": "太空人", "Kansas City Royals": "皇家",
    "Los Angeles Angels": "天使", "Los Angeles Dodgers": "道奇", "Miami Marlins": "馬林魚",
    "Milwaukee Brewers": "釀酒人", "Minnesota Twins": "雙城", "New York Mets": "大都會",
    "New York Yankees": "洋基", "Oakland Athletics": "運動家", "Philadelphia Phillies": "費城人",
    "Pittsburgh Pirates": "海盜", "San Diego Padres": "教士", "San Francisco Giants": "巨人",
    "Seattle Mariners": "水手", "St. Louis Cardinals": "紅雀", "Tampa Bay Rays": "光芒",
    "Texas Rangers": "遊騎兵", "Toronto Blue Jays": "藍鳥", "Washington Nationals": "國民"
}

def send_discord(text):
    MAX = 1900
    for i in range(0, len(text), MAX):
        requests.post(WEBHOOK_URL, json={"content": text[i:i+MAX]})

def kelly(prob, odds):
    if odds <= 1: return 0
    b = odds - 1
    k = (prob * b - (1 - prob)) / b
    return max(0, round(k, 3))

def analyze_mlb():
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals", # 這裡增加了 totals
        "oddsFormat": "decimal"
    }

    try:
        res = requests.get(BASE_URL, params=params)
        res.raise_for_status()
        games = res.json()
    except Exception as e:
        send_discord(f"API錯誤: {e}")
        return

    recommend_text = f"**⚾️ MLB 精準預測 (V8 大小分強化版)**\n"
    has_recommend = False

    for g in games:
        home_en = g["home_team"]
        away_en = g["away_team"]
        home = TEAM_CN.get(home_en, home_en)
        away = TEAM_CN.get(away_en, away_en)

        bookmakers = g.get("bookmakers", [])
        if not bookmakers: continue

        markets = bookmakers[0].get("markets", [])
        h2h = next((m["outcomes"] for m in markets if m["key"] == "h2h"), None)
        spreads = next((m["outcomes"] for m in markets if m["key"] == "spreads"), None)
        totals = next((m["outcomes"] for m in markets if m["key"] == "totals"), None)

        recs = []
        signal_count = 0

        # --- 1. 獨贏分析 ---
        if h2h:
            try:
                h_odds = next(o["price"] for o in h2h if o["name"] == home_en)
                a_odds = next(o["price"] for o in h2h if o["name"] == away_en)
                p_home = (1/h_odds) / ((1/h_odds) + (1/a_odds))
                
                # 簡單修正：主場 +3%，趨勢修正
                p_home = min(p_home + 0.03, 0.95)
                
                k_home = kelly(p_home, h_odds)
                k_away = kelly(1-p_home, a_odds)

                if p_home > 0.62 and k_home > 0.04:
                    recs.append(f"🔵 勝負：{home} (Kelly {k_home})")
                    signal_count += 1
                elif p_home < 0.38 and k_away > 0.04:
                    recs.append(f"🔵 勝負：{away} (Kelly {k_away})")
                    signal_count += 1
            except: pass

        # --- 2. 讓分分析 (-1.5 / +1.5) ---
        if spreads:
            try:
                h_spread = next(o for o in spreads if o["name"] == home_en)
                # 如果主隊強勢且讓 1.5 分
                if h_spread["point"] == -1.5 and p_home > 0.65:
                    recs.append(f"🚩 讓分：{home} -1.5")
                    signal_count += 1
            except: pass

        # --- 3. 大小分分析 (NEW) ---
        if totals:
            try:
                # 取得大分(Over)的基準與賠率
                over = next(o for o in totals if o["name"] == "Over")
                under = next(o for o in totals if o["name"] == "Under")
                line = over["point"]
                
                # 簡易模型：MLB平均得分約 8.5-9 分
                # 若盤口開得極低(< 7.5) 且 賠率偏好大分，或 盤口極高(> 10.5) 且偏好小分
                if line <= 7.5 and over["price"] < 1.90:
                    recs.append(f"🟢 大分：{line} Over")
                    signal_count += 1
                elif line >= 10.5 and under["price"] < 1.90:
                    recs.append(f"🟣 小分：{line} Under")
                    signal_count += 1
            except: pass

        # --- 輸出判定 ---
        # 只要有任何一個訊號符合就顯示，增加可看度
        if signal_count >= 1:
            has_recommend = True
            recommend_text += f"\n**{away} vs {home}**"
            for r in recs:
                recommend_text += f"\n{r}"
            recommend_text += "\n"

    if not has_recommend:
        recommend_text += "\n當前盤口未發現明顯訊號，建議觀望。"

    send_discord(recommend_text)

if __name__ == "__main__":
    analyze_mlb()
