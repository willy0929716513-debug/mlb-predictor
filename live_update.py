#!/usr/bin/env python3
"""
場中輕量更新器 — 只打 MLB Stats API（免費），不消耗 Odds API 額度。
每次執行：讀取 picks_latest.json → 抓即時比分 → 更新 live_games → 存回。
"""
import datetime
import json
import logging
import os

import requests

log = logging.getLogger("live_update")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

JSON_PATH = "docs/picks_latest.json"

CN = {
    "dodgers": "道奇", "yankees": "洋基", "mets": "大都會", "braves": "勇士",
    "phillies": "費城人", "mariners": "水手", "brewers": "釀酒人", "pirates": "海盜",
    "blue jays": "藍鳥", "tigers": "老虎", "red sox": "紅襪", "astros": "太空人",
    "rangers": "遊騎兵", "cubs": "小熊", "orioles": "金鶯", "royals": "皇家",
    "rays": "光芒", "diamondbacks": "響尾蛇", "reds": "紅人", "padres": "教士",
    "guardians": "守護者", "marlins": "馬林魚", "giants": "巨人", "twins": "雙城",
    "athletics": "運動家", "cardinals": "紅雀", "angels": "天使", "white sox": "白襪",
    "nationals": "國民", "rockies": "落磯",
}

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
    "arizona diamondbacks": "diamondbacks",
    "az diamondbacks": "diamondbacks",
    "cincinnati reds": "reds",
    "san diego padres": "padres",
    "cleveland guardians": "guardians",
    "miami marlins": "marlins",
    "san francisco giants": "giants",
    "minnesota twins": "twins",
    "oakland athletics": "athletics",
    "sacramento athletics": "athletics",
    "st. louis cardinals": "cardinals",
    "st louis cardinals": "cardinals",
    "los angeles angels": "angels",
    "la angels": "angels",
    "chicago white sox": "white sox",
    "washington nationals": "nationals",
    "colorado rockies": "rockies",
}


def norm_team(name):
    n = name.lower().strip()
    return TEAM_ALIAS.get(n, n)


def safe_get(url, params=None, timeout=10):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("safe_get %s: %s", url, e)
        return None


def fetch_live_scores(et_date_str):
    data = safe_get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={"date": et_date_str, "sportId": 1, "gameType": "R",
                "hydrate": "linescore,team"},
    )
    live = []
    for db in (data or {}).get("dates", []):
        for game in db.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Live":
                continue
            home_raw = game.get("teams", {}).get("home", {}).get("team", {}).get("name", "").lower()
            away_raw = game.get("teams", {}).get("away", {}).get("team", {}).get("name", "").lower()
            hk = norm_team(TEAM_ALIAS.get(home_raw, home_raw.split()[-1] if home_raw else ""))
            ak = norm_team(TEAM_ALIAS.get(away_raw, away_raw.split()[-1] if away_raw else ""))
            if not hk or not ak:
                continue
            ls        = game.get("linescore", {})
            inning    = int(ls.get("currentInning") or 1)
            top       = bool(ls.get("isTopInning", True))
            home_runs = int(ls.get("teams", {}).get("home", {}).get("runs") or 0)
            away_runs = int(ls.get("teams", {}).get("away", {}).get("runs") or 0)
            live.append({
                "home": hk, "away": ak,
                "inning": inning, "top_inning": top,
                "home_runs": home_runs, "away_runs": away_runs,
            })
    log.info("Live games: %d", len(live))
    return live


def generate_live_picks(live_games, game_preds):
    result = []
    for lg in live_games:
        home, away    = lg["home"], lg["away"]
        inning        = lg["inning"]
        top_inning    = lg["top_inning"]
        home_r        = lg["home_runs"]
        away_r        = lg["away_runs"]
        current_total = home_r + away_r
        diff          = home_r - away_r

        innings_done = float(inning) - (1.0 if top_inning else 0.5)
        innings_left = max(0.0, 9.0 - innings_done)

        pred         = game_preds.get("%s|%s" % (home, away), {})
        market_total = pred.get("market_total") or 8.5
        p_home       = pred.get("home_win_prob", 0.5)

        log.info("  %s@%s %s%d局 %d:%d diff=%+d mt=%.1f p_home=%.2f pred=%s",
                 away, home, "▲" if top_inning else "▼", inning,
                 away_r, home_r, diff, market_total, p_home,
                 "有" if pred else "無(預設0.5)")

        run_rate  = (current_total / innings_done) if innings_done > 0.5 else (market_total / 9.0)
        projected = round(current_total + run_rate * innings_left, 1)
        log.info("    預計終局 %.1f (門檻 UNDER<%.1f / OVER>%.1f)",
                 projected, market_total - 1.0, market_total + 1.0)

        bet = reason = None
        if inning >= 6 and projected < market_total - 1.0:
            bet    = "大小分 UNDER"
            reason = "第%d局 %d:%d → 預計終局%.1f分 < 盤口%.1f" % (inning, away_r, home_r, projected, market_total)
        elif inning <= 5 and projected > market_total + 1.0:
            bet    = "大小分 OVER"
            reason = "第%d局 %d:%d → 預計終局%.1f分 > 盤口%.1f" % (inning, away_r, home_r, projected, market_total)
        elif 4 <= inning <= 8:
            if -2 <= diff <= -1 and p_home >= 0.54:
                bet    = "主隊讓分(+1.5)"
                reason = "主隊落後%d分 第%d局，賽前主隊勝率%d%%" % (abs(diff), inning, round(p_home * 100))
            elif 1 <= diff <= 2 and p_home <= 0.46:
                bet    = "客隊讓分(+1.5)"
                reason = "客隊落後%d分 第%d局，賽前客隊勝率%d%%" % (diff, inning, round((1 - p_home) * 100))

        if bet:
            log.info("    ✅ 推薦: %s — %s", bet, reason)

        result.append({
            "home_cn":         CN.get(home, home),
            "away_cn":         CN.get(away, away),
            "inning":          inning,
            "top_inning":      top_inning,
            "home_runs":       home_r,
            "away_runs":       away_r,
            "projected_total": projected,
            "market_total":    market_total,
            "bet":             bet,
            "reason":          reason,
        })
    return result


def main():
    if not os.path.exists(JSON_PATH):
        log.error("%s not found — run main bot first", JSON_PATH)
        return

    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    game_preds = data.get("game_preds", {})
    log.info("game_preds: %d games", len(game_preds))

    et_now       = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
    et_date_str  = et_now.strftime("%Y-%m-%d")
    log.info("ET date: %s", et_date_str)

    live_games  = fetch_live_scores(et_date_str)
    live_picks  = generate_live_picks(live_games, game_preds)

    now_tw = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    data["live_games"]      = live_picks
    data["live_updated_at"] = now_tw.strftime("%Y-%m-%d %H:%M") + " (台灣時間)"

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    bets = [lp for lp in live_picks if lp.get("bet")]
    log.info("Done — %d 場進行中 / %d 個推薦", len(live_picks), len(bets))


if __name__ == "__main__":
    main()
