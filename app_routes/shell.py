"""Agents + Tools cockpit with a central Copilot chat (liquidround pattern).

`/app` is the central **Copilot** chat (the Agents view). Every Tool page renders
in the same center pane via `app_shell()`. The left rail has two role-scoped
sections — **Agents** (Copilot) and **Tools**. There is no right rail; the copilot
is the center. Roles: investor / supplier / payer / admin (Admin = full
back-office access — segregation of duties is collapsed to the single Admin role).
"""

from __future__ import annotations

import json
import secrets

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, Style, NotStr,
    Div, Span, A, Button, Form, Input, Textarea, P, H2,
)
from starlette.responses import JSONResponse, StreamingResponse

from app import rt
from utils.i18n import t, get_lang, LANG_META, SUPPORTED_LANGS, DEFAULT_LANG
from landing.components import TAILWIND_CONFIG, SITE_NAME
from utils.copilot import copilot_available

# ── Tool catalog: key -> (i18n_key, icon, href) ───────────────────────────
_COPILOT = ("copilot", "nav_copilot", "✨", "/app")
_FLEET = ("agentfleet", "nav_agent_fleet", "\U0001F9E0", "/app/admin/agents")
TOOLS = {
    "dashboard":    ("nav_dashboard",          "\U0001F4CA", "/app/dashboard"),
    "marketplace":  ("mkt_eyebrow",            "\U0001F9FE", "/app/marketplace"),
    "auctions":     ("nav_auctions",           "\U0001F528", "/app/marketplace/auctions"),
    "secondary":    ("nav_secondary",          "\U0001F501", "/app/marketplace/secondary"),
    "portfolio":    ("port_eyebrow",           "\U0001F4C1", "/app/portfolio"),
    "statement":    ("nav_statement",          "\U0001F9EE", "/app/statement"),
    "autoinvest":   ("nav_autoinvest",         "⚙️",         "/app/auto-invest"),
    "triage":       ("nav_triage",             "\U0001F4AC", "/app/triage"),
    "reports":      ("nav_assistant",          "\U0001F4C8", "/app/assistant"),
    "supplier":     ("nav_supplier",           "\U0001F9FE", "/app/supplier"),
    "profile":      ("nav_profile",            "\U0001F464", "/app/supplier/profile"),
    "payer":        ("nav_payer",              "\U0001F4E9", "/app/payer"),
    "console":      ("nav_admin",              "\U0001F6E0️", "/app/admin"),
    "onboarding":   ("nav_admin_onboarding",   "\U0001FAAA", "/app/admin/onboarding"),
    "processing":   ("nav_processing",         "\U0001F9FE", "/app/admin/processing"),
    "risk":         ("nav_admin_risk",         "⚠️",         "/app/admin/risk"),
    "scoring":      ("nav_scoring",            "\U0001F3AF", "/app/admin/scoring"),
    "funding":      ("nav_admin_funding",      "\U0001F4B8", "/app/admin/funding"),
    "collections":  ("nav_collections",        "\U0001F4E9", "/app/admin/collections"),
    "accounting":   ("nav_accounting",         "\U0001F4B7", "/app/admin/accounting"),
    "compliance":   ("nav_compliance",         "\U0001F6E1️", "/app/admin/compliance"),
    "integrations": ("nav_integrations",       "\U0001F517", "/app/admin/integrations"),
    "reports_admin":("nav_admin_reports",      "\U0001F4C8", "/app/admin/reports"),
    "audit":        ("nav_admin_audit",        "\U0001F4DC", "/app/admin/audit"),
    "pipeline":     ("nav_pipeline",           "\U0001F4C7", "/app/crm"),
    "drive":        ("nav_drive",              "\U0001F5C2️", "/app/drive"),
    "docs":         ("nav_docs",               "\U0001F4DD", "/app/docs"),
    "mail":         ("nav_mail",               "✉️",         "/app/mail"),
}

# Role-scoped tool lists (order = display order).
_TOOLS_BY_ROLE = {
    "investor": ["dashboard", "marketplace", "auctions", "secondary", "portfolio",
                 "statement", "autoinvest", "triage", "reports"],
    "supplier": ["supplier", "profile"],
    "payer":    ["payer"],
    "admin":    ["console", "onboarding", "processing", "risk", "scoring", "funding",
                 "collections", "accounting", "compliance", "integrations",
                 "reports_admin", "audit", "pipeline", "drive", "docs", "mail",
                 "dashboard", "marketplace", "auctions", "secondary", "portfolio", "statement"],
}


def _nav_for(role: str):
    """Return [(section_i18n_key, [(key, i18n_key, icon, href), ...]), ...] for a role."""
    tool_keys = _TOOLS_BY_ROLE.get(role, _TOOLS_BY_ROLE["investor"])
    tools = [(k,) + TOOLS[k] for k in tool_keys]
    agents = [_COPILOT] + ([_FLEET] if role == "admin" else [])
    return [("nav_sec_agents", agents), ("nav_sec_tools", tools)]


def _active_key(role: str, current_path: str) -> str:
    if current_path == "/app":
        return "copilot"
    if current_path == "/app/admin/agents":
        return "agentfleet"
    for k in _TOOLS_BY_ROLE.get(role, []):
        if TOOLS[k][2] == current_path:
            return k
    return ""


SHELL_CSS = """
.ws { display:grid; grid-template-columns:262px 1fr; grid-template-rows:56px 1fr;
  grid-template-areas:"top top" "left center"; height:100vh; overflow:hidden; }
.ws-top { grid-area:top; display:flex; align-items:center; justify-content:space-between;
  padding:0 16px; background:#FFFFFF; border-bottom:1px solid #E3DFD2; gap:8px; }
.ws-left { grid-area:left; background:#FFFFFF; border-right:1px solid #E3DFD2; overflow-y:auto; padding:10px 0; }
.ws-center { grid-area:center; overflow-y:auto; background:#F7F6F1; }
.ws-burger { display:none; background:none; border:0; font-size:22px; line-height:1; color:#14231B;
  cursor:pointer; padding:4px 8px; margin-right:2px; }
.ws-backdrop { display:none; position:fixed; inset:56px 0 0 0; background:rgba(0,0,0,.35); z-index:40; }

/* ── Mobile: left nav becomes a slide-in drawer; PDF pane goes full-width ── */
@media (max-width: 860px) {
  .ws { grid-template-columns:1fr; grid-template-areas:"top" "center"; }
  .ws-burger { display:block; }
  .ws-left { position:fixed; top:56px; bottom:0; left:-280px; width:264px; z-index:50;
    box-shadow:2px 0 18px rgba(0,0,0,.18); transition:left .2s ease; }
  .ws.nav-open .ws-left { left:0; }
  .ws.nav-open .ws-backdrop { display:block; }
  .ws-top { padding:0 8px; }
  .pdf-pane { width:100% !important; right:-100%; }
  .pdf-pane.wide { width:100% !important; }
  .ws-center section:first-of-type { padding:10px 14px !important; }
  .chat-form, .chat-cards { padding-left:14px; padding-right:14px; }
}

/* Compact page header: turn the first section into a slim sticky title bar so
   content fills the pane (liquidround / pehero pattern) — no wasted real estate. */
.ws-center section { padding-top:22px !important; padding-bottom:22px !important; }
.ws-center section:first-of-type {
  padding:11px 24px !important; border-top:0 !important; border-bottom:1px solid #E3DFD2;
  position:sticky; top:0; z-index:6; background:#FBFAF6; }
.ws-center section:first-of-type > div { max-width:none !important; padding:0 !important; margin:0 !important; }
.ws-center section:first-of-type .font-mono { display:none !important; }
.ws-center section:first-of-type h1 { font-size:18px !important; font-weight:600 !important;
  line-height:1.3 !important; letter-spacing:-.2px !important; margin:0 !important; max-width:none !important; }
.ws-center section:first-of-type p { font-size:12.5px !important; color:#7A867E !important;
  margin:3px 0 0 !important; max-width:none !important; line-height:1.4 !important; }
.nav-sec { margin:2px 0 10px; }
.nav-head { padding:8px 16px 4px; font-size:10.5px; text-transform:uppercase; letter-spacing:.9px; color:#7A867E; font-weight:700; }
.nav-item { display:flex; align-items:center; gap:9px; padding:8px 16px; font-size:13.5px; color:#415046;
  text-decoration:none; border-left:3px solid transparent; }
.nav-item:hover { background:#EFEDE4; color:#14231B; }
.nav-item.active { background:#CFE5DA; color:#0F3226; border-left-color:#1F5D43; font-weight:600; }
.nav-ic { width:18px; text-align:center; }
.nav-newchat { color:#1F5D43; font-weight:600; }
.nav-history { display:flex; flex-direction:column; }
.nav-hist { font-size:12.5px; color:#5b6b62; padding:6px 16px 6px 43px; white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis; border-left:3px solid transparent; }
.nav-hist:hover { background:#EFEDE4; color:#14231B; }
.nav-hist.active { background:#EFEDE4; color:#0F3226; border-left-color:#CFC8B4; }

/* Central Copilot chat */
.chat { display:flex; flex-direction:column; height:100%; max-width:860px; width:100%; margin:0 auto; }
.chat-head { display:flex; align-items:center; justify-content:space-between; padding:10px 24px;
  border-bottom:1px solid #E3DFD2; background:#FBFAF6; }
.chat-head-title { color:#415046; font-size:12px; font-weight:600; }
.chat-actions { display:flex; align-items:center; gap:7px; }
.chat-action { border:1px solid #CFC8B4; background:#fff; color:#1F5D43; border-radius:999px;
  padding:6px 11px; cursor:pointer; font:600 12px/1 Inter,sans-serif; }
.chat-action:hover { border-color:#1F5D43; background:#F3F1E9; }
.chat-share-status { min-width:70px; color:#5b6b62; font-size:11px; text-align:right; }
.chat-msgs { flex:1; overflow-y:auto; padding:28px 24px 8px; display:flex; flex-direction:column; gap:16px; }
.chat-hero { margin:auto; text-align:center; max-width:540px; padding:24px 0; }
.chat-hero .spark { font-size:30px; }
.chat-hero h2 { font-size:26px; font-weight:600; color:#14231B; margin-top:6px; }
.chat-hero p { color:#5b6b62; margin-top:8px; font-size:15px; line-height:1.5; }
.cp-msg { font-size:14px; line-height:1.55; max-width:100%; }
.cp-msg.user { align-self:flex-end; background:#1F5D43; color:#fff; padding:9px 13px; border-radius:14px; max-width:82%; }
.cp-msg.assistant { align-self:flex-start; color:#14231B; max-width:92%; }
.cp-msg.assistant p { margin:.25em 0; } .cp-msg.assistant ul { margin:.25em 0 .25em 1.1em; }
.cp-who { font-size:10px; font-family:monospace; text-transform:uppercase; letter-spacing:1px; color:#7A867E; margin-bottom:3px; }
.cp-tool { font-size:12px; color:#7A867E; font-style:italic; }
.chat-cards { padding:8px 24px 0; display:flex; flex-wrap:wrap; gap:8px; justify-content:center; }
.chat-card { font-size:12.5px; color:#1F5D43; background:#fff; border:1px solid #E3DFD2; border-radius:12px;
  padding:8px 13px; cursor:pointer; transition:border-color .15s, background .15s; }
.chat-card:hover { border-color:#1F5D43; background:#F3F1E9; }
.chat-form { display:flex; gap:10px; padding:14px 24px 22px; }
.chat-attach { width:44px; height:44px; border:1px solid #CFC8B4; border-radius:999px;
  background:#fff; color:#1F5D43; font-size:20px; cursor:pointer; flex:0 0 auto; }
.offer-table { width:100%; border-collapse:collapse; margin:10px 0; background:#fff; border-radius:12px; overflow:hidden; }
.offer-table td { padding:8px 10px; border-bottom:1px solid #E3DFD2; }
.offer-table td:last-child { text-align:right; font-weight:600; }
.offer-action { display:inline-block; border:0; border-radius:999px; padding:9px 14px; margin:6px 6px 0 0;
  cursor:pointer; font-weight:600; background:#1F5D43; color:#fff; }
.offer-action.secondary { background:#fff; color:#1F5D43; border:1px solid #CFC8B4; }
.chat-input { flex:1; border:1px solid #CFC8B4; border-radius:14px; padding:12px 14px; font-size:14px;
  resize:none; outline:none; background:#fff; font-family:inherit; }
.chat-input:focus { border-color:#1F5D43; }
.chat-send { background:#1F5D43; color:#fff; border:0; border-radius:999px; padding:0 20px; font-weight:600; cursor:pointer; }
.chat-disabled { text-align:center; color:#7A867E; font-size:13px; padding:40px 24px; }

/* Slide-in right pane: invoice PDF viewer */
.pdf-pane { position:fixed; top:0; right:-480px; width:460px; height:100vh; z-index:200;
  background:#FFFFFF; border-left:1px solid #E3DFD2; box-shadow:-6px 0 24px rgba(0,0,0,.08);
  display:flex; flex-direction:column; transition:right .28s ease; }
.pdf-pane.open { right:0; }
.pdf-pane.wide { width:min(72vw, 1000px); }
.pdf-head { display:flex; align-items:center; justify-content:space-between; padding:10px 14px;
  border-bottom:1px solid #E3DFD2; }
.pdf-title { font-size:13px; font-weight:600; color:#14231B; }
.pdf-head button { background:none; border:0; cursor:pointer; color:#7A867E; font-size:16px; padding:2px 6px; }
.pdf-frame { flex:1; width:100%; border:0; }
.pdf-view-btn { font-size:11px; color:#1F5D43; border:1px solid #CFC8B4; border-radius:999px;
  padding:3px 10px; cursor:pointer; background:#fff; text-decoration:none; white-space:nowrap; }
.pdf-view-btn:hover { border-color:#1F5D43; background:#F3F1E9; }
"""

SHELL_JS = """
function cpAdd(role, html){ var m=document.getElementById('cp-msgs');
  var h=document.getElementById('chat-hero'); if(h) h.remove();
  var wrap=document.createElement('div'); wrap.className='cp-msg '+role;
  if(role==='assistant'){ var w=document.createElement('div'); w.className='cp-who'; w.textContent='Factorio AI'; wrap.appendChild(w);
    var body=document.createElement('div'); body.innerHTML=html; wrap.appendChild(body); m.appendChild(wrap); m.scrollTop=m.scrollHeight; return body; }
  wrap.innerHTML=html; m.appendChild(wrap); m.scrollTop=m.scrollHeight; return wrap; }
function cpMd(t){ try{ return window.marked ? marked.parse(t) : t.replace(/\\n/g,'<br>'); }catch(e){ return t; } }
function cpEsc(s){ var d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

/* ── Copy and immutable public share snapshots ────────────────────── */
function fcVisibleMessages(){ return Array.from(document.querySelectorAll('#cp-msgs .cp-msg')).map(function(el){
  var clone=el.cloneNode(true), who=clone.querySelector('.cp-who'); if(who) who.remove();
  return {role:el.classList.contains('user')?'user':'assistant',content:(clone.innerText||clone.textContent||'').trim()};
}).filter(function(x){return x.content;}); }
function fcChatText(messages){ return messages.map(function(x){
  return (x.role==='user'?'You':'Factorio AI')+': '+x.content;
}).join('\\n\\n'); }
async function fcClipboard(text){ if(navigator.clipboard&&window.isSecureContext){ await navigator.clipboard.writeText(text); return; }
  var area=document.createElement('textarea'); area.value=text; area.style.position='fixed'; area.style.opacity='0';
  document.body.appendChild(area); area.select(); document.execCommand('copy'); area.remove(); }
function fcShareStatus(text){ var el=document.getElementById('chat-share-status'); if(!el)return;
  el.textContent=text; clearTimeout(window._fcShareTimer); window._fcShareTimer=setTimeout(function(){el.textContent='';},2500); }
async function fcCopyChat(){ var messages=fcVisibleMessages(); if(!messages.length){fcShareStatus('Nothing to copy');return;}
  try{await fcClipboard(fcChatText(messages));fcShareStatus('Chat copied');}catch(e){fcShareStatus('Copy failed');} }
async function fcShareChat(){ var messages=fcVisibleMessages(); if(!messages.length){fcShareStatus('Nothing to share');return;}
  fcShareStatus('Creating link…');
  try{var first=messages.filter(function(x){return x.role==='user';})[0];
    var resp=await fetch('/app/chat/share',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title:first?first.content.slice(0,80):'Factorio AI chat',messages:messages})});
    var out=await resp.json(); if(!resp.ok)throw new Error(out.error||'Share failed');
    await fcClipboard(location.origin+out.url); fcShareStatus('Link copied');
  }catch(e){fcShareStatus('Share failed');} }

/* ── Chat history (per-browser, localStorage) ─────────────────────── */
function fcChats(){ try{ return JSON.parse(localStorage.getItem('fc_chats')||'[]'); }catch(e){ return []; } }
function fcSaveAll(c){ try{ localStorage.setItem('fc_chats', JSON.stringify(c.slice(0,40))); }catch(e){} }
function fcActive(){ return localStorage.getItem('fc_active')||''; }
function fcSetActive(id){ if(id) localStorage.setItem('fc_active', id); else localStorage.removeItem('fc_active'); }
function fcGet(id){ return fcChats().filter(function(c){return c.id===id;})[0]; }
function fcUpsert(chat){ var all=fcChats(); var i=all.map(function(c){return c.id;}).indexOf(chat.id);
  if(i>=0) all.splice(i,1); all.unshift(chat); fcSaveAll(all); }
function fcRenderHistory(){ var el=document.getElementById('chat-history'); if(!el) return;
  var chats=fcChats(), act=fcActive(); el.innerHTML='';
  chats.forEach(function(c){ var a=document.createElement('a'); a.href='#';
    a.className='nav-item nav-hist'+(c.id===act?' active':'');
    a.textContent=(c.title||'New chat').slice(0,34);
    a.onclick=function(){ fcSetActive(c.id);
      if(location.pathname==='/app'){ fcLoad(c.id); fcRenderHistory(); } else { location.href='/app'; }
      return false; };
    el.appendChild(a); }); }
function fcLoad(id){ var c=fcGet(id); var m=document.getElementById('cp-msgs'); if(!m) return;
  m.innerHTML=''; if(!c){ return; }
  (c.msgs||[]).forEach(function(x){ cpAdd(x.role, x.role==='assistant'?cpMd(x.content):cpEsc(x.content)); }); }
function fcNewChat(){ fcSetActive(''); if(location.pathname==='/app'){ location.reload(); } else { location.href='/app'; } }

var _cpBusy=false;
async function cpSend(ev){ if(ev&&ev.preventDefault) ev.preventDefault();
  if(_cpBusy) return false;
  var inp=document.getElementById('cp-input'); var msg=inp.value.trim(); if(!msg) return false;
  _cpBusy=true; inp.value=''; cpAdd('user', cpEsc(msg));
  var think=cpAdd('assistant','<span class=cp-tool>thinking…</span>'); var acc=''; var bubble=null;
  try{
    var resp=await fetch('/app/copilot/stream',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({message:msg})});
    var reader=resp.body.getReader(), dec=new TextDecoder(), buf='';
    while(true){ var r=await reader.read(); if(r.done) break; buf+=dec.decode(r.value,{stream:true});
      var i; while((i=buf.indexOf('\\n\\n'))!==-1){ var raw=buf.slice(0,i); buf=buf.slice(i+2);
        var type=null,data=''; raw.split('\\n').forEach(function(l){ if(l.indexOf('event: ')===0) type=l.slice(7).trim(); else if(l.indexOf('data: ')===0) data+=l.slice(6); });
        var p=data?JSON.parse(data):{};
        if(type==='token'){ if(acc===''){ think.parentNode.remove(); bubble=cpAdd('assistant',''); } acc+=p.text||''; bubble.innerHTML=cpMd(acc); }
        else if(type==='tool_start'){ think.innerHTML='<span class=cp-tool>checking '+(p.name||'data')+'…</span>'; }
        else if(type==='error'){ think.innerHTML='<span class=cp-tool>error: '+cpEsc(p.message||'')+'</span>'; }
      }
    }
    if(acc==='' && think) think.innerHTML='<span class=cp-tool>(no response)</span>';
  }catch(e){ if(think) think.innerHTML='<span class=cp-tool>connection error</span>'; }
  /* persist to history */
  try{ var id=fcActive(); var chat=id?fcGet(id):null;
    if(!chat){ id=''+Date.now(); chat={id:id, title:msg.slice(0,40), msgs:[]}; fcSetActive(id); }
    chat.msgs.push({role:'user',content:msg}); chat.msgs.push({role:'assistant',content:acc});
    if(!chat.title) chat.title=msg.slice(0,40); fcUpsert(chat); fcRenderHistory();
  }catch(e){}
  var m=document.getElementById('cp-msgs'); m.scrollTop=m.scrollHeight; _cpBusy=false; return false;
}
function cpAsk(q){ var i=document.getElementById('cp-input'); i.value=q; cpSend(); }
async function fcInvoiceFile(e){ var file=e.target.files[0]; if(!file) return;
  cpAdd('user','📎 '+cpEsc(file.name)); var thinking=cpAdd('assistant','<span class=cp-tool>Reading invoice and preparing your offer…</span>');
  var data=await new Promise(function(resolve,reject){var r=new FileReader();r.onload=function(){resolve(r.result)};r.onerror=reject;r.readAsDataURL(file);});
  try{ var resp=await fetch('/app/supplier/extract',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({file_data:data,filename:file.name,mime_type:file.type})});
    var out=await resp.json(); thinking.parentNode.remove();
    if(!resp.ok){cpAdd('assistant','<span class=cp-tool>'+cpEsc(out.error||'Extraction failed')+'</span>');return;}
    cpAdd('assistant',out.html);
  }catch(err){thinking.innerHTML='<span class=cp-tool>Upload failed. Please try again.</span>';}
  e.target.value='';
}
async function fcAcceptOffer(){ var r=await fetch('/app/supplier/accept',{method:'POST'}); var out=await r.json();
  if(!r.ok){cpAdd('assistant','<span class=cp-tool>'+cpEsc(out.error||'Could not create application')+'</span>');return;}
  cpAdd('assistant',out.html);
}
async function fcReviseOffer(){var amount=document.getElementById('offer-amount').value;
  var days=document.getElementById('offer-days').value;
  var r=await fetch('/app/supplier/change',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({amount:amount,days:days})});var out=await r.json();
  if(!r.ok){cpAdd('assistant','<span class=cp-tool>'+cpEsc(out.error||'Could not change terms')+'</span>');return;}
  cpAdd('user','Please revise the offer to '+amount+' for '+days+' days.');
  cpAdd('assistant',out.html);
}
function fcBankStatement(e){var f=e.target.files[0];if(f)cpAdd('assistant','Bank statement <b>'+cpEsc(f.name)+'</b> attached for optional affordability review.');e.target.value='';}
function fcConnectBank(){cpAdd('assistant','Open Banking connection is optional. In this demo the secure bank-authorisation hand-off is ready to be connected.');}
function wsToggleNav(){ document.getElementById('ws').classList.toggle('nav-open'); }

/* ── Invoice PDF right pane ─────────────────────────────────────────── */
function fcShowPdf(num, search){ var f=document.getElementById('fc-pdf-frame');
  var t=document.getElementById('fc-pdf-title'); if(t) t.textContent=num;
  var url='/pdfjs/viewer?file='+encodeURIComponent('/app/invoice-pdf/'+num)+'&t='+Date.now();
  if(search) url+='#search='+encodeURIComponent(search);
  f.src='about:blank'; setTimeout(function(){ f.src=url; }, 40);
  document.getElementById('fc-pdf-pane').classList.add('open'); return false; }
function fcHidePdf(){ document.getElementById('fc-pdf-pane').classList.remove('open','wide');
  document.getElementById('fc-pdf-frame').src='about:blank'; }
function fcWidePdf(){ document.getElementById('fc-pdf-pane').classList.toggle('wide'); }

document.addEventListener('DOMContentLoaded', function(){ fcRenderHistory();
  if(location.pathname==='/app'){ var a=fcActive(); if(a && fcGet(a)) fcLoad(a); } });
"""

_SUGGESTIONS = ["cp_chip1", "cp_chip2", "cp_chip3", "cp_chip4"]


def _left_nav(role: str, current_path: str, lang: str):
    active = _active_key(role, current_path)
    secs = []
    for section_key, items in _nav_for(role):
        links = [
            A(Span(NotStr(icon), cls="nav-ic"), Span(t(i18n_key, lang)),
              href=href, cls="nav-item active" if active == key else "nav-item")
            for key, i18n_key, icon, href in items
        ]
        block = [Div(t(section_key, lang), cls="nav-head"), *links]
        if section_key == "nav_sec_agents":
            block.append(A(Span("＋", cls="nav-ic"), Span(t("cp_new_chat", lang)),
                           href="#", onclick="fcNewChat();return false;", cls="nav-item nav-newchat"))
            block.append(Div(id="chat-history", cls="nav-history"))
        secs.append(Div(*block, cls="nav-sec"))
    return Div(*secs, cls="ws-left")


def _chat_center(lang: str, role: str = "investor"):
    if not copilot_available():
        return Div(Div("Factorio AI", cls="cp-who"),
                   P("Set XAI_API_KEY to enable the copilot.", cls="chat-disabled"),
                   cls="chat")
    supplier = role == "supplier"
    hero = Div(Span("✨", cls="spark"),
               H2("Upload an invoice to get a financing offer" if supplier else t("cp_hero_title", lang)),
               P("Attach a digital PDF or invoice image. Factorio AI will extract the details and show how much you can receive today."
                 if supplier else t("cp_hero_sub", lang)),
               id="chat-hero", cls="chat-hero")
    cards = ([Span("How invoice financing works", cls="chat-card",
                   onclick="cpAsk('How does invoice financing work?')")]
             if supplier else
             [Span(t(k, lang), cls="chat-card", onclick=f"cpAsk('{t(k, lang)}')") for k in _SUGGESTIONS])
    return Div(
        Div(Span("Factorio AI conversation", cls="chat-head-title"),
            Div(Span("", id="chat-share-status", cls="chat-share-status"),
                Button("Copy", type="button", cls="chat-action", title="Copy conversation",
                       onclick="fcCopyChat()"),
                Button("Share", type="button", cls="chat-action", title="Create public read-only link",
                       onclick="fcShareChat()"),
                cls="chat-actions"),
            cls="chat-head"),
        Div(hero, id="cp-msgs", cls="chat-msgs"),
        Form(Input(type="file", id="cp-invoice-file", accept=".pdf,.png,.jpg,.jpeg,.json,.txt",
                   style="display:none", onchange="fcInvoiceFile(event)") if supplier else None,
             Input(type="file", id="cp-bank-file", accept=".pdf,.csv",
                   style="display:none", onchange="fcBankStatement(event)") if supplier else None,
             Button("📎", cls="chat-attach", type="button", title="Upload invoice",
                    onclick="document.getElementById('cp-invoice-file').click()") if supplier else None,
             Textarea("", id="cp-input", cls="chat-input", rows="1",
                      placeholder=t("cp_placeholder", lang), autocomplete="off",
                      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();cpSend();}"),
             Button(t("cp_send", lang), cls="chat-send", type="submit"),
             cls="chat-form", onsubmit="return cpSend(event)"),
        Div(*cards, cls="chat-cards"),
        cls="chat")


def _head(title: str, lang: str):
    return [
        Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(f"{title} · {SITE_NAME}"),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"),
        Script(src="https://cdn.tailwindcss.com"), Script(NotStr(TAILWIND_CONFIG)),
        Script(src="https://unpkg.com/htmx.org@2.0.3"),
        Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
        Link(rel="stylesheet", href="/static/site.css"),
        Style(SHELL_CSS),
    ]


def _lang_pill(lang: str):
    opts = [A(Span(LANG_META[c]["flag"], cls="mr-2"), Span(LANG_META[c]["name"], cls="text-xs"),
              href=f"/set-lang?lang={c}",
              onclick=f"document.cookie='lang={c};path=/;max-age=31536000;samesite=lax';location.reload();return false;",
              cls="flex items-center gap-1 px-3 py-1.5 text-sm text-ink-muted hover:bg-bg-raised no-underline")
            for c in SUPPORTED_LANGS]
    return Div(
        Button(LANG_META.get(lang, LANG_META["en"])["flag"], type="button",
               onclick="this.nextElementSibling.classList.toggle('hidden')",
               cls="text-base px-1.5 py-1 rounded hover:bg-bg-raised cursor-pointer bg-transparent border-0"),
        Div(*opts, cls="hidden absolute right-0 top-full mt-1 bg-bg-elevated border border-line rounded-lg shadow-lg z-50 py-1 min-w-[150px] flex flex-col"),
        cls="relative")


def _topbar(lang: str, role: str, investor, investors):
    from app_routes._shared import _role_switcher, _investor_switcher
    right = _investor_switcher(investor, investors, lang) if role == "investor" else Span("", cls="hidden")
    return Div(
        Div(
            Button(NotStr("&#9776;"), onclick="wsToggleNav()", type="button",
                   cls="ws-burger", title="Menu"),
            A(Span(NotStr("&#9670;"), cls="text-accent mr-2"), Span(SITE_NAME, cls="font-medium tracking-tight text-ink"),
              href="/", cls="flex items-center text-base no-underline"),
            cls="flex items-center"),
        Div(A(t("nav_signin", lang), href="/login", cls="hidden sm:inline text-xs text-ink-muted hover:text-ink no-underline"),
            Span("/", cls="hidden sm:inline text-ink-dim text-xs"),
            A(t("nav_signout", lang), href="/logout", cls="hidden sm:inline text-xs text-ink-muted hover:text-ink no-underline mr-2"),
            _role_switcher(role, lang), right, _lang_pill(lang),
            cls="flex items-center gap-3"),
        cls="ws-top")


def _lang_of(lang: str) -> str:
    return {"en": "en", "uz": "uz", "ru": "ru", "es": "es", "fr": "fr"}.get(lang, "en")


def _pdf_pane():
    from fasthtml.common import Iframe
    return Div(
        Div(Span("Invoice", id="fc-pdf-title", cls="pdf-title"),
            Div(Button(NotStr("⤢"), onclick="fcWidePdf()", type="button", title="Widen"),
                Button(NotStr("✕"), onclick="fcHidePdf()", type="button", title="Close")),
            cls="pdf-head"),
        Iframe(id="fc-pdf-frame", src="about:blank", cls="pdf-frame"),
        id="fc-pdf-pane", cls="pdf-pane")


def app_shell(title: str, *content, current_path: str = "/app", lang: str = DEFAULT_LANG,
              investor=None, investors=None, role: str = "investor", subrole: str = "ops"):
    """Render a Tool page inside the Agents+Tools cockpit (content in the center)."""
    from app_routes._shared import list_investors
    investors = investors if investors is not None else list_investors()
    return Html(
        Head(*_head(title, lang)),
        Body(Div(_topbar(lang, role, investor, investors),
                 _left_nav(role, current_path, lang),
                 Div(*content, cls="ws-center"),
                 Div(cls="ws-backdrop", onclick="wsToggleNav()"),
                 cls="ws", id="ws"),
             _pdf_pane(),
             Script(NotStr(SHELL_JS)),
             cls="bg-bg text-ink font-sans antialiased"),
        lang=_lang_of(lang))


@rt("/app")
def app_home(req):
    """Agents view — the central Copilot chat (default landing)."""
    from app_routes._shared import current_role, list_investors, current_investor
    lang = get_lang(req)
    role = current_role(req)
    investors = list_investors()
    investor = current_investor(req, investors) if role == "investor" else None
    return Html(
        Head(*_head("Factorio AI", lang)),
        Body(Div(_topbar(lang, role, investor, investors),
                 _left_nav(role, "/app", lang),
                 Div(_chat_center(lang, role), cls="ws-center"),
                 Div(cls="ws-backdrop", onclick="wsToggleNav()"),
                 cls="ws", id="ws"),
             _pdf_pane(),
             Script(NotStr(SHELL_JS)),
             cls="bg-bg text-ink font-sans antialiased"),
        lang=_lang_of(lang))


@rt("/app/chat/share", methods=["POST"])
async def share_chat(req):
    """Persist a bounded, plain-text snapshot and return its public URL."""
    try:
        payload = await req.json()
    except Exception:
        return JSONResponse({"error": "Invalid request"}, status_code=400)
    raw_messages = payload.get("messages", [])
    if not isinstance(raw_messages, list) or not raw_messages or len(raw_messages) > 200:
        return JSONResponse({"error": "A chat with 1–200 messages is required"}, status_code=400)
    messages = []
    total = 0
    for item in raw_messages:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            return JSONResponse({"error": "Invalid message"}, status_code=400)
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        content = content[:20_000]
        total += len(content)
        messages.append({"role": item["role"], "content": content})
    if not messages or total > 100_000:
        return JSONResponse({"error": "Chat is empty or too large"}, status_code=400)
    title = str(payload.get("title") or "Factorio AI chat").strip()[:120]
    token = secrets.token_urlsafe(24)
    from db import execute
    execute(
        "INSERT INTO factorio.shared_chats (token, title, messages) VALUES (%s, %s, %s)",
        (token, title, json.dumps(messages)),
    )
    return JSONResponse({"url": f"/shared/chat/{token}"})


@rt("/shared/chat/{token}")
def shared_chat(req, token: str):
    """Public, read-only conversation snapshot addressed by an unguessable token."""
    from db import fetch_one
    row = fetch_one(
        "SELECT title, messages, created_at FROM factorio.shared_chats WHERE token=%s",
        (token,),
    )
    if not row:
        return Html(Head(Title("Shared chat not found")), Body(H2("Shared chat not found"))), 404
    try:
        messages = json.loads(row["messages"])
    except (TypeError, json.JSONDecodeError):
        messages = []
    bubbles = [
        Div(Div("You" if item["role"] == "user" else "Factorio AI", cls="shared-who"),
            P(item["content"], cls="shared-copy"),
            cls=f"shared-msg {item['role']}")
        for item in messages
    ]
    shared_css = """
body{margin:0;background:#F7F6F1;color:#14231B;font-family:Inter,system-ui,sans-serif}
.shared{max-width:800px;margin:0 auto;padding:32px 20px 60px}.shared-brand{color:#1F5D43;font-weight:700}
h1{font-size:24px;margin:18px 0 5px}.shared-date{color:#7A867E;font-size:12px;margin-bottom:30px}
.shared-msg{margin:15px 0;max-width:88%;font-size:14px;line-height:1.55}
.shared-msg.user{margin-left:auto;background:#1F5D43;color:white;border-radius:14px;padding:10px 14px}
.shared-who{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#7A867E;margin-bottom:4px}
.shared-msg.user .shared-who{color:#CFE5DA}.shared-copy{white-space:pre-wrap;margin:0}
"""
    return Html(
        Head(Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width, initial-scale=1"),
             Title(f"{row['title']} · Factorio"), Style(shared_css)),
        Body(Div(Div("◆ Factorio", cls="shared-brand"), H2(row["title"]),
                 P(f"Read-only conversation · {row['created_at']:%d %b %Y}", cls="shared-date"),
                 *bubbles, cls="shared")))


# ── Copilot streaming endpoint (hand-rolled SSE) ──────────────────────────

def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@rt("/app/copilot/stream")
async def copilot_stream(req):
    form = await req.form()
    msg = (form.get("message") or "").strip()
    from app_routes._shared import current_role
    role = current_role(req)

    async def gen():
        if not msg:
            yield _sse("done", {}); return
        if role == "supplier":
            from utils import ai
            from utils.prompts import load_prompt
            prompt = load_prompt("supplier_factorio_ai.md")
            reply = ai.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": msg},
            ], temperature=0.2, max_tokens=500)
            yield _sse("token", {"text": reply})
            yield _sse("done", {})
            return
        from utils.copilot import answer_stream
        got = False
        try:
            async for ev, data in answer_stream(msg):
                if ev == "token":
                    got = True; yield _sse("token", {"text": data})
                elif ev == "tool_start":
                    yield _sse("tool_start", data)
                elif ev == "error":
                    yield _sse("error", {"message": data})
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"message": str(e)})
        if not got:
            yield _sse("token", {"text": "(no response)"})
        yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
