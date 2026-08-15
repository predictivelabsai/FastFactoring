"""Admin Agents console (Phase 1) — the agent fleet, a supervisor chat that runs
them autonomously, an activity feed (from the audit log) and a global kill switch.
Admin-only.
"""

from __future__ import annotations

import json
import hmac

from fasthtml.common import (
    Div, P, Span, A, Button, Form, Textarea, Input, NotStr, H3, Style,
)
from starlette.responses import StreamingResponse, RedirectResponse

from app import rt
from utils.i18n import get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, current_role, current_subrole
from utils.access import context_for
from utils import agents as fleet

try:
    from db import fetch_all
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

_POD_COLOR = {"Orchestration": "#1F5D43", "Origination": "#5B8FB0", "Decisioning": "#C87F5B",
              "Servicing": "#C89B5B", "Oversight": "#7A9E88", "Growth": "#9B6FB0"}

_CSS = """
.ag-wrap { display:grid; grid-template-columns:1fr 320px; gap:20px; }
@media (max-width:980px){ .ag-wrap { grid-template-columns:1fr; } }
.ag-card { border:1px solid #E3DFD2; border-radius:14px; background:#fff; padding:13px 14px; cursor:pointer;
  transition:border-color .15s, box-shadow .15s; }
.ag-card:hover { border-color:#1F5D43; box-shadow:0 1px 6px rgba(31,93,67,.1); }
.ag-badge { font-size:9.5px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; padding:2px 7px; border-radius:999px; color:#fff; }
.ag-auto { font-size:9.5px; color:#1F5D43; border:1px solid #CFE5DA; background:#EFF6F1; border-radius:999px; padding:2px 7px; }
.ag-msgs { min-height:120px; max-height:340px; overflow-y:auto; display:flex; flex-direction:column; gap:12px; padding:6px 2px; }
.ag-msg { font-size:13.5px; line-height:1.5; }
.ag-msg.user { align-self:flex-end; background:#1F5D43; color:#fff; padding:8px 12px; border-radius:14px; max-width:85%; }
.ag-msg.assistant { align-self:flex-start; color:#14231B; max-width:92%; }
.ag-who { font-size:10px; font-family:monospace; text-transform:uppercase; letter-spacing:1px; color:#7A867E; margin-bottom:3px; }
.ag-tool { font-size:12px; color:#7A867E; font-style:italic; }
.ag-feed-row { padding:8px 0; border-bottom:1px solid #EFEDE4; }
"""

_JS = """
var agSlug='supervisor';
function agPick(slug, name, ex){ agSlug=slug;
  var t=document.getElementById('ag-target'); if(t) t.textContent=name;
  var i=document.getElementById('ag-input'); if(i){ i.value=ex||''; i.focus(); } }
function agAdd(role, html){ var m=document.getElementById('ag-msgs');
  var w=document.createElement('div'); w.className='ag-msg '+role;
  if(role==='assistant'){ var h=document.createElement('div'); h.className='ag-who'; h.textContent=document.getElementById('ag-target').textContent||'Agent'; w.appendChild(h);
    var b=document.createElement('div'); b.innerHTML=html; w.appendChild(b); m.appendChild(w); m.scrollTop=m.scrollHeight; return b; }
  w.innerHTML=html; m.appendChild(w); m.scrollTop=m.scrollHeight; return w; }
function agMd(t){ try{ return window.marked?marked.parse(t):t.replace(/\\n/g,'<br>'); }catch(e){ return t; } }
function agEsc(s){ var d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
var _agBusy=false;
async function agSend(ev){ if(ev&&ev.preventDefault) ev.preventDefault(); if(_agBusy) return false;
  var i=document.getElementById('ag-input'); var msg=i.value.trim(); if(!msg) return false;
  _agBusy=true; i.value=''; agAdd('user', agEsc(msg));
  var think=agAdd('assistant','<span class=ag-tool>working…</span>'); var acc=''; var bub=null;
  try{ var resp=await fetch('/app/admin/agents/stream',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({slug:agSlug,message:msg})});
    var rd=resp.body.getReader(), dec=new TextDecoder(), buf='';
    while(true){ var r=await rd.read(); if(r.done) break; buf+=dec.decode(r.value,{stream:true});
      var idx; while((idx=buf.indexOf('\\n\\n'))!==-1){ var raw=buf.slice(0,idx); buf=buf.slice(idx+2);
        var type=null,data=''; raw.split('\\n').forEach(function(l){ if(l.indexOf('event: ')===0)type=l.slice(7).trim(); else if(l.indexOf('data: ')===0)data+=l.slice(6); });
        var p=data?JSON.parse(data):{};
        if(type==='token'){ if(acc===''){ think.parentNode.remove(); bub=agAdd('assistant',''); } acc+=p.text||''; bub.innerHTML=agMd(acc); }
        else if(type==='tool_start'){ think.innerHTML='<span class=ag-tool>running '+(p.name||'tool')+'…</span>'; }
        else if(type==='error'){ think.innerHTML='<span class=ag-tool>error: '+agEsc(p.message||'')+'</span>'; }
      } }
    if(acc==='' && think) think.innerHTML='<span class=ag-tool>(no response)</span>';
  }catch(e){ if(think) think.innerHTML='<span class=ag-tool>connection error</span>'; }
  _agBusy=false; return false; }
"""


def _guard(req):
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    return None


def _feed():
    if not _HAS_DB:
        return []
    try:
        return fetch_all("SELECT actor, action, entity, detail, created_at FROM factorio.audit_log "
                         "WHERE actor LIKE %(p)s ORDER BY created_at DESC LIMIT 15", {"p": "agent:%"})
    except Exception:
        return []


@rt("/app/admin/agents")
def agents_console(req):
    g = _guard(req)
    if g:
        return g
    lang = get_lang(req)
    on = fleet.agents_enabled()

    # fleet cards grouped by pod
    pods = []
    for pod in fleet.PODS:
        cards = []
        for slug, name, p, icon, auto, desc, _tk, ex in fleet.AGENTS:
            if p != pod:
                continue
            ex_js = ex.replace("'", "\\'")
            cards.append(Div(
                Div(Span(NotStr(icon), cls="text-lg"),
                    Span(pod, cls="ag-badge", style=f"background:{_POD_COLOR.get(pod,'#7A867E')}"),
                    cls="flex items-center justify-between mb-1"),
                H3(name, cls="text-ink text-sm font-semibold"),
                P(desc, cls="text-ink-muted text-xs mt-0.5"),
                Div(Span(auto, cls="ag-auto"),
                    A("Edit skills", href=f"/app/admin/agents/skills/{slug}",
                      onclick="event.stopPropagation()",
                      cls="text-[11px] text-accent hover:underline"),
                    cls="flex items-center justify-between mt-2"),
                cls="ag-card", onclick=f"agPick('{slug}','{name}','{ex_js}')"))
        if cards:
            pods.append(Div(P(pod, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-2 mt-4"),
                            Div(*cards, cls="grid sm:grid-cols-2 lg:grid-cols-3 gap-3")))

    chat = Div(
        Div(Span("Run the fleet →", cls="text-sm font-medium text-ink"),
            Span("supervisor", id="ag-target", cls="text-xs text-accent font-mono ml-2"),
            cls="flex items-center justify-between mb-2"),
        Div(Div("Ask the supervisor or pick an agent, then give an instruction. Agents act autonomously.",
                cls="ag-tool"), id="ag-msgs", cls="ag-msgs"),
        Form(Textarea("", id="ag-input", rows="2", placeholder="e.g. Start dunning on invoice INV-20260010",
                      cls="flex-1 border border-line-bright rounded-xl px-3 py-2 text-sm resize-none outline-none",
                      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();agSend();}"),
             Button("Run", type="submit", cls="px-5 rounded-full bg-accent text-bg font-medium"),
             cls="flex gap-2 mt-2", onsubmit="return agSend(event)"),
        cls="p-5 rounded-2xl bg-bg-elevated border border-line")

    feed_rows = [Div(
        Div(Span(f["actor"], cls="text-xs font-mono text-accent"),
            Span(str(f["created_at"]).split(".")[0][5:16], cls="text-[10px] text-ink-dim"),
            cls="flex items-center justify-between"),
        P(f"{f['action']} · {f['entity']}", cls="text-xs text-ink mt-0.5"),
        P(f["detail"], cls="text-[11px] text-ink-muted") if f["detail"] else None,
        cls="ag-feed-row") for f in _feed()]
    feed = Div(
        P("Activity feed", cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-2"),
        Div(*feed_rows, cls="") if feed_rows else P("No agent actions yet.", cls="text-ink-muted text-xs"),
        cls="p-5 rounded-2xl bg-bg-elevated border border-line")

    kill = Form(
        Input(type="hidden", name="csrf", value=context_for(req).csrf_token),
        Button(("⏻ Fleet: ON" if on else "⏻ Fleet: PAUSED"), type="submit",
               cls="text-xs font-medium px-4 py-2 rounded-full " +
                   ("bg-accent text-bg" if on else "bg-red-100 text-red-700 border border-red-200")),
        method="post", action="/app/admin/agents/toggle",
    )

    return app_page(
        "Agent fleet",
        Section_(Eyebrow("Back office · Agents"),
                 Heading(1, "Agent fleet", cls="mt-4"),
                 P("An autonomous team of back-office agents, coordinated by a supervisor. "
                   "Every action is written to the audit log.", cls="mt-3 text-ink-muted max-w-3xl"),
                 cls="border-t border-line"),
        Section_(
            Style(_CSS),
            Div(Span(f"{len(fleet.AGENTS)} agents across {len(fleet.PODS)} pods", cls="text-sm text-ink-muted"),
                kill, cls="flex items-center justify-between mb-4"),
            Div(Div(chat, *pods), feed, cls="ag-wrap"),
            NotStr(f"<script>{_JS}</script>"),
            cls="border-t border-line"),
        current_path="/app/admin/agents", lang=lang, role="admin", subrole=current_subrole(req))


def _prompt_versions(slug: str, limit: int = 12):
    if not _HAS_DB:
        return []
    try:
        return fetch_all(
            """SELECT id, changed_by, created_at, left(content, 180) preview
               FROM factorio.agent_prompt_versions
               WHERE agent_slug=%s ORDER BY id DESC LIMIT %s""",
            (slug, limit),
        )
    except Exception:
        return []


@rt("/app/admin/agents/skills")
def agent_skills_home(req):
    g = _guard(req)
    if g:
        return g
    cards = []
    for slug, name, pod, icon, autonomy, desc, tool_keys, _example in fleet.AGENTS:
        versions = _prompt_versions(slug, 1)
        cards.append(A(
            Div(Span(NotStr(icon), cls="text-xl"),
                Div(H3(name, cls="text-sm font-semibold"),
                    P(desc, cls="text-xs text-ink-muted mt-1"),
                    P(f"{pod} · {autonomy} · {len(tool_keys)} tool scope(s)",
                      cls="text-[10px] text-ink-dim mt-2"),
                    cls="flex-1"),
                Span("Edited" if versions else "Default",
                     cls="text-[10px] rounded-full px-2 py-1 bg-bg-raised text-ink-muted"),
                cls="flex gap-4 items-start"),
            href=f"/app/admin/agents/skills/{slug}",
            cls="block p-5 rounded-2xl bg-bg-elevated border border-line hover:border-accent"))
    return app_page(
        "Agent skills",
        Section_(Eyebrow("Automation · Governance"),
                 Heading(1, "Agent skills editor", cls="mt-4"),
                 P("View or edit the live instructions used by every fleet specialist. "
                   "Database-backed versions survive deployments and can be reverted.",
                   cls="mt-3 text-ink-muted max-w-3xl"),
                 cls="border-t border-line"),
        Section_(Div(*cards, cls="grid md:grid-cols-2 gap-4"), cls="border-t border-line"),
        current_path="/app/admin/agents/skills", lang=get_lang(req),
        role="admin", subrole=current_subrole(req))


@rt("/app/admin/agents/skills/{slug}", methods=["GET", "POST"])
async def agent_skill_edit(req, slug: str):
    g = _guard(req)
    if g:
        return g
    spec = fleet.agent_by_slug(slug)
    if not spec:
        return RedirectResponse("/app/admin/agents/skills", status_code=303)
    _slug, name, pod, _icon, autonomy, desc, tool_keys, _example = spec
    message = ""
    if req.method == "POST":
        form = await req.form()
        content = str(form.get("content") or "").strip()
        if len(content) < 40:
            message = "Instructions must be at least 40 characters."
        elif len(content) > 50_000:
            message = "Instructions must be 50,000 characters or fewer."
        else:
            from db import execute
            actor = str((getattr(req, "session", {}) or {}).get("uid") or "admin")
            execute(
                """INSERT INTO factorio.agent_prompt_versions
                   (agent_slug, content, changed_by) VALUES (%s, %s, %s)""",
                (slug, content, actor),
            )
            from app_routes.admin import log_action
            log_action("admin", actor, "agent.prompt.update", slug, f"{len(content)} characters")
            message = "Saved. New agent runs will use these instructions."
    from utils.prompts import load_agent_prompt
    content = load_agent_prompt(slug, name, desc)
    versions = _prompt_versions(slug)
    history = [
        Div(
            Div(Span(f"Version #{v['id']}", cls="font-mono text-xs text-accent"),
                Span(str(v["created_at"]).split(".")[0], cls="text-[10px] text-ink-dim"),
                cls="flex justify-between"),
            P(v["preview"], cls="text-xs text-ink-muted mt-2 whitespace-pre-wrap"),
            Form(Input(type="hidden", name="version_id", value=str(v["id"])),
                 Button("Revert to this version", type="submit",
                        cls="mt-2 text-xs text-accent hover:underline"),
                 method="post", action=f"/app/admin/agents/skills/{slug}/revert"),
            cls="p-4 border border-line rounded-xl bg-bg-elevated")
        for v in versions
    ]
    return app_page(
        f"Edit {name}",
        Section_(Eyebrow(f"{pod} · {autonomy}"),
                 Heading(1, name, cls="mt-4"),
                 P(desc, cls="mt-3 text-ink-muted max-w-3xl"),
                 P("Tools: " + ", ".join(tool_keys), cls="mt-2 text-xs font-mono text-ink-dim"),
                 cls="border-t border-line"),
        Section_(
            P(message, cls="mb-4 text-green-700") if message else None,
            Form(Textarea(content, name="content", rows="28", spellcheck="true",
                          cls="w-full min-h-[520px] p-4 font-mono text-sm border border-line-bright "
                              "rounded-xl bg-bg-elevated focus:outline-none focus:border-accent"),
                 Div(Button("Save instructions", type="submit",
                            cls="px-5 py-2.5 rounded-full bg-accent text-bg font-medium"),
                     A("Back to all agents", href="/app/admin/agents/skills",
                       cls="text-sm text-ink-muted"),
                     cls="flex items-center gap-4 mt-4"),
                 method="post", action=f"/app/admin/agents/skills/{slug}"),
            H3("Version history", cls="text-lg font-semibold mt-10 mb-4"),
            Div(*history, cls="grid gap-3") if history else
            P("No edited versions yet; this agent is using its checked-in default.",
              cls="text-sm text-ink-muted"),
            cls="border-t border-line"),
        current_path="/app/admin/agents/skills", lang=get_lang(req),
        role="admin", subrole=current_subrole(req))


@rt("/app/admin/agents/skills/{slug}/revert", methods=["POST"])
async def agent_skill_revert(req, slug: str):
    g = _guard(req)
    if g:
        return g
    if not fleet.agent_by_slug(slug):
        return RedirectResponse("/app/admin/agents/skills", status_code=303)
    form = await req.form()
    try:
        version_id = int(form.get("version_id") or 0)
    except (TypeError, ValueError):
        version_id = 0
    from db import fetch_one, execute
    version = fetch_one(
        """SELECT content FROM factorio.agent_prompt_versions
           WHERE id=%s AND agent_slug=%s""", (version_id, slug))
    if version:
        actor = str((getattr(req, "session", {}) or {}).get("uid") or "admin")
        execute(
            """INSERT INTO factorio.agent_prompt_versions
               (agent_slug, content, changed_by) VALUES (%s, %s, %s)""",
            (slug, version["content"], f"{actor}:revert:{version_id}"),
        )
        from app_routes.admin import log_action
        log_action("admin", actor, "agent.prompt.revert", slug, f"from version {version_id}")
    return RedirectResponse(f"/app/admin/agents/skills/{slug}", status_code=303)


@rt("/app/admin/agents/toggle", methods=["POST"])
def agents_toggle(req, csrf: str = ""):
    g = _guard(req)
    if g:
        return g
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return RedirectResponse("/app", status_code=303)
    fleet.set_agents_enabled(not fleet.agents_enabled())
    return RedirectResponse("/app/admin/agents", status_code=303)


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@rt("/app/admin/agents/stream", methods=["POST"])
async def agents_stream(req):
    if current_role(req) != "admin":
        return StreamingResponse(iter([_sse("token", "Admin only.")]), media_type="text/event-stream")
    form = await req.form()
    slug = (form.get("slug") or "supervisor").strip()
    msg = (form.get("message") or "").strip()

    async def gen():
        if not msg:
            yield _sse("done", {}); return
        got = False
        try:
            async for ev, data in fleet.run_agent_stream(slug, msg):
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
