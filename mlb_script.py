import requests
import os
from datetime import datetime

# ===== 環境變數 =====
API_KEY = os.getenv("ODDS_API_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

BASE_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"

# ===== 中文隊名對照表 =====
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
    text = f"⚾ MLB 投手模型 V12 (中文版)\n更新：{now}\n"
    has_pick = False

    for g in games:
        # 轉換成中文名稱，若找不到則顯示原名
        home_en = g["home_team"]
        away_en = g["away_team"]
        home = TEAM_CN.get(home_en, home_en)
        away = TEAM_CN.get(away_en, away_en)

        bookmakers = g.get("bookmakers", [])
        if not bookmakers: continue

        home_odds = []
        away_odds = []
        totals_list = []

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

        best_home = max(home_odds)
        best_away = max(away_odds)
        avg_home = sum(home_odds)/len(home_odds)
        avg_away = sum(away_odds)/len(away_odds)

        p_home = implied_prob(avg_home) / (implied_prob(avg_home) + implied_prob(avg_away))
        p_away = 1 - p_home

        total_line = totals_list[0][0] if totals_list else None
        over_price = totals_list[0][1] if totals_list else None

        recs = []

        # 核心邏輯
        if total_line:
            if total_line <= 8.5:
                if p_home > 0.58 and best_home >= 1.65:
                    recs.append(f"🔵 強推：{home} ({best_home})")
                elif p_away > 0.58 and best_away >= 1.65:
                    recs.append(f"🔵 強推：{away} ({best_away})")
                if over_price and over_price >= 1.98:
                    recs.append(f"🟣 小分價值：Under {total_line}")
            else:
                if over_price and over_price <= 1.90:
                    recs.append(f"🟢 大分偏好：Over {total_line}")
                if p_home < 0.48 and best_home >= 2.10:
                    recs.append(f"⭐ 爆冷機會：{home} ({best_home})")
                elif p_away < 0.48 and best_away >= 2.10:
                    recs.append(f"⭐ 爆冷機會：{away} ({best_away})")

        edge_home = p_home * best_home - 1
        edge_away = p_away * best_away - 1

        if edge_home > 0.03:
            recs.append(f"💰 價值：{home} (Edge {round(edge_home*100,1)}%)")
        if edge_away > 0.03:
            recs.append(f"💰 價值：{away} (Edge {round(edge_away*100,1)}%)")

        if recs:
            has_pick = True
            text += f"\n**{away} @ {home}** (總盤: {total_line})\n"
            for r in recs:
                text += f"  {r}\n"

    if not has_pick:
        text += "\n目前市場數據平衡，無顯著錯價場次。"

    send_discord(text)

if __name__ == "__main__":
    analyze_mlb()
