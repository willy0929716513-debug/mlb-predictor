import os, json, math, logging, datetime, requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("MLB_V129")

ODDS_API_KEY    = os.getenv("ODDS_API_KEY", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN        = os.getenv("GH_TOKEN", "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")  # OpenWeatherMap（選用）

GIST_DESC = "mlb_bot_history"

# ── 模型參數 ──────────────────────────────────
EDGE_MIN       = 0.08
EDGE_MIN_RL    = 0.12   # 讓分（run line）需更大 edge，波動較高
EDGE_MIN_TOT   = 0.09   # 大小分（totals）edge 門檻
MOD_W          = 0.18
MKT_W          = 0.82
TOTAL_STD      = 2.30   # 兩隊合計得分標準差（比勝負差距大）
STD            = 1.65
MIN_P          = 1.35
MAX_P          = 2.75
BANK           = float(os.getenv("BANK",      "1000"))
KELLY          = float(os.getenv("KELLY_FRAC", "0.12"))
KELLY_MAX      = float(os.getenv("KELLY_MAX",  "150"))
KELLY_MIN      = float(os.getenv("KELLY_MIN",  "5"))
LEAGUE_ERA     = 4.20
HIST_TTL       = 90
GAP1, GAP2, GAP3 = 1.5, 2.5, 3.5
ESPN_ALPHA_MAX = 0.65
SP_RECENT_W    = 0.65   # 近期 ERA 權重
SP_SEASON_W    = 0.35

# ── ★ 球場係數（FanGraphs Park Factors 2024）──
PARK_FACTOR = {
    "rockies":1.30,"rangers":1.12,"red sox":1.10,"cubs":1.08,"reds":1.07,
    "brewers":1.05,"phillies":1.04,"athletics":1.03,"blue jays":1.02,
    "nationals":1.01,"cardinals":1.00,"astros":0.99,"dodgers":0.99,
    "angels":0.99,"tigers":0.98,"white sox":0.98,"twins":0.98,"mets":0.97,
    "braves":0.97,"orioles":0.97,"yankees":0.97,"giants":0.96,"pirates":0.96,
    "padres":0.96,"guardians":0.95,"royals":0.95,"rays":0.95,
    "diamondbacks":0.94,"marlins":0.94,"mariners":0.93,
}

# ── ★ 牛棚 ERA（2024 賽季）──
BULLPEN_ERA = {
    "dodgers":3.45,"phillies":3.52,"braves":3.58,"astros":3.61,"padres":3.63,
    "guardians":3.65,"mariners":3.67,"yankees":3.70,"cubs":3.72,"mets":3.75,
    "rangers":3.78,"brewers":3.80,"red sox":3.82,"blue jays":3.85,"giants":3.87,
    "royals":3.90,"twins":3.92,"tigers":3.95,"orioles":3.97,"rays":3.98,
    "pirates":4.02,"diamondbacks":4.05,"cardinals":4.08,"reds":4.10,
    "athletics":4.15,"angels":4.20,"nationals":4.25,"white sox":4.35,
    "marlins":4.40,"rockies":4.85,
}
LEAGUE_BULL_ERA = 3.95
LEAGUE_DEF_AVG  = 4.45   # MLB 平均每場失分（用於防守品質調整）

# ── 投手賽季 ERA ──────────────────────────────
PITCHER_ERA = {
    "skubal":3.10,"yamamoto":2.49,"glasnow":3.00,"fried":3.10,"gausman":3.59,
    "schlittler":4.50,"sanchez":2.50,"skenes":1.96,"gilbert":3.44,"woo":3.50,
    "alcantara":4.20,"burns":3.50,"crochet":2.59,"brown":2.43,"cease":3.80,
    "webb":3.20,"pivetta":2.87,"vasquez":4.40,"peralta":3.40,"senga":3.60,
    "ryan":3.42,"bibee":4.24,"ragans":3.40,"lugo":1.59,"valdez":3.20,
    "leiter":2.45,"elder":4.20,"sale":2.58,"roupp":4.22,"mccullers":3.27,
    "gallen":4.00,"rodriguez_e":4.20,"soroka":4.00,"rasmussen":2.76,
    "boyle":3.18,"hancock":3.50,"rogers_t":2.50,"eovaldi":3.80,"springs":4.30,
    "ashcraft":2.25,"mlodzinski":4.36,"soriano_j":3.93,"detmers":2.38,
    "freeland":4.75,"misiorowski":4.36,"bradley_t":3.88,"bradley":3.88,
    "liberatore":4.21,"severino":4.54,"cavalli":4.25,"boyd":3.21,"horton":4.10,
    "abbott":3.42,"burke_s":3.60,"smith_s":3.81,"pfaadt":4.10,"weathers":4.50,
    "williamson":4.60,"chandler":4.00,"mize":4.30,"pallante":4.60,
    "mikolas":4.20,"marquez":4.90,"flexen":4.90,"taillon":4.40,"voth":4.80,
    "adon":4.60,"kolek":4.50,"crawford_k":4.20,"sandoval_p":4.00,
    "imanaga":3.55,"steele":3.75,"wetherholt":4.50,"winn":4.30,"keller":4.00,
    "pepiot":4.30,"blackburn":4.50,"javier":4.20,"paddack":4.30,"wood":4.20,
    "musgrove":3.50,"king_m":3.90,"bieber":3.40,"castillo":3.30,"nola":3.70,
    "flaherty":3.85,"ohtani":3.00,"sasaki":2.90,"mcclanahan":3.10,"burnes":3.20,
    "verlander":3.80,"kirby":3.50,"bello":4.10,"berrios":3.80,"junk":5.10,
    "fedde":4.60,"poulin":5.30,"painter":4.80,"mahle":4.20,"burns_c":3.50,
    "civale":4.50,"gray_j":3.95,"lauer":4.40,"kikuchi":4.20,"degrom":3.50,
    "holmes":4.00,"buehler":4.20,"williams_g":3.80,"varland":4.60,
    "martin_c":4.60,"sears":4.50,"cortes":4.30,"houser":4.60,"lynch":4.70,
    "cox":4.80,"feltner":5.20,"hudson":5.00,"small":4.70,"wesneski":4.40,
    # ── 2026 新增 / 修正 ──────────────────────────
    "povich":4.10,"woodruff":4.20,"littell":4.60,"cameron":4.60,
    "scherzer":4.30,"taylor":4.90,"lyles":5.10,"hendricks":4.70,
    "stroman":4.20,"alexander":4.40,"lorenzen":4.80,"cobb":4.50,
    "montgomery":4.10,"snell":3.60,"means":4.30,"bass":4.80,
    "irvin":4.60,"urquidy":4.70,"bradish":3.80,"suarez":4.50,
}

# ── BASE 隊伍實力 ──────────────────────────────
BASE = {
    "dodgers":{"off":5.10,"def":4.15},"yankees":{"off":4.85,"def":4.20},
    "mets":{"off":4.74,"def":4.21},"braves":{"off":4.76,"def":4.24},
    "phillies":{"off":4.58,"def":4.30},"mariners":{"off":4.44,"def":4.06},
    "brewers":{"off":4.62,"def":4.36},"pirates":{"off":4.50,"def":4.32},
    "blue jays":{"off":4.54,"def":4.38},"tigers":{"off":4.46,"def":4.24},
    "red sox":{"off":4.46,"def":4.28},"astros":{"off":4.72,"def":4.58},
    "rangers":{"off":4.50,"def":4.38},"cubs":{"off":4.54,"def":4.41},
    "orioles":{"off":4.68,"def":4.60},"royals":{"off":4.60,"def":4.58},
    "rays":{"off":4.34,"def":4.36},"diamondbacks":{"off":4.47,"def":4.58},
    "reds":{"off":4.42,"def":4.62},"padres":{"off":4.40,"def":4.52},
    "guardians":{"off":4.30,"def":4.50},"marlins":{"off":4.37,"def":4.54},
    "giants":{"off":4.22,"def":4.40},"twins":{"off":4.46,"def":4.58},
    "athletics":{"off":4.66,"def":4.88},"cardinals":{"off":4.28,"def":4.65},
    "angels":{"off":4.28,"def":4.72},"white sox":{"off":4.18,"def":4.98},
    "nationals":{"off":4.30,"def":4.98},"rockies":{"off":4.38,"def":5.42},
}
DEF_BASE = {"off":4.40,"def":4.50}

# ── 球場座標（天氣）──────────────────────────
PARK_COORDS = {
    "dodgers":(34.07,-118.24),"yankees":(40.83,-73.93),"mets":(40.76,-73.85),
    "braves":(33.89,-84.47),"phillies":(39.91,-75.17),"mariners":(47.59,-122.33),
    "brewers":(43.03,-87.97),"pirates":(40.44,-80.01),"blue jays":(43.64,-79.39),
    "tigers":(42.34,-83.05),"red sox":(42.35,-71.10),"astros":(29.76,-95.36),
    "rangers":(32.75,-97.08),"cubs":(41.95,-87.65),"orioles":(39.28,-76.62),
    "royals":(39.05,-94.48),"rays":(27.77,-82.65),"diamondbacks":(33.45,-112.07),
    "reds":(39.10,-84.51),"padres":(32.71,-117.16),"guardians":(41.50,-81.70),
    "marlins":(25.78,-80.22),"giants":(37.78,-122.39),"twins":(44.98,-93.28),
    "athletics":(38.59,-121.50),"cardinals":(38.62,-90.19),"angels":(33.80,-117.88),
    "white sox":(41.83,-87.63),"nationals":(38.87,-77.01),"rockies":(39.76,-104.99),
}

CN = {
    "dodgers":"道奇","yankees":"洋基","mets":"大都會","braves":"勇士",
    "phillies":"費城人","mariners":"水手","brewers":"釀酒人","pirates":"海盜",
    "blue jays":"藍鳥","tigers":"老虎","red sox":"紅襪","astros":"太空人",
    "rangers":"遊騎兵","cubs":"小熊","orioles":"金鶯","royals":"皇家",
    "rays":"光芒","diamondbacks":"響尾蛇","reds":"紅人","padres":"教士",
    "guardians":"守護者","marlins":"馬林魚","giants":"巨人","twins":"雙城",
    "athletics":"運動家","cardinals":"紅雀","angels":"天使","white sox":"白襪",
    "nationals":"國民","rockies":"落磯",
}

TEAM_ALIAS = {
    "los angeles dodgers":"dodgers","la dodgers":"dodgers",
    "new york yankees":"yankees","ny yankees":"yankees",
    "new york mets":"mets","ny mets":"mets","atlanta braves":"braves",
    "philadelphia phillies":"phillies","seattle mariners":"mariners",
    "milwaukee brewers":"brewers","pittsburgh pirates":"pirates",
    "toronto blue jays":"blue jays","detroit tigers":"tigers",
    "boston red sox":"red sox","houston astros":"astros","texas rangers":"rangers",
    "chicago cubs":"cubs","baltimore orioles":"orioles","kansas city royals":"royals",
    "tampa bay rays":"rays","arizona diamondbacks":"diamondbacks",
    "az diamondbacks":"diamondbacks","cincinnati reds":"reds","san diego padres":"padres",
    "cleveland guardians":"guardians","miami marlins":"marlins",
    "san francisco giants":"giants","minnesota twins":"twins",
    "oakland athletics":"athletics","sacramento athletics":"athletics",
    "st. louis cardinals":"cardinals","st louis cardinals":"cardinals",
    "los angeles angels":"angels","la angels":"angels",
    "chicago white sox":"white sox","washington nationals":"nationals",
    "colorado rockies":"rockies",
}

MLB_TEAM_ID = {
    108:"angels",109:"diamondbacks",110:"orioles",111:"red sox",112:"cubs",
    113:"reds",114:"guardians",115:"rockies",116:"tigers",117:"astros",
    118:"royals",119:"dodgers",120:"nationals",121:"mets",133:"athletics",
    134:"pirates",135:"padres",136:"mariners",137:"giants",138:"cardinals",
    139:"rays",140:"rangers",141:"blue jays",142:"twins",143:"phillies",
    144:"braves",145:"white sox",146:"marlins",147:"yankees",158:"brewers",
}

ESPN_ABBR = {
    "nyy":"yankees","lad":"dodgers","atl":"braves","hou":"astros","bal":"orioles",
    "phi":"phillies","tex":"rangers","ari":"diamondbacks","min":"twins",
    "sea":"mariners","mil":"brewers","chc":"cubs","sf":"giants","bos":"red sox",
    "nym":"mets","tor":"blue jays","cle":"guardians","tb":"rays","stl":"cardinals",
    "sd":"padres","det":"tigers","kc":"royals","pit":"pirates","cin":"reds",
    "col":"rockies","oak":"athletics","laa":"angels","mia":"marlins",
    "wsh":"nationals","chw":"white sox",
}

ROSTER = {
    "yankees":["judge","goldschmidt","volpe","stanton","cole","rodon"],
    "dodgers":["yamamoto","ohtani","freeman","betts","sasaki","snell"],
    "braves":["sale","acuna","olson","riley","schwellenbach","waldrep"],
    "astros":["brown","pena","abreu","bregman","diaz","wesneski"],
    "orioles":["rogers_t","henderson","rutschman","holliday","westburg","eflin"],
    "phillies":["sanchez","wheeler","nola","harper","schwarber","cole_w"],
    "rangers":["eovaldi","seager","carter","garcia"],
    "diamondbacks":["gallen","marte","carroll","moreno"],
    "twins":["ryan","buxton","lewis","miranda","lopez_p","festa"],
    "mariners":["gilbert","woo","kirby","castillo","raleigh","rodriguez"],
    "brewers":["misiorowski","contreras","chourio","yelich","adames"],
    "cubs":["boyd","steele","imanaga","suzuki","busch","taillon"],
    "giants":["webb","arraez","bailey","conforto"],
    "red sox":["crochet","duran","mayer","casas","houck","gonzalez_r"],
    "mets":["peralta","holmes","lindor","soto","vientos","nimmo"],
    "blue jays":["gausman","berrios","bieber","guerrero","varsho"],
    "guardians":["bibee","williams_g","ramirez","kwan","naylor"],
    "rays":["rasmussen","aranda","caminero","liberatore"],
    "cardinals":["liberatore","wetherholt","winn","gorman","donovan"],
    "padres":["pivetta","musgrove","tatis","machado","merrill","buehler_w"],
    "tigers":["skubal","verlander","torkelson","jung","jobe","melton","brieske"],
    "royals":["ragans","witt","pasquantino","perez","marsh","kolek"],
    "pirates":["skenes","chandler","hayes","triolo"],
    "reds":["abbott","burns","hgreene","delacruz","suarez"],
    "rockies":["freeland","tovar","doyle","beck"],
    "athletics":["severino","rooker","soderstrom","hoglund"],
    "angels":["soriano_j","trout","neto","schanuel","rendon","stephenson_r"],
    "marlins":["alcantara","paddack","stowers"],
    "nationals":["cavalli","wood","garcia","crews"],
    "white sox":["smith_s","martin","montgomery","teel","bush_k"],
}
OUT_STATIC = {
    "athletics":["hoglund"],"orioles":["westburg","bautista"],
    "red sox":["houck","gonzalez_r"],"white sox":["bush_k"],
    "tigers":["jobe","melton","brieske"],"astros":["wesneski"],
    "royals":["marsh"],"angels":["rendon","stephenson_r"],
    "dodgers":["snell"],"braves":["schwellenbach","waldrep","acuna"],
    "twins":["lopez_p"],"padres":["buehler_w"],
    "phillies":["cole_w","wheeler_z"],"yankees":["cole","rodon"],
    "reds":["hgreene"],
}
LTD_STATIC = {
    "orioles":[("holliday","A"),("eflin","A")],"red sox":[("casas","B"),("sandoval_p","B")],
    "tigers":[("verlander","S")],"astros":[("brown","S")],"royals":[("kolek","B")],
    "angels":[("trout","S")],"braves":[("riley","A")],"cubs":[("steele","A")],
    "twins":[("festa","B"),("buxton","A")],
}
LT_PEN = {"S":0.9,"A":0.7,"B":0.4}

KEY_SP = {
    "skubal","yamamoto","glasnow","fried","burns","gilbert","crochet","skenes",
    "castillo","burnes","mcclanahan","gausman","cease","webb","sale","nola",
    "flaherty","verlander","kirby","bieber","ragans","gallen","ohtani","sasaki",
    "degrom","wheeler","cole","ryan","woo","brown","peralta","lugo","valdez",
    "eovaldi","rogers_t","imanaga","steele",
}
KEY_POS = {
    "trout","judge","freeman","acuna","soto","tatis","devers","betts",
    "witt","henderson","rutschman","riley","seager","machado","lindor",
    "guerrero","harper","schwarber","alvarez","goldschmidt","arenado",
    "ramirez","bregman","springer","stanton","olson","alonso",
    "rodriguez_j","carroll","marte","buxton","adames","yelich","chourio",
    "volpe","torkelson","pasquantino","perez",
}
STAR_DISPLAY = {
    "trout":"Trout","judge":"Judge","freeman":"Freeman","acuna":"Acuña",
    "soto":"Soto","tatis":"Tatis Jr.","devers":"Devers","betts":"Betts",
    "witt":"Witt Jr.","henderson":"Henderson","rutschman":"Rutschman",
    "riley":"Riley","seager":"Seager","machado":"Machado","lindor":"Lindor",
    "guerrero":"Guerrero Jr.","harper":"Harper","schwarber":"Schwarber",
    "alvarez":"Álvarez","goldschmidt":"Goldschmidt","arenado":"Arenado",
    "ramirez":"Ramírez","bregman":"Bregman","springer":"Springer",
    "stanton":"Stanton","olson":"Olson","alonso":"Alonso","snell":"Snell",
    "buxton":"Buxton","adames":"Adames","yelich":"Yelich",
    "skubal":"Skubal","yamamoto":"Yamamoto","fried":"Fried","burns":"Burns",
    "crochet":"Crochet","skenes":"Skenes","castillo":"Castillo",
    "burnes":"Burnes","gausman":"Gausman","cease":"Cease","webb":"Webb",
    "sale":"Sale","nola":"Nola","verlander":"Verlander","kirby":"Kirby",
    "bieber":"Bieber","ragans":"Ragans","gallen":"Gallen","ohtani":"Ohtani",
    "sasaki":"Sasaki","degrom":"deGrom","wheeler":"Wheeler","cole":"Cole",
    "volpe":"Volpe","rodriguez_j":"J.Rodríguez",
}

# 動態快取
_DYN_OUT      = {}
_DYN_LTD      = {}
_ESPN_RATINGS = {}
_RECENT_ERA   = {}
_WEATHER_CACHE= {}
_SCORING_FORM    = {}   # {team: recent_runs_per_game} 最近10場得分均值
_B2B_TEAMS       = set() # 昨天有出賽的球隊（連續出賽疲勞）
_SERIES_MOMENTUM = {}   # {(t1,t2): [(home_team, home_won), ...]} 近3天系列賽紀錄


# ══════════════════════════════════════════════
# 工具函數
# ══════════════════════════════════════════════

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

def _name_to_key(full_name):
    if not full_name: return None
    parts = full_name.strip().split()
    k = parts[-1].lower() if len(parts) >= 2 else full_name.lower()
    if k in ("jr.","sr.","ii","iii","iv") and len(parts) >= 2:
        k = parts[-2].lower()
    return k

def _player_tier(k):
    if k in KEY_SP:  return "S"
    if k in KEY_POS: return "A"
    return "B"

def get_star_injuries(team):
    t = team.lower()
    out_stars, ltd_stars = [], []
    for p in _DYN_OUT.get(t, []):
        if p in KEY_SP or p in KEY_POS:
            out_stars.append(STAR_DISPLAY.get(p, p.title()))
    for item in _DYN_LTD.get(t, []):
        p = item[0] if isinstance(item, tuple) else item
        if p in KEY_SP or p in KEY_POS:
            ltd_stars.append(STAR_DISPLAY.get(p, p.title()))
    return out_stars, ltd_stars


# ══════════════════════════════════════════════
# ★ 投手近期 ERA
# ══════════════════════════════════════════════

def _parse_ip(ip_str):
    """MLB API 局數格式：'6.2' = 6 又 2/3 局（不是 6.2 小數）"""
    try:
        s = str(ip_str or "0").strip()
        if "." in s:
            whole, frac = s.split(".", 1)
            return int(whole) + int(frac) / 3.0
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def _fetch_recent_era(pitcher_id, last_n=3):
    data = safe_get(
        "https://statsapi.mlb.com/api/v1/people/%d/stats" % pitcher_id,
        params={"stats":"gameLog","group":"pitching",
                "season":datetime.date.today().year,
                "fields":"stats,splits,stat,inningsPitched,earnedRuns"},
        timeout=10,
    )
    if not data: return None
    splits = []
    for s in data.get("stats",[]): splits = s.get("splits",[]); break
    starts = [s for s in splits if _parse_ip(s.get("stat",{}).get("inningsPitched","0")) >= 3.0]
    recent = starts[-last_n:] if len(starts) >= last_n else starts
    if not recent: return None
    total_er = sum(float(s.get("stat",{}).get("earnedRuns","0") or 0) for s in recent)
    total_ip = sum(_parse_ip(s.get("stat",{}).get("inningsPitched","0")) for s in recent)
    if total_ip < 3: return None
    era = round(total_er / total_ip * 9, 2)
    # ★ 近期 ERA 0.00 或極低（< 0.50）代表樣本太少或開季第一場被完封
    # 用聯盟平均替代，避免模型誤判為超級王牌
    if era < 0.50:
        log.debug("Recent ERA %.2f too low for %s, clamping to league avg", era, pitcher_id)
        return None  # 回傳 None 讓 get_pitcher_era 改用賽季 ERA
    # 上限：近期 ERA > 12 通常是短暫崩盤，限制到 10 避免過度懲罰
    return min(era, 10.0)

def fetch_b2b_teams():
    """找出昨天有出賽的球隊（今天連續出賽者）"""
    global _B2B_TEAMS
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    data = safe_get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={"sportId":1,"date":yesterday,"gameType":"R",
                "fields":"dates,games,teams,home,away,team,id,name,status,detailedState"},
        timeout=10,
    )
    if not data: return
    b2b = set()
    for de in data.get("dates",[]):
        for game in de.get("games",[]):
            status = game.get("status",{}).get("detailedState","")
            if "Final" not in status and "Completed" not in status: continue
            hd = game.get("teams",{}).get("home",{})
            ad = game.get("teams",{}).get("away",{})
            hn = MLB_TEAM_ID.get(hd.get("team",{}).get("id")) or norm_team(hd.get("team",{}).get("name",""))
            an = MLB_TEAM_ID.get(ad.get("team",{}).get("id")) or norm_team(ad.get("team",{}).get("name",""))
            if hn: b2b.add(hn)
            if an: b2b.add(an)
    _B2B_TEAMS = b2b
    log.info("B2B teams: %s", sorted(b2b))

def fetch_recent_scoring():
    """最近14天完賽場次，計算各隊近10場每場得分均值"""
    global _SCORING_FORM
    start     = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    data = safe_get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={"sportId":1,"startDate":start,"endDate":yesterday,
                "hydrate":"linescore","gameType":"R",
                "fields":"dates,games,teams,home,away,team,id,name,score,status,detailedState,linescore,runs"},
        timeout=15,
    )
    if not data: return
    team_runs = {}  # {team: [runs_list]} 最早→最晚
    for de in data.get("dates",[]):
        for game in de.get("games",[]):
            status = game.get("status",{}).get("detailedState","")
            if "Final" not in status and "Completed" not in status: continue
            hd = game.get("teams",{}).get("home",{})
            ad = game.get("teams",{}).get("away",{})
            hn = MLB_TEAM_ID.get(hd.get("team",{}).get("id")) or norm_team(hd.get("team",{}).get("name",""))
            an = MLB_TEAM_ID.get(ad.get("team",{}).get("id")) or norm_team(ad.get("team",{}).get("name",""))
            # 嘗試從 teams.home/away.score 取分，再 fallback 到 linescore
            h_runs = hd.get("score")
            a_runs = ad.get("score")
            if h_runs is None:
                ls = game.get("linescore",{})
                h_runs = ls.get("teams",{}).get("home",{}).get("runs")
                a_runs = ls.get("teams",{}).get("away",{}).get("runs")
            if h_runs is None: continue
            try:
                if hn: team_runs.setdefault(hn,[]).append(float(h_runs))
                if an: team_runs.setdefault(an,[]).append(float(a_runs))
            except (TypeError, ValueError):
                continue
    form = {}
    for team, runs_list in team_runs.items():
        last10 = runs_list[-10:]   # 取最近10場
        if len(last10) >= 5:       # 至少5場才有統計意義
            form[team] = round(sum(last10)/len(last10), 2)
    _SCORING_FORM = form
    log.info("Scoring form cached: %d teams", len(form))

def fetch_series_momentum():
    """最近3天各系列賽勝敗紀錄 → 偵測連敗球隊（如太空人連輸水手）"""
    global _SERIES_MOMENTUM
    momentum = {}
    for days_ago in range(1, 4):
        d = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()
        data = safe_get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId":1,"date":d,"gameType":"R",
                    "fields":"dates,games,teams,home,away,team,id,name,score,status,detailedState"},
            timeout=10,
        )
        if not data: continue
        for de in data.get("dates",[]):
            for game in de.get("games",[]):
                status = game.get("status",{}).get("detailedState","")
                if "Final" not in status and "Completed" not in status: continue
                hd = game.get("teams",{}).get("home",{})
                ad = game.get("teams",{}).get("away",{})
                hn = MLB_TEAM_ID.get(hd.get("team",{}).get("id")) or norm_team(hd.get("team",{}).get("name",""))
                an = MLB_TEAM_ID.get(ad.get("team",{}).get("id")) or norm_team(ad.get("team",{}).get("name",""))
                if not hn or not an: continue
                try:
                    h_score = int(hd.get("score") or 0)
                    a_score = int(ad.get("score") or 0)
                except (TypeError, ValueError):
                    continue
                key = tuple(sorted([hn, an]))
                momentum.setdefault(key, []).append((hn, h_score > a_score))
    _SERIES_MOMENTUM = momentum
    count = sum(len(v) for v in momentum.values())
    log.info("Series momentum: %d matchups / %d games", len(momentum), count)

def build_recent_era_cache(pitchers_dict):
    global _RECENT_ERA
    cache = {}
    seen  = set()
    for (home, away), info in pitchers_dict.items():
        for key, full in [(info.get("home_pitcher"), info.get("home_name")),
                          (info.get("away_pitcher"), info.get("away_name"))]:
            if not key or key in seen: continue
            if not full or full == "TBD": continue
            seen.add(key)
            # 用 fullName 搜尋 playerId
            data = safe_get(
                "https://statsapi.mlb.com/api/v1/people/search",
                params={"names": full, "sportId": 1},
                timeout=8,
            )
            if not data: continue
            for p in data.get("people", []):
                if _name_to_key(p.get("fullName","")) == key:
                    pid = p.get("id")
                    if pid:
                        recent = _fetch_recent_era(pid)
                        if recent is not None:
                            cache[key] = recent
                            log.info("Recent ERA %s: %.2f (season: %.2f)",
                                     key, recent, PITCHER_ERA.get(key,4.80))
                    break
    _RECENT_ERA = cache
    log.info("Recent ERA cached: %d pitchers", len(cache))


# ══════════════════════════════════════════════
# ★ 天氣（選用）
# ══════════════════════════════════════════════

def fetch_weather(team, game_dt):
    if not WEATHER_API_KEY: return 1.0
    coords = PARK_COORDS.get(team)
    if not coords: return 1.0
    ck = "%s_%s" % (team, game_dt.strftime("%Y%m%d%H"))
    if ck in _WEATHER_CACHE: return _WEATHER_CACHE[ck]
    try:
        lat, lon = coords
        data = safe_get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat":lat,"lon":lon,"appid":WEATHER_API_KEY,"units":"metric"},
            timeout=8,
        )
        if not data: return 1.0
        wind  = data.get("wind",{}).get("speed", 0)
        temp  = data.get("main",{}).get("temp", 20)
        cond  = data.get("weather",[{}])[0].get("main","").lower()
        wf    = 1.0 + max(0, wind-8) * 0.008
        tf    = max(0.93, min(1.07, 1.0 + (temp-20)*0.004))
        rf    = 0.97 if "rain" in cond or "drizzle" in cond else 1.0
        factor = round(wf * tf * rf, 3)
        _WEATHER_CACHE[ck] = factor
        log.info("Weather %s: %.3f (wind=%.1f temp=%.0f %s)", team, factor, wind, temp, cond)
        return factor
    except Exception as e:
        log.debug("Weather failed: %s", e)
        return 1.0


# ══════════════════════════════════════════════
# ESPN 即時戰績
# ══════════════════════════════════════════════

def fetch_espn_ratings():
    global _ESPN_RATINGS
    data = None
    for url in ["https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings",
                "https://site.web.api.espn.com/apis/v2/sports/baseball/mlb/standings"]:
        data = safe_get(url, timeout=15)
        if data: break
    if not data:
        log.warning("ESPN failed"); return False
    def to_f(s):
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
                abbr  = e.get("team",{}).get("abbreviation","").lower()
                short = ESPN_ABBR.get(abbr)
                if not short: continue
                base  = BASE.get(short, DEF_BASE)
                st    = {(s.get("name") or s.get("shortDisplayName","")): to_f(s)
                         for s in e.get("stats",[]) if s.get("name") or s.get("shortDisplayName")}
                w = st.get("wins", st.get("W", st.get("w",0)))
                l = st.get("losses", st.get("L", st.get("l",0)))
                t = w + l
                if t < 5:
                    ratings[short] = {"off":base["off"],"def":base["def"],"form":0.0,"games":t}
                    continue
                rs = st.get("pointsFor", st.get("RS", st.get("runsScored",0)))
                ra = st.get("pointsAgainst", st.get("RA", st.get("runsAllowed",0)))
                wp = w / t
                if rs > 10 and ra > 10:
                    off_e = round(min(rs/t, 5.8), 2)
                    def_e = round(max(ra/t, 3.0), 2)
                else:
                    off_e = round(min(base["off"]+(wp-0.5)*0.5, 5.8), 2)
                    def_e = round(max(base["def"]-(wp-0.5)*0.5, 3.0), 2)
                alpha = min(t/30, ESPN_ALPHA_MAX)
                # L10 近期形態（若 ESPN 有提供）
                try:
                    l10w = int(st.get("last10Wins", st.get("L10W", st.get("vsLast10Wins", 0))) or 0)
                    l10l = int(st.get("last10Losses", st.get("L10L", st.get("vsLast10Losses", 0))) or 0)
                    l10 = l10w + l10l
                    if l10 >= 8:
                        l10_wp = l10w / l10
                        form = round((wp-0.5)*0.10 + (l10_wp-0.5)*0.25, 3)
                    else:
                        form = round((wp-0.5)*0.20, 3)
                except Exception:
                    form = round((wp-0.5)*0.20, 3)
                ratings[short] = {
                    "off":  round(off_e*alpha + base["off"]*(1-alpha), 2),
                    "def":  round(def_e*alpha + base["def"]*(1-alpha), 2),
                    "form": form,
                    "games": t,
                }
    except Exception as e:
        log.warning("ESPN parse: %s", e)
    if ratings:
        _ESPN_RATINGS = ratings
        log.info("ESPN ratings: %d teams", len(ratings))
        return True
    return False


# ══════════════════════════════════════════════
# 傷兵
# ══════════════════════════════════════════════

def fetch_injury_list():
    global _DYN_OUT, _DYN_LTD
    try:
        r = requests.get(
            "https://www.rotowire.com/baseball/injury-report.php",
            headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
        )
        r.raise_for_status()
        text = r.text.lower()
        out_kw  = ["ruled out","will not play","is out","60-day il","tommy john","season-ending"]
        ltd_kw  = ["day-to-day","questionable","limited","15-day il","10-day il"]
        skip_kw = ["probable","available","activated","reinstated"]
        dyn_out, dyn_ltd = {}, {}
        for short, players in ROSTER.items():
            for p in players:
                if p not in text: continue
                idx = text.find(p)
                ctx = text[max(0,idx-80):idx+200]
                if any(s in ctx for s in skip_kw): continue
                if any(s in ctx for s in out_kw):
                    dyn_out.setdefault(short,[]).append(p)
                elif any(s in ctx for s in ltd_kw):
                    dyn_ltd.setdefault(short,[]).append((p, _player_tier(p)))
        for short, players in OUT_STATIC.items():
            existing = set(dyn_out.get(short,[]))
            for p in players:
                if p not in existing: dyn_out.setdefault(short,[]).append(p)
        total = sum(len(v) for v in dyn_out.values()) + sum(len(v) for v in dyn_ltd.values())
        log.info("RotoWire: %d injuries", total)
        if total > 0:
            _DYN_OUT, _DYN_LTD = dyn_out, dyn_ltd
            return "rotowire"
    except Exception as e:
        log.warning("RotoWire failed: %s", e)
    log.warning("Using static injury list")
    _DYN_OUT = {k: list(v) for k,v in OUT_STATIC.items()}
    _DYN_LTD = {k: list(v) for k,v in LTD_STATIC.items()}
    return "static"


# ══════════════════════════════════════════════
# 先發投手
# ══════════════════════════════════════════════

def fetch_probable_pitchers():
    today = datetime.date.today().isoformat()
    data = safe_get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={"sportId":1,"date":today,"hydrate":"probablePitcher(note),team",
                "fields":"dates,games,gamePk,teams,home,away,probablePitcher,fullName,id,team,name"},
    )
    result = {}
    if not data: return result
    for de in data.get("dates",[]):
        for game in de.get("games",[]):
            hd  = game.get("teams",{}).get("home",{})
            ad  = game.get("teams",{}).get("away",{})
            hs  = MLB_TEAM_ID.get(hd.get("team",{}).get("id")) or norm_team(hd.get("team",{}).get("name",""))
            as_ = MLB_TEAM_ID.get(ad.get("team",{}).get("id")) or norm_team(ad.get("team",{}).get("name",""))
            hp  = hd.get("probablePitcher",{}).get("fullName")
            ap  = ad.get("probablePitcher",{}).get("fullName")
            if hs and as_:
                result[(hs, as_)] = {
                    "home_pitcher":_name_to_key(hp),"away_pitcher":_name_to_key(ap),
                    "home_name":hp or "TBD","away_name":ap or "TBD",
                }
                log.info("SP: %s vs %s | H=%s A=%s", hs, as_, _name_to_key(hp), _name_to_key(ap))
    log.info("Pitchers resolved: %d games", len(result))
    return result


# ══════════════════════════════════════════════
# Odds API
# ══════════════════════════════════════════════

def fetch_odds():
    if not ODDS_API_KEY: log.error("ODDS_API_KEY not set"); return []
    data = safe_get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={"apiKey":ODDS_API_KEY,"regions":"us","markets":"h2h,spreads,totals",
                "oddsFormat":"decimal","dateFormat":"iso"},
    )
    if not data: return []
    log.info("Odds: %d games", len(data))
    return data


# ══════════════════════════════════════════════
# Gist
# ══════════════════════════════════════════════

def _purge(records):
    cutoff = (datetime.datetime.utcnow()-datetime.timedelta(days=HIST_TTL)).strftime("%Y-%m-%d")
    return [r for r in records if r.get("date","9999") >= cutoff]

def _gh_h(): return {"Authorization":"token "+GH_TOKEN,"Content-Type":"application/json"}

def _find_gid(gists):
    old = {"mlb_bot_v107_history","mlb_bot_v108_history","mlb_bot_v109_history"}
    new_id = old_id = None
    for g in gists:
        d = g.get("description","")
        if d == GIST_DESC: new_id = g["id"]
        elif d in old and not old_id: old_id = g["id"]
    return new_id or old_id

def load_hist():
    if not GH_TOKEN: return []
    h = _gh_h()
    try:
        r = requests.get("https://api.github.com/gists", headers=h, timeout=15)
        r.raise_for_status(); gists = r.json()
    except Exception as e:
        log.warning("load_hist: %s", e); return []
    gid = _find_gid(gists)
    if not gid: return []
    try:
        detail = requests.get("https://api.github.com/gists/"+gid, headers=h, timeout=15).json()
        raw    = list(detail["files"].values())[0]["raw_url"]
        records = requests.get(raw, timeout=15).json()
        log.info("Hist loaded: %d records", len(records))
        return _purge(records)
    except Exception as e:
        log.warning("load_hist parse: %s", e); return []

def save_hist(records):
    if not GH_TOKEN: return
    records = _purge(records)
    h = _gh_h()
    body = json.dumps(records, ensure_ascii=False, indent=2)
    try:
        r = requests.get("https://api.github.com/gists", headers=h, timeout=15)
        r.raise_for_status(); gists = r.json()
    except Exception as e:
        log.warning("save_hist: %s", e); return
    gid = _find_gid(gists)
    pl  = {"description":GIST_DESC,"public":False,"files":{"history.json":{"content":body}}}
    for attempt in range(1,4):
        try:
            if gid:
                requests.patch("https://api.github.com/gists/"+gid, headers=h, json=pl, timeout=10).raise_for_status()
            else:
                requests.post("https://api.github.com/gists", headers=h, json=pl, timeout=10).raise_for_status()
            log.info("Hist saved (%d records)", len(records)); return
        except Exception as e:
            log.warning("save_hist %d/3: %s", attempt, e)


# ══════════════════════════════════════════════
# ★ 模型核心
# ══════════════════════════════════════════════

def get_rating(team):
    if team in _ESPN_RATINGS: return _ESPN_RATINGS[team]
    b = BASE.get(team, DEF_BASE)
    return {"off":b["off"],"def":b["def"],"form":0.0,"games":0}

def injury_penalty(team):
    t = team.lower()
    penalty = 0.0
    # OUT 懲罰依球員等級：S=王牌先發/明星野手，A=主力，B=一般
    _OUT_PEN = {"S": 0.28, "A": 0.16, "B": 0.06}
    for p in _DYN_OUT.get(t, []):
        penalty += _OUT_PEN.get(_player_tier(p), 0.06)
    for item in _DYN_LTD.get(t, []):
        tier = item[1] if isinstance(item, tuple) else "B"
        penalty += LT_PEN.get(tier, 0.4) * 0.15
    return round(min(penalty, 1.5), 3)

def get_pitcher_era(key):
    if not key: return LEAGUE_ERA + 0.60
    k = key.lower().strip()
    recent = _RECENT_ERA.get(k)
    season = PITCHER_ERA.get(k, None)
    if recent is not None and season is not None:
        # 小樣本偏差修正：極低/極高 ERA 加重賽季權重
        if recent < 1.50:
            w_r, w_s = 0.40, 0.60   # 極低→降低近期比重，避免過度樂觀
        elif recent > 7.00:
            w_r, w_s = 0.50, 0.50   # 極高→各半，避免過度悲觀
        else:
            w_r, w_s = SP_RECENT_W, SP_SEASON_W
        return round(recent * w_r + season * w_s, 2)
    if recent is not None:
        # 無賽季ERA：向聯盟平均回歸（防止小樣本過度依賴）
        if recent < 1.50:
            return round(recent * 0.45 + LEAGUE_ERA * 0.55, 2)  # 極低→強烈回歸
        elif recent > 7.00:
            return round(recent * 0.50 + LEAGUE_ERA * 0.50, 2)  # 極高→回歸
        return round(recent * 0.65 + LEAGUE_ERA * 0.35, 2)      # 正常→輕度回歸
    return season if season is not None else LEAGUE_ERA + 0.60

def era_adj(key):
    era = get_pitcher_era(key)
    delta = era - LEAGUE_ERA
    # 非線性：差距越大影響越顯著（|delta|^1.08），最大 ±2.0
    scaled = math.copysign(min(abs(delta) ** 1.08, 2.0) * 0.34, delta)
    return round(scaled, 3)

def bullpen_adj(team):
    era = BULLPEN_ERA.get(team.lower(), LEAGUE_BULL_ERA)
    return round((era - LEAGUE_BULL_ERA) * 0.20, 3)

def pitcher_confidence(key):
    era = get_pitcher_era(key)
    if era <= 2.5:   return 1.0
    elif era <= 3.2: return 0.92
    elif era <= 4.0: return 0.82
    elif era <= 4.5: return 0.72
    else:            return 0.62

def total_confidence(pure_total, market_total):
    gap = abs(pure_total - market_total)
    if gap < GAP1:   return 1.00
    elif gap < GAP2: return 0.90
    elif gap < GAP3: return 0.78
    else:            return 0.65

def norm_cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def win_prob_from_margin(margin, std=STD):
    return max(0.05, min(0.95, norm_cdf(margin/std)))

def predict(home, away, home_sp, away_sp, market_total=8.5, game_dt=None):
    hr = get_rating(home)
    ar = get_rating(away)
    games = hr.get("games", 0)

    # ① 先發 ERA（近期+賽季融合）
    h_sp_adj = era_adj(home_sp)
    a_sp_adj = era_adj(away_sp)

    # ② 動態主場優勢
    ha = 0.07 + hr.get("form", 0.0) * 0.3

    # ③ 基礎期望得分
    h_exp = hr["off"] + a_sp_adj + ha
    a_exp = ar["off"] + h_sp_adj

    # ④ 傷兵
    h_exp -= injury_penalty(home) * 0.4
    a_exp -= injury_penalty(away) * 0.4

    # ⑤ ★ 牛棚（對手牛棚好 → 己方後段得分降低）
    h_exp -= bullpen_adj(away)
    a_exp -= bullpen_adj(home)

    # ⑥ ★ 球場係數
    pf = PARK_FACTOR.get(home.lower(), 1.0)
    h_exp *= pf
    a_exp *= pf

    # ⑦ ★ 天氣（選用）
    if game_dt and WEATHER_API_KEY:
        wf = fetch_weather(home, game_dt)
        h_exp *= wf; a_exp *= wf

    # ⑧ ★ 球隊防守品質（ESPN 實際失分率 vs 聯盟均值）
    # 防守好的主隊→客隊得分減少；防守差的主隊→客隊得分增加
    if hr.get("games", 0) >= 5:
        a_exp -= (LEAGUE_DEF_AVG - hr.get("def", LEAGUE_DEF_AVG)) * 0.08
    if ar.get("games", 0) >= 5:
        h_exp -= (LEAGUE_DEF_AVG - ar.get("def", LEAGUE_DEF_AVG)) * 0.08

    # ⑨ ★ 客隊近期狀態對進攻的影響（熱門客隊客場也能多得分）
    a_exp += ar.get("form", 0.0) * 0.15

    # ⑩ ★ 近期得分形態（最近10場均值 vs ESPN整季均值）
    # 近期打線火熱/低迷 → 調整期望得分（權重20%）
    if home in _SCORING_FORM and _SCORING_FORM[home] > 0:
        h_exp += (_SCORING_FORM[home] - hr["off"]) * 0.20
    if away in _SCORING_FORM and _SCORING_FORM[away] > 0:
        a_exp += (_SCORING_FORM[away] - ar["off"]) * 0.20

    # ⑪ ★ 連續出賽疲勞（昨天出賽 → 今天體力稍遜 -0.06 runs）
    if home in _B2B_TEAMS: h_exp -= 0.06
    if away in _B2B_TEAMS: a_exp -= 0.06

    # ⑫ ★ 系列賽動能：近3天同一對陣的連勝/連敗
    # 連敗隊：進攻 -0.12、信心 ×0.93（打線低迷、投手輪轉劣勢）
    series_conf_mult = 1.0
    series_key  = tuple(sorted([home, away]))
    series_hist = _SERIES_MOMENTUM.get(series_key, [])
    if len(series_hist) >= 2:
        # 從主場角度計算：home 隊在系列賽中贏了幾場
        h_series_w = sum(
            1 for (ht, hw) in series_hist
            if (ht == home and hw) or (ht != home and not hw)
        )
        a_series_w = len(series_hist) - h_series_w
        if h_series_w == 0:    # home 隊系列賽全輸 → 動能不利主場
            h_exp  -= 0.12
            series_conf_mult = 0.93
            log.debug("Series: %s swept so far (%d games)", home, len(series_hist))
        elif a_series_w == 0:  # away 隊系列賽全輸 → 動能不利客場
            a_exp  -= 0.12
            series_conf_mult = 0.93
            log.debug("Series: %s swept so far (%d games)", away, len(series_hist))

    h_exp = max(2.5, h_exp)
    a_exp = max(2.5, a_exp)
    margin = h_exp - a_exp

    dyn_std = STD + max(0, (10-games)/10) * 0.15
    model_win_p = win_prob_from_margin(margin, dyn_std)
    # ★ 勝率上限 72%：MLB單場勝率現實上限（職棒強隊對弱隊約65-68%）
    model_win_p = min(model_win_p, 0.72)

    pure_total  = h_exp + a_exp
    model_total = round(pure_total*0.30 + market_total*0.70, 2)
    conf = total_confidence(pure_total, market_total)
    conf *= (pitcher_confidence(home_sp) * pitcher_confidence(away_sp)) ** 0.5
    # TBD 先發：缺乏先發資訊大幅降低信心
    if not home_sp: conf *= 0.86
    if not away_sp: conf *= 0.86
    # 系列賽連敗信心折扣
    conf *= series_conf_mult
    # 早賽季（<5 場）：ESPN 數據不可靠，限制信心上限
    if games < 5: conf = min(conf, 0.85)

    return {
        "home_win_prob": round(model_win_p, 4),
        "away_win_prob": round(1-model_win_p, 4),
        "model_total":   model_total,
        "pure_total":    round(pure_total, 2),
        "conf_factor":   round(max(0.40, min(1.0, conf)), 3),
        "h_expected":    round(h_exp, 2),
        "a_expected":    round(a_exp, 2),
        "margin":        round(margin, 3),
        "park_factor":   pf,
        "dyn_std":       round(dyn_std, 3),  # 供讓分概率計算使用
    }

def runline_prob(margin, spread, dyn_std):
    """P(主場隊蓋掉 -spread 讓分，即贏分差 > spread)"""
    return max(0.02, min(0.98, norm_cdf((margin - spread) / dyn_std)))

def over_prob(pure_total, line, std=TOTAL_STD):
    """P(兩隊合計得分 > 大小分線 line)"""
    return max(0.02, min(0.98, norm_cdf((pure_total - line) / std)))

def kelly_stake(edge, model_p, price, conf=1.0):
    if edge<=0 or price<=1.0: return 0.0
    b = price-1.0
    raw_k = (b*model_p - (1-model_p)) / b
    if raw_k<=0: return 0.0
    dyn_k = max(0.05, min(0.18, KELLY*conf))
    return round(max(0.0, min(KELLY_MAX, dyn_k*raw_k*BANK)), 1)

def calc_perf(hist):
    settled = [r for r in hist if r.get("result") in ("W","L")]
    wins = sum(1 for r in settled if r["result"]=="W")
    return len(settled), wins, wins/len(settled)*100 if settled else 0.0

def calc_pnl(hist):
    """計算有記錄 stake 的已結算注單累積損益"""
    total_in = total_pnl = 0.0
    for r in hist:
        if r.get("result") not in ("W","L"): continue
        stake = r.get("stake")
        if not stake: continue
        price = r.get("price", 0)
        total_in  += stake
        total_pnl += stake * (price - 1) if r["result"] == "W" else -stake
    return round(total_in, 1), round(total_pnl, 1)


# ══════════════════════════════════════════════
# Discord
# ══════════════════════════════════════════════

def send(content):
    if not DISCORD_WEBHOOK: print(content); return
    LIMIT = 1900
    chunks, cur = [], ""
    for line in content.split("\n"):
        if len(cur)+len(line)+1>LIMIT: chunks.append(cur); cur=line+"\n"
        else: cur+=line+"\n"
    if cur.strip(): chunks.append(cur)
    total = len(chunks)
    for i, chunk in enumerate(chunks,1):
        label = "(%d/%d)\n%s"%(i,total,chunk) if total>1 else chunk
        try: requests.post(DISCORD_WEBHOOK, json={"content":label}, timeout=10).raise_for_status()
        except Exception as e: log.error("Discord %d: %s", i, e)


# ══════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════

def run():
    now_tw    = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    today_str = now_tw.strftime("%Y-%m-%d")
    log.info("TW time: %s", now_tw.strftime("%Y-%m-%d %H:%M"))
    official = (now_tw.hour >= 23 or now_tw.hour < 7)  # 23:30排程 + 深夜補跑皆為正式

    if not ODDS_API_KEY: log.error("ODDS_API_KEY not set"); return

    hist      = load_hist()
    espn_ok   = fetch_espn_ratings()
    il_src    = fetch_injury_list()
    pitchers  = fetch_probable_pitchers()
    if pitchers:
        try: build_recent_era_cache(pitchers)
        except Exception as e: log.warning("Recent ERA failed: %s", e)
    try: fetch_b2b_teams()
    except Exception as e: log.warning("B2B teams failed: %s", e)
    try: fetch_recent_scoring()
    except Exception as e: log.warning("Recent scoring failed: %s", e)
    try: fetch_series_momentum()
    except Exception as e: log.warning("Series momentum failed: %s", e)
    odds_data = fetch_odds()
    if not odds_data: log.error("No odds data"); return

    season_start = "%d-03-25" % datetime.date.today().year
    season_games = sum(1 for r in hist if r.get("date","") >= season_start)
    # 已寫入 Gist 的場次集合（以比賽台灣日期 + 主客隊為 key，避免重複推薦）
    hist_game_keys = {(r.get("home"), r.get("away"), r.get("date")) for r in hist}
    picks, today_records = [], []

    for game in odds_data:
        if game.get("sport_key") != "baseball_mlb": continue
        commence = game.get("commence_time","")
        try:
            game_utc      = datetime.datetime.fromisoformat(commence.replace("Z","+00:00"))
            game_tw       = game_utc + datetime.timedelta(hours=8)
            game_date_str = game_tw.strftime("%Y-%m-%d")
            game_time_str = game_tw.strftime("%H:%M")
            game_dt       = game_tw
            # 跳過已開打超過 30 分鐘的比賽
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if game_utc < now_utc - datetime.timedelta(minutes=30): continue
        except Exception:
            game_date_str = today_str; game_time_str = commence[:16]; game_dt = None

        home = norm_team(game.get("home_team",""))
        away = norm_team(game.get("away_team",""))
        if home not in BASE or away not in BASE: continue

        sp_info  = pitchers.get((home,away),{})
        home_sp  = sp_info.get("home_pitcher")
        away_sp  = sp_info.get("away_pitcher")
        bms      = game.get("bookmakers",[])
        if not bms: continue

        # ── 收集所有市場最優/共識賠率 ──────────────────────────
        home_price=away_price=home_book=away_book=None
        rl_lines={}  # {spread_size: {h_price,h_book,h_all,a_price,a_book,a_all,h_pts}}
        over_price=under_price=over_book=under_book=None
        market_total=8.5
        con_h_prices=[]; con_a_prices=[]
        con_over=[]; con_under=[]
        for bm in bms:
            bk_name=bm.get("title","?")
            for mkt in bm.get("markets",[]):
                mk=mkt.get("key")
                if mk=="h2h":
                    for o in mkt.get("outcomes",[]):
                        t=norm_team(o.get("name","")); p=o.get("price",0)
                        if t==home:
                            con_h_prices.append(p)
                            if home_price is None or p>home_price: home_price=p; home_book=bk_name
                        elif t==away:
                            con_a_prices.append(p)
                            if away_price is None or p>away_price: away_price=p; away_book=bk_name
                elif mk in ("spreads","alternate_spreads"):
                    for o in mkt.get("outcomes",[]):
                        t=norm_team(o.get("name","")); p=o.get("price",0)
                        try: pts=float(o.get("point",0))
                        except (ValueError,TypeError): continue
                        if p<=0 or pts==0: continue
                        s=round(abs(pts),1)
                        if s not in rl_lines:
                            rl_lines[s]={"h_price":None,"h_book":None,"h_all":[],
                                         "a_price":None,"a_book":None,"a_all":[],"h_pts":None}
                        e=rl_lines[s]
                        if t==home:
                            e["h_pts"]=pts; e["h_all"].append(p)
                            if e["h_price"] is None or p>e["h_price"]: e["h_price"]=p; e["h_book"]=bk_name
                        elif t==away:
                            e["a_all"].append(p)
                            if e["a_price"] is None or p>e["a_price"]: e["a_price"]=p; e["a_book"]=bk_name
                elif mk=="totals":
                    for o in mkt.get("outcomes",[]):
                        pt=o.get("point"); p=o.get("price",0); nm=o.get("name","")
                        if pt is not None:
                            try: market_total=float(pt)
                            except (ValueError, TypeError): pass
                        if nm=="Over":
                            con_over.append(p)
                            if over_price is None or p>over_price: over_price=p; over_book=bk_name
                        elif nm=="Under":
                            con_under.append(p)
                            if under_price is None or p>under_price: under_price=p; under_book=bk_name
        if home_price is None or away_price is None: continue

        con_h = round(sum(con_h_prices)/len(con_h_prices),3) if con_h_prices else home_price
        con_a = round(sum(con_a_prices)/len(con_a_prices),3) if con_a_prices else away_price
        if con_h <= 0 or con_a <= 0: continue  # guard: 防止除以零

        con_ov_p   = round(sum(con_over)/len(con_over),3) if con_over else over_price
        con_un_p   = round(sum(con_under)/len(con_under),3) if con_under else under_price

        # ★ 書商數量信心乘數：書商越多，市場共識越可靠
        n_bks = len(bms)
        book_conf = 1.00 if n_bks >= 10 else (0.95 if n_bks >= 6 else 0.90)

        # ★ 市場 vig 信心：vig（書商抽水）越低 → 市場定價越有效率 → 信心越高
        vig = (1.0/con_h + 1.0/con_a) - 1.0
        vig_conf = 1.00 if vig < 0.04 else (0.95 if vig < 0.06 else 0.90)
        book_conf = round(min(book_conf * vig_conf, 1.0), 3)

        pred    = predict(home,away,home_sp,away_sp,market_total=market_total,game_dt=game_dt)
        margin  = pred["margin"]
        dyn_std = pred["dyn_std"]
        h_model = pred["home_win_prob"]; a_model = pred["away_win_prob"]
        conf    = pred["conf_factor"] * book_conf

        # 獨贏市場混合概率（用於 blend 過濾）
        inv_sum  = 1/con_h + 1/con_a
        h_mkt_nv = round((1/con_h)/inv_sum,4); a_mkt_nv = round((1/con_a)/inv_sum,4)
        h_blend  = MOD_W*h_model+MKT_W*h_mkt_nv; a_blend = MOD_W*a_model+MKT_W*a_mkt_nv

        # ── ★ 大小分概率（Over/Under）────────────────────────
        p_over  = over_prob(pred["pure_total"], market_total)
        p_under = 1.0 - p_over

        # ── ★ 建立所有候選注單並選最優 ──────────────────────
        BET_ML="獨贏"; BET_RL="讓分"; BET_TOT="大小分"
        candidates=[]
        if home_price: candidates.append({"btype":BET_ML,"bside":"home","bteam":home,"bp":home_price,
            "bk":home_book,"model_p":h_model,"edge_min":EDGE_MIN,"blend_p":h_blend,"con_p":con_h,
            "conf_mult":1.00,"label":"獨贏","rl_inv":None,"rl_s":None})
        if away_price: candidates.append({"btype":BET_ML,"bside":"away","bteam":away,"bp":away_price,
            "bk":away_book,"model_p":a_model,"edge_min":EDGE_MIN,"blend_p":a_blend,"con_p":con_a,
            "conf_mult":1.00,"label":"獨贏","rl_inv":None,"rl_s":None})
        # RL candidates：每個讓分數（1.5/2.5/…）都產生主客兩個候選
        for s,e in sorted(rl_lines.items()):
            hp=e["h_price"]; ap=e["a_price"]
            if hp is None or ap is None or hp<=0 or ap<=0: continue
            # ★ 至少 2 家書商才採用讓分市場（流動性不足不推薦）
            if len(e["h_all"]) < 2 or len(e["a_all"]) < 2: continue
            ch=round(sum(e["h_all"])/len(e["h_all"]),3) if e["h_all"] else hp
            ca=round(sum(e["a_all"])/len(e["a_all"]),3) if e["a_all"] else ap
            h_pts=e.get("h_pts") or -s
            if h_pts<=0:  # home team gives points (-s)
                p_h=runline_prob(margin,s,dyn_std); h_lbl="-%g"%s; a_lbl="+%g"%s
            else:         # home team receives points (+s)
                p_h=runline_prob(margin,-s,dyn_std); h_lbl="+%g"%s; a_lbl="-%g"%s
            p_a=1.0-p_h
            rl_inv_val=(1/ch+1/ca) if (ch>0 and ca>0) else 1.0
            candidates.append({"btype":BET_RL,"bside":"rl_h","bteam":home,"bp":hp,"bk":e["h_book"],
                "model_p":p_h,"edge_min":EDGE_MIN_RL,"blend_p":None,"con_p":ch,
                "conf_mult":0.90,"label":h_lbl,"rl_inv":rl_inv_val,"rl_s":s})
            candidates.append({"btype":BET_RL,"bside":"rl_a","bteam":away,"bp":ap,"bk":e["a_book"],
                "model_p":p_a,"edge_min":EDGE_MIN_RL,"blend_p":None,"con_p":ca,
                "conf_mult":0.90,"label":a_lbl,"rl_inv":rl_inv_val,"rl_s":s})
        # ★ 大小分：至少 2 家書商才採用
        if over_price and con_ov_p and len(con_over)>=2:
            candidates.append({"btype":BET_TOT,"bside":"over","bteam":"over","bp":over_price,
                "bk":over_book,"model_p":p_over,"edge_min":EDGE_MIN_TOT,"blend_p":None,"con_p":con_ov_p,
                "conf_mult":0.88,"label":"OVER","rl_inv":None,"rl_s":None})
        if under_price and con_un_p and len(con_under)>=2:
            candidates.append({"btype":BET_TOT,"bside":"under","bteam":"under","bp":under_price,
                "bk":under_book,"model_p":p_under,"edge_min":EDGE_MIN_TOT,"blend_p":None,"con_p":con_un_p,
                "conf_mult":0.88,"label":"UNDER","rl_inv":None,"rl_s":None})

        best_pick=None
        for c in candidates:
            btype=c["btype"]; bp=c["bp"]; con_p=c["con_p"]; model_p=c["model_p"]
            blend_p=c["blend_p"]; edge_min=c["edge_min"]
            if bp is None or bp<=0 or con_p is None or con_p<=0: continue
            bet_conf = conf*c["conf_mult"]
            raw_edge = model_p - 1/bp
            if raw_edge*bet_conf<edge_min: continue
            if bp<MIN_P or bp>MAX_P: continue
            if btype==BET_ML and (blend_p is None or blend_p<0.52): continue
            if btype!=BET_ML and model_p<0.55: continue
            if bet_conf<0.60: continue
            stake=kelly_stake(raw_edge,model_p,bp,conf=bet_conf)
            if stake<KELLY_MIN: continue
            score=raw_edge*bet_conf
            if best_pick is None or score>best_pick["score"]:
                best_pick={**c,"raw_edge":raw_edge,"bet_conf":bet_conf,"stake":stake,"score":score}

        if best_pick is None: continue

        # 已寫入 Gist → 跳過，避免同一場比賽重複出現在報告中
        if (home, away, game_date_str) in hist_game_keys: continue

        # ── 解包最優注單 ──────────────────────────────────────
        btype    = best_pick["btype"]
        bside    = best_pick["bside"]
        bteam    = best_pick["bteam"]
        bp       = best_pick["bp"]
        bk       = best_pick["bk"]
        model_p  = best_pick["model_p"]
        raw_edge = best_pick["raw_edge"]
        bet_conf = best_pick["bet_conf"]
        con_p    = best_pick["con_p"]
        stake    = best_pick["stake"]

        if raw_edge>=0.18 and bet_conf>=0.88:   tier="💎 頂級"
        elif raw_edge>=0.15 and bet_conf>=0.80: tier="🔥 強力"
        else:                                   tier="⭐ 穩定"

        acn=CN.get(away,away); hcn=CN.get(home,home)
        h_sp_n = sp_info.get("home_name","TBD") if sp_info else "TBD"
        a_sp_n = sp_info.get("away_name","TBD") if sp_info else "TBD"
        h_era=get_pitcher_era(home_sp); a_era=get_pitcher_era(away_sp)
        h_tag=("(近期ERA%.2f)"%h_era if home_sp in _RECENT_ERA else "(ERA%.2f)"%h_era) if home_sp else ""
        a_tag=("(近期ERA%.2f)"%a_era if away_sp in _RECENT_ERA else "(ERA%.2f)"%a_era) if away_sp else ""
        h_sp_str=h_sp_n+h_tag; a_sp_str=a_sp_n+a_tag

        stability = model_p * bet_conf
        stab_str  = "%.0f%%" % (stability * 100)
        warn_note = " ⚠️" if bet_conf < 0.75 else ""
        pf_note=" 🏟️PF%.2f"%pred["park_factor"] if abs(pred["park_factor"]-1.0)>0.05 else ""
        ou_diff=pred["model_total"]-market_total
        if   ou_diff>1.5:  ou_str="OVER偏向(%.1f/%.1f)"%(pred["model_total"],market_total)
        elif ou_diff<-1.5: ou_str="UNDER偏向(%.1f/%.1f)"%(pred["model_total"],market_total)
        else:              ou_str="大小分中性(%.1f/%.1f)"%(pred["model_total"],market_total)

        # 依注單類型產生推薦描述與統計行
        if btype==BET_ML:
            bcn=CN.get(bteam,bteam)
            bet_desc="`%s 獨贏` @ **%.2f** (%s)"%(bcn,bp,bk)
            stats_ln="> 共識賠率: %.2f | 市場勝率: %.1f%% | 模型勝率: %.1f%%"%(con_p,(1/bp)*100,model_p*100)
            mkt_tag=""
        elif btype==BET_RL:
            bcn=CN.get(bteam,bteam)
            pts_str=best_pick["label"]   # e.g. "-1.5", "+2.5"
            rl_inv_val=best_pick.get("rl_inv") or 1.0
            mkt_rl_p=(1/con_p)/rl_inv_val if rl_inv_val>0 else 1/con_p
            bet_desc="`%s 讓分(%s)` @ **%.2f** (%s)"%(bcn,pts_str,bp,bk)
            stats_ln="> 共識賠率: %.2f | 讓分勝率: %.1f%% | 市場隱含: %.1f%%"%(con_p,model_p*100,mkt_rl_p*100)
            mkt_tag=" [讓分%s]"%pts_str
        else:  # BET_TOT
            ov_un="OVER" if bside=="over" else "UNDER"
            tot_inv=(1/con_ov_p+1/con_un_p) if (con_ov_p and con_un_p) else 1.0
            mkt_tot_p=(1/con_p)/tot_inv if tot_inv>0 else 1/con_p
            bet_desc="`%s %.1f` @ **%.2f** (%s)"%(ov_un,market_total,bp,bk)
            stats_ln="> 共識賠率: %.2f | 模型總分: %.1f | 市場隱含: %.1f%%"%(con_p,pred["pure_total"],mkt_tot_p*100)
            mkt_tag=" [大小分]"
            ou_str=""  # 大小分注單不重複顯示方向

        h_out,h_ltd=get_star_injuries(home); a_out,a_ltd=get_star_injuries(away)
        inj_lines=[]
        out_p=[]
        if h_out: out_p.append("%s: %s"%(hcn," ".join(h_out)))
        if a_out: out_p.append("%s: %s"%(acn," ".join(a_out)))
        if out_p: inj_lines.append("\n> 🚑 缺陣: "+" | ".join(out_p))
        ltd_p=[]
        if h_ltd: ltd_p.append("%s: %s"%(hcn," ".join(h_ltd)))
        if a_ltd: ltd_p.append("%s: %s"%(acn," ".join(a_ltd)))
        if ltd_p: inj_lines.append("\n> ⚠️ 傷疑: "+" | ".join(ltd_p))
        inj_str="".join(inj_lines)

        # 最後一行：O/U 說明 + 傷兵
        if ou_str:
            last_line="> %s%s"%(ou_str,inj_str)
        elif inj_str:
            last_line=inj_str.lstrip("\n")
        else:
            last_line=None

        score_str = "> 預測得分: %s **%.1f** — **%.1f** %s"%(acn,pred["a_expected"],pred["h_expected"],hcn)
        msg_lines=[
            "**%s  %s @ %s**"%(tier,acn,hcn),
            "🕐 %s %s (台灣時間)%s%s"%(game_date_str[5:].replace("-","/"),game_time_str,pf_note,mkt_tag),
            "⚾ 先發: %s — %s"%(a_sp_str,h_sp_str),
            "💰 推薦: %s"%bet_desc,
            stats_ln,
            score_str,
            "> Edge: **%+.1f%%** | 穩定%s%s | Kelly: $%.1f"%(raw_edge*100,stab_str,warn_note,stake),
        ]
        if last_line: msg_lines.append(last_line)
        msg="\n".join(msg_lines)+"\n"

        gk=(home,away)
        ex=next((i for i,p in enumerate(picks) if (p["home"],p["away"])==gk),None)
        if ex is not None:
            if best_pick["score"]>picks[ex].get("score",0):
                picks[ex]={"msg":msg,"tier":tier,"team":str(bteam),"home":home,"away":away,
                           "edge":raw_edge,"conf":bet_conf,"stake":stake,"score":best_pick["score"],
                           "model_p":model_p,"bp":bp,"btype":btype,
                           "label":best_pick.get("label",""),"bteam_cn":CN.get(bteam,bteam),
                           "game_date":game_date_str,"game_time":game_time_str,"game_dt":game_dt}
        else:
            picks.append({"msg":msg,"tier":tier,"team":str(bteam),"home":home,"away":away,
                          "edge":raw_edge,"conf":bet_conf,"stake":stake,"score":best_pick["score"],
                          "model_p":model_p,"bp":bp,"btype":btype,
                          "label":best_pick.get("label",""),"bteam_cn":CN.get(bteam,bteam),
                          "game_date":game_date_str,"game_time":game_time_str,"game_dt":game_dt})
        if official:
            rk=(home,away,game_date_str)
            if not any((r.get("home"),r.get("away"),r.get("date"))==rk for r in today_records):
                today_records.append({"date":game_date_str,"team":str(bteam),"home":home,"away":away,
                                      "price":bp,"edge":round(raw_edge,4),"conf":round(bet_conf,3),
                                      "stake":stake,"bet_type":btype,"result":None})

    # ★ 依穩定性排序：model_p × bet_conf（勝率高且信心高 → 最穩定）
    picks.sort(key=lambda x:(-(x.get("model_p",0) * x.get("conf",0))))

    total_settled,wins,wr=calc_perf(hist)
    total_in, total_pnl = calc_pnl(hist)
    now_str  = now_tw.strftime("%m/%d %H:%M")
    espn_str = "✅ESPN" if espn_ok else "⚠️BASE"
    il_str   = {"rotowire":"✅RotoWire","static":"⚠️靜態"}.get(il_src,il_src)
    sp_str   = "✅已取得" if pitchers else "❌未取得"
    era_str  = "✅近期ERA(%d)"%len(_RECENT_ERA) if _RECENT_ERA else "⚠️賽季ERA"
    scr_str  = "✅得分形態(%d)"%len(_SCORING_FORM) if _SCORING_FORM else "⚠️無得分形態"
    b2b_str  = "✅B2B(%d)"%len(_B2B_TEAMS) if _B2B_TEAMS else "—B2B"
    ser_str  = "✅系列賽(%d)"%len(_SERIES_MOMENTUM) if _SERIES_MOMENTUM else "⚠️無系列賽"

    roi_str = "%+.1f%%" % (total_pnl/total_in*100) if total_in > 0 else "N/A"
    pnl_str = "**%+.1f$**" % total_pnl if total_in > 0 else "尚無結算資料"

    lines=[
        "⚾ **MLB V130 分析報告**",
        "🕐 %s | %s %s %s %s %s %s %s"%(now_str,espn_str,il_str,sp_str,era_str,scr_str,b2b_str,ser_str),
        "📌 正式記錄 (00–07時)" if official else "🔧 測試模式 (不寫gist)",
        "📊 歷史: %d勝/%d場 (%.1f%%)"%(wins,total_settled,wr),
        "💰 累計損益: 投入 $%.1f | 損益 %s | ROI %s"%(total_in, pnl_str, roi_str),
        "",
    ]

    if not picks:
        lines.append("今日無符合條件之推薦。")
        lines.append(""); lines.append("📋 **診斷：今日場次 edge 概況**")
        diag=[]
        for game in odds_data:
            if game.get("sport_key")!="baseball_mlb": continue
            h=norm_team(game.get("home_team","")); a=norm_team(game.get("away_team",""))
            if h not in BASE or a not in BASE: continue
            si=pitchers.get((h,a),{}); hp_k=si.get("home_pitcher"); ap_k=si.get("away_pitcher")
            bms2=game.get("bookmakers",[]); hp=ap=rl_hp=rl_ap=ov_p=un_p=None; mt=8.5
            for bm in bms2:
                for mkt in bm.get("markets",[]):
                    mk2=mkt.get("key")
                    if mk2=="h2h":
                        for o in mkt.get("outcomes",[]):
                            t=norm_team(o.get("name","")); p=o.get("price",0)
                            if t==h and (hp is None or p>hp): hp=p
                            elif t==a and (ap is None or p>ap): ap=p
                    elif mk2=="spreads":
                        for o in mkt.get("outcomes",[]):
                            t=norm_team(o.get("name","")); p=o.get("price",0)
                            if t==h and (rl_hp is None or p>rl_hp): rl_hp=p
                            elif t==a and (rl_ap is None or p>rl_ap): rl_ap=p
                    elif mk2=="totals":
                        for o in mkt.get("outcomes",[]):
                            pt=o.get("point"); p=o.get("price",0); nm=o.get("name","")
                            if pt is not None:
                                try: mt=float(pt)
                                except (ValueError, TypeError): pass
                            if nm=="Over" and (ov_p is None or p>ov_p): ov_p=p
                            elif nm=="Under" and (un_p is None or p>un_p): un_p=p
            if not hp or not ap: continue
            pr=predict(h,a,hp_k,ap_k,market_total=mt)
            cf=pr["conf_factor"]; mg=pr["margin"]; ds=pr["dyn_std"]
            # ML edge
            he=pr["home_win_prob"]-1/hp; ae=pr["away_win_prob"]-1/ap
            be=max(he,ae); bp2=hp if he>=ae else ap; best_lbl="ML"
            # 讓分 edge（比較時套用0.90信心折扣）
            if rl_hp and rl_ap:
                rl_ph=runline_prob(mg,1.5,ds)
                rl_he=rl_ph-1/rl_hp; rl_ae=(1-rl_ph)-1/rl_ap; rl_be=max(rl_he,rl_ae)
                if rl_be*0.90>be: be=rl_be; bp2=rl_hp if rl_he>=rl_ae else rl_ap; best_lbl="RL"
            # 大小分 edge（比較時套用0.88信心折扣）
            if ov_p and un_p:
                p_ov=over_prob(pr["pure_total"],mt)
                tot_he=p_ov-1/ov_p; tot_ue=(1-p_ov)-1/un_p; tot_be=max(tot_he,tot_ue)
                if tot_be*0.88>be: be=tot_be; bp2=ov_p if tot_he>=tot_ue else un_p; best_lbl="TOT"
            diag.append("`%s@%s` [%s] Edge=%+.1f%% P=%.2f conf=%.0f%% SP:%s/%s"%(
                CN.get(a,a),CN.get(h,h),best_lbl,be*100,bp2,cf*100,hp_k or "?",ap_k or "?"))
        for d in sorted(diag,key=lambda x:-float(x.split("Edge=")[1].split("%")[0])): lines.append(d)
    else:
        lines.append("**推薦 %d 場（穩定性高→低 排序）**"%len(picks))
        for p in picks: lines.append(p["msg"])

    lines+=[
        "═"*20,"🔧 **MLB V129 模型功能**",
        "• 投手近期ERA融合 | 球場PF | 牛棚ERA | 動態主場優勢 | 球隊防守品質",
        "• 球星傷兵分級懲罰 | ESPN即時戰績 | 天氣調整（選用）| 早賽季信心上限",
        "• 三市場自動選優（獨贏/讓分/大小分）| 穩定性排序 | 書商數量×vig雙重信心",
        "• 近期10場得分形態 | 連續出賽疲勞 | 顯示預測比分",
        "• [V129] ★ STD 1.45→1.65 / TOTAL_STD 2.10→2.30（修正讓分機率過度樂觀）",
        "• [V129] ★ 系列賽動能：連敗隊進攻-0.12/信心×0.93（如太空人連輸水手）",
        "• [V129] ★ RL edge門檻 0.10→0.12，RL/TOT最低勝率 0.45→0.55",
        "• [V130] ★ 模型勝率上限 90%→72%（MLB現實校準），blend_p門檻 0.48→0.52（避免重壓大冷門）",
    ]

    out="\n".join(lines)
    if official and today_records: save_hist(hist+today_records)
    log.info("Sending %d chars",len(out))
    send(out)
    log.info("Done")


if __name__ == "__main__":
    run()
