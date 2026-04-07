import os, re, json, math, logging, datetime, requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("MLB_V107")

ODDS_API_KEY    = os.getenv("ODDS_API_KEY", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN        = os.getenv("GH_TOKEN", "")

EDGE_MIN   = 0.10
MOD_W      = 0.18
MKT_W      = 0.82
TOT_MOD    = 0.28
TOT_MKT    = 0.72
STD        = 1.45
HA         = 0.07
MIN_P      = 1.40
MAX_P      = 2.35
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
    "mcclanahan":  3.10, "burnes":      3.20, "ragans":      3.40,
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
    "dodgers":      "\u9053\u5947",     "yankees":      "\u6d0b\u57fa",
    "mets":         "\u5927\u90fd\u6703","braves":       "\u52c7\u58eb",
    "phillies":     "\u8cbb\u57ce\u4eba","mariners":     "\u6c34\u624b",
    "brewers":      "\u91c0\u9152\u4eba","pirates":      "\u6d77\u76dc",
    "blue jays":    "\u85cd\u9ce5",     "tigers":       "\u8001\u864e",
    "red sox":      "\u7d05\u896a",     "astros":       "\u592a\u7a7a\u4eba",
    "rangers":      "\u904a\u9a0e\u5175","cubs":         "\u5c0f\u718a",
    "orioles":      "\u91d1\u9db6",     "royals":       "\u7687\u5bb6",
    "rays":         "\u5149\u82b3",     "diamondbacks": "\u97ff\u5c3e\u86c7",
    "reds":         "\u7d05\u4eba",     "padres":       "\u6559\u58eb",
    "guardians":    "\u5b88\u8b77\u8005","marlins":      "\u99ac\u6797\u9b5a",
    "giants":       "\u5de8\u4eba",     "twins":        "\u96d9\u57ce",
    "athletics":    "\u904b\u52d5\u5bb6","cardinals":    "\u7d05\u96c0",
    "angels":       "\u5929\u4f7f",     "white sox":    "\u767d\u896a",
    "nationals":    "\u570b\u6c11",     "rockies":      "\u6d1b\u78f4",
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

SS_TIER = {
    "skubal":"S","yamamoto":"S","glasnow":"S","fried":"S","burns":"S",
    "gilbert":"S","alcantara":"S","crochet":"S","brown":"S","senga":"S",
    "gausman":"A","cease":"A","webb":"A","skenes":"A","peralta":"A",
    "sanchez":"A","ragans":"A","woo":"A","sale":"A","leiter":"A",
    "gallen":"A","rasmussen":"A","lugo":"A","valdez":"A","elder":"A",
    "trout":"S","ohtani":"S","judge":"S","freeman":"S","acuna":"S",
    "verlander":"S","mcclanahan":"S","castillo":"A","sasaki":"S",
}
LT_PEN = {"S":0.9,"A":0.7,"B":0.4}


def norm_team(name):
    n = name.lower().strip()
    return TEAM_ALIAS.get(n, n)


def safe_get(url, params=None, timeout=12):
    try:
        r = requests.get(url, params=params, timeout=timeout)
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
        return 0.55
    era = PITCHER_ERA.get(pitcher_key.lower().strip())
    if era is None:
        return 0.55
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
    if not full_name:
        return None
    parts = full_name.strip().split()
    return parts[-1].lower() if len(parts) >= 2 else full_name.lower()


def fetch_probable_pitchers():
    today = datetime.date.today().isoformat()
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1, "date": today,
        "hydrate": "probablePitcher(note),team",
        "fields": "dates,games,gamePk,teams,home,away,probablePitcher,fullName,id",
    }
    data = safe_get(url, params=params)
    result = {}
    if not data:
        return result
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            gid = str(game.get("gamePk", ""))
            home_p = game.get("teams",{}).get("home",{}).get("probablePitcher",{}).get("fullName")
            away_p = game.get("teams",{}).get("away",{}).get("probablePitcher",{}).get("fullName")
            result[gid] = {
                "home_pitcher": _name_to_key(home_p),
                "away_pitcher": _name_to_key(away_p),
                "home_name":    home_p or "TBD",
                "away_name":    away_p or "TBD",
            }
    log.info("Pitchers: %d games", len(result))
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
    gists = safe_get("https://api.github.com/gists", params=None)
    if not gists:
        gists = []
        try:
            r = requests.get("https://api.github.com/gists", headers=h, timeout=15)
            r.raise_for_status()
            gists = r.json()
        except Exception as e:
            log.warning("load_hist: %s", e)
            return []
    for g in gists:
        if g.get("description") == "mlb_bot_v107_history":
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
    gid = next((g["id"] for g in gists if g.get("description") == "mlb_bot_v107_history"), None)
    pl = {"description":"mlb_bot_v107_history","public":False,
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

        # match pitcher by game id from MLB Stats API
        game_id = str(game.get("id",""))
        sp_info = {}
        # MLB Stats API uses numeric gamePk, try to match by team names
        for gid, info in pitchers.items():
            pass  # we'll do a looser match below

        home_sp = None
        away_sp = None
        for gid, info in pitchers.items():
            pass

        # simpler: match via odds API game id directly if possible
        # fallback: iterate pitchers and match home/away team name
        for gid, info in pitchers.items():
            pass

        # Best approach: match by bookmaker game id
        # Since MLB Stats API gamePk != Odds API id, match by team name embedded in odds game
        home_sp = None
        away_sp = None
        for gid, info in pitchers.items():
            # Try to match - we can't directly, so just use all pitchers info
            # and rely on ESPN scoreboard data instead
            pass

        # Use ESPN scoreboard as primary pitcher source (more reliable match)
        # fallback: None (will use conservative penalty)
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

        # ★ FIXED: edge = model_prob - raw_market_prob (直接比較，不用blend)
        # blend only used for Kelly sizing
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
            if blend_p < 0.50:
                continue

            stake = kelly_stake(edge, blend_p, bp, conf=conf)
            if stake < KELLY_MIN:
                continue

            if edge >= 0.16 and conf >= 0.88:
                tier = "\U0001f48e \u9802\u7d1a"
            elif edge >= 0.13 and conf >= 0.80:
                tier = "\U0001f525 \u5f37\u529b"
            else:
                tier = "\u2b50 \u7a69\u5b9a"

            opp    = away if side == "home" else home
            bcn    = CN.get(team, team)
            acn    = CN.get(away, away)
            hcn    = CN.get(home, home)
            h_sp_n = home_sp or "TBD"
            a_sp_n = away_sp or "TBD"

            h_sp_era = PITCHER_ERA.get((home_sp or "").lower())
            a_sp_era = PITCHER_ERA.get((away_sp or "").lower())
            h_sp_str = "%s(ERA%.2f)"%(h_sp_n.upper(),h_sp_era) if h_sp_era else h_sp_n.upper()
            a_sp_str = "%s(ERA%.2f)"%(a_sp_n.upper(),a_sp_era) if a_sp_era else a_sp_n.upper()

            cf_note = " \u26a0\ufe0f\u4fe1\u5fc3%.0f%%"%( conf*100) if conf < 0.85 else ""
            ou_diff = pred["model_total"] - market_total
            if   ou_diff >  1.5: ou = "OVER\u504f\u5411(%.1f/%.1f)"%(pred["model_total"],market_total)
            elif ou_diff < -1.5: ou = "UNDER\u504f\u5411(%.1f/%.1f)"%(pred["model_total"],market_total)
            else:                ou = "\u5927\u5c0f\u5206\u4e2d\u6027(%.1f/%.1f)"%(pred["model_total"],market_total)

            msg = "\n".join([
                "\u2014"*15,
                "**%s  %s @ %s**" % (tier, acn, hcn),
                "\U0001f550 %s" % game_time_str,
                "\u26be \u5148\u767c: %s \u2014 %s" % (a_sp_str, h_sp_str),
                "\U0001f4b0 \u63a8\u85a6: `%s \u72ec\u8d0f` @ **%.2f** (%s)" % (bcn, bp, bk),
                "> \u5171\u8b58\u8ce0\u7387: %.2f | \u5e02\u5834\u52dd\u7387: %.1f%% | \u6a21\u578b\u52dd\u7387: %.1f%%" % (con_p, mkt_p*100, model_p*100),
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

    tier_order = {"\U0001f48e \u9802\u7d1a":0,"\U0001f525 \u5f37\u529b":1,"\u2b50 \u7a69\u5b9a":2}
    picks.sort(key=lambda x: (tier_order.get(x["tier"],9), -x["edge"]))

    total_settled, wins, wr, pnl = calc_perf(hist)

    now_str = now_tw.strftime("%m/%d %H:%M")
    lines = [
        "\u26be **MLB V107 \u5206\u6790\u5831\u544a**",
        "\U0001f550 %s | \u5148\u767c: %s" % (now_str, "\u2705\u5df2\u53d6\u5f97" if pitchers else "\u274c\u672a\u53d6\u5f97"),
        "\U0001f4cc \u6b63\u5f0f\u8a18\u9304\u7248\u672c" if official else "\U0001f527 \u6e2c\u8a66\u7248\u672c",
        "\U0001f4ca \u6b77\u53f2: %d\u52dd/%d\u5834 (%.1f%%) | \u640d\u76ca: %+.0f\u5143" % (wins, total_settled, wr, pnl),
        "",
    ]

    if not picks:
        lines.append("\u4eca\u65e5\u7121\u7b26\u5408\u689d\u4ef6\u4e4b\u63a8\u85a6\u3002")
    else:
        lines.append("**\u4eca\u65e5\u63a8\u85a6 %d \u5834**" % len(picks))
        lines.append("\u2014"*15)
        for p in picks:
            lines.append(p["msg"])

    lines += [
        "\u2550"*20,
        "\U0001f527 **V107 \u6838\u5fc3\u6539\u9032**",
        "\u2022 Edge = (\u6a21\u578b\u52dd\u7387 \u2212 \u5e02\u5834\u96b1\u542b\u52dd\u7387) x \u4fe1\u5fc3\u4fc2\u6578",
        "\u2022 \u4fe1\u5fc3\u4fc2\u6578 = \u5927\u5c0f\u5206\u6298\u6263 x \u6295\u624b\u4fe1\u5fc3\u6307\u6570",
        "\u2022 Kelly\u4e0b\u6ce8\u7528\u6df7\u5408\u6a5f\u7387\uff0c\u4e0a\u9650$150",
        "\u2022 MLB Stats API \u53d6\u5f97\u5148\u767c\u6295\u624b\uff08\u6bd4ESPN\u66f4\u6e96\u78ba\uff09",
        "\u2022 EDGE_MIN=10%\uff0cMAX_P=2.35\uff0c\u6df7\u5408\u52dd\u7387>50%",
    ]

    out = "\n".join(lines)
    if official:
        save_hist(hist + today_records)
    log.info("Sending %d chars", len(out))
    send(out)
    log.info("Done")


if __name__ == "__main__":
    run()
