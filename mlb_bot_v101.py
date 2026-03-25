import requests
import os
import random
import logging
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("MLB_V101")

ODDS_API_KEY  = os.getenv("ODDS_API_KEY", "")
WEBHOOK       = os.getenv("DISCORD_WEBHOOK", "")
GITHUB_TOKEN  = os.getenv("GH_TOKEN", "")

SIMS             = 50000
EDGE_THRESHOLD   = 0.06
MODEL_WEIGHT     = 0.35
MARKET_WEIGHT    = 0.65
DYNAMIC_STD_BASE = 1.8
HOME_ADVANTAGE   = 0.15
MAX_RUNLINE      = 2.5
MIN_RUNLINE      = 0.5
MIN_PRICE        = 1.75
MAX_PRICE        = 2.15
DISCORD_CHAR_LIMIT = 1900
BANKROLL         = 1000.0
KELLY_FRACTION   = 0.20

IMPACT_PLAYERS = {
    "New York Yankees":        ["cole", "judge", "soto"],
    "Los Angeles Dodgers":     ["glasnow", "freeman", "ohtani"],
    "Atlanta Braves":          ["sale", "acuna", "olson"],
    "Houston Astros":          ["verlander", "altuve", "alvarez"],
    "Baltimore Orioles":       ["burnes", "henderson", "mullins"],
    "Philadelphia Phillies":   ["wheeler", "harper", "turner"],
    "Texas Rangers":           ["eovaldi", "seager", "garcia"],
    "Arizona Diamondbacks":    ["gallen", "walker", "carroll"],
    "Minnesota Twins":         ["gray", "correa", "buxton"],
    "Seattle Mariners":        ["castillo", "rodriguez", "france"],
    "Milwaukee Brewers":       ["peralta", "yelich", "adames"],
    "Chicago Cubs":            ["imanaga", "swanson", "bellinger"],
    "San Francisco Giants":    ["webb", "conforto", "soler"],
    "Boston Red Sox":          ["buehler", "devers", "yoshida"],
    "New York Mets":           ["scherzer", "alonso", "lindor"],
    "Toronto Blue Jays":       ["gausman", "guerrero", "springer"],
    "Cleveland Guardians":     ["bieber", "ramirez", "naylor"],
    "Tampa Bay Rays":          ["mcclanahan", "arozarena", "diaz"],
    "St. Louis Cardinals":     ["mikolas", "goldschmidt", "arenado"],
    "San Diego Padres":        ["musgrove", "tatis", "machado"],
    "Detroit Tigers":          ["skubal", "torkelson", "greene"],
    "Kansas City Royals":      ["singer", "perez", "witt"],
    "Pittsburgh Pirates":      ["skenes", "hayes", "suwinski"],
    "Cincinnati Reds":         ["lodolo", "india", "de la cruz"],
    "Colorado Rockies":        ["freeland", "tovar", "blackmon"],
    "Oakland Athletics":       ["deal", "langeliers", "brown"],
    "Los Angeles Angels":      ["canning", "rendon", "trout"],
    "Miami Marlins":           ["meyer", "soler", "berti"],
    "Washington Nationals":    ["gore", "abrams", "wood"],
    "Chicago White Sox":       ["fried", "robert", "benintendi"],
}

SEASON_OUT = {
    "verlander", "scherzer", "acuna", "rendon", "buxton", "correa",
}

LIMITED_PLAYERS = {
    "trout", "devers", "guerrero",
}

SUPERSTARS = {
    "ohtani", "judge", "freeman", "acuna", "tatis",
    "ramirez", "alvarez", "harper", "guerrero", "trout",
    "cole", "wheeler", "glasnow", "skubal",
}

SUPERSTAR_PENALTY = 1.2
STAR_PENALTY      = 0.8
LIMITED_PENALTY   = 0.4

FALLBACK_RATINGS = {
    "Los Angeles Dodgers":     {"off": 5.2, "def": 3.5},
    "New York Yankees":        {"off": 5.0, "def": 3.7},
    "Atlanta Braves":          {"off": 4.9, "def": 3.6},
    "Houston Astros":          {"off": 4.8, "def": 3.8},
    "Baltimore Orioles":       {"off": 4.7, "def": 3.9},
    "Philadelphia Phillies":   {"off": 4.8, "def": 3.8},
    "Texas Rangers":           {"off": 4.6, "def": 4.0},
    "Arizona Diamondbacks":    {"off": 4.6, "def": 4.0},
    "Minnesota Twins":         {"off": 4.5, "def": 4.1},
    "Seattle Mariners":        {"off": 4.3, "def": 3.7},
    "Milwaukee Brewers":       {"off": 4.4, "def": 3.9},
    "Chicago Cubs":            {"off": 4.4, "def": 4.0},
    "San Francisco Giants":    {"off": 4.2, "def": 4.1},
    "Boston Red Sox":          {"off": 4.6, "def": 4.2},
    "New York Mets":           {"off": 4.4, "def": 4.0},
    "Toronto Blue Jays":       {"off": 4.5, "def": 4.1},
    "Cleveland Guardians":     {"off": 4.3, "def": 3.8},
    "Tampa Bay Rays":          {"off": 4.3, "def": 3.9},
    "St. Louis Cardinals":     {"off": 4.2, "def": 4.1},
    "San Diego Padres":        {"off": 4.4, "def": 3.9},
    "Detroit Tigers":          {"off": 4.1, "def": 4.0},
    "Kansas City Royals":      {"off": 4.3, "def": 4.2},
    "Pittsburgh Pirates":      {"off": 4.0, "def": 4.3},
    "Cincinnati Reds":         {"off": 4.1, "def": 4.4},
    "Colorado Rockies":        {"off": 4.5, "def": 5.1},
    "Oakland Athletics":       {"off": 3.9, "def": 4.6},
    "Los Angeles Angels":      {"off": 4.1, "def": 4.5},
    "Miami Marlins":           {"off": 3.8, "def": 4.2},
    "Washington Nationals":    {"off": 3.9, "def": 4.6},
    "Chicago White Sox":       {"off": 3.8, "def": 4.8},
}
DEFAULT_RATING = {"off": 4.3, "def": 4.3}

TEAM_CN = {
    "New York Yankees":        "洋基",
    "Los Angeles Dodgers":     "道奇",
    "Atlanta Braves":          "勇士",
    "Houston Astros":          "太空人",
    "Baltimore Orioles":       "金鶯",
    "Philadelphia Phillies":   "費城人",
    "Texas Rangers":           "遊騎兵",
    "Arizona Diamondbacks":    "響尾蛇",
    "Minnesota Twins":         "雙城",
    "Seattle Mariners":        "水手",
    "Milwaukee Brewers":       "釀酒人",
    "Chicago Cubs":            "小熊",
    "San Francisco Giants":    "巨人",
    "Boston Red Sox":          "紅襪",
    "New York Mets":           "大都會",
    "Toronto Blue Jays":       "藍鳥",
    "Cleveland Guardians":     "守護者",
    "Tampa Bay Rays":          "光芒",
    "St. Louis Cardinals":     "紅雀",
    "San Diego Padres":        "教士",
    "Detroit Tigers":          "老虎",
    "Kansas City Royals":      "皇家",
    "Pittsburgh Pirates":      "海盜",
    "Cincinnati Reds":         "紅人",
    "Colorado Rockies":        "洛磯",
    "Oakland Athletics":       "運動家",
    "Los Angeles Angels":      "天使",
    "Miami Marlins":           "馬林魚",
    "Washington Nationals":    "國民",
    "Chicago White Sox":       "白襪",
}

# ESPN 縮寫 → 完整隊名
ESPN_SLUG_MAP = {
    "nyy": "New York Yankees",      "lad": "Los Angeles Dodgers",
    "atl": "Atlanta Braves",        "hou": "Houston Astros",
    "bal": "Baltimore Orioles",     "phi": "Philadelphia Phillies",
    "tex": "Texas Rangers",         "ari": "Arizona Diamondbacks",
    "min": "Minnesota Twins",       "sea": "Seattle Mariners",
    "mil": "Milwaukee Brewers",     "chc": "Chicago Cubs",
    "sf":  "San Francisco Giants",  "bos": "Boston Red Sox",
    "nym": "New York Mets",         "tor": "Toronto Blue Jays",
    "cle": "Cleveland Guardians",   "tb":  "Tampa Bay Rays",
    "stl": "St. Louis Cardinals",   "sd":  "San Diego Padres",
    "det": "Detroit Tigers",        "kc":  "Kansas City Royals",
    "pit": "Pittsburgh Pirates",    "cin": "Cincinnati Reds",
    "col": "Colorado Rockies",      "oak": "Oakland Athletics",
    "laa": "Los Angeles Angels",    "mia": "Miami Marlins",
    "wsh": "Washington Nationals",  "chw": "Chicago White Sox",
}


def normalize_team(name):
    if not name:
        return name
    n = name.lower()
    for full in TEAM_CN:
        if n in full.lower() or full.lower() in n:
            return full
    return name


def safe_get(url, headers=None, params=None, retries=3, timeout=15):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            log.warning("Timeout attempt %d/%d: %s", attempt, retries, url)
        except requests.exceptions.HTTPError as e:
            log.error("HTTP error %s: %s", e.response.status_code, url)
            break
        except Exception as e:
            log.warning("Request failed attempt %d/%d: %s", attempt, retries, e)
    return None


def fetch_team_stats():
    if not BALLDONTLIE_KEY:
        return {}
    headers = {"Authorization": BALLDONTLIE_KEY}
    data = safe_get(
        "https://api.balldontlie.io/mlb/v1/games",
        headers=headers,
        params={"seasons[]": 2025, "per_page": 100},
    )
    if not data or "data" not in data:
        log.warning("Balldontlie MLB API failed, using ESPN fallback")
        return fetch_team_stats_espn()
    
    run_stats = {}
    for game in data["data"]:
        if game.get("status") != "Final":
            continue
        home = normalize_team(game["home_team"]["full_name"])
        away = normalize_team(game["away_team"]["full_name"])
        hs   = game.get("home_team_score", 0) or 0
        vs   = game.get("away_team_score", 0) or 0
        if hs and vs:
            for team, scored, allowed in [(home, hs, vs), (away, vs, hs)]:
                r = run_stats.setdefault(team, {"rs": 0, "ra": 0, "g": 0})
                r["rs"] += scored
                r["ra"] += allowed
                r["g"]  += 1

    ratings = {}
    for team, r in run_stats.items():
        if team not in TEAM_CN or r["g"] == 0:
            continue
        win_pct = 0.5  # 無勝敗紀錄時用中性值
        ratings[team] = {
            "off":  round(r["rs"] / r["g"], 2),
            "def":  round(r["ra"] / r["g"], 2),
            "form": round((r["rs"] - r["ra"]) / r["g"] * 0.05, 3),
        }
    log.info("Balldontlie MLB ratings loaded: %d teams", len(ratings))
    return ratings

        for group in data.get("children", []):
            entries = group.get("standings", {}).get("entries", [])
            for entry in entries:
                slug = entry.get("team", {}).get("abbreviation", "").lower()
                full = ESPN_SLUG_MAP.get(slug)
                if not full:
                    continue

                stat_list = entry.get("stats", [])
                stats = {}
                for s in stat_list:
                    name = s.get("name") or s.get("shortDisplayName", "")
                    stats[name] = get_val(s)

                wins   = stats.get("wins", stats.get("W", 0))
                losses = stats.get("losses", stats.get("L", 0))
                total  = wins + losses
                if total == 0:
                    continue

                win_pct = wins / total
                rs = stats.get("pointsFor",     stats.get("RS", stats.get("runsScored", 0)))
                ra = stats.get("pointsAgainst", stats.get("RA", stats.get("runsAllowed", 0)))

                if rs > 0 and ra > 0:
                    off  = round(rs / total, 2)
                    def_ = round(ra / total, 2)
                else:
                    # 無得失分數據時用勝率推算
                    off  = round(3.5 + win_pct * 3.5, 2)
                    def_ = round(5.5 - win_pct * 3.0, 2)

                ratings[full] = {
                    "off":  off,
                    "def":  def_,
                    "form": round((win_pct - 0.5) * 0.5, 3),
                }
    except Exception as e:
        log.warning("ESPN parse error: %s", e)
        # debug：印出第一筆 entry 的原始 stats 方便追查
        try:
            first = data["children"][0]["standings"]["entries"][0]
            log.warning("ESPN first entry sample: %s", json.dumps(first.get("stats", [])[:3]))
        except Exception:
            pass

    log.info("ESPN live ratings loaded: %d teams", len(ratings))
    return ratings


def get_injury_report():
    """從 RotoWire 爬取 MLB 傷兵報告。"""
    try:
        url  = "https://www.rotowire.com/baseball/injury-report.php"
        hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r    = requests.get(url, headers=hdrs, timeout=15)
        r.raise_for_status()

        injured      = {}
        text         = r.text.lower()
        out_keywords = ["ruled out", "will not play", "is out", "has been ruled out",
                        "out (", "60-day il", "15-day il", "10-day il"]
        skip_kw      = ["questionable", "probable", "available", "good to go", "day-to-day"]

        for full_team, players in IMPACT_PLAYERS.items():
            for player in players:
                if player in text:
                    idx     = text.find(player)
                    context = text[max(0, idx - 80):idx + 200]
                    if any(s in context for s in skip_kw):
                        continue
                    if any(s in context for s in out_keywords):
                        injured.setdefault(full_team, []).append(player)

        for team, players in IMPACT_PLAYERS.items():
            for p in players:
                if p in SEASON_OUT and p not in injured.get(team, []):
                    injured.setdefault(team, []).append(p)

        log.info("RotoWire MLB injury loaded: %d entries", sum(len(v) for v in injured.values()))
        return injured

    except Exception as e:
        log.warning("RotoWire failed: %s, using SEASON_OUT fallback", e)
        fallback = {}
        for team, players in IMPACT_PLAYERS.items():
            out = [p for p in players if p in SEASON_OUT]
            if out:
                fallback[team] = out
        return fallback


def load_history():
    if not GITHUB_TOKEN:
        return {}
    headers = {"Authorization": "token %s" % GITHUB_TOKEN}
    gists   = safe_get("https://api.github.com/gists", headers=headers)
    if not gists:
        return {}
    for g in gists:
        if g.get("description") == "mlb_bot_history":
            raw_url = list(g["files"].values())[0]["raw_url"]
            data    = safe_get(raw_url)
            return data if isinstance(data, dict) else {}
    return {}


def save_history(history):
    if not GITHUB_TOKEN:
        return
    headers = {
        "Authorization": "token %s" % GITHUB_TOKEN,
        "Content-Type":  "application/json",
    }
    content = json.dumps(history, ensure_ascii=False, indent=2)
    gists   = safe_get("https://api.github.com/gists", headers=headers)
    gist_id = None
    if gists:
        for g in gists:
            if g.get("description") == "mlb_bot_history":
                gist_id = g["id"]
                break
    payload = {
        "description": "mlb_bot_history",
        "public":      False,
        "files":       {"history.json": {"content": content}},
    }
    try:
        if gist_id:
            requests.patch("https://api.github.com/gists/%s" % gist_id,
                           headers=headers, json=payload, timeout=10)
        else:
            requests.post("https://api.github.com/gists",
                          headers=headers, json=payload, timeout=10)
        log.info("History saved to Gist")
    except Exception as e:
        log.error("Failed to save history: %s", e)


def calc_performance(history):
    total = win = 0
    profit = 0.0
    for record in history.values():
        if record.get("result") not in ["win", "loss"]:
            continue
        total += 1
        stake = record.get("kelly_stake", 10.0)
        if record["result"] == "win":
            win    += 1
            profit += stake * (record.get("price", 1.9) - 1)
        else:
            profit -= stake
    win_rate = (win / total * 100) if total else 0
    return total, win, win_rate, profit


def kelly_stake(prob, price, bankroll, fraction=KELLY_FRACTION):
    q = 1 - prob
    b = price - 1
    k = (b * prob - q) / b
    k = max(0.0, k) * fraction
    return round(bankroll * k, 1)


def predict_margin(home, away, injury_data, live_ratings):
    h_base = live_ratings.get(home, FALLBACK_RATINGS.get(home, DEFAULT_RATING))
    a_base = live_ratings.get(away, FALLBACK_RATINGS.get(away, DEFAULT_RATING))
    h_stat = dict(h_base)
    a_stat = dict(a_base)

    def get_missing(team):
        injured_lower = [p.lower() for p in injury_data.get(team, [])]
        result = []
        for k in IMPACT_PLAYERS.get(team, []):
            if k in SEASON_OUT or any(k in p for p in injured_lower):
                result.append((k, "out"))
            elif k in LIMITED_PLAYERS:
                result.append((k, "limited"))
        return result

    h_missing = get_missing(home)
    a_missing = get_missing(away)

    for p, status in h_missing:
        penalty = (SUPERSTAR_PENALTY if p in SUPERSTARS else STAR_PENALTY) if status == "out" else LIMITED_PENALTY
        h_stat["off"] -= penalty * 0.6
        h_stat["def"] += penalty * 0.4

    for p, status in a_missing:
        penalty = (SUPERSTAR_PENALTY if p in SUPERSTARS else STAR_PENALTY) if status == "out" else LIMITED_PENALTY
        a_stat["off"] -= penalty * 0.6
        a_stat["def"] += penalty * 0.4

    h_expected = (h_stat["off"] + a_stat["def"]) / 2 + h_base.get("form", 0.0)
    a_expected = (a_stat["off"] + h_stat["def"]) / 2 + a_base.get("form", 0.0)
    margin     = (h_expected - a_expected) + HOME_ADVANTAGE

    def fmt(lst):
        return ["%s(%s)" % (p.capitalize(), "傷" if s == "out" else "限") for p, s in lst]

    return margin, fmt(h_missing), fmt(a_missing)


def predict_total(home, away, live_ratings):
    h_base = live_ratings.get(home, FALLBACK_RATINGS.get(home, DEFAULT_RATING))
    a_base = live_ratings.get(away, FALLBACK_RATINGS.get(away, DEFAULT_RATING))
    h_exp  = (h_base["off"] + a_base["def"]) / 2
    a_exp  = (a_base["off"] + h_base["def"]) / 2
    return round((h_exp + a_exp) * 0.98, 1)


def get_consensus_line(bookmakers, team_name):
    lines = []
    for book in bookmakers:
        for market in book.get("markets", []):
            if market.get("key") != "spreads":
                continue
            for outcome in market.get("outcomes", []):
                if normalize_team(outcome.get("name", "")) == team_name:
                    pt = outcome.get("point")
                    if pt is not None:
                        lines.append(pt)
    return (sum(lines) / len(lines)) if lines else None


def get_consensus_total(bookmakers):
    totals = []
    for book in bookmakers:
        for market in book.get("markets", []):
            if market.get("key") != "totals":
                continue
            for outcome in market.get("outcomes", []):
                if outcome.get("name", "").lower() == "over":
                    pt = outcome.get("point")
                    if pt is not None:
                        totals.append(pt)
    return (sum(totals) / len(totals)) if totals else None


def simulate_cover(blended, line):
    wins = sum(
        1 for _ in range(SIMS)
        if blended + random.gauss(0, DYNAMIC_STD_BASE) + line > 0
    )
    return wins / SIMS


def fetch_odds():
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us",
        "markets":    "spreads,totals",
        "oddsFormat": "decimal",
    }
    data = safe_get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params=params,
    )
    if data is None:
        log.error("Odds API failed")
        return []
    log.info("Odds loaded: %d games", len(data))
    return data


def chunked_send(content, webhook):
    lines = content.split("\n")
    chunk, chunks = "", []
    for line in lines:
        if len(chunk) + len(line) + 1 > DISCORD_CHAR_LIMIT:
            chunks.append(chunk)
            chunk = line + "\n"
        else:
            chunk += line + "\n"
    if chunk:
        chunks.append(chunk)
    for i, part in enumerate(chunks, 1):
        label = "(%d/%d)\n%s" % (i, len(chunks), part) if len(chunks) > 1 else part
        try:
            r = requests.post(webhook, json={"content": label}, timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.error("Discord send failed chunk %d: %s", i, e)


def run():
    if not all([ODDS_API_KEY, WEBHOOK]):
        log.error("Missing env vars")
        return

    now_utc = datetime.utcnow()
    now_tw  = now_utc + timedelta(hours=8)
    today_s = now_tw.strftime("%Y-%m-%d")

    is_official_run = (now_utc.hour == 22)
    log.info("Official run: %s (UTC hour: %d)", is_official_run, now_utc.hour)

    live_ratings = fetch_team_stats()
    data_source  = "ESPN即時" if live_ratings else "靜態備用"
    injuries     = get_injury_report()
    games        = fetch_odds()
    history      = load_history()

    if not games:
        return

    daily_picks = {}

    for g in games:
        try:
            c_time_utc = datetime.strptime(g["commence_time"], "%Y-%m-%dT%H:%M:%SZ")
            c_time_tw  = c_time_utc + timedelta(hours=8)
        except (KeyError, ValueError):
            continue

        if c_time_utc < now_utc:
            continue

        g_date     = c_time_tw.strftime("%Y-%m-%d")
        home       = normalize_team(g.get("home_team", ""))
        away       = normalize_team(g.get("away_team", ""))
        game_id    = "%s@%s_%s" % (away, home, g_date)
        bookmakers = g.get("bookmakers", [])

        daily_picks.setdefault(g_date, {})
        margin, h_missing, a_missing = predict_margin(home, away, injuries, live_ratings)

        model_total     = predict_total(home, away, live_ratings)
        consensus_total = get_consensus_total(bookmakers)
        ou_note = ""
        if consensus_total:
            diff = model_total - consensus_total
            if diff > 0.5:
                ou_note = "OU: 模型偏大分 (%.1f vs 市場 %.1f) 偏Over" % (model_total, consensus_total)
            elif diff < -0.5:
                ou_note = "OU: 模型偏小分 (%.1f vs 市場 %.1f) 偏Under" % (model_total, consensus_total)
            else:
                ou_note = "OU: 模型 %.1f vs 市場 %.1f (無明顯偏向)" % (model_total, consensus_total)

        for book in bookmakers:
            for market in book.get("markets", []):
                if market.get("key") != "spreads":
                    continue
                for outcome in market.get("outcomes", []):
                    name  = normalize_team(outcome.get("name", ""))
                    line  = outcome.get("point", 0)
                    price = outcome.get("price", 0)

                    if not (MIN_RUNLINE <= abs(line) <= MAX_RUNLINE):
                        continue
                    if not (MIN_PRICE < price <= MAX_PRICE):
                        continue

                    consensus = get_consensus_line(bookmakers, name)
                    if consensus is None:
                        consensus = line

                    line_advantage = line - consensus if line > 0 else consensus - line
                    if line_advantage < 0:
                        continue

                    target  = margin if name == home else -margin
                    blended = target * MODEL_WEIGHT + (-consensus) * MARKET_WEIGHT
                    prob    = simulate_cover(blended, line)
                    edge    = prob - (1 / price)

                    if edge < EDGE_THRESHOLD:
                        continue

                    missing = (h_missing if name == home else a_missing) + \
                              (a_missing if name == home else h_missing)

                    stake = kelly_stake(prob, price, BANKROLL)

                    if edge > 0.12:
                        tier = "💎 頂級"
                    elif edge > 0.09:
                        tier = "🔥 強力"
                    else:
                        tier = "⭐ 穩定"

                    bet_cn        = TEAM_CN.get(name, name)
                    away_cn       = TEAM_CN.get(away, away)
                    home_cn       = TEAM_CN.get(home, home)
                    missing_str   = "狀況: " + ", ".join(missing) if missing else "陣容完整"
                    consensus_str = "讓分共識: %+.1f" % consensus

                    msg = (
                        "**[%s] %s @ %s** (%s)\n"
                        "投注: `%s %+.1f` @ **%.2f** (%s)\n"
                        "> %s | %s\n"
                        "> 勝率: %.1f%% | Edge: %+.1f%% | Kelly建議: $%.1f\n"
                        "> %s\n"
                    ) % (
                        tier, away_cn, home_cn,
                        c_time_tw.strftime("%m/%d %H:%M"),
                        bet_cn, line, price, book.get("title", "?"),
                        missing_str, consensus_str,
                        prob * 100, edge * 100, stake,
                        ou_note,
                    )

                    existing = daily_picks[g_date].get(game_id)
                    if existing is None or edge > existing["edge"]:
                        daily_picks[g_date][game_id] = {
                            "edge":        edge,
                            "prob":        prob,
                            "price":       price,
                            "kelly_stake": stake,
                            "msg":         msg,
                        }

                    if edge > 0.12 and is_official_run and g_date == today_s:
                        existing_h = history.get(game_id)
                        if existing_h is None or edge > existing_h.get("edge", 0):
                            history[game_id] = {
                                "date":        g_date,
                                "bet":         "%s %+.1f" % (TEAM_CN.get(name, name), line),
                                "book":        book.get("title", "?"),
                                "price":       price,
                                "prob":        round(prob, 4),
                                "edge":        round(edge, 4),
                                "kelly_stake": stake,
                                "result":      existing_h.get("result", "pending") if existing_h else "pending",
                            }

    total_rec, wins, win_rate, profit = calc_performance(history)
    perf_msg = (
        "\n📊 **歷史績效報告** (僅統計💎頂級)\n"
        "總推薦: %d 場 | 已結算: %d 場\n"
        "勝率: %.1f%% | 損益: %+.1f 元\n"
        "（以每場 Kelly 建議金額計算）\n"
    ) % (len(history), total_rec, win_rate, profit)

    total_picks = sum(len(v) for v in daily_picks.values())
    avg_edge    = (
        sum(p["edge"] for d in daily_picks.values() for p in d.values()) / total_picks
        if total_picks else 0
    )

    output = "⚾ MLB V101.0 | 更新: %s | 資料: %s | 推薦: %d 場 | 平均Edge: %+.1f%%\n" % (
        now_tw.strftime("%m/%d %H:%M"), data_source, total_picks, avg_edge * 100
    )

    if is_official_run:
        output += "📌 正式記錄版本\n"
    else:
        output += "🔧 測試版本（不寫入回測）\n"

    if not daily_picks:
        output += "\n今日無符合條件之推薦。\n"
    else:
        for date in sorted(daily_picks):
            label = "📅 今日賽事" if date == today_s else ("⏭ 預告 %s" % date)
            output += "\n%s\n" % label
            for p in sorted(daily_picks[date].values(), key=lambda x: x["edge"], reverse=True):
                output += p["msg"]
            output += "-" * 30 + "\n"

    output += perf_msg

    if is_official_run:
        save_history(history)
        log.info("History saved (official run, top tier only)")
    else:
        log.info("History NOT saved (test run)")

    log.info("Sending to Discord, length: %d", len(output))
    chunked_send(output, WEBHOOK)
    log.info("Done")


if __name__ == "__main__":
    run()
