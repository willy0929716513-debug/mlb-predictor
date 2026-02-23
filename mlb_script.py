import requests
import os
from datetime import datetime

# ===== 環境變數 =====
API_KEY = os.getenv("ODDS_API_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

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
        "markets": "h2h,spreads,totals",
        "oddsFormat": "decimal"
    }

    try:
        res = requests.get(BASE_URL, params=params)
        res.raise_for_status()
        games = res.json()
    except Exception as e:
        send_discord(f"API錯誤: {e}")
        return

    recommend_text = f"**⚾️ MLB 數據平衡版 (V9)**\n"
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
        
        # --- 1. 平衡版勝負判定 ---
        if h2h:
            try:
                h_odds = next(o["price"] for o in h2h if o["name"] == home_en)
                a_odds = next(o["price"] for o in h2h if o["name"] == away_en)
                p_home = (1/h_odds) / ((1/h_odds) + (1/a_odds))
                p_home = min(p_home + 0.03, 0.95) # 主場微修正
                
                k_home = kelly(p_home, h_odds)
                k_away = kelly(1-p_home, a_odds)

                # 門檻降至 58%，但用星等區分
                if p_home > 0.63 and k_home > 0.05:
                    recs.append(f"🔵 **強烈推薦：{home}** ⭐️⭐️⭐️")
                elif p_home > 0.58 and k_home > 0.02:
                    recs.append(f"🔹 價值推薦：{home} ⭐️⭐️")
                elif (1-p_home) > 0.63 and k_away > 0.05:
                    recs.append(f"🔵 **強烈推薦：{away}** ⭐️⭐️⭐️")
                elif (1-p_home) > 0.58 and k_away > 0.02:
                    recs.append(f"🔹 價值推薦：{away} ⭐️⭐️")
            except: pass

        # --- 2. 平衡版讓分判定 ---
        if spreads:
            try:
                h_spread = next(o for o in spreads if o["name"] == home_en)
                if h_spread["point"] == -1.5 and p_home > 0.62:
                    recs.append(f"🚩 讓分優勢：{home} (-1.5)")
                elif h_spread["point"] == 1.5 and p_home > 0.45:
                    recs.append(f"🛡️ 受讓保險：{home} (+1.5)")
            except: pass

        # --- 3. 平衡版大小分判定 ---
        if totals:
            try:
                over = next(o for o in totals if o["name"] == "Over")
                under = next(o for o in totals if o["name"] == "Under")
                line = over["point"]
                
                # 只要賠率在 1.85 以下且盤口進入合理區間就提示
                if line <= 8.5 and over["price"] < 1.85:
                    recs.append(f"🟢 傾向大分：{line} Over")
                elif line >= 8.5 and under["price"] < 1.85:
                    recs.append(f"🟣 傾向小分：{line} Under")
            except: pass

        if recs:
            has_recommend = True
            recommend_text += f"\n**{away} @ {home}**"
            for r in recs:
                recommend_text += f"\n  {r}"
            recommend_text += "\n"

    if not has_recommend:
        recommend_text += "\n目前市場盤口極度平衡，無顯著數據優勢場次。"

    send_discord(recommend_text)

if __name__ == "__main__":
    analyze_mlb()
