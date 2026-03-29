import requests, os, random, logging, json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("MLB_V102")

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
WEBHOOK      = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN     = os.getenv("GH_TOKEN", "")

SIMS=50000; EDGE_MIN=0.08; MOD_W=0.25; MKT_W=0.75
STD=2.2; HA=0.10; MAX_RL=2.5; MIN_RL=0.5
MIN_P=1.75; MAX_P=2.15; LIMIT=1900
BANK=1000.0; KELLY=0.15

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

OUT = {"cole","santander","lopez","pjones","mccullers"}
LTD = {"trout","acuna","buxton","degrom","steele"}
SS  = {"ohtani","judge","freeman","acuna","tatis","ramirez","harper",
       "guerrero","trout","cole","wheeler","skubal","sale","fried",
       "lindor","soto","betts","seager","witt","degrom","skenes"}

SS_PEN=1.2; ST_PEN=0.8; LT_PEN=0.4

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

# Pitcher ERA tiers - used to adjust expected runs
# era_adj: runs above/below league average (4.30) per game
PITCHER_ERA = {
    # Aces
    "cole":       2.90, "fried":      3.10, "wheeler":    3.00,
    "skubal":     2.80, "sale":       3.20, "degrom":     2.95,
    "ohtani":     3.10, "burnes":     3.30, "castillo":   3.40,
    "webb":       3.20, "musgrove":   3.60, "skenes":     3.00,
    "glasnow":    3.10, "ragans":     3.40, "woodruff":   3.50,
    "gallen":     3.50, "mcclanahan": 3.30, "bieber":     3.50,
    # Mid rotation
    "bibee":      3.70, "peralta":    3.60, "berrios":    3.80,
    "gausman":    3.70, "eovaldi":    3.90, "steele":     3.80,
    "imanaga":    3.60, "burns":      3.50, "hgreene":    3.80,
    "nola":       3.70, "cease":      3.90, "flaherty":   3.90,
    "gray":       4.00, "rasmussen":  4.00, "mikolas":    4.30,
    "woo":        3.80, "bradish":    3.70, "gilbert":    3.80,
    "liberatore": 4.50, "cavalli":    4.60, "garrett":    4.20,
    "mahle":      4.10, "peterson":   4.20, "keller":     4.10,
    "javier":     4.30, "detmers":    4.40, "lorenzen":   4.50,
    "wacha":      4.40, "vasquez":    4.50, "cantillo":   4.60,
    # 2026 new/young starters
    "horton":     4.20, "singer":     4.30, "burke":      4.80,
    "patrick":    4.50, "springs":    4.40, "mcgreevy":   4.60,
    "boyle":      4.30, "bradley":    4.50, "warren":     4.70,
    "rodriguez":  4.20, "lopez":      4.40, "perez":      4.60,
    # Back rotation / fallback
    "freeland":   4.80, "smith":      4.90, "soriano":    4.40,
    "kurtz":      4.50, "manoah":     4.60, "arodriguez": 4.50,
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
    "New York Yankees":      "\u6d0b\u57fa",
    "Los Angeles Dodgers":   "\u9053\u5947",
    "Atlanta Braves":        "\u52c7\u58eb",
    "Houston Astros":        "\u592a\u7a7a\u4eba",
    "Baltimore Orioles":     "\u91d1\u9db6",
    "Philadelphia Phillies": "\u8cbb\u57ce\u4eba",
    "Texas Rangers":         "\u904a\u9a0e\u5175",
    "Arizona Diamondbacks":  "\u97ff\u5c3e\u86c7",
    "Minnesota Twins":       "\u96d9\u57ce",
    "Seattle Mariners":      "\u6c34\u624b",
    "Milwaukee Brewers":     "\u91c0\u9152\u4eba",
    "Chicago Cubs":          "\u5c0f\u718a",
    "San Francisco Giants":  "\u5de8\u4eba",
    "Boston Red Sox":        "\u7d05\u896a",
    "New York Mets":         "\u5927\u90fd\u6703",
    "Toronto Blue Jays":     "\u85cd\u9ce5",
    "Cleveland Guardians":   "\u5b88\u8b77\u8005",
    "Tampa Bay Rays":        "\u5149\u82b3",
    "St. Louis Cardinals":   "\u7d05\u96c0",
    "San Diego Padres":      "\u6559\u58eb",
    "Detroit Tigers":        "\u8001\u864e",
    "Kansas City Royals":    "\u7687\u5bb6",
    "Pittsburgh Pirates":    "\u6d77\u76dc",
    "Cincinnati Reds":       "\u7d05\u4eba",
    "Colorado Rockies":      "\u6d1b\u78f4",
    "Oakland Athletics":     "\u904b\u52d5\u5bb6",
    "Los Angeles Angels":    "\u5929\u4f7f",
    "Miami Marlins":         "\u99ac\u6797\u9b5a",
    "Washington Nationals":  "\u570b\u6c11",
    "Chicago White Sox":     "\u767d\u896a",
}


def norm(name):
    if not name: return name
    n = name.lower()
    for full in SHORT:
        if n in full.lower() or full.lower() in n:
            return full
    return name


def safe_get(url, headers=None, params=None, retries=3, timeout=15):
    for i in range(1, retries+1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            log.warning("Timeout %d/%d %s", i, retries, url)
        except requests.exceptions.HTTPError as e:
            log.error("HTTP %s: %s", e.response.status_code, url); break
        except Exception as e:
            log.warning("Err %d/%d: %s", i, retries, e)
    return None


def fetch_probable_pitchers():
    """
    Fetch today probable starters from ESPN scoreboard API.
    Returns dict: {game_id: {"home": "pitcher_name", "away": "pitcher_name"}}
    Also returns dict: {team_full_name: "pitcher_name"}
    """
    today = datetime.utcnow().strftime("%Y%m%d")
    url   = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
    data  = safe_get(url, params={"dates": today})
    if not data:
        log.warning("ESPN scoreboard failed, no pitcher data")
        return {}

    team_pitcher = {}
    try:
        for event in data.get("events", []):
            for comp in event.get("competitions", []):
                for team in comp.get("competitors", []):
                    team_name = norm(team.get("team", {}).get("displayName", ""))
                    if not team_name:
                        continue
                    # probable pitcher is in "probables" list
                    for prob in team.get("probables", []):
                        pitcher = prob.get("athlete", {}).get("displayName", "")
                        if pitcher:
                            last = pitcher.split()[-1].lower()
                            team_pitcher[team_name] = last
                            log.info("Probable: %s -> %s", team_name, last)
    except Exception as e:
        log.warning("Pitcher parse error: %s", e)

    log.info("Probable pitchers found: %d teams", len(team_pitcher))
    return team_pitcher


def pitcher_era_adj(pitcher_last):
    """
    Return runs adjustment vs league average.
    Negative = pitcher better than avg = fewer runs allowed.
    """
    if not pitcher_last:
        return 0.0
    era = PITCHER_ERA.get(pitcher_last.lower())
    if era is None:
        return 0.0
    return round((era - LEAGUE_AVG_ERA) / 9 * 6, 3)


def fetch_stats():
    for url in ["https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings",
                "https://site.web.api.espn.com/apis/v2/sports/baseball/mlb/standings"]:
        data = safe_get(url)
        if data: break
    else:
        log.warning("ESPN standings failed, using fallback"); return {}

    def val(s):
        for k in ("value","displayValue","summary"):
            v = s.get(k)
            if v is not None:
                try: return float(str(v).replace(",",""))
                except: pass
        return 0.0

    ratings = {}
    try:
        for grp in data.get("children",[]):
            for e in grp.get("standings",{}).get("entries",[]):
                slug = e.get("team",{}).get("abbreviation","").lower()
                full = SLUG.get(slug)
                if not full: continue
                st = {(s.get("name") or s.get("shortDisplayName","")): val(s)
                      for s in e.get("stats",[]) if s.get("name") or s.get("shortDisplayName")}
                w = st.get("wins",   st.get("W", st.get("w",0)))
                l = st.get("losses", st.get("L", st.get("l",0)))
                t = w + l
                if t == 0: continue
                wp = w / t
                rs = st.get("pointsFor",     st.get("RS", st.get("runsScored",0)))
                ra = st.get("pointsAgainst", st.get("RA", st.get("runsAllowed",0)))
                if rs > 10 and ra > 10:
                    off, df = round(rs/t,2), round(ra/t,2)
                else:
                    off, df = round(3.5+wp*3.5,2), round(5.5-wp*3.0,2)
                ratings[full] = {"off":off,"def":df,"form":round((wp-0.5)*0.5,3)}
    except Exception as e:
        log.warning("ESPN parse error: %s", e)
    log.info("ESPN ratings: %d teams", len(ratings))
    return ratings


def get_injuries():
    try:
        r = requests.get("https://www.rotowire.com/baseball/injury-report.php",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        text = r.text.lower()
        out_kw  = ["ruled out","will not play","is out","60-day il","15-day il","10-day il"]
        skip_kw = ["questionable","probable","available","day-to-day"]
        inj = {}
        for team, players in ROSTER.items():
            for p in players:
                if p in text:
                    idx = text.find(p)
                    ctx = text[max(0,idx-80):idx+200]
                    if any(s in ctx for s in skip_kw): continue
                    if any(s in ctx for s in out_kw):
                        inj.setdefault(team,[]).append(p)
        for team, players in ROSTER.items():
            for p in players:
                if p in OUT and p not in inj.get(team,[]):
                    inj.setdefault(team,[]).append(p)
        log.info("Injuries: %d entries", sum(len(v) for v in inj.values()))
        return inj
    except Exception as e:
        log.warning("RotoWire failed: %s", e)
        return {t:[p for p in pl if p in OUT] for t,pl in ROSTER.items() if any(p in OUT for p in pl)}


def load_hist():
    if not GH_TOKEN: return {}
    h = {"Authorization":"token "+GH_TOKEN}
    gists = safe_get("https://api.github.com/gists", headers=h)
    if not gists: return {}
    for g in gists:
        if g.get("description") == "mlb_bot_history":
            d = safe_get(list(g["files"].values())[0]["raw_url"])
            return d if isinstance(d, dict) else {}
    return {}


def save_hist(hist):
    if not GH_TOKEN: return
    h = {"Authorization":"token "+GH_TOKEN,"Content-Type":"application/json"}
    body = json.dumps(hist, ensure_ascii=False, indent=2)
    gists = safe_get("https://api.github.com/gists", headers=h)
    gid = next((g["id"] for g in (gists or []) if g.get("description")=="mlb_bot_history"), None)
    pl = {"description":"mlb_bot_history","public":False,
          "files":{"history.json":{"content":body}}}
    try:
        if gid:
            requests.patch("https://api.github.com/gists/"+gid, headers=h, json=pl, timeout=10)
        else:
            requests.post("https://api.github.com/gists", headers=h, json=pl, timeout=10)
        log.info("History saved")
    except Exception as e:
        log.error("Save failed: %s", e)


def calc_perf(hist):
    total=win=0; profit=0.0
    for r in hist.values():
        if r.get("result") not in ["win","loss"]: continue
        total+=1; stake=r.get("kelly_stake",10.0)
        if r["result"]=="win": win+=1; profit+=stake*(r.get("price",1.9)-1)
        else: profit-=stake
    return total, win, (win/total*100 if total else 0), profit


def kelly(prob, price):
    b=price-1; k=max(0.0,(b*prob-(1-prob))/b)*KELLY
    return round(BANK*k,1)


def predict_margin(home, away, inj, ratings, pitchers):
    hb = ratings.get(home, BASE.get(home, DEF_RATING))
    ab = ratings.get(away, BASE.get(away, DEF_RATING))
    hs, as_ = dict(hb), dict(ab)

    def missing(team):
        il = [p.lower() for p in inj.get(team,[])]
        res = []
        for p in ROSTER.get(team,[]):
            if p in OUT or any(p in x for x in il): res.append((p,"out",team))
            elif p in LTD: res.append((p,"ltd",team))
        return res

    hm, am = missing(home), missing(away)
    for p,s,t in hm:
        pen=(SS_PEN if p in SS else ST_PEN) if s=="out" else LT_PEN
        hs["off"]-=pen*0.6; hs["def"]+=pen*0.4
    for p,s,t in am:
        pen=(SS_PEN if p in SS else ST_PEN) if s=="out" else LT_PEN
        as_["off"]-=pen*0.6; as_["def"]+=pen*0.4

    h_pitcher = pitchers.get(home, "")
    a_pitcher = pitchers.get(away, "")
    h_pitch_adj = pitcher_era_adj(h_pitcher)
    a_pitch_adj = pitcher_era_adj(a_pitcher)

    he = (hs["off"] + as_["def"]) / 2 + hb.get("form",0.0) - a_pitch_adj
    ae = (as_["off"] + hs["def"]) / 2 + ab.get("form",0.0) - h_pitch_adj
    margin = (he - ae) + HA

    def fmt(lst):
        return ["%s %s(%s)"%(CN.get(t,t[:3]),p.upper(),"OUT" if s=="out" else "LTD") for p,s,t in lst]
    return margin, fmt(hm), fmt(am), h_pitcher, a_pitcher


def predict_total(home, away, ratings, pitchers, market_total=None):
    h = ratings.get(home, BASE.get(home, DEF_RATING))
    a = ratings.get(away, BASE.get(away, DEF_RATING))
    h_pitcher = pitchers.get(home, "")
    a_pitcher = pitchers.get(away, "")
    h_adj = pitcher_era_adj(h_pitcher)  # home SP quality -> affects away runs
    a_adj = pitcher_era_adj(a_pitcher)  # away SP quality -> affects home runs
    # home runs = home offense vs away pitching
    h_exp = h["off"] - a_adj
    # away runs = away offense vs home pitching
    a_exp = a["off"] - h_adj
    model_total = round(h_exp + a_exp, 1)
    # blend with market total to correct systematic bias
    if market_total:
        return round(model_total * 0.40 + market_total * 0.60, 1)
    return model_total


def consensus_line(books, team):
    pts = [o.get("point") for b in books for m in b.get("markets",[])
           if m.get("key")=="spreads" for o in m.get("outcomes",[])
           if norm(o.get("name",""))==team and o.get("point") is not None]
    return sum(pts)/len(pts) if pts else None


def consensus_total(books):
    pts = [o.get("point") for b in books for m in b.get("markets",[])
           if m.get("key")=="totals" for o in m.get("outcomes",[])
           if o.get("name","").lower()=="over" and o.get("point") is not None]
    return sum(pts)/len(pts) if pts else None


def sim(blended, line):
    return sum(1 for _ in range(SIMS)
               if blended+random.gauss(0,STD)+line>0)/SIMS


def fetch_odds():
    data = safe_get("https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
                    params={"apiKey":ODDS_API_KEY,"regions":"us",
                            "markets":"spreads,totals","oddsFormat":"decimal"})
    if not data: log.error("Odds API failed"); return []
    log.info("Odds: %d games", len(data)); return data


def send(content):
    lines=content.split("\n"); chunk=""; chunks=[]
    for line in lines:
        if len(chunk)+len(line)+1>LIMIT: chunks.append(chunk); chunk=line+"\n"
        else: chunk+=line+"\n"
    if chunk: chunks.append(chunk)
    for i,part in enumerate(chunks,1):
        label="(%d/%d)\n%s"%(i,len(chunks),part) if len(chunks)>1 else part
        try:
            r=requests.post(WEBHOOK,json={"content":label},timeout=10); r.raise_for_status()
        except Exception as e:
            log.error("Discord chunk %d failed: %s",i,e)


def run():
    if not all([ODDS_API_KEY, WEBHOOK]):
        log.error("Missing env vars"); return

    now_utc=datetime.utcnow(); now_tw=now_utc+timedelta(hours=8)
    today=now_tw.strftime("%Y-%m-%d")
    official=(now_utc.hour==22)
    log.info("Official run: %s (UTC hour: %d)", official, now_utc.hour)

    ratings  = fetch_stats()
    src      = "ESPN" if ratings else "fallback"
    inj      = get_injuries()
    pitchers = fetch_probable_pitchers()
    games    = fetch_odds()
    hist     = load_hist()
    if not games: return

    picks = {}

    for g in games:
        try:
            cut=datetime.strptime(g["commence_time"],"%Y-%m-%dT%H:%M:%SZ")
            ctw=cut+timedelta(hours=8)
        except: continue
        if cut < now_utc: continue

        gdate=ctw.strftime("%Y-%m-%d")
        home=norm(g.get("home_team",""))
        away=norm(g.get("away_team",""))
        gid="%s@%s_%s"%(away,home,gdate)
        books=g.get("bookmakers",[])
        picks.setdefault(gdate,{})

        margin,hm,am,h_sp,a_sp = predict_margin(home,away,inj,ratings,pitchers)
        ct = consensus_total(books)
        mt = predict_total(home,away,ratings,pitchers,ct)
        ou = ""
        if ct:
            pure = predict_total(home,away,ratings,pitchers)
            d = pure - ct
            if d > 0.5:   ou = "大分偏向 OVER (純模型%.1f / 市場%.1f)"%(pure,ct)
            elif d < -0.5: ou = "小分偏向 UNDER (純模型%.1f / 市場%.1f)"%(pure,ct)
            else:          ou = "大小分中性 (純模型%.1f / 市場%.1f)"%(pure,ct)

        # Pitcher display
        h_sp_era = PITCHER_ERA.get(h_sp, None)
        a_sp_era = PITCHER_ERA.get(a_sp, None)
        h_sp_str = "%s(ERA%.2f)"%(h_sp.upper(),h_sp_era) if h_sp and h_sp_era else (h_sp.upper() if h_sp else "TBD")
        a_sp_str = "%s(ERA%.2f)"%(a_sp.upper(),a_sp_era) if a_sp and a_sp_era else (a_sp.upper() if a_sp else "TBD")

        for book in books:
            for market in book.get("markets",[]):
                if market.get("key")!="spreads": continue
                for outcome in market.get("outcomes",[]):
                    name  = norm(outcome.get("name",""))
                    line  = outcome.get("point",0)
                    price = outcome.get("price",0)
                    if not (MIN_RL<=abs(line)<=MAX_RL): continue
                    if not (MIN_P<price<=MAX_P): continue
                    cl = consensus_line(books,name) or line
                    if (line-cl if line>0 else cl-line) < 0: continue
                    target  = margin if name==home else -margin
                    blended = target*MOD_W+(-cl)*MKT_W
                    prob    = sim(blended,line)
                    edge    = prob-(1/price)
                    if edge < EDGE_MIN: continue

                    miss  = (hm if name==home else am)+(am if name==home else hm)
                    stake = kelly(prob,price)
                    tier  = "\U0001f48e \u9802\u7d1a" if edge>0.12 else ("\U0001f525 \u5f37\u529b" if edge>0.09 else "\u2b50 \u7a69\u5b9a")
                    acn   = CN.get(away,  SHORT.get(away,  away))
                    hcn   = CN.get(home,  SHORT.get(home,  home))
                    bcn   = CN.get(name,  SHORT.get(name,  name))
                    ms    = "\u50b7\u5175: "+", ".join(miss) if miss else "\u9663\u5bb9\u6b63\u5e38"
                    ou_line = ("\n> %s"%ou) if ou else ""

                    msg = (
                        "\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n"
                        "**%s  %s\uff06 @ \uff06%s**\n"
                        "\U0001f550 %s\n"
                        "\u26be \u5148\u767c: %s \u2014 %s\n"
                        "\U0001f4b0 \u4eca\u65e5\u63a8\u85a6: `%s %+.1f` @ **%.2f** (%s)\n"
                        "> \u5171\u8b58\u7dda: %+.1f | %s\n"
                        "> \u52dd\u7387: **%.1f%%** | Edge: **%+.1f%%** | Kelly: $%.1f%s\n"
                    ) % (
                        tier, acn, hcn,
                        ctw.strftime("%m/%d %H:%M"),
                        a_sp_str, h_sp_str,
                        bcn, line, price, book.get("title","?"),
                        cl, ms,
                        prob*100, edge*100, stake, ou_line
                    )

                    ex=picks[gdate].get(gid)
                    if ex is None or edge>ex["edge"]:
                        picks[gdate][gid]={"edge":edge,"prob":prob,"price":price,
                                            "kelly_stake":stake,"msg":msg}
                    if edge>0.12 and official and gdate==today:
                        eh=hist.get(gid)
                        if eh is None or edge>eh.get("edge",0):
                            hist[gid]={"date":gdate,
                                       "bet":"%s %+.1f"%(bcn,line),
                                       "sp":"%s vs %s"%(a_sp_str,h_sp_str),
                                       "book":book.get("title","?"),
                                       "price":price,"prob":round(prob,4),
                                       "edge":round(edge,4),"kelly_stake":stake,
                                       "result":eh.get("result","pending") if eh else "pending"}

    tr,w,wr,pnl = calc_perf(hist)
    tp = sum(len(v) for v in picks.values())
    ae = sum(p["edge"] for d in picks.values() for p in d.values())/tp if tp else 0

    out  = (
        "\u26be **MLB V102 \u5206\u6790\u5831\u544a**\n"
        "\U0001f550 %s | \u8cc7\u6599: %s | \u5148\u767c: %s\n"
        "%s\n"
    ) % (
        now_tw.strftime("%m/%d %H:%M"),
        src,
        "\u5df2\u53d6\u5f97" if pitchers else "\u672a\u53d6\u5f97",
        "\U0001f4cc \u6b63\u5f0f\u8a18\u9304\u7248\u672c" if official else "\U0001f527 \u6e2c\u8a66\u7248\u672c\uff08\u4e0d\u5beb\u5165\u56de\u6e2c\uff09"
    )

    if not picks:
        out += "\n\u4eca\u65e5\u7121\u7b26\u5408\u689d\u4ef6\u4e4b\u63a8\u85a6\u3002\n"
    else:
        for date in sorted(picks):
            label = "\U0001f4c5 \u4eca\u65e5\u8cfb\u4e8b" if date==today else ("\u23ed \u9810\u544a %s"%date)
            cnt   = len(picks[date])
            out  += "\n**%s**\uff08%d \u5834\uff09\n" % (label, cnt)
            for p in sorted(picks[date].values(), key=lambda x: x["edge"], reverse=True):
                out += p["msg"]

    out += "\u2550"*20+"\n"
    out += (
        "\U0001f4ca **\u6b77\u53f2\u7e3e\u6548** (\U0001f48e \u9802\u7d1a\u5c08\u7528)\n"
        "\u63a8\u85a6: %d \u5834 | \u5df2\u7d50\u7b97: %d \u5834 | "
        "\u52dd\u7387: **%.1f%%** | \u640d\u76ca: **%+.1f \u5143**\n"
    ) % (len(hist), tr, wr, pnl)

    if official:
        save_hist(hist)
    log.info("Sending to Discord, length: %d", len(out))
    send(out)
    log.info("Done")


if __name__ == "__main__":
    run()
