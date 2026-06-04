#!/usr/bin/env python3
# /// script
# dependencies = ["fastapi", "uvicorn", "pandas"]
# ///
"""M3 rise_h window 리뷰 로컬 서버.

rise_h_window_manifest.csv의 window별 hydrograph(강수+유량+M3 onset/peak/rising limb)를
브라우저에서 basin 버튼으로 탐색하고, M3 rise_h가 만족스럽지 않은 window를 클릭하면
고정 CSV(rise_h_flagged_windows.csv)에 누적 저장한다.

실행:
  uv run scripts/model/expanded_drbc/serve_rising_limb_review.py
  → http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import threading
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[3]
WIN_DIR = ROOT / "output/model_analysis/band_signal/method_compare/data/rise_h_windows"
MANIFEST = WIN_DIR / "rise_h_window_manifest.csv"
FLAGGED_CSV = ROOT / "output/model_analysis/band_signal/method_compare/tables/rise_h_flagged_windows.csv"

FLAG_FIELDS = [
    "window_id", "basin_id", "peak_time", "rising_hours",
    "rise_slope_m4", "rise_rel_m4", "obs_class_primary", "auto_flags", "reason", "flagged_at",
]
_lock = threading.Lock()

app = FastAPI(title="M3 rise_h review")


# ── flagged CSV I/O ───────────────────────────────────────────────────────────
def read_flagged() -> dict[str, dict]:
    if not FLAGGED_CSV.exists():
        return {}
    out = {}
    with FLAGGED_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["window_id"]] = row
    return out


def write_flagged(rows: dict[str, dict]) -> None:
    FLAGGED_CSV.parent.mkdir(parents=True, exist_ok=True)
    with FLAGGED_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FLAG_FIELDS)
        w.writeheader()
        for wid in sorted(rows):
            w.writerow({k: rows[wid].get(k, "") for k in FLAG_FIELDS})


# ── manifest ──────────────────────────────────────────────────────────────────
def load_manifest() -> pd.DataFrame:
    if not MANIFEST.exists():
        raise SystemExit(f"manifest 없음: {MANIFEST}\n먼저 plot_rising_limb_m3_windows.py 실행.")
    df = pd.read_csv(MANIFEST, dtype={"basin_id": str, "window_id": str})
    df["basin_id"] = df["basin_id"].str.zfill(8)
    if "clean" in df:
        df["clean"] = df["clean"].astype(str).str.lower().isin(["true", "1"])
    for c in ("flags", "hard_flags", "soft_flags", "obs_class_summary"):
        if c in df:
            df[c] = df[c].fillna("")
    return df.sort_values(["basin_id", "peak_time"]).reset_index(drop=True)


MANIFEST_DF = load_manifest()


def manifest_payload() -> dict:
    windows = MANIFEST_DF.to_dict(orient="records")
    basins = []
    for bid, g in MANIFEST_DF.groupby("basin_id"):
        basins.append({
            "basin_id": bid,
            "n": int(len(g)),
            "n_clean": int(g["clean"].sum()) if "clean" in g else 0,
            "n_autoflag": int((~g["clean"]).sum()) if "clean" in g else 0,
            "n_above": int((g["obs_class_primary"] == "above_q99").sum()),
        })
    n_clean = int(MANIFEST_DF["clean"].sum()) if "clean" in MANIFEST_DF else 0
    return {"windows": windows, "basins": basins,
            "n_total": int(len(MANIFEST_DF)), "n_clean": n_clean}


# ── API ────────────────────────────────────────────────────────────────────────
@app.get("/api/flagged")
def api_flagged():
    return JSONResponse({"flagged": list(read_flagged().keys())})


@app.post("/api/flag")
async def api_flag(req: Request):
    body = await req.json()
    wid = str(body.get("window_id", "")).strip()
    if not wid:
        return JSONResponse({"ok": False, "error": "window_id required"}, status_code=400)
    reason = str(body.get("reason", "")).strip()
    row = MANIFEST_DF.loc[MANIFEST_DF["window_id"] == wid]
    if row.empty:
        return JSONResponse({"ok": False, "error": "unknown window_id"}, status_code=404)
    r = row.iloc[0]
    with _lock:
        flagged = read_flagged()
        flagged[wid] = {
            "window_id": wid,
            "basin_id": r["basin_id"],
            "peak_time": r["peak_time"],
            "rising_hours": r["rising_hours"],
            "rise_slope_m4": r.get("rise_slope_m4", ""),
            "rise_rel_m4": r.get("rise_rel_m4", ""),
            "obs_class_primary": r["obs_class_primary"],
            "auto_flags": r.get("flags", ""),
            "reason": reason,
            "flagged_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        write_flagged(flagged)
        n = len(flagged)
    return JSONResponse({"ok": True, "count": n})


@app.post("/api/unflag")
async def api_unflag(req: Request):
    body = await req.json()
    wid = str(body.get("window_id", "")).strip()
    with _lock:
        flagged = read_flagged()
        flagged.pop(wid, None)
        write_flagged(flagged)
        n = len(flagged)
    return JSONResponse({"ok": True, "count": n})


@app.get("/", response_class=HTMLResponse)
def index():
    payload = json.dumps(manifest_payload(), ensure_ascii=False, default=str)
    flagged = json.dumps(list(read_flagged().keys()), ensure_ascii=False, default=str)
    return HTML_TEMPLATE.replace("__PAYLOAD__", payload).replace("__FLAGGED__", flagged)


# StaticFiles for PNGs
app.mount("/img", StaticFiles(directory=str(WIN_DIR)), name="img")


# ── HTML ────────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>M4 rise_h window 리뷰</title>
<style>
  :root{--ink:#1f2933;--muted:#5f6b7a;--line:#d7dde5;--soft:#f4f6f8;--active:#1d4ed8;
        --flag:#dc2626;--flag-bg:#fff1f2;--green:#16a34a;}
  *{box-sizing:border-box;}
  body{margin:0;font-family:'Apple SD Gothic Neo',-apple-system,BlinkMacSystemFont,sans-serif;
       background:#f8fafc;color:var(--ink);}
  header{padding:14px 20px;background:#fff;border-bottom:1px solid var(--line);
         position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
  header h1{font-size:18px;margin:0;}
  .stat{font-size:13px;color:var(--muted);}
  .stat b{color:var(--ink);}
  .flag-counter{background:var(--flag-bg);border:1px solid #fca5a5;color:var(--flag);
                border-radius:999px;padding:4px 12px;font-size:13px;font-weight:700;}
  .btn{appearance:none;border:1px solid var(--line);background:#fff;border-radius:7px;
       padding:6px 12px;font:inherit;cursor:pointer;font-size:13px;}
  .btn:hover{background:var(--soft);}
  .btn.primary{background:var(--active);color:#fff;border-color:var(--active);}
  .layout{display:grid;grid-template-columns:220px 1fr;gap:16px;padding:16px 20px;}
  .rail{position:sticky;top:64px;align-self:start;max-height:calc(100vh - 80px);overflow:auto;
        background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px;}
  .rail h2{font-size:13px;margin:6px 4px 8px;color:var(--muted);}
  .basin-btn{display:flex;justify-content:space-between;align-items:center;width:100%;
             border:1px solid var(--line);background:#fff;border-radius:6px;padding:6px 8px;
             margin-bottom:4px;cursor:pointer;font:inherit;font-size:12px;text-align:left;}
  .basin-btn:hover{background:var(--soft);}
  .basin-btn.active{border-color:var(--active);box-shadow:0 0 0 2px rgba(29,78,216,.14);}
  .basin-btn .cnt{color:var(--muted);font-size:11px;}
  .basin-btn .badge{color:var(--flag);font-weight:700;}
  .filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center;}
  .filters label{font-size:13px;display:flex;align-items:center;gap:4px;}
  .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;}
  @media (max-width:1200px){.grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
  @media (max-width:760px){.grid{grid-template-columns:1fr;}}
  .card{background:#fff;border:1px solid var(--line);border-radius:9px;overflow:hidden;
        display:flex;flex-direction:column;}
  .card.flagged{border-color:var(--flag);box-shadow:0 0 0 2px rgba(220,38,38,.18);}
  .card.autoflag{border-style:dashed;border-color:#f59e0b;}
  .card.autoflag.flagged{border-style:solid;border-color:var(--flag);}
  .card img{width:100%;display:block;cursor:zoom-in;background:#fff;}
  .card .meta{padding:8px 10px;font-size:12px;border-top:1px solid var(--line);}
  .card .meta .wid{font-weight:700;font-size:12px;word-break:break-all;}
  .card .meta .stats{color:var(--muted);margin-top:2px;}
  .chip{display:inline-block;border-radius:999px;padding:1px 8px;font-size:11px;font-weight:700;color:#fff;margin-right:4px;}
  .card .actions{display:flex;gap:6px;padding:8px 10px;border-top:1px solid var(--line);align-items:center;}
  .flag-btn{flex:0 0 auto;border:1px solid var(--line);background:#fff;border-radius:6px;
            padding:5px 12px;cursor:pointer;font:inherit;font-size:12px;font-weight:700;white-space:nowrap;}
  .flag-btn.on{background:var(--flag);color:#fff;border-color:var(--flag);}
  .flag-btn:not(.on):hover{background:var(--flag-bg);border-color:#fca5a5;color:var(--flag);}
  .reason{flex:1;border:1px solid var(--line);border-radius:6px;padding:6px;font:inherit;font-size:12px;min-width:0;}
  .lb{position:fixed;inset:0;background:rgba(15,23,42,.85);display:none;z-index:50;
      align-items:center;justify-content:center;padding:20px;}
  .lb.open{display:flex;}
  .lb img{max-width:96vw;max-height:90vh;border-radius:8px;background:#fff;}
  .lb-close{position:absolute;top:16px;right:20px;color:#fff;font-size:28px;cursor:pointer;}
  .empty{padding:40px;text-align:center;color:var(--muted);}
</style></head>
<body>
<header>
  <h1>M4 rise_h window 리뷰</h1>
  <span class="stat">총 <b id="totalN">0</b> window · <b id="basinN">0</b> basin · clean <b id="cleanN">0</b> / auto-flag <b id="autoN">0</b></span>
  <span class="flag-counter">수동 불만족 flag: <span id="flagN">0</span></span>
  <button class="btn" id="dlBtn">flag 목록 CSV 다운로드</button>
  <span class="stat" id="csvPath"></span>
</header>
<div class="layout">
  <aside class="rail">
    <h2>BASIN</h2>
    <button class="basin-btn active" data-basin="__ALL__"><span>전체</span><span class="cnt" id="allCnt"></span></button>
    <div id="basinList"></div>
  </aside>
  <main>
    <div class="filters">
      <label><input type="checkbox" id="fClean"> clean만 (auto-flag 숨김)</label>
      <label><input type="checkbox" id="fAuto"> auto-flag된 것만</label>
      <label><input type="checkbox" id="fAbove"> above_q99만</label>
      <label><input type="checkbox" id="fFlagged"> 수동 flag된 것만</label>
      <label>정렬:
        <select id="sortBy">
          <option value="peak">peak 시각</option>
          <option value="rising_desc">rising_hours ↓</option>
          <option value="rising_asc">rising_hours ↑</option>
          <option value="slope_desc">rise_slope_max ↓</option>
        </select>
      </label>
      <span class="stat" id="shownN"></span>
    </div>
    <div class="grid" id="grid"></div>
    <div class="empty" id="empty" style="display:none">표시할 window 없음.</div>
  </main>
</div>
<div class="lb" id="lb"><span class="lb-close" id="lbClose">&times;</span><img id="lbImg" alt=""></div>

<script>
const DATA = __PAYLOAD__;
const BAND_COLORS = {below_q50:"#4393c3",q50_to_q90:"#92c5de",q90_to_q95:"#fddbc7",
                     q95_to_q99:"#f4a582",above_q99:"#d6604d"};
const flagged = new Set(__FLAGGED__);
let curBasin = "__ALL__";

const $ = s => document.querySelector(s);
const isClean = w => w.clean===true || w.clean==="True" || w.clean==="true";
const HARD = new Set(["no_rain_trigger","too_long","data_gap"]);
$("#totalN").textContent = DATA.windows.length;
$("#basinN").textContent = DATA.basins.length;
$("#cleanN").textContent = DATA.n_clean ?? DATA.windows.filter(w=>w.clean).length;
$("#autoN").textContent = DATA.windows.filter(w=>!isClean(w)).length;
$("#allCnt").textContent = DATA.windows.length;
$("#csvPath").textContent = "→ output/model_analysis/band_signal/method_compare/tables/rise_h_flagged_windows.csv";

function renderBasinList(){
  const el = $("#basinList"); el.innerHTML = "";
  DATA.basins.forEach(b=>{
    const flagCnt = DATA.windows.filter(w=>w.basin_id===b.basin_id && flagged.has(w.window_id)).length;
    const btn = document.createElement("button");
    btn.className = "basin-btn" + (curBasin===b.basin_id?" active":"");
    btn.dataset.basin = b.basin_id;
    btn.innerHTML = `<span>${b.basin_id}</span>`+
      `<span class="cnt">${b.n_clean ?? b.n}/${b.n}${flagCnt?` · <span class="badge">⚑${flagCnt}</span>`:""}</span>`;
    btn.onclick = ()=>{curBasin=b.basin_id; syncActive(); render();};
    el.appendChild(btn);
  });
}
function syncActive(){
  document.querySelectorAll(".basin-btn").forEach(x=>
    x.classList.toggle("active", x.dataset.basin===curBasin));
}
$('[data-basin="__ALL__"]').onclick = ()=>{curBasin="__ALL__"; syncActive(); render();};

function updateFlagN(){ $("#flagN").textContent = flagged.size; }

async function toggleFlag(w, card, btn, reasonEl){
  const on = flagged.has(w.window_id);
  try{
    if(on){
      await fetch("/api/unflag",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({window_id:w.window_id})});
      flagged.delete(w.window_id);
    }else{
      const reason = (reasonEl && reasonEl.value.trim()) ? reasonEl.value.trim() : "사유 없음";
      await fetch("/api/flag",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({window_id:w.window_id, reason})});
      flagged.add(w.window_id);
    }
  }catch(e){ alert("저장 실패: "+e); return; }
  btn.classList.toggle("on", flagged.has(w.window_id));
  btn.textContent = "불만족";
  card.classList.toggle("flagged", flagged.has(w.window_id));
  updateFlagN(); renderBasinList();
}

function filtered(){
  let ws = DATA.windows.slice();
  if(curBasin!=="__ALL__") ws = ws.filter(w=>w.basin_id===curBasin);
  if($("#fClean").checked) ws = ws.filter(w=>isClean(w));
  if($("#fAuto").checked)  ws = ws.filter(w=>!isClean(w));
  if($("#fAbove").checked) ws = ws.filter(w=>w.obs_class_primary==="above_q99");
  if($("#fFlagged").checked) ws = ws.filter(w=>flagged.has(w.window_id));
  const s = $("#sortBy").value;
  const num = v => { const x=parseFloat(v); return isNaN(x)?-1e9:x; };
  ws.sort((a,b)=>{
    if(s==="rising_desc") return num(b.rising_hours) - num(a.rising_hours);
    if(s==="rising_asc")  return num(a.rising_hours) - num(b.rising_hours);
    if(s==="slope_desc")  return num(b.rise_slope_max_m4) - num(a.rise_slope_max_m4);
    return a.peak_time < b.peak_time ? -1 : 1;
  });
  return ws;
}

function render(){
  const grid = $("#grid"); grid.innerHTML="";
  const ws = filtered();
  $("#shownN").textContent = `표시: ${ws.length}개`;
  $("#empty").style.display = ws.length? "none":"block";
  const frag = document.createDocumentFragment();
  ws.forEach(w=>{
    const clean = isClean(w);
    const card = document.createElement("div");
    card.className = "card" + (flagged.has(w.window_id)?" flagged":"") + (clean?"":" autoflag");
    const c = BAND_COLORS[w.obs_class_primary]||"#888";
    const af = (w.flags||"").split(";").filter(Boolean);
    const flagChips = af.map(f=>{
      const hard = HARD.has(f);
      return `<span class="chip" style="background:${hard?'#dc2626':'#d97706'}" title="${hard?'HARD(통계 제외)':'SOFT(주의)'}">${hard?'✗':'△'}${f}</span>`;
    }).join("");
    const rs = parseFloat(w.rise_slope_m4), rsm = parseFloat(w.rise_slope_max_m4), rr = parseFloat(w.rise_rel_m4), rh = parseFloat(w.rising_hours);
    card.innerHTML =
      `<img loading="lazy" src="/img/${w.plot_path}" data-full="/img/${w.plot_path}">`+
      `<div class="meta">`+
        `<div class="wid">${w.window_id} ${clean?'<span class="chip" style="background:#16a34a">clean</span>':''}</div>`+
        `<div class="stats">`+
          `<span class="chip" style="background:${c}">${w.obs_class_primary}</span>`+ flagChips +
          `rising_hours <b>${isNaN(rh)?'-':rh.toFixed(0)+'h'}</b> · `+
          `slope_avg <b>${isNaN(rs)?'-':rs.toFixed(3)}</b> · `+
          `slope_max <b style="color:#1a5276">${isNaN(rsm)?'-':rsm.toFixed(3)}</b> · `+
          `rise_rel <b>${isNaN(rr)?'-':rr.toFixed(2)}</b>`+
        `</div>`+
        `<div class="stats">obs_class(seed): ${w.obs_class_summary||"-"}</div>`+
      `</div>`+
      `<div class="actions"></div>`;
    const actions = card.querySelector(".actions");
    const btn = document.createElement("button");
    btn.className = "flag-btn" + (flagged.has(w.window_id)?" on":"");
    btn.textContent = "불만족";
    const reasonEl = document.createElement("input");
    reasonEl.className = "reason"; reasonEl.placeholder = "사유(선택): onset 너무 이름/늦음 등";
    btn.onclick = ()=>toggleFlag(w, card, btn, reasonEl);
    // flag된 상태에서 사유를 입력/수정하면 즉시 재저장 (flag 엔드포인트가 덮어씀)
    reasonEl.onchange = async ()=>{
      if(!flagged.has(w.window_id)) return;
      const reason = reasonEl.value.trim() ? reasonEl.value.trim() : "사유 없음";
      try{
        await fetch("/api/flag",{method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({window_id:w.window_id, reason})});
      }catch(e){ alert("사유 저장 실패: "+e); }
    };
    actions.appendChild(reasonEl); actions.appendChild(btn);
    card.querySelector("img").onclick = e=>{
      $("#lbImg").src = e.target.dataset.full; $("#lb").classList.add("open");
    };
    frag.appendChild(card);
  });
  grid.appendChild(frag);
}

$("#lbClose").onclick = ()=>$("#lb").classList.remove("open");
$("#lb").onclick = e=>{ if(e.target.id==="lb") $("#lb").classList.remove("open"); };
["fClean","fAuto","fAbove","fFlagged","sortBy"].forEach(id=>$("#"+id).addEventListener("change",render));

$("#dlBtn").onclick = async ()=>{
  const r = await fetch("/api/flagged"); const j = await r.json();
  const ids = new Set(j.flagged);
  const rows = DATA.windows.filter(w=>ids.has(w.window_id));
  const cols = ["window_id","basin_id","peak_time","rising_hours","rise_slope_m4","rise_slope_max_m4","rise_rel_m4","obs_class_primary","obs_class_summary","flags","clean"];
  const csv = [cols.join(",")].concat(rows.map(w=>cols.map(c=>`"${(w[c]??"")}"`).join(","))).join("\n");
  const blob = new Blob([csv],{type:"text/csv"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = "rise_h_flagged_windows.csv"; a.click();
};

updateFlagN(); renderBasinList(); render();
</script>
</body></html>"""


def main() -> None:
    import uvicorn
    ap = argparse.ArgumentParser(description="M3 rise_h window 리뷰 서버")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    print(f"manifest: {MANIFEST} ({len(MANIFEST_DF)} windows)")
    print(f"flagged CSV: {FLAGGED_CSV}")
    print(f"→ http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
