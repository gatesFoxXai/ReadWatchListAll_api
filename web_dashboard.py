"""Web Dashboard — 即時多股監控畫面 (Flask + SSE)
Usage: python web_dashboard.py [--port 5000]
"""

import argparse
import csv
import json
import os
import queue
import time
import threading
from datetime import datetime
from flask import Flask, Response, render_template_string, jsonify, request
from option_pricing import OptionPricing, put_call_ratio_analysis
import hedge_dashboard

app = Flask(__name__)


@app.after_request
def _no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


hedge_dashboard.register(app)
sse_queue = queue.Queue()

WATCHLIST_PATH = "watchlist.json"
WATCHLIST_META_PATH = "watchlist_meta.json"
NAMES_PATH = "stock_names.json"
_active_watchlist = "自選股1"


def load_names():
    if os.path.exists(NAMES_PATH):
        with open(NAMES_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_stock_name(stock_id: str) -> str:
    return load_names().get(stock_id, stock_id)


def load_watchlist_meta():
    if os.path.exists(WATCHLIST_META_PATH):
        try:
            with open(WATCHLIST_META_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[web_dashboard] WARNING: failed to read {WATCHLIST_META_PATH}: {e}.")
            return {}
    return {}


_market_cap_cache = None
_market_cap_cache_time = 0


def _load_market_cap():
    global _market_cap_cache, _market_cap_cache_time
    now = time.time()
    if _market_cap_cache is not None and now - _market_cap_cache_time < 3600:
        return _market_cap_cache
    path = "market_cap.json"
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                _market_cap_cache = json.load(f)
            _market_cap_cache_time = now
            return _market_cap_cache
        except Exception:
            pass
    return None


def _guess_market_from_market_cap(stock_id: str) -> str | None:
    cap = _load_market_cap()
    if not cap:
        return None
    entry = cap.get("stocks", {}).get(stock_id)
    if not isinstance(entry, dict):
        return None
    market = entry.get("market")
    if market == "TWSE":
        return "stocks"
    if market == "OTC":
        return "TWOTC"
    return None


def _normalize_watchlist_entry(entry: dict) -> dict:
    if not isinstance(entry, dict):
        return entry
    stocks = list(entry.get("stocks") or [])
    twotc = list(entry.get("TWOTC") or [])
    futures = list(entry.get("futures") or [])
    normalized_stocks = []
    normalized_twotc = []

    for stock_id in stocks:
        suggested = _guess_market_from_market_cap(stock_id)
        if suggested == "TWOTC":
            if stock_id not in normalized_twotc:
                normalized_twotc.append(stock_id)
        else:
            if stock_id not in normalized_stocks:
                normalized_stocks.append(stock_id)

    for stock_id in twotc:
        suggested = _guess_market_from_market_cap(stock_id)
        if suggested == "stocks":
            if stock_id not in normalized_stocks:
                normalized_stocks.append(stock_id)
        else:
            if stock_id not in normalized_twotc:
                normalized_twotc.append(stock_id)

    entry["stocks"] = normalized_stocks
    entry["TWOTC"] = normalized_twotc
    entry["futures"] = futures
    return entry


def load_watchlists():
    default = {
        "自選股1": {
            "stocks": ["2330", "2317", "2344"],
            "futures": ["TFX8", "TXFPM1"],
            "TWOTC": ["6123", "8936", "6122", "3293", "6143", "8069"],
        }
    }
    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, encoding="utf-8") as f:
                wl = json.load(f)
            updated = False
            for name, entry in list(wl.items()):
                normalized = _normalize_watchlist_entry(entry)
                if normalized != entry:
                    wl[name] = normalized
                    updated = True
            if updated:
                with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
                    json.dump(wl, f, ensure_ascii=False, indent=2)
            return wl
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[web_dashboard] WARNING: failed to parse {WATCHLIST_PATH}: {e}. Using default watchlist.")
            return default
        except Exception as e:
            print(f"[web_dashboard] WARNING: error reading {WATCHLIST_PATH}: {e}. Using default watchlist.")
            return default
    return default


def get_active_watchlist_entry():
    wl = load_watchlists()
    return wl.get(_active_watchlist, wl.get("自選股1", {"stocks": [], "TWOTC": []}))


def get_active_stocks():
    entry = get_active_watchlist_entry()
    stocks = entry.get("stocks", []) or []
    twotc = entry.get("TWOTC", []) or []
    combined = []
    for sid in stocks + twotc:
        if sid not in combined:
            combined.append(sid)
    return combined


STOCKS = get_active_stocks()
DATA_INTERVAL = 0.33
SNAPSHOT_DIR = "snapshot"
HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="shortcut icon" href="/favicon.ico" type="favicon.ico">
<title>v2.4-0612 • Yuanta OneAPI 即時監控</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#c9d1d9;font-family:'Microsoft YaHei',sans-serif;padding:16px}
	.stat-row{display:flex;justify-content:space-between;font-size:11px;margin-top:6px;color:#8b949e;border-top:1px solid #21262d;padding-top:4px;white-space:nowrap}
	.stat-row span:last-child{white-space:nowrap}
h1{font-size:20px;margin-bottom:12px;color:#58a6ff}
.header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.wl-select{padding:6px 10px;background:#21262d;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;font-size:13px}
.wl-select:focus{outline:none;border-color:#58a6ff}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
@media(max-width:1200px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
.card h2{font-size:16px;display:flex;justify-content:space-between}
.card .type{font-size:10px;padding:1px 6px;border-radius:10px;color:#fff}
.type-large{background:#238636}.type-mid{background:#9e6a03}.type-small{background:#6e7681}.type-spec{background:#da3633}
.row{display:flex;justify-content:space-between;margin:4px 0;font-size:13px}
.price{font-size:22px;font-weight:bold}
.price.limit-up{background:#da3633;color:#fff;padding:2px 8px;border-radius:4px;display:inline-block}
.price.limit-down{background:#238636;color:#fff;padding:2px 8px;border-radius:4px;display:inline-block}
.up{color:#f85149}.down{color:#3fb950}.muted{color:#8b949e}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold}
.tag-buy{background:#238636;color:#fff}.tag-strong-buy{background:#1f6feb;color:#fff}
.tag-sell{background:#da3633;color:#fff}.tag-strong-sell{background:#9e6a03;color:#fff}
.tag-churn{background:#6e7681;color:#fff}
.market-tag{display:inline-block;padding:2px 6px;border-radius:6px;color:#fff;font-size:11px;margin-left:6px}
  .market-TWSE{background:#1f6feb}
  .market-TWOTC{background:#d97706}
  .market-TAIFEX{background:#9333ea}
  .market-TWSEODD{background:#0ea5a4}
  .market-TWOTCODD{background:#06b6d4}
  .market-SGX{background:#64748b}
  .market-CFE{background:#b91c1c}
    /* 新增的變化類型標籤 */
    .tag-new{background:#ff4d4f;color:#fff}
    .tag-downgrade{background:#2e7d32;color:#fff}
    .tag-exit-mid{background:#6e7681;color:#fff}
    /* 大額成交列顏色 */
    .record-large{background:#ffeb3b;}
.wl-groups{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.wl-group{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;flex:1 1 240px;min-width:180px}
.wl-group h4{font-size:12px;color:#8b949e;margin-bottom:6px}
.wl-tag{display:inline-block;padding:2px 6px;border-radius:6px;background:#0d1117;color:#c9d1d9;font-size:11px;margin:2px 4px 0 0}
.bar{height:4px;border-radius:2px;margin-top:4px;background:#21262d}
.bar-fill{height:100%;border-radius:2px;transition:none}
.last-update{font-size:10px;color:#484f58;margin-top:6px}
.summary-bar{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;font-size:13px}
.summary-item{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 14px}
.summary-item .num{font-size:18px;font-weight:bold}
.pcr-panel{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;margin-top:12px}
.pcr-panel h3{font-size:14px;margin-bottom:8px}
.pcr-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.pcr-row input{width:80px;padding:4px 6px;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;border-radius:4px;font-size:12px}
.pcr-row label{font-size:11px;color:#8b949e}
.pcr-result{font-size:12px;margin-top:8px;line-height:1.6}
.toggle-btn{background:none;border:none;color:#58a6ff;cursor:pointer;font-size:13px;padding:4px 0}
.c-recs{display:none}.c-recs.open{display:block}
.depth-table{width:100%;border-collapse:collapse;font-size:11px;margin-top:4px}
.depth-table th{color:#8b949e;font-weight:normal;text-align:right;padding:1px 4px}
.depth-table td{text-align:right;padding:1px 4px;font-variant-numeric:tabular-nums}
.depth-table .bid{color:#3fb950}.depth-table .ask{color:#f85149}
.val-band{display:flex;align-items:center;gap:2px;margin-top:6px;font-size:10px}
.val-band .seg{flex:1;height:6px;border-radius:2px;position:relative}
.val-band .seg.special{background:#238636}.val-band .seg.cheap{background:#56d364}
.val-band .seg.fair{background:#d29922}.val-band .seg.expensive{background:#f85149}
.val-band .seg.crazy{background:#da3633}
.val-band .marker{position:absolute;top:-3px;width:2px;height:12px;background:#fff;border:1px solid #000}
.val-labels{display:flex;justify-content:space-between;font-size:9px;color:#8b949e;margin-top:2px}
.val-tier{font-size:10px;padding:1px 6px;border-radius:8px;font-weight:600}
.val-tier.special{background:#238636;color:#fff}.val-tier.cheap{background:#56d364;color:#000}
.val-tier.fair{background:#d29922;color:#000}.val-tier.expensive{background:#f85149;color:#fff}
.val-tier.crazy{background:#da3633;color:#fff}
.stale{color:#f85149}.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}.status-dot.live{background:#3fb950;box-shadow:0 0 6px #3fb950}.status-dot.stale{background:#f85149;box-shadow:0 0 6px #f85149}.status-dot.dead{background:#6e7681}
</style>
</head>
<body>
<div class="header">
<h1>v2.4-0612 Yuanta OneAPI — 即時監控 <a href="/hedge" style="font-size:13px;color:#d2991d;text-decoration:none;margin-left:12px">避險</a></h1>
<div style="display:flex;gap:8px;align-items:center">
<select class="wl-select" id="wlSelect" onchange="switchWatchlist(this.value)"></select>
<input id="stockSearch" placeholder="搜尋代號或名稱..." style="padding:6px 8px;background:#21262d;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;font-size:12px;width:160px" onkeyup="if(event.key==='Enter')addStock()">
<button onclick="addStock()" style="padding:6px 12px;background:#238636;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px">+ 新增</button>
<select class="wl-select" id="marketSelect" style="width:90px">
<option value="stocks">TWSE上市</option>
<option value="TWOTC">TWOTC上櫃</option>
</select>
<div id="searchResults" style="position:absolute;top:40px;right:0;background:#161b22;border:1px solid #30363d;border-radius:6px;z-index:99;display:none;max-height:200px;overflow-y:auto"></div>
</div>
</div>
<div class="summary-bar" id="summary"></div>
<button class="toggle-btn" id="recBtn" onclick="toggleAllRecords()">▸ 全部價量紀錄</button>
<div class="grid" id="grid"></div>
<button class="toggle-btn" onclick="document.getElementById('pcrPanel').style.display=document.getElementById('pcrPanel').style.display==='none'?'block':'none'">Put/Call 合理價計算 ▾</button>
<div class="pcr-panel" id="pcrPanel" style="display:none">
<h3>選擇權合理價評估</h3>
<div class="pcr-row">
<label>S(現貨)<input id="pcrS" value="23000"></label>
<label>K(履約)<input id="pcrK" value="23000"></label>
<label>天數<input id="pcrD" value="30"></label>
<label>Call市價<input id="pcrC" value="300"></label>
<label>Put市價<input id="pcrP" value="280"></label>
<label>波動率<input id="pcrV" value="0.25"></label>
<button onclick="calcPCR()" style="padding:4px 12px;background:#238636;border:none;color:#fff;border-radius:4px;cursor:pointer">計算</button>
</div>
<div class="pcr-result" id="pcrResult"></div>
</div>
<div class="last-update" id="status">等待資料...</div>
<div style="font-size:9px;color:#484f58;text-align:right;margin-top:2px;font-family:monospace">v2.4-0612</div>
<script>
async function loadWatchlists(){
  const r=await fetch('/api/watchlists');const d=await r.json();
  const sel=document.getElementById('wlSelect');
  sel.innerHTML=d.watchlists.map(w=>`<option value="${w}" ${w===d.active?'selected':''}>${w}</option>`).join('');
  const metaDiv = document.getElementById('wlMeta');
  if(metaDiv){
    if(d.meta && d.meta.markets){
      metaDiv.innerHTML = Object.entries(d.meta.markets).map(([k,v])=>`<span title="${v}" style="margin-right:8px;padding:2px 6px;background:#0d1117;border:1px solid #21262d;border-radius:6px">${k}</span>`).join('');
    } else if(d.meta && d.meta.description) {
      metaDiv.textContent = d.meta.description;
    } else {
      metaDiv.textContent = '';
    }
  }
  window._WL_CONTENT = d.content || {};
  window._WL_ACTIVE = d.active || null;
  window._WL_META = d.meta || {};
  renderWatchlistGroups(d.content[d.active] || {}, d.meta || {});
}

function renderWatchlistGroups(entry, meta){
  const container = document.getElementById('wlGroups');
  if(!container) return;
  const stocks = Array.isArray(entry.stocks) ? entry.stocks : [];
  const twotc = Array.isArray(entry.TWOTC) ? entry.TWOTC : [];
  const build = (label, items) => {
    if(!items.length) return '';
    return `<div class="wl-group"><h4>${label}</h4>${items.map(s=>`<span class="wl-tag">${s}</span>`).join('')}</div>`;
  };
  const html = build('TWSE 上市股票', stocks) + build('TWOTC 上櫃股票', twotc);
  container.innerHTML = html || '<div class="wl-group"><h4>目前自選股</h4><span class="wl-tag">尚未新增任何 TWSE/TWOTC 股票</span></div>';
}
async function switchWatchlist(name){
  if(!name) return;
  await fetch('/api/watchlist/'+encodeURIComponent(name),{method:'POST'});
  await loadWatchlists();
  location.reload();
}
(async function init(){
  try{
    await loadWatchlists();
    const r=await fetch('/api/stocks');const d=await r.json();render(d);summary(d);
  }catch(e){}
})();
function fmt(n,d=2){if(n==null)return'--';return Number(n).toFixed(d);}
function vol(n){if(n==null||n<0)return'--';return String(Math.round(n/1000)).replace(/\B(?=(\d{3})+(?!\d))/g,',');}
function amt(n){if(n==null||n<0)return'--';if(n>=1e10)return(n/1e8).toFixed(1)+'億';else if(n>=1e8)return(n/1e7).toFixed(1)+'千萬';else if(n>=1e7)return(n/1e4).toFixed(1)+'百萬';return(n/1e4).toFixed(2)+'萬';}
function badge(type){
  const m={large_cap:['大型','type-large'],mid_cap:['中型','type-mid'],
            small_cap:['小型','type-small'],speculative:['投機','type-spec']};
  const [label,cls]=m[type]||['--',''];
  return `<span class="${cls}">${label}</span>`;
}
const VAL_TIER_LABEL={special:'特價',cheap:'便宜',fair:'合理',expensive:'昂貴',crazy:'瘋狂'};
function valBand(s){
  const v=s.valuation;
  if(!v||!v.bands) return '';
  const b=v.bands, close=s.close_price;
  const lo=Math.min(b.special,b.cheap,b.fair,b.expensive,b.crazy);
  const hi=Math.max(b.special,b.cheap,b.fair,b.expensive,b.crazy);
  const range=hi-lo;
  const pos=close!=null?Math.min(100,Math.max(0,(close-lo)/range*100)):null;
  const tier=v.current_tier?VAL_TIER_LABEL[v.current_tier]:'--';
  const marker=pos!=null?`<div class="marker" style="left:${pos}%"></div>`:'';
  return `<div class="val-band" title="合理價 ${b.fair}｜目前 ${close!=null?close:'--'}">
    <div class="seg special">${marker}</div><div class="seg cheap"></div><div class="seg fair"></div><div class="seg expensive"></div><div class="seg crazy"></div>
  </div>
  <div class="val-labels"><span>特價${b.special}</span><span>便宜${b.cheap}</span><span>合理${b.fair}</span><span>昂貴${b.expensive}</span><span>瘋狂${b.crazy}</span></div>
  <div class="row" style="margin-top:2px"><span class="val-tier ${v.current_tier||''}">${tier}</span><span class="muted" style="font-size:10px">${v.mode==='cyclical'?'PBR':'PE'} 估值</span></div>`;
}
function tag(label){
  const map={主力強力買進:['強力買進','tag-strong-buy'],主力溫和買進:['溫和買進','tag-buy'],
             散戶盤整:['盤整','tag-churn'],主力溫和賣出:['溫和賣出','tag-sell'],
             主力強力賣出:['強力賣出','tag-strong-sell']};
  const [text,cls]=map[label]||[label,'tag-churn'];
  return `<span class="tag ${cls}">${text}</span>`;
}
const cards={};
function cardHTML(s){
  if(s.close_price==null) return `<h2>${s.stock_name||s.stock_id} <span>${s.stock_id}</span><button onclick="removeStock('${s.stock_id}')" title="移除" style="float:right;background:none;border:none;color:#8b949e;cursor:pointer;font-size:16px;padding:0 4px">×</button></h2><div class="row muted">等待資料...</div>`;
  const ref = s.ref_price != null ? s.ref_price : (s.open_price != null ? s.open_price : null);
  const cls = (ref !== null && s.close_price !== null)
    ? (s.close_price > ref ? 'up' : s.close_price < ref ? 'down' : '')
    : '';
  const limitCls = s.limit_state === 'up' ? ' limit-up' : s.limit_state === 'down' ? ' limit-down' : '';
  const limitLabel=s.limit_state==='up'?' 漲停':s.limit_state==='down'?' 跌停':'';
  const chgPct=(ref !== null && s.close_price != null && ref !== 0)
    ?(((s.close_price - ref) / ref) * 100).toFixed(2):'--';
  const inRatio=(s.total_in_volume || 0)+(s.total_out_volume || 0) > 0
    ?(((s.total_in_volume || 0)/((s.total_in_volume || 0)+(s.total_out_volume || 0))) * 100).toFixed(1):50;
  const dealAmt=s.deal_amount||0, dealVol=s.deal_volume||0;
  let recs='';
  if(s._records&&s._records.length){
        const LARGE_VOL = 1000; // threshold for large volume rows (in 張)
        const LARGE_AMT = 1_000_000; // threshold for large amount rows (in 金額)
        const LARGE_PRICE = 10_000; // threshold for large price per share (in 元)
        recs='<table class="depth-table" style="margin-top:4px"><tr><th>時間</th><th>成交價</th><th>量(張)</th><th>內盤</th><th>外盤</th><th>金額</th></tr>';
        for(const r of s._records){
            // Skip rows that have no volume and no price information.
            if((r.vol||0)===0 && (r.in_vol||0)===0 && (r.out_vol||0)===0 && (r.price==null || Number(r.price)===0)) continue;
            // 標記為 large 的條件：
            //   1. 成交量 > LARGE_VOL 且 > 1（避免單筆 1 張被誤判）
            //   2. 金額 > LARGE_AMT
            //   3. 單筆股價 >= LARGE_PRICE（例如 1 張價格 >= 10,000 元）
            const priceNum = Number(r.price) || 0;
            const volCls = (((r.vol||0) > LARGE_VOL && (r.vol||0) > 1) || (r.amt||0) > LARGE_AMT || priceNum >= LARGE_PRICE) ? 'record-large' : '';
            recs+=`<tr class="${volCls}"><td>${r.time||'--'}</td><td>${fmt(r.price)}</td><td>${vol(r.vol)}</td><td>${vol(r.in_vol)}</td><td>${vol(r.out_vol)}</td><td>${amt(r.amt)}</td></tr>`;
        }
        recs+='</table>';
  }
  let marketTag = '';
  try{
    const wlContent = window._WL_CONTENT || {};
    const wlActive = window._WL_ACTIVE;
    const wlMeta = window._WL_META || {};
    if(wlContent && wlActive && wlContent[wlActive]){
        const entry = wlContent[wlActive];
        const tags = [];
        try{
          if(Array.isArray(entry.stocks) && entry.stocks.includes(s.stock_id)){
            const title = (wlMeta.markets && wlMeta.markets['TWSE']) ? wlMeta.markets['TWSE'] : 'TWSE';
            tags.push(`<span class="market-tag market-TWSE" title="${title}">TWSE</span>`);
        }
        }catch(e){}
        try{
          if(Array.isArray(entry.TWOTC) && entry.TWOTC.includes(s.stock_id)){
            const title = (wlMeta.markets && wlMeta.markets['TWOTC']) ? wlMeta.markets['TWOTC'] : 'TWOTC';
            tags.push(`<span class="market-tag market-TWOTC" title="${title}">TWOTC</span>`);
          }
        }catch(e){}
        const otherKeys = ['TAIFEX','TWSEODD','TWOTCODD','SGX','CFE'];
        for(const k of otherKeys){
          try{
            if(Array.isArray(entry[k]) && entry[k].includes(s.stock_id)){
              const title = (wlMeta.markets && wlMeta.markets[k]) ? wlMeta.markets[k] : k;
              tags.push(`<span class="market-tag market-${k}" title="${title}">${k}</span>`);
            }
          }catch(e){}
        }
        if(tags.length) marketTag = tags.join(' ');
    }
  }catch(e){ }
  const uid='r'+s.stock_id;
	  const recsOpen = _recsOpen ? ' open' : '';
    // 變化類型標籤 (new, downgrade, exit-mid)
    const changeMap = {new:'tag-new',downgrade:'tag-downgrade',exit_mid:'tag-exit-mid'};
    const changeCls = changeMap[s.change_type]||'';
    const changeLabel = s.change_type ? `<span class="${changeCls}">${s.change_type}</span>` : '';
  return `<h2>${s.stock_name||s.stock_id} <span>${s.stock_id}</span> <span>${badge(s.stock_type)}</span> ${marketTag}<button onclick="removeStock('${s.stock_id}')" title="移除" style="float:right;background:none;border:none;color:#8b949e;cursor:pointer;font-size:16px;padding:0 4px">×</button></h2>
<div class="price ${cls}${limitCls}">${fmt(s.close_price)} ${limitLabel} <span style="font-size:13px">${chgPct>0?'+'+chgPct:chgPct}%</span></div>
<div class="row"><span>開 ${fmt(s.open_price)}</span><span>高 ${fmt(s.high_price)}</span><span>低 ${fmt(s.low_price)}</span></div>
<div class="row"><span>量 ${vol(dealVol)} 張</span><span>成交筆數 ${String(s.trade_count||0).replace(/\B(?=(\d{3})+(?!\d))/g,',')}</span></div>
<div class="row"><span>內盤 ${vol(s.total_in_volume)} 張</span><span class="muted">外盤 ${vol(s.total_out_volume)} 張</span></div>
<div class="row"><span>${s.volume_label||'估日量'} ${vol(s.estimated_day_volume)} 張</span><span class="muted">${s.pct_of_yesterday_avg!=null?(s.pct_of_yesterday_avg>=0?'增':'縮')+Math.abs(s.pct_of_yesterday_avg).toFixed(1)+'%':'--'}</span></div>
<div class="row"><span>MA5 ${fmt(s.ma5)}</span><span class="muted">MA10 ${fmt(s.ma10)}</span><span>${tag(s.participation_label||'N/A')}</span></div>
<div class="row" style="font-size:11px"><span class="${s.pe_source==='forward'?'up':'muted'}" title="${s.pe_source==='forward'?'本益比使用法人預估EPS':(s.pe_source==='trailing'?'本益比使用近四季EPS':'無EPS資料')}">PE ${fmt(s.pe,1)||"--"}</span>${s.pe_revision==='up'?'<span class="up" style="font-size:9px;margin-left:2px">上修</span>':s.pe_revision==='down'?'<span class="down" style="font-size:9px;margin-left:2px">下修</span>':''}<span class="muted" title="${s.peg_note||""}"> PB ${fmt(s.pb,2)||"--"} PEG ${fmt(s.peg,2)||"--"}</span></div>
${valBand(s)}
<div class="bar"><div class="bar-fill" style="width:${Math.min(100,Math.max(0,inRatio))}%;background:${inRatio>55?'#3fb950':inRatio<45?'#f85149':'#6e7681'}"></div></div>
<div class="row"><span class="muted">買盤佔比 ${inRatio}%</span><span class="muted">Score: ${s.participation_score||'--'}</span></div>
<div class="stat-row"><span>${(s.timestamp|| '').slice(-8)}</span><span>成交總額 ${amt(dealAmt)} / ${vol(dealVol)}張</span></div>
<div class="c-recs${recsOpen}">${recs}</div>`;
}
function render(data){
  const g=document.getElementById('grid'), active=new Set(Object.keys(data)), now=Date.now();
  for(const id of Object.keys(cards)){if(!active.has(id)){cards[id].remove();delete cards[id];}}
  for(const [id,s] of Object.entries(data)){
    let el=cards[id];
    if(!el){el=document.createElement('div');el.className='card';cards[id]=el;g.appendChild(el);}
    const h=cardHTML(s);if(el._h!==h){el.innerHTML=h;el._h=h;}
    const ts=s.timestamp;let stale=false;
    if(ts){const parts=ts.split(' ');if(parts.length>=2){const t=parts[1].split(':');const sec=now/1000-((+t[0])*3600+(+t[1])*60+(+t[2]));if(sec>30)stale=true;}}
    el.style.borderColor=stale?'#f85149':'#30363d';
  }
  for(const[id,el] of Object.entries(cards)){
    const r=el.querySelector('.c-recs');if(r)r.classList.toggle('open',_recsOpen);
  }
}
function summary(data){
  let totalVol=0,totalIn=0,totalOut=0,up=0,down=0;const entries=Object.entries(data);
  for(const[,s] of entries){
    totalVol += (s.deal_volume||0);
    totalIn += (s.total_in_volume||0);
    totalOut += (s.total_out_volume||0);
    if (s.close_price != null && s.open_price != null) {
      if (s.close_price > s.open_price) up++;
      else if (s.close_price < s.open_price) down++;
    }
  }
  const inPct=totalIn+totalOut>0?Math.round(totalIn/(totalIn+totalOut)*100):50;
  const bar=document.getElementById('summary');
  if(!bar._built){bar.innerHTML='<div class="summary-item"><span class="s-cnt"></span> <span class="s-updn"></span></div><div class="summary-item">總量 <span class="num s-tvol"></span></div><div class="summary-item">內盤佔比 <span class="num s-inpct"></span></div>';bar._built=true;}
  setText(bar.querySelector('.s-cnt'),'監控 '+entries.length+' 檔');
  setText(bar.querySelector('.s-updn'),up+'↑ '+down+'↓');
  setText(bar.querySelector('.s-tvol'),String(Math.round(totalVol/1000)).replace(/\B(?=(\d{3})+(?!\d))/g,',')+' 張');
  const pctEl=bar.querySelector('.s-inpct');setText(pctEl,inPct+'%');
  pctEl.style.color=inPct>55?'#3fb950':inPct<45?'#f85149':'#c9d1d9';
}



async function calcPCR(){
  const p=id=>document.getElementById(id).value;
  const r=await fetch('/api/options?'+new URLSearchParams({S:p('pcrS'),K:p('pcrK'),days:p('pcrD'),call:p('pcrC'),put:p('pcrP'),vol:p('pcrV')}));
  const d=await r.json();
  document.getElementById('pcrResult').innerHTML=`
理論 Call: ${d.fair_call} (市場 ${d.call_premium_pct>0?'+':''}${d.call_premium_pct}%)<br>
理論 Put: ${d.fair_put} (市場 ${d.put_premium_pct>0?'+':''}${d.put_premium_pct}%)<br>
Call IV: ${(d.call_iv*100).toFixed(1)}% | Put IV: ${(d.put_iv*100).toFixed(1)}%<br>
Parity偏差: ${d.parity_diff>0?'Call偏貴':'Put偏貴'} ${Math.abs(d.parity_diff).toFixed(1)}<br>
PCR 訊號: ${d.pcr.signal} (vol:${d.pcr.vol_ratio||'--'})`;
}
const statusEl=document.getElementById('status');
statusEl.textContent='連線中...';
(async function init(){
  try{const r=await fetch('/api/stocks');const d=await r.json();render(d);summary(d);}catch(e){}
})();
let _recsOpen=false;
function toggleAllRecords(){
  _recsOpen=!_recsOpen;
  document.getElementById('recBtn').textContent=_recsOpen?'▾ 全部價量紀錄':'▸ 全部價量紀錄';
  for(const[id,el] of Object.entries(cards)){
    const r=el.querySelector('.c-recs');if(r)r.classList.toggle('open',_recsOpen);
  }
}
const es=new EventSource('/stream');
let _lastUpdate=Date.now(),_staleCheck=null;
es.onopen=function(){statusEl.innerHTML='<span class="status-dot live"></span>SSE 已連線'};
es.onerror=function(){statusEl.innerHTML='<span class="status-dot dead"></span>SSE 斷線，重新連線中...'};
es.onmessage=function(e){const d=JSON.parse(e.data);render(d);summary(d);_lastUpdate=Date.now();statusEl.innerHTML='<span class="status-dot live"></span>更新 '+new Date().toLocaleTimeString()};
_staleCheck=setInterval(function(){
  const sec=Math.round((Date.now()-_lastUpdate)/1000);
  if(sec>10)statusEl.innerHTML='<span class="status-dot stale"></span>資料滯後 '+sec+'秒';
},2000);

function inferMarketGroup(stock_id){
  const entry = (window._WL_CONTENT||{})[window._WL_ACTIVE] || {};
  if(Array.isArray(entry.TWOTC) && entry.TWOTC.includes(stock_id)) return 'TWOTC';
  if(Array.isArray(entry.stocks) && entry.stocks.includes(stock_id)) return 'stocks';
  return document.getElementById('marketSelect')?.value || 'stocks';
}
async function addStock(){
  const inp=document.getElementById('stockSearch'),q=inp.value.trim();
  if(!q)return;
  const market=document.getElementById('marketSelect')?.value || inferMarketGroup(q);
  const r=await fetch('/api/watchlist/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stock_id:q, market:market})});
  const d=await r.json();
  if(d.ok){
    if(d.corrected_market){
      const correctedLabel = d.corrected_market === 'stocks' ? 'TWSE 上市' : 'TWOTC 上櫃';
      alert(`${d.added} 已自動歸類為 ${correctedLabel}，已加入自選股。`);
    }
    inp.value='';
    location.reload();
    return;
  }
  if(d.suggested_market){
    const suggestedLabel = d.suggested_market === 'stocks' ? 'TWSE 上市' : 'TWOTC 上櫃';
    if(confirm(`${d.error}\n\n是否要將市場改為 ${suggestedLabel} 並重新新增？`)){
      document.getElementById('marketSelect').value = d.suggested_market;
      return addStock();
    }
  }
  alert(d.error||'新增失敗');
}
async function removeStock(sid){
  if(!confirm(`確定要移除 ${sid} 嗎？`))return;
  const r=await fetch('/api/watchlist/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stock_id:sid})});
  const d=await r.json();
  if(d.ok)location.reload();
  else alert(d.error||'移除失敗');
}
let _searchTimer=null;
document.getElementById('stockSearch').addEventListener('input',function(){
  clearTimeout(_searchTimer);
  const q=this.value.trim();
  if(!q){document.getElementById('searchResults').style.display='none';return;}
  _searchTimer=setTimeout(async()=>{
    const r=await fetch('/api/stock/search?q='+encodeURIComponent(q));
    const d=await r.json();
    const div=document.getElementById('searchResults');
    if(!d.results.length){div.style.display='none';return;}
    div.innerHTML=d.results.map(s=>`<div style="padding:4px 8px;cursor:pointer;font-size:12px" onmouseover="this.style.background='#21262d'" onmouseout="this.style.background=''" onclick="document.getElementById('stockSearch').value='${s.symbol}';document.getElementById('searchResults').style.display='none';addStock()">${s.symbol} ${s.name}</div>`).join('');
    div.style.display='block';
  },200);
});
document.addEventListener('click',function(e){if(!e.target.closest('#stockSearch')&&!e.target.closest('#searchResults'))document.getElementById('searchResults').style.display='none';});

</script>
</body>
</html>"""


def read_snapshot(stock_id: str) -> dict | None:
    """從 snapshot/{stock_id}.json 讀取最新狀態（0.5 秒更新）。"""
    path = os.path.join(SNAPSHOT_DIR, f"{stock_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
        # 轉換為 dashboard 相容格式（與 read_latest_csv 回傳格式一致）
        d = {
            "stock_id": snap.get("stock_id", stock_id),
            "stock_name": get_stock_name(stock_id),
            "buy_prices": snap.get("buy_prices", []),
            "buy_volumes": snap.get("buy_volumes", []),
            "sell_prices": snap.get("sell_prices", []),
            "sell_volumes": snap.get("sell_volumes", []),
            "buy_total_volume": max(0, snap.get("buy_total_volume", 0) or 0),
            "sell_total_volume": max(0, snap.get("sell_total_volume", 0) or 0),
            "buy_sell_imbalance": snap.get("buy_sell_imbalance"),
            # 優先使用累積值（API 提供的總成交金額/總量），區間值作為降級
            "deal_amount": snap.get("cumulative_deal_amount")
            if snap.get("cumulative_deal_amount") is not None
            else snap.get("deal_amount"),
            "close_price": snap.get("close_price"),
            "open_price": snap.get("open_price"),
            "high_price": snap.get("high_price"),
            "low_price": snap.get("low_price"),
            "price_diff": snap.get("price_diff"),
            "deal_volume": snap.get("cumulative_deal_volume")
            if snap.get("cumulative_deal_volume") is not None
            else max(0, snap.get("deal_volume", 0) or 0),
            "trade_count": snap.get("trade_count"),
            "total_in_volume": max(0, snap.get("total_in_volume", 0) or 0),
            "total_out_volume": max(0, snap.get("total_out_volume", 0) or 0),
            "estimated_day_volume": max(0, snap.get("estimated_day_volume", 0) or 0),
            "volume_label": snap.get("volume_label", "估日量"),
            "pct_of_yesterday_avg": snap.get("pct_of_yesterday_avg"),
            "ma5": snap.get("ma5"),
            "ma10": snap.get("ma10"),
            "stock_type": snap.get("stock_type", ""),
            "timestamp": snap.get("timestamp", ""),
            "participation_score": snap.get("participation_score"),
            "participation_label": snap.get("participation_label", ""),
            # 財務數據 (PE/PB/PEG)
            "pe": None,
            "pb": None,
            "peg": None,
            "peg_note": "",
            "ref_price": _get_ref_price(stock_id, snap.get("open_price")),
            "limit_state": _calc_limit_state(snap.get("close_price"), stock_id),
            "_records": snap.get("records", []),
        }
        # PE/PB/PEG from live price + static fundamentals（在 close_price 覆蓋後計算）
        fund = _FUND.get(stock_id)
        d["pe"], d["pb"], d["peg"], d["peg_note"], d["pe_source"], d["pe_revision"] = _compute_pe_pb_peg(
            d.get("close_price"), fund
        )
        # 5 檔估值帶（valuation.json）
        d["valuation"] = _VALUATION.get(stock_id)
        # 盤後 (14:00+): 用 @stockID.csv 覆蓋 OHLCV + records
        from datetime import datetime as _dt

        if _dt.now().hour >= 14:
            if not d["_records"]:
                d["_records"] = _recent_rows_api(stock_id, n=10)
            actual_vol, day_info = _get_actual_day_volume(stock_id)
            if actual_vol is not None:
                d["estimated_day_volume"] = actual_vol
                d["volume_label"] = "盤後總量"
            if day_info is not None:
                if day_info.get("close") is not None:
                    d["close_price"] = day_info["close"]
                if day_info.get("open") is not None:
                    d["open_price"] = day_info["open"]
                if day_info.get("high") is not None:
                    d["high_price"] = day_info["high"]
                if day_info.get("low") is not None:
                    d["low_price"] = day_info["low"]
                if d["close_price"] is not None and d["open_price"] is not None:
                    d["price_diff"] = round(d["close_price"] - d["open_price"], 2)
                d["limit_state"] = _calc_limit_state(d["close_price"], stock_id)
            if actual_vol and actual_vol > (d.get("deal_volume") or 0):
                d["deal_volume"] = actual_vol
                d["deal_amount"] = int(actual_vol * d["close_price"]) if d.get("close_price") else None
            # 盤後重算 PE/PB/PEG（用收盤價）
            d["pe"], d["pb"], d["peg"], d["peg_note"], d["pe_source"], d["pe_revision"] = _compute_pe_pb_peg(
                d.get("close_price"), fund
            )
        # 補救 stock_type
        if not d["stock_type"] or d["stock_type"] == "unknown":
            d["stock_type"] = _detect_stock_type(stock_id, d["close_price"])
        # 補救 participation
        if d["participation_label"] in ("", "N/A", "等待資料") and d["total_in_volume"] + d["total_out_volume"] > 0:
            d["participation_score"] = round(
                (d["total_in_volume"] - d["total_out_volume"]) / (d["total_in_volume"] + d["total_out_volume"]) * 50, 1
            )
            d["participation_label"] = _score_to_label(d["participation_score"])
        return d
    except Exception:
        return None


def read_latest_csv(stock_id: str) -> dict | None:
    """讀取最新 CSV 資料（作為 snapshot 不存在時的降級方案）。
    盤後(14:00+)若 snapshot 無有效價格，無條件從 CSV/@stockID 補齊。"""
    from datetime import datetime as _dt

    is_after_close = _dt.now().hour >= 14
    # 優先讀取 snapshot（0.5 秒更新，1KB 小檔案）
    snap = read_snapshot(stock_id)
    if snap is not None and snap.get("close_price") is not None:
        return snap
    # 盤後: 若 snapshot 無有效 close_price，從 CSV 重建完整資料
    if is_after_close and snap is not None:
        # 嘗試從 @stockID.csv 取得今日收盤、成交量等
        actual_vol, day_info = _get_actual_day_volume(stock_id)
        if day_info and day_info.get("close") is not None:
            # 用 @stockID 的 OHLC 覆蓋
            snap["close_price"] = day_info["close"]
            snap["open_price"] = day_info.get("open")
            snap["high_price"] = day_info.get("high")
            snap["low_price"] = day_info.get("low")
            snap["deal_volume"] = actual_vol or 0
            snap["deal_amount"] = int((actual_vol or 0) * day_info["close"]) if actual_vol else 0
            snap["volume_label"] = "盤後總量"
            snap["estimated_day_volume"] = actual_vol or 0
        # 補 records（若無）
        if not snap.get("_records"):
            snap["_records"] = _recent_rows_api(stock_id, n=10)
        if snap.get("close_price") is not None:
            return snap
    # 降級：讀取 5 秒 CSV 最後一筆
    path = f"{stock_id}.csv"
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return None
        row = rows[-1]
        buy_prices = _parse_list(row.get("buy_prices", ""))
        buy_volumes = _parse_list(row.get("buy_volumes", ""))
        sell_prices = _parse_list(row.get("sell_prices", ""))
        sell_volumes = _parse_list(row.get("sell_volumes", ""))
        buy_total_volume = _num(row, "buy_total_volume", int) or sum(int(v) for v in buy_volumes if v)
        sell_total_volume = _num(row, "sell_total_volume", int) or sum(int(v) for v in sell_volumes if v)
        buy_sell_imbalance = _num(row, "buy_sell_imbalance", int)
        if buy_sell_imbalance is None and (buy_total_volume or sell_total_volume):
            buy_sell_imbalance = (buy_total_volume or 0) - (sell_total_volume or 0)
        pct_val = row.get("pct_of_yesterday_avg", "")
        pct_of_yesterday_avg = _num(row, "pct_of_yesterday_avg")
        if pct_val == "pct_of_yesterday_avg":
            pct_of_yesterday_avg = None
        close_price = _normalize_price(_num(row, "close_price"))
        open_price = _normalize_price(_num(row, "open_price"))
        price_diff = _num(row, "price_diff")
        if price_diff is None and close_price is not None and open_price is not None:
            price_diff = round(close_price - open_price, 2)
        deal_amount = _num(row, "deal_amount")
        deal_volume = _num(row, "deal_volume", int)
        if deal_amount is None and close_price is not None and deal_volume:
            deal_amount = round(close_price * deal_volume, 0)
        # 若隱含成交價不合理 (>20000 元/股)，視為 API 原始整數金額，正規化
        if deal_amount is not None and deal_volume and deal_volume > 0:
            implied = deal_amount / deal_volume
            if implied > 20000:
                deal_amount = round(deal_amount / 10000, 0)
        stock_type = row.get("stock_type", "")
        if not stock_type or stock_type == "unknown":
            stock_type = _detect_stock_type(stock_id, close_price)
        participation_score = _num(row, "participation_score")
        participation_label = row.get("participation_label", "")
        if participation_label in ("", "N/A", "等待資料") and participation_score is not None:
            participation_label = _score_to_label(participation_score)
        elif not participation_label or participation_label in ("N/A", "等待資料"):
            total_in = _num(row, "total_in_volume", int) or 0
            total_out = _num(row, "total_out_volume", int) or 0
            if total_in + total_out > 0:
                participation_score = round((total_in - total_out) / (total_in + total_out) * 50, 1)
                participation_label = _score_to_label(participation_score)

        def _normalize_volume(val):
            if val is None:
                return None
            try:
                return max(0, int(val))
            except (TypeError, ValueError):
                return None

        # 累積成交總額/總量（CSV 中有 cumulative_ 前綴的欄位）
        cum_vol = _normalize_volume(_num(row, "cumulative_volume", int))
        cum_amt = None
        if cum_vol and close_price:
            cum_amt = int(cum_vol * close_price)

        d = {
            "stock_id": row.get("stock_id", stock_id),
            "stock_name": get_stock_name(stock_id),
            "buy_prices": buy_prices,
            "buy_volumes": buy_volumes,
            "sell_prices": sell_prices,
            "sell_volumes": sell_volumes,
            "buy_total_volume": max(0, buy_total_volume),
            "sell_total_volume": max(0, sell_total_volume),
            "buy_sell_imbalance": buy_sell_imbalance,
            # 優先使用累積值，區間值為降級
            "deal_amount": cum_amt if cum_amt else deal_amount,
            "close_price": close_price,
            "open_price": open_price,
            "high_price": _normalize_price(_num(row, "high_price")),
            "low_price": _normalize_price(_num(row, "low_price")),
            "price_diff": price_diff,
            "deal_volume": cum_vol if cum_vol else _normalize_volume(deal_volume),
            "trade_count": _num(row, "trade_count", int),
            "total_in_volume": _normalize_volume(_num(row, "total_in_volume", int)),
            "total_out_volume": _normalize_volume(_num(row, "total_out_volume", int)),
            "estimated_day_volume": _normalize_volume(_num(row, "estimated_day_volume", int)),
            "volume_label": row.get("volume_label", "估日量"),
            "pct_of_yesterday_avg": pct_of_yesterday_avg,
            "ma5": _normalize_price(_num(row, "ma5")),
            "ma10": _normalize_price(_num(row, "ma10")),
            "stock_type": stock_type,
            "timestamp": row.get("timestamp", ""),
            "participation_score": participation_score,
            "participation_label": participation_label
            if participation_label not in ("", "N/A", "等待資料")
            else "等待資料",
            "ref_price": _get_ref_price(stock_id, open_price),
            "limit_state": _calc_limit_state(close_price, stock_id),
        }
        # 盤後 (14:30+) 用 @stockID.csv 的真實數據覆蓋估算值
        actual_vol, day_info = _get_actual_day_volume(stock_id)
        if actual_vol is not None:
            d["estimated_day_volume"] = actual_vol
            d["volume_label"] = "盤後總量"
        if day_info is not None:
            if day_info.get("close") is not None:
                d["close_price"] = day_info["close"]
            if day_info.get("open") is not None:
                d["open_price"] = day_info["open"]
            if day_info.get("high") is not None:
                d["high_price"] = day_info["high"]
            if day_info.get("low") is not None:
                d["low_price"] = day_info["low"]
            # 重算漲跌價差與漲跌停狀態
            if d["close_price"] is not None and d["open_price"] is not None:
                d["price_diff"] = round(d["close_price"] - d["open_price"], 2)
            d["limit_state"] = _calc_limit_state(d["close_price"], stock_id)
        # PE/PB/PEG from live price + static fundamentals（在 close_price 覆蓋後計算）
        fund = _FUND.get(stock_id)
        d["pe"], d["pb"], d["peg"], d["peg_note"], d["pe_source"], d["pe_revision"] = _compute_pe_pb_peg(
            d.get("close_price"), fund
        )
        # 盤後用 actual_vol 覆蓋 deal_volume/deal_amount
        if actual_vol and actual_vol > (d.get("deal_volume") or 0):
            d["deal_volume"] = actual_vol
            d["deal_amount"] = int(actual_vol * d["close_price"]) if d.get("close_price") else None
        # MA backup: keep last known good value
        for key in ("ma5", "ma10"):
            if d[key] is None:
                d[key] = _LAST_KNOWN.get(stock_id, {}).get(key)
        return d
    except Exception:
        return None


# val必須為無符號,避免負值影響計算,目前方法存在瑕疵,為 bug 原因之一需修正


def _normalize_price(val):
    """將可能為 API 原始整數的價格正規化為 TWD。
    台灣個股價格合理範圍 1~15000，若超過 100000 視為原始整數 (/10000)；
    0 或負值視為無效，回傳 None。"""
    if val is None:
        return None
    try:
        if val <= 0:
            return None
    except TypeError:
        return None
    if abs(val) >= 100000:
        return round(val / 10000, 2)
    return val


def _load_stock_ref() -> dict:
    """從 stock_ref.json 載入 API 查詢的昨收/漲停/跌停參考價。建議程式入口先檢查自選股的ref_price是否存在昨收,不存在則使用此工具更新方法"""
    path = "stock_ref.json"
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_ref_price(stock_id: str, fallback_open=None):
    """取得漲跌顏色基準價（昨收價），含多重降級。
    優先: stock_ref.json (API) → @stockID.csv → open_price。"""
    # 1) API 查詢的昨收價
    ref = _load_stock_ref()
    entry = ref.get(stock_id, {})
    yst = _normalize_price(entry.get("yst_price"))
    if yst is not None:
        return yst
    # 2) @stockID.csv 最後一筆收盤價
    # (支援中英文欄位名),若檔案時間屬性不合理就可很快判斷,需要外部工具修護正確資料.建議程式入口先檢查
    path = f"@{stock_id}.csv"
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                rows = list(csv.DictReader(f))
            if rows:
                yst = _normalize_price(_num(rows[-1], "收盤價") or _num(rows[-1], "close_price"))
                if yst is not None:
                    return yst
        except Exception:
            pass
    # 3) 今日開盤價
    return fallback_open


def _tick_size(price: float) -> float:
    """台股檔位跳動（tick size）。"""
    if price < 10:
        return 0.01
    if price < 50:
        return 0.05
    if price < 100:
        return 0.1
    if price < 500:
        return 0.5
    if price < 1000:
        return 1.0
    return 5.0


def _tick_floor(price: float) -> float:
    """截斷到 tick（漲停價用）。"""
    if price is None:
        return None
    import math

    tk = _tick_size(price)
    return round(math.floor(price / tk + 1e-9) * tk, 2)


def _tick_ceil(price: float) -> float:
    """進位到 tick（跌停價用）。"""
    if price is None:
        return None
    import math

    tk = _tick_size(price)
    return round(math.ceil(price / tk - 1e-9) * tk, 2)


def _get_limit_prices(stock_id: str):
    """取得漲停價/跌停價（含 tick rounding）。
    優先: stock_ref.json API 提供的 up_price/down_price（交易所權威值，已考量除權息調整）
    降級: 昨收價 ×1.10 / ×0.90（標準 10%）
    所有價格依台股檔位規則截斷（漲停）或進位（跌停）。
    回傳 (up_price, down_price) 或 (None, None)。"""
    ref = _load_stock_ref()
    entry = ref.get(stock_id, {})
    api_up = _normalize_price(entry.get("up_price"))
    api_down = _normalize_price(entry.get("down_price"))
    # 優先信任 API 提供的漲跌停價（交易所權威值）。
    # 只要「漲停 > 跌停」即視為有效，不再強求「漲停 > 昨收 > 跌停」——
    # 昨收價可能因除權息/資料延遲而不一致，過去此條件會誤拒有效的 API 漲跌停值，
    # 導致降級成昨收 ±10% 估算（即「漲跌停沒被參考到」的 bug）。
    if api_up is not None and api_down is not None and api_up > api_down:
        # 以 tick rounding 修正（API 值可能未考慮檔位，如 172.15→172.0）
        return _tick_floor(api_up), _tick_ceil(api_down)
    # 降級：直接用昨收計算 ±10% + tick rounding
    yst = _get_ref_price(stock_id)
    if yst is not None and yst > 0:
        return _tick_floor(yst * 1.10), _tick_ceil(yst * 0.90)
    return None, None


def _calc_limit_state(close_price, stock_id):
    """判斷是否漲跌停。"""
    if close_price is None:
        return None
    up_price, down_price = _get_limit_prices(stock_id)
    if up_price is not None and close_price >= up_price:
        return "up"
    if down_price is not None and close_price <= down_price:
        return "down"
    return None


_fin_cache = None
_fin_cache_time = 0


def _load_financials():
    """載入財務數據（優先 analyst_eps.json → 降級 stock_financials.json）。
    含 1 小時快取。"""
    global _fin_cache, _fin_cache_time
    now = time.time()
    if _fin_cache is not None and now - _fin_cache_time < 3600:
        return _fin_cache

    result = {}
    # 1) 優先: analyst_eps.json (法人預估共識)
    analyst_path = "analyst_eps.json"
    if os.path.exists(analyst_path):
        try:
            with open(analyst_path, encoding="utf-8") as f:
                analyst = json.load(f)
            for code, s in analyst.get("stocks", {}).items():
                peg_info = s.get("peg", {}) or {}
                result[code] = {
                    "pe": peg_info.get("forward_pe"),
                    "pb": None,
                    "peg": peg_info.get("peg"),
                    "peg_note": f"法人預估EPS={
                        s.get(
                            'consensus_eps',
                            '?')} ({
                        s.get(
                            'method',
                            '?')})",
                }
        except Exception:
            pass

    # 2) 降級: stock_financials.json (近四季 EPS)
    fin_path = "stock_financials.json"
    if os.path.exists(fin_path):
        try:
            with open(fin_path, encoding="utf-8") as f:
                fin = json.load(f)
            for code, s in fin.get("stocks", {}).items():
                if code not in result or result[code].get("pe") is None:
                    result[code] = {
                        "pe": s.get("pe"),
                        "pb": s.get("pb"),
                        "peg": s.get("peg"),
                        "peg_note": s.get("peg_note", ""),
                    }
        except Exception:
            pass

    # 3) 補 market_cap.json 的 PE/PB
    mcap = _load_market_cap()
    if mcap:
        for code, s in mcap.get("stocks", {}).items():
            if code in result:
                if result[code].get("pe") is None:
                    result[code]["pe"] = s.get("pe")
                if result[code].get("pb") is None:
                    result[code]["pb"] = s.get("pb")

    _fin_cache = result
    _fin_cache_time = now
    return result


def _load_fundamentals():
    """Load fundamentals.json once; PE/PB/PEG computed from live price.
    PE = close / eps_ttm ; PB = close / bps ; PEG = (close/forward_eps) / |growth|
    """
    path = "fundamentals.json"
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("stocks", {})
        except Exception:
            pass
    return {}


def _compute_pe_pb_peg(close_price, fund):
    """Compute PE/PB/PEG from live close_price + static fundamentals.
    Returns (pe, pb, peg, peg_note, pe_source, revision).
    pe_source: 'forward' | 'trailing' | None
    revision: 'up' (fwd_eps > ttm_eps) | 'down' (fwd_eps < ttm_eps) | None
    PE prefers forward_eps if available, falls back to eps_ttm."""
    if not fund or close_price is None:
        return None, None, None, "", None, None
    eps = fund.get("eps_ttm")
    bps = fund.get("bps")
    growth = fund.get("eps_growth_pct")
    fwd_eps = fund.get("forward_eps")

    # PE: prefer forward_eps (analyst estimate), fallback to trailing eps_ttm
    forward_pe = round(close_price / fwd_eps, 2) if fwd_eps and fwd_eps > 0 else None
    trailing_pe = round(close_price / eps, 2) if eps and eps > 0 else None
    pe = forward_pe if forward_pe is not None else trailing_pe
    pe_source = "forward" if forward_pe is not None else ("trailing" if trailing_pe is not None else None)

    # Revision: compare forward_eps vs eps_ttm (proxy for analyst revision
    # direction)
    revision = None
    if fwd_eps and eps and eps > 0:
        if fwd_eps > eps:
            revision = "up"
        elif fwd_eps < eps:
            revision = "down"

    pb = round(close_price / bps, 2) if bps and bps > 0 else None

    peg = None
    note = fund.get("note", "")
    use_eps = fwd_eps if fwd_eps else eps

    if pe and growth and abs(growth) > 0.1 and use_eps:
        peg = round(pe / abs(growth), 2)
        src = "forward" if fwd_eps else "ttm"
        note = f"{src}EPS={use_eps} | {note}"
    elif use_eps and use_eps > 0:
        src = "forward" if fwd_eps else "ttm"
        note = f"{src}EPS={use_eps} | no PEG"

    return pe, pb, peg, note, pe_source, revision


_LAST_KNOWN = {}
_FUND = _load_fundamentals()


_VALUATION_CACHE = None
_VALUATION_CACHE_TIME = 0


def _load_valuation() -> dict:
    """載入 valuation.json（5 檔估值帶）。含 1 小時快取。"""
    global _VALUATION_CACHE, _VALUATION_CACHE_TIME
    now = time.time()
    if _VALUATION_CACHE is not None and now - _VALUATION_CACHE_TIME < 3600:
        return _VALUATION_CACHE
    path = "valuation.json"
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                _VALUATION_CACHE = json.load(f).get("stocks", {})
            _VALUATION_CACHE_TIME = now
            return _VALUATION_CACHE
        except Exception:
            pass
    return {}


_VALUATION = _load_valuation()


def _detect_stock_type(stock_id: str, price=None) -> str:
    """依市值排名分類：大型/中型/小型。
    優先使用 market_cap.json（每月更新），降級使用內建 0050 清單。"""
    # 1) market_cap.json 排名
    mcap = _load_market_cap()
    if mcap and stock_id in mcap.get("stocks", {}):
        tier = mcap["stocks"][stock_id].get("tier", "")
        if tier in ("large_cap", "mid_cap", "small_cap"):
            return tier
    # 2) 降級：內建 0050 成分股清單
    tw50 = {
        "2330",
        "2317",
        "2454",
        "2412",
        "2881",
        "2882",
        "2886",
        "2891",
        "2308",
        "2303",
        "2327",
        "2344",
        "2345",
        "2357",
        "2379",
        "2382",
        "2395",
        "2408",
        "3008",
        "3034",
        "3045",
        "3711",
        "4904",
        "4938",
        "5871",
        "5876",
        "5880",
        "6505",
        "1301",
        "1303",
        "1326",
        "2002",
        "2207",
        "2603",
        "2609",
        "2610",
        "2615",
        "2633",
        "2801",
        "2880",
        "2883",
        "2884",
        "2885",
        "2887",
        "2888",
        "2890",
        "2892",
        "2912",
        "3443",
        "3533",
        "3661",
        "5269",
        "6415",
        "8046",
        "8299",
        "8454",
    }
    if stock_id in tw50:
        return "large_cap"
    if len(stock_id) == 4 and stock_id[0] in ("2", "3", "4", "5", "6", "8", "9"):
        return "mid_cap"
    return "small_cap"


def _score_to_label(score):
    if score > 30:
        return "主力強力買進"
    elif score > 10:
        return "主力溫和買進"
    elif score > -10:
        return "散戶盤整"
    elif score > -30:
        return "主力溫和賣出"
    else:
        return "主力強力賣出"


def _parse_list(val):
    """Parse CSV list string like '[1,2,3]' → [1,2,3]"""
    try:
        if isinstance(val, str) and val.startswith("["):
            return [float(x.strip()) for x in val.strip("[]").split(",") if x.strip()]
    except Exception:
        pass
    return []


def _num(row, key, cast=float):
    try:
        v = row.get(key)
        if v is None or v == "":
            return None
        return cast(v)
    except (ValueError, TypeError):
        return None


def poll_worker():
    """背景輪詢：每 0.5 秒掃描所有 snapshot 並推送 SSE。
    移除 mtime 比對以確保 0.5s 更新率（snapshot 為小檔，讀取成本低）。"""
    while True:
        stocks = get_active_stocks()
        data = {}
        for sid in stocks:
            # 直接讀取 snapshot（~1KB，0.5s 間隔無 I/O 壓力）
            rec = read_latest_csv(sid)
            d = rec if rec else _empty_card(sid)
            # 使用 snapshot 內建的 records；若無則降級讀 CSV
            if not d.get("_records"):
                d["_records"] = _recent_rows_api(sid)
            data[sid] = d
        if data:
            sse_queue.put(data)
        time.sleep(DATA_INTERVAL)


def _recent_rows_api(stock_id: str, n: int = 5) -> list:
    # 往前多讀一些，確保低量股也能湊滿 n 列有成交量的資料
    rows = read_recent_rows(stock_id, max(n * 6, 30))
    records = []
    for r in rows:
        price = _normalize_price(_num(r, "close_price"))
        vol = max(0, _num(r, "deal_volume", int) or 0)
        # int32 溢位防護: 負值轉無號 (> 2^31 視為溢位)
        if vol < 0:
            vol = vol + 0x100000000
        amt = _num(r, "deal_amount") or 0
        if amt < 0:
            amt = amt + 0x100000000
        if amt > 0 and vol > 0 and amt / vol > 20000:
            amt = round(amt / 10000, 0)
        in_vol = max(0, _num(r, "total_in_volume", int) or 0)
        out_vol = max(0, _num(r, "total_out_volume", int) or 0)
        if in_vol < 0:
            in_vol = in_vol + 0x100000000
        if out_vol < 0:
            out_vol = out_vol + 0x100000000
        # 跳過完全無成交量的列（內外盤區間 delta 為 0）
        if vol <= 0 and in_vol <= 0 and out_vol <= 0:
            continue
        records.append(
            {
                "time": r.get("timestamp", "")[-8:],
                "price": price,
                "vol": vol,
                "in_vol": in_vol,
                "out_vol": out_vol,
                "amt": max(0, amt),
            }
        )
    return records[-n:] if len(records) > n else records  # 不足 n 列就顯示實際有的


def read_recent_rows(stock_id: str, n: int = 5) -> list:
    path = f"{stock_id}.csv"
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        return rows[-n:]
    except Exception:
        return []


def _get_actual_day_volume(stock_id: str):
    """盤後從 @stockID.csv 讀取當日實際總量與收盤價，用於覆蓋 5 秒 CSV 的估算值。"""
    now = datetime.now()
    if now.hour < 14 or (now.hour == 14 and now.minute < 30):
        return None, None
    path = f"@{stock_id}.csv"
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        today = now.strftime("%Y%m%d")
        for r in reversed(rows):
            if r.get("日期", "") == today or r.get("date", "") == today:
                vol = _num(r, "成交股數") or _num(r, "total_volume")
                vol = int(vol) if vol is not None and vol > 0 else None
                close = _normalize_price(_num(r, "收盤價") or _num(r, "close_price"))
                open_p = _normalize_price(_num(r, "開盤價") or _num(r, "open_price"))
                high_p = _normalize_price(_num(r, "最高價") or _num(r, "high_price"))
                low_p = _normalize_price(_num(r, "最低價") or _num(r, "low_price"))
                day_info = {
                    "vol": vol,
                    "close": close,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                }
                return vol, day_info
        return None, None
    except Exception:
        return None, None


def _empty_card(stock_id: str) -> dict:
    return {
        "stock_id": stock_id,
        "stock_name": get_stock_name(stock_id),
        "close_price": None,
        "open_price": None,
        "timestamp": "",
        "high_price": None,
        "low_price": None,
        "price_diff": None,
        "deal_volume": 0,
        "deal_amount": None,
        "trade_count": 0,
        "total_in_volume": 0,
        "total_out_volume": 0,
        "estimated_day_volume": 0,
        "volume_label": "盤前預估量",
        "pct_of_yesterday_avg": None,
        "ma5": None,
        "ma10": None,
        "stock_type": "unknown",
        "participation_score": None,
        "pe_source": None,
        "pe_revision": None,
        "participation_label": "等待資料",
        "buy_prices": [],
        "buy_volumes": [],
        "sell_prices": [],
        "sell_volumes": [],
        "buy_total_volume": 0,
        "sell_total_volume": 0,
        "buy_sell_imbalance": 0,
        "ref_price": None,
        "limit_state": None,
    }


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/stream")
def stream():
    def event_stream():
        while True:
            try:
                data = sse_queue.get(timeout=30)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/stocks")
def api_stocks():
    result = {}
    for sid in get_active_stocks():
        rec = read_latest_csv(sid)
        result[sid] = rec if rec else _empty_card(sid)
    # Merge financial ratios (PE, PB, PEG, etc.) from cached financial data
    # `_load_financials` returns a dict keyed by stock code with fields:
    #   pe, pb, peg, peg_note (and potentially pe_source, pe_revision)
    # Update each stock record in-place so the front‑end cards can display
    # them.
    fin_data = _load_financials()
    for sid, rec in result.items():
        # Ensure rec is a mutable dict; _empty_card returns a dict as well.
        if isinstance(rec, dict):
            fd = fin_data.get(sid, {})
            if fd:
                rec.update(
                    {
                        "pe": fd.get("pe"),
                        "pb": fd.get("pb"),
                        "peg": fd.get("peg"),
                        "pe_source": fd.get("pe_source"),
                        "pe_revision": fd.get("pe_revision"),
                        "peg_note": fd.get("peg_note"),
                    }
                )
    return jsonify(result)


@app.route("/api/records")
def api_records():
    result = {}
    for sid in get_active_stocks():
        rows = read_recent_rows(sid, 5)
        records = []
        for r in rows:
            price = _normalize_price(_num(r, "close_price"))
            vol = max(0, _num(r, "deal_volume", int) or 0)
            amt = _num(r, "deal_amount") or 0
            if amt > 0 and vol > 0 and amt / vol > 20000:
                amt = round(amt / 10000, 0)
            records.append(
                {
                    "time": r.get("timestamp", "")[-8:],
                    "price": price,
                    "vol": vol,
                    "in_vol": max(0, _num(r, "total_in_volume", int) or 0),
                    "out_vol": max(0, _num(r, "total_out_volume", int) or 0),
                    "amt": max(0, amt),
                }
            )
        result[sid] = records
    return jsonify(result)


@app.route("/api/watchlists")
def api_watchlists():
    wl = load_watchlists()
    meta = load_watchlist_meta()
    return jsonify(
        {
            "watchlists": list(wl.keys()),
            "active": _active_watchlist,
            "meta": meta,
            "content": wl,
        }
    )


@app.route("/api/watchlist/<name>", methods=["POST"])
def api_switch_watchlist(name):
    global _active_watchlist
    wl = load_watchlists()
    if name in wl:
        _active_watchlist = name
        return jsonify({"ok": True, "active": name, "stocks": wl[name].get("stocks", [])})
    return jsonify({"ok": False, "error": f"自選股 '{name}' 不存在"}), 404


@app.route("/api/watchlist/add", methods=["POST"])
def api_watchlist_add():
    """新增股票到目前自選股，同步寫入 watchlist.json。"""
    data = request.get_json(silent=True) or {}
    stock_id = str(data.get("stock_id", "")).strip()
    market = str(data.get("market", "stocks")).strip()
    if not stock_id or len(stock_id) < 4 or len(stock_id) > 6:
        return jsonify({"ok": False, "error": "請提供有效的 4-6 碼股票代號"}), 400
    if market not in ("stocks", "TWOTC"):
        market = "stocks"
    # alphanumeric allowed (warrants/ETFs may contain letters e.g. 00980A)
    if not all(c.isdigit() or c.isalpha() for c in stock_id):
        return jsonify({"ok": False, "error": "股票代號僅接受英數字"}), 400

    suggested = _guess_market_from_market_cap(stock_id)
    corrected_market = None
    if suggested and suggested != market:
        corrected_market = suggested
        market = suggested

    wl = load_watchlists()
    entry = wl.get(_active_watchlist, wl.get("自選股1", {"stocks": [], "TWOTC": [], "futures": []}))
    stocks = entry.get("stocks", []) or []
    twotc = entry.get("TWOTC", []) or []
    if stock_id in stocks or stock_id in twotc:
        return jsonify({"ok": False, "error": f"{stock_id} 已在自選股中"})

    if market == "TWOTC":
        twotc.append(stock_id)
        entry["TWOTC"] = twotc
    else:
        stocks.append(stock_id)
        entry["stocks"] = stocks
    entry.setdefault("TWOTC", twotc)
    entry.setdefault("stocks", stocks)
    wl[_active_watchlist] = entry
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)

    # 嘗試為新股票取得昨日資料
    _fetch_new_stock_data(stock_id)

    # 更新全局股票清單
    global STOCKS
    STOCKS = get_active_stocks()
    response = {"ok": True, "added": stock_id, "market": market, "name": get_stock_name(stock_id)}
    if corrected_market:
        response["corrected_market"] = corrected_market
    return jsonify(response)


@app.route("/api/watchlist/remove", methods=["POST"])
def api_watchlist_remove():
    """從目前自選股移除股票，同步寫入 watchlist.json。"""
    data = request.get_json(silent=True) or {}
    stock_id = str(data.get("stock_id", "")).strip()

    wl = load_watchlists()
    entry = wl.get(_active_watchlist, wl.get("自選股1", {"stocks": [], "TWOTC": [], "futures": []}))
    stocks = entry.get("stocks", []) or []
    twotc = entry.get("TWOTC", []) or []
    removed_group = None
    if stock_id in stocks:
        stocks.remove(stock_id)
        entry["stocks"] = stocks
        removed_group = "stocks"
    elif stock_id in twotc:
        twotc.remove(stock_id)
        entry["TWOTC"] = twotc
        removed_group = "TWOTC"
    else:
        return jsonify({"ok": False, "error": f"{stock_id} 不在自選股中"})

    wl[_active_watchlist] = entry
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)

    global STOCKS
    STOCKS = get_active_stocks()
    return jsonify({"ok": True, "removed": stock_id, "group": removed_group, "stocks": stocks, "TWOTC": twotc})


@app.route("/api/stock/search")
def api_stock_search():
    """模糊搜尋股票（代號 or 名稱），回傳前 20 筆。"""
    q = (request.args.get("q", "")).strip()
    if not q:
        return jsonify({"results": []})
    names = load_names()
    results = []
    q_lower = q.lower()
    for sid, cname in names.items():
        if q in sid or q_lower in cname.lower():
            results.append({"symbol": sid, "name": cname})
        if len(results) >= 20:
            break
    return jsonify({"results": results})


def _fetch_new_stock_data(stock_id: str):
    """為新加入的自選股取得昨日收盤資料、參考價，並在 fundamentals.json 建立佔位。"""
    import subprocess
    import sys

    # 1. fundamentals.json 補佔位（避免 PE/PB/PEG 永遠 --）
    _ensure_fund_placeholder(stock_id)
    try:
        result = subprocess.run(
            [sys.executable, "fetch_daily_close.py", "--stocks", stock_id, "--compare-only"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if "無異常" not in result.stdout:
            subprocess.run(
                [sys.executable, "fetch_daily_close.py", "--stocks", stock_id],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
    except Exception:
        pass


def _ensure_fund_placeholder(stock_id: str):
    """在 fundamentals.json 中加入新股票的佔位條目（若不存在），並重載 _FUND。"""
    global _FUND
    fund_path = "fundamentals.json"
    try:
        import json as _json

        if os.path.exists(fund_path):
            with open(fund_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
        else:
            data = {"updated": "", "stocks": {}}
        if stock_id not in data.get("stocks", {}):
            data.setdefault("stocks", {})[stock_id] = {
                "name": get_stock_name(stock_id),
                "eps_ttm": None,
                "bps": None,
                "eps_growth_pct": None,
                "forward_eps": None,
                "note": "new_stock_placeholder",
            }
            with open(fund_path, "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)
            # 重載 _FUND 讓立即生效
            _FUND = data.get("stocks", {})
    except Exception:
        pass


@app.route("/api/lookup")
def api_lookup():
    """股票代號 ↔ 公司名稱 雙向查詢。
    ?symbol=2330 → 回傳公司名稱
    ?name=台積電 → 回傳股票代號
    ?q=xxx → 自動判斷（先試代號，再試名稱）"""
    names = load_names()
    symbol = request.args.get("symbol", "")
    name = request.args.get("name", "")
    q = request.args.get("q", "")

    if symbol:
        result = names.get(symbol.strip())
        return jsonify({"query": symbol, "result": result, "type": "symbol_to_name"})
    if name:
        name = name.strip()
        match = next((sid for sid, cname in names.items() if cname == name), None)
        return jsonify({"query": name, "result": match, "type": "name_to_symbol"})
    if q:
        q = q.strip()
        if q in names:
            return jsonify({"query": q, "result": names[q], "type": "symbol_to_name"})
        match = next((sid for sid, cname in names.items() if cname == q), None)
        if match:
            return jsonify({"query": q, "result": match, "type": "name_to_symbol"})
        if q.isdigit() and len(q) == 4:
            return jsonify(
                {"query": q, "result": None, "type": "symbol_to_name", "hint": f"'{q}' 不在 stock_names.json 中"}
            )
        return jsonify(
            {"query": q, "result": None, "type": "unknown", "hint": f"找不到 '{q}'，請確認股票代號或公司名稱"}
        )
    return jsonify({"error": "請提供 symbol= 或 name= 或 q= 查詢參數"}), 400


@app.route("/api/options")
def api_options():
    """Put/Call 合理價分析。查詢參數: S(現貨價), K(履約價), days(到期天數),
    call(市價), put(市價), vol(波動率,預設0.25)"""
    try:
        S = float(request.args.get("S", 0))
        K = float(request.args.get("K", 0))
        days = int(request.args.get("days", 30))
        call_mkt = float(request.args.get("call", 0))
        put_mkt = float(request.args.get("put", 0))
        vol = float(request.args.get("vol", 0.25))
    except (TypeError, ValueError):
        return jsonify({"error": "無效參數"}), 400

    if S <= 0 or K <= 0:
        return jsonify({"error": "S 和 K 必須大於 0"}), 400

    pricing = OptionPricing()
    result = pricing.evaluate(S, K, days, call_mkt, put_mkt, vol)

    pcr = put_call_ratio_analysis(
        call_vol=float(request.args.get("cv", call_mkt or 1)),
        put_vol=float(request.args.get("pv", put_mkt or 1)),
        call_oi=float(request.args.get("coi", 0)) or None,
        put_oi=float(request.args.get("poi", 0)) or None,
    )

    return jsonify(
        {
            "S": S,
            "K": K,
            "days": days,
            "fair_call": result.fair_call,
            "fair_put": result.fair_put,
            "call_premium_pct": result.call_premium_pct,
            "put_premium_pct": result.put_premium_pct,
            "call_iv": result.call_iv,
            "put_iv": result.put_iv,
            "parity_diff": result.parity_diff,
            "pcr": pcr,
        }
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    poll_thread = threading.Thread(target=poll_worker, daemon=True)
    poll_thread.start()

    print(f"Dashboard → http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
