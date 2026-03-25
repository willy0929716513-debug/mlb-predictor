import requests
import os
import random
import logging
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(“MLB_V101”)

ODDS_API_KEY  = os.getenv(“ODDS_API_KEY”, “”)
WEBHOOK       = os.getenv(“DISCORD_WEBHOOK”, “”)
GITHUB_TOKEN  = os.getenv(“GH_TOKEN”, “”)

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
“New York Yankees”:        [“fried”, “cole”, “judge”, “goldschmidt”],
“Los Angeles Dodgers”:     [“ohtani”, “freeman”, “betts”, “tucker”],
“Atlanta Braves”:          [“sale”, “acuna”, “olson”, “riley”],
“Houston Astros”:          [“mccullers”, “pena”, “correa”, “paredes”],
“Baltimore Orioles”:       [“burnes”, “henderson”, “rutschman”, “alonso”],
“Philadelphia Phillies”:   [“wheeler”, “nola”, “harper”, “schwarber”],
“Texas Rangers”:           [“degrom”, “eovaldi”, “seager”, “carter”],
“Arizona Diamondbacks”:    [“gallen”, “marte”, “carroll”, “moreno”],
“Minnesota Twins”:         [“buxton”, “lewis”, “keaschall”, “lopez”],
“Seattle Mariners”:        [“castillo”, “raleigh”, “rodriguez”, “arozarena”],
“Milwaukee Brewers”:       [“woodruff”, “contreras”, “chourio”, “yelich”],
“Chicago Cubs”:            [“steele”, “bregman”, “crow-armstrong”, “suzuki”],
“San Francisco Giants”:    [“webb”, “devers”, “adames”, “arraez”],
“Boston Red Sox”:          [“anthony”, “duran”, “contreras”, “mayer”],
“New York Mets”:           [“peralta”, “lindor”, “soto”, “bichette”],
“Toronto Blue Jays”:       [“berrios”, “bieber”, “guerrero”, “santander”],
“Cleveland Guardians”:     [“bibee”, “ramirez”, “kwan”, “williams”],
“Tampa Bay Rays”:          [“mcclanahan”, “rasmussen”, “aranda”, “caminero”],
“St. Louis Cardinals”:     [“liberatore”, “wetherholt”, “winn”, “gorman”],
“San Diego Padres”:        [“musgrove”, “tatis”, “machado”, “merrill”],
“Detroit Tigers”:          [“skubal”, “greene”, “torkelson”, “carpenter”],
“Kansas City Royals”:      [“ragans”, “witt”, “pasquantino”, “perez”],
“Pittsburgh Pirates”:      [“skenes”, “chandler”, “jones”, “hayes”],
“Cincinnati Reds”:         [“burns”, “hunter greene”, “de la cruz”, “suarez”],
“Colorado Rockies”:        [“freeland”, “tovar”, “doyle”, “beck”],
“Oakland Athletics”:       [“kurtz”, “wilson”, “rooker”, “soderstrom”],
“Los Angeles Angels”:      [“rodriguez”, “soriano”, “trout”, “manoah”],
“Miami Marlins”:           [“garrett”, “stowers”, “edwards”, “caissie”],
“Washington Nationals”:    [“cavalli”, “wood”, “garcia”, “crews”],
“Chicago White Sox”:       [“smith”, “montgomery”, “teel”, “benintendi”],
}

SEASON_OUT = {
“cole”, “santander”, “lopez”, “jones”, “mccullers”,
}

LIMITED_PLAYERS = {
“trout”, “acuna”, “buxton”, “degrom”, “steele”,
}

SUPERSTARS = {
“ohtani”, “judge”, “freeman”, “acuna”, “tatis”,
“ramirez”, “harper”, “guerrero”, “trout”,
“cole”, “wheeler”, “skubal”, “sale”, “fried”,
“lindor”, “soto”, “betts”, “seager”, “witt”,
“degrom”, “skenes”,
}

SUPERSTAR_PENALTY = 1.2
STAR_PENALTY      = 0.8
LIMITED_PENALTY   = 0.4

FALLBACK_RATINGS = {
“Los Angeles Dodgers”:     {“off”: 5.4, “def”: 3.3},
“New York Yankees”:        {“off”: 5.1, “def”: 3.6},
“Atlanta Braves”:          {“off”: 5.0, “def”: 3.5},
“Philadelphia Phillies”:   {“off”: 4.9, “def”: 3.7},
“New York Mets”:           {“off”: 4.8, “def”: 3.8},
“San Francisco Giants”:    {“off”: 4.8, “def”: 3.8},
“Baltimore Orioles”:       {“off”: 4.7, “def”: 3.8},
“Houston Astros”:          {“off”: 4.7, “def”: 3.9},
“Cleveland Guardians”:     {“off”: 4.5, “def”: 3.8},
“Kansas City Royals”:      {“off”: 4.5, “def”: 4.0},
“Detroit Tigers”:          {“off”: 4.4, “def”: 3.9},
“Seattle Mariners”:        {“off”: 4.4, “def”: 3.8},
“Texas Rangers”:           {“off”: 4.6, “def”: 4.0},
“Arizona Diamondbacks”:    {“off”: 4.6, “def”: 4.0},
“San Diego Padres”:        {“off”: 4.5, “def”: 3.9},
“Chicago Cubs”:            {“off”: 4.5, “def”: 4.0},
“Milwaukee Brewers”:       {“off”: 4.4, “def”: 3.9},
“Boston Red Sox”:          {“off”: 4.5, “def”: 4.1},
“Toronto Blue Jays”:       {“off”: 4.4, “def”: 4.1},
“Pittsburgh Pirates”:      {“off”: 4.2, “def”: 4.0},
“Cincinnati Reds”:         {“off”: 4.3, “def”: 4.2},
“Tampa Bay Rays”:          {“off”: 4.3, “def”: 3.9},
“St. Louis Cardinals”:     {“off”: 4.1, “def”: 4.3},
“Minnesota Twins”:         {“off”: 4.3, “def”: 4.2},
“Oakland Athletics”:       {“off”: 4.2, “def”: 4.3},
“Washington Nationals”:    {“off”: 4.0, “def”: 4.4},
“Colorado Rockies”:        {“off”: 4.4, “def”: 5.2},
“Los Angeles Angels”:      {“off”: 4.1, “def”: 4.5},
“Miami Marlins”:           {“off”: 3.8, “def”: 4.4},
“Chicago White Sox”:       {“off”: 3.7, “def”: 4.9},
}
DEFAULT_RATING = {“off”: 4.3, “def”: 4.3}

TEAM_CN = {
“New York Yankees”:        “\u6d0b\u57fa”,
“Los Angeles Dodgers”:     “\u9053\u5947”,
“Atlanta Braves”:          “\u52c7\u58eb”,
“Houston Astros”:          “\u592a\u7a7a\u4eba”,
“Baltimore Orioles”:       “\u91d1\u9db6”,
“Philadelphia Phillies”:   “\u8cbb\u57ce\u4eba”,
“Texas Rangers”:           “\u904a\u9a0e\u5175”,
“Arizona Diamondbacks”:    “\u97ff\u5c3e\u86c7”,
“Minnesota Twins”:         “\u96d9\u57ce”,
“Seattle Mariners”:        “\u6c34\u624b”,
“Milwaukee Brewers”:       “\u91c0\u9152\u4eba”,
“Chicago Cubs”:            “\u5c0f\u718a”,
“San Francisco Giants”:    “\u5de8\u4eba”,
“Boston Red Sox”:          “\u7d05\u896a”,
“New York Mets”:           “\u5927\u90fd\u6703”,
“Toronto Blue Jays”:       “\u85cd\u9ce5”,
“Cleveland Guardians”:     “\u5b88\u8b77\u8005”,
“Tampa Bay Rays”:          “\u5149\u82b3”,
“St. Louis Cardinals”:     “\u7d05\u96c0”,
“San Diego Padres”:        “\u6559\u58eb”,
“Detroit Tigers”:          “\u8001\u864e”,
“Kansas City Royals”:      “\u7687\u5bb6”,
“Pittsburgh Pirates”:      “\u6d77\u76dc”,
“Cincinnati Reds”:         “\u7d05\u4eba”,
“Colorado Rockies”:        “\u6d1b\u78f4”,
“Oakland Athletics”:       “\u904b\u52d5\u5bb6”,
“Los Angeles Angels”:      “\u5929\u4f7f”,
“Miami Marlins”:           “\u99ac\u6797\u9b5a”,
“Washington Nationals”:    “\u570b\u6c11”,
“Chicago White Sox”:       “\u767d\u896a”,
}

ESPN_SLUG_MAP = {
“nyy”: “New York Yankees”,      “lad”: “Los Angeles Dodgers”,
“atl”: “Atlanta Braves”,        “hou”: “Houston Astros”,
“bal”: “Baltimore Orioles”,     “phi”: “Philadelphia Phillies”,
“tex”: “Texas Rangers”,         “ari”: “Arizona Diamondbacks”,
“min”: “Minnesota Twins”,       “sea”: “Seattle Mariners”,
“mil”: “Milwaukee Brewers”,     “chc”: “Chicago Cubs”,
“sf”:  “San Francisco Giants”,  “bos”: “Boston Red Sox”,
“nym”: “New York Mets”,         “tor”: “Toronto Blue Jays”,
“cle”: “Cleveland Guardians”,   “tb”:  “Tampa Bay Rays”,
“stl”: “St. Louis Cardinals”,   “sd”:  “San Diego Padres”,
“det”: “Detroit Tigers”,        “kc”:  “Kansas City Royals”,
“pit”: “Pittsburgh Pirates”,    “cin”: “Cincinnati Reds”,
“col”: “Colorado Rockies”,      “oak”: “Oakland Athletics”,
“laa”: “Los Angeles Angels”,    “mia”: “Miami Marlins”,
“wsh”: “Washington Nationals”,  “chw”: “Chicago White Sox”,
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
log.warning(“Timeout attempt %d/%d: %s”, attempt, retries, url)
except requests.exceptions.HTTPError as e:
log.error(“HTTP error %s: %s”, e.response.status_code, url)
break
except Exception as e:
log.warning(“Request failed attempt %d/%d: %s”, attempt, retries, e)
return None

def fetch_team_stats():
urls = [
“https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings”,
“https://site.web.api.espn.com/apis/v2/sports/baseball/mlb/standings”,
]
data = None
for url in urls:
data = safe_get(url)
if data:
break
if not data:
log.warning(“ESPN standings API failed, using fallback”)
return {}

```
def get_val(stat):
    for key in ("value", "displayValue", "summary"):
        v = stat.get(key)
        if v is not None:
            try:
                return float(str(v).replace(",", ""))
            except (ValueError, TypeError):
                pass
    return 0.0

ratings = {}
try:
    for group in data.get("children", []):
        entries = group.get("standings", {}).get("entries", [])
        for entry in entries:
            slug = entry.get("team", {}).get("abbreviation", "").lower()
            full = ESPN_SLUG_MAP.get(slug)
            if not full:
                continue
            stats = {}
            for s in entry.get("stats", []):
                name = s.get("name") or s.get("shortDisplayName", "")
                if name:
                    stats[name] = get_val(s)
            wins   = stats.get("wins",   stats.get("W", stats.get("w", 0)))
            losses = stats.get("losses", stats.get("L", stats.get("l", 0)))
            total  = wins + losses
            if total == 0:
                continue
            win_pct = wins / total
            rs = stats.get("pointsFor",     stats.get("RS", stats.get("runsScored",  0)))
            ra = stats.get("pointsAgainst", stats.get("RA", stats.get("runsAllowed", 0)))
            if rs > 10 and ra > 10:
                off  = round(rs / total, 2)
                def_ = round(ra / total, 2)
            else:
                off  = round(3.5 + win_pct * 3.5, 2)
                def_ = round(5.5 - win_pct * 3.0, 2)
            ratings[full] = {
                "off":  off,
                "def":  def_,
                "form": round((win_pct - 0.5) * 0.5, 3),
            }
except Exception as e:
    log.warning("ESPN parse error: %s", e)
    try:
        sample = data["children"][0]["standings"]["entries"][0].get("stats", [])[:3]
        log.warning("ESPN stat sample: %s", json.dumps(sample))
    except Exception:
        pass

log.info("ESPN live ratings loaded: %d teams", len(ratings))
return ratings
```

def get_injury_report():
try:
url  = “https://www.rotowire.com/baseball/injury-report.php”
hdrs = {“User-Agent”: “Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36”}
r    = requests.get(url, headers=hdrs, timeout=15)
r.raise_for_status()
injured      = {}
text         = r.text.lower()
out_keywords = [“ruled out”, “will not play”, “is out”, “has been ruled out”,
“out (”, “60-day il”, “15-day il”, “10-day il”]
skip_kw      = [“questionable”, “probable”, “available”, “good to go”, “day-to-day”]
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
log.info(“RotoWire MLB injury loaded: %d entries”, sum(len(v) for v in injured.values()))
return injured
except Exception as e:
log.warning(“RotoWire failed: %s, using SEASON_OUT fallback”, e)
fallback = {}
for team, players in IMPACT_PLAYERS.items():
out = [p for p in players if p in SEASON_OUT]
if out:
fallback[team] = out
return fallback

def load_history():
if not GITHUB_TOKEN:
return {}
headers = {“Authorization”: “token %s” % GITHUB_TOKEN}
gists   = safe_get(“https://api.github.com/gists”, headers=headers)
if not gists:
return {}
for g in gists:
if g.get(“description”) == “mlb_bot_history”:
raw_url = list(g[“files”].values())[0][“raw_url”]
data    = safe_get(raw_url)
return data if isinstance(data, dict) else {}
return {}

def save_history(history):
if not GITHUB_TOKEN:
return
headers = {
“Authorization”: “token %s” % GITHUB_TOKEN,
“Content-Type”:  “application/json”,
}
content = json.dumps(history, ensure_ascii=False, indent=2)
gists   = safe_get(“https://api.github.com/gists”, headers=headers)
gist_id = None
if gists:
for g in gists:
if g.get(“description”) == “mlb_bot_history”:
gist_id = g[“id”]
break
payload = {
“description”: “mlb_bot_history”,
“public”:      False,
“files”:       {“history.json”: {“content”: content}},
}
try:
if gist_id:
requests.patch(“https://api.github.com/gists/%s” % gist_id,
headers=headers, json=payload, timeout=10)
else:
requests.post(“https://api.github.com/gists”,
headers=headers, json=payload, timeout=10)
log.info(“History saved to Gist”)
except Exception as e:
log.error(“Failed to save history: %s”, e)

def calc_performance(history):
total = win = 0
profit = 0.0
for record in history.values():
if record.get(“result”) not in [“win”, “loss”]:
continue
total += 1
stake = record.get(“kelly_stake”, 10.0)
if record[“result”] == “win”:
win    += 1
profit += stake * (record.get(“price”, 1.9) - 1)
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

```
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
    return ["%s(%s)" % (p.capitalize(), "\u50b7" if s == "out" else "\u9650") for p, s in lst]

return margin, fmt(h_missing), fmt(a_missing)
```

def predict_total(home, away, live_ratings):
h_base = live_ratings.get(home, FALLBACK_RATINGS.get(home, DEFAULT_RATING))
a_base = live_ratings.get(away, FALLBACK_RATINGS.get(away, DEFAULT_RATING))
h_exp  = (h_base[“off”] + a_base[“def”]) / 2
a_exp  = (a_base[“off”] + h_base[“def”]) / 2
return round((h_exp + a_exp) * 0.98, 1)

def get_consensus_line(bookmakers, team_name):
lines = []
for book in bookmakers:
for market in book.get(“markets”, []):
if market.get(“key”) != “spreads”:
continue
for outcome in market.get(“outcomes”, []):
if normalize_team(outcome.get(“name”, “”)) == team_name:
pt = outcome.get(“point”)
if pt is not None:
lines.append(pt)
return (sum(lines) / len(lines)) if lines else None

def get_consensus_total(bookmakers):
totals = []
for book in bookmakers:
for market in book.get(“markets”, []):
if market.get(“key”) != “totals”:
continue
for outcome in market.get(“outcomes”, []):
if outcome.get(“name”, “”).lower() == “over”:
pt = outcome.get(“point”)
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
“apiKey”:     ODDS_API_KEY,
“regions”:    “us”,
“markets”:    “spreads,totals”,
“oddsFormat”: “decimal”,
}
data = safe_get(
“https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/”,
params=params,
)
if data is None:
log.error(“Odds API failed”)
return []
log.info(“Odds loaded: %d games”, len(data))
return data

def chunked_send(content, webhook):
lines = content.split(”\n”)
chunk, chunks = “”, []
for line in lines:
if len(chunk) + len(line) + 1 > DISCORD_CHAR_LIMIT:
chunks.append(chunk)
chunk = line + “\n”
else:
chunk += line + “\n”
if chunk:
chunks.append(chunk)
for i, part in enumerate(chunks, 1):
label = “(%d/%d)\n%s” % (i, len(chunks), part) if len(chunks) > 1 else part
try:
r = requests.post(webhook, json={“content”: label}, timeout=10)
r.raise_for_status()
except Exception as e:
log.error(“Discord send failed chunk %d: %s”, i, e)

def run():
if not all([ODDS_API_KEY, WEBHOOK]):
log.error(“Missing env vars”)
return

```
now_utc = datetime.utcnow()
now_tw  = now_utc + timedelta(hours=8)
today_s = now_tw.strftime("%Y-%m-%d")

is_official_run = (now_utc.hour == 22)
log.info("Official run: %s (UTC hour: %d)", is_official_run, now_utc.hour)

live_ratings = fetch_team_stats()
data_source  = "ESPN" if live_ratings else "fallback"
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
            ou_note = "OU: model %.1f vs market %.1f -> Over" % (model_total, consensus_total)
        elif diff < -0.5:
            ou_note = "OU: model %.1f vs market %.1f -> Under" % (model_total, consensus_total)
        else:
            ou_note = "OU: model %.1f vs market %.1f (neutral)" % (model_total, consensus_total)

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
                    tier = "\U0001f48e TOP"
                elif edge > 0.09:
                    tier = "\U0001f525 STRONG"
                else:
                    tier = "\u2b50 SOLID"

                bet_cn        = TEAM_CN.get(name, name)
                away_cn       = TEAM_CN.get(away, away)
                home_cn       = TEAM_CN.get(home, home)
                missing_str   = "\u72c0\u6cc1: " + ", ".join(missing) if missing else "\u9663\u5bb9\u5b8c\u6574"
                consensus_str = "\u8b93\u5206\u5171\u8b58: %+.1f" % consensus

                msg = (
                    "**[%s] %s @ %s** (%s)\n"
                    "\u6295\u6ce8: `%s %+.1f` @ **%.2f** (%s)\n"
                    "> %s | %s\n"
                    "> \u52dd\u7387: %.1f%% | Edge: %+.1f%% | Kelly: $%.1f\n"
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
    "\n\U0001f4ca **Record** (\U0001f48e TOP only)\n"
    "Total: %d | Settled: %d\n"
    "Win rate: %.1f%% | P&L: %+.1f\n"
) % (len(history), total_rec, win_rate, profit)

total_picks = sum(len(v) for v in daily_picks.values())
avg_edge    = (
    sum(p["edge"] for d in daily_picks.values() for p in d.values()) / total_picks
    if total_picks else 0
)

output = "\u26be MLB V101.0 | %s | %s | picks: %d | avg edge: %+.1f%%\n" % (
    now_tw.strftime("%m/%d %H:%M"), data_source, total_picks, avg_edge * 100
)

if is_official_run:
    output += "\U0001f4cc official run\n"
else:
    output += "\U0001f527 test run (not saving)\n"

if not daily_picks:
    output += "\nNo picks today.\n"
else:
    for date in sorted(daily_picks):
        label = "\U0001f4c5 Today" if date == today_s else ("\u23ed Preview %s" % date)
        output += "\n%s\n" % label
        for p in sorted(daily_picks[date].values(), key=lambda x: x["edge"], reverse=True):
            output += p["msg"]
        output += "-" * 30 + "\n"

output += perf_msg

if is_official_run:
    save_history(history)
    log.info("History saved (official run)")
else:
    log.info("History NOT saved (test run)")

log.info("Sending to Discord, length: %d", len(output))
chunked_send(output, WEBHOOK)
log.info("Done")
```

if **name** == “**main**”:
run()