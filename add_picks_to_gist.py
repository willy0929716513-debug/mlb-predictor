#!/usr/bin/env python3
"""一次性腳本：從 Gist 刪除指定比賽記錄"""
import json, os, requests

GH_TOKEN  = os.getenv("GH_TOKEN", "")
GIST_DESC = "mlb_bot_history"

# 要刪除的比賽（home, away, date）
PICKS_TO_DELETE = [
    ("phillies", "guardians", "2026-05-24"),
    ("angels",   "rangers",   "2026-05-24"),
]

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

    r = requests.get("https://api.github.com/gists", headers=gh_h(), timeout=15)
    r.raise_for_status()
    gid = find_gid(r.json())
    if not gid:
        print("ERROR: Gist not found"); return

    detail  = requests.get("https://api.github.com/gists/" + gid, headers=gh_h(), timeout=15).json()
    raw_url = list(detail["files"].values())[0]["raw_url"]
    records = requests.get(raw_url, timeout=15).json()
    print(f"Loaded {len(records)} records")

    new_records = []
    for rec in records:
        rk = (rec.get("home",""), rec.get("away",""), rec.get("date",""))
        if rk in PICKS_TO_DELETE:
            print(f"Deleted: {rec.get('away')}@{rec.get('home')} {rec.get('date')}")
        else:
            new_records.append(rec)

    removed = len(records) - len(new_records)
    if removed == 0:
        print("Nothing deleted."); return

    body = json.dumps(new_records, ensure_ascii=False, indent=2)
    pl   = {"description": GIST_DESC, "public": False,
            "files": {"history.json": {"content": body}}}
    requests.patch("https://api.github.com/gists/" + gid, headers=gh_h(), json=pl, timeout=10).raise_for_status()
    print(f"Done. Removed {removed} records. Total: {len(new_records)}")

if __name__ == "__main__":
    main()
