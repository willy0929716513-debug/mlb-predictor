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

# ===== Discord 發送 =====
def send_discord(text):
    MAX = 1900
    for i in range(0, len(text), MAX):
        requests.post(WEBHOOK_URL, json={"content": text[i:i+MAX]})

# ===== Kelly =====
def kelly(prob, odds):
    if odds <= 1:
        return 0
    b = odds - 1
    k = (prob * b - (1 - prob)) / b
    return max(0, round(k, 3))

# ===== 主程式 =====
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

    now = datetime.now().strftime("%m/%d %H:%M")

    recommend_text = f"**⚾ MLB 數據平衡版 V10**\n更新時間：{now}\n"
    has_recommend = False

    for g in games:

        home_en = g["home_team"]
        away_en = g["away_team"]
        home = TEAM_CN.get(home_en, home_en)
        away = TEAM_CN.get(away_en, away_en)

        bookmakers = g.get("bookmakers", [])
        if not bookmakers:
            continue

        # ===== 取得最佳主客勝賠率（多莊比較）=====
        h_odds = None
        a_odds = None
        spreads_data = []
        totals_data = []

        for b in bookmakers:
            for m in b.get("markets", []):
                if m["key"] == "h2h":
                    for o in m["outcomes"]:
                        if o["name"] == home_en:
                            h_odds = max(h_odds or 0, o["price"])
                        elif o["name"] == away_en:
                            a_odds = max(a_odds or 0, o["price"])

                elif m["key"] == "spreads":
                    spreads_data.extend(m["outcomes"])

                elif m["key"] == "totals":
                    totals_data.extend(m["outcomes"])

        recs = []

        # ===== 1. 勝負判定 =====
        if h_odds and a_odds:

            # 市場隱含機率
            p_home = (1/h_odds) / ((1/h_odds) + (1/a_odds))

            # 主場優勢 +2%
            p_home = min(p_home + 0.02, 0.95)

            k_home = kelly(p_home, h_odds)
            k_away = kelly(1-p_home, a_odds)

            # ⭐⭐⭐ 強推
            if p_home > 0.62 and k_home > 0.03:
                recs.append(f"🔵 強烈推薦：{home} ⭐⭐⭐")
            elif (1-p_home) > 0.62 and k_away > 0.03:
                recs.append(f"🔵 強烈推薦：{away} ⭐⭐⭐")

            # ⭐⭐ 價值
            elif p_home > 0.56 and k_home > 0.01:
                recs.append(f"🔹 價值推薦：{home} ⭐⭐")
            elif (1-p_home) > 0.56 and k_away > 0.01:
                recs.append(f"🔹 價值推薦：{away} ⭐⭐")

            # ⭐ 輕微優勢
            elif p_home > 0.53:
                recs.append(f"⚪ 輕微優勢：{home} ⭐")
            elif (1-p_home) > 0.53:
                recs.append(f"⚪ 輕微優勢：{away} ⭐")

        # ===== 2. 讓分判定 =====
        if spreads_data and h_odds and a_odds:
            try:
                h_spread = next(o for o in spreads_data if o["name"] == home_en)

                if h_spread["point"] == -1.5 and p_home > 0.58:
                    recs.append(f"🚩 讓分機會：{home} (-1.5)")

                elif h_spread["point"] == 1.5 and p_home > 0.48:
                    recs.append(f"🛡️ 受讓保護：{home} (+1.5)")
            except:
                pass

        # ===== 3. 大小分判定 =====
        if totals_data:
            try:
                over = next(o for o in totals_data if o["name"] == "Over")
                under = next(o for o in totals_data if o["name"] == "Under")
                line = over["point"]

                # 放寬條件：市場明顯偏向一邊就提示
                if over["price"] <= 1.90:
                    recs.append(f"🟢 市場偏大：{line} Over")

                elif under["price"] <= 1.90:
                    recs.append(f"🟣 市場偏小：{line} Under")

            except:
                pass

        # ===== 有推薦才輸出 =====
        if recs:
            has_recommend = True
            recommend_text += f"\n**{away} @ {home}**"
            for r in recs:
                recommend_text += f"\n  {r}"
            recommend_text += "\n"

    if not has_recommend:
        recommend_text += "\n目前市場盤口極度平衡，無明顯優勢場次。"

    send_discord(recommend_text)


# ===== 執行 =====
if __name__ == "__main__":
    analyze_mlb()
