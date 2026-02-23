import requests
import os
from datetime import datetime

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
    text = f"⚾ MLB 投手模型 V14（實戰版）\n更新：{now}\n"
    has_output = False

    for g in games:
        home_en = g["home_team"]
        away_en = g["away_team"]
        home = TEAM_CN.get(home_en, home_en)
        away = TEAM_CN.get(away_en, away_en)

        bookmakers = g.get("bookmakers", [])
        if not bookmakers:
            continue

        home_odds, away_odds = [], []
        total_lines, over_prices = [], []

        for b in bookmakers:
            for m in b.get("markets", []):
                if m["key"] == "h2h":
                    for o in m["outcomes"]:
                        if o["name"] == home_en:
                            home_odds.append(o["price"])
                        elif o["name"] == away_en:
                            away_odds.append(o["price"])

                elif m["key"] == "totals":
                    for o in m["outcomes"]:
                        if o["name"] == "Over":
                            total_lines.append(o["point"])
                            over_prices.append(o["price"])

        if not home_odds or not away_odds:
            continue

        # 最佳賠率
        best_home = max(home_odds)
        best_away = max(away_odds)

        # 平均賠率（去水位）
        avg_home = sum(home_odds) / len(home_odds)
        avg_away = sum(away_odds) / len(away_odds)

        raw_h = implied_prob(avg_home)
        raw_a = implied_prob(avg_away)
        p_home = raw_h / (raw_h + raw_a)
        p_away = 1 - p_home

        # 主流總分（平均）
        total_line = None
        avg_over = None
        if total_lines:
            total_line = round(sum(total_lines) / len(total_lines), 1)
            avg_over = sum(over_prices) / len(over_prices)

        # Edge
        edge_home = p_home * best_home - 1
        edge_away = p_away * best_away - 1

        recs = []
        max_edge = max(edge_home, edge_away)

        # ===== 投手模型邏輯 =====
        if total_line:

            # 低分＝投手戰
            if total_line <= 8.0:
                if p_home > 0.57 and best_home >= 1.65:
                    recs.append(f"🔵 投手優勢：{home} ({best_home})")
                if p_away > 0.57 and best_away >= 1.65:
                    recs.append(f"🔵 投手優勢：{away} ({best_away})")

            # 高分＝打擊戰
            elif total_line >= 9.0:
                if avg_over and avg_over <= 1.85:
                    recs.append(f"🟢 打擊戰大分：Over {total_line}")

                # 爆冷環境
                if p_home < 0.46 and best_home >= 2.20:
                    recs.append(f"⭐ 爆冷機會：{home}")
                if p_away < 0.46 and best_away >= 2.20:
                    recs.append(f"⭐ 爆冷機會：{away}")

        # ===== Edge 分級 =====
        if edge_home > 0.05:
            recs.append(f"💰💰 強價值：{home} +{edge_home*100:.1f}%")
        elif edge_home > 0.03:
            recs.append(f"💰 價值：{home} +{edge_home*100:.1f}%")

        if edge_away > 0.05:
            recs.append(f"💰💰 強價值：{away} +{edge_away*100:.1f}%")
        elif edge_away > 0.03:
            recs.append(f"💰 價值：{away} +{edge_away*100:.1f}%")

        # ===== 只輸出有意義的場 =====
        if recs or max_edge > 0.02:
            has_output = True
            text += f"\n**{away} @ {home}**"
            if total_line:
                text += f" (總分 {total_line})"
            text += "\n"
            text += f"勝率：{away} {p_away:.1%} | {home} {p_home:.1%}\n"

            if recs:
                for r in recs:
                    text += f"  {r}\n"
            else:
                text += "  ⚖️ 小幅價差觀察\n"

    if not has_output:
        text += "\n今天市場效率極高，無可交易機會。"

    send_discord(text)

if __name__ == "__main__":
    analyze_mlb()
