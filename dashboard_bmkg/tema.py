"""Tema bersama dashboard BMKG x IPB (satu sumber tampilan untuk semua halaman).

Isi: warna, CSS template (diambil apa adanya dari app Abie), logo header, tombol layar penuh.
Dipakai oleh app.py (cangkang) dan oleh halaman-halaman di halaman/pN_*/ lewat `from tema import ...`.
Mengubah tampilan seluruh dashboard = ubah file ini saja.
"""
import base64
import os

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ konstanta warna
NAVY, BLUE, ORANGE = "#0b2a4a", "#1f6fb5", "#e8710a"
BLUE_LINE, GRID, INK, INK2, ZERO = "#9db4cc", "#e6ebf1", "#10243b", "#44566c", "#8793a3"
BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
TEAL = "#0f8b8d"   # warna khusus forecast (oranye = anomali positif)
FONT = "Poppins, 'Segoe UI', sans-serif"


# ------------------------------------------------------------------ gaya (layout mengikuti desain Canva, 1 layar)
def _h(key, expr):
    sel = ", ".join(f'.st-key-{key}{x}' for x in ("", ' [data-testid="stPlotlyChart"]', " .js-plotly-plot", " .plot-container", " .svg-container", " .main-svg"))
    return f".st-key-{key}{{flex:0 0 auto !important;}} {sel} {{height:{expr} !important;}}\n"


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
:root{--hdr:56px; --flt:80px; --kpi:72px; --ftr:32px; --gap:8px;
  --M:max(440px, calc(100vh - var(--hdr) - var(--flt) - var(--kpi) - var(--ftr) - 5*var(--gap) - 8px));
  --A:calc(var(--M) - 40px); --Tt:calc(var(--A)*.555); --Tb:calc(var(--A)*.445); --Rt:calc(var(--A)*.48); --Rb:calc(var(--A)*.52);}
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu {display:none !important;}
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {background:#eef2f7 !important; color:§INK; color-scheme:light; font-family:"Poppins","Segoe UI",sans-serif;}
html, body, [data-testid="stAppViewContainer"] {overflow-x:hidden !important;}
[data-testid="stMain"] {overflow-y:auto !important;}
.block-container, [data-testid="stMainBlockContainer"], .stMainBlockContainer {padding:0 .6rem 0 .6rem !important; max-width:100% !important;}
[data-testid="stMain"] > div:first-child, [data-testid="stMainBlockContainer"] > div:first-child {padding-top:0 !important; margin-top:0 !important;}
[data-testid="stVerticalBlock"] {gap:var(--gap) !important;}
[data-testid="stHorizontalBlock"] {gap:var(--gap) !important;}
div[data-testid="stElementContainer"] {margin:0 !important; flex-shrink:0 !important;}
.st-key-main, .st-key-filt, .st-key-secL, .st-key-secR, .st-key-rowL {flex-shrink:0 !important;}
[data-testid="stMarkdown"], [data-testid="stMarkdownContainer"] {margin:0 !important;}
/* elemen tanpa tinggi (CSS, nav absolut) jangan ikut dihitung gap */
div[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style) {display:none !important;}
div[data-testid="stElementContainer"]:has(> .st-key-pgnav), [data-testid="stLayoutWrapper"]:has(> .st-key-pgnav) {margin-bottom:-6px !important; margin-top:0 !important; height:0 !important; min-height:0 !important;}
[data-testid="stMarkdownContainer"] p {margin:0 !important;}
/* header */
.hdr {margin:0 -.6rem; height:var(--hdr); background:#fff; color:§NAVY; display:flex; align-items:center; gap:10px; padding:0 .6rem; border-bottom:3px solid §ORANGE; box-sizing:border-box; box-shadow:0 1px 6px rgba(11,42,74,.10);}
.hdr .lg {height:44px;flex:none;background:transparent;padding:0;display:flex;align-items:center;color:§NAVY;font-weight:800;font-size:9px;text-align:center;line-height:1.1;}
.hdr .lg img {height:44px;width:auto;display:block;}
.hdr .lg + .lg {margin-left:14px;}
.hdr .ttl {flex:1; text-align:center; min-width:0;}
.hdr h1 {font-size:18px; margin:0; padding:0; font-weight:700; color:§NAVY; line-height:1.15; letter-spacing:.2px;}
.hdr .sub {font-size:11px; color:#5b6b7f; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.hdr .bx {flex:none; border:1px solid #d3dde9; border-radius:8px; padding:3px 12px; font-size:11px; line-height:1.25; text-align:center; color:#41546b; background:#f4f7fb;}
.hdr .bx b {color:§NAVY; font-size:12px;}
.hdr .pg {width:150px; height:38px; box-sizing:border-box; position:relative;}
.hdr .pgl {position:absolute; top:2px; left:0; right:0; font-size:9.5px; text-transform:uppercase; letter-spacing:.6px; color:#5b6b7f;}
[data-testid="stMainBlockContainer"] {position:relative !important;}
.hdr .pgl {display:none !important;}
.st-key-pgnav {position:absolute !important; top:14px; right:calc(.6rem + 225px); width:140px; z-index:999990; height:26px; gap:0 !important;}
.st-key-pgnav [data-testid="stSelectbox"] > div, .st-key-pgnav [data-testid="stSelectbox"] div[role="group"], .st-key-pgnav [data-baseweb="select"] > div {min-height:26px !important; height:26px !important; background:§NAVY !important; border-color:§NAVY !important; border-radius:6px !important;}
.st-key-pgnav input, .st-key-pgnav button, .st-key-pgnav [data-baseweb="select"] div, .st-key-pgnav [data-baseweb="select"] span {height:24px !important; min-height:0 !important; font-size:12px !important; font-weight:600 !important; color:#fff !important; -webkit-text-fill-color:#fff !important; background:transparent !important; text-align:center; line-height:24px !important; padding-top:0 !important; padding-bottom:0 !important;}
.st-key-pgnav input {text-align:center !important; padding-left:22px !important; caret-color:transparent; cursor:pointer;}
.st-key-pgnav svg {width:14px !important; height:14px !important; fill:#fff !important; color:#fff !important;}
.blank {height:calc(var(--flt) + var(--kpi) + var(--M) + 2*var(--gap) - 16px); border:2px dashed #b9c7d8; border-radius:10px; display:grid; place-items:center; text-align:center; background:rgba(255,255,255,.4);}
.blank .bt {font-size:20px; font-weight:700; color:§NAVY;} .blank .bs {font-size:12px; color:#5b6b7f; margin-top:4px;} .hdr .idn {width:210px;}
/* filter */
.st-key-filt {position:sticky; top:0; z-index:30; height:var(--flt); background:§NAVY; border:1px solid #0b2a4a; border-radius:10px; padding:4px 12px !important; box-sizing:border-box; overflow:hidden; justify-content:center;}
.st-key-filt [data-testid="stHorizontalBlock"] {align-items:flex-start;}
.st-key-filt [data-testid="stColumn"]:nth-child(n+5) {padding-top:16px;}
/* filter bergaya gelap */
.st-key-filt label p, .st-key-filt [data-testid="stWidgetLabel"] p, .st-key-filt label {color:#b9cde3 !important;}
.st-key-filt [data-baseweb="select"] > div, .st-key-filt div[role="group"], .st-key-filt [data-baseweb="input"], .st-key-filt [data-baseweb="base-input"], .st-key-filt [data-testid="stDateInput"] > div > div, .st-key-filt [data-testid="stDateInputField"] {background:#15395f !important; border-color:rgba(255,255,255,.22) !important; color:#fff !important;}
.st-key-filt input, .st-key-filt [data-baseweb="select"] div, .st-key-filt [data-baseweb="select"] span, .st-key-filt div[role="combobox"] {color:#fff !important; -webkit-text-fill-color:#fff !important;}
.st-key-filt svg {fill:#fff !important; color:#fff !important;}
.st-key-filt .stButton button, .st-key-filt [data-testid="stPopover"] > button, .st-key-filt [data-testid="stPopoverButton"], .st-key-filt button {background:transparent !important; color:#fff !important; border:1px solid rgba(255,255,255,.55) !important;}
.st-key-filt button *, .st-key-filt [data-testid="stDateInput"] *, .st-key-filt [data-testid="stDateInputField"] * {color:#fff !important; -webkit-text-fill-color:#fff !important;}
.st-key-filt [data-testid="stWidgetLabel"], .st-key-filt [data-testid="stWidgetLabel"] * {color:#b9cde3 !important; -webkit-text-fill-color:#b9cde3 !important; font-weight:600 !important;}
.st-key-filt [data-baseweb="select"] button, .st-key-filt div[role="group"] button {border:0 !important; background:transparent !important;}
.st-key-filt .stButton button:hover, .st-key-filt [data-testid="stPopover"] > button:hover, .st-key-filt button:hover {background:rgba(255,255,255,.12) !important;}
[data-testid="stSelectbox"] *, [data-testid="stDateInput"] * {font-size:12px !important;}
[data-testid="stWidgetLabel"] p {font-size:10.5px !important; color:#5b6b7f; text-transform:uppercase; letter-spacing:.4px; font-weight:600;}
[data-testid="stWidgetLabel"] {min-height:0 !important; margin:0 0 2px 0 !important; height:auto !important;}
div[data-baseweb="select"] {min-height:30px !important;}
div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="base-input"], [data-testid="stDateInputField"] {background:#fff !important; color:§INK !important; border-radius:6px !important; min-height:30px !important; height:30px !important;}
div[data-baseweb="select"] > div {border:1px solid #dde4ec !important;}
div[data-baseweb="select"] *, [data-testid="stDateInput"] input {font-size:12px !important; color:§INK;}
[data-testid="stDateInput"] input {height:28px !important; padding-top:0 !important; padding-bottom:0 !important;}
.stButton button, [data-testid="stPopover"] > button, [data-testid="stPopoverButton"] {height:30px !important; min-height:30px !important; padding:0 10px !important; background:#fff !important; color:§BLUE !important; border:1px solid §BLUE !important; border-radius:6px !important;}
.stButton button:hover, [data-testid="stPopover"] > button:hover {background:#dbe8f5 !important;}
.stButton button p, [data-testid="stPopover"] button p {color:§BLUE !important; font-size:12px !important;}
/* KPI */
.kpis {display:grid; grid-template-columns:repeat(5,1fr) 1.15fr; gap:var(--gap); height:var(--kpi);}
.kpi {background:#fff;border:1px solid #dde4ec;border-top:3px solid #c5d3e2;border-radius:10px;padding:4px 11px;min-width:0;overflow:hidden;box-sizing:border-box;box-shadow:0 1px 2px rgba(11,42,74,.06);font-variant-numeric:tabular-nums;}
.kpi.key {background:#f0f8f8;border-color:#bfe0e0;border-top-color:§TEAL;}
.kpi.key.hot {background:#fff6ec;border-color:#f3d4b0;border-top-color:§ORANGE;}
.kpi .l {font-size:11px;color:§INK2;font-weight:600;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.kpi .v {font-size:20px;font-weight:700;line-height:1.2;color:§INK;white-space:nowrap;}
.kpi.key .v {font-size:24px;line-height:1.1;}
.kpi .v small {font-size:12px;font-weight:600;color:§INK2;}
.kpi .s {font-size:11px;line-height:1.3;color:§INK2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.tp {border-bottom:1px dotted #5b6b7f; cursor:help;}
.kpi .l .tp {border-bottom:none;}
.pos {color:§ORANGE;} .neg {color:§BLUE;}
.chip {display:inline-block;font-size:10.5px;font-weight:700;padding:0 6px;border-radius:9px;vertical-align:middle;margin-left:4px;}
.chip.pos {background:#fdebd9;} .chip.neg {background:#dbe8f5;} .chip.obs {background:#e3eaf3;color:#0b2a4a;margin:0 4px 0 0;} .chip.sk {background:#d9eeee;color:#0a6a6c;}
/* seksi */
.st-key-main {height:var(--M);}
.st-key-secL, .st-key-secR {height:var(--M); border:0; padding:0 !important; box-sizing:border-box; overflow:hidden; background:transparent;}
.sec {height:24px; line-height:22px; font-size:13px; font-weight:700; color:§NAVY; text-align:left; padding-left:2px; letter-spacing:.3px; text-transform:uppercase;}
.sec span {font-weight:500; color:#5b6b7f; text-transform:none; letter-spacing:0; margin-left:8px; font-size:11px;}
.st-key-tsCard > *, .st-key-mapCard > *, .st-key-anCard > *, .st-key-fiCard > *, .st-key-evCard > * {flex-shrink:0 !important;}
.st-key-tsCard, .st-key-mapCard, .st-key-anCard, .st-key-fiCard, .st-key-evCard {background:#fff; border:1px solid #dde4ec; border-radius:10px; box-shadow:0 1px 2px rgba(11,42,74,.06); overflow:hidden; gap:0 !important; box-sizing:border-box;}
.st-key-tsCard {height:var(--Tt); flex:0 0 auto !important;}
.st-key-mapCard {height:var(--Rt); flex:0 0 auto !important;}
.st-key-anCard {height:var(--Rb); flex:0 0 auto !important;}
.st-key-fiCard, .st-key-evCard {height:var(--Tb); flex:0 0 auto !important;}
.st-key-tsHead [data-testid="stButtonGroup"] button, .st-key-tsHead [data-baseweb="button-group"] button {min-height:24px !important; height:26px !important; padding:0 10px !important;}
.st-key-tsHead [data-testid="stButtonGroup"] button p, .st-key-tsHead [data-testid="stButtonGroup"] button div, .st-key-tsHead label p {font-size:11px !important;}
.st-key-tsHead {height:30px; flex:0 0 auto !important;}
.st-key-tsHead button {background:§NAVY !important; border:1px solid §NAVY !important;}
.st-key-tsHead button p, .st-key-tsHead button div, .st-key-tsHead button span {color:#fff !important;}
.st-key-tsHead button[aria-checked="true"], .st-key-tsHead button[aria-pressed="true"], .st-key-tsHead button[data-testid="stBaseButton-segmented_controlActive"] {background:§BLUE !important; border-color:§BLUE !important;}
.st-key-tsHead label p {color:§NAVY !important;}
.st-key-tsHead [data-testid="stHorizontalBlock"] {align-items:center; padding-right:4px;}
.st-key-tsHead [data-testid="stHorizontalBlock"] > div:last-child {display:flex; justify-content:flex-end;}
.st-key-tsHead [data-testid="stHorizontalBlock"] > div:last-child > div {width:auto !important;}
.st-key-rowL {height:var(--Tb); flex:0 0 auto !important;}
.st-key-rowL [data-testid="stHorizontalBlock"] {height:var(--Tb);}
.st-key-rowL [data-testid="stColumn"] {height:var(--Tb);}
.st-key-mapHead {height:30px; flex:0 0 auto !important;}
.st-key-mapHead [data-testid="stHorizontalBlock"] {align-items:center; padding-right:8px;}
.ct {font-size:12px;font-weight:650;color:§NAVY;padding:6px 10px 0;height:28px;box-sizing:border-box;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.ct span {font-weight:500;color:#44566c;font-size:11px;margin-left:8px;background:#eef2f7;border-radius:10px;padding:1px 8px;}
.ins {font-size:11.5px;color:§INK2;padding:0 12px;height:20px;line-height:20px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums;} .ins b {color:§NAVY;}
.note {font-size:11px;line-height:1.3;color:#5b6b7f;padding:2px 10px 0;height:30px;overflow:hidden;}
table.ev {border-collapse:collapse;width:100%;font-size:11.5px;font-variant-numeric:tabular-nums;}
table.ev th {font-size:11px;text-transform:uppercase;color:#5b6b7f;font-weight:600;text-align:right;padding:2px 8px;border-bottom:1px solid #dde4ec;}
table.ev th:first-child, table.ev td:first-child {text-align:left;}
table.ev td {padding:3px 8px;text-align:right;border-bottom:1px solid #eef2f7;white-space:nowrap;color:§INK;}
table.ev tr.act td {background:#dbe8f5;font-weight:600;}
table.ev tr.base td {color:#5b6b7f;font-style:italic;}
table.ev td.min {color:§ORANGE;font-weight:700;}
.bar {display:inline-block;height:6px;background:§BLUE;border-radius:3px;vertical-align:middle;margin-right:5px;opacity:.6;}
.evw {padding:0 8px;}
.sumw {display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:6px 10px 0;height:58px;box-sizing:border-box;}
.sum {border-left:3px solid §BLUE;padding-left:7px;min-width:0;overflow:hidden;}
.sum .l {font-size:10.5px;color:#5b6b7f;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sum .v {font-size:13.5px;font-variant-numeric:tabular-nums;font-weight:700;color:§INK;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;}
.sum .s {font-size:11px;color:#44566c;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
/* footer */
.foot {height:var(--ftr); display:grid; grid-template-columns:auto 1fr; gap:var(--gap); box-sizing:border-box;}
.foot > div {background:#fff; border:1px solid #dde4ec; border-radius:8px; display:flex; align-items:center; padding:0 12px; font-size:11px; color:§INK2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; gap:8px;}
.foot .pill {background:§NAVY; color:#d7e4f2; padding:3px 10px; border-radius:12px; font-size:11px;}
.foot .dot {display:inline-block;width:7px;height:7px;border-radius:50%;background:#5ad18f;margin-right:6px;}
.foot .w {color:#8a4300;}
@media (max-height: 830px) {
  table.ev td {padding:1px 8px !important; font-size:11px !important;} table.ev th {padding:1px 8px !important;}
  .bar {height:5px;}
}
/* responsif */
@media (max-width: 1200px) {
  .kpis {grid-template-columns:repeat(3,1fr); height:auto;} .kpi {height:72px;}
  .st-key-filt {height:auto !important; min-height:var(--flt);}
}
@media (max-width: 900px) {
  .st-key-main, .st-key-secL, .st-key-secR, .st-key-rowL, .st-key-rowL [data-testid="stHorizontalBlock"] {height:auto !important;}
  .st-key-main [data-testid="stHorizontalBlock"] {flex-direction:column;}
  .st-key-main [data-testid="stColumn"] {width:100% !important; flex:1 1 auto !important; min-width:0 !important;}
  .st-key-rowL [data-testid="stColumn"] {height:var(--Tb);}
  .kpis {grid-template-columns:repeat(2,1fr);}
}
/* tinggi grafik */
§CHARTS
</style>
"""
_CHARTS = (_h("c_temp", "calc(var(--Tt) - 54px)") + _h("c_anom", "calc(var(--Rb) - 30px)") + _h("c_fi", "calc(var(--Tb) - 40px)")
           + _h("map_sel", "calc(var(--Rt) - 30px - 58px - 4px)") + _h("bars", "calc(var(--Rt) - 30px - 58px - 4px)"))
CSS = CSS.replace("/* responsif */", "\n".join(l.replace(".st-key-filt", ".st-key-filt2") for l in CSS.splitlines() if l.startswith(".st-key-filt") and "nth-child(n+5)" not in l) + "\n/* responsif */")
CSS = CSS.replace("/* responsif */", """.st-key-ukuran_layar {position:absolute !important; width:0 !important; height:0 !important; overflow:hidden !important; margin:0 !important;}
.st-key-filt2 [data-testid="stSlider"] div[role="group"] {background:transparent !important; border:0 !important;}
.st-key-filt2 [data-testid="stSliderThumbValue"], .st-key-filt2 [data-testid="stSliderThumbValue"] * {color:#fff !important; -webkit-text-fill-color:#fff !important; font-weight:600;}
.st-key-filt2 [data-testid="stSliderTickBar"], .st-key-filt2 [data-testid="stSliderTickBar"] * {color:#b9cde3 !important;}
/* responsif */""")
CSS = CSS.replace("  .st-key-filt {height:auto !important; min-height:var(--flt);}", "  .st-key-filt, .st-key-filt2 {height:auto !important; min-height:var(--flt);}")
for _k, _v in {"§NAVY": NAVY, "§BLUE": BLUE, "§ORANGE": ORANGE, "§INK2": INK2, "§INK": INK, "§TEAL": TEAL, "§CHARTS": _CHARTS}.items():
    CSS = CSS.replace(_k, _v)


# ------------------------------------------------------------------ logo header
def logo(fn, txt):
    """Logo dari assets/<fn>.(png|jpg|jpeg|webp); bila tidak ada, tampil teks pengganti."""
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = os.path.join(HERE, "assets", f"{fn}.{ext}")
        if os.path.exists(p):
            with open(p, "rb") as f:
                return f'<div class="lg"><img src="data:image/{ext};base64,{base64.b64encode(f.read()).decode()}"></div>'
    return f'<div class="lg">{txt}</div>'


def header_html(title, sub, nama, unit):
    """Header seragam semua halaman: logo BMKG + IPB, judul, kotak halaman, identitas pemilik halaman."""
    return (f'''<div class="hdr">{logo("logo_bmkg", "logo<br>BMKG")}{logo("logo_ipb", "logo<br>IPB")}
<div class="ttl"><h1>{title}</h1>
<div class="sub">{sub}</div></div>
<div class="bx pg"><span class="pgl">Halaman</span></div><div class="bx idn"><b>{nama}</b><br>{unit}</div></div>''')


# ------------------------------------------------------------------ tombol layar penuh (untuk bilah filter gelap)
_FS = """<style>html,body{margin:0;background:transparent;overflow:hidden}body{font-family:"Poppins","Segoe UI",Arial,sans-serif}button{width:100%;height:__H__px;border:1px solid rgba(255,255,255,.55);border-radius:8px;background:transparent;color:#fff;font:inherit;font-size:12px;cursor:pointer}button:hover{background:rgba(255,255,255,.12)}</style>
<button id="b" onclick="go()">⛶ Layar penuh</button>
<script>function go(){var b=document.getElementById('b'),f=function(){b.textContent='Tekan F11';};try{var d=window.parent.document; if(d.fullscreenElement){d.exitFullscreen();}else{var p=d.documentElement.requestFullscreen(); if(p&&p.catch){p.catch(f);}}}catch(e){f();}}</script>"""


def fullscreen_btn(h=30):
    html = _FS.replace("__H__", str(h))
    if hasattr(st, "iframe"):
        st.iframe(html, height=h + 2)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=h + 2)

