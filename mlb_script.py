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
        send_discord(f"❌ API 連線錯誤: {e}")
        return

    now = datetime.now().strftime("%m/%d %H:%M")
    header = f"⚾ **MLB 投手模型 V15 (賽季掃描)**\n⏰ 更新：{now}\n"
    content = ""
    
    if not games:
        send_discord(header + "⚠️ API 目前未回傳任何比賽數據。可能原因：春訓期間盤口未開或非賽季。")
        return

    for g in games:
        home_en, away_en = g["home_team"], g["away_team"]
        home, away = TEAM_CN.get(home_en, home_en), TEAM_CN.get(away_en, away_en)
        
        bookmakers = g.get("bookmakers", [])
        content += f"\n**{away} @ {home}**"

        if not bookmakers:
            content += "\n  ⚪ 狀態：已排程，但博彩公司尚未釋出賠率。\n"
            continue

        # --- 數據抓取 ---
        h_odds, a_odds, totals_list = [], [], []
        for b in bookmakers:
            for m in b.get("markets", []):
                if m["key"] == "h2h":
                    for o in m["outcomes"]:
                        if o["name"] == home_en: h_odds.append(o["price"])
                        elif o["name"] == away_en: a_odds.append(o["price"])
                elif m["key"] == "totals":
                    for o in m["outcomes"]:
                        if o["name"] == "Over": totals_list.append((o["point"], o["price"]))

        if not h_odds or not a_odds:
            content += "\n  ⚪ 狀態：獨贏盤口數據不足。\n"
            continue

        # --- 核心計算 ---
        best_h, best_a = max(h_odds), max(a_odds)
        avg_h, avg_a = sum(h_odds)/len(h_odds), sum(a_odds)/len(a_odds)
        p_h = implied_prob(avg_h) / (implied_prob(avg_h) + implied_prob(avg_a))
        p_a = 1 - p_h
        
        t_line = totals_list[0][0] if totals_list else "未開盤"
        over_p = totals_list[0][1] if totals_list else None
        
        content += f"\n  📊 勝率：{away} {p_a:.1%} vs {home} {p_h:.1%}"
        content += f"\n  🎰 總分盤：{t_line}"

        # --- 靈敏推薦邏輯 ---
        recs = []
        # 勝負推薦 (55% 門檻)
        if p_h > 0.55 and best_h >= 1.60: recs.append(f"🔵 推薦：{home} ({best_h})")
        elif p_a > 0.55 and best_a >= 1.60: recs.append(f"🔵 推薦：{away} ({best_a})")
        
        # 價值感應 (1.5% 門檻)
        edge_h, edge_a = p_h * best_h - 1, p_a * best_a - 1
        if edge_h > 0.015: recs.append(f"💰 價值：{home} (+{round(edge_h*100,1)}%)")
        if edge_a > 0.015: recs.append(f"💰 價值：{away} (+{round(edge_a*100,1)}%)")

        if recs:
            for r in recs: content += f"\n  {r}"
        else:
            content += "\n  ⚖️ 數據平衡，建議觀望"
        content += "\n"

    send_discord(header + content)

if __name__ == "__main__":
    analyze_mlb()
