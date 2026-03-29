# ============================================================
# MLB_V104 — 完整修正版
# ============================================================
import requests, os, logging, json, math, time
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("MLB_V104")

# ── 環境變數 ────────────────────────────────────────────────
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
WEBHOOK      = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN     = os.getenv("GH_TOKEN", "")

# ── 超參數 ──────────────────────────────────────────────────
EDGE_MIN    = 0.06
MOD_W       = 0.25
MKT_W       = 0.75
TOT_MOD     = 0.40
TOT_MKT     = 0.60
STD         = 1.6
HA          = 0.10
MIN_P       = 1.30
MAX_P       = 2.80
LIMIT       = 1900
BANK        = 1000.0
KELLY       = 0.15
HIST_TTL    = 90
OFFICIAL_H  = (0, 10)   # 台灣時間 0~9 點視為正式模式（涵蓋賽前分析時段）

# ── 名單 ────────────────────────────────────────────────────
ROSTER = {
    "New York Yankees":      ["fried","cole","judge","goldschmidt"],
    "Los Angeles Dodgers":   ["ohtani","freeman","betts","tucker"],
    "Atlanta Braves":        ["sale","acuna","olson","riley"],
    "Houston Astros":        ["mccullers","pena","correa","paredes"],
    "Baltimore Orioles":     ["burnes","henderson","rutschman","alonso"],
    "Philadelphia Phillies": ["wheeler","nola","harper","schwarber"],
    "Texas Rangers":         ["degrom","eovaldi","seager","carter"],
    "Arizona Diamondbacks":  ["gallen","marte","carroll","moreno"],
    "Minnesota Twins":       ["buxton","lewis","keaschall","lopez"],
    "Seattle Mariners":      ["castillo","raleigh","rodriguez","arozarena"],
    "Milwaukee Brewers":     ["woodruff","contreras","chourio","yelich"],
    "Chicago Cubs":          ["steele","bregman","crow","suzuki"],
    "San Francisco Giants":  ["webb","devers","adames","arraez"],
    "Boston Red Sox":        ["anthony","duran","wcontreras","mayer"],
    "New York Mets":         ["peralta","lindor","soto","bichette"],
    "Toronto Blue Jays":     ["berrios","bieber","guerrero","santander"],
    "Cleveland Guardians":   ["bibee","ramirez","kwan","gwilliams"],
    "Tampa Bay Rays":        ["mcclanahan","rasmussen","aranda","caminero"],
    "St. Louis Cardinals":   ["liberatore","wetherholt","winn","gorman"],
    "San Diego Padres":      ["musgrove","tatis","machado","merrill"],
    "Detroit Tigers":        ["skubal","rgreene","torkelson","carpenter"],
    "Kansas City Royals":    ["ragans","witt","pasquantino","perez"],
    "Pittsburgh Pirates":    ["skenes","chandler","pjones","hayes"],
    "Cincinnati Reds":       ["burns","hgreene","delacruz","suarez"],
    "Colorado Rockies":      ["freeland","tovar","doyle","beck"],
    "Oakland Athletics":     ["kurtz","jwilson","rooker","soderstrom"],
    "Los Angeles Angels":    ["arodriguez","soriano","trout","manoah"],
    "Miami Marlins":         ["garrett","stowers","edwards","caissie"],
    "Washington Nationals":  ["cavalli","wood","garcia","crews"],
    "Chicago White Sox":     ["smith","montgomery","teel","benintendi"],
}

OUT = frozenset({"cole","santander","lopez","pjones","mccullers"})
LTD = frozenset({"trout","acuna","buxton","degrom","steele"})
SS  = frozenset({
    "ohtani","judge","freeman","acuna","tatis","ramirez","harper",
    "guerrero","trout","cole","wheeler","skubal","sale","fried",
    "lindor","soto","betts","seager","witt","degrom","skenes",
})

SS_PEN = 1.2
ST_PEN = 0.8
LT_PEN = 0.4

BASE = {
    "Los Angeles Dodgers":   {"off":4.8,"def":3.6},
    "New York Yankees":      {"off":4.6,"def":3.8},
    "Atlanta Braves":        {"off":4.5,"def":3.7},
    "Philadelphia Phillies": {"off":4.4,"def":3.8},
    "New York Mets":         {"off":4.4,"def":3.9},
    "San Francisco Giants":  {"off":4.3,"def":3.9},
    "Baltimore Orioles":     {"off":4.3,"def":3.9},
    "Houston Astros":        {"off":4.3,"def":4.0},
    "Cleveland Guardians":   {"off":4.1,"def":3.8},
    "Kansas City Royals":    {"off":4.2,"def":4.0},
    "Detroit Tigers":        {"off":4.0,"def":3.9},
    "Seattle Mariners":      {"off":4.0,"def":3.8},
    "Texas Rangers":         {"off":4.2,"def":4.0},
    "Arizona Diamondbacks":  {"off":4.2,"def":4.0},
    "San Diego Padres":      {"off":4.1,"def":3.9},
    "Chicago Cubs":          {"off":4.1,"def":4.0},
    "Milwaukee Brewers":     {"off":4.0,"def":3.9},
    "Boston Red Sox":        {"off":4.1,"def":4.1},
    "Toronto Blue Jays":     {"off":4.0,"def":4.1},
    "Pittsburgh Pirates":    {"off":3.8,"def":4.0},
    "Cincinnati Reds":       {"off":3.9,"def":4.2},
    "Tampa Bay Rays":        {"off":3.9,"def":3.9},
    "St. Louis Cardinals":   {"off":3.7,"def":4.3},
    "Minnesota Twins":       {"off":3.9,"def":4.2},
    "Oakland Athletics":     {"off":3.8,"def":4.3},
    "Washington Nationals":  {"off":3.6,"def":4.4},
    "Colorado Rockies":      {"off":4.0,"def":4.8},
    "Los Angeles Angels":    {"off":3.7,"def":4.5},
    "Miami Marlins":         {"off":3.5,"def":4.4},
    "Chicago White Sox":     {"off":3.3,"def":4.8},
}
DEF_RATING = {"off":4.0,"def":4.2}

# 注意：ohtani 在 PITCHER_ERA 中保留，但 fetch_probable_pitchers
# 會從 ESPN 實際抓取，若 Ohtani 本季不投球就不會命中此表
PITCHER_ERA = {
    "cole":3.90,"fried":3.10,"wheeler":3.00,"skubal":2.80,"sale":3.20,
    "degrom":2.95,"ohtani":3.10,"burnes":3.30,"castillo":3.40,"webb":3.20,
    "musgrove":3.60,"skenes":3.00,"glasnow":3.10,"ragans":3.40,"woodruff":3.50,
    "gallen":3.50,"mcclanahan":3.30,"bieber":3.50,
    "bibee":3.70,"peralta":3.60,"berrios":3.80,"gausman":3.70,"eovaldi":3.90,
    "steele":3.80,"imanaga":3.60,"burns":3.50,"hgreene":3.80,"nola":3.70,
    "cease":3.90,"flaherty":3.90,"gray":4.00,"rasmussen":4.00,"mikolas":4.30,
    "woo":3.80,"bradish":3.70,"gilbert":3.80,"liberatore":4.50,"cavalli":4.60,
    "garrett":4.20,"mahle":4.10,"peterson":4.20,"keller":4.10,"javier":4.30,
    "detmers":4.40,"lorenzen":4.50,"wacha":4.40,"vasquez":4.50,"cantillo":4.60,
    "horton":4.20,"singer":4.30,"burke":4.80,"patrick":4.50,"springs":4.40,
    "mcgreevy":4.60,"boyle":4.30,"bradley":4.50,"warren":4.70,"rodriguez":4.20,
    "lopez":4.40,"perez":4.60,
    "freeland":4.80,"smith":4.90,"soriano":4.40,"kurtz":4.50,"manoah":4.60,
    "arodriguez":4.50,
}
LEAGUE_AVG_ERA = 4.30

SLUG = {
    "nyy":"New York Yankees","lad":"Los Angeles Dodgers","atl":"Atlanta Braves",
    "hou":"Houston Astros","bal":"Baltimore Orioles","phi":"Philadelphia Phillies",
    "tex":"Texas Rangers","ari":"Arizona Diamondbacks","min":"Minnesota Twins",
    "sea":"Seattle Mariners","mil":"Milwaukee Brewers","chc":"Chicago Cubs",
    "sf":"San Francisco Giants","bos":"Boston Red Sox","nym":"New York Mets",
    "tor":"Toronto Blue Jays","cle":"Cleveland Guardians","tb":"Tampa Bay Rays",
    "stl":"St. Louis Cardinals","sd":"San Diego Padres","det":"Detroit Tigers",
    "kc":"Kansas City Royals","pit":"Pittsburgh Pirates","cin":"Cincinnati Reds",
    "col":"Colorado Rockies","oak":"Oakland Athletics","laa":"Los Angeles Angels",
    "mia":"Miami Marlins","wsh":"Washington Nationals","chw":"Chicago White Sox",
}
SHORT = {v: k.upper() for k, v in SLUG.items()}

CN = {
    "New York Yankees":      "洋基",
    "Los Angeles Dodgers":   "道奇",
    "Atlanta Braves":        "勇士",
    "Houston Astros":        "太空人",
    "Baltimore Orioles":     "金鶯",
    "Philadelphia Phillies": "費城人",
    "Texas Rangers":         "遊騎兵",
    "Arizona Diamondbacks":  "響尾蛇",
    "Minnesota Twins":       "雙城",
    "Seattle Mariners":      "水手",
    "Milwaukee Brewers":     "釀酒人",
    "Chicago Cubs":          "小熊",
    "San Francisco Giants":  "巨人",
    "Boston Red Sox":        "紅襪",
    "New York Mets":         "大都會",
    "Toronto Blue Jays":     "藍鳥",
    "Cleveland Guardians":   "守護者",
    "Tampa Bay Rays":        "光芒",
    "St. Louis Cardinals":   "紅雀",
    "San Diego Padres":      "教士",
    "Detroit Tigers":        "老虎",
    "Kansas City Royals":    "皇家",
    "Pittsburgh Pirates":    "海盜",
    "Cincinnati Reds":       "紅人",
    "Colorado Rockies":      "洛磯",
    "Oakland Athletics":     "運動家",
    "Los Angeles Angels":    "天使",
    "Miami Marlins":         "馬林魚",
    "Washington Nationals":  "國民",
    "Chicago White Sox":     "白襪",
}

# ── 隊名標準化 ───────────────────────────────────────────────

# 預先建立大寫縮寫 -> 全名的查表（避免每次呼叫重建）
_SLUG_UPPER = {k.upper(): v for k, v in SLUG.items()}
_FULL_LOWER = {v.lower(): v for v in SHORT}  # 全名小寫 -> 正式全名

def norm(name: str) -> str:
    """
    將隊名字串標準化為 ROSTER 全名。
    優先順序：
      1. 直接完整命中（如 "New York Yankees"）
      2. 縮寫查表（如 "NYY", "nyy"）
      3. 全名小寫完整比對
      4. 子字串模糊比對（最後手段，有誤匹配風險）
    """
    if not name:
        return name
    n = name.strip()

    # 1. 直接命中已知全名
    if n in SHORT:
        return n

    # 2. 縮寫查表（大小寫不敏感）
    candidate = _SLUG_UPPER.get(n.upper())
    if candidate:
        return candidate

    # 3. 全名小寫完整比對
    candidate = _FULL_LOWER.get(n.lower())
    if candidate:
        return candidate

    # 4. 子字串模糊比對（只在前三關都失敗時）
    n_low = n.lower()
    for full_low, full in _FULL_LOWER.items():
        if n_low in full_low:
            return full

    log.debug("norm() 無法識別隊名: %r", name)
    return name


# ── 基礎 HTTP ────────────────────────────────────────────────

def safe_get(url, headers=None, params=None, retries=3, timeout=15):
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


# ── 先發投手 ────────────────────────────────────────────────

def fetch_probable_pitchers() -> dict:
    """
    從 ESPN scoreboard 抓今日先發投手。
    修正：移除 athletes 作為 fallback（會抓到野手），
    改為只信任 probables 字段，找不到就跳過該隊。
    回傳 {隊伍全名: 投手姓氏小寫}
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
        log.warning("ESPN scoreboard 全部失敗，無先發資料")
        return {}

    team_pitcher: dict = {}
    try:
        for event in data.get("events", []):
            for comp in event.get("competitions", []):
                for team in comp.get("competitors", []):
                    team_name = norm(team.get("team", {}).get("displayName", ""))
                    if not team_name:
                        continue
                    # 只使用 probables，不使用 athletes（athletes 包含全隊球員）
                    probables = team.get("probables", [])
                    if not probables:
                        log.debug("無先發資料: %s", team_name)
                        continue
                    for prob in probables:
                        athlete = prob.get("athlete", {})
                        pitcher = athlete.get("displayName", "")
                        if pitcher:
                            last = pitcher.split()[-1].lower()
                            team_pitcher[team_name] = last
                            log.info("先發: %s → %s", team_name, last)
                            break  # 每隊只取第一位
    except Exception as e:
        log.warning("投手解析錯誤: %s", e)

    log.info("先發投手取得: %d 隊", len(team_pitcher))
    return team_pitcher


def pitcher_era_adj(pitcher_last: str) -> float:
    """
    回傳與聯盟平均的失分差（每場約 6 局）。
    負值 = 投手優於平均 = 壓低對手得分。
    """
    if not pitcher_last:
        return 0.0
    era = PITCHER_ERA.get(pitcher_last.lower())
    if era is None:
        return 0.0
    return round((era - LEAGUE_AVG_ERA) / 9 * 6, 3)


# ── ESPN 戰績/攻守評分 ───────────────────────────────────────

def fetch_stats() -> dict:
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
        log.warning("ESPN standings 失敗，使用靜態 BASE"); return {}

    def val(s):
        for k in ("value", "displayValue", "summary"):
            v = s.get(k)
            if v is not None:
                try:
                    return float(str(v).replace(",", ""))
                except Exception:
                    pass
        return 0.0

    ratings: dict = {}
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
                wp = w / t
                rs = st.get("pointsFor",     st.get("RS", st.get("runsScored", 0)))
                ra = st.get("pointsAgainst", st.get("RA", st.get("runsAllowed", 0)))
                if rs > 10 and ra > 10:
                    off = round(min(rs / t, 5.2), 2)
                    df  = round(max(ra / t, 3.2), 2)
                else:
                    off = round(min(3.2 + wp * 2.0, 5.0), 2)
                    df  = round(max(5.0 - wp * 2.0, 3.2), 2)
                ratings[full] = {
                    "off":  off,
                    "def":  df,
                    "form": round((wp - 0.5) * 0.3, 3),
                }
    except Exception as e:
        log.warning("ESPN standings 解析錯誤: %s", e)

    log.info("ESPN ratings: %d 隊", len(ratings))
    return ratings


# ── 傷兵 ────────────────────────────────────────────────────

def get_injuries() -> dict:
    """
    爬取 RotoWire 傷兵資訊，並強制合併 OUT 固定集合。
    inj[team] 是該隊確定無法出賽的球員 list。
    """
    inj: dict = {}

    try:
        r = requests.get(
            "https://www.rotowire.com/baseball/injury-report.php",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        r.raise_for_status()
        text = r.text.lower()
        out_kw  = ["ruled out","will not play","is out","60-day il","15-day il","10-day il"]
        skip_kw = ["questionable","probable","available","day-to-day"]

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
        log.warning("RotoWire 失敗: %s", e)

    # 固定 OUT 集合強制加入（去重）
    for team, players in ROSTER.items():
        existing = set(inj.get(team, []))
        for p in players:
            if p in OUT and p not in existing:
                inj.setdefault(team, []).append(p)
                existing.add(p)

    log.info("傷兵: %d 條目", sum(len(v) for v in inj.values()))
    return inj


# ── 歷史紀錄 ────────────────────────────────────────────────

def _purge_old(hist: dict) -> dict:
    """清除超過 HIST_TTL 天的歷史記錄。"""
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


def save_hist(hist: dict, retries: int = 3) -> None:
    if not GH_TOKEN:
        return
    hist = _purge_old(hist)
    h = {"Authorization": "token " + GH_TOKEN, "Content-Type": "application/json"}
    body = json.dumps(hist, ensure_ascii=False, indent=2)
    gists = safe_get("https://api.github.com/gists", headers=h)
    gid = next(
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
                    "https://api.github.com/gists/" + gid,
                    headers=h, json=pl, timeout=10,
                ).raise_for_status()
            else:
                requests.post(
                    "https://api.github.com/gists",
                    headers=h, json=pl, timeout=10,
                ).raise_for_status()
            log.info("歷史儲存成功 (第 %d 次)", attempt)
            return
        except Exception as e:
            log.warning("儲存失敗 %d/%d: %s", attempt, retries, e)
    log.error("歷史儲存全部失敗")


def calc_perf(hist: dict):
    total = win = 0
    profit = 0.0
    for r in hist.values():
        if r.get("result") not in ("win", "loss"):
            continue
        total += 1
        stake = r.get("kelly_stake", 10.0)
        if r["result"] == "win":
            win    += 1
            profit += stake * (r.get("price", 1.9) - 1)
        else:
            profit -= stake
    wr = win / total * 100 if total else 0.0
    return total, win, wr, profit


# ── 賠率與機率 ───────────────────────────────────────────────

def kelly(prob: float, price: float) -> float:
    b = price - 1
    if b <= 0:
        return 0.0
    k = max(0.0, (b * prob - (1 - prob)) / b) * KELLY
    return round(BANK * k, 1)


def win_prob_from_margin(margin: float) -> float:
    return round(0.5 + 0.5 * math.erf(margin / (STD * math.sqrt(2))), 4)


def consensus_ml(books: list, team: str) -> float | None:
    prices = []
    for b in books:
        for m in b.get("markets", []):
            if m.get("key") != "h2h":
                continue
            for o in m.get("outcomes", []):
                if norm(o.get("name", "")) == team and o.get("price") is not None:
                    prices.append(o["price"])
    return round(sum(prices) / len(prices), 3) if prices else None


def consensus_total(books: list) -> float | None:
    pts = []
    for b in books:
        for m in b.get("markets", []):
            if m.get("key") != "totals":
                continue
            for o in m.get("outcomes", []):
                if o.get("name", "").lower() == "over" and o.get("point") is not None:
                    pts.append(o["point"])
    return sum(pts) / len(pts) if pts else None


# ── 預測核心 ────────────────────────────────────────────────

def _get_missing(team: str, inj: dict) -> list:
    """
    回傳 [(player, status, team), ...]
    修正：il 集合直接從 inj 取，OUT 判斷與 il 合併，
    避免雙重懲罰（因為 get_injuries 已把 OUT 加入 inj）。
    """
    il = {p.lower() for p in inj.get(team, [])}
    result = []
    for p in ROSTER.get(team, []):
        if p in il:                  # 包含 OUT（已由 get_injuries 加入）
            result.append((p, "out", team))
        elif p in LTD:
            result.append((p, "ltd", team))
    return result


def predict_margin(home: str, away: str, inj: dict, ratings: dict, pitchers: dict):
    """
    預測主隊分差（正值 = 主隊勝）。
    修正：form 統一從 ratings/BASE 取，語意一致；
    hb/ab 不再被 hs/as_ 共用，確保獨立計算。
    """
    src_h = ratings.get(home, BASE.get(home, DEF_RATING))
    src_a = ratings.get(away, BASE.get(away, DEF_RATING))
    hs  = {"off": src_h["off"], "def": src_h["def"]}
    as_ = {"off": src_a["off"], "def": src_a["def"]}
    h_form = src_h.get("form", 0.0)
    a_form = src_a.get("form", 0.0)

    hm = _get_missing(home, inj)
    am = _get_missing(away, inj)

    for p, s, t in hm:
        pen = (SS_PEN if p in SS else ST_PEN) if s == "out" else LT_PEN
        hs["off"] -= pen * 0.6
        hs["def"] += pen * 0.4

    for p, s, t in am:
        pen = (SS_PEN if p in SS else ST_PEN) if s == "out" else LT_PEN
        as_["off"] -= pen * 0.6
        as_["def"] += pen * 0.4

    h_pitcher   = pitchers.get(home, "")
    a_pitcher   = pitchers.get(away, "")
    h_pitch_adj = pitcher_era_adj(h_pitcher)   # 主場投手壓制客隊
    a_pitch_adj = pitcher_era_adj(a_pitcher)   # 客場投手壓制主隊

    he = (hs["off"] + as_["def"]) / 2 + h_form - a_pitch_adj
    ae = (as_["off"] + hs["def"]) / 2 + a_form - h_pitch_adj
    margin = (he - ae) + HA

    def fmt(lst):
        return [
            "%s %s(%s)" % (CN.get(t, t[:3]), p.upper(), "OUT" if s == "out" else "LTD")
            for p, s, t in lst
        ]
    return margin, fmt(hm), fmt(am), h_pitcher, a_pitcher


def predict_total(
    home: str, away: str, ratings: dict, pitchers: dict,
    market_total: float | None = None,
) -> float:
    h = ratings.get(home, BASE.get(home, DEF_RATING))
    a = ratings.get(away, BASE.get(away, DEF_RATING))
    h_adj = pitcher_era_adj(pitchers.get(home, ""))
    a_adj = pitcher_era_adj(pitchers.get(away, ""))
    h_exp = h["off"] - a_adj
    a_exp = a["off"] - h_adj
    model_total = round(h_exp + a_exp, 1)
    if market_total:
        return round(model_total * TOT_MOD + market_total * TOT_MKT, 1)
    return model_total


# ── Odds API ────────────────────────────────────────────────

def fetch_odds() -> list:
    """
    修正：確認回傳值為 list，若 API 回傳 dict（錯誤訊息）則視為失敗。
    """
    data = safe_get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={
            "apiKey":     ODDS_API_KEY,
            "regions":    "us",
            "markets":    "h2h,totals",
            "oddsFormat": "decimal",
        },
    )
    if not isinstance(data, list):
        if isinstance(data, dict):
            log.error("Odds API 回傳錯誤: %s", data.get("message", data))
        else:
            log.error("Odds API 失敗，無回傳資料")
        return []
    log.info("Odds: %d 場比賽", len(data))
    return data


# ── Discord ─────────────────────────────────────────────────

def send(content: str) -> None:
    """
    修正：每次 chunk 之間加入 sleep(0.6)，
    避免觸發 Discord Webhook 速率限制（429）。
    """
    lines  = content.split("\n")
    chunks: list[str] = []
    buf:    list[str] = []
    size = 0

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
        label = "(%d/%d)\n%s" % (i, total, part) if total > 1 else part
        try:
            r = requests.post(WEBHOOK, json={"content": label}, timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.error("Discord chunk %d 傳送失敗: %s", i, e)
        if total > 1:
            time.sleep(0.6)   # 避免 Discord 429


# ── 主程式 ──────────────────────────────────────────────────

def run() -> None:
    if not all([ODDS_API_KEY, WEBHOOK]):
        log.error("缺少環境變數 ODDS_API_KEY 或 DISCORD_WEBHOOK"); return

    now_utc  = datetime.utcnow()
    now_tw   = now_utc + timedelta(hours=8)
    today    = now_tw.strftime("%Y-%m-%d")
    # 修正：擴大正式模式時間窗口到 10 點，確保賽前分析都能寫入歷史
    official = OFFICIAL_H[0] <= now_tw.hour < OFFICIAL_H[1]
    log.info("正式模式: %s (台灣時間 %02d:%02d)", official, now_tw.hour, now_tw.minute)

    ratings  = fetch_stats()
    src      = "ESPN" if ratings else "fallback"
    inj      = get_injuries()
    pitchers = fetch_probable_pitchers()
    games    = fetch_odds()
    hist     = load_hist()
    if not games:
        return

    picks: dict = {}

    for g in games:
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
            log.warning("無法識別隊名: %s / %s", g.get("home_team"), g.get("away_team"))
            continue

        gid   = "%s@%s_%s" % (away, home, gdate)
        books = g.get("bookmakers", [])
        picks.setdefault(gdate, {})

        margin, hm, am, h_sp, a_sp = predict_margin(home, away, inj, ratings, pitchers)
        ct = consensus_total(books)
        ou = ""
        if ct:
            pure = predict_total(home, away, ratings, pitchers)
            d = pure - ct
            if   d >  1.0: ou = "大分偏向 OVER  (純模型%.1f / 市場%.1f)" % (pure, ct)
            elif d < -1.0: ou = "小分偏向 UNDER (純模型%.1f / 市場%.1f)" % (pure, ct)
            else:           ou = "大小分中性     (純模型%.1f / 市場%.1f)" % (pure, ct)

        h_sp_era = PITCHER_ERA.get(h_sp)
        a_sp_era = PITCHER_ERA.get(a_sp)
        h_sp_str = ("%s(ERA%.2f)" % (h_sp.upper(), h_sp_era)
                    if h_sp and h_sp_era else (h_sp.upper() if h_sp else "TBD"))
        a_sp_str = ("%s(ERA%.2f)" % (a_sp.upper(), a_sp_era)
                    if a_sp and a_sp_era else (a_sp.upper() if a_sp else "TBD"))

        for book in books:
            for market in book.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    name  = norm(outcome.get("name", ""))
                    price = outcome.get("price", 0)
                    if not name or not price:
                        continue
                    if not (MIN_P < price <= MAX_P):
                        continue

                    is_home    = (name == home)
                    raw_margin = margin if is_home else -margin
                    model_prob = win_prob_from_margin(raw_margin)
                    mkt_prob   = 1 / price

                    prob = model_prob * MOD_W + mkt_prob * MKT_W
                    prob = min(max(prob, 0.01), 0.99)
                    edge = prob - mkt_prob
                    if edge < EDGE_MIN:
                        continue

                    con_price = consensus_ml(books, name) or price
                    stake     = kelly(prob, price)

                    # 修正：只顯示推薦隊伍自己的傷兵，不顯示對手
                    own_miss = hm if is_home else am
                    ms = "傷兵: " + ", ".join(own_miss) if own_miss else "陣容正常"

                    if   edge > 0.10: tier = "💎 頂級"
                    elif edge > 0.07: tier = "🔥 強力"
                    else:             tier = "⭐ 穩定"

                    acn     = CN.get(away, SHORT.get(away, away))
                    hcn     = CN.get(home, SHORT.get(home, home))
                    bcn     = CN.get(name, SHORT.get(name, name))
                    ou_line = ("\n> %s" % ou) if ou else ""

                    msg = "\n".join([
                        "—" * 15,
                        "**%s  %s @ %s**" % (tier, acn, hcn),
                        "🕐 %s" % ctw.strftime("%m/%d %H:%M"),
                        "⚾ 先發: %s — %s" % (a_sp_str, h_sp_str),
                        "💰 今日推薦: `%s 獨贏` @ **%.2f** (%s)" % (bcn, price, book.get("title","?")),
                        "> 共識賠率: %.2f | %s" % (con_price, ms),
                        "> 勝率: **%.1f%%** | Edge: **%+.1f%%** | Kelly: $%.1f%s" % (
                            prob * 100, edge * 100, stake, ou_line),
                    ]) + "\n"

                    key = gid + "_" + name
                    ex  = picks[gdate].get(key)
                    if ex is None or edge > ex["edge"]:
                        picks[gdate][key] = {
                            "edge": edge, "prob": prob, "price": price,
                            "kelly_stake": stake, "msg": msg,
                        }

                    if edge > 0.10 and official and gdate == today:
                        eh = hist.get(key)
                        if eh is None or edge > eh.get("edge", 0):
                            hist[key] = {
                                "date":        gdate,
                                "bet":         "%s 獨贏" % bcn,
                                "sp":          "%s vs %s" % (a_sp_str, h_sp_str),
                                "book":        book.get("title", "?"),
                                "price":       price,
                                "prob":        round(prob, 4),
                                "edge":        round(edge, 4),
                                "kelly_stake": stake,
                                "result":      eh.get("result", "pending") if eh else "pending",
                            }

    tr, w, wr, pnl = calc_perf(hist)
    tp = sum(len(v) for v in picks.values())
    avg_edge = (
        sum(p["edge"] for d in picks.values() for p in d.values()) / tp
        if tp else 0
    )

    lines = [
        "⚾ **MLB V104 分析報告**",
        "🕐 %s | 資料: %s | 先發: %s | 平均Edge: %+.1f%%" % (
            now_tw.strftime("%m/%d %H:%M"), src,
            "已取得" if pitchers else "未取得",
            avg_edge * 100,   # 修正：avg_edge 現在實際顯示於報告中
        ),
        "📌 正式記錄版本" if official else "🔧 測試版本（不寫入回測）",
        "",
    ]

    if not picks:
        lines.append("今日無符合條件之推薦。")
    else:
        for date in sorted(picks):
            label = "📅 今日賽事" if date == today else "⏭ 預告 %s" % date
            cnt   = len(picks[date])
            lines.append("**%s**（%d 場）" % (label, cnt))
            for p in sorted(picks[date].values(), key=lambda x: x["edge"], reverse=True):
                lines.append(p["msg"])

    lines += [
        "═" * 20,
        "📊 **歷史績效** (💎 頂級專用)",
        "推薦: %d 場 | 已結算: %d 場 | 勝率: **%.1f%%** | 損益: **%+.1f 元**" % (
            len(hist), tr, wr, pnl),
    ]

    out = "\n".join(lines)
    if official:
        save_hist(hist)
    log.info("傳送至 Discord，長度: %d 字元，%d 推薦", len(out), tp)
    send(out)
    log.info("完成")


if __name__ == "__main__":
    run()
