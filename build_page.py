#!/usr/bin/env python3
"""Build the static AMECA speech-enhancement showcase page.

DESIGN NOTE (2026-09, editorial rebuild; replaces the Bulma "Nerfies" clone)
 1. Reference points: distill.pub article pages, Apple ML Research index, and the
    plain-rule listings both use: off-white paper, near-black text, hairline rules,
    no cards, no shadows, no hero banner. We copy that restraint, not their layout.
 2. Palette: paper #FAF9F7, panel #FFFFFF, ink #17161A, muted ink #6E6A64,
    rule #E4E0D9. Gantt "hearing" is one muted grey #D6D1C9; each strategy owns one
    accent used for its label, bar and chips: default #6B6660 (graphite),
    situated quality #1D5FA8 (blue), situated efficiency #B4531F (terracotta);
    the "repeat" segment is that accent at 24% on white (#D2D0CE/#C4D6E9/#EDD2C1).
 3. Type: one sans (system UI stack) + one mono (ui-monospace/SF Mono) for every
    number, so digits are tabular and nothing re-flows when values change length.
    Scale 11.5 / 13 / 15 / 17 / 22 / 34 px, line-height 1.55 body, 1.25 headings.
 4. Spacing scale 4 / 8 / 12 / 20 / 32 / 56 px; content measure 760 px, video group
    720 px = 3 x 224 px columns + 2 x 24 px gutters (fixed px, so the three columns
    are provably identical and evenly spaced; videos are locked to 2:3).
 5. Structure: sticky backbone tab bar (one backbone visible), utterance rows, three
    arms racing on one clock, one shared Gantt axis with a single playhead.
 6. No framework, no build step, no external asset: stdlib Python out, static HTML in.

    python3 build_page.py
    python3 build_page.py --manifest robot/manifest_stub.json -o preview.html
"""

import argparse
import html
import json
import os
import re
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))

BACKBONE_ORDER = ["sb", "sgmse", "flowse", "storm"]
BACKBONE_NAMES = {"sb": "SB", "sgmse": "SGMSE+", "flowse": "FlowSE", "storm": "StoRM"}
STRATEGY_ORDER = ["default", "quality", "efficiency"]


def e(x):
    return html.escape("" if x is None else str(x), quote=True)


def num(x, nd=2):
    try:
        return ("%." + str(nd) + "f") % float(x)
    except (TypeError, ValueError):
        return ""


def fnum(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def chip(text, cls=""):
    return '<span class="chip%s">%s</span>' % ((" " + cls) if cls else "", text)


# --------------------------------------------------------------------------- arms


def arm_labels(entry, backbone_name):
    """Headline + sub-label. The default arm is headlined with the BACKBONE name."""
    strategy = entry.get("strategy", "default")
    nfe = entry.get("nfe")
    nfe_txt = ("NFE %s" % e(nfe)) if nfe is not None else ""
    if strategy == "default":
        sub = "backbone default" + (", " + nfe_txt if nfe_txt else "")
        return e(backbone_name), sub
    if strategy == "quality":
        return "situated &middot; quality", ("situated inference" + (", " + nfe_txt if nfe_txt else ""))
    return "situated &middot; efficiency", ("situated inference" + (", " + nfe_txt if nfe_txt else ""))


def audio_btn(src, label, cls=""):
    if not src:
        return ""
    return '<button type="button" class="ab%s" data-src="%s"><i class="abi"></i>%s</button>' % (
        (" " + cls) if cls else "",
        e(src),
        label,
    )


def arm_html(entry, backbone_name, idx, default_compute):
    strategy = entry.get("strategy", "default")
    head, sub = arm_labels(entry, backbone_name)

    chips = []
    nfe = entry.get("nfe")
    if nfe is not None:
        chips.append(chip('NFE&nbsp;<b class="n">%s</b>' % e(nfe)))
    cmp_s = entry.get("compute")
    if cmp_s is not None:
        chips.append(chip('<b class="n">%s</b>&nbsp;s' % num(cmp_s)))
    if strategy != "default" and cmp_s and default_compute:
        ratio = float(default_compute) / float(cmp_s)
        if ratio >= 1.0:
            chips.append(chip('<b class="n">%s&times;</b>&nbsp;faster' % num(ratio, 1), "hi"))
        else:
            chips.append(chip('<b class="n">%s&times;</b>&nbsp;slower' % num(1.0 / ratio, 1), "hi"))
    if entry.get("same_as_quality") and strategy == "efficiency":
        chips.append(chip("= quality cfg", "eq"))
    pesq = entry.get("pesq")
    if pesq is not None:
        # hard break: configuration chips on line 1, PESQ on line 2 for every arm,
        # so the three columns keep identical chip-block geometry
        chips.append('<i class="brk"></i>')
        chips.append(chip('PESQ&nbsp;<b class="n">%s</b>' % num(pesq)))

    cfg = entry.get("cfg")
    title_attr = ' title="%s"' % e(cfg) if cfg else ""

    frame = (
        '<div class="frame{mid}" data-arm="{idx}">'
        '<video class="rv" playsinline preload="none" muted poster="{poster}" src="{video}" '
        'data-clip="{clip}"></video>'
        '<span class="spk" aria-hidden="true">&#128266;</span>'
        "{overlay}"
        "</div>"
    ).format(
        mid=" mid" if idx == 1 else "",
        idx=idx,
        poster=e(entry.get("poster", "")),
        video=e(entry.get("video", "")),
        clip=num(entry.get("clip"), 3),
        overlay=(
            '<button type="button" class="bigplay" aria-label="play all three arms">'
            '<svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">'
            '<path class="pi" d="M8 5.5v13l11-6.5z"></path>'
            '<path class="pa" d="M8.5 5.5h3.4v13H8.5zM14.1 5.5h3.4v13h-3.4z"></path></svg>'
            "</button>"
        )
        if idx == 1
        else "",
    )

    meta = (
        '<div class="cell" data-arm="{idx}">'
        '<div class="lab"{title_attr}><span class="lname">{head}</span>'
        '<span class="lsub">{sub}</span></div>'
        '<div class="chips">{chips}</div>'
        '<div class="auds">{heard}{enh}</div>'
        "</div>"
    ).format(
        idx=idx,
        title_attr=title_attr,
        head=head,
        sub=sub,
        chips="".join(chips),
        heard=audio_btn(entry.get("heard"), "heard"),
        enh=audio_btn(entry.get("enh"), "enhanced"),
    )
    return frame, meta


# --------------------------------------------------------------------------- gantt


def gantt_row_html(entry, backbone_name, axis, idx):
    clip = fnum(entry.get("clip"))
    se = fnum(entry.get("t_speech_end"))
    rp = fnum(entry.get("t_reply"))
    axis = axis or clip or 1.0
    inf = max(rp - se, 0.0)
    rep = max(clip - rp, 0.0)
    infer_s = entry.get("compute")
    if infer_s is None:
        infer_s = inf
    end_frac = min(rp / axis, 1.0)

    strategy = entry.get("strategy", "default")
    if strategy == "default":
        gl = e(backbone_name)
    elif strategy == "quality":
        gl = "quality"
    else:
        gl = "efficiency"

    if end_frac > 0.76:
        npos = 'right:%.3f%%;text-align:right;padding-right:6px' % (100.0 * (1.0 - end_frac))
    else:
        npos = 'left:%.3f%%;padding-left:6px' % (100.0 * end_frac)

    return (
        '<div class="grow" data-arm="{idx}">'
        '<span class="glab">{gl}</span>'
        '<span class="gbar">'
        '<span class="gs gh" style="width:{wh:.3f}%"></span>'
        '<span class="gs gi" style="width:{wi:.3f}%"></span>'
        '<span class="gs gr" style="width:{wr:.3f}%"></span>'
        '<span class="gnum" style="{npos}">{infs}&nbsp;s</span>'
        "</span></div>"
    ).format(
        idx=idx,
        gl=gl,
        wh=100.0 * se / axis,
        wi=100.0 * inf / axis,
        wr=100.0 * rep / axis,
        npos=npos,
        infs=num(infer_s),
    )


# --------------------------------------------------------------------------- rows


def row_html(utt, entries, backbone_name, rid):
    order = {s: i for i, s in enumerate(STRATEGY_ORDER)}
    arms = sorted(entries, key=lambda x: order.get(x.get("strategy"), 9))
    axis = max([fnum(a.get("clip")) for a in arms] + [0.001])
    default_compute = None
    for a in arms:
        if a.get("strategy") == "default":
            default_compute = a.get("compute")

    frames, metas, grows = [], [], []
    for i, a in enumerate(arms):
        f, m = arm_html(a, backbone_name, i, default_compute)
        frames.append(f)
        metas.append(m)
        grows.append(gantt_row_html(a, backbone_name, axis, i))

    first = arms[0]
    raw = (first.get("transcript", "") or "").strip()
    if raw.isupper():
        raw = raw.capitalize()
        raw = re.sub(r"\bi\b", "I", raw)
    transcript = e(raw)
    snr = first.get("snr_db")
    snr_html = chip('SNR&nbsp;<b class="n">%s</b>&nbsp;dB' % num(snr, 1)) if snr is not None else ""
    noisy = audio_btn(first.get("noisy"), "noisy input", "wide")

    audible = len(arms) - 1  # situated efficiency is audible by default

    return (
        '<article class="row" data-axis="{axis}" data-audible="{aud}" id="{rid}">'
        '<header class="rhead"><h3 class="utt">{transcript}</h3>'
        '<div class="rmeta">{snr}{noisy}</div></header>'
        '<div class="vidgrid">{frames}</div>'
        '<div class="metagrid">{metas}</div>'
        '<div class="transport">'
        '<button type="button" class="tbtn play" aria-label="play or pause the row">'
        '<span class="pl">Play all three</span><span class="pls">Play</span>'
        '<span class="pp">Pause</span></button>'
        '<button type="button" class="tbtn restart" aria-label="restart the row">Restart</button>'
        '<input class="scrub" type="range" min="0" max="{axis}" step="0.01" value="0" '
        'aria-label="scrub the row">'
        '<span class="clock"><b class="now">0.00</b> / {axmax} s</span>'
        "</div>"
        '<div class="gantt">{grows}'
        '<div class="phwrap"><i class="playhead"></i></div></div>'
        '<div class="axis"><span>0 s</span><span class="akey">'
        '<i class="sw kh"></i>hearing<i class="sw ki"></i>inference<i class="sw kr"></i>repeat'
        "</span><span>{axmax} s</span></div>"
        "</article>"
    ).format(
        axis=num(axis, 3),
        aud=audible,
        rid=rid,
        transcript=transcript,
        snr=snr_html,
        noisy=noisy,
        frames="".join(frames),
        metas="".join(metas),
        axmax=num(axis),
        grows="".join(grows),
    )


def backbone_html(key, name, entries, first):
    rows = OrderedDict()
    for x in entries:
        rows.setdefault(x.get("utt"), []).append(x)
    body = "".join(
        row_html(u, v, name, "%s-%d" % (e(key), i + 1)) for i, (u, v) in enumerate(rows.items())
    )
    return (
        '<section class="bb" id="bb-{key}" data-bb="{key}"{hidden}>'
        '<p class="bbnote">{name} &mdash; {n} utterances, three arms each: '
        "backbone default, situated quality, situated efficiency.</p>"
        "{body}</section>"
    ).format(key=e(key), hidden="" if first else " hidden", name=e(name), n=len(rows), body=body)


# --------------------------------------------------------------------------- assets

CSS = """
:root{
 --paper:#FAF9F7; --panel:#FFFFFF; --ink:#17161A; --ink2:#6E6A64; --ink3:#918C85;
 --rule:#E4E0D9; --hear:#D6D1C9;
 --s1:4px; --s2:8px; --s3:12px; --s4:20px; --s5:32px; --s6:56px;
 --col:224px; --gap:24px; --grp:720px; --measure:760px;
 --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
 --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
 --a0:#6B6660; --a1:#1D5FA8; --a2:#B4531F;
 --r0:#D2D0CE; --r1:#C4D6E9; --r2:#EDD2C1;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--sans);
 font-feature-settings:"kern" 1;-webkit-font-smoothing:antialiased}
.n,.mono,.clock,.chip,.gnum,.scrub{font-variant-numeric:tabular-nums}
.wrap{max-width:var(--measure);margin:0 auto;padding:0 var(--s4)}
a{color:var(--ink);text-underline-offset:2px}

/* ---------- header ---------- */
header.top{padding:var(--s6) 0 var(--s5)}
h1{font-size:34px;line-height:1.2;font-weight:600;letter-spacing:-.015em;margin:0 0 var(--s3)}
.byline{font-size:13px;color:var(--ink2);margin:0 0 var(--s5);
 display:flex;gap:var(--s3);flex-wrap:wrap;align-items:baseline}
.byline .dot{color:var(--ink3)}
.links{display:flex;gap:var(--s3);flex-wrap:wrap;margin-top:var(--s2)}
.links a{font-size:13px;border:1px solid var(--rule);border-radius:999px;
 padding:3px 12px;text-decoration:none;background:var(--panel)}
.links a:hover{border-color:var(--ink3)}
.kicker{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);
 margin:0 0 var(--s2);font-weight:600}
.lead{font-size:15.5px;max-width:64ch;margin:0 0 var(--s4)}
.note{font-size:14px;color:var(--ink2);max-width:66ch;margin:0 0 var(--s3)}
hr.rule{border:0;border-top:1px solid var(--rule);margin:var(--s5) 0}

/* ---------- sticky tabs ---------- */
.tabbar{position:sticky;top:0;z-index:30;background:var(--paper);
 border-bottom:1px solid var(--rule)}
.tabbar .in{max-width:var(--measure);margin:0 auto;padding:0 var(--s4);
 display:flex;gap:var(--s4);align-items:center;height:46px;overflow-x:auto}
.tab{appearance:none;background:none;border:0;padding:0;height:46px;cursor:pointer;
 font:600 13px/46px var(--sans);color:var(--ink2);white-space:nowrap;
 border-bottom:2px solid transparent;letter-spacing:.02em}
.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--ink)}
.tab:hover{color:var(--ink)}
.bbnote{font-size:13px;color:var(--ink2);margin:var(--s5) 0 var(--s4)}

/* ---------- row ---------- */
.row{border-top:1px solid var(--rule);padding:var(--s5) 0 var(--s5)}
.rhead{max-width:var(--grp);margin:0 auto var(--s4);display:flex;gap:var(--s3);
 align-items:baseline;justify-content:space-between;flex-wrap:wrap}
.utt{font-size:17px;line-height:1.3;font-weight:500;margin:0;max-width:52ch;
 letter-spacing:-.005em}
.rmeta{display:flex;gap:var(--s2);align-items:center}

.vidgrid,.metagrid{display:grid;grid-template-columns:repeat(3,var(--col));
 gap:var(--gap);justify-content:center;width:100%}
.frame{position:relative;aspect-ratio:2/3;background:#141414;overflow:hidden;
 border:1px solid var(--rule);cursor:pointer}
.frame video{display:block;width:100%;height:100%;object-fit:cover}
.frame video::-webkit-media-controls{display:none!important}
.spk{position:absolute;top:6px;right:6px;font-size:12px;line-height:1;padding:4px 5px;
 border-radius:3px;background:rgba(0,0,0,.55);opacity:0;transition:opacity .15s}
.row .frame.audible .spk{opacity:1}
.row .frame.audible{outline:2px solid var(--ink);outline-offset:-2px}
.bigplay{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
 width:62px;height:62px;border-radius:50%;border:1px solid rgba(255,255,255,.7);
 background:rgba(20,20,20,.55);color:#fff;cursor:pointer;display:grid;place-items:center;
 padding:0;backdrop-filter:blur(2px);transition:opacity .18s,transform .18s}
.bigplay svg{fill:#fff;transform:translateX(1px)}
.bigplay .pa{display:none}
.row.playing .bigplay{opacity:0}
.row.playing .frame:hover .bigplay{opacity:1}
.row.playing .bigplay .pi{display:none}
.row.playing .bigplay .pa{display:block;transform:translateX(-1px)}
.bigplay:hover{transform:translate(-50%,-50%) scale(1.05)}

.metagrid{margin-top:var(--s3)}
.cell{min-width:0}
.lab{display:block;padding-top:var(--s1);border-top:2px solid var(--a0);min-height:44px}
.cell[data-arm="1"] .lab{border-top-color:var(--a1)}
.cell[data-arm="2"] .lab{border-top-color:var(--a2)}
.lname{display:block;font-size:13.5px;font-weight:600;letter-spacing:.01em;color:var(--a0)}
.cell[data-arm="1"] .lname{color:var(--a1)}
.cell[data-arm="2"] .lname{color:var(--a2)}
.lsub{display:block;font-size:11.5px;color:var(--ink3);margin-top:1px}
.chips{display:flex;flex-wrap:wrap;gap:var(--s1);min-height:46px;
 align-content:flex-start;margin-top:var(--s2)}
.brk{flex:0 0 100%;height:0;margin:0}
.chip{font:11.5px/1.5 var(--mono);color:var(--ink2);border:1px solid var(--rule);
 background:var(--panel);border-radius:2px;padding:1px 6px;white-space:nowrap}
.chip .n{color:var(--ink);font-weight:600}
.chip.hi{border-color:var(--a0);color:var(--a0)}
.cell[data-arm="1"] .chip.hi{border-color:var(--a1);color:var(--a1)}
.cell[data-arm="2"] .chip.hi{border-color:var(--a2);color:var(--a2)}
.chip.eq{border-style:dashed}
.auds{display:flex;gap:var(--s1);flex-wrap:wrap;min-height:24px}
.ab{appearance:none;cursor:pointer;font:11.5px/1.5 var(--sans);color:var(--ink2);
 background:var(--panel);border:1px solid var(--rule);border-radius:2px;
 padding:2px 7px 2px 5px;display:inline-flex;align-items:center;gap:5px}
.ab:hover{border-color:var(--ink3);color:var(--ink)}
.ab .abi{width:0;height:0;border-left:6px solid currentColor;
 border-top:4px solid transparent;border-bottom:4px solid transparent}
.ab.on{border-color:var(--ink);color:var(--ink)}
.ab.on .abi{width:6px;height:8px;border:0;background:currentColor;
 box-shadow:inset 0 0 0 1px var(--panel)}
.ab.wide{padding:3px 9px 3px 7px}

/* ---------- transport ---------- */
.transport{max-width:var(--grp);margin:var(--s4) auto 0;display:flex;align-items:center;
 gap:var(--s3);height:28px}
.tbtn{appearance:none;cursor:pointer;background:var(--panel);border:1px solid var(--rule);
 border-radius:2px;font:12px/1 var(--sans);color:var(--ink);padding:6px 10px;height:26px}
.tbtn:hover{border-color:var(--ink3)}
.tbtn{white-space:nowrap}
.tbtn .pp,.tbtn .pls{display:none}
.row.playing .tbtn.play .pl{display:none}
.row.playing .tbtn.play .pp{display:inline}
.scrub{flex:1;appearance:none;height:26px;background:none;cursor:pointer;margin:0}
.scrub::-webkit-slider-runnable-track{height:2px;background:var(--rule)}
.scrub::-webkit-slider-thumb{appearance:none;width:11px;height:11px;border-radius:50%;
 background:var(--ink);margin-top:-4.5px}
.scrub::-moz-range-track{height:2px;background:var(--rule)}
.scrub::-moz-range-thumb{width:11px;height:11px;border:0;border-radius:50%;background:var(--ink)}
.clock{font:12px/1 var(--mono);color:var(--ink2);min-width:96px;text-align:right}
.clock .now{color:var(--ink);font-weight:600}

/* ---------- gantt ---------- */
.gantt{position:relative;max-width:var(--grp);margin:var(--s3) auto 0;--glab:86px}
.grow{display:grid;grid-template-columns:var(--glab) 1fr;align-items:center;
 gap:0;height:22px}
.glab{font:11.5px/1 var(--sans);color:var(--ink2);text-align:right;padding-right:10px;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.grow[data-arm="0"] .glab{color:var(--a0);font-weight:600}
.grow[data-arm="1"] .glab{color:var(--a1);font-weight:600}
.grow[data-arm="2"] .glab{color:var(--a2);font-weight:600}
.gbar{position:relative;display:flex;height:12px;background:#F1EEE9}
.gs{display:block;height:100%}
.gh{background:var(--hear)}
.grow[data-arm="0"] .gi{background:var(--a0)} .grow[data-arm="0"] .gr{background:var(--r0)}
.grow[data-arm="1"] .gi{background:var(--a1)} .grow[data-arm="1"] .gr{background:var(--r1)}
.grow[data-arm="2"] .gi{background:var(--a2)} .grow[data-arm="2"] .gr{background:var(--r2)}
.gnum{position:absolute;top:-1px;font:11px/14px var(--mono);color:var(--ink);
 background:linear-gradient(var(--paper),var(--paper));white-space:nowrap}
.phwrap{position:absolute;left:var(--glab);right:0;top:0;bottom:0;pointer-events:none}
.playhead{position:absolute;top:0;bottom:0;width:1px;background:var(--ink);left:0;
 opacity:0;transition:opacity .15s}
.row.playing .playhead,.row.scrubbed .playhead{opacity:1}
.playhead:before{content:"";position:absolute;top:-3px;left:-2.5px;width:6px;height:6px;
 border-radius:50%;background:var(--ink)}
.axis{max-width:var(--grp);margin:var(--s2) auto 0;padding-left:86px;display:flex;
 justify-content:space-between;font:11px/1.4 var(--mono);color:var(--ink3)}
.akey{font:11.5px/1.4 var(--sans);color:var(--ink2);display:flex;gap:var(--s2);
 align-items:center}
.sw{width:10px;height:8px;display:inline-block;margin-right:3px}
.kh{background:var(--hear)} .ki{background:var(--a2)} .kr{background:var(--r2)}

footer.foot{border-top:1px solid var(--rule);margin-top:var(--s6);padding:var(--s4) 0 var(--s6);
 font-size:12.5px;color:var(--ink3);max-width:70ch}

@media (max-width:820px){
 :root{--col:62vw;--gap:12px}
 .vidgrid,.metagrid{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;
  gap:var(--gap);padding-bottom:var(--s2);justify-content:flex-start;
  -webkit-overflow-scrolling:touch;scrollbar-width:none}
 .vidgrid::-webkit-scrollbar,.metagrid::-webkit-scrollbar{display:none}
 .frame,.cell{flex:0 0 var(--col);scroll-snap-align:center}
 .transport{gap:var(--s2)}
 .tbtn.play .pl{display:none}
 .row:not(.playing) .tbtn.play .pls{display:inline}
 .clock{min-width:74px;font-size:11px}
 .gantt{--glab:74px}
 .axis{padding-left:74px}
 h1{font-size:26px}
 .akey{display:none}
}
"""

SCRIPT = r"""
(function(){
 var AUD=document.getElementById('sharedaudio');
 var curBtn=null, rows=[];

 function stopAudio(){ if(curBtn){curBtn.classList.remove('on');curBtn=null;} AUD.pause(); }
 AUD.addEventListener('ended',stopAudio);

 document.addEventListener('click',function(ev){
  var b=ev.target.closest('.ab'); if(!b) return;
  var was=(b===curBtn);
  stopAudio();
  if(was) return;
  rows.forEach(function(r){r.pause();});
  curBtn=b; b.classList.add('on');
  AUD.src=b.dataset.src; AUD.currentTime=0;
  AUD.play().catch(function(){ stopAudio(); });
 });

 function Row(el){
  var self=this;
  this.el=el;
  this.axis=parseFloat(el.dataset.axis)||1;
  this.vids=[].slice.call(el.querySelectorAll('video.rv'));
  this.frames=[].slice.call(el.querySelectorAll('.frame'));
  this.durs=this.vids.map(function(v){return parseFloat(v.dataset.clip)||self.axis;});
  this.ph=el.querySelector('.playhead');
  this.scrub=el.querySelector('.scrub');
  this.now=el.querySelector('.now');
  this.raf=null; this.iv=null; this.dragging=false;
  this.ref=0;                       /* clock arm = longest clip */
  for(var i=1;i<this.durs.length;i++) if(this.durs[i]>this.durs[this.ref]) this.ref=i;

  this.setAudible(parseInt(el.dataset.audible,10)||0);

  this.frames.forEach(function(f,i){
   f.addEventListener('click',function(ev){
    if(ev.target.closest('.bigplay')){ self.toggle(); return; }
    self.setAudible(i);
   });
  });
  el.querySelectorAll('.cell').forEach(function(c,i){
   c.querySelector('.lab').addEventListener('click',function(){ self.setAudible(i); });
  });
  el.querySelector('.tbtn.play').addEventListener('click',function(){ self.toggle(); });
  el.querySelector('.tbtn.restart').addEventListener('click',function(){ self.seek(0); self.play(); });
  this.scrub.addEventListener('input',function(){
   self.dragging=true; self.pause(); self.seek(parseFloat(self.scrub.value)||0);
   el.classList.add('scrubbed');
  });
  this.scrub.addEventListener('change',function(){ self.dragging=false; });
  this.vids.forEach(function(v){ v.addEventListener('ended',function(){ self.check(); }); });
  this.paint(0);
 }

 Row.prototype.setAudible=function(i){
  this.audible=i;
  this.vids.forEach(function(v,k){ v.muted=(k!==i); });
  this.frames.forEach(function(f,k){ f.classList.toggle('audible',k===i); });
 };
 Row.prototype.seek=function(t){
  var self=this;
  this.vids.forEach(function(v,k){
   var tt=Math.min(t,Math.max(self.durs[k]-0.04,0));
   if(v.readyState===0){                       /* preload="none": wait for metadata */
    v.preload='metadata';
    v.addEventListener('loadedmetadata',function h(){
     v.removeEventListener('loadedmetadata',h); try{ v.currentTime=tt; }catch(e){}
    });
    try{ v.load(); }catch(e){}
   } else { try{ v.currentTime=tt; }catch(e){} }
  });
  this.paint(t);
 };
 Row.prototype.play=function(){
  var self=this;
  stopAudio();
  rows.forEach(function(r){ if(r!==self) r.pause(); });
  this.el.classList.add('playing');
  this.vids.forEach(function(v,k){
   if(self.durs[k]-v.currentTime<0.05) return;       /* ended: hold last frame */
   v.playbackRate=1; var p=v.play(); if(p&&p.catch) p.catch(function(){});
  });
  cancelAnimationFrame(this.raf); clearInterval(this.iv);
  this.loop();
  /* rAF is frozen in background tabs; a slow interval keeps sync and playhead alive */
  var s2=this; this.iv=setInterval(function(){ s2.tick(); },200);
 };
 Row.prototype.pause=function(){
  this.el.classList.remove('playing');
  this.vids.forEach(function(v){ v.pause(); v.playbackRate=1; });
  cancelAnimationFrame(this.raf); this.raf=null;
  clearInterval(this.iv); this.iv=null;
 };
 Row.prototype.toggle=function(){
  if(this.el.classList.contains('playing')) this.pause();
  else{
   var t=this.vids[this.ref].currentTime;
   if(t>=this.durs[this.ref]-0.05) this.seek(0);
   this.play();
  }
 };
 Row.prototype.check=function(){
  var self=this, live=this.vids.some(function(v,k){ return v.currentTime<self.durs[k]-0.06; });
  if(!live) this.pause();
 };
 Row.prototype.paint=function(t){
  var f=Math.max(0,Math.min(t/this.axis,1));
  this.ph.style.left=(100*f)+'%';
  this.now.textContent=t.toFixed(2);
  if(!this.dragging) this.scrub.value=t;
 };
 Row.prototype.loop=function(){
  var self=this;
  if(!this.tick()) return;
  this.raf=requestAnimationFrame(function(){ self.loop(); });
 };
 Row.prototype.tick=function(){
  var self=this;
  var t=this.vids[this.ref].currentTime;
  /* clock arm stalled (buffering, or a background tab suspending muted video):
     don't fight it by dragging the others back */
  var stalled=(t===this._lastT); this._lastT=t;
  this.vids.forEach(function(v,k){
   if(k===self.ref||stalled) return;
   if(t>=self.durs[k]-0.06){ if(!v.paused) v.pause(); return; }   /* hold last frame */
   var d=v.currentTime-t;
   if(Math.abs(d)>0.25){ try{ v.currentTime=t; }catch(e){} v.playbackRate=1; }
   else if(Math.abs(d)>0.035){ v.playbackRate=d>0?0.94:1.06; }
   else v.playbackRate=1;
   if(v.paused){ var p=v.play(); if(p&&p.catch) p.catch(function(){}); }
  });
  this.paint(t);
  if(!this.el.classList.contains('playing')) return false;
  if(t>=this.durs[this.ref]-0.05){ this.pause(); return false; }
  return true;
 };

 document.querySelectorAll('.row').forEach(function(el){ rows.push(new Row(el)); });

 /* sticky backbone tabs: one backbone at a time */
 var tabs=[].slice.call(document.querySelectorAll('.tab'));
 tabs.forEach(function(t){
  t.addEventListener('click',function(){
   rows.forEach(function(r){r.pause();}); stopAudio();
   tabs.forEach(function(o){
    var on=(o===t); o.setAttribute('aria-selected',on?'true':'false');
    var sec=document.getElementById('bb-'+o.dataset.bb);
    if(sec) sec.hidden=!on;
   });
   window.scrollTo({top:0,behavior:'auto'});
  });
 });

 window.__rows=rows;   /* verification hook */
})();
"""


# --------------------------------------------------------------------------- page

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%23FAF9F7'/%3E%3Crect x='2' y='5' width='12' height='2' fill='%23D6D1C9'/%3E%3Crect x='2' y='9' width='7' height='2' fill='%23B4531F'/%3E%3C/svg%3E">
<style>__CSS__</style>
</head>
<body>
<div class="wrap">
<header class="top">
<h1>__TITLE__</h1>
<div class="byline">__BYLINE__</div>
<p class="kicker">Abstract</p>
<p class="lead">__ABSTRACT__</p>
<p class="kicker">How it was recorded</p>
__RECORDED__
__LINKS__
</header>
</div>

<div class="tabbar"><div class="in" role="tablist">__TABS__</div></div>

<div class="wrap">
<section id="humanoid">
<h2 class="kicker" style="margin-top:var(--s5)">__ROBOT_TITLE__</h2>
__SECTIONS__
</section>
<footer class="foot">__FOOT__</footer>
</div>
<audio id="sharedaudio" preload="none"></audio>
<script>__SCRIPT__</script>
</body>
</html>
"""


def build(site, manifest):
    groups = OrderedDict()
    for x in manifest:
        groups.setdefault(x.get("backbone"), []).append(x)
    keys = [k for k in BACKBONE_ORDER if k in groups]
    keys += [k for k in groups if k not in BACKBONE_ORDER]

    sections, tabs = [], []
    for i, k in enumerate(keys):
        entries = groups[k]
        name = entries[0].get("backbone_name") or BACKBONE_NAMES.get(k, str(k))
        sections.append(backbone_html(k, name, entries, i == 0))
        tabs.append(
            '<button type="button" class="tab" role="tab" data-bb="%s" aria-selected="%s">%s</button>'
            % (e(k), "true" if i == 0 else "false", e(name))
        )

    byline = [e(site.get("authors", ""))]
    if site.get("venue"):
        byline.append('<span class="dot">&middot;</span>')
        byline.append(e(site["venue"]))

    links = ""
    if site.get("links"):
        links = '<div class="links">%s</div>' % "".join(
            '<a href="%s">%s</a>' % (e(l.get("href", "#")), e(l.get("label", "")))
            for l in site["links"]
        )

    intro = site.get("intro", []) or []
    recorded = "".join('<p class="note">%s</p>' % p for p in intro) or ""

    out = PAGE
    for token, value in [
        ("__TITLE__", e(site.get("title", ""))),
        ("__CSS__", CSS),
        ("__BYLINE__", "".join(byline)),
        ("__ABSTRACT__", e(site.get("abstract", ""))),
        ("__RECORDED__", recorded),
        ("__LINKS__", links),
        ("__TABS__", "".join(tabs)),
        ("__ROBOT_TITLE__", e(site.get("robot_section_title", "Robot demo"))),
        ("__SECTIONS__", "".join(sections)),
        ("__FOOT__", site.get("footnote", "") or ""),
        ("__SCRIPT__", SCRIPT),
    ]:
        out = out.replace(token, value)
    return out


def main():
    ap = argparse.ArgumentParser(description="Build the AMECA showcase page.")
    ap.add_argument("--site", default=os.path.join(HERE, "site.json"))
    ap.add_argument("--manifest", default=os.path.join(HERE, "robot", "manifest.json"))
    ap.add_argument("-o", "--out", default=os.path.join(HERE, "index.html"))
    a = ap.parse_args()

    with open(a.site, encoding="utf-8") as f:
        site = json.load(f)
    with open(a.manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    if isinstance(manifest, dict):
        manifest = manifest.get("entries", [])

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(build(site, manifest))
    print("wrote %s (%d entries from %s)" % (a.out, len(manifest), a.manifest))


if __name__ == "__main__":
    main()
