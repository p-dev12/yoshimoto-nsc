#!/usr/bin/env python3
"""
members.json + overrides.json → index.html を生成
GitHub Actionsで自動実行されます
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT_DIR       = Path(__file__).resolve().parents[2]
DATA_DIR       = ROOT_DIR / "data"
MEMBERS_FILE   = DATA_DIR / "members.json"
OVERRIDES_FILE = DATA_DIR / "overrides.json"
OUTPUT_FILE    = ROOT_DIR / "index.html"

def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def members_to_js(members, overrides):
    """メンバーリストをJavaScript配列に変換"""
    lines = []
    for m in members:
        name   = m.get("name", "")
        tier   = m.get("tier", "翔")
        mid    = m.get("id", "")
        people = m.get("people", "")
        # NSC期: overrides > nsc_manual > nsc の優先順
        nsc = (overrides.get(name) or m.get("nsc_manual") or m.get("nsc") or "")
        # JavaScriptで安全に使えるようエスケープ
        def esc(s):
            return s.replace('\\', '\\\\').replace('"', '\\"')
        lines.append(f'["{esc(name)}","{esc(tier)}","{esc(mid)}","{esc(people)}","{esc(nsc)}"]')
    return ",\n".join(lines)

def build():
    members  = load_json(MEMBERS_FILE, [])
    ov_data  = load_json(OVERRIDES_FILE, {"overrides": {}})
    overrides = ov_data.get("overrides", {})

    # 不明リスト（JSに埋め込む用）
    unknown_list = [m["name"] for m in members if not (overrides.get(m["name"]) or m.get("nsc_manual") or m.get("nsc"))]

    jst = timezone(timedelta(hours=9))
    updated_at = datetime.now(jst).strftime("%Y/%m/%d %H:%M")

    members_js = members_to_js(members, overrides)

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>よしもとメンバー｜NSC期別早見表</title>
<link rel="stylesheet" href="style.css">
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-text">よしもと<span>メンバー</span></div>
  </div>
  <div class="header-right">
    <div class="fbtns">
      <button class="fb on" onclick="setF(\'all\',this)">全員</button>
      <button class="fb" onclick="setF(\'極\',this)">極メンバー</button>
      <button class="fb" onclick="setF(\'翔\',this)">翔メンバー</button>
    </div>
  </div>
</header>

<div class="stat" id="stat"></div>
<div class="jumpnav" id="jumpnav"></div>
<div id="main"></div>

<script>
const CURRENT_YEAR = new Date().getFullYear();
const TOKYO_BASE   = 1995;
const OSAKA_DIFF   = 17;
const UPDATED_AT   = "{updated_at}";

function calcYear(tokyoN) {{
  return CURRENT_YEAR - (tokyoN + TOKYO_BASE) + 1;
}}

function parseNsc(s) {{
  if (!s) return null;
  const m = s.match(/^(東京|大阪)(\\d+)期$/);
  if (!m) return null;
  return {{ region: m[1], num: parseInt(m[2]) }};
}}

function groupKey(nscStr) {{
  const p = parseNsc(nscStr);
  if (!p) return {{ sortN: 9999, label: "不明", sub: "", yearN: null }};
  const tokyoN = p.region === "大阪" ? p.num - OSAKA_DIFF : p.num;
  const osakaN = tokyoN + OSAKA_DIFF;
  return {{ sortN: tokyoN, label: `東京${{tokyoN}}期`, sub: `大阪${{osakaN}}期`, yearN: calcYear(tokyoN) }};
}}

const MEMBERS = [
{members_js}
];

let curFilter = "all";

function setF(f, btn) {{
  curFilter = f;
  document.querySelectorAll(".fb").forEach(b => b.classList.remove("on"));
  btn.classList.add("on");
  render();
}}

function ek(s) {{ return s.replace(/[^\\w\\u3000-\\u9fff]/g, "_"); }}

function render() {{
  const list = curFilter === "all" ? MEMBERS : MEMBERS.filter(m => m[1] === curFilter);
  const gmap = {{}};
  list.forEach(m => {{
    const g = groupKey(m[4]);
    const k = g.label;
    if (!gmap[k]) gmap[k] = {{ sortN: g.sortN, sub: g.sub, yearN: g.yearN, arr: [] }};
    gmap[k].arr.push(m);
  }});

  const sorted = Object.entries(gmap).sort((a, b) => a[1].sortN - b[1].sortN);
  const known  = sorted.filter(([k]) => k !== "不明");

  document.getElementById("jumpnav").innerHTML = known.map(([k, v]) =>
    `<span class="jchip" onclick="document.getElementById('r${{ek(k)}}').scrollIntoView({{behavior:'smooth',block:'start'}})">
      ${{k}}<span style="color:var(--text-dim);margin-left:3px">${{v.arr.length}}</span>
    </span>`
  ).join("");

  const total   = list.length;
  const withNsc = list.filter(m => m[4]).length;
  document.getElementById("stat").innerHTML =
    `<span>表示: <strong>${{total}}組</strong></span>` +
    `<span>NSC期確認済: <strong>${{withNsc}}組</strong></span>` +
    `<span>不明: <strong>${{total - withNsc}}組</strong></span>` +
    `<span style="margin-left:auto;color:var(--text-dim);font-size:10px">更新: ${{UPDATED_AT}}</span>`;

  document.getElementById("main").innerHTML = sorted.map(([k, g]) => {{
    const unk = k === "不明";
    return `<div class="nsc-row" id="r${{ek(k)}}">
      <div class="label-col${{unk ? " unk" : ""}}">
        <div class="lmain">${{unk ? "不明" : k}}</div>
        ${{!unk && g.yearN !== null ? `<div class="lyear">${{g.yearN}}年目</div>` : ""}}
        ${{!unk && g.sub ? `<div class="lsub">${{g.sub}}</div>` : ""}}
        <div class="lsub" style="margin-top:4px">${{g.arr.length}}組</div>
      </div>
      <div class="members-col">${{g.arr.map(cardHtml).join("")}}</div>
    </div>`;
  }}).join("");
}}

function cardHtml(m) {{
  const [name, tier, id, people] = m;
  const href = id ? `https://profile.yoshimoto.co.jp/talent/detail?id=${{id}}` : "#";
  return `<a class="card" href="${{href}}" target="_blank" rel="noopener">
    <div class="cname">${{name}}</div>
    ${{people ? `<div class="cppl">${{people}}</div>` : ""}}
  </a>`;
}}

render();
</script>
</body>
</html>'''

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"index.html を生成しました（{len(members)}組）")

if __name__ == "__main__":
    build()
