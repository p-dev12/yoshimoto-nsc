#!/usr/bin/env python3
"""
members.json + overrides.json → index.html を生成
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT_DIR       = Path(__file__).resolve().parents[2]
DATA_DIR       = ROOT_DIR / "data"
MEMBERS_FILE   = DATA_DIR / "members.json"
OVERRIDES_FILE = DATA_DIR / "overrides.json"
OUTPUT_FILE    = ROOT_DIR / "index.html"

OSAKA_DIFF = 17

def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def members_to_js(members, overrides):
    lines = []
    for m in members:
        name    = m.get("name", "")
        theater = m.get("theater", "東京")
        tier    = m.get("tier", "翔")
        mid     = m.get("id", "")
        people  = m.get("people", "")
        nsc     = (overrides.get(name) or m.get("nsc_manual") or m.get("nsc") or "")
        def esc(s):
            return s.replace('\\', '\\\\').replace('"', '\\"')
        lines.append(f'["{esc(name)}","{esc(theater)}","{esc(tier)}","{esc(mid)}","{esc(people)}","{esc(nsc)}"]')
    return ",\n".join(lines)

def build():
    members   = load_json(MEMBERS_FILE, [])
    ov_data   = load_json(OVERRIDES_FILE, {"overrides": {}})
    overrides = ov_data.get("overrides", {})

    jst = timezone(timedelta(hours=9))
    updated_at = datetime.now(jst).strftime("%Y/%m/%d %H:%M")

    print(f"overrides読み込み: {overrides}")
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
    <div class="filter-group">
      <div class="fbtns theater-btns">
        <button class="fb on" data-theater="all" onclick="setTheater(\'all\',this)">全員</button>
        <button class="fb tokyo" data-theater="東京" onclick="setTheater(\'東京\',this)">東京</button>
        <button class="fb osaka" data-theater="大阪" onclick="setTheater(\'大阪\',this)">大阪</button>
      </div>
      <div class="fbtns tier-btns">
        <button class="fb on" data-tier="all" onclick="setTier(\'all\',this)">全員</button>
        <button class="fb" data-tier="極" onclick="setTier(\'極\',this)">極</button>
        <button class="fb" data-tier="翔" onclick="setTier(\'翔\',this)">翔</button>
      </div>
    </div>
  </div>
</header>

<div class="stat" id="stat"></div>
<div class="jumpnav" id="jumpnav"></div>
<div id="main"></div>

<script>
const CURRENT_YEAR = new Date().getFullYear();
const TOKYO_BASE   = 1995;
const OSAKA_DIFF   = {OSAKA_DIFF};
const UPDATED_AT   = "{updated_at}";

// [name, theater, tier, id, people, nsc]
const MEMBERS = [
{members_js}
];

let curTheater = "all";
let curTier    = "all";

function setTheater(v, btn) {{
  curTheater = v;
  document.querySelectorAll(".theater-btns .fb").forEach(b => b.classList.remove("on"));
  btn.classList.add("on");
  render();
}}

function setTier(v, btn) {{
  curTier = v;
  document.querySelectorAll(".tier-btns .fb").forEach(b => b.classList.remove("on"));
  btn.classList.add("on");
  render();
}}

function calcYear(tokyoN) {{
  return CURRENT_YEAR - (tokyoN + TOKYO_BASE) + 1;
}}

function parseNsc(s) {{
  if (!s) return null;
  const m = s.match(/^(東京|大阪)(\\d+)期$/);
  if (!m) return null;
  return {{ region: m[1], num: parseInt(m[2]) }};
}}

function toTokyoN(region, num) {{
  return region === "大阪" ? num - OSAKA_DIFF : num;
}}

function groupKey(nscStr) {{
  const p = parseNsc(nscStr);
  if (!p) return {{ sortN: 9999, label: "不明", sub: "", yearN: null }};
  const tokyoN = toTokyoN(p.region, p.num);
  const osakaN = tokyoN + OSAKA_DIFF;
  return {{ sortN: tokyoN, label: `東京${{tokyoN}}期`, sub: `大阪${{osakaN}}期`, yearN: calcYear(tokyoN) }};
}}

function ek(s) {{ return s.replace(/[^\\w\\u3000-\\u9fff]/g, "_"); }}

function render() {{
  let list = MEMBERS;
  if (curTheater !== "all") list = list.filter(m => m[1] === curTheater);
  if (curTier !== "all")    list = list.filter(m => m[2] === curTier);

  const gmap = {{}};
  list.forEach(m => {{
    const g = groupKey(m[5]);
    const k = g.label;
    if (!gmap[k]) gmap[k] = {{ sortN: g.sortN, sub: g.sub, yearN: g.yearN, arr: [] }};
    gmap[k].arr.push(m);
  }});

  const sorted = Object.entries(gmap).sort((a, b) => a[1].sortN - b[1].sortN);
  const known  = sorted.filter(([k]) => k !== "不明");

  // ジャンプナビ
  document.getElementById("jumpnav").innerHTML = known.map(([k, v]) =>
    `<span class="jchip" onclick="document.getElementById('r${{ek(k)}}').scrollIntoView({{behavior:'smooth',block:'start'}})">
      ${{k}}<span style="color:var(--text-dim);margin-left:3px">${{v.arr.length}}</span>
    </span>`
  ).join("");

  // 統計
  document.getElementById("stat").innerHTML =
    `<span>表示: <strong>${{list.length}}組</strong></span>` +
    `<span style="margin-left:auto;color:var(--text-dim);font-size:10px">更新: ${{UPDATED_AT}}</span>`;

  // 行
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
  const [name, theater, tier, id, people] = m;
  const href = id ? `https://profile.yoshimoto.co.jp/talent/detail?id=${{id}}` : "#";
  // 全員表示時は劇場で色分け、絞り込み時はニュートラル
  const colorClass = curTheater === "all" ? (theater === "東京" ? " tokyo" : " osaka") : "";
  return `<a class="card${{colorClass}}" href="${{href}}" target="_blank" rel="noopener">
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
