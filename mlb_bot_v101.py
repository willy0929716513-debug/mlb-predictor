import os, json, math, logging, datetime, re, requests, unicodedata

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("MLB_V123")

ODDS_API_KEY    = os.getenv("ODDS_API_KEY", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN        = os.getenv("GH_TOKEN", "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")  # OpenWeatherMap（選用）

GIST_DESC = "mlb_bot_history"

# ── 模型參數 ──────────────────────────────────
EDGE_MIN       = 0.08
EDGE_MIN_RL    = 0.12   # 讓分 raw_edge 門檻（↑0.10→0.12 要求更明確優勢）
EDGE_MIN_TOT   = 0.09   # 大小分（totals）edge 門檻
EDGE_MIN_ML_FAV= 0.14   # ML低賠（賠率<1.65）額外edge門檻：損益平衡高，需更大優勢
MIN_MODEL_P_ML  = 0.65  # ML 模型勝率門檻（↑0.55→0.65，1.60賠率損益平衡62.5%）
MIN_MODEL_P_RL  = 0.73  # RL 門檻（↑0.68→0.73 過濾70-72%邊際注單）
MIN_MODEL_P_TOT = 0.60  # TOT 門檻：避免貼線邊際注單
ML_BET_CONF_MIN = 0.72  # ML 最低信心門檻（同RL，過濾邊際低賠注單）
ML_FAV_PRICE    = 1.65  # ML低賠閾值：低於此賠率視為高損益平衡重注
ML_FAV_KELLY    = 0.80  # ML低賠Kelly折扣（損益平衡高，縮注20%）
KELLY_BAYES_W   = 0.35  # Kelly計算時，devigged市場概率混入model_p的比重（貝葉斯收縮）
MOD_W          = 0.18
MKT_W          = 0.82
TOTAL_STD      = 2.30   # 兩隊合計得分標準差
STD            = 1.80   # 比賽勝負分差標準差（↑1.65→1.80 減少過度自信）
RL_STD_MULT    = 1.90   # 讓分概率用更高不確定性
RS_BLEND_W     = 0.12   # 投手隊友得分支援調整幅度（用於ML/RL預測）
RS_BLEND_W_TOT = 0.04   # 大小分預測的RS權重（極低，防止RS拉高Over）
MIN_P          = 1.35
MAX_P          = 2.50
BANK           = 1000.0
KELLY          = 0.12
KELLY_MAX      = 150.0
KELLY_MIN      = 5.0
MAX_PICKS      = 5      # CLV 排序後只取前 N 名，讓推薦穩定
MAX_RL_PICKS   = 2      # 每日RL推薦上限（防止同日過度集中）
RL_BET_CONF_MIN= 0.72  # RL 最低信心門檻（高於全局 0.65，邊際RL需更確定）
RL_KELLY_MULT  = 0.75  # RL Kelly 折扣（不確定性更高，下注降低25%）
RL_KELLY_MAX   = 100.0 # RL 最大下注上限（低於ML的150）
LINE_CLV_MIN   = -0.30  # 線路 CLV 門檻：允許 ≤0.30% 的線路噪音，避免過度過濾
BLOWOUT_ERA_DIFF = 1.5  # ERA差門檻：弱投手隊不推薦讓分受讓
BLOWOUT_ERA_POOR = 4.20 # 弱投手ERA門檻（≥此值且ERA差距大，拒絕RL）
ELITE_ERA_DUAL   = 3.50 # 雙方投手都低於此值時視為菁英對決
ELITE_ERA_OVER_P = 0.68 # 菁英投手對決時，OVER需達更高概率門檻（防RS拉高）
ACE_ERA_RL       = 2.70 # 面對此ERA以下的王牌投手時，拒絕推薦讓分受讓
FIP_ERA_WARN_GAP = 1.50 # RL: 推薦隊SP的FIP比ERA高超過此值 → 幸運ERA不可持續，拒絕RL
FIP_ERA_UNDER_GAP= 1.00 # UNDER: 任一SP的FIP比ERA高超過此值 → 幸運ERA，失分回歸，拒絕UNDER
ODDS_SNAP_PATH = "docs/odds_snapshot.json"
LEAGUE_ERA     = 4.20
HIST_TTL       = 90
GAP1, GAP2, GAP3 = 1.5, 2.5, 3.5
ESPN_ALPHA_MAX = 0.65
SP_RECENT_W    = 0.80   # 本賽季 ERA 權重（80%）
SP_SEASON_W    = 0.20   # 四年歷史均值 ERA 權重（20%）
SCORING_FORM_W = 0.10   # 近期打擊得分調整幅度（±10%）
MIN_SP_IP_UNDER    = 5.0   # 先發場均局數門檻：低於此值UNDER需更高概率（開場/短局投手保護）
UNDER_LOW_IP_EXTRA = 0.10  # 低局數先發UNDER額外概率門檻（+10%）
UNDER_WHIP_THRESH  = 1.40  # 高WHIP門檻：任一先發超過此值時UNDER需額外確認
UNDER_WHIP_EXTRA   = 0.05  # 高WHIP UNDER額外概率門檻（+5%）
# ── ★ FIP + K/9 ──────────────────────────────────────────
FIP_CONST      = 3.10   # FIP固定常數（依聯盟ERA標準化）
FIP_BLEND_W    = 0.35   # 近期FIP混入ERA的比重（基準，FIP-ERA缺口小時使用）
FIP_BLEND_MID  = 0.55   # FIP-ERA缺口 0.5–1.0：輕度幸運ERA，FIP權重提升
FIP_BLEND_HIGH = 0.70   # FIP-ERA缺口 1.0–1.5：嚴重幸運ERA，FIP主導
FIP_BLEND_MAX  = 0.85   # FIP-ERA缺口 > 1.5：極端幸運ERA，幾乎全信FIP
FIP_MISSING_REGRESS = 0.25  # FIP無資料時，ERA向聯盟均值回歸比例（保守修正）
ERA_FLOOR_NO_FIP    = 2.50  # FIP無資料時有效ERA下限（防止過信異常低ERA）
K9_HIGH_THRESH = 9.0    # 高三振率門檻（K/9）：雙方達標時UNDER信心加成
K9_UNDER_CONF  = 0.04   # 雙高K/9 UNDER信心加成幅度
# ── ★ 投手休息天數 ────────────────────────────────────────
REST_SHORT_DAYS = 3     # 短休門檻（≤此天數）：投手可能未完全恢復
REST_SHORT_ERA  = 0.30  # 短休 ERA 懲罰（效果等同ERA+0.30）
REST_LONG_DAYS  = 9     # 長休門檻（≥此天數）：鏽腳/狀態不穩定
REST_LONG_ERA   = 0.20  # 長休 ERA 懲罰
# ── ★ 市場品質 ────────────────────────────────────────────
MIN_BOOKS      = 3      # 最少bookmaker數（不足時視為非流動市場）
LOW_BOOKS_CONF = 0.88   # bookmaker數不足時的信心係數折扣
# ── ★ 相關性風險管理 ──────────────────────────────────────
CORR_DAMP_W    = 0.80   # 同方向第二注以後的Kelly折扣（20%縮注）
# ── ★ 風險管理 ────────────────────────────────────────────
MAX_DAILY_STAKE  = 300.0 # 單日總曝險上限（佔bankroll 30%）
SLUMP_WINDOW     = 10    # 低迷偵測近N注
SLUMP_WR_THRESH  = 0.40  # 近N注勝率低於此值視為低迷期
SLUMP_KELLY_MUL  = 0.75  # 低迷期全局Kelly折扣
# ── ★ 校正 ───────────────────────────────────────────────
MIN_SAMPLE_CALIB = 20    # 分類型勝率校正所需最少樣本

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

# ── ★ 牛棚深度（1.0=均值，>1.0=陣容深、可靠，<1.0=陣容薄）──
BULLPEN_DEPTH = {
    "dodgers":1.20,"braves":1.15,"phillies":1.15,"yankees":1.18,"astros":1.12,
    "guardians":1.10,"padres":1.08,"mariners":1.08,"cubs":1.05,"mets":1.05,
    "brewers":1.05,"rangers":1.03,"red sox":1.00,"blue jays":1.00,"giants":1.00,
    "royals":0.98,"twins":0.97,"tigers":0.97,"orioles":0.97,"rays":0.98,
    "pirates":0.93,"diamondbacks":0.95,"cardinals":0.95,"reds":0.92,
    "athletics":0.90,"angels":0.88,"nationals":0.88,"white sox":0.85,
    "marlins":0.85,"rockies":0.80,
}

# ── 投手賽季 ERA（四年歷史均值作為基準）──────────────
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
    "freeland":4.75,"misiorowski":4.36,"bradley_t":0.87,"liberatore":4.21,
    "severino":4.54,"cavalli":4.25,"boyd":3.21,"horton":4.10,"abbott":3.42,
    "burke_s":3.60,"smith_s":3.81,"pfaadt":4.10,"weathers":4.50,
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
    "martin_c":4.60,"sears":4.50,"cortes":4.30,"houser":4.80,"lynch":4.70,
    "cox":4.80,"feltner":5.20,"hudson":5.00,"small":4.70,"wesneski":4.40,
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
_DYN_OUT        = {}
_DYN_LTD        = {}
_ESPN_RATINGS   = {}
_RECENT_ERA     = {}
_PITCHER_RS     = {}  # pitcher_key -> run_support_per_start (隊友場均得分)
_PITCHER_IP     = {}  # pitcher_key -> avg_ip_per_qualifying_start (IP≥4.0才計入)
_PITCHER_WHIP   = {}  # pitcher_key -> recent WHIP = (BB+H)/IP
_PITCHER_FIP    = {}  # pitcher_key -> recent FIP (Fielding Independent Pitching，防守獨立ERA)
_PITCHER_K9     = {}  # pitcher_key -> recent K/9 (每9局三振數)
_PITCHER_LAST   = {}  # pitcher_key -> last start date (YYYY-MM-DD)
_RELIEVER_FLAGS = set()  # 偵測為牛棚型：有出賽紀錄但無任何IP≥4.0先發
_LIVE_SP_ERA    = {}  # pitcher_key -> 本賽季整體ERA（MLB Stats API即時）
_WEATHER_CACHE  = {}


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
    # Strip accents: "Rodríguez" → "rodriguez", "Peña" → "pena"
    ascii_name = unicodedata.normalize("NFKD", full_name).encode("ascii", "ignore").decode("ascii")
    parts = ascii_name.strip().split()
    k = parts[-1].lower() if len(parts) >= 2 else ascii_name.lower()
    if k in ("jr.","jr","sr.","sr","ii","iii","iv") and len(parts) >= 2:
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

def _fetch_recent_era(pitcher_id, last_n=3):
    """返回 (ERA, RS, avg_ip, WHIP, FIP, K9, last_start, is_reliever) 8-tuple。
    FIP = Fielding Independent Pitching：消除打者運氣的純投手指標。
    K9 = 每9局三振數：高K9是UNDER的強烈正向信號。
    last_start = 最近先發日期 YYYY-MM-DD，用於計算休息天數。
    is_reliever = 有出賽紀錄但無任何IP≥4.0先發。"""
    _NONE8 = (None, None, None, None, None, None, None, False)
    year = datetime.date.today().year
    data = safe_get(
        "https://statsapi.mlb.com/api/v1/people/%d/stats" % pitcher_id,
        params={"stats":"gameLog","group":"pitching","season":year,"gameType":"R"},
        timeout=10,
    )
    if not data: return _NONE8
    splits = []
    for s in data.get("stats",[]): splits = s.get("splits",[]); break

    # 完整先發（IP ≥ 4.0，過濾開場型中繼與牛棚短局出賽）
    proper_starts = [s for s in splits
                     if float(s.get("stat",{}).get("inningsPitched","0") or 0) >= 4.0]
    any_apps = [s for s in splits
                if float(s.get("stat",{}).get("inningsPitched","0") or 0) >= 0.1]
    is_reliever = (len(any_apps) > 0 and len(proper_starts) == 0)

    recent = proper_starts[-last_n:] if len(proper_starts) >= last_n else proper_starts
    if not recent: return (None, None, None, None, None, None, None, is_reliever)

    def _f(key, default="0"):
        return sum(float(s.get("stat",{}).get(key, default) or default) for s in recent)

    total_ip  = _f("inningsPitched")
    if total_ip < 4: return (None, None, None, None, None, None, None, is_reliever)

    total_er  = _f("earnedRuns")
    total_bb  = _f("baseOnBalls")
    total_h   = _f("hits")
    total_hr  = _f("homeRuns")
    total_k   = _f("strikeOuts")
    total_hbp = _f("hitBatsmen")

    # ── ERA ──────────────────────────────────────────────────
    era     = round(total_er / total_ip * 9, 2)
    era_ret = None if era < 0.50 else min(era, 10.0)

    # ── FIP（防守獨立投球指標）──────────────────────────────
    # FIP = (13×HR + 3×(BB+HBP) - 2×K) / IP + FIP_CONST
    # 消除守備/BABIP運氣，更能預測未來表現
    fip_raw = (13*total_hr + 3*(total_bb+total_hbp) - 2*total_k) / total_ip + FIP_CONST
    fip_ret = round(max(0.50, min(fip_raw, 10.0)), 2)

    # ── K/9（每9局三振數）────────────────────────────────────
    k9_ret   = round(total_k / total_ip * 9, 1)

    # ── 場均局數 + WHIP ──────────────────────────────────────
    avg_ip   = round(total_ip / len(recent), 1)
    whip_ret = round((total_bb + total_h) / total_ip, 2)

    # ── 最近先發日期（用於休息天數計算）────────────────────
    dates = [s.get("game",{}).get("gameDate","")[:10] for s in recent if s.get("game",{}).get("gameDate")]
    last_start_ret = max(dates) if dates else None

    # ── Run Support：從各場 boxscore 取隊伍得分 ──
    rs_vals = []
    for s in recent:
        gpk = s.get("game",{}).get("gamePk")
        tid = s.get("team",{}).get("id")
        if not gpk or not tid: continue
        box = safe_get(
            "https://statsapi.mlb.com/api/v1/game/%d/boxscore" % gpk,
            params={"fields":"teams,home,away,team,id,teamStats,batting,runs"},
            timeout=6,
        )
        if not box: continue
        for side in ("home","away"):
            td = box.get("teams",{}).get(side,{})
            if td.get("team",{}).get("id") == tid:
                r = td.get("teamStats",{}).get("batting",{}).get("runs")
                if r is not None:
                    try: rs_vals.append(min(float(r), 10.0))
                    except: pass
                break
    rs_ret = round(min(sum(rs_vals)/len(rs_vals), 8.0), 2) if rs_vals else None
    return era_ret, rs_ret, avg_ip, whip_ret, fip_ret, k9_ret, last_start_ret, is_reliever

def build_recent_era_cache(pitchers_dict):
    global _RECENT_ERA, _PITCHER_RS, _PITCHER_IP, _PITCHER_WHIP
    global _PITCHER_FIP, _PITCHER_K9, _PITCHER_LAST, _RELIEVER_FLAGS
    cache={}; rs_cache={}; ip_cache={}; whip_cache={}
    fip_cache={}; k9_cache={}; last_cache={}; reliever_set=set()
    seen = set()
    for (home, away), info in pitchers_dict.items():
        for key, full, direct_id in [
            (info.get("home_pitcher"), info.get("home_name"), info.get("home_pitcher_id")),
            (info.get("away_pitcher"), info.get("away_name"), info.get("away_pitcher_id")),
        ]:
            if not key or key in seen: continue
            if not full or full == "TBD": continue
            seen.add(key)

            # ★ 優先使用 schedule API 直接給的 pitcher ID（省去 name-search API 往返）
            pid = direct_id
            if not pid:
                # Fallback：name search（API 未給 ID 時）
                sdata = safe_get(
                    "https://statsapi.mlb.com/api/v1/people/search",
                    params={"names": full, "sportId": 1},
                    timeout=8,
                )
                if sdata:
                    for p in sdata.get("people", []):
                        if _name_to_key(p.get("fullName","")) == key:
                            pid = p.get("id"); break

            if not pid: continue
            era, rs, avg_ip, whip, fip, k9, last_start, is_reliever = _fetch_recent_era(pid)
            if is_reliever:
                reliever_set.add(key)
                log.info("Reliever: %s (no IP≥4.0 starts)", key)
            if era is not None:
                cache[key] = era
                log.info("ERA %s: %.2f (FIP=%.2f K9=%.1f avgIP=%.1f WHIP=%.2f)",
                         key, era,
                         fip if fip else 0, k9 if k9 else 0,
                         avg_ip if avg_ip else 0, whip if whip else 0)
            if rs is not None:      rs_cache[key]   = rs
            if avg_ip is not None:  ip_cache[key]   = avg_ip
            if whip is not None:    whip_cache[key] = whip
            if fip is not None:     fip_cache[key]  = fip
            if k9 is not None:      k9_cache[key]   = k9
            if last_start:          last_cache[key] = last_start
    _RECENT_ERA     = cache
    _PITCHER_RS     = rs_cache
    _PITCHER_IP     = ip_cache
    _PITCHER_WHIP   = whip_cache
    _PITCHER_FIP    = fip_cache
    _PITCHER_K9     = k9_cache
    _PITCHER_LAST   = last_cache
    _RELIEVER_FLAGS = reliever_set
    log.info("ERA:%d FIP:%d K9:%d RS:%d IP:%d Relievers:%d",
             len(cache), len(fip_cache), len(k9_cache),
             len(rs_cache), len(ip_cache), len(reliever_set))


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
                # 近期打擊得分形態（最近10場 vs 賽季均值）
                l10rs = st.get("last10RunsScored", st.get("vsLast10RunsScored",
                        st.get("last10PointsFor", None)))
                if l10rs is not None and t >= 10 and rs > 0:
                    recent_rpg = float(l10rs) / 10.0
                    season_rpg = rs / t
                    scoring_form = round((recent_rpg - season_rpg) / max(season_rpg, 3.0), 3)
                    scoring_form = max(-0.20, min(0.20, scoring_form))
                else:
                    scoring_form = 0.0
                ratings[short] = {
                    "off":   round(off_e*alpha + base["off"]*(1-alpha), 2),
                    "def":   round(def_e*alpha + base["def"]*(1-alpha), 2),
                    "form":  round((wp-0.5)*0.2, 3),
                    "games": t,
                    "scoring_form": scoring_form,
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
            hp     = hd.get("probablePitcher",{}).get("fullName")
            ap     = ad.get("probablePitcher",{}).get("fullName")
            hp_id  = hd.get("probablePitcher",{}).get("id")   # ★ 直接 MLB ID，省去重複 name-search
            ap_id  = ad.get("probablePitcher",{}).get("id")
            if hs and as_:
                result[(hs, as_)] = {
                    "home_pitcher":_name_to_key(hp),"away_pitcher":_name_to_key(ap),
                    "home_name":hp or "TBD","away_name":ap or "TBD",
                    "home_pitcher_id": hp_id,
                    "away_pitcher_id": ap_id,
                }
                log.info("SP: %s vs %s | H=%s A=%s", hs, as_, _name_to_key(hp), _name_to_key(ap))
    log.info("Pitchers resolved: %d games", len(result))
    return result


# ══════════════════════════════════════════════
# ★ 即時先發投手賽季ERA（MLB Stats API）
# ══════════════════════════════════════════════

def fetch_live_sp_era():
    """從 MLB Stats API 拉取本賽季全部投手ERA，
    補充靜態 PITCHER_ERA 字典（同名者不覆蓋，新名者補入）。
    IP≥20 局過濾，排除純牛棚。"""
    global _LIVE_SP_ERA
    year = datetime.date.today().year
    data = safe_get(
        "https://statsapi.mlb.com/api/v1/stats",
        params={"stats":"season","group":"pitching","gameType":"R",
                "season":year,"limit":1000,
                "fields":"stats,splits,player,fullName,stat,era,inningsPitched"},
        timeout=15,
    )
    if not data: return False
    live = {}
    for split in data.get("stats",[{}])[0].get("splits",[]):
        pname = split.get("player",{}).get("fullName","")
        stat  = split.get("stat",{})
        era_s = stat.get("era","")
        ip_s  = str(stat.get("inningsPitched","0"))
        try:
            # MLB API IP格式："123.1" = 123又1/3局
            ip_parts = ip_s.split(".")
            ip_total = int(ip_parts[0]) + (int(ip_parts[1])/3 if len(ip_parts)>1 and ip_parts[1] else 0)
            if ip_total < 20: continue
            era = float(era_s)
            if era < 0.5 or era > 9.5: continue
            key = _name_to_key(pname)
            if key: live[key] = round(era, 2)
        except: pass
    if live:
        _LIVE_SP_ERA = live
        log.info("Live SP ERA: %d pitchers (IP≥20)", len(live))
        return True
    return False


# ══════════════════════════════════════════════
# Odds API
# ══════════════════════════════════════════════

def fetch_odds():
    if not ODDS_API_KEY: log.error("ODDS_API_KEY not set"); return []
    data = safe_get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={"apiKey":ODDS_API_KEY,"regions":"us",
                "markets":"h2h,spreads,totals",
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

def _tkey(name):
    """球隊名標準化：移除空格/特殊字元，全小寫，用於比對。"""
    return re.sub(r'[^a-z]', '', (name or "").lower())

def _team_match(n1, n2):
    """MLB API / Odds API 隊名可能略有差異（如 Angels vs Angels of Anaheim），
    用包含關係做模糊比對。"""
    k1, k2 = _tkey(n1), _tkey(n2)
    if not k1 or not k2: return False
    return k1 == k2 or k1 in k2 or k2 in k1

def settle_hist(hist):
    """結算 result=None 的過去紀錄，透過 MLB Stats API 查最終比分。
    直接修改 hist 內容（in-place），回傳結算筆數。"""
    today = datetime.date.today().isoformat()
    pending = [r for r in hist
               if r.get("result") is None and r.get("date","") < today]
    log.info("settle_hist: total=%d pending=%d (today=%s)", len(hist), len(pending), today)
    if pending:
        s = pending[0]
        log.info("settle_hist sample: date=%s home=%r away=%r team=%r bet=%r",
                 s.get("date"), s.get("home"), s.get("away"), s.get("team"), s.get("bet_type"))
    if not pending: return 0

    by_date = {}
    for r in pending:
        by_date.setdefault(r["date"], []).append(r)

    updated = 0
    for date_str, records in sorted(by_date.items()):
        data = safe_get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId":1,"date":date_str,
                    "fields":"dates,games,teams,home,away,team,name,score,status,detailedState"},
            timeout=10,
        )
        if not data: log.warning("settle_hist: no API data for %s", date_str); continue

        # 建立 (home隊名key, away隊名key) -> (h_score, a_score) 查找表
        score_map = {}
        for d in data.get("dates",[]):
            for g in d.get("games",[]):
                if "Final" not in g.get("status",{}).get("detailedState",""):
                    continue
                hd = g.get("teams",{}).get("home",{}); ad = g.get("teams",{}).get("away",{})
                hs = hd.get("score"); as_ = ad.get("score")
                if hs is None or as_ is None: continue
                hk = _tkey(hd.get("team",{}).get("name",""))
                ak = _tkey(ad.get("team",{}).get("name",""))
                score_map[(hk, ak)] = (int(hs), int(as_))
        log.info("settle_hist %s: %d final games, %d pending picks", date_str, len(score_map), len(records))

        for r in records:
            r_hk = _tkey(r.get("home",""))
            r_ak = _tkey(r.get("away",""))
            scores = None
            for (hk, ak), sc in score_map.items():
                if _team_match(r_hk, hk) and _team_match(r_ak, ak):
                    scores = sc; break
            if scores is None: continue
            h_score, a_score = scores

            btype = r.get("bet_type","")
            team  = r.get("team","")
            label = r.get("label","") or ""
            team_is_home = _team_match(_tkey(team), r_hk)

            try:
                if btype == "獨贏":
                    win = (h_score > a_score) if team_is_home else (a_score > h_score)
                elif btype == "讓分":
                    spread = float(label)
                    if team_is_home:
                        win = (h_score + spread) > a_score
                    else:
                        win = (a_score + spread) > h_score
                elif btype == "大小分":
                    mkt = r.get("market_total")
                    if mkt is None: continue
                    total = h_score + a_score
                    win = (total > mkt) if label == "OVER" else (total < mkt)
                else:
                    continue
            except Exception as ex:
                log.warning("settle calc error %s: %s", r, ex); continue

            r["result"] = "W" if win else "L"
            updated += 1
            log.info("Settled [%s] %s (%d-%d) → %s  %s %s",
                     date_str, r.get("home","")+"v"+r.get("away",""),
                     h_score, a_score, r["result"], btype, label or team)

    log.info("Auto-settled: %d records", updated)
    return updated

# ── 線路 CLV 快照 ────────────────────────────────
_SIDE_KEY = {
    "home":"home_ml","away":"away_ml",
    "rl_h":"rl_h","rl_a":"rl_a",
    "rl_h_25":"rl_h_25","rl_a_25":"rl_a_25",
    "over":"over","under":"under",
}

def load_odds_snapshot():
    try:
        with open(ODDS_SNAP_PATH,"r",encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_odds_snapshot(snap):
    try:
        with open(ODDS_SNAP_PATH,"w",encoding="utf-8") as f:
            json.dump(snap,f,ensure_ascii=False,indent=2)
    except Exception as e:
        log.warning("save odds snap: %s", e)

def line_clv(curr_price, prev_price):
    """市場賠率移動帶來的真實 CLV 信號（%）：
    正值 = 賠率縮短（市場認同我方），負值 = 賠率拉長（市場不認同）。"""
    if not prev_price or not curr_price: return None
    return round((1/curr_price - 1/prev_price) * 100, 2)

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
    import time as _time
    pl  = {"description":GIST_DESC,"public":False,"files":{"history.json":{"content":body}}}
    for attempt in range(1, 4):
        try:
            if gid:
                requests.patch("https://api.github.com/gists/"+gid, headers=h, json=pl, timeout=10).raise_for_status()
            else:
                requests.post("https://api.github.com/gists", headers=h, json=pl, timeout=10).raise_for_status()
            log.info("Hist saved (%d records)", len(records)); return
        except Exception as e:
            log.warning("save_hist %d/3: %s", attempt, e)
            if attempt < 3: _time.sleep(2 ** attempt)  # 指數退避：2s, 4s


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
    for _ in _DYN_OUT.get(t,[]): penalty += 0.05
    for item in _DYN_LTD.get(t,[]):
        tier = item[1] if isinstance(item,tuple) else "B"
        penalty += LT_PEN.get(tier,0.4) * 0.15
    return round(min(penalty, 1.2), 3)

def get_pitcher_era(key):
    """ERA 估計：近期ERA+FIP 混合（消除BABIP），再與賽季基準融合。
    有效公式：0.48×近期ERA + 0.32×近期FIP + 0.20×賽季基準
    賽季基準優先序：_LIVE_SP_ERA（MLB API即時）> PITCHER_ERA（靜態字典）"""
    if not key: return LEAGUE_ERA + 0.60
    k = key.lower().strip()
    recent_era = _RECENT_ERA.get(k)
    # 賽季基準：優先即時API，靜態字典次之（新投手/未收錄者自動補）
    season_era = _LIVE_SP_ERA.get(k) or PITCHER_ERA.get(k)
    fip        = _PITCHER_FIP.get(k)
    if recent_era is not None:
        # FIP 動態混合：FIP-ERA缺口越大 → FIP權重越高（幸運ERA回歸修正）
        if fip:
            _gap = fip - recent_era
            if _gap > 1.50:   _fw = FIP_BLEND_MAX   # 極端幸運ERA
            elif _gap > 1.00: _fw = FIP_BLEND_HIGH   # 嚴重幸運ERA
            elif _gap > 0.50: _fw = FIP_BLEND_MID    # 輕度幸運ERA
            else:             _fw = FIP_BLEND_W       # ERA可信，基準混合
            adj_recent = round(recent_era*(1-_fw) + fip*_fw, 2)
        else:
            # FIP無資料：ERA可靠性未知，向聯盟均值保守回歸，且不低於下限
            adj_recent = round(recent_era*(1-FIP_MISSING_REGRESS) + LEAGUE_ERA*FIP_MISSING_REGRESS, 2)
            adj_recent = max(ERA_FLOOR_NO_FIP, adj_recent)
        if season_era is not None:
            return round(adj_recent*SP_RECENT_W + season_era*SP_SEASON_W, 2)
        return adj_recent
    return (season_era if season_era is not None else LEAGUE_ERA+0.60)

def get_rest_days(sp_key):
    """計算投手從最後先發到今天的休息天數；無資料返回 None。"""
    if not sp_key: return None
    last_str = _PITCHER_LAST.get(sp_key)
    if not last_str: return None
    try:
        last = datetime.date.fromisoformat(last_str)
        return (datetime.date.today() - last).days
    except: return None

def rest_era_penalty(sp_key):
    """短休（≤3天）或長休（≥9天）都會增加有效ERA。
    正常休息（4-8天）不調整。返回 ERA 加成值。"""
    days = get_rest_days(sp_key)
    if days is None: return 0.0
    if days <= REST_SHORT_DAYS: return REST_SHORT_ERA
    if days >= REST_LONG_DAYS:  return REST_LONG_ERA
    return 0.0

def era_adj(key):
    return round((get_pitcher_era(key) - LEAGUE_ERA) * 0.35, 3)

def bullpen_adj(team):
    t = team.lower()
    era   = BULLPEN_ERA.get(t, LEAGUE_BULL_ERA)
    depth = BULLPEN_DEPTH.get(t, 1.0)
    # 深度好的牛棚：ERA 優勢放大；陣容薄：ERA 優勢縮水
    return round((era - LEAGUE_BULL_ERA) * 0.20 * depth, 3)

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

def poisson_cdf(k_int, lam):
    """P(Poisson(lam) ≤ k_int)：直接累積計算，無需外部函式庫。"""
    if lam <= 0: return 1.0
    total, term = 0.0, math.exp(-lam)
    for i in range(int(k_int) + 1):
        total += term
        if total >= 1.0: return 1.0
        term *= lam / (i + 1)
    return total

def over_prob(exp_total, line):
    """P(合計得分 > line) — Poisson 模型（棒球得分正確分佈）。
    8.5線 → P(X≥9) = 1 - P(X≤8)；9.0線 → P(X≥10) = 1 - P(X≤9)。"""
    k = int(line)  # floor: P(X > line) = P(X >= k+1) = 1 - P(X <= k)
    return max(0.02, min(0.98, 1.0 - poisson_cdf(k, max(0.1, exp_total))))

def predict(home, away, home_sp, away_sp, market_total=8.5, game_dt=None):
    hr = get_rating(home)
    ar = get_rating(away)
    games = hr.get("games", 0)

    # ① 先發 ERA（近期ERA×(1-FIP_BLEND) + FIP×FIP_BLEND 混合，已在 get_pitcher_era 中完成）
    h_sp_adj = era_adj(home_sp)
    a_sp_adj = era_adj(away_sp)

    # ① 延伸：休息天數懲罰（短休/長休 → 有效ERA上升 → 對手得分微增）
    # era_adj 的轉換係數 0.35：ERA 增加 1.0 → scoring adjustment 增加 0.35
    h_rest_pen = rest_era_penalty(home_sp) * 0.35  # 主隊SP短休 → 客隊得分小幅增加
    a_rest_pen = rest_era_penalty(away_sp) * 0.35  # 客隊SP短休 → 主隊得分小幅增加

    # ② 動態主場優勢
    ha = 0.07 + hr.get("form", 0.0) * 0.3

    # ③ 基礎期望得分（含休息天數調整）
    h_exp = hr["off"] + a_sp_adj + a_rest_pen + ha
    a_exp = ar["off"] + h_sp_adj + h_rest_pen

    # ④ 傷兵
    h_exp -= injury_penalty(home) * 0.4
    a_exp -= injury_penalty(away) * 0.4

    # ⑤ ★ 牛棚深度（對手牛棚好且深 → 己方後段得分降低）
    h_exp -= bullpen_adj(away)
    a_exp -= bullpen_adj(home)

    # ⑥a ★ 近期打擊得分形態（熱打/冷打調整）
    h_sf = hr.get("scoring_form", 0.0)
    a_sf = ar.get("scoring_form", 0.0)
    h_exp = round(h_exp * (1.0 + h_sf * SCORING_FORM_W), 3)
    a_exp = round(a_exp * (1.0 + a_sf * SCORING_FORM_W), 3)

    # ⑥b ★ 投手隊友得分支援（run support/GS vs 隊伍場均）
    # 若這投手先發時隊伍習慣多/少得分，微調期望得分
    # ML/RL使用完整RS_BLEND_W；大小分使用極低RS_BLEND_W_TOT（防RS拉高Over）
    h_rs = _PITCHER_RS.get(home_sp)
    a_rs = _PITCHER_RS.get(away_sp)
    h_rpg = hr.get("off", h_exp)   # 用 off 當隊伍基準得分
    a_rpg = ar.get("off", a_exp)
    h_exp_tot = h_exp  # 大小分專用，RS權重更低
    a_exp_tot = a_exp
    if h_rs is not None and h_rpg > 0:
        rs_adj_h = h_rs - h_rpg
        h_exp     = round(h_exp     + rs_adj_h * RS_BLEND_W,     3)
        h_exp_tot = round(h_exp_tot + rs_adj_h * RS_BLEND_W_TOT, 3)
    if a_rs is not None and a_rpg > 0:
        rs_adj_a = a_rs - a_rpg
        a_exp     = round(a_exp     + rs_adj_a * RS_BLEND_W,     3)
        a_exp_tot = round(a_exp_tot + rs_adj_a * RS_BLEND_W_TOT, 3)

    # ⑦ ★ 球場係數
    pf = PARK_FACTOR.get(home.lower(), 1.0)
    h_exp     *= pf; a_exp     *= pf
    h_exp_tot *= pf; a_exp_tot *= pf

    # ⑧ ★ 天氣（選用）
    if game_dt and WEATHER_API_KEY:
        wf = fetch_weather(home, game_dt)
        h_exp     *= wf; a_exp     *= wf
        h_exp_tot *= wf; a_exp_tot *= wf

    h_exp = max(2.5, h_exp); a_exp = max(2.5, a_exp)
    h_exp_tot = max(2.5, h_exp_tot); a_exp_tot = max(2.5, a_exp_tot)
    margin = h_exp - a_exp

    dyn_std = STD + max(0, (10-games)/10) * 0.15
    model_win_p = win_prob_from_margin(margin, dyn_std)
    # ★ 勝率上限 90%：現實中單場勝率不會超過此值
    model_win_p = min(model_win_p, 0.82)  # 單場 ML 勝率上限 82%（原 90% 過高）

    pure_total     = h_exp     + a_exp
    pure_total_tot = h_exp_tot + a_exp_tot  # 大小分投注用（降低RS影響）
    model_total    = round(pure_total*0.30 + market_total*0.70, 2)
    _pc = (pitcher_confidence(home_sp) * pitcher_confidence(away_sp)) ** 0.5
    conf     = total_confidence(pure_total, market_total) * _pc
    # ★ TOT專用信心：用pure_total_tot（降低RS影響）比較更準確
    conf_tot = total_confidence(pure_total_tot, market_total) * _pc

    return {
        "home_win_prob":  round(model_win_p, 4),
        "away_win_prob":  round(1-model_win_p, 4),
        "model_total":    model_total,
        "pure_total":     round(pure_total, 2),
        "pure_total_tot": round(pure_total_tot, 2),
        "conf_factor":    round(max(0.40, min(1.0, conf)), 3),
        "conf_tot":       round(max(0.40, min(1.0, conf_tot)), 3),
        "h_expected":     round(h_exp, 2),
        "a_expected":     round(a_exp, 2),
        "margin":         round(margin, 3),
        "park_factor":    pf,
        "dyn_std":        round(dyn_std, 3),
        "h_rs":           h_rs,          # 投手專屬 RS/GS（API 有才有，否則 None）
        "a_rs":           a_rs,
        "h_team_rpg":     round(hr.get("off", 4.5), 2),
        "a_team_rpg":     round(ar.get("off", 4.5), 2),
    }

def runline_prob(margin, spread, dyn_std):
    """P(主場隊蓋掉 -spread 讓分，即贏分差 > spread)"""
    return max(0.02, min(0.98, norm_cdf((margin - spread) / dyn_std)))

def kelly_stake(edge, model_p, price, conf=1.0, dv_p=None):
    if edge<=0 or price<=1.0: return 0.0
    b = price-1.0
    # 貝葉斯收縮：model_p 混入 devigged 市場概率，避免過信模型高估
    kp = (model_p*(1-KELLY_BAYES_W) + dv_p*KELLY_BAYES_W) if dv_p else model_p
    raw_k = (b*kp - (1-kp)) / b
    if raw_k<=0: return 0.0
    dyn_k = max(0.05, min(0.18, KELLY*conf))
    return round(max(0.0, min(KELLY_MAX, dyn_k*raw_k*BANK)), 1)

def calc_perf(hist):
    settled = [r for r in hist if r.get("result") in ("W","L")]
    wins = sum(1 for r in settled if r["result"]=="W")
    return len(settled), wins, wins/len(settled)*100 if settled else 0.0

def calc_pnl(hist):
    total_in = total_pnl = 0.0
    for r in hist:
        if r.get("result") not in ("W","L"): continue
        stake = r.get("stake")
        if not stake: continue
        price = r.get("price", 0)
        total_in  += stake
        total_pnl += stake * (price - 1) if r["result"] == "W" else -stake
    return round(total_in, 1), round(total_pnl, 1)

def calc_perf_by_type(hist):
    """分別計算 ML/RL/TOT 歷史勝率，用於動態信心校正。
    需 ≥ MIN_SAMPLE_CALIB 筆才回傳值，否則回傳 None（避免小樣本過擬合）。"""
    buckets = {"獨贏":[0,0], "讓分":[0,0], "大小分":[0,0]}
    for r in hist:
        if r.get("result") not in ("W","L"): continue
        bt = r.get("bet_type","")
        if bt in buckets:
            buckets[bt][0] += 1
            if r["result"]=="W": buckets[bt][1] += 1
    return {
        bt: (v[1]/v[0] if v[0]>=MIN_SAMPLE_CALIB else None)
        for bt, v in buckets.items()
    }

def write_pages_json(picks, hist, now_tw):
    total_settled, wins, wr = calc_perf(hist)
    total_in, total_pnl     = calc_pnl(hist)
    roi = round(total_pnl / total_in * 100, 1) if total_in > 0 else None

    # ★ 分類型勝率 + ROI（供網頁顯示）
    by_type = {}
    for btlabel, btkey in [("ML","獨贏"),("RL","讓分"),("TOT","大小分")]:
        _rs = [r for r in hist if r.get("result") in ("W","L") and r.get("bet_type")==btkey]
        if len(_rs) >= 3:
            _w = sum(1 for r in _rs if r["result"]=="W")
            _in = sum(r.get("stake",0) for r in _rs)
            _pnl = sum(r.get("stake",0)*(r.get("price",2)-1) if r["result"]=="W"
                       else -r.get("stake",0) for r in _rs)
            by_type[btlabel] = {
                "wins": _w, "settled": len(_rs),
                "win_rate": round(_w/len(_rs)*100, 1),
                "roi": round(_pnl/_in*100, 1) if _in > 0 else None,
            }

    _ak = lambda p, k: p.get("away_sp_name","")
    _hk = lambda p, k: p.get("home_sp_name","")
    records = []
    for p in picks:
        ask, hsk = p.get("away_sp_name",""), p.get("home_sp_name","")
        records.append({
            "tier":        p.get("tier",""),
            "btype":       p.get("btype",""),
            "away":        p.get("away",""),
            "home":        p.get("home",""),
            "away_cn":     p.get("away_cn",""),
            "home_cn":     p.get("home_cn",""),
            "bet_label":   p.get("bet_label",""),
            "bk":          p.get("bk",""),
            "bp":          round(p.get("bp",0),2),
            "con_p":       p.get("con_p"),
            "dv_p":        p.get("dv_p"),            # devigged 真實市場概率
            "edge":        round(p.get("edge",0)*100,1),
            "conf":        round(p.get("conf",0)*100,1),
            "stake":       round(p.get("stake",0),1),
            "model_p":     round(p.get("model_p",0)*100,1),
            "away_sp":     p.get("away_sp_full", ask) or ask,   # 完整姓名
            "home_sp":     p.get("home_sp_full", hsk) or hsk,
            "away_era":    p.get("away_era"),
            "home_era":    p.get("home_era"),
            "away_fip":    round(_PITCHER_FIP[ask],2) if ask in _PITCHER_FIP else None,
            "home_fip":    round(_PITCHER_FIP[hsk],2) if hsk in _PITCHER_FIP else None,
            "away_k9":     round(_PITCHER_K9[ask],1)  if ask in _PITCHER_K9  else None,
            "home_k9":     round(_PITCHER_K9[hsk],1)  if hsk in _PITCHER_K9  else None,
            "away_avgip":  round(_PITCHER_IP[ask],1)  if ask in _PITCHER_IP  else None,
            "home_avgip":  round(_PITCHER_IP[hsk],1)  if hsk in _PITCHER_IP  else None,
            "away_whip":   round(_PITCHER_WHIP[ask],2) if ask in _PITCHER_WHIP else None,
            "home_whip":   round(_PITCHER_WHIP[hsk],2) if hsk in _PITCHER_WHIP else None,
            "away_rest":   get_rest_days(ask) if ask else None,
            "home_rest":   get_rest_days(hsk) if hsk else None,
            "away_rs":     p.get("away_rs"),
            "home_rs":     p.get("home_rs"),
            "away_rpg":    p.get("away_rpg"),
            "home_rpg":    p.get("home_rpg"),
            "pred_away":   p.get("pred_away"),
            "pred_home":   p.get("pred_home"),
            "model_total": p.get("model_total"),
            "market_total":p.get("market_total"),
            "park_factor": p.get("park_factor"),
            "line_clv":    p.get("line_clv"),
            "game_date":   p.get("game_date",""),
            "game_time":   p.get("game_time",""),
        })
    payload = {
        "generated_at": now_tw.strftime("%Y-%m-%d %H:%M") + " (台灣時間)",
        "date":         now_tw.strftime("%Y-%m-%d"),
        "stats": {
            "settled":   total_settled, "wins": wins,
            "win_rate":  round(wr,1),
            "total_in":  round(total_in,1), "total_pnl": round(total_pnl,1), "roi": roi,
            "by_type":   by_type,      # ★ 分類型勝率（ML/RL/TOT）
        },
        "picks": records,
    }
    os.makedirs("docs", exist_ok=True)
    with open("docs/picks_latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info("Wrote docs/picks_latest.json (%d picks)", len(records))


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
    official = (now_tw.hour >= 23 or now_tw.hour < 7)  # 台灣時間 23:00–07:00

    if not ODDS_API_KEY: log.error("ODDS_API_KEY not set"); return

    hist      = load_hist()
    settled_n = settle_hist(hist)       # 結算昨天以前的未結算紀錄
    if settled_n > 0: save_hist(hist)   # 有更新就立即存回 Gist

    # ★ 按投注類型計算歷史勝率（≥MIN_SAMPLE_CALIB 才啟用，防小樣本過擬合）
    wr_by_type = calc_perf_by_type(hist) or {}
    for _bt, _bwr in wr_by_type.items():
        if _bwr is not None:
            log.info("HistCalib [%s]: WR=%.1f%%", _bt, _bwr * 100)

    # ★ 低迷偵測：近 SLUMP_WINDOW 已結算注，勝率 < SLUMP_WR_THRESH → 全局縮注
    _recent_settled = [r for r in hist if r.get("result") in ("W", "L")][-SLUMP_WINDOW:]
    _slump_mult = (SLUMP_KELLY_MUL
                   if len(_recent_settled) >= SLUMP_WINDOW
                   and sum(1 for r in _recent_settled if r["result"] == "W") / len(_recent_settled) < SLUMP_WR_THRESH
                   else 1.0)
    if _slump_mult < 1.0:
        log.info("Slump detected (last %d: WR<%.0f%%), Kelly x%.2f",
                 SLUMP_WINDOW, SLUMP_WR_THRESH * 100, _slump_mult)

    espn_ok   = fetch_espn_ratings()
    il_src    = fetch_injury_list()
    pitchers  = fetch_probable_pitchers()
    if pitchers:
        try: build_recent_era_cache(pitchers)
        except Exception as e: log.warning("Recent ERA failed: %s", e)
    # ★ 即時賽季 ERA（補強靜態 PITCHER_ERA 字典）
    try: fetch_live_sp_era()
    except Exception as e: log.warning("Live SP ERA fetch failed: %s", e)

    odds_data = fetch_odds()
    if not odds_data: log.error("No odds data"); return

    season_start = "%d-03-25" % datetime.date.today().year
    season_games = sum(1 for r in hist if r.get("date","") >= season_start)
    picks, today_records = [], []

    prev_snap = load_odds_snapshot()
    new_snap  = {}

    for game in odds_data:
        if game.get("sport_key") != "baseball_mlb": continue
        commence = game.get("commence_time","")
        try:
            game_utc      = datetime.datetime.fromisoformat(commence.replace("Z","+00:00"))
            game_tw       = game_utc + datetime.timedelta(hours=8)
            game_date_str = game_tw.strftime("%Y-%m-%d")
            game_time_str = game_tw.strftime("%H:%M")
            game_dt       = game_tw
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
        rl_h_price=rl_a_price=rl_h_book=rl_a_book=None
        rl_h_pts=None  # 主隊讓分點數（負=讓分，正=受讓）
        rl_h_price_25=rl_a_price_25=rl_h_book_25=rl_a_book_25=None
        rl_h_pts_25=None  # 主隊2.5讓分點數
        over_price=under_price=over_book=under_book=None
        market_total=8.5
        con_h_prices=[]; con_a_prices=[]
        con_rl_h=[]; con_rl_a=[]
        con_rl_h_25=[]; con_rl_a_25=[]
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
                elif mk=="spreads":
                    for o in mkt.get("outcomes",[]):
                        t=norm_team(o.get("name","")); p=o.get("price",0)
                        pt=o.get("point")
                        if t==home:
                            con_rl_h.append(p)
                            if rl_h_price is None or p>rl_h_price:
                                rl_h_price=p; rl_h_book=bk_name
                            if rl_h_pts is None and pt is not None:
                                try: rl_h_pts=float(pt)
                                except (ValueError, TypeError): pass
                        elif t==away:
                            con_rl_a.append(p)
                            if rl_a_price is None or p>rl_a_price: rl_a_price=p; rl_a_book=bk_name
                elif mk=="alternate_spreads":
                    for o in mkt.get("outcomes",[]):
                        t=norm_team(o.get("name","")); p=o.get("price",0)
                        pt=o.get("point")
                        if pt is None: continue
                        try: pt_f=float(pt)
                        except (ValueError, TypeError): continue
                        if abs(abs(pt_f)-2.5)>0.01: continue  # 只取 2.5 讓分線
                        if t==home:
                            con_rl_h_25.append(p)
                            if rl_h_price_25 is None or p>rl_h_price_25:
                                rl_h_price_25=p; rl_h_book_25=bk_name
                            if rl_h_pts_25 is None: rl_h_pts_25=pt_f
                        elif t==away:
                            con_rl_a_25.append(p)
                            if rl_a_price_25 is None or p>rl_a_price_25:
                                rl_a_price_25=p; rl_a_book_25=bk_name
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

        # ── 儲存本次賠率快照（供下次計算線路 CLV）──
        snap_key = "%s|%s|%s" % (game_date_str, home, away)
        new_snap[snap_key] = {
            "ts":today_str,
            "home_ml":home_price,"away_ml":away_price,
            "rl_h":rl_h_price,"rl_a":rl_a_price,
            "rl_h_25":rl_h_price_25,"rl_a_25":rl_a_price_25,
            "over":over_price,"under":under_price,
        }
        prev_game = prev_snap.get(snap_key, {})

        con_h = round(sum(con_h_prices)/len(con_h_prices),3) if con_h_prices else home_price
        con_a = round(sum(con_a_prices)/len(con_a_prices),3) if con_a_prices else away_price
        if con_h <= 0 or con_a <= 0: continue  # guard: 防止除以零

        con_rl_h_p = round(sum(con_rl_h)/len(con_rl_h),3) if con_rl_h else rl_h_price
        con_rl_a_p = round(sum(con_rl_a)/len(con_rl_a),3) if con_rl_a else rl_a_price
        con_rl_h_p_25 = round(sum(con_rl_h_25)/len(con_rl_h_25),3) if con_rl_h_25 else rl_h_price_25
        con_rl_a_p_25 = round(sum(con_rl_a_25)/len(con_rl_a_25),3) if con_rl_a_25 else rl_a_price_25
        con_ov_p   = round(sum(con_over)/len(con_over),3) if con_over else over_price
        con_un_p   = round(sum(con_under)/len(con_under),3) if con_under else under_price

        pred    = predict(home,away,home_sp,away_sp,market_total=market_total,game_dt=game_dt)
        margin  = pred["margin"]
        dyn_std = pred["dyn_std"]
        h_model   = pred["home_win_prob"]; a_model = pred["away_win_prob"]
        conf      = pred["conf_factor"]    # ML/RL 信心（pure_total 基礎）
        conf_tot  = pred["conf_tot"]       # TOT 專用信心（pure_total_tot，降低RS影響）

        # 獨贏市場混合概率（用於 blend 過濾）
        inv_sum  = 1/con_h + 1/con_a
        h_mkt_nv = round((1/con_h)/inv_sum,4); a_mkt_nv = round((1/con_a)/inv_sum,4)
        h_blend  = MOD_W*h_model+MKT_W*h_mkt_nv; a_blend = MOD_W*a_model+MKT_W*a_mkt_nv

        # ── ★ 讓分概率（根據 API 實際 spread 方向）───────────
        # RL 使用更高不確定性（RL_STD_MULT），避免模型對接近場次過度樂觀
        rl_dyn_std = dyn_std * RL_STD_MULT
        h_gives = (rl_h_pts is None or rl_h_pts < 0)
        spread_val = abs(rl_h_pts) if rl_h_pts is not None else 1.5
        if h_gives:
            p_h_rl = runline_prob(margin, spread_val, rl_dyn_std)
        else:
            p_h_rl = runline_prob(margin, -spread_val, rl_dyn_std)
        p_h_rl = max(0.25, min(0.72, p_h_rl))
        p_a_rl = 1.0 - p_h_rl

        # ── ★ 2.5 讓分概率 ──────────────────────────────────────
        p_h_rl_25 = p_a_rl_25 = None
        h_gives_25 = True  # 預設主隊讓分
        if rl_h_price_25 is not None or rl_a_price_25 is not None:
            h_gives_25 = (rl_h_pts_25 is None or rl_h_pts_25 < 0)
            spread_val_25 = abs(rl_h_pts_25) if rl_h_pts_25 is not None else 2.5
            if h_gives_25:
                p_h_rl_25 = runline_prob(margin, spread_val_25, rl_dyn_std)
            else:
                p_h_rl_25 = runline_prob(margin, -spread_val_25, rl_dyn_std)
            p_h_rl_25 = max(0.20, min(0.75, p_h_rl_25))
            p_a_rl_25 = 1.0 - p_h_rl_25

        # ── ★ 大小分概率（50% 模型 + 50% 市場混合）─────────
        # 使用 pure_total_tot（RS權重極低），防止高RS誤拉高Over概率
        _tot_blend = pred["pure_total_tot"] * 0.50 + market_total * 0.50
        p_over  = over_prob(_tot_blend, market_total)
        p_under = 1.0 - p_over

        # ── ★ Devig：從共識賠率移除 bookmaker vig，得到真實市場隱含概率 ──
        # raw_edge = model_p - true_market_p（更準確量化真實優勢）
        _dv = {}
        if con_h>0 and con_a>0:
            _m = 1/con_h + 1/con_a
            _dv["home"] = round((1/con_h)/_m, 4); _dv["away"] = round((1/con_a)/_m, 4)
        if con_rl_h_p and con_rl_a_p and con_rl_h_p>0 and con_rl_a_p>0:
            _m = 1/con_rl_h_p + 1/con_rl_a_p
            _dv["rl_h"] = round((1/con_rl_h_p)/_m, 4); _dv["rl_a"] = round((1/con_rl_a_p)/_m, 4)
        if con_rl_h_p_25 and con_rl_a_p_25 and con_rl_h_p_25>0 and con_rl_a_p_25>0:
            _m25 = 1/con_rl_h_p_25 + 1/con_rl_a_p_25
            _dv["rl_h_25"] = round((1/con_rl_h_p_25)/_m25, 4); _dv["rl_a_25"] = round((1/con_rl_a_p_25)/_m25, 4)
        if con_ov_p and con_un_p and con_ov_p>0 and con_un_p>0:
            _m = 1/con_ov_p + 1/con_un_p
            _dv["over"] = round((1/con_ov_p)/_m, 4); _dv["under"] = round((1/con_un_p)/_m, 4)

        # ── ★ 建立所有候選注單並選最優 ──────────────────────
        BET_ML="獨贏"; BET_RL="讓分"; BET_TOT="大小分"
        candidates=[]
        if home_price: candidates.append((BET_ML,"home",home,home_price,home_book,h_model,EDGE_MIN,h_blend,con_h,1.00))
        if away_price: candidates.append((BET_ML,"away",away,away_price,away_book,a_model,EDGE_MIN,a_blend,con_a,1.00))
        if rl_h_price and con_rl_h_p: candidates.append((BET_RL,"rl_h",home,rl_h_price,rl_h_book,p_h_rl,EDGE_MIN_RL,None,con_rl_h_p,0.90))
        if rl_a_price and con_rl_a_p: candidates.append((BET_RL,"rl_a",away,rl_a_price,rl_a_book,p_a_rl,EDGE_MIN_RL,None,con_rl_a_p,0.90))
        if rl_h_price_25 and con_rl_h_p_25 and p_h_rl_25 is not None and not h_gives_25:
            candidates.append((BET_RL,"rl_h_25",home,rl_h_price_25,rl_h_book_25,p_h_rl_25,EDGE_MIN_RL,None,con_rl_h_p_25,0.88))
        if rl_a_price_25 and con_rl_a_p_25 and p_a_rl_25 is not None and h_gives_25:
            candidates.append((BET_RL,"rl_a_25",away,rl_a_price_25,rl_a_book_25,p_a_rl_25,EDGE_MIN_RL,None,con_rl_a_p_25,0.88))
        if over_price and con_ov_p:   candidates.append((BET_TOT,"over","over",over_price,over_book,p_over,EDGE_MIN_TOT,None,con_ov_p,0.88))
        if under_price and con_un_p:  candidates.append((BET_TOT,"under","under",under_price,under_book,p_under,EDGE_MIN_TOT,None,con_un_p,0.88))

        best_pick=None
        _h_era_v = get_pitcher_era(home_sp)
        _a_era_v = get_pitcher_era(away_sp)
        for btype,bside,bteam,bp,bk,model_p,edge_min,blend_p,con_p,conf_mult in candidates:
            if bp is None or bp<=0 or con_p is None or con_p<=0: continue
            # ★ TOT使用conf_tot（pure_total_tot基礎，RS影響更低）；ML/RL用conf
            _base_conf = conf_tot if btype == BET_TOT else conf
            bet_conf = _base_conf*conf_mult
            # ★ 分類型歷史勝率校正（需 ≥MIN_SAMPLE_CALIB 才生效，防小樣本過擬合）
            _wr_hist = wr_by_type.get(btype)
            if _wr_hist is not None:
                if   _wr_hist < 0.50: bet_conf = round(bet_conf * 0.90, 4)
                elif _wr_hist < 0.55: bet_conf = round(bet_conf * 0.95, 4)
                elif _wr_hist > 0.68: bet_conf = round(min(1.0, bet_conf * 1.05), 4)
            raw_edge = model_p - _dv.get(bside, 1/bp)  # ★ Devigged edge
            # ML: edge*conf ≥ threshold；RL/TOT: 直接比 raw_edge（EDGE_MIN 已較高）
            edge_ok = (raw_edge*bet_conf >= edge_min) if btype==BET_ML else (raw_edge >= edge_min)
            if not edge_ok: continue
            if bp<MIN_P or bp>MAX_P: continue
            if btype==BET_ML and (blend_p is None or blend_p<0.60): continue
            _mp_min = MIN_MODEL_P_RL if btype==BET_RL else (MIN_MODEL_P_TOT if btype==BET_TOT else MIN_MODEL_P_ML)
            if model_p < _mp_min: continue
            if bet_conf<0.65: continue
            if btype == BET_ML and bet_conf < ML_BET_CONF_MIN: continue  # ML 同RL，過濾邊際低賠
            if btype == BET_RL and bet_conf < RL_BET_CONF_MIN: continue  # RL 需更高信心
            # ML低賠保護：賠率<1.65（損益平衡≥60.6%），需更大的devigged edge
            if btype == BET_ML and bp < 1.65 and raw_edge < EDGE_MIN_ML_FAV: continue
            # ── ★ RL 保護層（依序：信心→TBD→爆冷→王牌→菁英對決）──
            if btype == BET_RL:
                # ① TBD 投手：ERA預設值不可靠，不推薦讓分受讓
                if bside in ("rl_a","rl_a_25") and not home_sp:
                    continue
                if bside in ("rl_h","rl_h_25") and not away_sp:
                    continue
                _era_diff = _h_era_v - _a_era_v  # 正值=主隊投手較弱
                _margin   = pred["margin"]        # 正值=主隊模型預期較強
                if bside in ("rl_a","rl_a_25"):
                    # ② 爆冷保護：客隊弱投手 + ERA差大 + 模型分差大
                    if _era_diff < -BLOWOUT_ERA_DIFF and _a_era_v >= BLOWOUT_ERA_POOR and _margin > 1.2:
                        continue
                    # ③ 王牌封殺：面對 ERA≤2.70 王牌，客隊幾乎無法得分
                    if _h_era_v <= ACE_ERA_RL:
                        continue
                    # ④ FIP回歸保護：客隊推薦隊SP的FIP遠高於ERA → 幸運ERA不可持續，RL風險高
                    _rl_sp_fip = _PITCHER_FIP.get(away_sp)
                    _rl_sp_era_raw = _RECENT_ERA.get(away_sp)
                    if (_rl_sp_fip and _rl_sp_era_raw and
                            (_rl_sp_fip - _rl_sp_era_raw) > FIP_ERA_WARN_GAP):
                        log.info("RL blocked FIP-ERA gap: %s gap=%.2f (FIP=%.2f ERA=%.2f)",
                                 away_sp, _rl_sp_fip - _rl_sp_era_raw, _rl_sp_fip, _rl_sp_era_raw)
                        continue
                elif bside in ("rl_h","rl_h_25"):
                    # ② 爆冷保護：主隊弱投手 + ERA差大 + 模型分差大
                    if _era_diff > BLOWOUT_ERA_DIFF and _h_era_v >= BLOWOUT_ERA_POOR and _margin < -1.2:
                        continue
                    # ③ 王牌封殺：面對 ERA≤2.70 王牌，主隊幾乎無法得分
                    if _a_era_v <= ACE_ERA_RL:
                        continue
                    # ④ FIP回歸保護：主隊推薦隊SP的FIP遠高於ERA → 幸運ERA不可持續，RL風險高
                    _rl_sp_fip = _PITCHER_FIP.get(home_sp)
                    _rl_sp_era_raw = _RECENT_ERA.get(home_sp)
                    if (_rl_sp_fip and _rl_sp_era_raw and
                            (_rl_sp_fip - _rl_sp_era_raw) > FIP_ERA_WARN_GAP):
                        log.info("RL blocked FIP-ERA gap: %s gap=%.2f (FIP=%.2f ERA=%.2f)",
                                 home_sp, _rl_sp_fip - _rl_sp_era_raw, _rl_sp_fip, _rl_sp_era_raw)
                        continue
            # ── ★ 菁英對決保護：雙方ERA均優時，OVER門檻提高 ──
            # 若雙SP ERA < 3.50，RS易誤拉高total，需更高p_over才下Over
            if btype == BET_TOT and bside == "over":
                if _h_era_v < ELITE_ERA_DUAL and _a_era_v < ELITE_ERA_DUAL:
                    if model_p < ELITE_ERA_OVER_P:
                        continue
            # ── ★ UNDER 保護層（依序：TBD→牛棚投手→低局數→高WHIP）──
            if btype == BET_TOT and bside == "under":
                # ① TBD先發：不知道誰上場幾局，UNDER風險極高，直接拒絕
                if not home_sp or not away_sp:
                    continue
                # ② 牛棚型投手擔任先發：ERA不具整場代表性，拒絕UNDER
                if home_sp in _RELIEVER_FLAGS or away_sp in _RELIEVER_FLAGS:
                    continue
                # ③ 場均局數不足（開場/短局型）：牛棚投球局數多，UNDER風險高
                _h_avgip = _PITCHER_IP.get(home_sp, 6.0)
                _a_avgip = _PITCHER_IP.get(away_sp, 6.0)
                if min(_h_avgip, _a_avgip) < MIN_SP_IP_UNDER:
                    if model_p < MIN_MODEL_P_TOT + UNDER_LOW_IP_EXTRA:
                        continue
                # ④ 高WHIP先發：上壘率高，UNDER有較高失分風險
                _h_whip = _PITCHER_WHIP.get(home_sp)
                _a_whip = _PITCHER_WHIP.get(away_sp)
                if ((_h_whip is not None and _h_whip > UNDER_WHIP_THRESH) or
                        (_a_whip is not None and _a_whip > UNDER_WHIP_THRESH)):
                    if model_p < MIN_MODEL_P_TOT + UNDER_WHIP_EXTRA:
                        continue
                # ⑤ FIP回歸保護：任一SP的FIP遠高於ERA → 幸運ERA，失分回歸風險，拒絕UNDER
                _h_fip_raw = _PITCHER_FIP.get(home_sp)
                _a_fip_raw = _PITCHER_FIP.get(away_sp)
                _h_era_raw = _RECENT_ERA.get(home_sp)
                _a_era_raw = _RECENT_ERA.get(away_sp)
                if (_h_fip_raw and _h_era_raw and
                        (_h_fip_raw - _h_era_raw) > FIP_ERA_UNDER_GAP):
                    log.info("UNDER blocked FIP-ERA gap: %s gap=%.2f (FIP=%.2f ERA=%.2f)",
                             home_sp, _h_fip_raw - _h_era_raw, _h_fip_raw, _h_era_raw)
                    continue
                if (_a_fip_raw and _a_era_raw and
                        (_a_fip_raw - _a_era_raw) > FIP_ERA_UNDER_GAP):
                    log.info("UNDER blocked FIP-ERA gap: %s gap=%.2f (FIP=%.2f ERA=%.2f)",
                             away_sp, _a_fip_raw - _a_era_raw, _a_fip_raw, _a_era_raw)
                    continue
                # ⑥ K/9 加成：雙方高三振 → UNDER更有利（三振=少安打少跑壘）
                _h_k9 = _PITCHER_K9.get(home_sp, 7.0)
                _a_k9 = _PITCHER_K9.get(away_sp, 7.0)
                if _h_k9 >= K9_HIGH_THRESH and _a_k9 >= K9_HIGH_THRESH:
                    bet_conf = min(1.0, bet_conf + K9_UNDER_CONF)
            # ── ★ 市場品質：bookmaker數不足時降低信心（非流動市場賠率不可靠）──
            if btype == BET_ML:
                _n_books = len(con_h_prices) if bside=="home" else len(con_a_prices)
            elif btype == BET_RL:
                _n_books = len(con_rl_h) if bside in ("rl_h","rl_h_25") else len(con_rl_a)
            else:
                _n_books = len(con_over) if bside=="over" else len(con_under)
            if _n_books < MIN_BOOKS:
                bet_conf = round(bet_conf * LOW_BOOKS_CONF, 4)
            # ── 線路 CLV 過濾：有前次賠率才比較，無資料直接放行 ──
            prev_bp = prev_game.get(_SIDE_KEY.get(bside,""))
            lclv = line_clv(bp, prev_bp)
            if lclv is not None and lclv < LINE_CLV_MIN: continue
            _dv_p_kelly = _dv.get(bside, 1.0/con_p) if con_p else None
            stake = kelly_stake(raw_edge, model_p, bp, conf=bet_conf, dv_p=_dv_p_kelly)
            if btype == BET_RL:
                # RL 下注降低25%、上限100（不確定性更高）
                stake = round(min(max(KELLY_MIN, stake * RL_KELLY_MULT), RL_KELLY_MAX), 1)
            elif btype == BET_ML and bp < ML_FAV_PRICE:
                # ML低賠（損益平衡高）：Kelly縮水20%，降低高break-even場次的曝險
                stake = round(max(KELLY_MIN, stake * ML_FAV_KELLY), 1)
            if stake < KELLY_MIN: continue
            score = raw_edge * bet_conf
            # ④ 菁英對決中RL降分，讓TOT注單更容易獲選（偏好UNDER而非RL）
            if btype == BET_RL and _h_era_v < ELITE_ERA_DUAL and _a_era_v < ELITE_ERA_DUAL:
                score *= 0.80
            if best_pick is None or score>best_pick["score"]:
                best_pick={"btype":btype,"bside":bside,"bteam":bteam,
                           "bp":bp,"bk":bk,"model_p":model_p,"lclv":lclv,
                           "raw_edge":raw_edge,"bet_conf":bet_conf,
                           "con_p":con_p,"stake":stake,"score":score}

        if best_pick is None: continue

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
        lclv     = best_pick.get("lclv")  # 線路 CLV（%），None = 首次出現無前次資料

        if raw_edge>=0.18 and bet_conf>=0.88:   tier="💎 頂級"
        elif raw_edge>=0.15 and bet_conf>=0.80: tier="🔥 強力"
        else:                                   tier="⭐ 穩定"

        # 預先計算歷史紀錄所需的 label（RL=讓分點數, TOT=OVER/UNDER, ML=""）
        if btype==BET_RL:
            if bside in ("rl_h","rl_h_25"):
                _h_pt = (rl_h_pts_25 if bside=="rl_h_25" and rl_h_pts_25 is not None
                         else (rl_h_pts if rl_h_pts is not None else (-2.5 if bside=="rl_h_25" else -1.5)))
                _hist_label = ("%.4g"%_h_pt if _h_pt<0 else "+%.4g"%_h_pt)
            else:
                _h_pt = (rl_h_pts_25 if bside=="rl_a_25" and rl_h_pts_25 is not None
                         else (rl_h_pts if rl_h_pts is not None else (-2.5 if bside=="rl_a_25" else -1.5)))
                _hist_label = ("+%.4g"%-_h_pt if -_h_pt>0 else "%.4g"%-_h_pt)
        elif btype==BET_TOT:
            _hist_label = "OVER" if bside=="over" else "UNDER"
        else:
            _hist_label = ""

        acn=CN.get(away,away); hcn=CN.get(home,home)
        h_sp_n = sp_info.get("home_name","TBD") if sp_info else "TBD"
        a_sp_n = sp_info.get("away_name","TBD") if sp_info else "TBD"
        h_era=get_pitcher_era(home_sp); a_era=get_pitcher_era(away_sp)
        def _sp_tag(sp_key, era, rs_pitcher, team_rpg, in_recent):
            if not sp_key: return ""
            pfx = "近期" if in_recent else ""
            # ── ERA + FIP（FIP與ERA差距>0.5時才顯示，過濾噪音）──
            fip_val = _PITCHER_FIP.get(sp_key)
            if fip_val and abs(fip_val - era) >= 0.50:
                era_tag = "(%sERA%.2f/FIP%.2f)" % (pfx, era, fip_val)
            else:
                era_tag = "(%sERA%.2f)" % (pfx, era)
            # ── K/9（≥8.5才顯示，突出高三振型投手）──
            k9_val = _PITCHER_K9.get(sp_key)
            k9_tag = " K9:%.1f"%k9_val if k9_val and k9_val >= 8.5 else ""
            # ── 角色標記：牛棚警示 / 場均局數（低於5局加⚠️）──
            if sp_key in _RELIEVER_FLAGS:
                role_tag = " ⚠️牛棚"
            elif sp_key in _PITCHER_IP:
                ip_val = _PITCHER_IP[sp_key]
                role_tag = (" ⚠️%.1fIP" % ip_val) if ip_val < MIN_SP_IP_UNDER else (" %.1fIP" % ip_val)
            else:
                role_tag = ""
            # ── 休息天數（短休/長休才顯示警示）──
            rest_d = get_rest_days(sp_key)
            if rest_d is not None:
                if rest_d <= REST_SHORT_DAYS:   rest_tag = " 短休%dd⚠️" % rest_d
                elif rest_d >= REST_LONG_DAYS:  rest_tag = " 長休%dd⚠️" % rest_d
                else:                           rest_tag = ""
            else:
                rest_tag = ""
            # ── Run Support ──
            if rs_pitcher is not None:
                rs_tag = " RS%.1f" % rs_pitcher
            else:
                rs_tag = " 隊%.1f" % team_rpg if team_rpg else ""
            return era_tag + k9_tag + role_tag + rest_tag + rs_tag
        h_tag = _sp_tag(home_sp, h_era, pred.get("h_rs"), pred.get("h_team_rpg"), home_sp in _RECENT_ERA)
        a_tag = _sp_tag(away_sp, a_era, pred.get("a_rs"), pred.get("a_team_rpg"), away_sp in _RECENT_ERA)
        h_sp_str=h_sp_n+h_tag; a_sp_str=a_sp_n+a_tag

        cf_note=" ⚠️信心%.0f%%"%(bet_conf*100) if bet_conf<0.85 else ""
        pf_note=" 🏟️PF%.2f"%pred["park_factor"] if abs(pred["park_factor"]-1.0)>0.05 else ""
        ou_diff=pred["model_total"]-market_total
        if   ou_diff>1.5:  ou_str="OVER偏向(%.1f/%.1f)"%(pred["model_total"],market_total)
        elif ou_diff<-1.5: ou_str="UNDER偏向(%.1f/%.1f)"%(pred["model_total"],market_total)
        else:              ou_str="大小分中性(%.1f/%.1f)"%(pred["model_total"],market_total)

        # 依注單類型產生推薦描述與統計行
        if btype==BET_ML:
            bcn=CN.get(bteam,bteam)
            bet_desc="`%s 獨贏` @ **%.2f** (%s)"%(bcn,bp,bk)
            # ★ 使用 devigged 真實市場概率（已移除 bookmaker vig）
            _mkt_true_p = _dv.get(bside, 1.0/con_p) * 100
            _break_even = (1.0/bp)*100
            stats_ln="> 共識賠率: %.2f | 真實市場: %.1f%% | 盈虧平衡: %.1f%% | 模型: %.1f%%"%(
                con_p, _mkt_true_p, _break_even, model_p*100)
            mkt_tag=""
        elif btype==BET_RL:
            bcn=CN.get(bteam,bteam)
            # 根據實際 API spread 決定標籤（支援 1.5 及 2.5）
            if bside=="rl_h_25":
                h_pt_raw = rl_h_pts_25 if rl_h_pts_25 is not None else -2.5
            elif bside=="rl_h":
                h_pt_raw = rl_h_pts if rl_h_pts is not None else -1.5
            elif bside=="rl_a_25":
                h_pt_raw = rl_h_pts_25 if rl_h_pts_25 is not None else -2.5
            else:
                h_pt_raw = rl_h_pts if rl_h_pts is not None else -1.5
            if bside in ("rl_h","rl_h_25"):
                pts_str = "%.4g" % h_pt_raw
            else:
                pts_str = "%.4g" % (-h_pt_raw)
            if not pts_str.startswith("-"): pts_str = "+"+pts_str
            if bside in ("rl_h_25","rl_a_25"):
                con_h_p_use = con_rl_h_p_25; con_a_p_use = con_rl_a_p_25
            else:
                con_h_p_use = con_rl_h_p; con_a_p_use = con_rl_a_p
            rl_inv=(1/con_h_p_use+1/con_a_p_use) if (con_h_p_use and con_a_p_use) else 1.0
            mkt_rl_p=(1/con_p)/rl_inv if rl_inv>0 else 1/con_p
            bet_desc="`%s 讓分(%s)` @ **%.2f** (%s)"%(bcn,pts_str,bp,bk)
            stats_ln="> 共識賠率: %.2f | 讓分勝率: %.1f%% | 市場隱含: %.1f%%"%(con_p,model_p*100,mkt_rl_p*100)
            mkt_tag=" [讓分]"
        else:  # BET_TOT
            ov_un="OVER" if bside=="over" else "UNDER"
            tot_inv=(1/con_ov_p+1/con_un_p) if (con_ov_p and con_un_p) else 1.0
            mkt_tot_p=(1/con_p)/tot_inv if tot_inv>0 else 1/con_p
            bet_desc="`%s %.1f` @ **%.2f** (%s)"%(ov_un,market_total,bp,bk)
            stats_ln="> 共識賠率: %.2f | 模型總分: %.1f | 市場隱含: %.1f%%"%(con_p,pred["pure_total_tot"],mkt_tot_p*100)
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

        msg_lines=[
            "**%s  %s @ %s**"%(tier,acn,hcn),
            "🕐 %s %s (台灣時間)%s%s"%(game_date_str[5:].replace("-","/"),game_time_str,pf_note,mkt_tag),
            "⚾ 先發: %s — %s"%(a_sp_str,h_sp_str),
            "💰 推薦: %s"%bet_desc,
            stats_ln,
            "> Edge: **%+.1f%%**%s | Kelly: $%.1f%s"%(
                raw_edge*100,cf_note,stake,
                " | 線路CLV: **%+.1f%%**"%lclv if lclv is not None else " | 線路CLV: 首次出現"),
        ]
        if last_line: msg_lines.append(last_line)
        msg="\n".join(msg_lines)+"\n"

        gk=(home,away)
        ex=next((i for i,p in enumerate(picks) if (p["home"],p["away"])==gk),None)
        _pick = {"msg":msg,"tier":tier,"team":str(bteam),"home":home,"away":away,
                 "edge":raw_edge,"conf":bet_conf,"stake":stake,"score":best_pick["score"],
                 "clv":round(raw_edge*100,1),"line_clv":lclv,
                 "game_date":game_date_str,"game_time":game_time_str,"game_dt":game_dt,
                 "btype":btype,"bp":bp,"bk":bk,"con_p":con_p,"model_p":model_p,
                 "dv_p": round(_dv.get(bside, 1.0/con_p), 4),  # ★ devigged 真實市場概率
                 "away_cn":acn,"home_cn":hcn,"bet_label":bet_desc.replace("`","").split("@")[0].strip(),
                 "away_sp_name":away_sp or "TBD","home_sp_name":home_sp or "TBD",
                 "away_sp_full":a_sp_n,"home_sp_full":h_sp_n,  # ★ 完整姓名（顯示用）
                 "away_era":round(a_era,2),"home_era":round(h_era,2),
                 "away_rs": round(pred.get("a_rs"),2) if pred.get("a_rs") is not None else None,
                 "home_rs": round(pred.get("h_rs"),2) if pred.get("h_rs") is not None else None,
                 "away_rpg":round(pred.get("a_team_rpg",4.5),2),
                 "home_rpg":round(pred.get("h_team_rpg",4.5),2),
                 "pred_away":round(pred.get("a_expected",0),1),"pred_home":round(pred.get("h_expected",0),1),
                 "model_total":round(pred.get("pure_total_tot",0),1) if btype==BET_TOT else None,
                 "market_total":market_total if btype==BET_TOT else None,
                 "park_factor":round(pred.get("park_factor",1.0),2) if abs(pred.get("park_factor",1.0)-1.0)>0.05 else None,
                 "hist_label":_hist_label,
                 "hist_mkt_total":market_total if btype==BET_TOT else None}
        if ex is not None:
            if best_pick["score"]>picks[ex].get("score",0):
                picks[ex]=_pick
        else:
            picks.append(_pick)

    # 當天比賽優先，同日純按 CLV（score）降序排列，讓輸出穩定
    picks.sort(key=lambda x:(0 if x["game_date"]==today_str else 1,
                              -x.get("score", x.get("edge",0)),
                              x["game_date"],
                              x.get("game_dt") or datetime.datetime.min))
    picks = picks[:MAX_PICKS]  # 只取 CLV 最高的前 N 場

    # ★ RL濃度控制：每日RL推薦不超過 MAX_RL_PICKS 場（防同日過度集中）
    _rl_cnt = 0
    _filtered = []
    for p in picks:
        if p.get("btype") == "讓分":
            if _rl_cnt < MAX_RL_PICKS:
                _filtered.append(p); _rl_cnt += 1
        else:
            _filtered.append(p)
    picks = _filtered

    # ★ 相關性折扣：同方向多注 第二注起縮注20%（UNDER/OVER分別計算，防高度相關虧損）
    _under_seen = 0
    _over_seen  = 0
    for p in picks:
        _is_under = p.get("btype")=="大小分" and "UNDER" in p.get("bet_label","")
        _is_over  = p.get("btype")=="大小分" and "OVER"  in p.get("bet_label","")
        if _is_under:
            _under_seen += 1
            if _under_seen > 1:
                old_s = p["stake"]
                p["stake"] = round(max(KELLY_MIN, old_s * CORR_DAMP_W), 1)
                p["msg"]   = re.sub(r"Kelly: \$[0-9.]+(?:\s*\[[^\]]*\])?",
                                    "Kelly: $%.1f [📊相關折]"%p["stake"], p["msg"], count=1)
        if _is_over:
            _over_seen += 1
            if _over_seen > 1:
                old_s = p["stake"]
                p["stake"] = round(max(KELLY_MIN, old_s * CORR_DAMP_W), 1)
                p["msg"]   = re.sub(r"Kelly: \$[0-9.]+(?:\s*\[[^\]]*\])?",
                                    "Kelly: $%.1f [📊相關折]"%p["stake"], p["msg"], count=1)

    # ★ 低迷縮注：近N注勝率過低，Kelly全局折扣（保護本金）
    if _slump_mult < 1.0:
        log.info("Slump mode: Kelly x%.2f applied to all picks", _slump_mult)
        for p in picks:
            old_s = p["stake"]
            p["stake"] = round(max(KELLY_MIN, old_s * _slump_mult), 1)
            p["msg"] = re.sub(r"Kelly: \$[0-9.]+(?:\s*\[[^\]]*\])?",
                              "Kelly: $%.1f [📉低迷]"%p["stake"], p["msg"], count=1)

    # ★ 每日總曝險上限：超過 MAX_DAILY_STAKE 按比例縮注
    _total_stake = sum(p["stake"] for p in picks)
    if _total_stake > MAX_DAILY_STAKE:
        _ratio = MAX_DAILY_STAKE / _total_stake
        log.info("Daily cap: total_stake %.1f > %.1f, ratio=%.2f", _total_stake, MAX_DAILY_STAKE, _ratio)
        for p in picks:
            old_s = p["stake"]
            p["stake"] = round(max(KELLY_MIN, old_s * _ratio), 1)
            p["msg"] = re.sub(r"Kelly: \$[0-9.]+(?:\s*\[[^\]]*\])?",
                              "Kelly: $%.1f [🔒限額]"%p["stake"], p["msg"], count=1)

    # ★ 歷史紀錄只寫入最終顯示的注單（過濾後），避免被拒之注單汙染勝率統計
    if official:
        for p in picks:
            if p["game_date"] != today_str: continue
            rk = (p["home"], p["away"], today_str)
            already_in_hist  = any((r.get("home"),r.get("away"),r.get("date"))==rk for r in hist)
            already_in_today = any((r.get("home"),r.get("away"),r.get("date"))==rk for r in today_records)
            if not already_in_hist and not already_in_today:
                today_records.append({
                    "date":    today_str,
                    "team":    p["team"],
                    "home":    p["home"],
                    "away":    p["away"],
                    "price":   round(p["bp"], 2),
                    "stake":   round(p["stake"], 1),
                    "edge":    round(p["edge"], 4),
                    "conf":    round(p["conf"], 3),
                    "bet_type":p["btype"],
                    "result":  None,
                    "label":   p.get("hist_label",""),
                    "market_total": p.get("hist_mkt_total"),
                })

    total_settled,wins,wr=calc_perf(hist)
    now_str  = now_tw.strftime("%m/%d %H:%M")
    espn_str = "✅ESPN" if espn_ok else "⚠️BASE"
    il_str   = {"rotowire":"✅RotoWire","static":"⚠️靜態"}.get(il_src,il_src)
    sp_str   = "✅已取得" if pitchers else "❌未取得"
    era_str  = ("✅近期ERA(%d%s)" % (len(_RECENT_ERA),
                "/⚠️%d牛棚" % len(_RELIEVER_FLAGS) if _RELIEVER_FLAGS else "")
                if _RECENT_ERA else "⚠️賽季ERA")

    # ★ 分類型歷史統計（勝率 + ROI，用於頁尾顯示）
    _type_stats = []
    for _btname, _btkey in [("ML","獨贏"),("RL","讓分"),("TOT","大小分")]:
        _settled_t = [r for r in hist if r.get("result") in ("W","L") and r.get("bet_type")==_btkey]
        if len(_settled_t) >= 5:
            _w_t   = sum(1 for r in _settled_t if r["result"]=="W")
            _wr_t  = _w_t / len(_settled_t) * 100
            _in_t  = sum(r.get("stake",0) for r in _settled_t)
            _pnl_t = sum(r.get("stake",0)*(r.get("price",2)-1) if r["result"]=="W"
                         else -r.get("stake",0) for r in _settled_t)
            _roi_t = _pnl_t / _in_t * 100 if _in_t > 0 else 0
            _type_stats.append("%s %d/%d(%.0f%% ROI%+.0f%%)" % (
                _btname, _w_t, len(_settled_t), _wr_t, _roi_t))
    _type_stats_str = " | ".join(_type_stats) if _type_stats else ""

    lines=[
        "⚾ **MLB V2 分析報告**",
        "🕐 %s | %s %s %s %s"%(now_str,espn_str,il_str,sp_str,era_str),
        "📌 正式記錄 (00–07時)" if official else "🔧 測試模式 (不寫gist)",
        "📊 歷史: %d勝/%d場 (%.1f%%)%s"%(wins,total_settled,wr,
            "  [%s]"%_type_stats_str if _type_stats_str else ""),
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
                p_ov=over_prob(pr.get("pure_total_tot", pr["pure_total"]),mt)
                tot_he=p_ov-1/ov_p; tot_ue=(1-p_ov)-1/un_p; tot_be=max(tot_he,tot_ue)
                if tot_be*0.88>be: be=tot_be; bp2=ov_p if tot_he>=tot_ue else un_p; best_lbl="TOT"
            diag.append("`%s@%s` [%s] Edge=%+.1f%% P=%.2f conf=%.0f%% SP:%s/%s"%(
                CN.get(a,a),CN.get(h,h),best_lbl,be*100,bp2,cf*100,hp_k or "?",ap_k or "?"))
        for d in sorted(diag,key=lambda x:-float(x.split("Edge=")[1].split("%")[0])): lines.append(d)
    else:
        lines.append("**推薦 %d 場（💎強→⭐弱 排序）**"%len(picks))
        for p in picks: lines.append(p["msg"])

    lines+=[
        "═"*20,
        "• Poisson大小分 · ERA+FIP混合(去BABIP) · K/9 · WHIP · 場均IP · 休息天數 · 球場PF · 傷兵",
        "• Devig真實市場概率 · 三市場選優(ML/RL/TOT) · Kelly下注 · 每日最多%d推薦 · 每日曝險≤$%d"%( MAX_PICKS, int(MAX_DAILY_STAKE)),
        "• RL多層保護 · UNDER(TBD/牛棚/低IP/WHIP/K9) · OVER/UNDER相關折 · 低迷縮注 · BM品質過濾",
    ]

    out="\n".join(lines)
    write_pages_json(picks, hist, now_tw)
    save_odds_snapshot(new_snap)
    if official and today_records: save_hist(hist+today_records)
    log.info("Sending %d chars",len(out))
    send(out)
    log.info("Done")


if __name__ == "__main__":
    run()
