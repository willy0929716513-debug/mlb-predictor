import requests, os, random, logging, json, math
from datetime import datetime, timedelta

logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s [%(levelname)s] %(name)s: %(message)s”,
)
log = logging.getLogger(“MLB_V105”)

ODDS_API_KEY = os.getenv(“ODDS_API_KEY”, “”)
WEBHOOK      = os.getenv(“DISCORD_WEBHOOK”, “”)
GH_TOKEN     = os.getenv(“GH_TOKEN”, “”)

EDGE_MIN  = 0.09
MOD_W     = 0.25
MKT_W     = 0.75
TOT_MOD   = 0.35
TOT_MKT   = 0.65
STD       = 1.6
HA        = 0.10
MIN_P     = 1.30
MAX_P     = 2.55
LIMIT     = 1900
BANK      = 1000.0
KELLY     = 0.15
KELLY_MAX = 25.0
HIST_TTL  = 90

ROSTER = {
“New York Yankees”:      [“fried”,“judge”,“goldschmidt”,“cabrera”,“volpe”,“rice”,“stanton”],
“Los Angeles Dodgers”:   [“yamamoto”,“ohtani”,“freeman”,“betts”,“sasaki”,“buehler”,“pages”],
“Atlanta Braves”:        [“sale”,“acuna”,“olson”,“riley”,“kim”,“sorokin”,“harris”],
“Houston Astros”:        [“brown”,“pena”,“abreu”,“paredes”,“bregman”,“diaz”],
“Baltimore Orioles”:     [“rogers”,“henderson”,“rutschman”,“alonso”,“holliday”,“westburg”],
“Philadelphia Phillies”: [“sanchez”,“wheeler”,“nola”,“harper”,“schwarber”,“stott”,“castellanos”],
“Texas Rangers”:         [“eovaldi”,“degrom”,“seager”,“carter”,“garcia”,“taveras”],
“Arizona Diamondbacks”:  [“gallen”,“kelly”,“marte”,“carroll”,“moreno”,“lourdes”],
“Minnesota Twins”:       [“ryan”,“buxton”,“lewis”,“miranda”,“wallner”],
“Seattle Mariners”:      [“gilbert”,“woo”,“kirby”,“castillo”,“raleigh”,“rodriguez”,“arozarena”],
“Milwaukee Brewers”:     [“misiorowski”,“contreras”,“chourio”,“yelich”,“adames”,“wiemer”],
“Chicago Cubs”:          [“boyd”,“steele”,“imanaga”,“bregman”,“suzuki”,“busch”,“taillon”],
“San Francisco Giants”:  [“webb”,“devers”,“adames”,“arraez”,“bailey”,“conforto”],
“Boston Red Sox”:        [“crochet”,“duran”,“wcontreras”,“mayer”,“casas”,“abreu”],
“New York Mets”:         [“peralta”,“holmes”,“lindor”,“soto”,“bichette”,“vientos”,“nimmo”],
“Toronto Blue Jays”:     [“gausman”,“berrios”,“bieber”,“guerrero”,“santander”,“varsho”],
“Cleveland Guardians”:   [“bibee”,“williams_g”,“ramirez”,“kwan”,“naylor”,“freeman”],
“Tampa Bay Rays”:        [“rasmussen”,“aranda”,“caminero”,“palacios”,“brujan”,“liberatore”],
“St. Louis Cardinals”:   [“liberatore”,“wetherholt”,“winn”,“gorman”,“donovan”,“walker”],
“San Diego Padres”:      [“pivetta”,“musgrove”,“tatis”,“machado”,“merrill”,“king”],
“Detroit Tigers”:        [“skubal”,“verlander”,“torkelson”,“carpenter”,“jung”,“greene”],
“Kansas City Royals”:    [“ragans”,“witt”,“pasquantino”,“perez”,“melendez”,“massey”],
“Pittsburgh Pirates”:    [“skenes”,“chandler”,“hayes”,“triolo”,“davis”,“o’neil”],
“Cincinnati Reds”:       [“abbott”,“burns”,“hgreene”,“delacruz”,“suarez”,“candelario”],
“Colorado Rockies”:      [“freeland”,“tovar”,“doyle”,“beck”,“grichuk”],
“Oakland Athletics”:     [“severino”,“kurtz”,“jwilson”,“rooker”,“soderstrom”,“langeliers”],
“Los Angeles Angels”:    [“soriano”,“kikuchi”,“trout”,“neto”,“schanuel”,“rendon”],
“Miami Marlins”:         [“alcantara”,“paddack”,“stowers”,“edwards”,“caissie”,“leblanc”],
“Washington Nationals”:  [“cavalli”,“wood”,“garcia”,“crews”,“young”],
“Chicago White Sox”:     [“smith_s”,“martin”,“montgomery”,“teel”,“benintendi”,“anderson”],
}

OUT = frozenset({
“cole”,“hgreene”,“degrom”,“acuna”,“wheeler”,
“blanco”,“wesneski”,“holliday”,“westburg”,“casas”,“houck”,“teel”,
“jobe”,“olson_r”,“hader”,“massey”,“marsh”,“manoah”,“rodriguez_g”,“rendon”,
“festa”,“adams_t”,“lopez_p”,“kolek”,“hoglund”,
})

LTD = frozenset({
“trout”,“buxton”,“steele”,“skubal”,“riley”,“berrios”,“eflin”,
“crawford”,“sandoval_p”,“gipson”,“kjerstad”,
})

SS = frozenset({
“ohtani”,“judge”,“freeman”,“acuna”,“tatis”,“ramirez”,“harper”,
“guerrero”,“trout”,“cole”,“wheeler”,“skubal”,“sale”,“fried”,
“lindor”,“soto”,“betts”,“seager”,“witt”,“degrom”,“skenes”,
“verlander”,“rutschman”,“henderson”,“crochet”,“castillo”,“sasaki”,
“yamamoto”,“peralta”,“ragans”,“mcclanahan”,“gilbert”,“bibee”,
“hgreene”,“sanchez”,“scherzer”,“rasmussen”,“pivetta”,“rodriguez_a”,
})

SS_PEN      = 1.2
ST_PEN      = 0.8
LT_PEN_SS   = 0.8
LT_PEN_NORM = 0.4

BASE = {
“Los Angeles Dodgers”:   {“off”: 5.04, “def”: 4.16},
“New York Yankees”:      {“off”: 4.73, “def”: 4.22},
“New York Mets”:         {“off”: 4.74, “def”: 4.25},
“Seattle Mariners”:      {“off”: 4.51, “def”: 4.08},
“Atlanta Braves”:        {“off”: 4.70, “def”: 4.27},
“Toronto Blue Jays”:     {“off”: 4.64, “def”: 4.36},
“Philadelphia Phillies”: {“off”: 4.63, “def”: 4.40},
“Texas Rangers”:         {“off”: 4.59, “def”: 4.39},
“Boston Red Sox”:        {“off”: 4.49, “def”: 4.30},
“Milwaukee Brewers”:     {“off”: 4.56, “def”: 4.36},
“Detroit Tigers”:        {“off”: 4.42, “def”: 4.25},
“Baltimore Orioles”:     {“off”: 4.71, “def”: 4.60},
“Chicago Cubs”:          {“off”: 4.60, “def”: 4.44},
“Houston Astros”:        {“off”: 4.63, “def”: 4.55},
“Pittsburgh Pirates”:    {“off”: 4.42, “def”: 4.35},
“Tampa Bay Rays”:        {“off”: 4.36, “def”: 4.35},
“Kansas City Royals”:    {“off”: 4.53, “def”: 4.57},
“Arizona Diamondbacks”:  {“off”: 4.55, “def”: 4.57},
“San Francisco Giants”:  {“off”: 4.31, “def”: 4.35},
“Minnesota Twins”:       {“off”: 4.45, “def”: 4.55},
“Cincinnati Reds”:       {“off”: 4.47, “def”: 4.68},
“Miami Marlins”:         {“off”: 4.30, “def”: 4.52},
“San Diego Padres”:      {“off”: 4.39, “def”: 4.56},
“Oakland Athletics”:     {“off”: 4.61, “def”: 4.81},
“Cleveland Guardians”:   {“off”: 4.28, “def”: 4.60},
“St. Louis Cardinals”:   {“off”: 4.31, “def”: 4.63},
“Los Angeles Angels”:    {“off”: 4.33, “def”: 4.74},
“Washington Nationals”:  {“off”: 4.29, “def”: 4.87},
“Chicago White Sox”:     {“off”: 4.23, “def”: 5.01},
“Colorado Rockies”:      {“off”: 4.48, “def”: 5.50},
}
DEF_RATING = {“off”: 4.40, “def”: 4.50}

LEAGUE_AVG_ERA = 4.20

PITCHER_ERA = {
“skenes”:      1.96, “skubal”:      3.08, “yamamoto”:    2.49,
“crochet”:     2.59, “sanchez”:     2.50, “ohtani”:      3.00,
“sale”:        2.58, “mcclanahan”:  3.10, “fried”:       3.10,
“rasmussen”:   2.76, “gilbert”:     3.44, “webb”:        3.20,
“burnes”:      3.20, “ragans”:      3.40, “castillo”:    3.30,
“peralta”:     3.40, “pivetta”:     2.87, “woo”:         3.50,
“kirby”:       3.50, “bibee”:       4.24, “williams_g”:  3.80,
“eovaldi”:     3.80, “gausman”:     3.59, “ryan”:        3.42,
“brown”:       2.43, “rogers_t”:    2.50, “misiorowski”: 4.36,
“boyd”:        3.21, “liberatore”:  4.21, “abbott”:      3.42,
“cavalli”:     4.25, “gallen”:      4.00, “verlander”:   3.80,
“severino”:    4.54, “burns”:       3.50, “freeland”:    4.75,
“alcantara”:   5.36, “smith_s”:     3.81, “imanaga”:     3.55,
“taillon”:     4.40, “steele”:      3.75, “soriano”:     3.93,
“kikuchi”:     4.20, “degrom”:      3.50, “chandler”:    4.00,
“senga”:       3.60, “holmes”:      4.00, “buehler”:     4.20,
“sasaki”:      2.90, “bello”:       4.10, “berrios”:     3.80,
“bieber”:      3.40, “cease”:       3.80, “flaherty”:    3.85,
“nola”:        3.70, “musgrove”:    3.50, “king_m”:      3.90,
“vsquez”:      4.40, “paddack”:     4.30, “wood”:        4.20,
“javier”:      4.20, “montero”:     4.50, “horton”:      4.10,
“martin_c”:    4.60, “keller”:      4.00, “pepiot”:      4.30,
“springs”:     4.30, “winn”:        4.30, “wetherholt”:  4.50,
“mikolas”:     4.20, “ryan_j”:      3.42, “varland”:     4.60,
“gray_j”:      3.95, “bradish”:     3.65, “hall_d”:      4.30,
“sears”:       4.50, “cortes”:      4.30, “schlittler”:  4.70,
“houser”:      4.80, “flexen”:      4.90, “blackburn”:   4.50,
“kolek”:       4.50, “lynch”:       4.70, “cox”:         4.80,
“feltner”:     5.20, “hudson”:      5.00, “mize”:        4.30,
“pfaadt”:      4.10, “marquez”:     4.90, “williamson”:  4.60,
“junk”:        5.10, “fedde”:       4.60, “pallante”:    4.60,
“poulin”:      5.30, “painter”:     4.80, “small”:       4.70,
“wesneski”:    4.40, “cobb”:        4.50,
}

SLUG = {
“nyy”: “New York Yankees”,    “lad”: “Los Angeles Dodgers”,
“atl”: “Atlanta Braves”,      “hou”: “Houston Astros”,
“bal”: “Baltimore Orioles”,   “phi”: “Philadelphia Phillies”,
“tex”: “Texas Rangers”,       “ari”: “Arizona Diamondbacks”,
“min”: “Minnesota Twins”,     “sea”: “Seattle Mariners”,
“mil”: “Milwaukee Brewers”,   “chc”: “Chicago Cubs”,
“sf”:  “San Francisco Giants”,“bos”: “Boston Red Sox”,
“nym”: “New York Mets”,       “tor”: “Toronto Blue Jays”,
“cle”: “Cleveland Guardians”, “tb”:  “Tampa Bay Rays”,
“stl”: “St. Louis Cardinals”, “sd”:  “San Diego Padres”,
“det”: “Detroit Tigers”,      “kc”:  “Kansas City Royals”,
“pit”: “Pittsburgh Pirates”,  “cin”: “Cincinnati Reds”,
“col”: “Colorado Rockies”,    “oak”: “Oakland Athletics”,
“laa”: “Los Angeles Angels”,  “mia”: “Miami Marlins”,
“wsh”: “Washington Nationals”,“chw”: “Chicago White Sox”,
}
SHORT = {v: k.upper() for k, v in SLUG.items()}

CN = {
“New York Yankees”:      “\u6d0b\u57fa”,
“Los Angeles Dodgers”:   “\u9053\u5947”,
“Atlanta Braves”:        “\u52c7\u58eb”,
“Houston Astros”:        “\u592a\u7a7a\u4eba”,
“Baltimore Orioles”:     “\u91d1\u9db6”,
“Philadelphia Phillies”: “\u8cbb\u57ce\u4eba”,
“Texas Rangers”:         “\u904a\u9a0e\u5175”,
“Arizona Diamondbacks”:  “\u97ff\u5c3e\u86c7”,
“Minnesota Twins”:       “\u96d9\u57ce”,
“Seattle Mariners”:      “\u6c34\u624b”,
“Milwaukee Brewers”:     “\u91c0\u9152\u4eba”,
“Chicago Cubs”:          “\u5c0f\u718a”,
“San Francisco Giants”:  “\u5de8\u4eba”,
“Boston Red Sox”:        “\u7d05\u896a”,
“New York Mets”:         “\u5927\u90fd\u6703”,
“Toronto Blue Jays”:     “\u85cd\u9ce5”,
“Cleveland Guardians”:   “\u5b88\u8b77\u8005”,
“Tampa Bay Rays”:        “\u5149\u82b3”,
“St. Louis Cardinals”:   “\u7d05\u96c0”,
“San Diego Padres”:      “\u6559\u58eb”,
“Detroit Tigers”:        “\u8001\u864e”,
“Kansas City Royals”:    “\u7687\u5bb6”,
“Pittsburgh Pirates”:    “\u6d77\u76dc”,
“Cincinnati Reds”:       “\u7d05\u4eba”,
“Colorado Rockies”:      “\u6d1b\u78f4”,
“Oakland Athletics”:     “\u904b\u52d5\u5bb6”,
“Los Angeles Angels”:    “\u5929\u4f7f”,
“Miami Marlins”:         “\u99ac\u6797\u9b5a”,
“Washington Nationals”:  “\u570b\u6c11”,
“Chicago White Sox”:     “\u767d\u896a”,
}

def norm(name):
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
for i in range(1, retries + 1):
try:
r = requests.get(url, headers=headers, params=params, timeout=timeout)
r.raise_for_status()
return r.json()
except requests.exceptions.Timeout:
log.warning(“Timeout %d/%d %s”, i, retries, url)
except requests.exceptions.HTTPError as e:
log.error(“HTTP %s: %s”, e.response.status_code, url)
break
except Exception as e:
log.warning(“Err %d/%d: %s”, i, retries, e)
return None

def _extract_pitcher_last(team_obj):
for prob in team_obj.get(“probables”, []):
athlete = prob.get(“athlete”, prob)
name = athlete.get(“displayName”) or athlete.get(“fullName”, “”)
if name:
return name.strip().split()[-1].lower()
for ath in team_obj.get(“athletes”, []):
inner = ath.get(“athlete”, ath)
pos   = (inner.get(“position”, {}) or {}).get(“abbreviation”, “”)
role  = ath.get(“role”, “”)
if pos.upper() in (“SP”, “P”) or “start” in role.lower():
name = inner.get(“displayName”) or inner.get(“fullName”, “”)
if name:
return name.strip().split()[-1].lower()
for s in team_obj.get(“starters”, []):
name = s.get(“displayName”) or s.get(“fullName”, “”)
if name:
return name.strip().split()[-1].lower()
return “”

def fetch_probable_pitchers():
today = datetime.utcnow().strftime(”%Y%m%d”)
urls = [
“https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard”,
“https://site.web.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard”,
]
data = None
for url in urls:
data = safe_get(url, params={“dates”: today})
if data:
break
if not data:
log.warning(“ESPN scoreboard failed”)
return {}
team_pitcher = {}
try:
for event in data.get(“events”, []):
for comp in event.get(“competitions”, []):
for team in comp.get(“competitors”, []):
team_name = norm(team.get(“team”, {}).get(“displayName”, “”))
if not team_name:
continue
last = _extract_pitcher_last(team)
if last:
team_pitcher[team_name] = last
log.info(“SP: %s -> %s”, team_name, last)
except Exception as e:
log.warning(“Pitcher parse error: %s”, e)
log.info(“Probable pitchers: %d teams”, len(team_pitcher))
return team_pitcher

def fetch_stats():
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
log.warning(“ESPN standings failed”)
return {}

```
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
            base = BASE.get(full, DEF_RATING)
            if t < 5:
                ratings[full] = {"off": base["off"], "def": base["def"], "form": 0.0}
                continue
            rs = st.get("pointsFor",     st.get("RS", st.get("runsScored",  0)))
            ra = st.get("pointsAgainst", st.get("RA", st.get("runsAllowed", 0)))
            wp = w / t
            if rs > 10 and ra > 10:
                off = round(min(rs / t, 5.8), 2)
                df  = round(max(ra / t, 3.0), 2)
            else:
                off = round(min(base["off"] + (wp - 0.5) * 0.5, 5.8), 2)
                df  = round(max(base["def"] - (wp - 0.5) * 0.5, 3.0), 2)
            alpha = min(t / 30, 0.5)
            ratings[full] = {
                "off":  round(off * alpha + base["off"] * (1 - alpha), 2),
                "def":  round(df  * alpha + base["def"] * (1 - alpha), 2),
                "form": round((wp - 0.5) * 0.2, 3),
            }
except Exception as e:
    log.warning("ESPN standings parse error: %s", e)
log.info("ESPN ratings: %d teams", len(ratings))
return ratings
```

def get_injuries():
inj = {}
try:
r = requests.get(
“https://www.rotowire.com/baseball/injury-report.php”,
headers={“User-Agent”: “Mozilla/5.0”},
timeout=15,
)
r.raise_for_status()
text = r.text.lower()
out_kw  = [“ruled out”,“will not play”,“is out”,
“60-day il”,“15-day il”,“10-day il”,“tommy john”]
skip_kw = [“questionable”,“probable”,“available”]
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
log.warning(“RotoWire failed: %s”, e)
for team, players in ROSTER.items():
existing = set(inj.get(team, []))
for p in players:
if p in OUT and p not in existing:
inj.setdefault(team, []).append(p)
existing.add(p)
log.info(“Injuries: %d total”, sum(len(v) for v in inj.values()))
return inj

def _purge_old(hist):
cutoff = (datetime.utcnow() - timedelta(days=HIST_TTL)).strftime(”%Y-%m-%d”)
return {k: v for k, v in hist.items() if v.get(“date”, “9999”) >= cutoff}

def load_hist():
if not GH_TOKEN:
return {}
h = {“Authorization”: “token “ + GH_TOKEN}
gists = safe_get(“https://api.github.com/gists”, headers=h)
if not gists:
return {}
for g in gists:
if g.get(“description”) == “mlb_bot_history”:
raw_url = list(g[“files”].values())[0][“raw_url”]
d = safe_get(raw_url)
if isinstance(d, dict):
return _purge_old(d)
return {}

def save_hist(hist, retries=3):
if not GH_TOKEN:
return
hist = _purge_old(hist)
h    = {“Authorization”: “token “ + GH_TOKEN, “Content-Type”: “application/json”}
body = json.dumps(hist, ensure_ascii=False, indent=2)
gists = safe_get(“https://api.github.com/gists”, headers=h)
gid   = next(
(g[“id”] for g in (gists or []) if g.get(“description”) == “mlb_bot_history”),
None,
)
pl = {“description”: “mlb_bot_history”, “public”: False,
“files”: {“history.json”: {“content”: body}}}
for attempt in range(1, retries + 1):
try:
if gid:
requests.patch(“https://api.github.com/gists/” + gid,
headers=h, json=pl, timeout=10).raise_for_status()
else:
requests.post(“https://api.github.com/gists”,
headers=h, json=pl, timeout=10).raise_for_status()
log.info(“History saved (attempt %d)”, attempt)
return
except Exception as e:
log.warning(“Save failed %d/%d: %s”, attempt, retries, e)
log.error(“History save all failed”)

def calc_perf(hist):
total = win = 0
profit = 0.0
for r in hist.values():
if r.get(“result”) not in (“win”, “loss”):
continue
total += 1
stake = r.get(“kelly_stake”, 10.0)
if r[“result”] == “win”:
win    += 1
profit += stake * (r.get(“price”, 1.9) - 1)
else:
profit -= stake
return total, win, (win / total * 100 if total else 0.0), profit

def kelly(prob, price):
b = price - 1
if b <= 0:
return 0.0
k = max(0.0, (b * prob - (1 - prob)) / b) * KELLY
return min(round(BANK * k, 1), KELLY_MAX)

def win_prob_from_margin(margin):
return round(0.5 + 0.5 * math.erf(margin / (STD * math.sqrt(2))), 4)

def best_price(books, team):
prices = []
for b in books:
for m in b.get(“markets”, []):
if m.get(“key”) != “h2h”:
continue
for o in m.get(“outcomes”, []):
if norm(o.get(“name”, “”)) == team and o.get(“price”):
prices.append((o[“price”], b.get(“title”, “?”)))
if not prices:
return None, None
return max(prices, key=lambda x: x[0])

def consensus_ml(books, team):
prices = []
for b in books:
for m in b.get(“markets”, []):
if m.get(“key”) != “h2h”:
continue
for o in m.get(“outcomes”, []):
if norm(o.get(“name”, “”)) == team and o.get(“price”):
prices.append(o[“price”])
return round(sum(prices) / len(prices), 3) if prices else None

def consensus_total(books):
pts = []
for b in books:
for m in b.get(“markets”, []):
if m.get(“key”) != “totals”:
continue
for o in m.get(“outcomes”, []):
if o.get(“name”, “”).lower() == “over” and o.get(“point”) is not None:
pts.append(o[“point”])
return sum(pts) / len(pts) if pts else None

def pitcher_era_adj(pitcher_last):
if not pitcher_last:
return 0.0
era = PITCHER_ERA.get(pitcher_last.lower())
if era is None:
log.debug(“Unknown pitcher: %s -> conservative penalty”, pitcher_last)
era = LEAGUE_AVG_ERA + 0.50
return round((era - LEAGUE_AVG_ERA) / 9 * 6, 3)

def total_confidence_factor(pure_model, market):
if market is None:
return 1.0
gap = abs(pure_model - market)
if gap <= 1.5:   return 1.00
elif gap <= 2.5: return 0.85
elif gap <= 3.5: return 0.65
elif gap <= 5.0: return 0.45
else:            return 0.30

def _get_missing(team, inj):
il = {p.lower() for p in inj.get(team, [])}
result = []
for p in ROSTER.get(team, []):
if p in OUT or p in il:
result.append((p, “out”, team))
elif p in LTD:
result.append((p, “ltd”, team))
return result

def _apply_injury_penalty(rating, missing):
r = {“off”: rating[“off”], “def”: rating[“def”]}
for p, s, t in missing:
if s == “out”:
pen = SS_PEN if p in SS else ST_PEN
else:
pen = LT_PEN_SS if p in SS else LT_PEN_NORM
r[“off”] -= pen * 0.6
r[“def”] += pen * 0.4
return r

def pitcher_replacement_bonus(team, pitchers, missing):
sp = pitchers.get(team, “”)
if not sp:
return 0.0
sp_era = PITCHER_ERA.get(sp.lower(), LEAGUE_AVG_ERA + 0.5)
if sp_era < LEAGUE_AVG_ERA:
bonus = (LEAGUE_AVG_ERA - sp_era) / 9 * 3
return round(min(bonus, 0.40), 3)
return 0.0

def predict_margin(home, away, inj, ratings, pitchers):
hb  = ratings.get(home, BASE.get(home, DEF_RATING))
ab  = ratings.get(away, BASE.get(away, DEF_RATING))
hm  = _get_missing(home, inj)
am  = *get_missing(away, inj)
hs  = *apply_injury_penalty(hb, hm)
as* = *apply_injury_penalty(ab, am)
h_sp        = pitchers.get(home, “”)
a_sp        = pitchers.get(away, “”)
h_pitch_adj = pitcher_era_adj(h_sp)
a_pitch_adj = pitcher_era_adj(a_sp)
h_bonus     = pitcher_replacement_bonus(home, pitchers, hm)
a_bonus     = pitcher_replacement_bonus(away, pitchers, am)
h_exp  = (hs[“off”] + as*[“def”]) / 2 + hb.get(“form”, 0.0) - a_pitch_adj + h_bonus
a_exp  = (as*[“off”] + hs[“def”]) / 2 + ab.get(“form”, 0.0) - h_pitch_adj + a_bonus
margin = (h_exp - a_exp) + HA

```
def fmt(lst):
    return [
        "%s %s(%s)" % (CN.get(t, t[:3]), p.upper(), "OUT" if s == "out" else "LTD")
        for p, s, t in lst
    ]
return margin, fmt(hm), fmt(am), h_sp, a_sp
```

def predict_total(home, away, ratings, pitchers, market_total=None):
h     = ratings.get(home, BASE.get(home, DEF_RATING))
a     = ratings.get(away, BASE.get(away, DEF_RATING))
h_adj = pitcher_era_adj(pitchers.get(home, “”))
a_adj = pitcher_era_adj(pitchers.get(away, “”))
h_exp = h[“off”] - a_adj
a_exp = a[“off”] - h_adj
pure  = round(h_exp + a_exp, 1)
if market_total:
blended = round(pure * TOT_MOD + market_total * TOT_MKT, 1)
return blended, pure
return pure, pure

def fetch_odds():
data = safe_get(
“https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/”,
params={“apiKey”: ODDS_API_KEY, “regions”: “us”,
“markets”: “h2h,totals”, “oddsFormat”: “decimal”},
)
if not data:
log.error(“Odds API failed”)
return []
log.info(“Odds: %d games”, len(data))
return data

def send(content):
lines = content.split(”\n”)
chunks = []
buf = []
size = 0
for line in lines:
addition = len(line) + 1
if size + addition > LIMIT and buf:
chunks.append(”\n”.join(buf))
buf = [line]
size = addition
else:
buf.append(line)
size += addition
if buf:
chunks.append(”\n”.join(buf))
total = len(chunks)
for i, part in enumerate(chunks, 1):
label = “(%d/%d)\n%s” % (i, total, part) if total > 1 else part
try:
r = requests.post(WEBHOOK, json={“content”: label}, timeout=10)
r.raise_for_status()
except Exception as e:
log.error(“Discord chunk %d failed: %s”, i, e)

def run():
if not all([ODDS_API_KEY, WEBHOOK]):
log.error(“Missing ODDS_API_KEY or DISCORD_WEBHOOK”)
return

```
now_utc  = datetime.utcnow()
now_tw   = now_utc + timedelta(hours=8)
today    = now_tw.strftime("%Y-%m-%d")
official = (0 <= now_tw.hour < 14)
log.info("Official: %s (TW %02d:%02d)", official, now_tw.hour, now_tw.minute)

ratings  = fetch_stats()
src      = "ESPN" if ratings else "BASE(FanGraphs\u6295\u5f71)"
inj      = get_injuries()
pitchers = fetch_probable_pitchers()
games    = fetch_odds()
hist     = load_hist()

if not ratings:
    ratings = {k: {"off": v["off"], "def": v["def"], "form": 0.0}
               for k, v in BASE.items()}
if not games:
    log.error("No games data, aborting")
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
    home  = norm(g.get("home_team", ""))
    away  = norm(g.get("away_team", ""))
    if not home or not away:
        continue
    gid   = "%s@%s_%s" % (away, home, gdate)
    books = g.get("bookmakers", [])
    picks.setdefault(gdate, {})

    margin, hm, am, h_sp, a_sp = predict_margin(home, away, inj, ratings, pitchers)
    ct                = consensus_total(books)
    blended_mt, pure_mt = predict_total(home, away, ratings, pitchers, ct)
    conf_factor       = total_confidence_factor(pure_mt, ct)

    ou = ""
    if ct:
        diff = pure_mt - ct
        if   diff >  1.5:
            ou = "\u5927\u5206\u504f\u5411 OVER  (\u7d14\u6a21\u578b%.1f / \u5e02\u5834%.1f)" % (pure_mt, ct)
        elif diff < -1.5:
            ou = "\u5c0f\u5206\u504f\u5411 UNDER (\u7d14\u6a21\u578b%.1f / \u5e02\u5834%.1f)" % (pure_mt, ct)
        else:
            ou = "\u5927\u5c0f\u5206\u4e2d\u6027     (\u7d14\u6a21\u578b%.1f / \u5e02\u5834%.1f)" % (pure_mt, ct)

    def sp_str(sp_key):
        if not sp_key:
            return "TBD"
        era = PITCHER_ERA.get(sp_key.lower())
        if era:
            return "%s(ERA%.2f)" % (sp_key.upper(), era)
        return sp_key.upper()

    h_sp_str = sp_str(h_sp)
    a_sp_str = sp_str(a_sp)

    h_best_price, h_best_book = best_price(books, home)
    a_best_price, a_best_book = best_price(books, away)

    for (team, bp, bbook) in [
        (home, h_best_price, h_best_book),
        (away, a_best_price, a_best_book),
    ]:
        if not bp or not (MIN_P < bp <= MAX_P):
            continue

        is_home      = (team == home)
        raw_margin   = margin if is_home else -margin
        model_prob   = win_prob_from_margin(raw_margin)
        raw_mkt_prob = 1 / bp

        con_h = consensus_ml(books, home)
        con_a = consensus_ml(books, away)
        if con_h and con_a:
            inv_sum     = 1 / con_h + 1 / con_a
            no_vig_prob = round((1 / (con_h if is_home else con_a)) / inv_sum, 4)
        else:
            no_vig_prob = raw_mkt_prob

        edge_raw = model_prob - raw_mkt_prob
        edge     = edge_raw * conf_factor
        if edge < EDGE_MIN:
            continue

        bet_prob  = min(max(model_prob * MOD_W + no_vig_prob * MKT_W, 0.01), 0.99)
        con_price = con_h if is_home else con_a
        miss      = (hm if is_home else am) + (am if is_home else hm)
        stake     = kelly(bet_prob, bp)

        if   edge > 0.12: tier = "\U0001f48e \u9802\u7d1a"
        elif edge > 0.09: tier = "\U0001f525 \u5f37\u529b"
        else:             tier = "\u2b50 \u7a69\u5b9a"

        acn   = CN.get(away, SHORT.get(away, away))
        hcn   = CN.get(home, SHORT.get(home, home))
        bcn   = CN.get(team, SHORT.get(team, team))
        ms    = "\u50b7\u5175: " + ", ".join(miss) if miss else "\u9663\u5bb9\u6b63\u5e38"
        ou_ln = ("\n> %s" % ou) if ou else ""
        conf_note = (" \u26a0\ufe0f \u5927\u5c0f\u5206\u6298\u6263%.0f%%" % (conf_factor * 100)) if conf_factor < 1.0 else ""

        msg = "\n".join([
            "\u2014" * 15,
            "**%s  %s @ %s**" % (tier, acn, hcn),
            "\U0001f550 %s" % ctw.strftime("%m/%d %H:%M"),
            "\u26be \u5148\u767c: %s \u2014 %s" % (a_sp_str, h_sp_str),
            "\U0001f4b0 \u4eca\u65e5\u63a8\u85a6: `%s \u72ec\u8d0f` @ **%.2f** (%s)" % (bcn, bp, bbook),
            "> \u5171\u8b58\u8ce0\u7387: %.2f | %s" % (con_price or bp, ms),
            "> \u52dd\u7387: **%.1f%%** | Edge: **%+.1f%%**%s | Kelly: $%.1f%s" % (
                model_prob * 100, edge * 100, conf_note, stake, ou_ln),
        ]) + "\n"

        key = "%s_%s" % (gid, team)
        ex  = picks[gdate].get(key)
        if ex is None or edge > ex["edge"]:
            picks[gdate][key] = {
                "edge": edge, "prob": bet_prob, "price": bp,
                "kelly_stake": stake, "msg": msg,
            }

        if official and gdate == today:
            eh = hist.get(key)
            if eh is None or edge > eh.get("edge", 0):
                hist[key] = {
                    "date":        gdate,
                    "tier":        tier,
                    "bet":         "%s \u72ec\u8d0f" % bcn,
                    "sp":          "%s vs %s" % (a_sp_str, h_sp_str),
                    "book":        bbook,
                    "price":       bp,
                    "model_prob":  round(model_prob, 4),
                    "bet_prob":    round(bet_prob, 4),
                    "edge":        round(edge, 4),
                    "conf_factor": round(conf_factor, 2),
                    "kelly_stake": stake,
                    "result":      eh.get("result", "pending") if eh else "pending",
                }

tr, w, wr, pnl = calc_perf(hist)
tp = sum(len(v) for v in picks.values())
ae = sum(p["edge"] for d in picks.values() for p in d.values()) / tp if tp else 0

lines = [
    "\u26be **MLB V105 \u5206\u6790\u5831\u544a**",
    "\U0001f550 %s | \u8cc7\u6599: %s | \u5148\u767c: %s" % (
        now_tw.strftime("%m/%d %H:%M"), src,
        "\u5df2\u53d6\u5f97" if pitchers else "\u672a\u53d6\u5f97"),
    "\U0001f4cc \u6b63\u5f0f\u8a18\u9304\u7248\u672c" if official else "\U0001f527 \u6e2c\u8a66\u7248\u672c\uff08\u4e0d\u5beb\u5165\u56de\u6e2c\uff09",
    "",
]

if not picks:
    lines.append("\u4eca\u65e5\u7121\u7b26\u5408\u689d\u4ef6\u4e4b\u63a8\u85a6\u3002")
else:
    for date in sorted(picks):
        label = "\U0001f4c5 \u4eca\u65e5\u8cfb\u4e8b" if date == today else "\u23ed \u9810\u544a %s" % date
        cnt   = len(picks[date])
        lines.append("**%s**\uff08%d \u5834\uff09" % (label, cnt))
        lines.append("\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014")
        for p in sorted(picks[date].values(), key=lambda x: x["edge"], reverse=True):
            lines.append(p["msg"])

lines += [
    "\u2550" * 20,
    "\U0001f4ca **\u6b77\u53f2\u7e3e\u6548**\uff08V105 \u6240\u6709\u7b49\u7d1a\uff09",
    "\u63a8\u85a6: %d \u5834 | \u5df2\u7d50\u7b97: %d \u5834 | \u52dd\u7387: **%.1f%%** | \u640d\u76ca: **%+.1f \u5143**" % (
        len(hist), tr, wr, pnl),
    "\u672c\u65e5: %d \u5834 | \u5e73\u5747Edge: **%.1f%%**" % (tp, ae * 100),
]

out = "\n".join(lines)
if official:
    save_hist(hist)
log.info("Sending to Discord, length: %d", len(out))
send(out)
log.info("Done")
```

if **name** == “**main**”:
run()
