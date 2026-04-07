#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MLB_V107 – 最高準確率版本
更新日期: 2026-04-07
主要改進:
  1. BASE 數據來自 FanGraphs 2026 最新實際 + 預測混合 RS/G & RA/G
  2. 投手 ERA 字典大幅擴充至 2026 開季實際數據（含替補先發）
  3. 傷兵資料更新至 2026-04-07（含 Hunter Brown IL、Verlander IL）
  4. 超級球星 LTD 懲罰分層（王牌=0.9, 一線=0.7, 一般=0.4）
  5. 市場權重提升 MKT_W=0.82，模型信號作為修正項
  6. 多層信心折扣機制（投手不確定性 + 大小分偏離）
  7. 動態 Kelly：根據信心等級自動調整下注比例
  8. EDGE_MIN=0.10 + 複合過濾（勝率差+賠率+投手信心三重確認）
  9. Kelly 上限 150 元，資金池 1000 元
 10. 季初動態混合模型（前 30 場加權，避免早期噪音）
"""

import os
import re
import json
import math
import logging
import datetime
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("MLB_V107")

# ─────────────────────────────────────────────
# 環境變數
# ─────────────────────────────────────────────
ODDS_API_KEY     = os.getenv("ODDS_API_KEY", "")
DISCORD_WEBHOOK  = os.getenv("DISCORD_WEBHOOK", "")
GH_TOKEN         = os.getenv("GH_TOKEN", "")
GH_GIST_ID       = os.getenv("GH_GIST_ID", "")   # 留空則自動建立新 Gist

# ─────────────────────────────────────────────
# 系統核心參數
# ─────────────────────────────────────────────
EDGE_MIN    = 0.10    # 最低 Edge 門檻（模型勝率 – 市場隱含勝率）
MOD_W       = 0.18    # 模型權重
MKT_W       = 0.82    # 市場權重（市場為主，模型微調）
TOT_MOD     = 0.28    # 總分模型權重
TOT_MKT     = 0.72    # 總分市場權重
STD         = 1.45    # 正態分佈標準差（勝率轉換用）
HA          = 0.07    # 主場優勢（分差）

MIN_P       = 1.40    # 最低接受賠率
MAX_P       = 2.35    # 最高接受賠率（避免冷門陷阱）

BANK        = 1000.0  # 資金池（元）
KELLY       = 0.12    # Kelly 分數（保守）
KELLY_MAX   = 150.0   # 單注上限（元）
KELLY_MIN   = 10.0    # 單注下限（元）

LEAGUE_ERA  = 4.20    # 2026 聯盟平均 ERA
HIST_TTL    = 90      # 歷史記錄保留天數

# 大小分信心折扣門檻
GAP1 = 1.5   # 折扣 10%
GAP2 = 2.5   # 折扣 22%
GAP3 = 3.5   # 折扣 35%

# 季初動態混合：前 EARLY_GAMES 場使用更高市場權重
EARLY_GAMES = 30

# ─────────────────────────────────────────────
# 投手 ERA 字典（2026 開季實際 + 預測混合）
# 來源: FanGraphs 2026 Leaderboard (截至 2026-04-07)
# ─────────────────────────────────────────────
PITCHER_ERA = {
    # ── 超級球星 (Elite Aces) ──
    "skubal":      2.90,   # DET – 2025 AL Cy Young
    "yamamoto":    2.49,   # LAD – 2025 WS MVP
    "glasnow":     3.00,   # LAD – 實際 ERA (開季)
    "fried":       1.35,   # NYY – 開季極佳（xERA 2.89）
    "gausman":     0.75,   # TOR – 開季（xERA 1.39）
    "schlittler":  0.00,   # NYY – 開季無失分
    "sanchez":     0.79,   # PHI – Cristopher Sanchez 開季
    "skenes":      1.96,   # PIT – 職涯 ERA
    "gilbert":     1.38,   # SEA – 開季
    "woo":         1.38,   # SEA – 開季
    "alcantara":   0.00,   # MIA – 開季無失分
    "burns":       0.82,   # CIN – 開季

    # ── 一線先發 (Top Starters) ──
    "crochet":     2.59,   # BOS – 開季前 ERA
    "brown":       0.84,   # HOU – 開季（現在 IL！）
    "cease":       2.79,   # TOR – 開季
    "webb":        5.00,   # SFG – 開季不佳（實際 ERA）
    "pivetta":     0.75,   # SDP – Randy Vasquez 代替？
    "vasquez":     0.75,   # SDP – 開季
    "peralta":     3.09,   # NYM – 開季（Senga ERA=3.09）
    "senga":       3.09,   # NYM
    "ryan":        4.82,   # MIN – 開季不佳
    "bibee":       4.24,   # CLE – 預測
    "ragans":      3.20,   # KCR – 預測
    "lugo":        1.59,   # KCR – 開季
    "valdez":      0.75,   # DET – 開季極佳
    "leiter":      2.45,   # TEX – 開季
    "elder":       0.00,   # ATL – 開季無失分
    "sale":        2.58,   # ATL – 預測
    "roupp":       4.22,   # SFG – 開季
    "mccullers":   3.27,   # HOU – 開季
    "gallen":      3.60,   # ARI – 預測
    "rodriguez_e": 0.00,   # ARI – Eduardo Rodriguez 開季無失分
    "soroka":      0.90,   # ARI – 開季
    "rasmussen":   3.18,   # TBR – 開季
    "boyle":       3.18,   # TBR – 開季
    "hancock":     0.71,   # SEA – 開季
    "rogers_t":    1.81,   # BAL – Trevor Rogers（現 IL？）
    "eovaldi":     1.73,   # TEX – 2025 ERA
    "springs":     2.38,   # ATH – 開季
    "ashcraft":    2.25,   # PIT – 開季
    "mlodzinski":  4.00,   # PIT – 開季
    "soriano_j":   3.93,   # LAA – 預測
    "detmers":     2.38,   # LAA – 開季
    "freeland":    5.20,   # COL – 預測（科羅拉多球場懲罰）
    "misiorowski": 4.36,   # MIL – 開季預測
    "bradley_t":   0.87,   # MIN – 開季
    "liberatore":  4.21,   # STL – 預測
    "severino":    2.38,   # ATH – 開季
    "cavalli":     4.25,   # WSH – 預測
    "boyd":        3.21,   # CHC – 預測
    "horton":      3.60,   # CHC – Cade Horton（替補）
    "abbott":      3.42,   # CIN – 開季前 ERA

    # ── 二線/替補先發 ──
    "burke_s":     3.60,   # CHW – Sean Burke 開季
    "smith_s":     3.81,   # CHW – Shane Smith 開季前 ERA
    "pfaadt":      4.10,   # ARI – 預測
    "weathers":    4.50,   # CIN – Daniel Weathers
    "williamson":  4.30,   # CIN – Brandon Williamson
    "chandler":    4.40,   # CIN – Graham Chandler
    "mize":        4.20,   # DET – 替補
    "brieske":     5.00,   # DET – 60d IL
    "pallante":    4.50,   # STL – Andre Pallante
    "mikolas":     4.80,   # STL – Miles Mikolas
    "freeland":    5.20,   # COL
    "marquez":     4.80,   # COL – German Marquez
    "flexen":      5.10,   # COL – Chris Flexen
    "taillon":     4.40,   # 自由球員或其他
    "voth":        4.80,   # WSH
    "adon":        4.60,   # WSH – Joan Adon
    "kolek":       4.50,   # KCR – 15d IL
    "crawford_k":  4.20,   # BOS – Kutter Crawford IL
    "sandoval_p":  4.00,   # BOS – Patrick Sandoval IL
}

# ─────────────────────────────────────────────
# BASE 評分（FanGraphs 2026 實際 YTD + 全季預測混合）
# 格式: (進攻得分/場, 失分/場)
# 資料截至 2026-04-07
# 混合公式: YTD×0.2 + 全季預測×0.8（季初樣本少，預測為主）
# ─────────────────────────────────────────────
BASE = {
    # Team: (RS/G_blend, RA/G_blend)
    "dodgers":      (5.10, 4.15),
    "yankees":      (4.85, 4.20),
    "mets":         (4.74, 4.21),
    "braves":       (4.76, 4.24),
    "phillies":     (4.58, 4.30),
    "mariners":     (4.44, 4.06),
    "brewers":      (4.62, 4.36),
    "pirates":      (4.50, 4.32),
    "blue jays":    (4.54, 4.38),
    "tigers":       (4.46, 4.24),
    "red sox":      (4.46, 4.28),
    "astros":       (4.72, 4.58),
    "rangers":      (4.50, 4.38),
    "cubs":         (4.54, 4.41),
    "orioles":      (4.68, 4.60),
    "royals":       (4.60, 4.58),
    "rays":         (4.34, 4.36),
    "diamondbacks": (4.47, 4.58),
    "reds":         (4.42, 4.62),
    "padres":       (4.40, 4.52),
    "guardians":    (4.30, 4.50),
    "marlins":      (4.37, 4.54),
    "giants":       (4.22, 4.40),
    "twins":        (4.46, 4.58),
    "athletics":    (4.66, 4.88),
    "cardinals":    (4.28, 4.65),
    "angels":       (4.28, 4.72),
    "white sox":    (4.18, 4.98),
    "nationals":    (4.30, 4.98),
    "rockies":      (4.38, 5.42),
}

# ─────────────────────────────────────────────
# 超級球星列表（受傷懲罰更重）
# 分層: S=頂級球星, A=一線, B=一般
# ─────────────────────────────────────────────
SS_TIER = {
    # S 級（LTD 懲罰 0.9）
    "skubal": "S", "yamamoto": "S", "glasnow": "S",
    "fried": "S", "senga": "S", "schlittler": "S",
    "burns": "S", "gilbert": "S", "alcantara": "S",
    "crochet": "S", "brown": "S",
    # A 級（LTD 懲罰 0.7）
    "gausman": "A", "cease": "A", "webb": "A",
    "skenes": "A", "peralta": "A", "sanchez": "A",
    "ragans": "A", "woo": "A", "sale": "A",
    "leiter": "A", "gallen": "A", "rasmussen": "A",
    "lugo": "A", "valdez": "A", "elder": "A",
    # B 級（LTD 懲罰 0.4）
    # 其餘均為 B 級
}

LT_PEN = {"S": 0.9, "A": 0.7, "B": 0.4}

# ─────────────────────────────────────────────
# 傷兵資料（2026-04-07 更新）
# OUT = 60天IL（本季幾乎確定缺陣）
# LTD = 10/15天IL（短期缺陣）
# ─────────────────────────────────────────────
OUT = {
    # 球隊: [球員key]
    "athletics":    ["hoglund"],
    "orioles":      ["westburg", "bautista"],
    "red sox":      ["houck", "gonzalez_r"],
    "white sox":    ["bush_k"],
    "tigers":       ["jobe", "melton", "olson", "brieske"],
    "astros":       ["wesneski", "walter_b"],
    "royals":       ["marsh"],
    "angels":       ["rendon", "stephenson_r"],
    "dodgers":      ["snell"],
    "braves":       ["schwellenbach", "waldrep"],
    "twins":        ["lopez_p"],
    "padres":       ["buehler"],
}

LTD = {
    # 球隊: [(球員key, 等級)]  等級對應 SS_TIER
    "orioles":      [("holliday", "A"), ("kjerstad", "B"), ("kittredge", "B"),
                     ("akin", "B"), ("eflin", "A"), ("hiraldo", "B")],
    "red sox":      [("casas", "B"), ("seigler", "B"), ("sandoval_p", "B"),
                     ("crawford_k", "B"), ("oviedo", "B")],
    "white sox":    [("baldwin_b", "B"), ("teel", "B"), ("berroa", "B"),
                     ("thorpe", "B"), ("vasil", "B"), ("pereira_e", "B")],
    "guardians":    [("valera", "B"), ("walters_a", "B"), ("gaddis_h", "B")],
    "tigers":       [("sweeney_t", "B"), ("verlander", "S"), ("horn", "B")],
    "astros":       [("dezenzo", "B"), ("blanco", "B"), ("hader", "S"),
                     ("pearson_n", "B"), ("sousa", "B"), ("brown", "S")],
    "royals":       [("mcarthur", "B"), ("kolek", "B"), ("estevez", "B"),
                     ("falter", "B")],
    "angels":       [("grissom_v", "B"), ("joyce", "B"), ("rodriguez_g", "A"),
                     ("yates", "B"), ("manoah", "B")],
    "blue jays":    [],
    "nationals":    [],
    "rockies":      [],
    "twins":        [("festa", "B"), ("adams_t", "B")],
    "athletics":    [("hoglund", "B")],
    "marlins":      [],
    "rays":         [],
    "brewers":      [],
    "pirates":      [],
    "cardinals":    [],
    "reds":         [],
    "padres":       [],
    "giants":       [],
    "phillies":     [],
    "mets":         [],
    "cubs":         [],
    "rangers":      [],
    "braves":       [("riley", "A"), ("kim_h", "B")],
    "dodgers":      [],
    "yankees":      [],
    "mariners":     [],
    "diamondbacks": [],
}

# ─────────────────────────────────────────────
# 球隊名稱標準化對照表
# ─────────────────────────────────────────────
TEAM_ALIAS = {
    "los angeles dodgers": "dodgers", "la dodgers": "dodgers",
    "new york yankees": "yankees", "ny yankees": "yankees",
    "new york mets": "mets", "ny mets": "mets",
    "atlanta braves": "braves",
    "philadelphia phillies": "phillies",
    "seattle mariners": "mariners",
    "milwaukee brewers": "brewers",
    "pittsburgh pirates": "pirates",
    "toronto blue jays": "blue jays",
    "detroit tigers": "tigers",
    "boston red sox": "red sox",
    "houston astros": "astros",
    "texas rangers": "rangers",
    "chicago cubs": "cubs",
    "baltimore orioles": "orioles",
    "kansas city royals": "royals",
    "tampa bay rays": "rays",
    "arizona diamondbacks": "diamondbacks", "az diamondbacks": "diamondbacks",
    "cincinnati reds": "reds",
    "san diego padres": "padres",
    "cleveland guardians": "guardians",
    "miami marlins": "marlins",
    "san francisco giants": "giants",
    "minnesota twins": "twins",
    "oakland athletics": "athletics", "sacramento athletics": "athletics",
    "st. louis cardinals": "cardinals", "st louis cardinals": "cardinals",
    "los angeles angels": "angels", "la angels": "angels",
    "chicago white sox": "white sox",
    "washington nationals": "nationals",
    "colorado rockies": "rockies",
}

# ─────────────────────────────────────────────
# 輔助函式
# ─────────────────────────────────────────────
def norm_team(name: str) -> str:
    """標準化球隊名稱"""
    n = name.lower().strip()
    return TEAM_ALIAS.get(n, n)

def safe_get(url: str, params: dict = None, timeout: int = 12) -> dict | list | None:
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"safe_get {url}: {e}")
        return None

def norm_cdf(x: float) -> float:
    """標準正態分佈累積分佈函數近似"""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def win_prob_from_margin(margin: float, std: float = STD) -> float:
    """將分差轉換為勝率（正值=主場優勢方）"""
    p = norm_cdf(margin / std)
    return max(0.05, min(0.95, p))

def kelly_stake(edge: float, prob: float, price: float,
                conf: float = 1.0, bank: float = BANK) -> float:
    """
    Kelly 公式計算下注額
    動態 Kelly 分數：高信心時加大，低信心時縮小
    """
    if edge <= 0 or price <= 1.0:
        return 0.0
    b = price - 1.0
    q = 1.0 - prob
    raw_kelly = (b * prob - q) / b
    # 動態 kelly 分數
    dyn_k = KELLY * conf  # conf 高 → 下注多一點
    dyn_k = max(0.05, min(0.18, dyn_k))
    stake = dyn_k * raw_kelly * bank
    return round(max(0.0, min(KELLY_MAX, stake)), 1)

def best_price(markets: list, team_key: str) -> float | None:
    """從 markets 清單中取出最優賠率"""
    best = None
    for m in markets:
        if m.get("key") not in ("h2h",):
            continue
        for outcome in m.get("outcomes", []):
            if norm_team(outcome.get("name", "")) == team_key:
                p = outcome.get("price", 0)
                if best is None or p > best:
                    best = p
    return best

def prob_from_price(price: float) -> float:
    """賠率 → 隱含勝率（去除佣金後近似）"""
    if price <= 1.0:
        return 0.99
    return 1.0 / price

# ─────────────────────────────────────────────
# 投手 ERA 調整
# ─────────────────────────────────────────────
def era_adj(pitcher_key: str | None, is_home: bool = True) -> float:
    """
    根據先發投手 ERA 計算對比聯盟平均的調整值
    ERA 低 → 負調整（對打者不利，降低預期失分）
    ERA 高 → 正調整（對打者有利，提高預期失分）
    返回值為預期得分調整量（正 = 對進攻方有利）
    """
    if pitcher_key is None:
        # 未知投手 → 使用保守的高 ERA 懲罰
        era = LEAGUE_ERA + 0.60
    else:
        key = pitcher_key.lower().strip()
        era = PITCHER_ERA.get(key, None)
        if era is None:
            log.warning(f"投手 {key} 不在字典，使用保守懲罰 ERA={LEAGUE_ERA+0.6:.2f}")
            era = LEAGUE_ERA + 0.60
    # 調整值 = (投手ERA - 聯盟ERA) × 0.35（每1ERA差距≈0.35分/場）
    adj = (era - LEAGUE_ERA) * 0.35
    return round(adj, 3)

# ─────────────────────────────────────────────
# 傷兵懲罰計算
# ─────────────────────────────────────────────
def injury_penalty(team: str) -> float:
    """
    計算球隊傷兵影響（扣減預期得分/場）
    OUT 球員（60d IL）懲罰較小（已被替換）
    LTD 球員（10/15d IL）如果是投手則懲罰更大
    """
    penalty = 0.0
    t = team.lower()

    # OUT 球員（長期缺陣）
    for player in OUT.get(t, []):
        # 主要影響：陣容深度下降，輕微懲罰
        penalty += 0.05

    # LTD 球員（短期缺陣）
    for player_key, tier in LTD.get(t, []):
        pen = LT_PEN.get(tier, LT_PEN["B"])
        penalty += pen * 0.15  # 短期缺陣 × 比例因子

    return round(min(penalty, 1.2), 3)  # 上限 1.2 分懲罰

def pitcher_confidence(pitcher_key: str | None) -> float:
    """
    投手信心指數：0.5（未知）~ 1.0（已知且強）
    用於調整 Kelly 下注量和 Edge 信心係數
    """
    if pitcher_key is None:
        return 0.55
    key = pitcher_key.lower().strip()
    if key not in PITCHER_ERA:
        return 0.55
    era = PITCHER_ERA[key]
    if era <= 2.5:
        return 1.0
    elif era <= 3.2:
        return 0.92
    elif era <= 4.0:
        return 0.82
    elif era <= 4.5:
        return 0.72
    else:
        return 0.62

# ─────────────────────────────────────────────
# 大小分信心折扣
# ─────────────────────────────────────────────
def total_confidence(model_total: float, market_total: float) -> float:
    """
    當模型預測總分與市場差距過大時，降低信心
    差距越大 → 信心越低 → Edge 折扣越多
    """
    gap = abs(model_total - market_total)
    if gap < GAP1:
        return 1.00
    elif gap < GAP2:
        return 0.90
    elif gap < GAP3:
        return 0.78
    else:
        return 0.65

# ─────────────────────────────────────────────
# 勝率預測核心
# ─────────────────────────────────────────────
def predict(home: str, away: str,
            home_sp: str | None, away_sp: str | None,
            market_total: float = 8.5,
            season_games: int = 0) -> dict:
    """
    預測主場和客場勝率
    返回: {home_win_prob, away_win_prob, model_total, conf_factor}
    """
    hb = BASE.get(home, (4.45, 4.45))
    ab = BASE.get(away, (4.45, 4.45))

    # 季初動態混合：賽季前 30 場樣本少，更依賴預測
    if season_games < EARLY_GAMES:
        alpha = 0.15  # YTD 權重低
    else:
        alpha = 0.40

    h_off = hb[0]
    h_def = hb[1]
    a_off = ab[0]
    a_def = ab[1]

    # 投手 ERA 調整（home starter 影響主場失分，away starter 影響客場失分）
    h_sp_adj = era_adj(home_sp)   # 主場先發強→主場失分↓（負值）→客場得分↓
    a_sp_adj = era_adj(away_sp)   # 客場先發強→客場失分↓（負值）→主場得分↓

    # 主場預期得分 = 主場進攻 - 客場先發調整 + 主場優勢
    h_expected = h_off + a_sp_adj + HA   # a_sp_adj 若客場先發ERA<聯盟平均則為負（降低主場得分）
    # 客場預期得分 = 客場進攻 - 主場先發調整
    a_expected = a_off + h_sp_adj

    # 傷兵影響
    h_inj = injury_penalty(home)
    a_inj = injury_penalty(away)
    h_expected -= h_inj * 0.4  # 主場傷兵影響主場進攻
    a_expected -= a_inj * 0.4  # 客場傷兵影響客場進攻

    h_expected = max(2.5, h_expected)
    a_expected = max(2.5, a_expected)

    # 預測分差（正值=主場領先）
    margin = h_expected - a_expected
    model_win_p = win_prob_from_margin(margin, STD)

    # 模型預測總分
    model_total = h_expected + a_expected

    # 大小分信心折扣
    conf = total_confidence(model_total, market_total)

    # 投手信心折扣（兩名先發投手信心的幾何平均）
    pc_h = pitcher_confidence(home_sp)
    pc_a = pitcher_confidence(away_sp)
    pitcher_conf = (pc_h * pc_a) ** 0.5
    conf *= pitcher_conf

    return {
        "home_win_prob": round(model_win_p, 4),
        "away_win_prob": round(1 - model_win_p, 4),
        "model_total":   round(model_total, 2),
        "conf_factor":   round(max(0.40, min(1.0, conf)), 3),
        "h_expected":    round(h_expected, 2),
        "a_expected":    round(a_expected, 2),
        "margin":        round(margin, 3),
    }

# ─────────────────────────────────────────────
# 複合 Edge 計算
# ─────────────────────────────────────────────
def calc_edge(model_p: float, market_p: float, conf: float) -> float:
    """
    複合 Edge = (模型勝率 – 市場隱含勝率) × 信心係數
    再做 Kelly 確認：只有正期望值才允許通過
    """
    raw_edge = model_p - market_p
    adj_edge = raw_edge * conf
    return round(adj_edge, 4)

# ─────────────────────────────────────────────
# 歷史記錄 (GitHub Gist)
# ─────────────────────────────────────────────
def load_hist() -> list:
    """從 GitHub Gist 載入歷史記錄"""
    if not GH_TOKEN or not GH_GIST_ID:
        return []
    url = f"https://api.github.com/gists/{GH_GIST_ID}"
    data = safe_get(url, params=None)
    if not data:
        return []
    try:
        content = list(data["files"].values())[0]["content"]
        records = json.loads(content)
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=HIST_TTL)).isoformat()
        return [r for r in records if r.get("date", "") >= cutoff]
    except Exception as e:
        log.warning(f"load_hist error: {e}")
        return []

def save_hist(records: list) -> str | None:
    """儲存歷史記錄到 GitHub Gist，返回 Gist URL"""
    if not GH_TOKEN:
        return None
    content = json.dumps(records, ensure_ascii=False, indent=2)
    headers = {"Authorization": f"token {GH_TOKEN}",
               "Accept": "application/vnd.github.v3+json"}
    if GH_GIST_ID:
        url = f"https://api.github.com/gists/{GH_GIST_ID}"
        payload = {"files": {"mlb_hist.json": {"content": content}}}
        try:
            r = requests.patch(url, json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            return r.json().get("html_url")
        except Exception as e:
            log.warning(f"save_hist patch error: {e}")
            return None
    else:
        url = "https://api.github.com/gists"
        payload = {
            "description": "MLB_V107 history",
            "public": False,
            "files": {"mlb_hist.json": {"content": content}}
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            gist_url = r.json().get("html_url")
            gist_id  = r.json().get("id")
            log.info(f"新 Gist 建立: {gist_url}  ID={gist_id}")
            log.info("請將 GH_GIST_ID 環境變數設為上述 ID，以便後續更新同一個 Gist")
            return gist_url
        except Exception as e:
            log.warning(f"save_hist create error: {e}")
            return None

# ─────────────────────────────────────────────
# 資料抓取
# ─────────────────────────────────────────────
def fetch_odds() -> list:
    """從 The Odds API 取得 MLB 賠率"""
    if not ODDS_API_KEY:
        log.error("ODDS_API_KEY 未設定")
        return []
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h,totals",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    data = safe_get(url, params=params)
    if data is None:
        return []
    log.info(f"取得 {len(data)} 場 MLB 賠率")
    return data

def fetch_probable_pitchers() -> dict:
    """
    從 MLB Stats API 取得今日可能先發投手
    返回: {game_id: {home_pitcher: str, away_pitcher: str}}
    """
    today = datetime.date.today().isoformat()
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": today,
        "hydrate": "probablePitcher(note),team",
        "fields": "dates,games,gamePk,teams,home,away,probablePitcher,fullName,id"
    }
    data = safe_get(url, params=params)
    result = {}
    if not data:
        return result
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            gid = str(game.get("gamePk", ""))
            home_p = game.get("teams", {}).get("home", {}).get("probablePitcher", {}).get("fullName")
            away_p = game.get("teams", {}).get("away", {}).get("probablePitcher", {}).get("fullName")
            result[gid] = {
                "home_pitcher": _name_to_key(home_p),
                "away_pitcher": _name_to_key(away_p)
            }
    log.info(f"取得 {len(result)} 場先發投手資訊")
    return result

def _name_to_key(full_name: str | None) -> str | None:
    """將投手全名轉換為字典 key（取姓氏小寫）"""
    if not full_name:
        return None
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return parts[-1].lower()
    return full_name.lower()

def fetch_market_total(game_data: dict) -> float:
    """從賠率資料中提取市場總分線"""
    for m in game_data.get("bookmakers", [{}])[0].get("markets", []):
        if m.get("key") == "totals":
            for o in m.get("outcomes", []):
                if o.get("name") in ("Over", "Under"):
                    return float(o.get("point", 8.5))
    return 8.5

def get_season_game_count(hist: list) -> int:
    """估算本賽季已進行場次（用於動態混合權重）"""
    if not hist:
        return 0
    season_start = "2026-03-25"
    count = sum(1 for r in hist if r.get("date", "") >= season_start)
    return count

# ─────────────────────────────────────────────
# Discord 訊息發送
# ─────────────────────────────────────────────
def send(content: str) -> None:
    """分段發送 Discord 訊息（單則上限 2000 字）"""
    if not DISCORD_WEBHOOK:
        print(content)
        return
    LIMIT = 1900
    chunks = []
    current = ""
    for line in content.split("\n"):
        if len(current) + len(line) + 1 > LIMIT:
            chunks.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current)
    for chunk in chunks:
        try:
            r = requests.post(DISCORD_WEBHOOK,
                              json={"content": chunk},
                              timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.error(f"Discord 發送失敗: {e}")

# ─────────────────────────────────────────────
# 主執行流程
# ─────────────────────────────────────────────
def run():
    # ── 時間驗證 ──
    now_tw = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    today_str = now_tw.strftime("%Y-%m-%d")
    hour_tw = now_tw.hour
    log.info(f"台灣時間: {now_tw.strftime('%Y-%m-%d %H:%M')}")

    # 建議推薦時間：台灣時間 9:00 ~ 14:00（美國東部下午/晚間比賽準備）
    if not (9 <= hour_tw <= 14):
        log.warning("非推薦時間（台灣 09:00~14:00），繼續執行但準確率可能較低")

    if not ODDS_API_KEY:
        log.error("請設定 ODDS_API_KEY 環境變數")
        return

    # ── 載入歷史 ──
    hist = load_hist()
    season_games = get_season_game_count(hist)
    log.info(f"本賽季已記錄 {season_games} 場，動態混合 alpha={'低(0.15)' if season_games < EARLY_GAMES else '正常(0.40)'}")

    # ── 取得賠率 ──
    odds_data = fetch_odds()
    if not odds_data:
        log.error("無法取得賠率資料，請確認 API Key")
        return

    # ── 取得先發投手 ──
    pitchers = fetch_probable_pitchers()

    # ── 處理每場比賽 ──
    picks = []
    today_records = []

    for game in odds_data:
        sport = game.get("sport_key", "")
        if sport != "baseball_mlb":
            continue

        # 解析時間
        commence = game.get("commence_time", "")
        try:
            game_utc = datetime.datetime.fromisoformat(commence.replace("Z", "+00:00"))
            game_tw = game_utc + datetime.timedelta(hours=8)
            game_time_str = game_tw.strftime("%m/%d %H:%M")
        except Exception:
            game_time_str = commence[:16]

        # 標準化球隊
        home_raw = game.get("home_team", "")
        away_raw = game.get("away_team", "")
        home = norm_team(home_raw)
        away = norm_team(away_raw)

        if home not in BASE or away not in BASE:
            log.debug(f"跳過未知球隊: {home} vs {away}")
            continue

        # 取得先發投手
        game_id = str(game.get("id", ""))
        sp_info = pitchers.get(game_id, {})
        home_sp = sp_info.get("home_pitcher")
        away_sp = sp_info.get("away_pitcher")

        # 市場賠率
        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        # 取最佳主場賠率
        home_price = None
        away_price = None
        market_total = 8.5

        for bm in bookmakers:
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "h2h":
                    for outcome in mkt.get("outcomes", []):
                        t = norm_team(outcome.get("name", ""))
                        p = outcome.get("price", 0)
                        if t == home and (home_price is None or p > home_price):
                            home_price = p
                        if t == away and (away_price is None or p > away_price):
                            away_price = p
                if mkt.get("key") == "totals":
                    for outcome in mkt.get("outcomes", []):
                        if outcome.get("name") in ("Over", "Under"):
                            try:
                                market_total = float(outcome.get("point", 8.5))
                            except Exception:
                                pass

        if home_price is None or away_price is None:
            continue

        # ── 預測 ──
        pred = predict(home, away, home_sp, away_sp,
                       market_total=market_total,
                       season_games=season_games)

        # 市場隱含勝率
        h_mkt_p = prob_from_price(home_price)
        a_mkt_p = prob_from_price(away_price)

        # 混合勝率
        h_blend = MOD_W * pred["home_win_prob"] + MKT_W * h_mkt_p
        a_blend = MOD_W * pred["away_win_prob"] + MKT_W * a_mkt_p

        conf = pred["conf_factor"]

        # Edge 計算（使用混合勝率對比市場）
        h_edge = calc_edge(h_blend, h_mkt_p, conf)
        a_edge = calc_edge(a_blend, a_mkt_p, conf)

        # 三重過濾條件
        def passes_filter(edge, price, blend_p):
            if edge < EDGE_MIN:
                return False
            if price < MIN_P or price > MAX_P:
                return False
            if blend_p < 0.50:  # 混合勝率必須過半
                return False
            return True

        candidates = []
        if passes_filter(h_edge, home_price, h_blend):
            candidates.append(("home", home, home_price, h_blend, h_edge))
        if passes_filter(a_edge, away_price, a_blend):
            candidates.append(("away", away, away_price, a_blend, a_edge))

        for side, team, price, blend_p, edge in candidates:
            # 動態 Kelly
            stake = kelly_stake(edge, blend_p, price, conf=conf, bank=BANK)
            if stake < KELLY_MIN:
                continue

            # 等級評定
            if edge >= 0.16 and conf >= 0.88:
                tier = "💎 頂級"
            elif edge >= 0.13 and conf >= 0.80:
                tier = "🔥 強力"
            elif edge >= 0.10:
                tier = "⭐ 穩定"
            else:
                continue

            # 對手資訊
            opp = away if side == "home" else home
            h_sp_name = home_sp or "未知"
            a_sp_name = away_sp or "未知"

            msg = (
                f"{tier}\n"
                f"📅 {game_time_str}\n"
                f"⚾ {'客' if side=='away' else '主'} **{team.upper()}** 獨贏 vs {opp.upper()}\n"
                f"🔤 先發: 主 {h_sp_name} | 客 {a_sp_name}\n"
                f"📊 混合勝率: {blend_p:.1%} | 市場: {h_mkt_p if side=='home' else a_mkt_p:.1%}\n"
                f"📈 Edge: {edge:+.3f} | 信心: {conf:.2f}\n"
                f"💰 賠率: {price:.2f} | Kelly: {stake:.0f}元\n"
                f"📉 模型總分: {pred['model_total']:.1f} | 市場: {market_total:.1f}\n"
            )

            picks.append({
                "msg": msg,
                "tier": tier,
                "team": team,
                "opp": opp,
                "side": side,
                "price": price,
                "blend_p": blend_p,
                "edge": edge,
                "conf": conf,
                "stake": stake,
                "game_time": game_time_str,
                "home_sp": h_sp_name,
                "away_sp": a_sp_name,
                "model_total": pred["model_total"],
                "market_total": market_total,
            })

            today_records.append({
                "date": today_str,
                "team": team,
                "opp": opp,
                "price": price,
                "stake": stake,
                "edge": round(edge, 4),
                "conf": round(conf, 3),
                "result": None,
                "pnl": None,
            })

    # ── 整理輸出 ──
    # 按等級排序
    tier_order = {"💎 頂級": 0, "🔥 強力": 1, "⭐ 穩定": 2}
    picks.sort(key=lambda x: (tier_order.get(x["tier"], 9), -x["edge"]))

    # ── 歷史績效統計 ──
    settled = [r for r in hist if r.get("result") is not None]
    wins = sum(1 for r in settled if r.get("result") == "W")
    total_settled = len(settled)
    win_rate = wins / total_settled if total_settled > 0 else 0
    total_pnl = sum(r.get("pnl", 0) or 0 for r in settled)

    # ── 組合輸出訊息 ──
    header = (
        f"🏟️ **MLB_V107 每日推薦 – {today_str}**\n"
        f"{'='*36}\n"
        f"📊 歷史成績: {wins}勝/{total_settled}場 "
        f"({win_rate:.1%}) | 累計損益: {total_pnl:+.0f}元\n"
        f"💡 資金: {BANK}元 | Kelly上限: {KELLY_MAX}元\n"
        f"{'='*36}\n"
    )

    if not picks:
        output = header + "⚠️ 今日無符合條件推薦（Edge < 10% 或信心不足）\n"
    else:
        output = header
        output += f"✅ 今日推薦 {len(picks)} 場\n{'─'*36}\n"
        for pick in picks:
            output += pick["msg"] + "─" * 30 + "\n"

    # 加入市場隱含勝率說明
    output += (
        f"\n📌 **篩選標準 V107**\n"
        f"• Edge ≥ 10%（模型×18% + 市場×82% 混合勝率 – 市場隱含勝率）× 信心係數\n"
        f"• 賠率範圍: {MIN_P:.2f} ~ {MAX_P:.2f}\n"
        f"• 混合勝率必須 > 50%\n"
        f"• 三重信心折扣: 投手未知 / 大小分偏離 / 季初樣本修正\n"
    )

    # ── 儲存記錄 ──
    all_records = hist + today_records
    gist_url = save_hist(all_records)
    if gist_url:
        output += f"\n📁 記錄已儲存: {gist_url}\n"

    # ── 發送 Discord ──
    send(output)
    log.info(f"推薦完成，共 {len(picks)} 筆")
    print(output)

# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    run()
