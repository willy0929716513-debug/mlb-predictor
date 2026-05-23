#!/usr/bin/env python3
"""從 Gist 讀取最新歷史（含已結算結果），更新 picks_latest.json 的 recent_history 和 stats。"""
import json, os, requests, re, datetime

GH_TOKEN  = os.getenv("GH_TOKEN", "")
GIST_DESC = "mlb_bot_history"
JSON_PATH = "docs/picks_latest.json"

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

def gh_h():
    return {"Authorization": "token " + GH_TOKEN, "Content-Type": "application/json"}

def find_gid(gists):
    old = {"mlb_bot_v107_history","mlb_bot_v108_history","mlb_bot_v109_history"}
    new_id = old_id = None
    for g in gists:
        d = g.get("description","")
        if d == GIST_DESC: new_id = g["id"]
        elif d in old and not old_id: old_id = g["id"]
    return new_id or old_id

def main():
    if not GH_TOKEN:
        print("ERROR: GH_TOKEN not set"); return

    # 讀取 Gist 歷史
    r = requests.get("https://api.github.com/gists", headers=gh_h(), timeout=15)
    r.raise_for_status()
    gid = find_gid(r.json())
    if not gid:
        print("ERROR: Gist not found"); return

    detail  = requests.get("https://api.github.com/gists/" + gid, headers=gh_h(), timeout=15).json()
    raw_url = list(detail["files"].values())[0]["raw_url"]
    hist    = requests.get(raw_url, timeout=15).json()
    print(f"Loaded {len(hist)} records from Gist")

    # 統計
    settled = [r for r in hist if r.get("result") in ("W","L")]
    wins    = sum(1 for r in settled if r["result"] == "W")
    wr      = round(wins / len(settled) * 100, 1) if settled else 0.0
    total_in  = sum(r.get("stake", 0) for r in settled)
    total_pnl = sum(
        r.get("stake",0) * (r.get("price",2)-1) if r["result"]=="W" else -r.get("stake",0)
        for r in settled
    )
    roi = round(total_pnl / total_in * 100, 1) if total_in else 0.0

    by_type = {}
    for btlabel, btkey in [("ML","獨贏"),("RL","讓分"),("TOT","大小分")]:
        rs = [r for r in settled if r.get("bet_type") == btkey]
        w  = sum(1 for r in rs if r["result"] == "W")
        _in  = sum(r.get("stake",0) for r in rs)
        _pnl = sum(
            r.get("stake",0)*(r.get("price",2)-1) if r["result"]=="W" else -r.get("stake",0)
            for r in rs
        )
        by_type[btlabel] = {
            "settled": len(rs), "wins": w,
            "win_rate": round(w/len(rs)*100,1) if rs else 0.0,
            "roi": round(_pnl/_in*100,1) if _in else 0.0,
        }

    # 最近 10 筆歷史
    hist_sorted = sorted(
        [r for r in hist if r.get("date")],
        key=lambda r: (r.get("date",""), r.get("bet_type","")),
        reverse=True
    )[:10]
    recent_history = []
    for r in hist_sorted:
        _h = r.get("home",""); _a = r.get("away","")
        recent_history.append({
            "date":     r.get("date",""),
            "home":     _h, "away": _a,
            "home_cn":  CN.get(_h, _h.title()),
            "away_cn":  CN.get(_a, _a.title()),
            "bet_type": r.get("bet_type",""),
            "label":    r.get("label",""),
            "price":    r.get("price"),
            "stake":    r.get("stake"),
            "edge":     round(r.get("edge",0)*100, 1),
            "result":   r.get("result"),
        })

    # 更新 picks_latest.json
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    data["recent_history"] = recent_history
    data["stats"] = {
        "settled":   len(settled), "wins": wins,
        "win_rate":  wr,
        "total_in":  round(total_in,1), "total_pnl": round(total_pnl,1), "roi": roi,
        "by_type":   by_type,
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Updated {JSON_PATH}: {len(settled)} settled, {wins}W, ROI {roi}%")
    print(f"Recent history: {len(recent_history)} records")

if __name__ == "__main__":
    main()
