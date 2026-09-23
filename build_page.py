#!/usr/bin/env python3
"""Build the static Situated Inference project page (index.html).

DESIGN NOTE (2026-09, Clarity rebuild)
 1. Typography follows Clarity (Shikun Liu, CC0, shikun.io/projects/clarity): a serif reading
    column (Charter, bundled in assets/fonts) under sans headings (Poppins), and width
    tiers (main 760 / demo 1240 px). No jQuery, MathJax or FontAwesome: static HTML.
 2. The page is the demo: centred title, the abstract, then the Ameca humanoid rows.
    Backbone navigation is a side rail (>=1100 px) or a sticky bar. Text lives in site.json.
 3. The Ameca demo keeps the synchronised 'race' rows: three arms on one clock, a
    shared Gantt axis and one playhead. Strategy accents: default #6B6660, situated
    quality #1D5FA8, situated efficiency #B4531F.
 4. Sync: the audible arm is the clock and is never retimed; muted arms follow with
    hysteresis and seek only on large drift (clips carry a 0.5 s GOP).

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
BACKBONE_LONG = {"sb": "Schr\u00f6dinger Bridge", "sgmse": "Score-based diffusion",
                 "flowse": "Flow matching", "storm": "Stochastic regeneration"}
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


def title_html(title):
    """Split at the first colon: main name on line 1 (accent colour), subtitle on line 2."""
    head, sep, tail = title.partition(":")
    if not sep:
        return e(title)
    return '<span class="t1">%s</span><span class="t2">%s</span>' % (e(head.strip()), e(tail.strip()))


def arm_labels(entry, backbone_name):
    """Under-video caption. Default arm = backbone name only; situated arms name the
    backbone plus the SI objective, e.g. "SB + SI (quality)"."""
    strategy = entry.get("strategy", "default")
    bn = e(backbone_name)
    if strategy == "default":
        return bn
    if strategy == "quality":
        return "%s + SI (quality)" % bn
    return "%s + SI (efficiency)" % bn


def gantt_label(entry, backbone_name):
    strategy = entry.get("strategy", "default")
    if strategy == "default":
        return e(backbone_name)
    if strategy == "quality":
        return "+SI Q"
    return "+SI E"


def audio_btn(src, label, cls=""):
    if not src:
        return ""
    return '<button type="button" class="ab%s" data-src="%s"><i class="abi"></i>%s</button>' % (
        (" " + cls) if cls else "",
        e(src),
        label,
    )


OVERLAY_SVG = (
    '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">'
    '<path class="pi" d="M8 5.5v13l11-6.5z"></path>'
    '<path class="pa" d="M8.5 5.5h3.4v13H8.5zM14.1 5.5h3.4v13h-3.4z"></path></svg>'
)


def arm_html(entry, backbone_name, idx, default_compute):
    strategy = entry.get("strategy", "default")
    armlab = arm_labels(entry, backbone_name)

    chips = []
    nfe = entry.get("nfe")
    if nfe is not None:
        chips.append(chip('NFE&nbsp;<b class="n">%s</b>' % e(nfe)))
    pesq = entry.get("pesq")
    if pesq is not None:
        chips.append(chip('PESQ&nbsp;<b class="n">%s</b>' % num(pesq)))
    cmp_s = entry.get("compute")
    if strategy != "default" and cmp_s and default_compute:
        ratio = float(default_compute) / float(cmp_s)
        if ratio >= 1.0:
            chips.append(chip('<b class="n">%s&times;</b>&nbsp;faster' % num(ratio, 1), "hi"))
        else:
            chips.append(chip('<b class="n">%s&times;</b>&nbsp;slower' % num(1.0 / ratio, 1), "hi"))
    if entry.get("same_as_quality") and strategy == "efficiency":
        chips.append(chip("= quality", "eq"))

    cfg = entry.get("cfg")
    title_attr = ' title="%s"' % e(cfg) if cfg else ""

    frame = (
        '<div class="frame" data-arm="{idx}">'
        '<video class="rv" playsinline preload="none" muted poster="{poster}" src="{video}" '
        'data-clip="{clip}" data-compute="{compute}"></video>'
        '<span class="spk" aria-hidden="true">&#128266;</span>'
        '<button type="button" class="ov" data-arm="{idx}" aria-label="play or pause this arm alone">'
        "{svg}</button></div>"
    ).format(
        idx=idx,
        poster=e(entry.get("poster", "")),
        video=e(entry.get("video", "")),
        clip=num(entry.get("clip"), 3),
        compute=num(cmp_s, 4) if cmp_s is not None else "",
        svg=OVERLAY_SVG,
    )

    return (
        '<div class="cell" data-arm="{idx}">'
        '<figure class="fig">{frame}'
        '<figcaption class="armlab"{title_attr}>{armlab}</figcaption></figure>'
        '<aside class="side"><div class="chips">{chips}</div>'
        '<div class="auds">{heard}{enh}</div></aside>'
        "</div>"
    ).format(
        idx=idx,
        frame=frame,
        title_attr=title_attr,
        armlab=armlab,
        chips="".join(chips),
        heard=audio_btn(entry.get("heard"), "Ameca heard", "wide"),
        enh=audio_btn(entry.get("enh"), "Enhanced speech", "wide"),
    )


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

    gl = gantt_label(entry, backbone_name)

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

    cells, grows = [], []
    for i, a in enumerate(arms):
        cells.append(arm_html(a, backbone_name, i, default_compute))
        grows.append(gantt_row_html(a, backbone_name, axis, i))

    # audible arm for "play all" = the fastest arm (smallest measured compute)
    audible = 0
    best = None
    for i, a in enumerate(arms):
        c = a.get("compute")
        if c is not None and (best is None or float(c) < best):
            best, audible = float(c), i

    first = arms[0]
    raw = (first.get("transcript", "") or "").strip()
    if raw.isupper():
        raw = raw.capitalize()
        raw = re.sub(r"\bi\b", "I", raw)
    transcript = e(raw)
    snr = first.get("snr_db")
    snr_html = chip('SNR&nbsp;<b class="n">%s</b>&nbsp;dB' % num(snr, 1)) if snr is not None else ""
    noisy = audio_btn(first.get("noisy"), "noisy input", "wide")

    return (
        '<article class="row" data-axis="{axis}" data-audible="{aud}" id="{rid}">'
        '<header class="rhead"><span class="bbtag">{bbname}</span>'
        '<h3 class="utt">{transcript}</h3>'
        '<div class="rmeta">{snr}{noisy}</div></header>'
        '<div class="cells">{cells}</div>'
        '<div class="transport">'
        '<button type="button" class="tbtn play" aria-label="play or pause the row">'
        '<span class="pl">Play all</span><span class="pls">Play</span>'
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
        bbname=e(backbone_name),
        transcript=transcript,
        snr=snr_html,
        noisy=noisy,
        cells="".join(cells),
        axmax=num(axis),
        grows="".join(grows),
    )


def backbone_html(key, name, entries, idx):
    rows = OrderedDict()
    for x in entries:
        rows.setdefault(x.get("utt"), []).append(x)
    body = "".join(
        row_html(u, v, name, "%s-%d" % (e(key), i + 1)) for i, (u, v) in enumerate(rows.items())
    )
    return (
        '<section class="bb" id="bb-{key}" data-bb="{key}">'
        '<h2 class="bbh"><span><span class="bbk">Backbone:</span> {full} ({name})</span>{legend}</h2>'
        "{body}</section>"
    ).format(key=e(key), name=e(name), n=len(rows), body=body,
             legend='<span class="legend">SI = Situated Inference</span>' if idx == 0 else '',
             full=e(BACKBONE_LONG.get(key, "")))


# --------------------------------------------------------------------------- assets

CSS = """
@font-face{font-family:Charter;font-style:normal;font-weight:400;font-display:swap;src:url(assets/fonts/charter_regular.woff2) format('woff2')}
@font-face{font-family:Charter;font-style:italic;font-weight:400;font-display:swap;src:url(assets/fonts/charter_italic.woff2) format('woff2')}
@font-face{font-family:Charter;font-style:normal;font-weight:700;font-display:swap;src:url(assets/fonts/charter_bold.woff2) format('woff2')}
@font-face{font-family:Charter;font-style:italic;font-weight:700;font-display:swap;src:url(assets/fonts/charter_bold_italic.woff2) format('woff2')}
:root{
 --paper:#FFFFFF; --panel:#F6F6F6; --hero:#E8ECEF; --ink:#2F2F2F; --ink2:#5F5F5F; --ink3:#8A8A8A;
 --rule:#E2E2E2; --hear:#D6D6D6;
 --s1:4px; --s2:8px; --s3:12px; --s4:20px; --s5:32px; --s6:56px;
 --gap:24px; --main:760px; --large:1100px; --measure:1240px;
 --sans:"Poppins",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 --serif:Charter,"Bitstream Charter","Iowan Old Style",Georgia,serif;
 --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
 --a0:#6B6660; --a1:#1D5FA8; --a2:#B4531F;
 --r0:#D2D0CE; --r1:#C4D6E9; --r2:#EDD2C1;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font:300 15px/1.55 var(--sans);
 -webkit-font-smoothing:antialiased}
b,strong{font-weight:600}
.n,.mono,.clock,.chip,.gnum,.scrub{font-variant-numeric:tabular-nums}
a{color:inherit;text-underline-offset:2px}
img{display:block;max-width:100%;height:auto}
::selection{color:#fff;background:#353535}

/* ---------- width tiers (Clarity: main / large / extra-large) ---------- */
.w-main,.wrap{margin:0 auto;padding:0 var(--s4)}
.w-main{max-width:calc(var(--main) + 2*var(--s4))}
.wrap{max-width:calc(var(--measure) + 2*var(--s4))}

/* ---------- hero ---------- */
.hero{background:var(--hero)}
.hero-in{max-width:calc(var(--main) + 2*var(--s4));margin:0 auto;padding:var(--s6) var(--s4) var(--s5);text-align:center}
.venue{font:600 12px/1.5 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 var(--s3)}
h1{margin:0 0 var(--s3);display:flex;flex-direction:column;align-items:center;gap:6px;line-height:1.2;letter-spacing:-.01em;font-weight:600}
/* one size step apart: 30 / 26 px on desktop */
.t1{font-size:clamp(25px,3vw,30px);color:var(--a1)}
.t2{font-size:clamp(21px,2.6vw,26px);font-weight:500;color:var(--ink)}
.authors{font-style:italic;font-weight:500;font-size:15px;margin:0;color:var(--ink2)}

/* ---------- backbone nav: side rail when there is room, sticky bar otherwise ---------- */
.siderail{position:sticky;top:0;z-index:40;background:rgba(255,255,255,.94);backdrop-filter:blur(8px);
 -webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--rule);display:flex;gap:var(--s4);align-items:center;
 justify-content:center;overflow-x:auto;height:44px;padding:0 var(--s4);scrollbar-width:none}
.siderail::-webkit-scrollbar{display:none}
.navhead{display:none}
.navlink{font:500 13px/44px var(--sans);color:var(--ink2);text-decoration:none;white-space:nowrap;
 border-bottom:2px solid transparent}
.navlink:hover{color:var(--ink)}
.navlink.cur{color:var(--ink);border-bottom-color:var(--ink)}
@media (min-width:1100px){
 /* page stays centred on the viewport; the demo column narrows to leave a 160 px margin for the rail */
 .wrap{max-width:min(calc(var(--measure) + 2*var(--s4)), calc(100vw - 320px))}
 .siderail{position:fixed;top:50%;transform:translateY(-50%);left:max(16px, calc((100vw - var(--measure))/2 - 150px));height:auto;width:120px;
  flex-direction:column;align-items:flex-start;justify-content:flex-start;gap:2px;background:none;border:0;
  padding:0;overflow:visible;backdrop-filter:none;-webkit-backdrop-filter:none}
 .siderail .navhead{display:block;font:600 11px/1.6 var(--sans);letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink3);margin:0 0 6px;padding-left:12px}
 .siderail .navlink{font:500 13px/1.5 var(--sans);border-bottom:0;border-left:2px solid var(--rule);padding:5px 0 5px 12px}
 .siderail .navlink.cur{border-left-color:var(--ink)}
}

/* ---------- sections ---------- */
section.sec{padding:var(--s5) 0 0;scroll-margin-top:48px}
#humanoid{padding-top:var(--s3)}
.kicker{font:600 12px/1.5 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);margin:0 0 var(--s2)}
h2{font:600 clamp(24px,2.6vw,30px)/1.2 var(--sans);letter-spacing:-.01em;margin:0 0 var(--s4)}
p.text{font:400 18px/1.68 var(--serif);color:#353535;margin:0 0 var(--s4)}
p.text i{font-style:italic}
.m{white-space:nowrap}
footer.foot{margin-top:var(--s6);padding:var(--s5) 0;border-top:1px solid var(--rule);font:400 13px/1.6 var(--sans);color:var(--ink3);text-align:center}

/* ---------- backbone sections ---------- */
.legend{font-size:12px;color:var(--ink3);font-weight:400;font-style:italic}
.bbh{font:600 20px/1.3 var(--sans);letter-spacing:-.01em;margin:0 0 var(--s3);padding-top:var(--s5);
 display:flex;justify-content:space-between;align-items:baseline;gap:var(--s3);flex-wrap:wrap}
.bbk{color:var(--ink3);font-weight:500}
.bb{padding:0 0 var(--s4);scroll-margin-top:48px}

/* ---------- row ---------- */
.row{border-top:1px solid var(--rule);padding:var(--s5) 0;scroll-margin-top:56px}
.row:nth-of-type(even){background:var(--panel);margin:0 calc(-1 * var(--s4));padding-left:var(--s4);padding-right:var(--s4);border-radius:6px}
.rhead{margin:0 0 var(--s4);display:flex;gap:var(--s3);align-items:baseline;flex-wrap:wrap}
.bbtag{font:600 11px/1.7 var(--mono);letter-spacing:.04em;text-transform:uppercase;
 color:var(--ink2);border:1px solid var(--rule);border-radius:2px;padding:1px 6px;background:var(--paper)}
.utt{font:italic 400 18px/1.4 var(--serif);margin:0;flex:1 1 260px}
.rmeta{display:flex;gap:var(--s2);align-items:center;margin-left:auto}

.cells{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--gap);width:100%}
.cell{min-width:0;display:flex;gap:var(--s3);align-items:flex-start}
.fig{margin:0;flex:1 1 58%;min-width:0}
.frame{position:relative;width:100%;aspect-ratio:2/3;background:#141414;overflow:hidden;
 border-radius:4px;cursor:pointer}
.frame video{display:block;width:100%;height:100%;object-fit:cover}
.frame video::-webkit-media-controls{display:none!important}
.spk{position:absolute;top:6px;right:6px;font-size:12px;line-height:1;padding:4px 5px;
 border-radius:3px;background:rgba(0,0,0,.55);opacity:0;transition:opacity .15s}
.frame.audible .spk{opacity:1}
.frame.audible{outline:2px solid var(--ink);outline-offset:-2px}
.armlab{font:500 12px/1.4 var(--sans);color:var(--a0);text-align:center;margin:var(--s1) 0 0;
 border-top:2px solid var(--a0);padding-top:4px}
.cell[data-arm="1"] .armlab{border-top-color:var(--a1);color:var(--a1)}
.cell[data-arm="2"] .armlab{border-top-color:var(--a2);color:var(--a2)}

.ov{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
 width:44px;height:44px;border-radius:50%;border:1px solid rgba(255,255,255,.7);
 background:rgba(20,20,20,.55);color:#fff;cursor:pointer;display:grid;place-items:center;
 padding:0;backdrop-filter:blur(2px);opacity:0;transition:opacity .18s,transform .18s}
.frame:hover .ov,.frame.audible .ov{opacity:1}
.ov svg{fill:#fff;transform:translateX(1px)}
.ov .pa{display:none}
.ov.on .pi{display:none}
.ov.on .pa{display:block;transform:translateX(-1px)}
.ov:hover{transform:translate(-50%,-50%) scale(1.06)}

.side{flex:1 1 42%;min-width:76px;display:flex;flex-direction:column;gap:var(--s2)}
.chips{display:flex;flex-wrap:wrap;gap:var(--s1);align-content:flex-start}
.chip{font:11.5px/1.5 var(--mono);color:var(--ink2);border:1px solid var(--rule);
 background:var(--paper);border-radius:2px;padding:1px 6px;white-space:nowrap}
.chip .n{color:var(--ink);font-weight:600}
.chip.hi{border-color:var(--a0);color:var(--a0)}
.cell[data-arm="1"] .chip.hi{border-color:var(--a1);color:var(--a1)}
.cell[data-arm="2"] .chip.hi{border-color:var(--a2);color:var(--a2)}
.chip.eq{border-style:dashed}
.auds{display:flex;flex-direction:column;gap:var(--s1)}
.ab{appearance:none;cursor:pointer;font:400 12px/1.5 var(--sans);color:var(--ink2);
 background:var(--paper);border:1px solid var(--rule);border-radius:3px;
 padding:2px 7px 2px 5px;display:inline-flex;align-items:center;gap:6px}
.ab:hover{border-color:var(--ink3);color:var(--ink)}
.ab .abi{width:0;height:0;border-left:6px solid currentColor;
 border-top:4px solid transparent;border-bottom:4px solid transparent}
.ab.on{border-color:var(--ink);color:var(--ink)}
.ab.on .abi{width:6px;height:8px;border:0;background:currentColor;
 box-shadow:inset 0 0 0 1px var(--paper)}
.ab.wide{width:100%;padding:5px 9px 5px 7px}

/* ---------- transport ---------- */
.transport{margin:var(--s4) 0 0;display:flex;align-items:center;gap:var(--s3);height:28px}
.tbtn{appearance:none;cursor:pointer;background:var(--paper);border:1px solid var(--rule);
 border-radius:3px;font:500 12.5px/1 var(--sans);color:var(--ink);padding:6px 11px;height:28px;white-space:nowrap}
.tbtn:hover{border-color:var(--ink3)}
.tbtn .pp,.tbtn .pls{display:none}
.row.playing .tbtn.play .pl{display:none}
.row.playing .tbtn.play .pp{display:inline}
.row.loading .tbtn.play{opacity:.55}
.scrub{flex:1;appearance:none;height:26px;background:none;cursor:pointer;margin:0}
.scrub::-webkit-slider-runnable-track{height:2px;background:var(--rule)}
.scrub::-webkit-slider-thumb{appearance:none;width:11px;height:11px;border-radius:50%;
 background:var(--ink);margin-top:-4.5px}
.scrub::-moz-range-track{height:2px;background:var(--rule)}
.scrub::-moz-range-thumb{width:11px;height:11px;border:0;border-radius:50%;background:var(--ink)}
.clock{font:12px/1 var(--mono);color:var(--ink2);min-width:96px;text-align:right}
.clock .now{color:var(--ink);font-weight:600}

/* ---------- gantt ---------- */
.gantt{position:relative;margin:var(--s3) 0 0;--glab:86px}
.grow{display:grid;grid-template-columns:var(--glab) 1fr;align-items:center;gap:0;height:22px}
.glab{font:500 11.5px/1 var(--sans);color:var(--ink2);text-align:right;padding-right:10px;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.grow[data-arm="0"] .glab{color:var(--a0)}
.grow[data-arm="1"] .glab{color:var(--a1)}
.grow[data-arm="2"] .glab{color:var(--a2)}
.gbar{position:relative;display:flex;height:12px;background:#EDEDED}
.gs{display:block;height:100%}
.gh{background:var(--hear)}
.grow[data-arm="0"] .gi{background:var(--a0)} .grow[data-arm="0"] .gr{background:var(--r0)}
.grow[data-arm="1"] .gi{background:var(--a1)} .grow[data-arm="1"] .gr{background:var(--r1)}
.grow[data-arm="2"] .gi{background:var(--a2)} .grow[data-arm="2"] .gr{background:var(--r2)}
.gnum{position:absolute;top:-1px;font:11px/14px var(--mono);color:var(--ink);white-space:nowrap}
.phwrap{position:absolute;left:var(--glab);right:0;top:0;bottom:0;pointer-events:none}
.playhead{position:absolute;top:0;bottom:0;width:1px;background:var(--ink);left:0;
 opacity:0;transition:opacity .15s}
.row.playing .playhead,.row.scrubbed .playhead{opacity:1}
.playhead:before{content:"";position:absolute;top:-3px;left:-2.5px;width:6px;height:6px;
 border-radius:50%;background:var(--ink)}
.axis{margin:var(--s2) 0 0;padding-left:86px;display:flex;
 justify-content:space-between;font:11px/1.4 var(--mono);color:var(--ink3)}
.akey{font:400 11.5px/1.4 var(--sans);color:var(--ink2);display:flex;gap:var(--s2);align-items:center}
.sw{width:10px;height:8px;display:inline-block;margin-right:3px}
.kh{background:var(--hear)} .ki{background:var(--a2)} .kr{background:var(--r2)}

/* ---------- responsive ---------- */
@media (max-width:899px){
 .cells{grid-template-columns:1fr;gap:var(--s4)}
 .gantt{--glab:74px}
 .axis{padding-left:74px}
}
@media (max-width:600px){ .hero-in{padding:var(--s5) var(--s4) var(--s4)} }
@media (max-width:480px){
 p.text{font-size:17px}
 .cell{flex-direction:column}
 .side{width:100%}
 .transport{gap:var(--s2)}
 .tbtn.play .pl{display:none}
 .row:not(.playing) .tbtn.play .pls{display:inline}
 .clock{min-width:74px;font-size:11px}
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
  rows.forEach(function(r){r.pause(); r.stopSolo();});
  curBtn=b; b.classList.add('on');
  AUD.src=b.dataset.src; AUD.currentTime=0;
  AUD.play().catch(function(){ stopAudio(); });
 });

 /* Sync model. The arm you hear is the clock and is never retimed, so its sound
    is never time-stretched. The muted arms follow it: a gentle rate nudge for
    small drift (with hysteresis so the rate does not flutter frame to frame) and
    a seek only for large drift, which is cheap because clips carry a keyframe
    every 0.5 s. When the audible arm has finished, the longest arm is the clock. */
 var SEEK=0.35, NUDGE_ON=0.06, NUDGE_OFF=0.02, SLOW=0.92, FAST=1.08;

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
  this.raf=null; this.iv=null; this.dragging=false; this.soloIdx=-1;
  this.ref=0;                       /* longest clip: decides when the row ends */
  for(var i=1;i<this.durs.length;i++) if(this.durs[i]>this.durs[this.ref]) this.ref=i;

  this.setAudible(parseInt(el.dataset.audible,10)||0);

  this.frames.forEach(function(f,i){
   var ov=f.querySelector('.ov');
   if(ov) ov.addEventListener('click',function(ev){ ev.stopPropagation(); self.toggleSolo(i); });
   f.addEventListener('click',function(ev){
    if(ev.target.closest('.ov')) return;
    if(self.el.classList.contains('playing')) self.setAudible(i);
   });
  });
  el.querySelector('.tbtn.play').addEventListener('click',function(){ self.toggle(); });
  el.querySelector('.tbtn.restart').addEventListener('click',function(){ self.seek(0); self.play(); });
  this.scrub.addEventListener('input',function(){
   self.dragging=true; self.pause(); self.seek(parseFloat(self.scrub.value)||0);
   el.classList.add('scrubbed');
  });
  this.scrub.addEventListener('change',function(){ self.dragging=false; });
  this.vids.forEach(function(v,k){
   v.addEventListener('ended',function(){ if(self.soloIdx===k) self.stopSolo(); self.check(); });
  });
  this.paint(0);
 }

 Row.prototype.warm=function(){       /* fetch clips before the first press */
  this.vids.forEach(function(v){ if(v.preload!=='auto'){ v.preload='auto'; } });
 };
 Row.prototype.setAudible=function(i){
  this.audible=i;
  this.vids.forEach(function(v,k){ v.muted=(k!==i); if(k===i) v.playbackRate=1; });
  this.frames.forEach(function(f,k){ f.classList.toggle('audible',k===i); });
 };
 Row.prototype.clock=function(){
  var a=this.audible;
  if(this.vids[a] && this.vids[a].currentTime<this.durs[a]-0.06) return a;
  return this.ref;
 };
 /* solo: play exactly one arm alone, unmuted, outside the synced transport */
 Row.prototype.toggleSolo=function(i){
  var self=this;
  stopAudio();
  rows.forEach(function(r){ if(r!==self){ r.pause(); r.stopSolo(); } });
  if(this.el.classList.contains('playing')) this.pause();
  if(this.soloIdx===i){ this.stopSolo(); return; }
  this.stopSolo();
  this.soloIdx=i;
  var ov=this.frames[i].querySelector('.ov');
  this.vids.forEach(function(v,k){ v.muted=(k!==i); if(k!==i) v.pause(); });
  this.frames.forEach(function(f,k){ f.classList.toggle('audible',k===i); });
  if(ov) ov.classList.add('on');
  var v=this.vids[i];
  if(v.currentTime>=this.durs[i]-0.05) v.currentTime=0;
  v.playbackRate=1;
  var p=v.play(); if(p&&p.catch) p.catch(function(){});
 };
 Row.prototype.stopSolo=function(){
  if(this.soloIdx<0) return;
  var i=this.soloIdx, v=this.vids[i], ov=this.frames[i].querySelector('.ov');
  v.pause();
  if(ov) ov.classList.remove('on');
  this.soloIdx=-1;
  this.setAudible(this.audible);
 };
 Row.prototype.seek=function(t){
  var self=this;
  this.vids.forEach(function(v,k){
   var tt=Math.min(t,Math.max(self.durs[k]-0.04,0));
   if(v.readyState===0){                       /* not loaded yet: wait for metadata */
    v.preload='auto';
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
  this.stopSolo();
  rows.forEach(function(r){ if(r!==self){ r.pause(); r.stopSolo(); } });
  this.warm();
  this.el.classList.add('playing');
  /* all play() calls stay inside the click so browsers allow the unmuted arm */
  this.vids.forEach(function(v,k){
   v.playbackRate=1;
   if(self.durs[k]-v.currentTime<0.05) return;       /* ended: hold last frame */
   var p=v.play(); if(p&&p.catch) p.catch(function(){});
  });
  cancelAnimationFrame(this.raf); clearInterval(this.iv);
  this.loop();
  /* rAF is frozen in background tabs; a slow interval keeps sync and playhead alive */
  this.iv=setInterval(function(){ self.tick(); },200);
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
  var self=this, c=this.clock(), cv=this.vids[c], t=cv.currentTime;
  /* clock arm buffering: hold corrections instead of dragging the others around */
  var stalled=(t===this._lastT && c===this._lastC) || cv.readyState<3;
  this._lastT=t; this._lastC=c;
  this.vids.forEach(function(v,k){
   if(k===c) return;
   if(t>=self.durs[k]-0.06){ if(!v.paused) v.pause(); v.playbackRate=1; return; }  /* hold last frame */
   if(stalled) return;
   var d=v.currentTime-t, ad=Math.abs(d);
   if(ad>SEEK){ try{ v.currentTime=t; }catch(e){} v.playbackRate=1; }
   else if(ad>NUDGE_ON){ var r=d>0?SLOW:FAST; if(v.playbackRate!==r) v.playbackRate=r; }
   else if(ad<NUDGE_OFF && v.playbackRate!==1){ v.playbackRate=1; }
   if(v.paused){ var p=v.play(); if(p&&p.catch) p.catch(function(){}); }
  });
  this.paint(t);
  if(!this.el.classList.contains('playing')) return false;
  if(this.vids[this.ref].currentTime>=this.durs[this.ref]-0.05){ this.pause(); return false; }
  return true;
 };

 document.querySelectorAll('.row').forEach(function(el){ rows.push(new Row(el)); });

 /* start fetching a row's three clips shortly before it scrolls into view */
 if('IntersectionObserver' in window){
  var warmObs=new IntersectionObserver(function(entries){
   entries.forEach(function(en){
    if(!en.isIntersecting) return;
    var r=rows.filter(function(x){ return x.el===en.target; })[0];
    if(r) r.warm(); warmObs.unobserve(en.target);
   });
  },{rootMargin:'300px 0px'});
  rows.forEach(function(r){ warmObs.observe(r.el); });
 }

 /* scrollspy: backbone sections */
 function spy(selector, links, onChange){
  var secs=[].slice.call(document.querySelectorAll(selector));
  if(!('IntersectionObserver' in window) || !secs.length) return;
  var seen={};
  var obs=new IntersectionObserver(function(entries){
   entries.forEach(function(en){ seen[en.target.id]=en.isIntersecting; });
   var inview=secs.filter(function(s){ return seen[s.id]; });
   var id=inview.length?inview[0].id:null;
   links.forEach(function(a){ a.classList.toggle('cur', id!==null && a.getAttribute('href')==='#'+id); });
   if(onChange) onChange(id);
  },{rootMargin:'-20% 0px -70% 0px',threshold:0});
  secs.forEach(function(s){ obs.observe(s); });
 }
 spy('.bb', [].slice.call(document.querySelectorAll('.siderail .navlink')));

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
<meta name="description" content="__DESC__">
<meta property="og:type" content="website">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__URL__">
<meta property="og:image" content="__URL__assets/ameca_cover.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%23E8ECEF'/%3E%3Crect x='2' y='5' width='12' height='2' fill='%23BFC6CC'/%3E%3Crect x='2' y='9' width='7' height='2' fill='%231D5FA8'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,300;0,400;0,500;0,600;1,400;1,500&display=swap" rel="stylesheet">
<link rel="preload" href="assets/fonts/charter_regular.woff2" as="font" type="font/woff2" crossorigin>
<style>__CSS__</style>
</head>
<body>
<header class="hero">
 <div class="hero-in">
  <p class="venue">__VENUE__</p>
  <h1>__TITLE_HTML__</h1>
  <p class="authors">__AUTHORS__</p>
 </div>
</header>

<nav class="siderail" aria-label="backbones"><span class="navhead">Backbone</span>__NAVBB__</nav>

<main>
<section class="sec" id="abstract">
 <div class="w-main">
  <p class="kicker">Abstract</p>
  <p class="text">__ABSTRACT__</p>
 </div>
</section>

<section class="sec" id="humanoid">
 <div class="wrap">
__SECTIONS__
 </div>
</section>
</main>

<footer class="foot"><div class="w-main">__FOOTER__</div></footer>
<audio id="sharedaudio" preload="none"></audio>
<script>__SCRIPT__</script>
</body>
</html>
"""


def paras(items):
    """Trusted HTML from site.json (it carries <i>, <sub>, <b>)."""
    return "".join('<p class="text">%s</p>' % t for t in items)


def build(site, manifest):
    groups = OrderedDict()
    for x in manifest:
        groups.setdefault(x.get("backbone"), []).append(x)
    keys = [k for k in BACKBONE_ORDER if k in groups]
    keys += [k for k in groups if k not in BACKBONE_ORDER]

    sections, navbb = [], []
    for i, k in enumerate(keys):
        entries = groups[k]
        name = entries[0].get("backbone_name") or BACKBONE_NAMES.get(k, str(k))
        sections.append(backbone_html(k, name, entries, i))
        navbb.append('<a class="navlink" href="#bb-%s">%s</a>' % (e(k), e(name)))


    out = PAGE
    for token, value in [
        ("__CSS__", CSS),
        ("__SCRIPT__", SCRIPT),
        ("__TITLE_HTML__", title_html(site.get("title", ""))),
        ("__TITLE__", e(site.get("title", ""))),
        ("__DESC__", e(site.get("tldr", ""))),
        ("__URL__", e(site.get("page_url", ""))),
        ("__VENUE__", e(site.get("venue", ""))),
        ("__AUTHORS__", e(site.get("authors", ""))),
        ("__NAVBB__", "".join(navbb)),
        ("__ABSTRACT__", e(site.get("abstract", ""))),
        ("__SECTIONS__", "".join(sections)),
        ("__FOOTER__", site.get("footer", "")),
    ]:
        out = out.replace(token, value)
    leftover = re.findall(r"__[A-Z_]+__", out)
    if leftover:
        raise SystemExit("unfilled tokens: %s" % sorted(set(leftover)))
    return out


def main():
    ap = argparse.ArgumentParser(description="Build the Situated Inference project page.")
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
