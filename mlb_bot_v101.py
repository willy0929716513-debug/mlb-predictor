# ============================================================
# MLB_V104  (修正版：2026 MLB 賽季)
# 主要修改：
#  1. PITCHER_ERA 補入 2026 賽季先發投手
#  2. ROSTER / OUT / LTD / SS 更新至 2026
#  3. BASE 攻守評分依 2025 成績調整
#  4. edge 改為用純 model_prob 計算，避免 blended 壓縮問題
#  5. best_price 改取最佳賠率（max），consensus 仍取平均
#  6. official 時間窗口調整（台灣時間 0~14 點視為當日正式推薦）
#  7. 歷史記錄擴展至所有等級（edge >= EDGE_MIN）
#  8. Kelly 加入最大下注上限保護
#  9. fetch_probable_pitchers 增加備援解析路徑
# 10. f-string 取代 % 格式化，提升可讀性與穩定性
# ============================================================
import requests, os, random, logging, json, math
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("MLB_V104")

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
WEBHOOK      = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN     = os.getenv("GH_TOKEN", "")

# ── 核心參數 ──────────────────────────────────────────────────
EDGE_MIN  = 0.06    # 最低 edge 閾值
MOD_W     = 0.25    # 模型權重（win prob blend 用）
MKT_W     = 0.75    # 市場權重
TOT_MOD   = 0.40    # 大小分模型權重
TOT_MKT   = 0.60    # 大小分市場權重
STD       = 1.6     # 得分差標準差（用於勝率轉換）
HA        = 0.12    # 主場優勢（得分差，MLB 歷史約 0.10~0.15）
MIN_P     = 1.30    # 最低賠率過濾
MAX_P     = 2.80    # 最高賠率過濾
LIMIT     = 1900    # Discord 每則訊息字元上限
BANK      = 1000.0  # 賭注基準金額
KELLY     = 0.15    # Kelly 係數（分數 Kelly）
KELLY_MAX = 35.0    # 單筆最高下注上限（元）
HIST_TTL  = 90      # 歷史記錄保留天數

# ── 球員名單（2026 賽季更新）────────────────────────────────
ROSTER = {
    "New York Yankees":      ["cole","judge","goldschmidt","cabrera","volpe"],
    "Los Angeles Dodgers":   ["ohtani","freeman","betts","sasaki","buehler"],
    "Atlanta Braves":        ["sale","acuna","olson","riley","sorokin"],
    "Houston Astros":        ["brown","pena","abreu","paredes","blanco"],
    "Baltimore Orioles":     ["burnes","henderson","rutschman","alonso","hall"],
    "Philadelphia Phillies": ["wheeler","nola","harper","schwarber","stott"],
    "Texas Rangers":         ["eovaldi","seager","carter","garcia","taveras"],
    "Arizona Diamondbacks":  ["kelly","gallen","marte","carroll","moreno"],
    "Minnesota Twins":       ["buxton","lewis","keaschall","ryan","wallner"],
    "Seattle Mariners":      ["castillo","raleigh","rodriguez","arozarena","france"],
    "Milwaukee Brewers":     ["harrison","contreras","chourio","yelich","adames"],
    "Chicago Cubs":          ["steele","bregman","crow","suzuki","busch"],
    "San Francisco Giants":  ["webb","devers","adames","arraez","bailey"],
    "Boston Red Sox":        ["anthony","duran","wcontreras","mayer","casas"],
    "New York Mets":         ["holmes","lindor","soto","bichette","vientos"],
    "Toronto Blue Jays":     ["berrios","bieber","guerrero","santander","varsho"],
    "Cleveland Guardians":   ["bibee","ramirez","kwan","naylor","freeman"],
    "Tampa Bay Rays":        ["martinez","aranda","caminero","palacios","brujan"],
    "St. Louis Cardinals":   ["leahy","wetherholt","winn","gorman","donovan"],
    "San Diego Padres":      ["musgrove","tatis","machado","merrill","king"],
    "Detroit Tigers":        ["verlander","skubal","torkelson","carpenter","jung"],
    "Kansas City Royals":    ["ragans","witt","pasquantino","perez","melendez"],
    "Pittsburgh Pirates":    ["skenes","chandler","hayes","triolo","davis"],
    "Cincinnati Reds":       ["burns","hgreene","delacruz","suarez","candelario"],
    "Colorado Rockies":      ["freeland","tovar","doyle","beck","grichuk"],
    "Oakland Athletics":     ["kurtz","jwilson","rooker","soderstrom","langeliers"],
    "Los Angeles Angels":    ["soriano","trout","neto","schanuel","manoah"],
    "Miami Marlins":         ["paddack","stowers","edwards","caissie","leblanc"],
    "Washington Nationals":  ["cavalli","wood","garcia","crews","young"],
    "Chicago White Sox":     ["martin","montgomery","teel","benintendi","anderson"],
}

# ── 傷兵名單（2026 賽季初，定期更新）──────────────────────
OUT = frozenset({"santander","pjones","mccullers","cole","acuna"})
LTD = frozenset({"trout","buxton","degrom","steele","skubal"})

# ── 超級球星集合（傷病懲罰加重）────────────────────────────
SS = frozenset({
    "ohtani","judge","freeman","acuna","tatis","ramirez","harper",
    "guerrero","trout","cole","wheeler","skubal","sale","fried",
    "lindor","soto","betts","seager","witt","degrom","skenes",
    "verlander","rutschman","henderson","burnes","castillo","sasaki",
})

SS_PEN = 1.2
ST_PEN = 0.8
LT_PEN = 0.4

# ── 各隊基礎攻守評分（依 2025 賽季成績調整）────────────────
BASE = {
    "Los Angeles Dodgers":   {"off": 5.0, "def": 3.5},
    "New York Yankees":      {"off": 4.7, "def": 3.7},
    "Atlanta Braves":        {"off": 4.5, "def": 3.7},
    "Philadelphia Phillies": {"off": 4.5, "def": 3.7},
    "New York Mets":         {"off": 4.4, "def": 3.8},
    "Cleveland Guardians":   {"off": 4.3, "def": 3.7},
    "Kansas City Royals":    {"off": 4.3, "def": 3.9},
    "Detroit Tigers":        {"off": 4.2, "def": 3.8},
    "Houston Astros":        {"off": 4.2, "def": 3.9},
    "Baltimore Orioles":     {"off": 4.2, "def": 3.9},
    "Seattle Mariners":      {"off": 4.1, "def": 3.7},
    "San Francisco Giants":  {"off": 4.1, "def": 3.9},
    "Texas Rangers":         {"off": 4.1, "def": 4.0},
    "Arizona Diamondbacks":  {"off": 4.1, "def": 4.0},
    "San Diego Padres":      {"off": 4.1, "def": 3.8},
    "Milwaukee Brewers":     {"off": 4.0, "def": 3.9},
    "Chicago Cubs":          {"off": 4.0, "def": 4.0},
    "Boston Red Sox":        {"off": 4.0, "def": 4.1},
    "Toronto Blue Jays":     {"off": 4.0, "def": 4.0},
    "Tampa Bay Rays":        {"off": 3.9, "def": 3.9},
    "Minnesota Twins":       {"off": 3.9, "def": 4.1},
    "Pittsburgh Pirates":    {"off": 3.9, "def": 4.0},
    "Cincinnati Reds":       {"off": 3.9, "def": 4.1},
    "St. Louis Cardinals":   {"off": 3.8, "def": 4.2},
    "Oakland Athletics":     {"off": 3.7, "def": 4.2},
    "Washington Nationals":  {"off": 3.7, "def": 4.3},
    "Los Angeles Angels":    {"off": 3.7, "def": 4.4},
    "Colorado Rockies":      {"off": 4.0, "def": 4.8},
    "Miami Marlins":         {"off": 3.6, "def": 4.3},
    "Chicago White Sox":     {"off": 3.4, "def": 4.7},
}
DEF_RATING = {"off": 4.0, "def": 4.2}

# ── 投手 ERA 字典（2026 賽季，含開幕系列先發）───────────────
# 格式：姓氏小寫 -> 預估 ERA
PITCHER_ERA = {
    # ── 頂級王牌 ──────────────────────────────────────────
    "ohtani":    3.00, "sasaki":    2.90, "skubal":    2.80,
    "skenes":    2.95, "degrom":    2.95, "sale":      3.10,
    "wheeler":   3.00, "burnes":    3.20, "webb":      3.20,
    "fried":     3.10, "cole":      3.85, "castillo":  3.30,
    "musgrove":  3.50, "gallen":    3.50, "burns":     3.50,
    "ragans":    3.40, "mcclanahan":3.30, "bieber":    3.40,
    # ── 穩定先發 ──────────────────────────────────────────
    "verlander": 3.80, "bibee":     3.60, "peralta":   3.60,
    "berrios":   3.80, "gausman":   3.70, "eovaldi":   3.80,
    "steele":    3.75, "imanaga":   3.55, "hgreene":   3.70,
    "nola":      3.70, "flaherty":  3.85, "woodruff":  3.40,
    "gilbert":   3.75, "woo":       3.70, "bradish":   3.65,
    "kelly":     4.00, "soroka":    4.20, "harrison":  4.10,
    "paddack":   4.30, "martin":    4.60, "martinez":  4.40,
    "messick":   4.70, "holmes":    4.00, "leahy":     4.80,
    # ── 中段先發 ──────────────────────────────────────────
    "gray":      3.95, "rasmussen": 3.95, "mikolas":   4.20,
    "liberatore":4.40, "cavalli":   4.50, "garrett":   4.10,
    "peterson":  4.20, "keller":    4.00, "javier":    4.20,
    "detmers":   4.40, "lorenzen":  4.40, "wacha":     4.30,
    "vasquez":   4.40, "horton":    4.10, "singer":    4.20,
    "rodriguez": 4.10, "wetherholt":4.50, "winn":      4.30,
    "ryan":      4.00, "brown":     4.20, "hall":      4.30,
    "blanco":    4.40, "burke":     4.70, "springs":   4.30,
    "mcgreevy":  4.50, "boyle":     4.20, "bradley":   4.40,
    "warren":    4.60, "lopez":     4.30, "perez":     4.50,
    # ── 弱勢先發 ──────────────────────────────────────────
    "freeland":  4.75, "smith":     4.85, "soriano":   4.30,
    "kurtz":     4.40, "manoah":    4.50, "buehler":   4.20,
    "leiter":    4.60, "crochet":   3.70, "cease":     3.80,
}
LEAGUE_AVG_ERA = 4.25  # 2025 聯盟平均 ERA（微調）

# ── 隊名對照表 ────────────────────────────────────────────────
SLUG = {
    "nyy": "New York Yankees",    "lad": "Los Angeles Dodgers",
    "atl": "Atlanta Braves",      "hou": "Houston Astros",
    "bal": "Baltimore Orioles",   "phi": "Philadelphia Phillies",
    "tex": "Texas Rangers",       "ari": "Arizona Diamondbacks",
    "min": "Minnesota Twins",     "sea": "Seattle Mariners",
    "mil": "Milwaukee Brewers",   "chc": "Chicago Cubs",
    "sf":  "San Francisco Giants","bos": "Boston Red Sox",
    "nym": "New York Mets",       "tor": "Toronto Blue Jays",
    "cle": "Cleveland Guardians", "tb":  "Tampa Bay Rays",
    "stl": "St. Louis Cardinals", "sd":  "San Diego Padres",
    "det": "Detroit Tigers",      "kc":  "Kansas City Royals",
    "pit": "Pittsburgh Pirates",  "cin": "Cincinnati Reds",
    "col": "Colorado Rockies",    "oak": "Oakland Athletics",
    "laa": "Los Angeles Angels",  "mia": "Miami Marlins",
    "wsh": "Washington Nationals","chw": "Chicago White Sox",
}
SHORT = {v: k.upper() for k, v in SLUG.items()}

CN = {
    "New York Yankees":      "洋基",  "Los Angeles Dodgers":  "道奇",
    "Atlanta Braves":        "勇士",  "Houston Astros":       "太空人",
    "Baltimore Orioles":     "金鶯",  "Philadelphia Phillies":"費城人",
    "Texas Rangers":         "遊騎兵","Arizona Diamondbacks":  "響尾蛇",
    "Minnesota Twins":       "雙城",  "Seattle Mariners":     "水手",
    "Milwaukee Brewers":     "釀酒人","Chicago Cubs":         "小熊",
    "San Francisco Giants":  "巨人",  "Boston Red Sox":       "紅襪",
    "New York Mets":         "大都會","Toronto Blue Jays":    "藍鳥",
    "Cleveland Guardians":   "守護者","Tampa Bay Rays":       "光芒",
    "St. Louis Cardinals":   "紅雀",  "San Diego Padres":     "教士",
    "Detroit Tigers":        "老虎",  "Kansas City Royals":   "皇家",
    "Pittsburgh Pirates":    "海盜",  "Cincinnati Reds":      "紅人",
    "Colorado Rockies":      "落磯",  "Oakland Athletics":    "運動家",
    "Los Angeles Angels":    "天使",  "Miami Marlins":        "馬林魚",
    "Washington Nationals":  "國民",  "Chicago White Sox":    "白襪",
}


# ═══════════════════════════════════════════════════════════════
# 工具函數
# ═══════════════════════════════════════════════════════════════

def norm(name: str) -> str:
    """將各種隊名寫法標準化為完整英文隊名。"""
    if not name:
        return name
    n = name.strip()
    if n in SHORT:
        return n
    upper = n.upper()
    slug_up = {k.upper(): v for k, v in SLUG.items()}
    if upper in slug_up:
        return slug_up[upper]
    n_low = n.lower()
    for full in SHORT:
        if n_low == full.lower():
            return full
    for full in SHORT:
        if n_low in full.lower() or full.lower() in n_low:
            return full
    return name


def safe_get(url, headers=None, params=None, retries=3, timeout=15):
    """帶重試的 HTTP GET，回傳 JSON 或 None。"""
    for i in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            log.warning("Timeout %d/%d %s", i, retries, url)
        except requests.exceptions.HTTPError as e:
            log.error("HTTP %s: %s", e.response.status_code, url)
            break
        except Exception as e:
            log.warning("Err %d/%d: %s", i, retries, e)
    return None


# ═══════════════════════════════════════════════════════════════
# 資料獲取：先發投手
# ═══════════════════════════════════════════════════════════════

def fetch_probable_pitchers() -> dict:
    """
    從 ESPN scoreboard 抓取當日先發投手。
    增加多層備援路徑解析，避免 API 結構變動導致失敗。
    """
    today = datetime.utcnow().strftime("%Y%m%d")
    urls = [
        "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
        "https://site.web.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    ]
    data = None
    for url in urls:
        data = safe_get(url, params={"dates": today})
        if data:
            break
    if not data:
        log.warning("ESPN scoreboard failed")
        return {}

    team_pitcher = {}
    try:
        for event in data.get("events", []):
            for comp in event.get("competitions", []):
                for team in comp.get("competitors", []):
                    team_name = norm(team.get("team", {}).get("displayName", ""))
                    if not team_name:
                        continue
                    pitcher_last = _extract_pitcher_last(team)
                    if pitcher_last:
                        team_pitcher[team_name] = pitcher_last
                        log.info("SP: %s -> %s", team_name, pitcher_last)
    except Exception as e:
        log.warning("Pitcher parse error: %s", e)

    log.info("Probable pitchers: %d teams", len(team_pitcher))
    return team_pitcher


def _extract_pitcher_last(team_obj: dict) -> str:
    """
    從 competitor 物件中嘗試多條路徑抽取先發投手姓氏。
    路徑1: team.probables[0].athlete.displayName
    路徑2: team.athletes（role=starter 或 position=SP）
    路徑3: team.starters[0].fullName
    """
    # 路徑 1：probables
    for prob in team_obj.get("probables", []):
        athlete = prob.get("athlete", prob)
        name = athlete.get("displayName") or athlete.get("fullName", "")
        if name:
            return name.strip().split()[-1].lower()

    # 路徑 2：athletes 裡找 starter
    for ath in team_obj.get("athletes", []):
        inner = ath.get("athlete", ath)
        pos = (inner.get("position", {}) or {}).get("abbreviation", "")
        role = ath.get("role", "")
        if pos.upper() in ("SP", "P") or "start" in role.lower():
            name = inner.get("displayName") or inner.get("fullName", "")
            if name:
                return name.strip().split()[-1].lower()

    # 路徑 3：starters 陣列
    for s in team_obj.get("starters", []):
        name = s.get("displayName") or s.get("fullName", "")
        if name:
            return name.strip().split()[-1].lower()

    return ""


# ═══════════════════════════════════════════════════════════════
# 資料獲取：ESPN 積分榜 -> 攻守評分
# ═══════════════════════════════════════════════════════════════

def fetch_stats() -> dict:
    """從 ESPN standings 計算各隊攻守評分，失敗時回傳空字典（使用 BASE）。"""
    urls = [
        "https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings",
        "https://site.web.api.espn.com/apis/v2/sports/baseball/mlb/standings",
    ]
    data = None
    for url in urls:
        data = safe_get(url)
        if data:
            break
    if not data:
        log.warning("ESPN standings failed")
        return {}

    def val(s):
        for k in ("value", "displayValue", "summary"):
            v = s.get(k)
            if v is not None:
                try:
                    return float(str(v).replace(",", ""))
                except Exception:
                    pass
        return 0.0

    ratings = {}
    try:
        for grp in data.get("children", []):
            for e in grp.get("standings", {}).get("entries", []):
                slug = e.get("team", {}).get("abbreviation", "").lower()
                full = SLUG.get(slug)
                if not full:
                    continue
                st = {
                    (s.get("name") or s.get("shortDisplayName", "")): val(s)
                    for s in e.get("stats", [])
                    if s.get("name") or s.get("shortDisplayName")
                }
                w = st.get("wins",   st.get("W", st.get("w", 0)))
                l = st.get("losses", st.get("L", st.get("l", 0)))
                t = w + l
                if t == 0:
                    continue
                wp  = w / t
                rs  = st.get("pointsFor",     st.get("RS", st.get("runsScored",  0)))
                ra  = st.get("pointsAgainst", st.get("RA", st.get("runsAllowed", 0)))
                if rs > 10 and ra > 10:
                    off = round(min(rs / t, 5.5), 2)
                    df  = round(max(ra / t, 3.0), 2)
                else:
                    # 賽季初場次不足，用勝率估算
                    base = BASE.get(full, DEF_RATING)
                    off  = round(min(base["off"] + (wp - 0.5) * 0.5, 5.5), 2)
                    df   = round(max(base["def"] - (wp - 0.5) * 0.5, 3.0), 2)
                ratings[full] = {
                    "off":  off,
                    "def":  df,
                    "form": round((wp - 0.5) * 0.3, 3),
                }
    except Exception as e:
        log.warning("ESPN standings parse error: %s", e)

    log.info("ESPN ratings: %d teams", len(ratings))
    return ratings


# ═══════════════════════════════════════════════════════════════
# 資料獲取：傷兵報告
# ═══════════════════════════════════════════════════════════════

def get_injuries() -> dict:
    """從 RotoWire 抓取傷兵資訊，並合併靜態 OUT 集合。"""
    inj = {}
    try:
        r = requests.get(
            "https://www.rotowire.com/baseball/injury-report.php",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        r.raise_for_status()
        text = r.text.lower()
        out_kw  = ["ruled out", "will not play", "is out", "60-day il", "15-day il", "10-day il"]
        skip_kw = ["questionable", "probable", "available", "day-to-day"]
        for team, players in ROSTER.items():
            for p in players:
                if p not in text:
                    continue
                idx = text.find(p)
                ctx = text[max(0, idx - 80): idx + 200]
                if any(s in ctx for s in skip_kw):
                    continue
                if any(s in ctx for s in out_kw):
                    inj.setdefault(team, []).append(p)
    except Exception as e:
        log.warning("RotoWire failed: %s", e)

    # 靜態 OUT 集合補充
    for team, players in ROSTER.items():
        existing = set(inj.get(team, []))
        for p in players:
            if p in OUT and p not in existing:
                inj.setdefault(team, []).append(p)
                existing.add(p)

    log.info("Injuries: %d players total", sum(len(v) for v in inj.values()))
    return inj


# ═══════════════════════════════════════════════════════════════
# 歷史記錄管理
# ═══════════════════════════════════════════════════════════════

def _purge_old(hist: dict) -> dict:
    cutoff = (datetime.utcnow() - timedelta(days=HIST_TTL)).strftime("%Y-%m-%d")
    return {k: v for k, v in hist.items() if v.get("date", "9999") >= cutoff}


def load_hist() -> dict:
    if not GH_TOKEN:
        return {}
    h = {"Authorization": "token " + GH_TOKEN}
    gists = safe_get("https://api.github.com/gists", headers=h)
    if not gists:
        return {}
    for g in gists:
        if g.get("description") == "mlb_bot_history":
            raw_url = list(g["files"].values())[0]["raw_url"]
            d = safe_get(raw_url)
            if isinstance(d, dict):
                return _purge_old(d)
    return {}


def save_hist(hist: dict, retries: int = 3):
    if not GH_TOKEN:
        return
    hist = _purge_old(hist)
    h    = {"Authorization": "token " + GH_TOKEN, "Content-Type": "application/json"}
    body = json.dumps(hist, ensure_ascii=False, indent=2)
    gists = safe_get("https://api.github.com/gists", headers=h)
    gid  = next(
        (g["id"] for g in (gists or []) if g.get("description") == "mlb_bot_history"),
        None,
    )
    pl = {
        "description": "mlb_bot_history",
        "public": False,
        "files": {"history.json": {"content": body}},
    }
    for attempt in range(1, retries + 1):
        try:
            if gid:
                requests.patch(
                    f"https://api.github.com/gists/{gid}",
                    headers=h, json=pl, timeout=10,
                ).raise_for_status()
            else:
                requests.post(
                    "https://api.github.com/gists",
                    headers=h, json=pl, timeout=10,
                ).raise_for_status()
            log.info("History saved (attempt %d)", attempt)
            return
        except Exception as e:
            log.warning("Save failed %d/%d: %s", attempt, retries, e)
    log.error("History save all failed")


def calc_perf(hist: dict) -> tuple:
    total = win = 0
    profit = 0.0
    for r in hist.values():
        if r.get("result") not in ("win", "loss"):
            continue
        total  += 1
        stake   = r.get("kelly_stake", 10.0)
        if r["result"] == "win":
            win    += 1
            profit += stake * (r.get("price", 1.9) - 1)
        else:
            profit -= stake
    wr = win / total * 100 if total else 0.0
    return total, win, wr, profit


# ═══════════════════════════════════════════════════════════════
# 核心計算
# ═══════════════════════════════════════════════════════════════

def kelly(prob: float, price: float) -> float:
    """分數 Kelly 公式，加上最大下注上限保護。"""
    b = price - 1
    if b <= 0:
        return 0.0
    k = max(0.0, (b * prob - (1 - prob)) / b) * KELLY
    stake = round(BANK * k, 1)
    return min(stake, KELLY_MAX)


def win_prob_from_margin(margin: float) -> float:
    """將得分差 margin 轉換為勝率（正態 CDF）。"""
    return round(0.5 + 0.5 * math.erf(margin / (STD * math.sqrt(2))), 4)


def best_price(books: list, team: str) -> float | None:
    """取所有博彩公司對指定隊伍最高的賠率（對下注者最有利）。"""
    prices = []
    for b in books:
        for m in b.get("markets", []):
            if m.get("key") != "h2h":
                continue
            for o in m.get("outcomes", []):
                if norm(o.get("name", "")) == team and o.get("price"):
                    prices.append((o["price"], b.get("title", "?")))
    if not prices:
        return None, None
    return max(prices, key=lambda x: x[0])


def consensus_ml(books: list, team: str) -> float | None:
    """取所有博彩公司對指定隊伍賠率的平均值（共識賠率）。"""
    prices = []
    for b in books:
        for m in b.get("markets", []):
            if m.get("key") != "h2h":
                continue
            for o in m.get("outcomes", []):
                if norm(o.get("name", "")) == team and o.get("price"):
                    prices.append(o["price"])
    return round(sum(prices) / len(prices), 3) if prices else None


def consensus_total(books: list) -> float | None:
    """取所有博彩公司大小分盤口的平均值。"""
    pts = []
    for b in books:
        for m in b.get("markets", []):
            if m.get("key") != "totals":
                continue
            for o in m.get("outcomes", []):
                if o.get("name", "").lower() == "over" and o.get("point") is not None:
                    pts.append(o["point"])
    return sum(pts) / len(pts) if pts else None


def pitcher_era_adj(pitcher_last: str) -> float:
    """
    計算投手 ERA 對得分的調整量。
    ERA 高於聯盟平均 → 對手得分增加（正值）
    ERA 低於聯盟平均 → 對手得分減少（負值）
    """
    if not pitcher_last:
        return 0.0
    era = PITCHER_ERA.get(pitcher_last.lower())
    if era is None:
        log.debug("Unknown pitcher ERA: %s (using 0 adj)", pitcher_last)
        return 0.0
    return round((era - LEAGUE_AVG_ERA) / 9 * 6, 3)


def _get_missing(team: str, inj: dict) -> list:
    """回傳球隊中傷缺球員清單，含狀態標記。"""
    il     = {p.lower() for p in inj.get(team, [])}
    result = []
    for p in ROSTER.get(team, []):
        if p in OUT or p in il:
            result.append((p, "out", team))
        elif p in LTD:
            result.append((p, "ltd", team))
    return result


def predict_margin(
    home: str, away: str,
    inj: dict, ratings: dict, pitchers: dict,
) -> tuple:
    """
    預測主客隊得分差（主隊視角，正數=主隊領先）。
    回傳: (margin, home_missing_fmt, away_missing_fmt, home_sp, away_sp)
    """
    hb  = ratings.get(home, BASE.get(home, DEF_RATING))
    ab  = ratings.get(away, BASE.get(away, DEF_RATING))
    hs  = {"off": hb["off"], "def": hb["def"]}
    as_ = {"off": ab["off"], "def": ab["def"]}

    hm  = _get_missing(home, inj)
    am  = _get_missing(away, inj)

    for p, s, t in hm:
        pen = (SS_PEN if p in SS else ST_PEN) if s == "out" else LT_PEN
        hs["off"] -= pen * 0.6
        hs["def"] += pen * 0.4

    for p, s, t in am:
        pen = (SS_PEN if p in SS else ST_PEN) if s == "out" else LT_PEN
        as_["off"] -= pen * 0.6
        as_["def"] += pen * 0.4

    h_sp        = pitchers.get(home, "")
    a_sp        = pitchers.get(away, "")
    h_pitch_adj = pitcher_era_adj(h_sp)   # 主隊投手 ERA 調整（影響客隊得分）
    a_pitch_adj = pitcher_era_adj(a_sp)   # 客隊投手 ERA 調整（影響主隊得分）

    # 預期得分：攻撃力 + 對方守備力的平均，加上近期狀態修正，減去對方投手影響
    h_exp  = (hs["off"] + as_["def"]) / 2 + hb.get("form", 0.0) - a_pitch_adj
    a_exp  = (as_["off"] + hs["def"]) / 2 + ab.get("form", 0.0) - h_pitch_adj
    margin = (h_exp - a_exp) + HA

    def fmt(lst):
        return [
            f"{CN.get(t, t[:3])} {p.upper()}({'OUT' if s == 'out' else 'LTD'})"
            for p, s, t in lst
        ]

    return margin, fmt(hm), fmt(am), h_sp, a_sp


def predict_total(
    home: str, away: str,
    ratings: dict, pitchers: dict,
    market_total: float | None = None,
) -> float:
    """預測大小分，混合模型值與市場值。"""
    h     = ratings.get(home, BASE.get(home, DEF_RATING))
    a     = ratings.get(away, BASE.get(away, DEF_RATING))
    h_adj = pitcher_era_adj(pitchers.get(home, ""))
    a_adj = pitcher_era_adj(pitchers.get(away, ""))
    h_exp = h["off"] - a_adj
    a_exp = a["off"] - h_adj
    model_total = round(h_exp + a_exp, 1)
    if market_total:
        return round(model_total * TOT_MOD + market_total * TOT_MKT, 1)
    return model_total


# ═══════════════════════════════════════════════════════════════
# 賠率獲取
# ═══════════════════════════════════════════════════════════════

def fetch_odds() -> list:
    data = safe_get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={
            "apiKey":     ODDS_API_KEY,
            "regions":    "us",
            "markets":    "h2h,totals",
            "oddsFormat": "decimal",
        },
    )
    if not data:
        log.error("Odds API failed")
        return []
    log.info("Odds: %d games", len(data))
    return data


# ═══════════════════════════════════════════════════════════════
# Discord 發送
# ═══════════════════════════════════════════════════════════════

def send(content: str):
    """將長訊息切分後依序發送至 Discord Webhook。"""
    lines  = content.split("\n")
    chunks = []
    buf    = []
    size   = 0
    for line in lines:
        addition = len(line) + 1
        if size + addition > LIMIT and buf:
            chunks.append("\n".join(buf))
            buf  = [line]
            size = addition
        else:
            buf.append(line)
            size += addition
    if buf:
        chunks.append("\n".join(buf))

    total = len(chunks)
    for i, part in enumerate(chunks, 1):
        label = f"({i}/{total})\n{part}" if total > 1 else part
        try:
            r = requests.post(WEBHOOK, json={"content": label}, timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.error("Discord chunk %d failed: %s", i, e)


# ═══════════════════════════════════════════════════════════════
# 主程式
# ═══════════════════════════════════════════════════════════════

def run():
    if not all([ODDS_API_KEY, WEBHOOK]):
        log.error("Missing ODDS_API_KEY or DISCORD_WEBHOOK")
        return

    now_utc  = datetime.utcnow()
    now_tw   = now_utc + timedelta(hours=8)
    today    = now_tw.strftime("%Y-%m-%d")

    # 台灣時間 0~14 點視為當日正式推薦（涵蓋早盤到午間）
    official = (0 <= now_tw.hour < 14)
    log.info("Official: %s (TW %02d:%02d)", official, now_tw.hour, now_tw.minute)

    ratings  = fetch_stats()
    src      = "ESPN" if ratings else "BASE預設值"
    inj      = get_injuries()
    pitchers = fetch_probable_pitchers()
    games    = fetch_odds()
    hist     = load_hist()

    if not games:
        log.error("No games data, aborting")
        return

    picks = {}

    for g in games:
        # ── 時間解析 ─────────────────────────────────────────
        try:
            cut = datetime.strptime(g["commence_time"], "%Y-%m-%dT%H:%M:%SZ")
            ctw = cut + timedelta(hours=8)
        except Exception:
            continue
        if cut < now_utc:
            continue

        gdate = ctw.strftime("%Y-%m-%d")
        home  = norm(g.get("home_team", ""))
        away  = norm(g.get("away_team", ""))
        if not home or not away:
            continue
        gid   = f"{away}@{home}_{gdate}"
        books = g.get("bookmakers", [])
        picks.setdefault(gdate, {})

        # ── 模型計算 ─────────────────────────────────────────
        margin, hm, am, h_sp, a_sp = predict_margin(home, away, inj, ratings, pitchers)
        ct  = consensus_total(books)
        mt  = predict_total(home, away, ratings, pitchers, ct)

        # 大小分傾向
        ou  = ""
        if ct:
            pure = predict_total(home, away, ratings, pitchers)
            diff = pure - ct
            if   diff >  1.5:
                ou = f"大分偏向 OVER  (純模型{pure:.1f} / 市場{ct:.1f})"
            elif diff < -1.5:
                ou = f"小分偏向 UNDER (純模型{pure:.1f} / 市場{ct:.1f})"
            else:
                ou = f"大小分中性     (純模型{pure:.1f} / 市場{ct:.1f})"

        # 先發投手展示字串
        h_era = PITCHER_ERA.get(h_sp) if h_sp else None
        a_era = PITCHER_ERA.get(a_sp) if a_sp else None
        h_sp_str = (f"{h_sp.upper()}(ERA{h_era:.2f})" if h_sp and h_era
                    else (h_sp.upper() if h_sp else "TBD"))
        a_sp_str = (f"{a_sp.upper()}(ERA{a_era:.2f})" if a_sp and a_era
                    else (a_sp.upper() if a_sp else "TBD"))

        # ── 遍歷博彩公司，尋找有價值的賭注 ─────────────────
        # 先計算兩隊的最佳賠率（最高賠率對應最優 book）
        h_best_price, h_best_book = best_price(books, home)
        a_best_price, a_best_book = best_price(books, away)

        for (team, bp, bbook) in [
            (home, h_best_price, h_best_book),
            (away, a_best_price, a_best_book),
        ]:
            if not bp or not (MIN_P < bp <= MAX_P):
                continue

            is_home    = (team == home)
            raw_margin = margin if is_home else -margin

            # 純模型勝率
            model_prob = win_prob_from_margin(raw_margin)

            # 計算無水分市場機率（no-vig），用共識賠率計算
            con_h = consensus_ml(books, home)
            con_a = consensus_ml(books, away)
            if con_h and con_a:
                inv_sum     = 1 / con_h + 1 / con_a
                no_vig_prob = round((1 / (con_h if is_home else con_a)) / inv_sum, 4)
            else:
                no_vig_prob = 1 / bp

            # ★ 關鍵修正：edge 使用純 model_prob 與市場機率的差值
            #    避免 blended prob 因含市場成分而低估 edge
            raw_mkt_prob = 1 / bp
            edge         = model_prob - raw_mkt_prob
            if edge < EDGE_MIN:
                continue

            # 下注用機率：混合模型與市場無水分機率
            bet_prob = min(max(model_prob * MOD_W + no_vig_prob * MKT_W, 0.01), 0.99)

            con_price = con_h if is_home else con_a
            miss      = (hm if is_home else am) + (am if is_home else hm)
            stake     = kelly(bet_prob, bp)

            # 等級判定
            if   edge > 0.10: tier = "💎 頂級"
            elif edge > 0.07: tier = "🔥 強力"
            else:             tier = "⭐ 穩定"

            acn   = CN.get(away, SHORT.get(away, away))
            hcn   = CN.get(home, SHORT.get(home, home))
            bcn   = CN.get(team, SHORT.get(team, team))
            ms    = "傷兵: " + ", ".join(miss) if miss else "陣容正常"
            ou_ln = f"\n> {ou}" if ou else ""

            msg = "\n".join([
                "—" * 15,
                f"**{tier}  {acn} @ {hcn}**",
                f"🕐 {ctw.strftime('%m/%d %H:%M')}",
                f"⚾ 先發: {a_sp_str} — {h_sp_str}",
                f"💰 今日推薦: `{bcn} 獨贏` @ **{bp:.2f}** ({bbook})",
                f"> 共識賠率: {con_price:.2f} | {ms}",
                f"> 勝率: **{model_prob*100:.1f}%** | Edge: **{edge*100:+.1f}%** | Kelly: ${stake:.1f}{ou_ln}",
            ]) + "\n"

            key = f"{gid}_{team}"
            ex  = picks[gdate].get(key)
            if ex is None or edge > ex["edge"]:
                picks[gdate][key] = {
                    "edge": edge, "prob": bet_prob, "price": bp,
                    "kelly_stake": stake, "msg": msg,
                }

            # ★ 修正：所有等級（edge >= EDGE_MIN）都寫入歷史，不限頂級
            if official and gdate == today:
                eh = hist.get(key)
                if eh is None or edge > eh.get("edge", 0):
                    hist[key] = {
                        "date":        gdate,
                        "tier":        tier,
                        "bet":         f"{bcn} 獨贏",
                        "sp":          f"{a_sp_str} vs {h_sp_str}",
                        "book":        bbook,
                        "price":       bp,
                        "model_prob":  round(model_prob, 4),
                        "bet_prob":    round(bet_prob, 4),
                        "edge":        round(edge, 4),
                        "kelly_stake": stake,
                        "result":      eh.get("result", "pending") if eh else "pending",
                    }

    # ── 績效統計 ──────────────────────────────────────────────
    tr, w, wr, pnl = calc_perf(hist)
    tp = sum(len(v) for v in picks.values())
    ae = (sum(p["edge"] for d in picks.values() for p in d.values()) / tp
          if tp else 0)

    # ── 組裝輸出訊息 ──────────────────────────────────────────
    lines = [
        "⚾ **MLB V104 分析報告**",
        f"🕐 {now_tw.strftime('%m/%d %H:%M')} | 資料: {src} | 先發: {'已取得' if pitchers else '未取得'}",
        "📌 正式記錄版本" if official else "🔧 測試版本（不寫入回測）",
        "",
    ]

    if not picks:
        lines.append("今日無符合條件之推薦。")
    else:
        for date in sorted(picks):
            label = "📅 今日賭事" if date == today else f"⏭ 預告 {date}"
            cnt   = len(picks[date])
            lines.append(f"**{label}**（{cnt} 場）")
            for p in sorted(picks[date].values(), key=lambda x: x["edge"], reverse=True):
                lines.append(p["msg"])

    lines += [
        "═" * 20,
        "📊 **歷史績效**（所有等級）",
        f"推薦: {len(hist)} 場 | 已結算: {tr} 場 | 勝率: **{wr:.1f}%** | 損益: **{pnl:+.1f} 元**",
        f"本日場次: {tp} | 平均 Edge: {ae*100:.1f}%",
    ]

    out = "\n".join(lines)
    if official:
        save_hist(hist)
    log.info("Sending to Discord, length: %d", len(out))
    send(out)
    log.info("Done")


if __name__ == "__main__":
    run()
