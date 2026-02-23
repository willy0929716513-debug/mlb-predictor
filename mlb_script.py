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

def implied_prob(odds):
    return 1 / odds if odds else 0

def analyze_mlb():
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,totals",
        "oddsFormat": "decimal"
    }

    try:
        res = requests.get(BASE_URL, params=params)
        res.raise_for_status()
        games = res.json()
    except Exception as e:
        send_discord(f"API錯誤: {e}")
        return

    now = datetime.now().strftime("%m/%d %H:%M")
    text = f"⚾ MLB 投手模型 V13 (靈敏數據版)\n更新時間：{now}\n"
    has_pick = False

    for g in games:
        home_en = g["home_team"]
        away_en = g["away_team"]
        home = TEAM_CN.get(home_en, home_en)
        away = TEAM_CN.get(away_en, away_en)

        bookmakers = g.get("bookmakers", [])
        if not bookmakers: continue

        home_odds, away_odds, totals_list = [], [], []

        for b in bookmakers:
            for m in b.get("markets", []):
                if m["key"] == "h2h":
                    for o in m["outcomes"]:
                        if o["name"] == home_en: home_odds.append(o["price"])
                        elif o["name"] == away_en: away_odds.append(o["price"])
                elif m["key"] == "totals":
                    for o in m["outcomes"]:
                        if o["name"] == "Over":
                            totals_list.append((o["point"], o["price"]))

        if not home_odds or not away_odds: continue

        best_home, best_away = max(home_odds), max(away_odds)
        avg_home, avg_away = sum(home_odds)/len(home_odds), sum(away_odds)/len(away_odds)

        # 計算去抽水後的公平勝率
        raw_p_h = implied_prob(avg_home)
        raw_p_a = implied_prob(avg_away)
        p_home = raw_p_h / (raw_p_h + raw_p_a)
        p_away = 1 - p_home

        total_line = totals_list[0][0] if totals_list else "未開"
        over_price = totals_list[0][1] if totals_list else None

        recs = []

        # --- 靈敏推薦邏輯 ---
        if isinstance(total_line, float):
            if total_line <= 8.5:
                if p_home > 0.55 and best_home >= 1.60: recs.append(f"🔵 推薦：{home} ({best_home})")
                elif p_away > 0.55 and best_away >= 1.60: recs.append(f"🔵 推薦：{away} ({best_away})")
            else:
                if over_price and over_price <= 1.95: recs.append(f"🟢 偏大：Over {total_line}")
                if p_home < 0.49 and best_home >= 2.05: recs.append(f"⭐ 爆冷：{home} ({best_home})")
                elif p_away < 0.49 and best_away >= 2.05: recs.append(f"⭐ 爆冷：{away} ({best_away})")

        # --- Edge 價值感應 (靈敏度 1.5%) ---
        edge_home = p_home * best_home - 1
        edge_away = p_away * best_away - 1
        if edge_home > 0.015: recs.append(f"💰 價值：{home} (+{round(edge_home*100,1)}%)")
        if edge_away > 0.015: recs.append(f"💰 價值：{away} (+{round(edge_away*100,1)}%)")

        # --- 顯示數據 (不論是否有推薦) ---
        has_pick = True
        text += f"\n**{away} @ {home}** (總盤: {total_line})\n"
        text += f"📊 預估勝率：{away} {p_away:.1%} vs {home} {p_home:.1%}\n"
        
        if recs:
            for r in recs:
                text += f"  {r}\n"
        else:
            text += "  ⚖️ 市場極度平衡，建議觀望\n"

    send_discord(text)

if __name__ == "__main__":
    analyze_mlb()
