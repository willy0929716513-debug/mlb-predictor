import requests
import os
from datetime import datetime

# ===== 環境變數 =====
API_KEY = os.getenv("ODDS_API_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

if not API_KEY or not WEBHOOK_URL:
    raise ValueError("請確保 ODDS_API_KEY 與 DISCORD_WEBHOOK 已設定於環境變數中")

# MLB API 端點
BASE_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"

# ===== MLB 中文隊名對照表 =====
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

# ===== 功能組件 =====
def send_discord(text):
    MAX = 1900
    for i in range(0, len(text), MAX):
        part = text[i:i+MAX]
        try:
            requests.post(WEBHOOK_URL, json={"content": part})
        except Exception as e:
            print(f"Discord 發送失敗: {e}")

def kelly_criterion(prob, odds):
    """
    凱利公式計算建議倉位
    $k = (p * b - q) / b$
    """
    if odds <= 1: return 0
    b = odds - 1
    q = 1 - prob
    k = (prob * b - q) / b
    return max(0, round(k, 3))

def mlb_momentum_adjust(prob):
    """
    針對棒球連勝/連敗慣性較強的 EMA 修正模擬
    """
    if prob > 0.62: # 強者恆強
        return min(prob + 0.04, 0.98)
    elif prob < 0.38: # 弱者恆弱
        return max(prob - 0.04, 0.02)
    return prob

def ballpark_home_factor(prob):
    """
    MLB 主場優勢（通常約為 3%-4%）
    """
    return min(prob + 0.035, 0.98)

# ===== 主程式 =====
def analyze_mlb():
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads", # MLB 讓分通常稱為 Run Line (-1.5)
        "oddsFormat": "decimal"
    }

    try:
        res = requests.get(BASE_URL, params=params)
        res.raise_for_status()
        games = res.json()
    except Exception as e:
        send_discord(f"❌ MLB API 請求失敗: {e}")
        return

    recommend_text = f"**⚾️ MLB 精準預測 (V7 MLB 版)**\n📅 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    has_recommend = False

    for g in games:
        home_en = g["home_team"]
        away_en = g["away_team"]
        home_cn = TEAM_CN.get(home_en, home_en)
        away_cn = TEAM_CN.get(away_en, away_en)

        bookmakers = g.get("bookmakers", [])
        if not bookmakers: continue

        # 優先取用具代表性的博彩公司 (如 Pinnacle 或 DraftKings)
        market_data = bookmakers[0].get("markets", [])
        h2h = next((m["outcomes"] for m in market_data if m["key"] == "h2h"), None)
        spreads = next((m["outcomes"] for m in market_data if m["key"] == "spreads"), None)

        if not h2h: continue

        try:
            h_odds = next(o["price"] for o in h2h if o["name"] == home_en)
            a_odds = next(o["price"] for o in h2h if o["name"] == away_en)
        except: continue

        # 1. 計算隱含勝率 (去抽水)
        raw_p_home = (1/h_odds) / ((1/h_odds) + (1/a_odds))
        
        # 2. 演算法修正
        adj_p_home = mlb_momentum_adjust(raw_p_home)
        adj_p_home = ballpark_home_factor(adj_p_home)
        adj_p_away = 1 - adj_p_home

        # 3. 凱利準則計算
        k_home = kelly_criterion(adj_p_home, h_odds)
        k_away = kelly_criterion(adj_p_away, a_odds)

        # 4. 判定邏輯 (MLB 較嚴謹版本)
        recs = []
        signal_count = 0

        # --- 強力獨贏訊號 ---
        if adj_p_home > 0.65 and k_home > 0.06:
            recs.append(f"🔵 **獨贏推薦：{home_cn}** (信心度: {adj_p_home:.1%})")
            signal_count += 2
        elif adj_p_away > 0.65 and k_away > 0.06:
            recs.append(f"🔵 **獨贏推薦：{away_cn}** (信心度: {adj_p_away:.1%})")
            signal_count += 2

        # --- 讓分訊號 (Run Line -1.5) ---
        # 棒球讓分通常固定在 1.5，若強隊賠率依然合理則推薦
        if spreads:
            try:
                h_spread_info = next(o for o in spreads if o["name"] == home_en)
                if h_spread_info["point"] == -1.5 and adj_p_home > 0.68:
                    recs.append(f"🚩 **讓分推薦：{home_cn} (-1.5)**")
                    signal_count += 1
                elif h_spread_info["point"] == 1.5 and adj_p_home > 0.45:
                    recs.append(f"🚩 **受讓推薦：{home_cn} (+1.5)**")
                    signal_count += 1
            except: pass

        # 5. 輸出結果
        if signal_count >= 2:
            has_recommend = True
            recommend_text += f"\n---"
            recommend_text += f"\n🏟️ {away_cn} @ {home_cn}"
            recommend_text += f"\n📊 預估主勝率：{adj_p_home:.2f}"
            for r in recs:
                recommend_text += f"\n{r}"
            recommend_text += "\n"

    if not has_recommend:
        recommend_text += "\n當前盤口未發現高勝率投資機會。"

    send_discord(recommend_text)

if __name__ == "__main__":
    analyze_mlb()
