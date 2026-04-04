# ============================================================
# MLB_V106  全面重構版
# 核心設計哲學改變：
#  1. 大幅提高市場賠率權重（市場才是最聰明的預測者）
#  2. 模型只做「找市場定價錯誤」，不做勝負預測
#  3. BASE全面使用FanGraphs 2026實際RS/G & RA/G投影數據
#  4. 投手ERA字典全面補完，未知投手給予保守懲罰
#  5. 超級球星LTD懲罰獨立加重
#  6. 大小分異常自動降低信心
#  7. EDGE_MIN提高至0.10，場次少但準確率高
#  8. 完全移除虛高勝率顯示，改用市場隱含勝率對照
#  9. 新增近期戰績動態調整（滾動更新）
# 10. Kelly下注更保守，單注上限20元
# ============================================================

import requests, os, logging, json, math
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("MLB_V106")

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
WEBHOOK      = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN     = os.getenv("GH_TOKEN", "")

# ══════════════════════════════════════════════════════════════
# 核心參數（全面保守化）
# ══════════════════════════════════════════════════════════════
EDGE_MIN     = 0.10   # 提高門檻：只推高確信度場次
MOD_W        = 0.20   # 模型權重降低（市場更準）
MKT_W        = 0.80   # 市場權重提高
TOT_MOD      = 0.30   # 大小分模型權重
TOT_MKT      = 0.70   # 大小分市場權重
STD          = 1.5    # 得分差標準差（稍微收窄）
HA           = 0.08   # 主場優勢（保守值）
MIN_P        = 1.40   # 最低賠率（不追極熱門）
MAX_P        = 2.40   # 最高賠率（不追極冷門）
LIMIT        = 1900
BANK         = 1000.0
KELLY        = 0.12   # 更保守Kelly係數
KELLY_MAX    = 20.0   # 單注最高20元
HIST_TTL     = 90
LEAGUE_ERA   = 4.20   # 2026聯盟平均ERA
# 大小分信心折扣門檻
GAP_WARN1    = 1.5    # 輕微警示gap
GAP_WARN2    = 2.5    # 中度警示gap
GAP_WARN3    = 3.5    # 嚴重警示gap

# ══════════════════════════════════════════════════════════════
# 隊名對照
# ══════════════════════════════════════════════════════════════
SLUG = {
    "nyy":"New York Yankees",    "lad":"Los Angeles Dodgers",
    "atl":"Atlanta Braves",      "hou":"Houston Astros",
    "bal":"Baltimore Orioles",   "phi":"Philadelphia Phillies",
    "tex":"Texas Rangers",       "ari":"Arizona Diamondbacks",
    "min":"Minnesota Twins",     "sea":"Seattle Mariners",
    "mil":"Milwaukee Brewers",   "chc":"Chicago Cubs",
    "sf": "San Francisco Giants","bos":"Boston Red Sox",
    "nym":"New York Mets",       "tor":"Toronto Blue Jays",
    "cle":"Cleveland Guardians", "tb": "Tampa Bay Rays",
    "stl":"St. Louis Cardinals", "sd": "San Diego Padres",
    "det":"Detroit Tigers",      "kc": "Kansas City Royals",
    "pit":"Pittsburgh Pirates",  "cin":"Cincinnati Reds",
    "col":"Colorado Rockies",    "oak":"Oakland Athletics",
    "laa":"Los Angeles Angels",  "mia":"Miami Marlins",
    "wsh":"Washington Nationals","chw":"Chicago White Sox",
}
SHORT = {v: k.upper() for k, v in SLUG.items()}
CN = {
    "New York Yankees":      "洋基",  "Los Angeles Dodgers":  "道奇",
    "Atlanta Braves":        "勇士",  "Houston Astros":       "太空人",
    "Baltimore Orioles":     "金鶯",  "Philadelphia Phillies":"費城人",
    "Texas Rangers":         "遊騎兵","Arizona Diamondbacks": "響尾蛇",
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

# ══════════════════════════════════════════════════════════════
# BASE攻守評分
# 來源：FanGraphs 2026 Projected RS/G & RA/G（2026/04/04）
# off = 投影得分/場，def = 投影失分/場（越低守備越強）
# ══════════════════════════════════════════════════════════════
BASE = {
    "Los Angeles Dodgers":   {"off":5.04,"def":4.16},
    "New York Yankees":      {"off":4.73,"def":4.22},
    "New York Mets":         {"off":4.74,"def":4.25},
    "Seattle Mariners":      {"off":4.51,"def":4.08},
    "Atlanta Braves":        {"off":4.70,"def":4.27},
    "Toronto Blue Jays":     {"off":4.64,"def":4.36},
    "Philadelphia Phillies": {"off":4.63,"def":4.40},
    "Texas Rangers":         {"off":4.59,"def":4.39},
    "Boston Red Sox":        {"off":4.49,"def":4.30},
    "Milwaukee Brewers":     {"off":4.56,"def":4.36},
    "Detroit Tigers":        {"off":4.42,"def":4.25},
    "Baltimore Orioles":     {"off":4.71,"def":4.60},
    "Chicago Cubs":          {"off":4.60,"def":4.44},
    "Houston Astros":        {"off":4.63,"def":4.55},
    "Pittsburgh Pirates":    {"off":4.42,"def":4.35},
    "Tampa Bay Rays":        {"off":4.36,"def":4.35},
    "Kansas City Royals":    {"off":4.53,"def":4.57},
    "Arizona Diamondbacks":  {"off":4.55,"def":4.57},
    "San Francisco Giants":  {"off":4.31,"def":4.35},
    "Minnesota Twins":       {"off":4.45,"def":4.55},
    "Cincinnati Reds":       {"off":4.47,"def":4.68},
    "Miami Marlins":         {"off":4.30,"def":4.52},
    "San Diego Padres":      {"off":4.39,"def":4.56},
    "Oakland Athletics":     {"off":4.61,"def":4.81},
    "Cleveland Guardians":   {"off":4.28,"def":4.60},
    "St. Louis Cardinals":   {"off":4.31,"def":4.63},
    "Los Angeles Angels":    {"off":4.33,"def":4.74},
    "Washington Nationals":  {"off":4.29,"def":4.87},
    "Chicago White Sox":     {"off":4.23,"def":5.01},
    "Colorado Rockies":      {"off":4.48,"def":5.50},
}
DEF_BASE = {"off":4.40,"def":4.50}

# ══════════════════════════════════════════════════════════════
# 投手ERA字典（2026賽季，依開幕先發資料全面更新）
# 來源：MLB.com / CBS Sports 2026 Opening Day Starters
# ══════════════════════════════════════════════════════════════
PITCHER_ERA = {
    # ── 頂級王牌 ──────────────────────────────────────────────
    "skenes":      1.96,  # PIT NL Cy Young冠軍
    "yamamoto":    2.49,  # LAD WS MVP
    "crochet":     2.59,  # BOS AL Cy Young亞軍
    "sanchez":     2.50,  # PHI NL Cy Young亞軍（Cristopher Sánchez）
    "sale":        2.58,  # ATL 2024 NL Cy Young
    "brown":       2.43,  # HOU AL Cy Young第3（Hunter Brown）
    "rogers_t":    2.50,  # BAL 下半季1.81 ERA（Trevor Rogers）
    "rasmussen":   2.76,  # TB  復出大爆發
    "mcclanahan":  3.10,  # TB  頂級左投
    "fried":       3.10,  # NYY AL Cy Young第4
    "ohtani":      3.00,  # LAD 雙刀流
    "sasaki":      2.90,  # LAD 頂級新秀
    "skubal":      3.08,  # DET AL Cy Young兩連霸
    "webb":        3.20,  # SF  5連開幕先發
    "gilbert":     3.44,  # SEA 穩定王牌
    "pivetta":     2.87,  # SD  生涯最佳（Nick Pivetta）
    "bieber":      3.40,  # TOR
    "ragans":      3.40,  # KC
    "castillo":    3.30,  # SEA
    "peralta":     3.40,  # NYM（Freddy Peralta）
    "burnes":      3.20,  # 備用
    # ── 穩定先發 ──────────────────────────────────────────────
    "woo":         3.50,  # SEA
    "kirby":       3.50,  # SEA
    "bibee":       4.24,  # CLE
    "williams_g":  3.80,  # CLE（Gavin Williams）
    "eovaldi":     3.80,  # TEX
    "gausman":     3.59,  # TOR
    "ryan":        3.42,  # MIN（Joe Ryan）
    "misiorowski": 4.36,  # MIL 新秀
    "boyd":        3.21,  # CHC（Matthew Boyd）
    "liberatore":  4.21,  # STL
    "abbott":      2.87,  # CIN（Andrew Abbott，2025賽季爆發）
    "burns_c":     3.50,  # CIN（Chase Burns）
    "cavalli":     4.25,  # WSH（Tommy John復出）
    "gallen":      4.00,  # ARI
    "verlander":   3.80,  # DET
    "severino":    4.54,  # ATH
    "freeland":    4.75,  # COL（科爾斯球場加成）
    "alcantara":   4.50,  # MIA（復甦跡象，取中間值）
    "smith_s":     3.81,  # CHW（Shane Smith開幕先發）
    "nola":        3.70,  # PHI
    "musgrove":    3.50,  # SD
    "king_m":      3.90,  # SD（Michael King）
    "flaherty":    3.85,  # ?
    "degrom":      3.50,  # TEX（若健康）
    # ── 輪換/備援先發 ─────────────────────────────────────────
    "imanaga":     3.55,  # CHC
    "steele":      3.75,  # CHC（LTD中）
    "taillon":     4.40,  # CHC
    "soriano":     3.93,  # LAA
    "kikuchi":     4.20,  # LAA
    "buehler":     4.20,  # LAD
    "bello":       4.10,  # BOS
    "berrios":     3.80,  # TOR（傷中）
    "cease":       3.80,  # TOR
    "paddack":     4.30,  # MIA
    "wood":        4.20,  # WSH
    "javier":      4.20,  # HOU
    "keller":      4.00,  # PIT（Mitch Keller）
    "pepiot":      4.30,  # TB
    "springs":     4.30,  # TB
    "winn":        4.30,  # STL
    "wetherholt":  4.50,  # STL
    "mikolas":     4.20,  # STL
    "valdez_f":    3.50,  # DET（Framber Valdez，從HOU轉來）
    "varland":     4.60,  # MIN
    "bradish":     3.65,  # BAL
    "hall_d":      4.30,  # BAL
    "sears":       4.50,  # NYY備援
    "cortes":      4.30,  # NYY備援
    "schlittler":  4.70,  # NYY新秀
    "houser":      4.80,  # NYY備援
    "flexen":      4.90,  # SEA備援
    "blackburn":   4.50,  # OAK
    "kolek":       4.50,  # KC（傷中）
    "lynch":       4.70,  # KC
    "cox":         4.80,  # KC
    "feltner":     5.20,  # COL
    "hudson":      5.00,  # COL
    "gray_s":      3.95,  # STL（Sonny Gray）
    "vsquez":      4.40,  # SD備援
    "mcgreevy":    4.50,  # STL備援
    "warren":      4.60,  # NYY備援
    # ── 今日/近期比賽補入 ─────────────────────────────────────
    "mize":        4.30,  # DET
    "pfaadt":      4.10,  # ARI
    "marquez":     4.90,  # SD備援
    "williamson":  4.60,  # CIN備援
    "junk":        5.10,  # MIA牛棚型
    "fedde":       4.60,  # CHW
    "pallante":    4.60,  # STL
    "poulin":      5.30,  # WSH新秀
    "painter":     4.80,  # PHI新秀備援
    "chandler":    4.00,  # PIT新秀
    "senga":       3.60,  # NYM
    "sheehan":     4.20,  # LAD備援（Emmet Sheehan）
    "peterson_d":  4.20,  # NYM（David Peterson）
    "ray":         4.50,  # NYM（Robbie Ray）
    "tidwell":     4.80,  # NYM新秀
    "mahle":       4.20,  # SF（Tyler Mahle）
    "susac":       4.50,  # SF新秀（Joe Susac）
    "bradley_t":   3.80,  # MIN（Taj Bradley）
    "ryan_j":      3.42,  # MIN同ryan
    "valdez_f2":   3.50,  # DET同valdez_f
}

# ══════════════════════════════════════════════════════════════
# 傷兵名單（2026開幕週，FanGraphs IL報告）
# ══════════════════════════════════════════════════════════════
OUT = frozenset({
    "cole",         # NYY Tommy John（5~6月）
    "hgreene",      # CIN 骨刺手術（7月+）
    "rodón",        # NYY
    "acuna",        # ATL
    "wheeler",      # PHI 胸廓出口症（4月中回歸，初期OUT）
    "blanco",       # HOU Tommy John
    "wesneski",     # HOU Tommy John
    "holliday",     # BAL Hamate手術
    "westburg",     # BAL 至少5月
    "casas",        # BOS 膝傷
    "houck",        # BOS Tommy John
    "teel",         # CHW 腿後腱
    "jobe",         # DET Tommy John
    "olson_r",      # DET 肩傷全季
    "hader",        # HOU 二頭肌腱炎（至少4月底）
    "massey",       # KCR 小腿
    "marsh",        # KCR 肩膀全季
    "manoah",       # LAA 手指
    "rodriguez_g",  # LAA 肩炎
    "rendon",       # LAA 髖關節手術
    "festa",        # MIN 肩膀
    "adams_t",      # MIN 三頭肌
    "lopez_p",      # MIN
    "kolek",        # KCR 斜肌
    "hoglund",      # ATH 背傷
    "degrom",       # TEX
})
LTD = frozenset({
    "trout",        # LAA
    "buxton",       # MIN
    "steele",       # CHC
    "skubal",       # DET（賽季初略受限，後已出賽）
    "riley",        # ATL 核心肌肉
    "berrios",      # TOR 肘炎
    "eflin",        # BAL 肘不適
    "crawford_k",   # BOS 手腕
    "sandoval_p",   # BOS 肘
    "kjerstad",     # BAL 腿後腱
})

# ══════════════════════════════════════════════════════════════
# 超級球星集合（傷病懲罰加重）
# ══════════════════════════════════════════════════════════════
SS = frozenset({
    "ohtani","judge","freeman","acuna","tatis","ramirez","harper",
    "guerrero","trout","cole","wheeler","skubal","sale","fried",
    "lindor","soto","betts","seager","witt","degrom","skenes",
    "verlander","rutschman","henderson","crochet","castillo","sasaki",
    "yamamoto","peralta","ragans","mcclanahan","gilbert","bibee",
    "hgreene","sanchez","rasmussen","pivetta",
})
SS_PEN      = 1.2   # 超級球星OUT懲罰
ST_PEN      = 0.8   # 一般球員OUT懲罰
LT_PEN_SS   = 0.8   # 超級球星LTD懲罰（加重）
LT_PEN_NORM = 0.4   # 一般球員LTD懲罰

# ══════════════════════════════════════════════════════════════
# 工具函數
# ══════════════════════════════════════════════════════════════
def norm(name: str) -> str:
    if not name:
        return name
    n = name.strip()
    if n in SHORT:
        return n
    up = n.upper()
    su = {k.upper(): v for k, v in SLUG.items()}
    if up in su:
        return su[up]
    nl = n.lower()
    for full in SHORT:
        if nl == full.lower():
            return full
    for full in SHORT:
        if nl in full.lower() or full.lower() in nl:
            return full
    return name

def safe_get(url, headers=None, params=None, retries=3, timeout=15):
    for i in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            log.warning("Timeout %d/%d %s", i, retries, url)
        except requests.exceptions.HTTPError as e:
            log.error("HTTP %s %s", e.response.status_code, url)
            break
        except Exception as e:
            log.warning("Err %d/%d: %s", i, retries, e)
    return None

# ══════════════════════════════════════════════════════════════
# 先發投手抓取
# ══════════════════════════════════════════════════════════════
def fetch_probable_pitchers() -> dict:
    today = datetime.utcnow().strftime("%Y%m%d")
    for url in [
        "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
        "https://site.web.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    ]:
        data = safe_get(url, params={"dates": today})
        if data:
            break
    else:
        log.warning("ESPN scoreboard failed")
        return {}

    result = {}
    try:
        for event in data.get("events", []):
            for comp in event.get("competitions", []):
                for team in comp.get("competitors", []):
                    tname = norm(team.get("team", {}).get("displayName", ""))
                    if not tname:
                        continue
                    sp = _extract_sp(team)
                    if sp:
                        result[tname] = sp
                        log.info("SP: %s -> %s", tname, sp)
    except Exception as e:
        log.warning("Pitcher parse: %s", e)
    log.info("Pitchers: %d", len(result))
    return result

def _extract_sp(team_obj: dict) -> str:
    for prob in team_obj.get("probables", []):
        ath = prob.get("athlete", prob)
        name = ath.get("displayName") or ath.get("fullName", "")
        if name:
            return name.strip().split()[-1].lower()
    for ath in team_obj.get("athletes", []):
        inner = ath.get("athlete", ath)
        pos   = (inner.get("position", {}) or {}).get("abbreviation", "")
        role  = ath.get("role", "")
        if pos.upper() in ("SP","P") or "start" in role.lower():
            name = inner.get("displayName") or inner.get("fullName", "")
            if name:
                return name.strip().split()[-1].lower()
    for s in team_obj.get("starters", []):
        name = s.get("displayName") or s.get("fullName", "")
        if name:
            return name.strip().split()[-1].lower()
    return ""

# ══════════════════════════════════════════════════════════════
# ESPN Standings → 動態攻守評分
# ══════════════════════════════════════════════════════════════
def fetch_stats() -> dict:
    for url in [
        "https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings",
        "https://site.web.api.espn.com/apis/v2/sports/baseball/mlb/standings",
    ]:
        data = safe_get(url)
        if data:
            break
    else:
        return {}

    def val(s):
        for k in ("value","displayValue","summary"):
            v = s.get(k)
            if v is not None:
                try:
                    return float(str(v).replace(",",""))
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
                base = BASE.get(full, DEF_BASE)
                st = {
                    (s.get("name") or s.get("shortDisplayName","")): val(s)
                    for s in e.get("stats", [])
                    if s.get("name") or s.get("shortDisplayName")
                }
                w = st.get("wins",   st.get("W", st.get("w", 0)))
                l = st.get("losses", st.get("L", st.get("l", 0)))
                t = w + l
                if t < 5:
                    # 場次不足，完全用FanGraphs投影
                    ratings[full] = {"off": base["off"], "def": base["def"], "form": 0.0}
                    continue
                rs = st.get("pointsFor",     st.get("RS", st.get("runsScored",  0)))
                ra = st.get("pointsAgainst", st.get("RA", st.get("runsAllowed", 0)))
                wp = w / t
                if rs > 10 and ra > 10:
                    live_off = min(rs / t, 6.0)
                    live_def = max(ra / t, 2.8)
                else:
                    live_off = base["off"] + (wp - 0.5) * 0.4
                    live_def = base["def"] - (wp - 0.5) * 0.4
                # 賽季初以FanGraphs投影為主，隨場次增加逐漸轉向實際數據
                alpha = min(t / 40, 0.45)
                ratings[full] = {
                    "off":  round(live_off * alpha + base["off"] * (1 - alpha), 2),
                    "def":  round(live_def * alpha + base["def"] * (1 - alpha), 2),
                    "form": round((wp - 0.5) * 0.15, 3),
                }
    except Exception as e:
        log.warning("Standings parse: %s", e)
    log.info("Ratings: %d teams", len(ratings))
    return ratings

# ══════════════════════════════════════════════════════════════
# 傷兵報告
# ══════════════════════════════════════════════════════════════
def get_injuries() -> dict:
    inj = {}
    try:
        r = requests.get(
            "https://www.rotowire.com/baseball/injury-report.php",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        r.raise_for_status()
        text = r.text.lower()
        out_kw  = ["60-day il","15-day il","10-day il","tommy john",
                   "ruled out","will not play","season-ending"]
        skip_kw = ["probable","questionable","available","day-to-day"]
        for team, players in ROSTER.items():
            for p in players:
                if p not in text:
                    continue
                idx = text.find(p)
                ctx = text[max(0, idx-100): idx+250]
                if any(s in ctx for s in skip_kw):
                    continue
                if any(s in ctx for s in out_kw):
                    inj.setdefault(team, []).append(p)
    except Exception as e:
        log.warning("RotoWire: %s", e)

    # 靜態OUT補充
    for team, players in ROSTER.items():
        exist = set(inj.get(team, []))
        for p in players:
            if p in OUT and p not in exist:
                inj.setdefault(team, []).append(p)
                exist.add(p)
    return inj

# ══════════════════════════════════════════════════════════════
# 歷史記錄
# ══════════════════════════════════════════════════════════════
def _purge(hist: dict) -> dict:
    cutoff = (datetime.utcnow() - timedelta(days=HIST_TTL)).strftime("%Y-%m-%d")
    return {k: v for k, v in hist.items() if v.get("date","9999") >= cutoff}

def load_hist() -> dict:
    if not GH_TOKEN:
        return {}
    h = {"Authorization": "token " + GH_TOKEN}
    gists = safe_get("https://api.github.com/gists", headers=h)
    if not gists:
        return {}
    for g in gists:
        if g.get("description") == "mlb_bot_history_v106":
            raw = list(g["files"].values())[0]["raw_url"]
            d = safe_get(raw)
            if isinstance(d, dict):
                return _purge(d)
    return {}

def save_hist(hist: dict):
    if not GH_TOKEN:
        return
    hist = _purge(hist)
    h    = {"Authorization": "token " + GH_TOKEN, "Content-Type": "application/json"}
    body = json.dumps(hist, ensure_ascii=False, indent=2)
    gists = safe_get("https://api.github.com/gists", headers=h)
    gid   = next(
        (g["id"] for g in (gists or [])
         if g.get("description") == "mlb_bot_history_v106"),
        None,
    )
    pl = {
        "description": "mlb_bot_history_v106",
        "public": False,
        "files": {"history.json": {"content": body}},
    }
    for attempt in range(1, 4):
        try:
            if gid:
                requests.patch(f"https://api.github.com/gists/{gid}",
                               headers=h, json=pl, timeout=10).raise_for_status()
            else:
                requests.post("https://api.github.com/gists",
                              headers=h, json=pl, timeout=10).raise_for_status()
            log.info("History saved (attempt %d)", attempt)
            return
        except Exception as e:
            log.warning("Save %d/3: %s", attempt, e)

def calc_perf(hist: dict) -> tuple:
    total = win = 0
    profit = 0.0
    for r in hist.values():
        if r.get("result") not in ("win","loss"):
            continue
        total += 1
        stake  = r.get("kelly_stake", 10.0)
        if r["result"] == "win":
            win    += 1
            profit += stake * (r.get("price", 1.9) - 1)
        else:
            profit -= stake
    wr = win / total * 100 if total else 0.0
    return total, win, wr, profit

# ══════════════════════════════════════════════════════════════
# 核心計算函數
# ══════════════════════════════════════════════════════════════
def kelly_stake(prob: float, price: float) -> float:
    b = price - 1
    if b <= 0:
        return 0.0
    k = max(0.0, (b * prob - (1 - prob)) / b) * KELLY
    return min(round(BANK * k, 1), KELLY_MAX)

def win_prob(margin: float) -> float:
    """得分差轉勝率（正態CDF）"""
    return round(0.5 + 0.5 * math.erf(margin / (STD * math.sqrt(2))), 4)

def era_adj(pitcher_key: str) -> float:
    """
    投手ERA對對方得分的調整量。
    未知投手：保守懲罰（聯盟均值+0.5），不返回0。
    """
    if not pitcher_key:
        return 0.0
    era = PITCHER_ERA.get(pitcher_key.lower())
    if era is None:
        log.debug("Unknown SP %s → conservative ERA", pitcher_key)
        era = LEAGUE_ERA + 0.50
    return round((era - LEAGUE_ERA) / 9 * 6, 3)

def conf_factor(pure_model: float, market: float | None) -> float:
    """
    大小分信心折扣：純模型與市場差距越大→折扣越重
    用於過濾攻擊力評估嚴重失真的比賽
    """
    if market is None:
        return 1.0
    gap = abs(pure_model - market)
    if   gap <= GAP_WARN1: return 1.00
    elif gap <= GAP_WARN2: return 0.85
    elif gap <= GAP_WARN3: return 0.65
    elif gap <= 5.0:       return 0.45
    else:                  return 0.30

def apply_injury(rating: dict, missing: list) -> dict:
    """套用傷兵懲罰，超級球星LTD加重"""
    r = {"off": rating["off"], "def": rating["def"]}
    for p, s, _ in missing:
        if s == "out":
            pen = SS_PEN if p in SS else ST_PEN
        else:
            pen = LT_PEN_SS if p in SS else LT_PEN_NORM
        r["off"] -= pen * 0.6
        r["def"] += pen * 0.4
    return r

def sp_bonus(team: str, pitchers: dict, missing: list) -> float:
    """
    若明星球員OUT但替換先發質量優異，補回部分懲罰。
    例：COLE OUT但FRIED(ERA3.10)先發→補回投手端損失。
    """
    sp = pitchers.get(team, "")
    if not sp:
        return 0.0
    sp_era = PITCHER_ERA.get(sp.lower(), LEAGUE_ERA + 0.5)
    if sp_era < LEAGUE_ERA:
        bonus = (LEAGUE_ERA - sp_era) / 9 * 3
        return round(min(bonus, 0.35), 3)
    return 0.0

def get_missing(team: str, inj: dict) -> list:
    il = {p.lower() for p in inj.get(team, [])}
    res = []
    for p in ROSTER.get(team, []):
        if p in OUT or p in il:
            res.append((p, "out", team))
        elif p in LTD:
            res.append((p, "ltd", team))
    return res

def predict_margin(home, away, inj, ratings, pitchers):
    hb = ratings.get(home, BASE.get(home, DEF_BASE))
    ab = ratings.get(away, BASE.get(away, DEF_BASE))
    hm = get_missing(home, inj)
    am = get_missing(away, inj)
    hs = apply_injury(hb, hm)
    as_ = apply_injury(ab, am)
    h_sp = pitchers.get(home, "")
    a_sp = pitchers.get(away, "")
    h_adj = era_adj(h_sp)
    a_adj = era_adj(a_sp)
    h_bon = sp_bonus(home, pitchers, hm)
    a_bon = sp_bonus(away, pitchers, am)
    h_exp = (hs["off"] + as_["def"]) / 2 + hb.get("form", 0.0) - a_adj + h_bon
    a_exp = (as_["off"] + hs["def"]) / 2 + ab.get("form", 0.0) - h_adj + a_bon
    margin = (h_exp - a_exp) + HA

    def fmt(lst):
        return [
            f"{CN.get(t,t[:3])} {p.upper()}({'OUT' if s=='out' else 'LTD'})"
            for p, s, t in lst
        ]
    return margin, fmt(hm), fmt(am), h_sp, a_sp

def predict_total(home, away, ratings, pitchers, market=None):
    h = ratings.get(home, BASE.get(home, DEF_BASE))
    a = ratings.get(away, BASE.get(away, DEF_BASE))
    h_adj = era_adj(pitchers.get(home, ""))
    a_adj = era_adj(pitchers.get(away, ""))
    pure = round((h["off"] - a_adj) + (a["off"] - h_adj), 1)
    if market:
        return round(pure * TOT_MOD + market * TOT_MKT, 1), pure
    return pure, pure

def best_price(books, team):
    prices = []
    for b in books:
        for m in b.get("markets", []):
            if m.get("key") != "h2h":
                continue
            for o in m.get("outcomes", []):
                if norm(o.get("name","")) == team and o.get("price"):
                    prices.append((o["price"], b.get("title","?")))
    return max(prices, key=lambda x: x[0]) if prices else (None, None)

def consensus_ml(books, team):
    prices = [
        o["price"]
        for b in books
        for m in b.get("markets", [])
        if m.get("key") == "h2h"
        for o in m.get("outcomes", [])
        if norm(o.get("name","")) == team and o.get("price")
    ]
    return round(sum(prices) / len(prices), 3) if prices else None

def consensus_total(books):
    pts = [
        o["point"]
        for b in books
        for m in b.get("markets", [])
        if m.get("key") == "totals"
        for o in m.get("outcomes", [])
        if o.get("name","").lower() == "over" and o.get("point") is not None
    ]
    return sum(pts) / len(pts) if pts else None

# ══════════════════════════════════════════════════════════════
# 賠率獲取
# ══════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════
# Discord發送
# ══════════════════════════════════════════════════════════════
def send(content: str):
    lines = content.split("\n")
    chunks, buf, size = [], [], 0
    for line in lines:
        add = len(line) + 1
        if size + add > LIMIT and buf:
            chunks.append("\n".join(buf))
            buf, size = [line], add
        else:
            buf.append(line)
            size += add
    if buf:
        chunks.append("\n".join(buf))
    total = len(chunks)
    for i, part in enumerate(chunks, 1):
        label = f"({i}/{total})\n{part}" if total > 1 else part
        try:
            requests.post(WEBHOOK, json={"content": label}, timeout=10).raise_for_status()
        except Exception as e:
            log.error("Discord %d: %s", i, e)

# ══════════════════════════════════════════════════════════════
# ROSTER（最新2026陣容）
# ══════════════════════════════════════════════════════════════
ROSTER = {
    "New York Yankees":      ["fried","judge","goldschmidt","cabrera","volpe","rice","stanton"],
    "Los Angeles Dodgers":   ["yamamoto","ohtani","freeman","betts","sasaki","buehler","pages","sheehan"],
    "Atlanta Braves":        ["sale","acuna","olson","riley","kim","harris"],
    "Houston Astros":        ["brown","pena","abreu","paredes","bregman","javier","springs"],
    "Baltimore Orioles":     ["rogers_t","henderson","rutschman","alonso","holliday","westburg","bradish"],
    "Philadelphia Phillies": ["sanchez","wheeler","nola","harper","schwarber","stott","castellanos"],
    "Texas Rangers":         ["eovaldi","degrom","seager","carter","garcia","taveras"],
    "Arizona Diamondbacks":  ["gallen","kelly","marte","carroll","moreno","pfaadt"],
    "Minnesota Twins":       ["ryan","buxton","lewis","miranda","wallner","bradley_t"],
    "Seattle Mariners":      ["gilbert","woo","kirby","castillo","raleigh","rodriguez_j","arozarena"],
    "Milwaukee Brewers":     ["misiorowski","contreras","chourio","yelich","adames","wiemer"],
    "Chicago Cubs":          ["boyd","steele","imanaga","taillon","suzuki","busch"],
    "San Francisco Giants":  ["webb","devers","adames_n","arraez","bailey","mahle","susac"],
    "Boston Red Sox":        ["crochet","duran","wcontreras","mayer","casas","abreu_w"],
    "New York Mets":         ["peralta","peterson_d","ray","senga","lindor","soto","bichette","vientos","nimmo"],
    "Toronto Blue Jays":     ["gausman","berrios","bieber","cease","guerrero","santander","varsho"],
    "Cleveland Guardians":   ["bibee","williams_g","ramirez","kwan","naylor","freeman_s"],
    "Tampa Bay Rays":        ["rasmussen","pepiot","springs","aranda","caminero","palacios"],
    "St. Louis Cardinals":   ["liberatore","winn","wetherholt","gorman","donovan","walker","mikolas"],
    "San Diego Padres":      ["pivetta","musgrove","king_m","vsquez","tatis","machado","merrill"],
    "Detroit Tigers":        ["skubal","verlander","valdez_f","mize","torkelson","jung","carpenter"],
    "Kansas City Royals":    ["ragans","witt","pasquantino","perez","melendez","lynch"],
    "Pittsburgh Pirates":    ["skenes","chandler","keller","hayes","triolo","davis_h"],
    "Cincinnati Reds":       ["abbott","burns_c","williamson","hgreene","delacruz","suarez","candelario"],
    "Colorado Rockies":      ["freeland","feltner","hudson","tovar","doyle","beck"],
    "Oakland Athletics":     ["severino","blackburn","kurtz","jwilson","rooker","soderstrom"],
    "Los Angeles Angels":    ["soriano","kikuchi","trout","neto","schanuel","rendon"],
    "Miami Marlins":         ["alcantara","paddack","junk","stowers","edwards","caissie"],
    "Washington Nationals":  ["cavalli","poulin","wood","garcia","crews","young"],
    "Chicago White Sox":     ["smith_s","fedde","martin_c","benintendi","anderson","montgomery"],
}

# ══════════════════════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════════════════════
def run():
    if not all([ODDS_API_KEY, WEBHOOK]):
        log.error("Missing env vars")
        return

    now_utc = datetime.utcnow()
    now_tw  = now_utc + timedelta(hours=8)
    today   = now_tw.strftime("%Y-%m-%d")
    official = (0 <= now_tw.hour < 14)
    log.info("TW %02d:%02d | Official: %s", now_tw.hour, now_tw.minute, official)

    # 資料獲取
    raw_ratings = fetch_stats()
    src = "ESPN+FanGraphs" if raw_ratings else "FanGraphs投影"
    # 確保所有隊伍都有評分（用FanGraphs補全）
    ratings = {}
    for full, base in BASE.items():
        if full in raw_ratings:
            ratings[full] = raw_ratings[full]
        else:
            ratings[full] = {"off": base["off"], "def": base["def"], "form": 0.0}

    inj      = get_injuries()
    pitchers = fetch_probable_pitchers()
    games    = fetch_odds()
    hist     = load_hist()

    if not games:
        log.error("No games")
        return

    picks = {}

    for g in games:
        try:
            cut = datetime.strptime(g["commence_time"], "%Y-%m-%dT%H:%M:%SZ")
            ctw = cut + timedelta(hours=8)
        except Exception:
            continue
        if cut < now_utc:
            continue

        gdate = ctw.strftime("%Y-%m-%d")
        home  = norm(g.get("home_team",""))
        away  = norm(g.get("away_team",""))
        if not home or not away:
            continue

        gid   = f"{away}@{home}_{gdate}"
        books = g.get("bookmakers",[])
        picks.setdefault(gdate, {})

        # 模型計算
        margin, hm, am, h_sp, a_sp = predict_margin(home, away, inj, ratings, pitchers)
        ct = consensus_total(books)
        _, pure_mt = predict_total(home, away, ratings, pitchers, ct)
        cf = conf_factor(pure_mt, ct)

        # 大小分標籤
        ou = ""
        if ct:
            diff = pure_mt - ct
            if   diff >  1.5: ou = f"OVER偏向   (模型{pure_mt:.1f}/市場{ct:.1f})"
            elif diff < -1.5: ou = f"UNDER偏向  (模型{pure_mt:.1f}/市場{ct:.1f})"
            else:             ou = f"大小分中性  (模型{pure_mt:.1f}/市場{ct:.1f})"

        # 先發展示
        def sp_label(k):
            if not k: return "TBD"
            era = PITCHER_ERA.get(k.lower())
            return f"{k.upper()}(ERA{era:.2f})" if era else k.upper()

        h_label = sp_label(h_sp)
        a_label = sp_label(a_sp)

        # 兩隊最佳賠率
        h_bp, h_bk = best_price(books, home)
        a_bp, a_bk = best_price(books, away)

        for team, bp, bk in [(home, h_bp, h_bk), (away, a_bp, a_bk)]:
            if not bp or not (MIN_P < bp <= MAX_P):
                continue

            is_home    = (team == home)
            raw_margin = margin if is_home else -margin
            model_prob = win_prob(raw_margin)

            # 市場隱含機率（去除水分）
            con_h = consensus_ml(books, home)
            con_a = consensus_ml(books, away)
            if con_h and con_a:
                inv_sum    = 1 / con_h + 1 / con_a
                mkt_prob   = round((1 / (con_h if is_home else con_a)) / inv_sum, 4)
            else:
                mkt_prob = 1 / bp

            # 市場直接隱含機率（用於edge計算）
            raw_mkt = 1 / bp

            # Edge = 純模型 vs 市場，再乘信心折扣
            edge = (model_prob - raw_mkt) * cf
            if edge < EDGE_MIN:
                continue

            # 下注機率：主要依賴市場無水分機率，模型作微調
            bet_prob = min(max(model_prob * MOD_W + mkt_prob * MKT_W, 0.01), 0.99)
            stake    = kelly_stake(bet_prob, bp)

            con_p = con_h if is_home else con_a
            miss  = (hm if is_home else am) + (am if is_home else hm)
            ms    = "傷兵: " + ", ".join(miss) if miss else "陣容正常"

            # 等級
            if   edge > 0.14: tier = "💎 頂級"
            elif edge > 0.11: tier = "🔥 強力"
            else:             tier = "⭐ 穩定"

            acn   = CN.get(away, away[:3])
            hcn   = CN.get(home, home[:3])
            bcn   = CN.get(team, team[:3])
            cf_note = f" ⚠️折扣{cf:.0%}" if cf < 1.0 else ""
            ou_ln = f"\n> {ou}" if ou else ""

            # 市場隱含勝率（顯示用，比model_prob更誠實）
            mkt_pct = round(mkt_prob * 100, 1)
            mod_pct = round(model_prob * 100, 1)

            msg = "\n".join([
                "—" * 15,
                f"**{tier}  {acn} @ {hcn}**",
                f"🕐 {ctw.strftime('%m/%d %H:%M')}",
                f"⚾ 先發: {a_label} — {h_label}",
                f"💰 推薦: `{bcn} 獨贏` @ **{bp:.2f}** ({bk})",
                f"> 共識賠率: {con_p:.2f} | {ms}",
                f"> 市場勝率: {mkt_pct}% | 模型勝率: {mod_pct}% | Edge: **{edge*100:+.1f}%**{cf_note}",
                f"> Kelly: ${stake:.1f}{ou_ln}",
            ]) + "\n"

            key = f"{gid}_{team}"
            ex  = picks[gdate].get(key)
            if ex is None or edge > ex["edge"]:
                picks[gdate][key] = {
                    "edge": edge, "prob": bet_prob,
                    "price": bp, "kelly_stake": stake, "msg": msg,
                }

            if official and gdate == today:
                eh = hist.get(key)
                if eh is None or edge > eh.get("edge", 0):
                    hist[key] = {
                        "date":        gdate,
                        "tier":        tier,
                        "bet":         f"{bcn} 獨贏",
                        "sp":          f"{a_label} vs {h_label}",
                        "book":        bk,
                        "price":       bp,
                        "model_prob":  round(model_prob, 4),
                        "mkt_prob":    round(mkt_prob,   4),
                        "bet_prob":    round(bet_prob,   4),
                        "edge":        round(edge,       4),
                        "conf_factor": round(cf,         2),
                        "kelly_stake": stake,
                        "result":      eh.get("result","pending") if eh else "pending",
                    }

    # 績效
    tr, w, wr, pnl = calc_perf(hist)
    tp = sum(len(v) for v in picks.values())
    ae = sum(p["edge"] for d in picks.values() for p in d.values()) / tp if tp else 0

    lines = [
        "⚾ **MLB V106 分析報告**",
        f"🕐 {now_tw.strftime('%m/%d %H:%M')} | 資料: {src} | 先發: {'✅已取得' if pitchers else '❌未取得'}",
        "📌 正式記錄版本" if official else "🔧 測試版本",
        "",
    ]

    if not picks:
        lines.append("今日無符合條件之推薦（EDGE_MIN=10%，嚴格篩選）。")
    else:
        for date in sorted(picks):
            label = "📅 今日賭事" if date == today else f"⏭ 預告 {date}"
            lines.append(f"**{label}**（{len(picks[date])} 場）")
            lines.append("———————————————")
            for p in sorted(picks[date].values(), key=lambda x: x["edge"], reverse=True):
                lines.append(p["msg"])

    lines += [
        "═" * 20,
        "📊 **V106 歷史績效**",
        f"推薦: {len(hist)} 場 | 已結算: {tr} 場 | 勝率: **{wr:.1f}%** | 損益: **{pnl:+.1f} 元**",
        f"今日: {tp} 場 | 平均Edge: {ae*100:.1f}%",
        "",
        "🔧 **V106核心改進**",
        "• BASE = FanGraphs 2026 RS/G & RA/G實際投影",
        "• ERA字典全補完，未知投手=均值+0.5（不為0）",
        "• 超級球星LTD懲罰0.4→0.8",
        "• 大小分異常信心折扣（gap>1.5開始折）",
        "• EDGE_MIN 0.06→0.10 | MAX_P 2.80→2.40",
        "• Kelly更保守：係數0.12，上限20元",
        "• 顯示市場勝率vs模型勝率（更透明）",
        "• 新增先發替換補償邏輯",
    ]

    out = "\n".join(lines)
    if official:
        save_hist(hist)
    log.info("Sending %d chars", len(out))
    send(out)
    log.info("Done")


if __name__ == "__main__":
    run()
