import requests
import os
from datetime import datetime

API_KEY = os.getenv("ODDS_API_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

BASE_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"

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
    text = f"⚾ MLB 投手模型 V11\n更新：{now}\n"
    has_pick = False

    for g in games:

        home = g["home_team"]
        away = g["away_team"]
        bookmakers = g.get("bookmakers", [])

        if not bookmakers:
            continue

        home_odds = []
        away_odds = []
        totals_list = []

        # 收集市場資料
        for b in bookmakers:
            for m in b.get("markets", []):
                if m["key"] == "h2h":
                    for o in m["outcomes"]:
                        if o["name"] == home:
                            home_odds.append(o["price"])
                        elif o["name"] == away:
                            away_odds.append(o["price"])

                elif m["key"] == "totals":
                    for o in m["outcomes"]:
                        if o["name"] == "Over":
                            totals_list.append((o["point"], o["price"]))

        if not home_odds or not away_odds:
            continue

        best_home = max(home_odds)
        best_away = max(away_odds)

        avg_home = sum(home_odds)/len(home_odds)
        avg_away = sum(away_odds)/len(away_odds)

        # 市場公平勝率
        p_home = implied_prob(avg_home)
        p_away = implied_prob(avg_away)

        total_line = None
        over_price = None

        if totals_list:
            total_line, over_price = totals_list[0]

        recs = []

        # ===== 投手戰判定（低分）=====
        if total_line and total_line <= 8:
            # 低分戰 → 強隊優勢更大
            if p_home > 0.60 and best_home >= 1.70:
                recs.append(f"🔵 投手戰強推：{home} ({best_home})")

            if p_away > 0.60 and best_away >= 1.70:
                recs.append(f"🔵 投手戰強推：{away} ({best_away})")

            if over_price and over_price >= 2.00:
                recs.append(f"🟣 小分價值：Under {total_line}")

        # ===== 打擊戰判定（高分）=====
        elif total_line and total_line >= 9:

            if over_price and over_price <= 1.80:
                recs.append(f"🟢 打擊戰大分：Over {total_line}")

            # 高分戰 → 爆冷機率上升
            if p_home < 0.45 and best_home >= 2.20:
                recs.append(f"⭐ 爆冷機會：{home} ({best_home})")

            if p_away < 0.45 and best_away >= 2.20:
                recs.append(f"⭐ 爆冷機會：{away} ({best_away})")

        # ===== 一般價值判定 =====
        edge_home = p_home * best_home - 1
        edge_away = p_away * best_away - 1

        if edge_home > 0.04:
            recs.append(f"💰 價值：{home} Edge {round(edge_home*100,1)}%")

        if edge_away > 0.04:
            recs.append(f"💰 價值：{away} Edge {round(edge_away*100,1)}%")

        if recs:
            has_pick = True
            text += f"\n{away} @ {home}\n"
            for r in recs:
                text += f"  {r}\n"

    if not has_pick:
        text += "\n今天市場非常有效率，無明顯優勢。"

    send_discord(text)


if __name__ == "__main__":
    analyze_mlb()
