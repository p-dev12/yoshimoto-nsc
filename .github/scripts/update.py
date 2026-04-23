#!/usr/bin/env python3
"""
よしもとメンバー自動更新スクリプト
毎日GitHub Actionsで実行され、members.jsonを最新状態に保ちます
"""

import json
import re
import time
import urllib.request
from pathlib import Path

THEATER_URL  = "https://jimbocho-manzaigekijyo.yoshimoto.co.jp/profile/"
PROFILE_BASE = "https://profile.yoshimoto.co.jp/talent/detail?id="
DATA_DIR     = Path(__file__).parent / "data"
MEMBERS_FILE = DATA_DIR / "members.json"
OVERRIDES_FILE = DATA_DIR / "overrides.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"  fetch error ({i+1}/{retries}): {url} → {e}")
            time.sleep(2)
    return ""

def extract_nsc(html):
    """プロフィールHTMLからNSC期を抽出"""
    # 「東京NSC28期」「NSC東京校28期生」「大阪NSC34期」などに対応
    patterns = [
        r'(東京)NSC[\s　]*(\d+)期',
        r'NSC東京校[\s　]*(\d+)期',
        r'(大阪)NSC[\s　]*(\d+)期',
        r'NSC大阪校[\s　]*(\d+)期',
        r'NSC[\s　]*(\d+)期',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            if '東京' in pat or '東京' in m.group(0):
                return f"東京{m.group(2) if len(m.groups()) > 1 else m.group(1)}期"
            elif '大阪' in pat or '大阪' in m.group(0):
                return f"大阪{m.group(2) if len(m.groups()) > 1 else m.group(1)}期"
            else:
                # 地域不明の場合は東京とみなす
                return f"東京{m.group(1)}期"
    return ""

def extract_img(html, talent_id):
    """プロフィールHTMLから画像URLを抽出"""
    m = re.search(
        rf'https://profile\.yoshimoto\.co\.jp/assets/data/profile/{talent_id}/[a-f0-9]+\.jpg',
        html
    )
    return m.group(0) if m else ""

def fetch_profile(talent_id):
    """タレントプロフィールからNSC期・画像URLを取得"""
    if not talent_id:
        return "", ""
    html = fetch(PROFILE_BASE + talent_id)
    if not html:
        return "", ""
    return extract_nsc(html), extract_img(html, talent_id)

def fetch_theater_members():
    """劇場サイトからコンビIDリストを取得"""
    html = fetch(THEATER_URL)
    if not html:
        return []
    ids = re.findall(
        r'href="https://profile\.yoshimoto\.co\.jp/talent/detail\?id=(\d+)"',
        html
    )
    return list(dict.fromkeys(ids))  # 重複除去・順序保持

def fetch_combo_info(talent_id):
    """コンビ名・区分・メンバー名を取得"""
    html = fetch(PROFILE_BASE + talent_id)
    if not html:
        return None

    # コンビ名
    name_m = re.search(r'<h1[^>]*>\s*([^<\n]+?)\s*</h1>', html)
    name = name_m.group(1).strip() if name_m else f"ID:{talent_id}"

    # NSC期
    nsc = extract_nsc(html)

    # 画像URL
    img = extract_img(html, talent_id)

    return {
        "name":       name,
        "tier":       "翔",   # 新規はとりあえず翔メンバーとして追加
        "id":         talent_id,
        "people":     "",
        "nsc":        nsc,
        "nsc_manual": "",
        "img":        img,
    }

def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("=== よしもとメンバー自動更新 ===")

    # 既存データ読み込み
    members = load_json(MEMBERS_FILE, [])
    overrides_data = load_json(OVERRIDES_FILE, {"overrides": {}})
    overrides = overrides_data.get("overrides", {})

    current_ids = {m["id"] for m in members if m.get("id")}

    # 劇場サイトから最新IDリストを取得
    print("劇場サイトからメンバーリストを取得中...")
    theater_ids = fetch_theater_members()
    print(f"  劇場サイト: {len(theater_ids)}件")

    added = 0
    updated = 0

    # 新規メンバーを追加
    for tid in theater_ids:
        if tid in current_ids:
            continue
        print(f"  新規メンバー検出: ID={tid}")
        time.sleep(0.5)
        info = fetch_combo_info(tid)
        if info:
            members.append(info)
            added += 1
            print(f"    → {info['name']} / NSC: {info['nsc'] or '不明'}")

    # 既存メンバーのNSC期・画像を再取得（空のものだけ）
    print("既存メンバーのNSC期を確認中...")
    for m in members:
        if not m.get("id"):
            continue
        if m.get("nsc") and m.get("img"):
            continue  # 既に取得済み
        print(f"  取得中: {m['name']}")
        time.sleep(0.5)
        nsc, img = fetch_profile(m["id"])
        if nsc and not m.get("nsc"):
            m["nsc"] = nsc
            updated += 1
        if img and not m.get("img"):
            m["img"] = img

    # 脱退メンバーを除外（IDなしエントリは保持）
    theater_id_set = set(theater_ids)
    before = len(members)
    members = [m for m in members if not m.get("id") or m["id"] in theater_id_set]
    removed = before - len(members)

    # overrides.jsonの不明リストを更新
    unknown_names = [m["name"] for m in members if not m.get("nsc") and not overrides.get(m["name"])]
    for name in unknown_names:
        if name not in overrides:
            overrides[name] = ""
    overrides_data["overrides"] = overrides

    # 保存
    save_json(MEMBERS_FILE, members)
    save_json(OVERRIDES_FILE, overrides_data)

    print(f"\n完了！ 追加:{added}組 / 更新:{updated}組 / 削除:{removed}組")
    print(f"不明NSC期: {len([v for v in overrides.values() if not v])}組")

if __name__ == "__main__":
    main()
