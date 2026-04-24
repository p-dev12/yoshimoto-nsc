#!/usr/bin/env python3
"""
よしもとメンバー自動更新スクリプト
東京・大阪両劇場に対応
"""

import json
import re
import time
import urllib.request
from pathlib import Path

THEATERS = {
    "東京": "https://jimbocho-manzaigekijyo.yoshimoto.co.jp/profile/",
    "大阪": "https://manzaigekijyo.yoshimoto.co.jp/profile/",
}
PROFILE_BASE   = "https://profile.yoshimoto.co.jp/talent/detail?id="
ROOT_DIR       = Path(__file__).resolve().parents[2]
DATA_DIR       = ROOT_DIR / "data"
MEMBERS_FILE   = DATA_DIR / "members.json"
OVERRIDES_FILE = DATA_DIR / "overrides.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
OSAKA_DIFF = 17


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"  fetch error ({i+1}/{retries}): {e}")
            time.sleep(2)
    return ""

def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def normalize_text(text):
    z2h = str.maketrans("０１２３４５６７８９　", "0123456789 ")
    return text.translate(z2h)

def strip_tags_loose(html):
    text = re.sub(r'<br\s*/?>', ' ', html, flags=re.IGNORECASE)
    text = re.sub(r'</p>|</div>|</li>|</h\d>|</span>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;|&#160;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def find_nsc_candidates(text):
    text = normalize_text(text)
    found = []
    patterns = [
        (r'東京\s*NSC\s*(\d+)\s*期(?:生)?', '東京'),
        (r'NSC\s*東京(?:校)?\s*(\d+)\s*期(?:生)?', '東京'),
        (r'大阪\s*NSC\s*(\d+)\s*期(?:生)?', '大阪'),
        (r'NSC\s*大阪(?:校)?\s*(\d+)\s*期(?:生)?', '大阪'),
        (r'NSC\s*(\d+)\s*期(?:生)?', '大阪'),
    ]
    for pat, region in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            found.append((region, int(m.group(1))))
    return found

def to_tokyo(region, num):
    return num - OSAKA_DIFF if region == "大阪" else num

def extract_nsc(html):
    text = normalize_text(strip_tags_loose(html))
    m = re.search(r'出身/入社/入門\s*[:：]\s*(.+?)(?:\n|$)', text, flags=re.IGNORECASE)
    if m:
        candidates = find_nsc_candidates(m.group(1))
        if candidates:
            region, num = max(candidates, key=lambda x: to_tokyo(x[0], x[1]))
            return f"{region}{num}期"
    candidates = find_nsc_candidates(text)
    if not candidates:
        return ""
    region, num = max(candidates, key=lambda x: to_tokyo(x[0], x[1]))
    return f"{region}{num}期"

def extract_img(html, tid):
    m = re.search(
        rf'https://profile\.yoshimoto\.co\.jp/assets/data/profile/{tid}/[a-f0-9]+\.jpg',
        html
    )
    return m.group(0) if m else ""

def extract_name(html, tid):
    m = re.search(r'<h1[^>]*>\s*(?:<p[^>]*>)?\s*([^<\n]+?)\s*(?:</p>)?\s*</h1>', html)
    return m.group(1).strip() if m else f"ID:{tid}"

def fetch_theater_ids(url):
    html = fetch(url)
    if not html:
        return []
    ids = re.findall(
        r'href="https://profile\.yoshimoto\.co\.jp/talent/detail\?id=(\d+)"',
        html
    )
    return list(dict.fromkeys(ids))

def main():
    print("=== よしもとメンバー自動更新（東京・大阪両劇場） ===")

    members = load_json(MEMBERS_FILE, [])
    ov_data = load_json(OVERRIDES_FILE, {"overrides": {}})
    overrides = ov_data.get("overrides", {})

    existing_by_id = {m["id"]: m for m in members if isinstance(m, dict) and m.get("id")}
    manual_only = [m for m in members if isinstance(m, dict) and not m.get("id")]

    print(f"既存: {len(existing_by_id)}組")

    # 各劇場からID取得
    all_theater_ids = {}
    for theater_name, theater_url in THEATERS.items():
        print(f"{theater_name}劇場取得中...")
        ids = fetch_theater_ids(theater_url)
        print(f"  {len(ids)}件")
        for tid in ids:
            if tid not in all_theater_ids:
                all_theater_ids[tid] = theater_name

    print(f"合計: {len(all_theater_ids)}件")

    rebuilt = []
    added = updated = 0

    for tid, theater in all_theater_ids.items():
        old = existing_by_id.get(tid, {})
        time.sleep(0.3)

        html = fetch(PROFILE_BASE + tid)
        if not html:
            if old:
                rebuilt.append(old)
            continue

        name    = extract_name(html, tid)
        nsc     = extract_nsc(html)
        img     = extract_img(html, tid)
        tier    = old.get("tier", "翔")
        people  = old.get("people", "")
        nsc_man = old.get("nsc_manual", "")

        new_m = {
            "name":       name,
            "theater":    theater,
            "tier":       tier,
            "id":         tid,
            "people":     people,
            "nsc":        nsc,
            "nsc_manual": nsc_man,
            "img":        img,
        }

        if not old:
            added += 1
            print(f"  新規({theater}): {name} / NSC: {nsc or '不明'}")
        else:
            changed = [k for k in ["name", "nsc", "img"] if str(old.get(k, "")) != str(new_m.get(k, ""))]
            if changed:
                updated += 1

        rebuilt.append(new_m)

    rebuilt.extend(manual_only)
    save_json(MEMBERS_FILE, rebuilt)
    print(f"\n完了！ 追加:{added} / 更新:{updated} / 合計:{len(rebuilt)}組")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
