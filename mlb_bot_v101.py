import os, re, json, math, logging, datetime, requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("MLB_V108")

ODDS_API_KEY    = os.getenv("ODDS_API_KEY", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN        = os.getenv("GH_TOKEN", "")

EDGE_MIN   = 0.08   # 降低門檻 (原0.10) 避免沒推薦
MOD_W      = 0.18
MKT_W      = 0.82
TOT_MOD    = 0.28
TOT_MKT    = 0.72
STD        = 1.45
HA         = 0.07
MIN_P      = 1.35   # 略放寬 (原1.40)
MAX_P      = 2.50   # 略放寬 (原2.35)
BANK       = 1000.0
KELLY      = 0.12
KELLY_MAX  = 150.0
KELLY_MIN  = 5.0
LEAGUE_ERA = 4.20
HIST_TTL   = 90
GAP1       = 1.5
GAP2       = 2.5
GAP3       = 3.5
EARLY_GAMES = 30

PITCHER_ERA = {
    "skubal":      2.90, "yamamoto":    2.49, "glasnow":     3.00,
    "fried":       1.35, "gausman":     0.75, "schlittler":  0.00,
    "sanchez":     0.79, "skenes":      1.96, "gilbert":     1.38,
    "woo":         1.38, "alcantara":   0.00, "burns":       0.82,
    "crochet":     2.59, "brown":       0.84, "cease":       2.79,
    "webb":        5.00, "pivetta":     0.75, "vasquez":     0.75,
    "peralta":     3.09, "senga":       3.09, "ryan":        4.82,
    "bibee":       4.24, "ragans":      3.20, "lugo":        1.59,
    "valdez":      0.75, "leiter":      2.45, "elder":       0.00,
    "sale":        2.58, "roupp":       4.22, "mccullers":   3.27,
    "gallen":      3.60, "rodriguez_e": 0.00, "soroka":      0.90,
    "rasmussen":   3.18, "boyle":       3.18, "hancock":     0.71,
    "rogers_t":    1.81, "eovaldi":     1.73, "springs":     2.38,
    "ashcraft":    2.25, "mlodzinski":  4.00, "soriano_j":   3.93,
    "detmers":     2.38, "freeland":    5.20, "misiorowski": 4.36,
    "bradley_t":   0.87, "liberatore":  4.21, "severino":    2.38,
    "cavalli":     4.25, "boyd":        3.21, "horton":      3.60,
    "abbott":      3.42, "burke_s":     3.60, "smith_s":     3.81,
    "pfaadt":      4.10, "weathers":    4.50, "williamson":  4.30,
    "chandler":    4.40, "mize":        4.20, "pallante":    4.50,
    "mikolas":     4.80, "marquez":     4.80, "flexen":      5.10,
    "taillon":     4.40, "voth":        4.80, "adon":        4.60,
    "kolek":       4.50, "crawford_k":  4.20, "sandoval_p":  4.00,
    "imanaga":     3.55, "steele":      3.75, "wetherholt":  4.50,
    "winn":        4.30, "keller":      4.00, "pepiot":      4.30,
    "blackburn":   4.50, "javier":      4.20, "paddack":     4.30,
    "wood":        4.20, "musgrove":    3.50, "king_m":      3.90,
    "bieber":      3.40, "castillo":    3.30, "nola":        3.70,
    "flaherty":    3.85, "ohtani":      3.00, "sasaki":      2.90,
    "mcclanahan":  3.10, "burnes":      3.20,
    "verlander":   3.80, "kirby":       3.50, "bello":       4.10,
    "berrios":     3.80, "junk":        5.10, "fedde":       4.60,
    "poulin":      5.30, "painter":     4.80, "mahle":       4.20,
    "burns_c":     3.50, "burns_s":     0.82,
}

BASE = {
    "dodgers":      (5.10, 4.15), "yankees":      (4.85, 4.20),
    "mets":         (4.74, 4.21), "braves":        (4.76, 4.24),
    "phillies":     (4.58, 4.30), "mariners":      (4.44, 4.06),
    "brewers":      (4.62, 4.36), "pirates":       (4.50, 4.32),
    "blue jays":    (4.54, 4.38), "tigers":        (4.46, 4.24),
    "red sox":      (4.46, 4.28), "astros":        (4.72, 4.58),
    "rangers":      (4.50, 4.38), "cubs":          (4.54, 4.41),
    "orioles":      (4.68, 4.60), "royals":        (4.60, 4.58),
    "rays":         (4.34, 4.36), "diamondbacks":  (4.47, 4.58),
    "reds":         (4.42, 4.62), "padres":        (4.40, 4.52),
    "guardians":    (4.30, 4.50), "marlins":       (4.37, 4.54),
    "giants":       (4.22, 4.40), "twins":         (4.46, 4.58),
    "athletics":    (4.66, 4.88), "cardinals":     (4.28, 4.65),
    "angels":       (4.28, 4.72), "white sox":     (4.18, 4.98),
    "nationals":    (4.30, 4.98), "rockies":       (4.38, 5.42),
}
DEF_BASE = (4.40, 4.50)

CN = {
    "dodgers":      "道奇",     "yankees":      "洋基",
    "mets":         "大都會",   "braves":       "勇士",
    "phillies":     "費城人",   "mariners":     "水手",
    "brewers":      "釀酒人",   "pirates":      "海盜",
    "blue jays":    "藍鳥",     "tigers":       "老虎",
    "red sox":      "紅襪",     "astros":       "太空人",
    "rangers":      "遊騎兵",   "cubs":         "小熊",
    "orioles":      "金鶯",     "royals":       "皇家",
    "rays":         "光芒",     "diamondbacks": "響尾蛇",
    "reds":         "紅人",     "padres":       "教士",
    "guardians":    "守護者",   "marlins":      "馬林魚",
    "giants":       "巨人",     "twins":        "雙城",
    "athletics":    "運動家",   "cardinals":    "紅雀",
    "angels":       "天使",     "white sox":    "白襪",
    "nationals":    "國民",     "rockies":      "落磯",
}

TEAM_ALIAS = {
    "los angeles dodgers":"dodgers","la dodgers":"dodgers",
    "new york yankees":"yankees","ny yankees":"yankees",
    "new york mets":"mets","ny mets":"mets",
    "atlanta braves":"braves",
    "philadelphia phillies":"phillies",
    "seattle mariners":"mariners",
    "milwaukee brewers":"brewers",
    "pittsburgh pirates":"pirates",
    "toronto blue jays":"blue jays",
    "detroit tigers":"tigers",
    "boston red sox":"red sox",
    "houston astros":"astros",
    "texas rangers":"rangers",
    "chicago cubs":"cubs",
    "baltimore orioles":"orioles",
    "kansas city royals":"royals",
    "tampa bay rays":"rays",
    "arizona diamondbacks":"diamondbacks","az diamondbacks":"diamondbacks",
    "cincinnati reds":"reds",
    "san diego padres":"padres",
    "cleveland guardians":"guardians",
    "miami marlins":"marlins",
    "san francisco giants":"giants",
    "minnesota twins":"twins",
    "oakland athletics":"athletics","sacramento athletics":"athletics",
    "st. louis cardinals":"cardinals","st louis cardinals":"cardinals",
    "los angeles angels":"angels","la angels":"angels",
    "chicago white sox":"white sox",
    "washington nationals":"nationals",
    "colorado rockies":"rockies",
}

# MLB Stats API team id -> short name mapping
MLB_TEAM_ID = {
    108:"angels",109:"diamondbacks",110:"orioles",111:"red sox",
    112:"cubs",113:"reds",114:"guardians",115:"rockies",
    116:"tigers",117:"astros",118:"royals",119:"dodgers",
    120:"nationals",121:"mets",133:"athletics",134:"pirates",
    135:"padres",136:"mariners",137:"giants",138:"cardinals",
    139:"rays",140:"rangers",141:"blue jays",142:"twins",
    143:"phillies",144:"braves",145:"white sox",146:"marlins",
    147:"yankees",158:"brewers",
}

OUT = {
    "athletics":    ["hoglund"],
    "orioles":      ["westburg","bautista"],
    "red sox":      ["houck","gonzalez_r"],
    "white sox":    ["bush_k"],
    "tigers":       ["jobe","melton","olson_r","brieske"],
    "astros":       ["wesneski","walter_b"],
    "royals":       ["marsh"],
    "angels":       ["rendon","stephenson_r"],
    "dodgers":      ["snell"],
    "braves":       ["schwellenbach","waldrep","acuna"],
    "twins":        ["lopez_p"],
    "padres":       ["buehler_w"],
    "phillies":     ["cole_w","wheeler_z"],
    "yankees":      ["cole","rodon"],
    "reds":         ["hgreene"],
}

LTD = {
    "orioles":      [("holliday","A"),("kjerstad","B"),("eflin","A")],
    "red sox":      [("casas","B"),("sandoval_p","B"),("crawford_k","B")],
    "white sox":    [("teel","B")],
    "tigers":       [("verlander","S"),("skubal","S")],
    "astros":       [("hader","S"),("brown","S")],
    "royals":       [("kolek","B")],
    "angels":       [("rodriguez_g","A"),("manoah","B"),("trout","S")],
    "braves":       [("riley","A")],
    "cubs":         [("steele","A")],
    "twins":        [("festa","B"),("adams_t","B"),("buxton","A")],
}

LT_PEN = {"S":0.9,"A":0.7,"B":0.4}


def norm_team(name):
    n = name.lower().strip()
    return TEAM_ALIAS.get(n, n)


def safe_get(url, params=None, headers=None, timeout=12):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("safe_get %s: %s", url, e)
        return None


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def win_prob_from_margin(margin, std=STD):
    p = norm_cdf(margin / std)
    return max(0.05, min(0.95, p))


def era_adj(pitcher_key):
    if not pitcher_key:
        era = LEAGUE_ERA + 0.60
    else:
        era = PITCHER_ERA.get(pitcher_key.lower().strip(), LEAGUE_ERA + 0.60)
    return round((era - LEAGUE_ERA) * 0.35, 3)


def injury_penalty(team):
    t = team.lower()
    penalty = 0.0
    for _ in OUT.get(t, []):
        penalty += 0.05
    for _, tier in LTD.get(t, []):
        penalty += LT_PEN.get(tier, 0.4) * 0.15
    return round(min(penalty, 1.2), 3)


def pitcher_confidence(pitcher_key):
    if not pitcher_key:
        return 0.60   # 提高未知投手基礎信心 (原0.55)
    era = PITCHER_ERA.get(pitcher_key.lower().strip())
    if era is None:
        return 0.60
    if era <= 2.5:   return 1.0
    elif era <= 3.2: return 0.92
    elif era <= 4.0: return 0.82
    elif era <= 4.5: return 0.72
    else:            return 0.62


def total_confidence(model_total, market_total):
    gap = abs(model_total - market_total)
    if gap < GAP1:   return 1.00
    elif gap < GAP2: return 0.90
    elif gap < GAP3: return 0.78
    else:            return 0.65


def predict(home, away, home_sp, away_sp, market_total=8.5, season_games=0):
    hb = BASE.get(home, DEF_BASE)
    ab = BASE.get(away, DEF_BASE)
    h_off, h_def = hb
    a_off, a_def = ab
    h_sp_adj = era_adj(home_sp)
    a_sp_adj = era_adj(away_sp)
    h_expected = h_off + a_sp_adj + HA
    a_expected = a_off + h_sp_adj
    h_inj = injury_penalty(home)
    a_inj = injury_penalty(away)
    h_expected -= h_inj * 0.4
    a_expected -= a_inj * 0.4
    h_expected = max(2.5, h_expected)
    a_expected = max(2.5, a_expected)
    margin = h_expected - a_expected
    model_win_p = win_prob_from_margin(margin, STD)
    model_total = h_expected + a_expected
    conf = total_confidence(model_total, market_total)
    pc_h = pitcher_confidence(home_sp)
    pc_a = pitcher_confidence(away_sp)
    conf *= (pc_h * pc_a) ** 0.5
    return {
        "home_win_prob": round(model_win_p, 4),
        "away_win_prob": round(1 - model_win_p, 4),
        "model_total":   round(model_total, 2),
        "conf_factor":   round(max(0.40, min(1.0, conf)), 3),
        "h_expected":    round(h_expected, 2),
        "a_expected":    round(a_expected, 2),
        "margin":        round(margin, 3),
    }


def kelly_stake(edge, prob, price, conf=1.0):
    if edge <= 0 or price <= 1.0:
        return 0.0
    b = price - 1.0
    q = 1.0 - prob
    raw_k = (b * prob - q) / b
    dyn_k = max(0.05, min(0.18, KELLY * conf))
    stake = dyn_k * raw_k * BANK
    return round(max(0.0, min(KELLY_MAX, stake)), 1)


def _name_to_key(full_name):
    """Convert 'Tarik Skubal' -> 'skubal'"""
    if not full_name:
        return None
    parts = full_name.strip().split()
    return parts[-1].lower() if len(parts) >= 2 else full_name.lower()


# ─────────────────────────────────────────────
# ★ 核心修復：用 MLB Stats API teamId 精準匹配
# ─────────────────────────────────────────────
def fetch_probable_pitchers():
    """
    回傳格式: { (home_norm, away_norm): {home_pitcher, away_pitcher, ...}, ... }
    以球隊名稱 tuple 作為 key，讓後面比對更容易。
    """
    today = datetime.date.today().isoformat()
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1, "date": today,
        "hydrate": "probablePitcher(note),team",
        "fields": "dates,games,gamePk,teams,home,away,probablePitcher,fullName,id,team,name",
    }
    data = safe_get(url, params=params)
    result = {}
    if not data:
        return result

    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            home_data = game.get("teams", {}).get("home", {})
            away_data = game.get("teams", {}).get("away", {})

            # 用 teamId 查短名
            home_tid = home_data.get("team", {}).get("id")
            away_tid = away_data.get("team", {}).get("id")
            home_short = MLB_TEAM_ID.get(home_tid)
            away_short = MLB_TEAM_ID.get(away_tid)

            # 備用：用球隊全名轉換
            if not home_short:
                home_short = norm_team(home_data.get("team", {}).get("name", ""))
            if not away_short:
                away_short = norm_team(away_data.get("team", {}).get("name", ""))

            home_p = home_data.get("probablePitcher", {}).get("fullName")
            away_p = away_data.get("probablePitcher", {}).get("fullName")

            info = {
                "home_pitcher": _name_to_key(home_p),
                "away_pitcher": _name_to_key(away_p),
                "home_name":    home_p or "TBD",
                "away_name":    away_p or "TBD",
            }

            if home_short and away_short:
                result[(home_short, away_short)] = info
                log.info("Pitcher match: %s vs %s | HP=%s AP=%s",
                         home_short, away_short, info["home_pitcher"], info["away_pitcher"])

    log.info("Pitchers: %d games resolved", len(result))
    return result


def fetch_odds():
    if not ODDS_API_KEY:
        log.error("ODDS_API_KEY not set")
        return []
    data = safe_get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={"apiKey":ODDS_API_KEY,"regions":"us",
                "markets":"h2h,totals","oddsFormat":"decimal","dateFormat":"iso"},
    )
    if not data:
        return []
    log.info("Odds: %d games", len(data))
    return data


def _purge(records):
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=HIST_TTL)).strftime("%Y-%m-%d")
    return [r for r in records if r.get("date","9999") >= cutoff]


def load_hist():
    if not GH_TOKEN:
        return []
    h = {"Authorization": "token " + GH_TOKEN}
    try:
        r = requests.get("https://api.github.com/gists", headers=h, timeout=15)
        r.raise_for_status()
        gists = r.json()
    except Exception as e:
        log.warning("load_hist: %s", e)
        return []
    for g in gists:
        if g.get("description") == "mlb_bot_v108_history":
            try:
                raw_url = list(g["files"].values())[0]["raw_url"]
                r2 = requests.get(raw_url, timeout=15)
                records = r2.json()
                return _purge(records)
            except Exception as e:
                log.warning("load_hist parse: %s", e)
    return []


def save_hist(records):
    if not GH_TOKEN:
        return
    records = _purge(records)
    h = {"Authorization": "token " + GH_TOKEN, "Content-Type": "application/json"}
    body = json.dumps(records, ensure_ascii=False, indent=2)
    try:
        r = requests.get("https://api.github.com/gists", headers=h, timeout=15)
        r.raise_for_status()
        gists = r.json()
    except Exception as e:
        log.warning("save_hist list: %s", e)
        return
    gid = next((g["id"] for g in gists if g.get("description") == "mlb_bot_v108_history"), None)
    pl = {"description":"mlb_bot_v108_history","public":False,
          "files":{"history.json":{"content":body}}}
    for attempt in range(1, 4):
        try:
            if gid:
                requests.patch("https://api.github.com/gists/"+gid,
                               headers=h, json=pl, timeout=10).raise_for_status()
            else:
                requests.post("https://api.github.com/gists",
                              headers=h, json=pl, timeout=10).raise_for_status()
            log.info("History saved (attempt %d)", attempt)
            return
        except Exception as e:
            log.warning("save_hist %d/3: %s", attempt, e)


def calc_perf(hist):
    settled = [r for r in hist if r.get("result") in ("W","L")]
    wins = sum(1 for r in settled if r.get("result") == "W")
    pnl  = sum(r.get("pnl", 0) or 0 for r in settled)
    wr   = wins / len(settled) * 100 if settled else 0.0
    return len(settled), wins, wr, pnl


def send(content):
    if not DISCORD_WEBHOOK:
        print(content)
        return
    LIMIT = 1900
    chunks, cur = [], ""
    for line in content.split("\n"):
        if len(cur) + len(line) + 1 > LIMIT:
            chunks.append(cur)
            cur = line + "\n"
        else:
            cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    total = len(chunks)
    for i, chunk in enumerate(chunks, 1):
        label = "(%d/%d)\n%s" % (i, total, chunk) if total > 1 else chunk
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": label}, timeout=10).raise_for_status()
        except Exception as e:
            log.error("Discord %d: %s", i, e)


def run():
    now_tw = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    today_str = now_tw.strftime("%Y-%m-%d")
    log.info("TW time: %s", now_tw.strftime("%Y-%m-%d %H:%M"))
    official = (0 <= now_tw.hour < 14)

    if not ODDS_API_KEY:
        log.error("ODDS_API_KEY not set")
        return

    hist      = load_hist()
    odds_data = fetch_odds()
    # ★ pitchers 現在是 {(home, away): info} dict
    pitchers  = fetch_probable_pitchers()

    if not odds_data:
        log.error("No odds data")
        return

    season_games = sum(1 for r in hist if r.get("date","") >= "2026-03-25")
    log.info("Season games recorded: %d", season_games)

    picks = []
    today_records = []

    for game in odds_data:
        if game.get("sport_key") != "baseball_mlb":
            continue

        commence = game.get("commence_time","")
        try:
            game_utc = datetime.datetime.fromisoformat(commence.replace("Z","+00:00"))
            game_tw  = game_utc + datetime.timedelta(hours=8)
            game_time_str = game_tw.strftime("%m/%d %H:%M")
        except Exception:
            game_time_str = commence[:16]

        home = norm_team(game.get("home_team",""))
        away = norm_team(game.get("away_team",""))
        if home not in BASE or away not in BASE:
            log.debug("Skip unknown teams: %s vs %s", home, away)
            continue

        # ★ 核心修復：直接用 (home, away) tuple 查投手
        sp_info = pitchers.get((home, away), {})
        home_sp = sp_info.get("home_pitcher")
        away_sp = sp_info.get("away_pitcher")
        if not sp_info:
            log.debug("No pitcher info for %s vs %s", home, away)

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        home_price = None
        away_price = None
        home_book  = None
        away_book  = None
        market_total = 8.5
        con_h_prices = []
        con_a_prices = []

        for bm in bookmakers:
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "h2h":
                    for outcome in mkt.get("outcomes", []):
                        t = norm_team(outcome.get("name",""))
                        p = outcome.get("price", 0)
                        if t == home:
                            con_h_prices.append(p)
                            if home_price is None or p > home_price:
                                home_price = p
                                home_book  = bm.get("title","?")
                        if t == away:
                            con_a_prices.append(p)
                            if away_price is None or p > away_price:
                                away_price = p
                                away_book  = bm.get("title","?")
                if mkt.get("key") == "totals":
                    for outcome in mkt.get("outcomes", []):
                        if outcome.get("name") in ("Over","Under"):
                            try:
                                market_total = float(outcome.get("point", 8.5))
                            except Exception:
                                pass

        if home_price is None or away_price is None:
            continue

        con_h = round(sum(con_h_prices)/len(con_h_prices), 3) if con_h_prices else home_price
        con_a = round(sum(con_a_prices)/len(con_a_prices), 3) if con_a_prices else away_price

        pred = predict(home, away, home_sp, away_sp,
                       market_total=market_total, season_games=season_games)

        # no-vig market prob
        if con_h and con_a:
            inv_sum   = 1/con_h + 1/con_a
            h_mkt_nv  = round((1/con_h) / inv_sum, 4)
            a_mkt_nv  = round((1/con_a) / inv_sum, 4)
        else:
            h_mkt_nv = 1/home_price
            a_mkt_nv = 1/away_price

        conf = pred["conf_factor"]

        h_raw_mkt = 1/home_price
        a_raw_mkt = 1/away_price

        h_model = pred["home_win_prob"]
        a_model = pred["away_win_prob"]

        h_edge = (h_model - h_raw_mkt) * conf
        a_edge = (a_model - a_raw_mkt) * conf

        # blend for kelly
        h_blend = MOD_W * h_model + MKT_W * h_mkt_nv
        a_blend = MOD_W * a_model + MKT_W * a_mkt_nv

        for side, team, bp, bk, edge, blend_p, model_p, mkt_p, con_p in [
            ("home", home, home_price, home_book, h_edge, h_blend, h_model, h_raw_mkt, con_h),
            ("away", away, away_price, away_book, a_edge, a_blend, a_model, a_raw_mkt, con_a),
        ]:
            if edge < EDGE_MIN:
                continue
            if bp < MIN_P or bp > MAX_P:
                continue
            if blend_p < 0.48:   # 略放寬 (原0.50)
                continue

            stake = kelly_stake(edge, blend_p, bp, conf=conf)
            if stake < KELLY_MIN:
                continue

            if edge >= 0.16 and conf >= 0.88:
                tier = "💎 頂級"
            elif edge >= 0.13 and conf >= 0.80:
                tier = "🔥 強力"
            else:
                tier = "⭐ 穩定"

            opp    = away if side == "home" else home
            bcn    = CN.get(team, team)
            acn    = CN.get(away, away)
            hcn    = CN.get(home, home)
            h_sp_n = sp_info.get("home_name", "TBD") if sp_info else "TBD"
            a_sp_n = sp_info.get("away_name", "TBD") if sp_info else "TBD"

            h_sp_era = PITCHER_ERA.get((home_sp or "").lower())
            a_sp_era = PITCHER_ERA.get((away_sp or "").lower())
            h_sp_str = "%s(ERA%.2f)"%(h_sp_n,h_sp_era) if h_sp_era is not None else h_sp_n
            a_sp_str = "%s(ERA%.2f)"%(a_sp_n,a_sp_era) if a_sp_era is not None else a_sp_n

            cf_note = " ⚠️信心%.0f%%"%(conf*100) if conf < 0.85 else ""
            ou_diff = pred["model_total"] - market_total
            if   ou_diff >  1.5: ou = "OVER偏向(%.1f/%.1f)"%(pred["model_total"],market_total)
            elif ou_diff < -1.5: ou = "UNDER偏向(%.1f/%.1f)"%(pred["model_total"],market_total)
            else:                ou = "大小分中性(%.1f/%.1f)"%(pred["model_total"],market_total)

            msg = "\n".join([
                "—"*15,
                "**%s  %s @ %s**" % (tier, acn, hcn),
                "🕐 %s" % game_time_str,
                "⚾ 先發: %s — %s" % (a_sp_str, h_sp_str),
                "💰 推薦: `%s 獨贏` @ **%.2f** (%s)" % (bcn, bp, bk),
                "> 共識賠率: %.2f | 市場勝率: %.1f%% | 模型勝率: %.1f%%" % (con_p, mkt_p*100, model_p*100),
                "> Edge: **%+.1f%%**%s | Kelly: $%.1f" % (edge*100, cf_note, stake),
                "> %s" % ou,
            ]) + "\n"

            picks.append({
                "msg": msg, "tier": tier, "team": team, "opp": opp,
                "side": side, "price": bp, "blend_p": blend_p,
                "edge": edge, "conf": conf, "stake": stake,
                "game_time": game_time_str,
            })

            if official:
                today_records.append({
                    "date": today_str, "team": team, "opp": opp,
                    "price": bp, "stake": stake,
                    "edge": round(edge,4), "conf": round(conf,3),
                    "result": None, "pnl": None,
                })

    tier_order = {"💎 頂級":0,"🔥 強力":1,"⭐ 穩定":2}
    picks.sort(key=lambda x: (tier_order.get(x["tier"],9), -x["edge"]))

    total_settled, wins, wr, pnl = calc_perf(hist)

    now_str = now_tw.strftime("%m/%d %H:%M")
    pitcher_status = "✅已取得" if pitchers else "❌未取得"
    lines = [
        "⚾ **MLB V108 分析報告**",
        "🕐 %s | 先發: %s" % (now_str, pitcher_status),
        "📌 正式記錄版本" if official else "🔧 測試版本",
        "📊 歷史: %d勝/%d場 (%.1f%%) | 損益: %+.0f元" % (wins, total_settled, wr, pnl),
        "",
    ]

    if not picks:
        # 診斷資訊：顯示今日場次與 edge 情況
        lines.append("今日無符合條件之推薦。")
        lines.append("")
        lines.append("📋 **診斷：今日場次 edge 概況**")
        diag_lines = []
        for game in odds_data:
            if game.get("sport_key") != "baseball_mlb":
                continue
            home = norm_team(game.get("home_team",""))
            away = norm_team(game.get("away_team",""))
            if home not in BASE or away not in BASE:
                continue
            sp_info = pitchers.get((home, away), {})
            home_sp = sp_info.get("home_pitcher")
            away_sp = sp_info.get("away_pitcher")
            bookmakers = game.get("bookmakers", [])
            if not bookmakers:
                continue
            home_price = None
            away_price = None
            market_total = 8.5
            for bm in bookmakers:
                for mkt in bm.get("markets", []):
                    if mkt.get("key") == "h2h":
                        for outcome in mkt.get("outcomes", []):
                            t = norm_team(outcome.get("name",""))
                            p = outcome.get("price", 0)
                            if t == home and (home_price is None or p > home_price):
                                home_price = p
                            if t == away and (away_price is None or p > away_price):
                                away_price = p
                    if mkt.get("key") == "totals":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") in ("Over","Under"):
                                try: market_total = float(outcome.get("point", 8.5))
                                except: pass
            if not home_price or not away_price:
                continue
            pred = predict(home, away, home_sp, away_sp, market_total=market_total)
            conf = pred["conf_factor"]
            h_edge = (pred["home_win_prob"] - 1/home_price) * conf
            a_edge = (pred["away_win_prob"] - 1/away_price) * conf
            best_edge = max(h_edge, a_edge)
            best_side = CN.get(home,home) if h_edge >= a_edge else CN.get(away,away)
            best_price = home_price if h_edge >= a_edge else away_price
            hn = CN.get(home,home)
            an = CN.get(away,away)
            diag_lines.append(
                "`%s@%s` Edge=%+.1f%% P=%.2f conf=%.0f%% SP:%s/%s" % (
                    an, hn, best_edge*100, best_price, conf*100,
                    home_sp or "?", away_sp or "?"
                )
            )
        for dl in sorted(diag_lines, key=lambda x: -float(x.split("Edge=")[1].split("%")[0])):
            lines.append(dl)
    else:
        lines.append("**今日推薦 %d 場**" % len(picks))
        lines.append("—"*15)
        for p in picks:
            lines.append(p["msg"])

    lines += [
        "═"*20,
        "🔧 **V108 核心改進**",
        "• 投手比對：MLB teamId → 短名精準匹配（修復主要 bug）",
        "• EDGE_MIN 8%（原10%）、MAX_P 2.50（原2.35）",
        "• 無推薦時顯示診斷 edge 表",
        "• 未知投手基礎信心 60%（原55%）",
    ]

    out = "\n".join(lines)
    if official:
        save_hist(hist + today_records)
    log.info("Sending %d chars", len(out))
    send(out)
    log.info("Done")


if __name__ == "__main__":
    run()
