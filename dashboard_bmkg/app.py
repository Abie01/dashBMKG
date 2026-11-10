"""Dashboard Forecast Suhu Udara Pulau Jawa (Streamlit, 1 layar).

Jalankan : streamlit run app.py
Data     : folder data_dashboard/ di sebelah file ini (hasil ekspor notebook, Bagian 10).
Peta     : opsional, data_dashboard/provinsi_jawa.geojson (kolom properti 'provinsi').
"""
import json
import os
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Dashboard Forecast Suhu Jawa", layout="wide", initial_sidebar_state="collapsed")

# ------------------------------------------------------------------ konstanta
NAVY, BLUE, ORANGE = "#0b2a4a", "#1f6fb5", "#e8710a"
BLUE_LINE, GRID, INK, INK2, ZERO = "#9db4cc", "#e6ebf1", "#10243b", "#4a5b70", "#8793a3"
BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
NINO_ASUMSI = 1.90  # asumsi Niño 3.4 pada forecast (sesuai notebook)
ALGO_NAME = {"XGB": "XGBoost", "HGB": "HistGradientBoosting"}
PROV_LABEL = {"Jakarta": "DKI Jakarta"}
MODELS = [("Pooled", "XGBoost"), ("Pooled", "HistGradientBoosting"), ("Per-provinsi", "XGBoost"),
          ("Per-provinsi", "HistGradientBoosting"), ("Baseline", "Persistence"), ("Baseline", "Seasonal naive")]
ERA5_VARS = {"t2m": "suhu udara 2 m", "sp": "tekanan permukaan", "strd": "radiasi gelombang panjang turun di permukaan",
             "slhf": "fluks panas laten permukaan", "swvl1": "kadar air tanah lapisan 1", "sshf": "fluks panas sensibel permukaan",
             "ssrd": "radiasi gelombang pendek turun di permukaan", "tcwv": "total uap air kolom", "tcc": "tutupan awan total",
             "tp": "curah hujan total", "msl": "tekanan muka laut", "u10": "angin zonal 10 m", "v10": "angin meridional 10 m",
             "d2m": "suhu titik embun 2 m", "sst": "suhu permukaan laut", "nino34": "indeks Niño 3.4"}
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DASHBOARD_DATA", os.path.join(HERE, "data_dashboard"))


def pl(p):
    return PROV_LABEL.get(p, p)


def fmt(x, d=2, sign=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    s = f"{x:+,.{d}f}" if sign else f"{x:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".").replace("-", "−")


def mon_label(ts):
    ts = pd.Timestamp(ts)
    return f"{BLN[ts.month - 1]} {ts.year}"


# ------------------------------------------------------------------ gaya (layout mengikuti desain Canva, 1 layar)
def _h(key, expr):
    sel = ", ".join(f'.st-key-{key}{x}' for x in ("", ' [data-testid="stPlotlyChart"]', " .js-plotly-plot", " .plot-container", " .svg-container", " .main-svg"))
    return f".st-key-{key}{{flex:0 0 auto !important;}} {sel} {{height:{expr} !important;}}\n"


_CSS = """
<style>
:root{--hdr:56px; --flt:68px; --kpi:80px; --ftr:32px; --gap:8px;
  --M:max(440px, calc(100vh - var(--hdr) - var(--flt) - var(--kpi) - var(--ftr) - 5*var(--gap) - 8px));
  --A:calc(var(--M) - 52px); --Tt:calc(var(--A)*.555); --Tb:calc(var(--A)*.445);}
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu {display:none !important;}
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {background:#eef2f7 !important; color:§INK; color-scheme:light; font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;}
html, body, [data-testid="stAppViewContainer"] {overflow-x:hidden !important;}
[data-testid="stMain"] {overflow-y:auto !important;}
.block-container {padding:0 .6rem 0 .6rem !important; max-width:100% !important;}
[data-testid="stVerticalBlock"] {gap:var(--gap) !important;}
[data-testid="stHorizontalBlock"] {gap:var(--gap) !important;}
div[data-testid="stElementContainer"] {margin:0 !important; flex-shrink:0 !important;}
.st-key-main, .st-key-filt, .st-key-secL, .st-key-secR, .st-key-rowL {flex-shrink:0 !important;}
[data-testid="stMarkdown"], [data-testid="stMarkdownContainer"] {margin:0 !important;}
[data-testid="stMarkdownContainer"] p {margin:0 !important;}
/* header */
.hdr {margin:0 -.6rem; height:var(--hdr); background:§NAVY; color:#fff; display:flex; align-items:center; gap:10px; padding:0 .6rem; border-bottom:3px solid §ORANGE; box-sizing:border-box;}
.hdr .lg {width:40px;height:40px;flex:none;border-radius:8px;background:#fff;color:§NAVY;display:grid;place-items:center;font-weight:800;font-size:9px;text-align:center;line-height:1.1;overflow:hidden;}
.hdr .lg img {width:100%;height:100%;object-fit:contain;}
.hdr .ttl {flex:1; text-align:center; min-width:0;}
.hdr h1 {font-size:18px; margin:0; padding:0; font-weight:700; color:#fff; line-height:1.15; letter-spacing:.2px;}
.hdr .sub {font-size:10.5px; color:#b9cde3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.hdr .bx {flex:none; border:1px solid rgba(255,255,255,.35); border-radius:8px; padding:3px 12px; font-size:11px; line-height:1.25; text-align:center; color:#e4eef8; background:rgba(255,255,255,.08);}
.hdr .bx b {color:#fff; font-size:12px;}
.hdr .pg {width:150px;} .hdr .idn {width:210px;}
/* filter */
.st-key-filt {height:var(--flt); background:#fff; border:1px solid #dde4ec; border-radius:8px; padding:4px 12px !important; box-sizing:border-box; overflow:hidden; justify-content:center;}
.st-key-filt [data-testid="stHorizontalBlock"] {align-items:flex-start;}
.st-key-filt [data-testid="stColumn"]:nth-child(n+5) {padding-top:16px;}
[data-testid="stSelectbox"] *, [data-testid="stDateInput"] * {font-size:12px !important;}
[data-testid="stWidgetLabel"] p {font-size:10px !important; color:#7a8a9d; text-transform:uppercase; letter-spacing:.4px; font-weight:600;}
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
.kpi {background:#fff;border:1px solid #dde4ec;border-top:3px solid §BLUE;border-radius:8px;padding:5px 11px;min-width:0;overflow:hidden;box-sizing:border-box;}
.kpi.acc {border-top-color:§ORANGE;}
.kpi .l {font-size:10.5px;color:§INK2;font-weight:600;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.kpi .v {font-size:21px;font-weight:700;line-height:1.2;color:§INK;white-space:nowrap;}
.kpi .v small {font-size:12px;font-weight:600;color:§INK2;}
.kpi .s {font-size:10.5px;color:§INK2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pos {color:§ORANGE;} .neg {color:§BLUE;}
.chip {display:inline-block;font-size:10px;font-weight:700;padding:0 6px;border-radius:9px;vertical-align:middle;margin-left:4px;}
.chip.pos {background:#fdebd9;} .chip.neg {background:#dbe8f5;}
/* seksi */
.st-key-main {height:var(--M);}
.st-key-secL, .st-key-secR {height:var(--M); border:1px solid #cdd8e4; border-radius:10px; padding:6px 8px !important; box-sizing:border-box; overflow:hidden; background:rgba(255,255,255,.45);}
.sec {height:24px; line-height:20px; font-size:12.5px; font-weight:700; color:§NAVY; text-align:center; letter-spacing:.3px; text-transform:uppercase;}
.sec span {font-weight:500; color:#7a8a9d; text-transform:none; letter-spacing:0; margin-left:6px; font-size:10.5px;}
.st-key-tsCard > *, .st-key-mapCard > *, .st-key-anCard > *, .st-key-fiCard > *, .st-key-evCard > * {flex-shrink:0 !important;}
.st-key-tsCard, .st-key-mapCard, .st-key-anCard, .st-key-fiCard, .st-key-evCard {background:#fff; border:1px solid #dde4ec; border-radius:8px; overflow:hidden; gap:0 !important; box-sizing:border-box;}
.st-key-tsCard, .st-key-mapCard {height:var(--Tt); flex:0 0 auto !important;}
.st-key-anCard, .st-key-fiCard, .st-key-evCard {height:var(--Tb); flex:0 0 auto !important;}
.st-key-rowL {height:var(--Tb); flex:0 0 auto !important;}
.st-key-rowL [data-testid="stHorizontalBlock"] {height:var(--Tb);}
.st-key-rowL [data-testid="stColumn"] {height:var(--Tb);}
.st-key-mapHead {height:30px; flex:0 0 auto !important;}
.st-key-mapHead [data-testid="stHorizontalBlock"] {align-items:center; padding-right:8px;}
.ct {font-size:12px;font-weight:650;color:§NAVY;padding:6px 10px 0;height:28px;box-sizing:border-box;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.ct span {font-weight:500;color:#7a8a9d;font-size:10.5px;margin-left:6px;}
.note {font-size:10px;color:#7a8a9d;padding:2px 10px 0;height:18px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;}
table.ev {border-collapse:collapse;width:100%;font-size:11px;}
table.ev th {font-size:10px;text-transform:uppercase;color:#7a8a9d;font-weight:600;text-align:right;padding:2px 8px;border-bottom:1px solid #dde4ec;}
table.ev th:first-child, table.ev td:first-child {text-align:left;}
table.ev td {padding:3px 8px;text-align:right;border-bottom:1px solid #eef2f7;white-space:nowrap;color:§INK;}
table.ev tr.act td {background:#dbe8f5;font-weight:600;}
table.ev tr.base td:first-child {color:§INK2;}
table.ev td.min {color:§ORANGE;font-weight:700;}
.bar {display:inline-block;height:6px;background:§BLUE;border-radius:3px;vertical-align:middle;margin-right:5px;opacity:.6;}
.evw {padding:0 8px;}
.sumw {display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:6px 10px 0;height:58px;box-sizing:border-box;}
.sum {border-left:3px solid §ORANGE;padding-left:7px;min-width:0;overflow:hidden;}
.sum .l {font-size:9.5px;color:#7a8a9d;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sum .v {font-size:12.5px;font-weight:700;color:§INK;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
/* footer */
.foot {height:var(--ftr); display:grid; grid-template-columns:auto 1fr; gap:var(--gap); box-sizing:border-box;}
.foot > div {background:#fff; border:1px solid #dde4ec; border-radius:8px; display:flex; align-items:center; padding:0 12px; font-size:10.5px; color:§INK2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; gap:8px;}
.foot .pill {background:§NAVY; color:#d7e4f2; padding:3px 10px; border-radius:12px; font-size:10.5px;}
.foot .dot {display:inline-block;width:7px;height:7px;border-radius:50%;background:#5ad18f;margin-right:6px;}
.foot .w {color:#8a4300;}
/* tinggi grafik */
§CHARTS
</style>
"""
_CHARTS = (_h("c_temp", "calc(var(--Tt) - 30px)") + _h("c_anom", "calc(var(--Tb) - 30px)") + _h("c_fi", "calc(var(--Tb) - 56px)")
           + _h("map_sel", "calc(var(--Tt) - 30px - 58px - 4px)") + _h("bars", "calc(var(--Tt) - 30px - 58px - 4px)"))
for _k, _v in {"§NAVY": NAVY, "§BLUE": BLUE, "§ORANGE": ORANGE, "§INK2": INK2, "§INK": INK, "§CHARTS": _CHARTS}.items():
    _CSS = _CSS.replace(_k, _v)
st.markdown(_CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner=False)
def load(folder):
    def rd(name, dates=()):
        return pd.read_csv(os.path.join(folder, name + ".csv"), encoding="utf-8-sig", parse_dates=list(dates))

    D = dict(obs=rd("t2m_bulanan", ["tanggal"]), fc=rd("forecast", ["tanggal_target"]), met=rd("metrik"),
             imp=rd("importance"), nino=rd("nino34", ["tanggal"]))
    D["imp"]["model"] = D["imp"]["model"].astype(str).str.replace(r"\s*tuned\s*", "", regex=True).str.strip()
    for n, k in (("ringkasan_anomali", "ring"), ("normal_bulanan", "norm")):
        p = os.path.join(folder, n + ".csv")
        D[k] = pd.read_csv(p, encoding="utf-8-sig") if os.path.exists(p) else None
    gp = os.path.join(folder, "provinsi_jawa.geojson")
    D["geo"] = json.load(open(gp, encoding="utf-8")) if os.path.exists(gp) else None
    return D


try:
    D = load(DATA_DIR)
except FileNotFoundError as e:
    st.error(f"File data tidak ditemukan: {e}. Pastikan folder 'data_dashboard' ada di sebelah app.py.")
    st.stop()

obs, fc_all, met, imp, nino = D["obs"], D["fc"], D["met"], D["imp"], D["nino"]
PROVS = sorted(obs["provinsi"].unique())
norm_period = str(D["norm"]["periode_normal"].iloc[0]).replace("-", "–") if D["norm"] is not None else "1995–2024"
level = int(fc_all["level_interval_%"].iloc[0]) if "level_interval_%" in fc_all.columns else 95
nat_obs = (obs.groupby("tanggal")[["t2m", "normal", "anomali"]].mean().reset_index()
           .merge(obs.groupby("tanggal").size().rename("n").reset_index(), on="tanggal"))
nat_obs = nat_obs[nat_obs["n"] == len(PROVS)].sort_values("tanggal").reset_index(drop=True)
last_obs, first_obs = nat_obs["tanggal"].iloc[-1], nat_obs["tanggal"].iloc[0]
fc_dates = sorted(fc_all["tanggal_target"].unique())
fc_start, fc_end = pd.Timestamp(fc_dates[0]), pd.Timestamp(fc_dates[-1])

# ------------------------------------------------------------------ state + klik peta
SS = st.session_state
DEFAULTS = {"prov": "ALL", "algo": "XGB", "src": "Pooled",
            "rng": (max(first_obs, last_obs - pd.DateOffset(years=5) + pd.DateOffset(months=0)).date(), fc_end.date())}
for k, v in DEFAULTS.items():
    SS.setdefault(k, v)

ms = (SS.get("map_sel") or {}).get("selection", {}).get("points", []) if isinstance(SS.get("map_sel"), dict) else []
sig = tuple((p.get("curve_number"), p.get("point_index")) for p in ms)
if sig != SS.get("_map_sig"):
    SS["_map_sig"] = sig
    if ms:
        cd = ms[0].get("customdata")
        clicked = cd[0] if isinstance(cd, (list, tuple)) else cd
        if clicked in PROVS:
            SS["prov"] = "ALL" if SS["prov"] == clicked else clicked


def reset_all():
    for k, v in DEFAULTS.items():
        SS[k] = v


# ------------------------------------------------------------------ header (identitas bisa diubah di sini)
NAMA_SAYA = "Nama Anda"
UNIT_SAYA = "Magang BMKG · IPB"


def _logo(fn, txt):
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", f"{fn}.{ext}")
        if os.path.exists(p):
            import base64
            return f'<div class="lg"><img src="data:image/{ext};base64,{base64.b64encode(open(p, "rb").read()).decode()}"></div>'
    return f'<div class="lg">{txt}</div>'


st.markdown(
    f"""<div class="hdr">{_logo("logo_bmkg", "logo<br>BMKG")}{_logo("logo_ipb", "logo<br>IPB")}
<div class="ttl"><h1>Dashboard Forecast Suhu Udara Pulau Jawa</h1>
<div class="sub">Pemantauan t2m, anomali, dan performa model ML untuk 6 provinsi, ERA5 + Niño 3.4</div></div>
<div class="bx pg">Halaman<br><b>1 / 1</b></div><div class="bx idn"><b>{NAMA_SAYA}</b><br>{UNIT_SAYA}</div></div>""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ filter
filt = st.container(key="filt")
c1, c2, c3, c4, c5, c6 = filt.columns([1.2, 1.2, 1, 1.5, .55, .6])
prov = c1.selectbox("Provinsi", ["ALL"] + PROVS, key="prov", format_func=lambda p: "Semua Provinsi" if p == "ALL" else pl(p))
algo = c2.selectbox("Model", ["XGB", "HGB"], key="algo", format_func=lambda a: ALGO_NAME[a])
src = c3.selectbox("Pendekatan", ["Pooled", "Per-provinsi"], key="src")
rng = c4.date_input("Rentang waktu", key="rng", min_value=first_obs.date(), max_value=fc_end.date(), format="DD/MM/YYYY")
c5.button("Reset", on_click=reset_all, use_container_width=True)
with c6.popover("ⓘ Catatan", use_container_width=True):
    st.markdown(
        f"""**Catatan metode dan batasan**
- **Sumber dan periode.** ERA5 dan indeks Niño 3.4, 6 provinsi di Pulau Jawa. Observasi {mon_label(first_obs)} – {mon_label(last_obs)}; normal klimatologis {norm_period}; forecast {mon_label(fc_start)} – {mon_label(fc_end)}, 1 bulan ke depan (input bulan t, target t+1).
- **Forecast.** Eksperimental dan bersyarat pada asumsi Niño 3.4 = {fmt(NINO_ASUMSI)} dengan variabel pendukung klimatologis. Bukan skenario ENSO dinamis dan bukan produk operasional BMKG.
- **Interval {level}%.** Kuantil empiris dari 12 residual uji, lebarnya konstan, kemungkinan terlalu sempit. Pada "Semua Provinsi" interval adalah rata-rata batas antarprovinsi (aproksimasi).
- **Anomali.** Suhu observasi/prediksi dikurangi normal bulanan ({norm_period}). Berbeda dari error prediksi (prediksi − aktual).
- **KPI nasional.** Rata-rata tak berbobot 6 provinsi di Pulau Jawa, bukan seluruh Indonesia.
- **Evaluasi.** Hasil final test 12 bulan, tanpa cross-validation. Selisih antarmodel sering kecil; jangan dibaca sebagai keunggulan pasti.
- **Feature Importance.** Kenaikan RMSE ketika fitur diacak. Kontribusi prediktif relatif, bukan hubungan sebab-akibat."""
    )

if isinstance(rng, (tuple, list)) and len(rng) == 2:
    d0, d1 = pd.Timestamp(rng[0]).to_period("M").to_timestamp(), pd.Timestamp(rng[1]).to_period("M").to_timestamp("M")
else:
    d0, d1 = pd.Timestamp(DEFAULTS["rng"][0]), pd.Timestamp(DEFAULTS["rng"][1])


# ------------------------------------------------------------------ turunan
def obs_for(p):
    if p == "ALL":
        return nat_obs.drop(columns=["n"]).rename(columns={"tanggal": "d", "t2m": "t", "normal": "n", "anomali": "a"})[["d", "t", "n", "a"]]
    g = obs[obs["provinsi"] == p].sort_values("tanggal")
    return g.rename(columns={"tanggal": "d", "t2m": "t", "normal": "n", "anomali": "a"})[["d", "t", "n", "a"]].reset_index(drop=True)


def fc_for(p):
    g = fc_all[(fc_all["sumber"] == src) & (fc_all["algoritma"] == algo)]
    if p != "ALL":
        g = g[g["provinsi"] == p]
    g = g.groupby("tanggal_target")[["prediksi", "batas_bawah", "batas_atas", "normal", "anomali", "anomali_bawah", "anomali_atas"]].mean().reset_index()
    return g.rename(columns={"tanggal_target": "d", "prediksi": "p", "batas_bawah": "lo", "batas_atas": "hi", "normal": "n",
                             "anomali": "a", "anomali_bawah": "alo", "anomali_atas": "ahi"}).sort_values("d").reset_index(drop=True)


def layout(fig, **kw):
    base = dict(separators=",.", font=dict(size=11, color=INK2, family="Segoe UI, Roboto, Arial, sans-serif"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=42, r=12, t=34, b=28), hoverlabel=dict(font_size=11, bgcolor="#fff", font_color=INK),
                legend=dict(orientation="h", x=0, y=1, yanchor="bottom", font=dict(size=10, color=INK2), tracegroupgap=0, itemwidth=30))
    base.update(kw)
    fig.update_layout(**base)
    return fig


def axes(fig, x=None, y=None):
    bx = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=10))
    by = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=10))
    bx.update(x or {})
    by.update(y or {})
    fig.update_xaxes(**bx)
    fig.update_yaxes(**by)


def divider(fig):
    b = pd.Timestamp(last_obs) + pd.Timedelta(days=15)
    fig.add_vrect(x0=b, x1=pd.Timestamp("2100-01-01"), fillcolor="rgba(232,113,10,.05)", line_width=0, layer="below")
    fig.add_vline(x=b, line=dict(color=ORANGE, width=1, dash="dot"))
    fig.add_annotation(x=b, xref="x", y=1, yref="paper", text="Forecast →", showarrow=False, xanchor="left", yanchor="top",
                       xshift=4, font=dict(size=10, color=ORANGE))


def plot(fig, key=None, **kw):
    cfg = dict(displaylogo=False, displayModeBar=False)
    try:
        return st.plotly_chart(fig, width="stretch", config=cfg, key=key, **kw)
    except TypeError:
        return st.plotly_chart(fig, use_container_width=True, config=cfg, key=key, **kw)


def fig_temp():
    o = obs_for(prov)
    o = o[(o["d"] >= d0) & (o["d"] <= d1)]
    f = fc_for(prov)
    f = f[(f["d"] >= d0) & (f["d"] <= d1)]
    allp = prov == "ALL"
    nm = "Rata-rata 6 provinsi" if allp else pl(prov)
    fig = go.Figure()
    fig.add_scatter(x=o["d"], y=o["t"], mode="lines", name=f"Observasi: {nm}", line=dict(color=NAVY, width=2.2),
                    hovertemplate=f"<b>{nm}</b><br>Observasi: %{{y:.2f}} °C<extra></extra>")
    fig.add_scatter(x=o["d"], y=o["n"], mode="lines", name=f"Normal {norm_period}", line=dict(color="#6b7a8d", width=1.4, dash="dash"),
                    hovertemplate="Normal: %{y:.2f} °C<extra></extra>")
    if len(f):
        fig.add_scatter(x=f["d"], y=f["hi"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip", legendgroup="ci")
        fig.add_scatter(x=f["d"], y=f["lo"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(232,113,10,.18)",
                        name=f"Interval {level}%", legendgroup="ci", hoverinfo="skip")
        fig.add_scatter(x=f["d"], y=f["p"], mode="lines+markers", name=f"Forecast: {nm}", line=dict(color=ORANGE, width=2, dash="dash"),
                        marker=dict(size=5, color=ORANGE), customdata=np.stack([f["lo"], f["hi"]], axis=-1),
                        hovertemplate=f"<b>{nm}</b><br>Forecast: %{{y:.2f}} °C<br>Interval {level}%: %{{customdata[0]:.2f}} – %{{customdata[1]:.2f}} °C<extra></extra>")
    divider(fig)
    layout(fig, hovermode="x unified")
    axes(fig, x=dict(range=[d0, d1]), y=dict(title=dict(text="°C", standoff=4)))
    return fig, nm


def fig_anom():
    o = obs_for(prov)
    o = o[(o["d"] >= d0) & (o["d"] <= d1)]
    f = fc_for(prov)
    f = f[(f["d"] >= d0) & (f["d"] <= d1)]
    nm = "Rata-rata 6 provinsi" if prov == "ALL" else pl(prov)
    fig = go.Figure()

    def bars(df, pos, name, hatch, leg=True):
        a = df[df["a"] >= 0] if pos else df[df["a"] < 0]
        col = ORANGE if pos else BLUE
        kw = dict(x=a["d"], y=a["a"], name=name, showlegend=leg, marker=dict(color=col), hovertemplate=f"<b>{nm}</b><br>Observasi: %{{y:+.2f}} °C<extra></extra>")
        if hatch:
            kw["marker"] = dict(color=col, pattern=dict(shape="/", bgcolor="#fff", fgcolor=col, size=5, solidity=.55), line=dict(color=col, width=1))
            kw["error_y"] = dict(type="data", symmetric=False, array=(a["ahi"] - a["a"]).values, arrayminus=(a["a"] - a["alo"]).values,
                                 color="#5d6b7c", thickness=1, width=2)
            kw["customdata"] = np.stack([a["alo"], a["ahi"]], axis=-1)
            kw["hovertemplate"] = (f"<b>{nm}</b><br>Forecast: %{{y:+.2f}} °C<br>Interval {level}%: "
                                   "%{customdata[0]:+.2f} – %{customdata[1]:+.2f} °C<extra></extra>")
        fig.add_bar(**kw)

    bars(o, True, "Obs. positif", False)
    bars(o, False, "Obs. negatif", False)
    bars(f, True, f"Forecast (± interval {level}%)", True)
    bars(f, False, "Forecast negatif", True, False)
    divider(fig)
    fig.add_hline(y=0, line=dict(color=ZERO, width=1))
    layout(fig, barmode="overlay", bargap=.15, hovermode="x unified")
    axes(fig, x=dict(range=[d0, d1]), y=dict(title=dict(text="°C", standoff=4)))
    return fig, nm


def describe(f):
    m = re.match(r"^(.+)_lag(\d+)$", f)
    if m:
        v = ERA5_VARS.get(m.group(1))
        return f"{v if v else 'variabel ' + m.group(1)} ({m.group(1)}), nilai {m.group(2)} bulan sebelum bulan input (lag {m.group(2)})."
    m = re.match(r"^(.+)_roll(\d+)_(mean|std)$", f)
    if m:
        v = ERA5_VARS.get(m.group(1))
        return f"{'Rata-rata' if m.group(3) == 'mean' else 'Simpangan baku'} bergulir {m.group(2)} bulan dari {v if v else 'variabel ' + m.group(1)} ({m.group(1)})."
    if f in ("month_sin", "month_cos"):
        return f"Komponen {'sinus' if f == 'month_sin' else 'kosinus'} dari bulan: penanda siklus musiman."
    return "Fitur model; lihat nama kolom pada notebook."


def fig_fi():
    r = imp[(imp["model"] == ALGO_NAME[algo]) & (imp["pendekatan"] == src)]
    if src == "Pooled":
        g = r[r["provinsi"].astype(str).str.contains("semua", case=False)]
        r, note = (g if len(g) else r), "Pooled: satu model untuk semua provinsi"
    elif prov != "ALL":
        r, note = r[r["provinsi"] == prov], pl(prov)
    else:
        r, note = r.groupby("fitur", as_index=False)["importance"].mean(), "rata-rata importance 6 model provinsi"
    r = r.sort_values("importance", ascending=False).head(10).iloc[::-1]
    fig = go.Figure(go.Bar(x=r["importance"], y=r["fitur"], orientation="h", marker_color=BLUE, text=[fmt(v, 3) for v in r["importance"]],
                           textposition="outside", cliponaxis=False, textfont=dict(size=10), customdata=[describe(f) for f in r["fitur"]],
                           hovertemplate="<b>%{y}</b><br>Importance: %{x:.4f}<br>%{customdata}<extra></extra>"))
    layout(fig, margin=dict(l=100, r=42, t=6, b=26), showlegend=False)
    axes(fig, x=dict(title=dict(text="Kenaikan RMSE bila fitur diacak (°C)", font=dict(size=10), standoff=2),
                     range=[0, (r["importance"].max() if len(r) else 1) * 1.22]),
         y=dict(automargin=True, gridcolor="rgba(0,0,0,0)", tickmode="array", tickvals=list(r["fitur"]), ticktext=list(r["fitur"])))
    return fig, note


# ---- ringkasan anomali + peta
def summary():
    if D["ring"] is not None:
        s = D["ring"][(D["ring"]["sumber"] == src) & (D["ring"]["algoritma"] == algo)]
        return pd.DataFrame({"prov": s["provinsi"], "mean": s["anomali_rata2"], "max": s["anomali_maks"], "peak": s["bulan_puncak"].astype(str),
                             "neg": s["jumlah_bulan_negatif"]})
    g = fc_all[(fc_all["sumber"] == src) & (fc_all["algoritma"] == algo)]
    rows = []
    for p, x in g.groupby("provinsi"):
        i = x["anomali"].idxmax()
        rows.append((p, x["anomali"].mean(), x["anomali"].max(), str(x.loc[i, "tanggal_target"])[:7], int((x["anomali"] < 0).sum())))
    return pd.DataFrame(rows, columns=["prov", "mean", "max", "peak", "neg"])


def centroid(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    best = max((p[0] for p in polys), key=lambda r: (max(q[0] for q in r) - min(q[0] for q in r)) * (max(q[1] for q in r) - min(q[1] for q in r)))
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(best[:-1], best[1:]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    a /= 2
    return (cx / (6 * a), cy / (6 * a)) if a else tuple(best[0])


def norm_name(s):
    s = re.sub(r"^dki\s+", "", str(s).lower())
    s = re.sub(r"^daerah istimewa\s+", "di ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return {"jakarta raya": "jakarta", "di yogyakarta": "yogyakarta"}.get(s, s)


@st.cache_data(show_spinner=False)
def prep_geo(geo, provs):
    want = {norm_name(p): p for p in provs}
    feats = []
    for f in geo["features"]:
        pr = f.get("properties", {}) or {}
        raw = pr.get("provinsi") or pr.get("NAME_1") or pr.get("Propinsi") or pr.get("PROVINSI") or pr.get("nama") or pr.get("name") or ""
        p = want.get(norm_name(raw))
        if p:
            g = f["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            xs, ys = [], []
            for poly in polys:
                for q in poly[0]:
                    xs.append(q[0])
                    ys.append(q[1])
                xs.append(None)
                ys.append(None)
            feats.append(dict(prov=p, x=xs, y=ys, c=centroid(g), pts=sample_points(g)))
    return feats


def inside(px, py, ring):
    x = np.array([q[0] for q in ring])
    y = np.array([q[1] for q in ring])
    res = np.zeros(px.shape, bool)
    j = len(x) - 1
    for i in range(len(x)):
        cond = ((y[i] > py) != (y[j] > py)) & (px < (x[j] - x[i]) * (py - y[i]) / (y[j] - y[i] + 1e-15) + x[i])
        res ^= cond
        j = i
    return res


def sample_points(g, step=0.14):
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    X, Y = [], []
    for poly in polys:
        r = poly[0]
        xs, ys = [q[0] for q in r], [q[1] for q in r]
        gx, gy = np.meshgrid(np.arange(min(xs), max(xs) + step, step), np.arange(min(ys), max(ys) + step, step))
        px, py = gx.ravel(), gy.ravel()
        m = inside(px, py, r)
        X += list(px[m])
        Y += list(py[m])
    return X, Y


def scale_rgb(v, m):
    t = max(0.0, min(1.0, (v + m) / (2 * m)))
    hx = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    B, W, O = hx(BLUE), [244, 244, 244], hx(ORANGE)
    a, b, u = (B, W, t / .5) if t < .5 else (W, O, (t - .5) / .5)
    return [round(a[i] + (b[i] - a[i]) * u) for i in range(3)]


def map_values(metric, s):
    if metric == "obs":
        return {p: dict(v=float(obs_for(p)["a"].iloc[-1]), t="Observasi " + mon_label(obs_for(p)["d"].iloc[-1])) for p in PROVS}
    if metric == "fc1":
        out = {}
        for p in PROVS:
            f = fc_for(p)
            if len(f):
                out[p] = dict(v=float(f["a"].iloc[0]), t="Forecast " + mon_label(f["d"].iloc[0]))
        return out
    return {r.prov: dict(v=float(r.mean), t="Forecast, rerata 12 bulan", mx=float(r.max), peak=r.peak, neg=int(r.neg)) for r in s.itertuples()}


def fig_map(s, metric):
    feats = prep_geo(D["geo"], tuple(PROVS))
    mv = map_values(metric, s)
    feats = [f for f in feats if f["prov"] in mv]
    m = max(0.1, max(abs(mv[f["prov"]]["v"]) for f in feats))
    fig = go.Figure()
    for f in feats:
        o = mv[f["prov"]]
        dim = prov != "ALL" and prov != f["prov"]
        rgb = scale_rgb(o["v"], m)
        hov = f"<b>{pl(f['prov'])}</b><br>{o['t']}: {fmt(o['v'], 2, True)} °C"
        if "mx" in o:
            pk = o["peak"]
            pk = mon_label(pk[:7] + "-01") if len(pk) >= 7 else pk
            hov += f"<br>Maks: {fmt(o['mx'], 2, True)} °C ({pk})<br>Bulan negatif: {o['neg']}"
        fig.add_scatter(x=f["x"], y=f["y"], mode="lines", fill="toself", fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{.18 if dim else 1})",
                        line=dict(color="#fff", width=1), hoveron="fills", hoverinfo="text", text=hov, showlegend=False)
    if prov != "ALL":
        for f in feats:
            if f["prov"] == prov:
                fig.add_scatter(x=f["x"], y=f["y"], mode="lines", line=dict(color=NAVY, width=1.2), hoverinfo="skip", showlegend=False)
    lbl = {"Jakarta": "DKI", "Yogyakarta": "DIY"}
    pos = {"Jakarta": "top right", "Banten": "bottom left"}
    def _lab(f):
        n = lbl.get(f["prov"], pl(f["prov"]))
        if prov != "ALL" and prov != f["prov"]:
            return n  # provinsi lain: angka disembunyikan, nama dipudarkan
        return f"{n}<br><b>{fmt(mv[f['prov']]['v'], 2, True)}</b>"
    fig.add_scatter(x=[f["c"][0] for f in feats], y=[f["c"][1] for f in feats], mode="text",
                    text=[_lab(f) for f in feats],
                    textposition=[pos.get(f["prov"], "middle center") for f in feats],
                    textfont=dict(size=[(11 if prov == f["prov"] else 9) for f in feats],
                                  color=["#b4bfcc" if (prov != "ALL" and prov != f["prov"]) else INK for f in feats]),
                    hoverinfo="skip", showlegend=False)
    # titik klik tak terlihat yang menutupi seluruh provinsi (untuk lintas-filter lewat klik)
    px = [v for f in feats for v in f["pts"][0]]
    py = [v for f in feats for v in f["pts"][1]]
    cd = [[f["prov"]] for f in feats for _ in f["pts"][0]]
    fig.add_scatter(x=px, y=py, mode="markers", customdata=cd, marker=dict(size=11, color="rgba(0,0,0,0.01)"),
                    selected=dict(marker=dict(opacity=.01)), unselected=dict(marker=dict(opacity=.01)), hoverinfo="none", showlegend=False)
    xs = [v for f in feats for v in f["x"] if v is not None]
    ys = [v for f in feats for v in f["y"] if v is not None]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    fig.add_scatter(x=[x0], y=[y0], mode="markers", hoverinfo="skip", showlegend=False,
                    marker=dict(size=.1, color=[0], cmin=-m, cmax=m, colorscale=[[0, BLUE], [.5, "#f4f4f4"], [1, ORANGE]], showscale=True,
                                colorbar=dict(thickness=8, len=.8, tickfont=dict(size=9), outlinewidth=0, tickformat="+.1f", x=1.0, xpad=0)))
    layout(fig, margin=dict(l=2, r=38, t=2, b=2), showlegend=False, hovermode="closest", dragmode=False,
           clickmode="event+select", xaxis=dict(visible=False, range=[x0 - (x1 - x0) * .03, x1 + (x1 - x0) * .03], constrain="domain", fixedrange=True),
           yaxis=dict(visible=False, range=[y0 - (y1 - y0) * .06, y1 + (y1 - y0) * .06], scaleanchor="x", scaleratio=1, constrain="domain", fixedrange=True))
    return fig


def fig_bars(s):
    s = s.sort_values("mean")
    fig = go.Figure(go.Bar(x=s["mean"], y=[pl(p) for p in s["prov"]], orientation="h",
                           marker=dict(color=[ORANGE if v >= 0 else BLUE for v in s["mean"]],
                                       opacity=[1 if prov in ("ALL", p) else .35 for p in s["prov"]]),
                           text=[fmt(v, 2, True) for v in s["mean"]], textposition="outside", cliponaxis=False, textfont=dict(size=10)))
    layout(fig, margin=dict(l=84, r=42, t=4, b=24), showlegend=False)
    axes(fig, x=dict(title=dict(text="Anomali rata-rata forecast (°C)", font=dict(size=10), standoff=2), zeroline=True, zerolinecolor=ZERO),
         y=dict(automargin=True, gridcolor="rgba(0,0,0,0)"))
    return fig


# ------------------------------------------------------------------ KPI
f_nat = fc_for("ALL")
f0, last, prev = f_nat.iloc[0], nat_obs.iloc[-1], nat_obs.iloc[-2]
ml = met[(met["provinsi"] == "Semua provinsi") & (met["pendekatan"] != "Baseline")].sort_values("RMSE")
best, second = ml.iloc[0], ml.iloc[1]
nn = nino.sort_values("tanggal").iloc[-1]
sg = lambda v: "pos" if v >= 0 else "neg"
chip = lambda v: f'<span class="chip {sg(v)}">{"Positif" if v >= 0 else "Negatif"}</span>'
dT = last["t2m"] - prev["t2m"]
cards = [
    ("", "Suhu aktual nasional", f'{fmt(last["t2m"])} <small>°C</small>', f'{mon_label(last["tanggal"])} · {"▲" if dT >= 0 else "▼"} {fmt(dT, 2, True)} °C vs {mon_label(prev["tanggal"])}'),
    ("acc", "Prediksi suhu nasional", f'{fmt(f0["p"])} <small>°C</small>', f'Target {mon_label(f0["d"])} · rerata 12 bln {fmt(f_nat["p"].mean())}'),
    ("", "Anomali suhu nasional", f'<span class="{sg(last["anomali"])}">{fmt(last["anomali"], 2, True)}</span> <small>°C</small>{chip(last["anomali"])}',
     f'{mon_label(last["tanggal"])} · normal {norm_period}'),
    ("acc", "Prediksi anomali nasional", f'<span class="{sg(f0["a"])}">{fmt(f0["a"], 2, True)}</span> <small>°C</small>{chip(f0["a"])}',
     f'{mon_label(f0["d"])} · {"▲" if f0["a"] > last["anomali"] else "▼"} dari anomali terakhir · 12 bln {fmt(f_nat["a"].mean(), 2, True)}'),
    ("", "Model terbaik (RMSE)", f'{fmt(best["RMSE"], 3)} <small>°C</small>',
     f'{best["pendekatan"]} · {str(best["model"]).replace("HistGradientBoosting", "HGB")} · Δ ke #2: {fmt(second["RMSE"] - best["RMSE"], 3)}'),
    ("acc", "Niño 3.4 dan fase ENSO", f'{fmt(nn["nino34"])} <small>°C · {nn["fase"]}</small>', f'{mon_label(nn["tanggal"])} · asumsi forecast: {fmt(NINO_ASUMSI)} (tetap)'),
]
st.markdown('<div class="kpis">' + "".join(f'<div class="kpi {c}"><div class="l">{l}</div><div class="v">{v}</div><div class="s">{s}</div></div>' for c, l, v, s in cards) + "</div>",
            unsafe_allow_html=True)

# ------------------------------------------------------------------ susunan utama (mengikuti desain Canva)
def eval_table():
    scope = "Semua provinsi" if prov == "ALL" else prov
    rows = []
    for pe, mo in MODELS:
        r = met[(met["pendekatan"] == pe) & (met["model"] == mo) & (met["provinsi"] == scope)]
        rows.append((pe, mo, r.iloc[0] if len(r) else None))
    ok = [x for x in rows if x[2] is not None]
    mn = {k: min(x[2][k] for x in ok) for k in ("RMSE", "MAE", "MAPE_%")}
    mx = max(x[2]["RMSE"] for x in ok)
    h = '<div class="evw"><table class="ev"><thead><tr><th>Model</th><th>RMSE (°C)</th><th>MAE (°C)</th><th>MAPE (%)</th></tr></thead><tbody>'
    for pe, mo, r in rows:
        nmz = mo + " (baseline)" if pe == "Baseline" else f'{pe} · {mo.replace("HistGradientBoosting", "HGB")}'
        if r is None:
            h += f'<tr><td>{nmz}</td><td colspan="3">n/a</td></tr>'
            continue
        act = pe == src and mo == ALGO_NAME[algo]
        cl = lambda k, d: f'<td class="{"min" if r[k] == mn[k] else ""}">{fmt(r[k], d)}{" ▼" if r[k] == mn[k] else ""}</td>'
        h += (f'<tr class="{"base" if pe == "Baseline" else ""} {"act" if act else ""}"><td>{nmz}</td>'
              f'<td class="{"min" if r["RMSE"] == mn["RMSE"] else ""}"><span class="bar" style="width:{r["RMSE"] / mx * 40:.0f}px"></span>{fmt(r["RMSE"], 3)}{" ▼" if r["RMSE"] == mn["RMSE"] else ""}</td>'
              f'{cl("MAE", 3)}{cl("MAPE_%", 2)}</tr>')
    h += "</tbody></table></div>"
    n = ok[0][2]["n"] if ok else None
    return h, scope, n


with st.container(key="main"):
    L, R = st.columns([1.56, 1])

    # ---------------- kiri: model
    with L.container(key="secL"):
        st.markdown('<div class="sec">Forecast dan Performa Model<span>observasi, prediksi, evaluasi</span></div>', unsafe_allow_html=True)
        with st.container(key="tsCard"):
            fg, nm = fig_temp()
            st.markdown(f'<div class="ct">Suhu udara 2 m, observasi dan forecast<span>{nm} · {ALGO_NAME[algo]} · {src}</span></div>', unsafe_allow_html=True)
            plot(fg, key="c_temp")
        with st.container(key="rowL"):
            a, b = st.columns(2)
            with a.container(key="fiCard"):
                fg, note = fig_fi()
                st.markdown(f'<div class="ct">Feature Importance, Top 10<span>{ALGO_NAME[algo]} · {src}</span></div>', unsafe_allow_html=True)
                plot(fg, key="c_fi")
                n_feat = int(imp[(imp["model"] == ALGO_NAME[algo]) & (imp["pendekatan"] == src)]["fitur"].nunique())
                st.markdown(f'<div class="note">Top 10 dari {n_feat} fitur · {note} · bukan bukti sebab-akibat</div>', unsafe_allow_html=True)
            with b.container(key="evCard"):
                h, scope, n = eval_table()
                st.markdown(f'<div class="ct">Evaluasi model, final test 12 bulan<span>{"semua provinsi" if prov == "ALL" else pl(prov)}</span></div>', unsafe_allow_html=True)
                st.markdown(h, unsafe_allow_html=True)
                st.markdown(f'<div class="note">{f"n = {int(n)} · " if n else ""}▼ = terendah · selisih antarmodel sering kecil</div>', unsafe_allow_html=True)

    # ---------------- kanan: anomali
    with R.container(key="secR"):
        st.markdown('<div class="sec">Anomali Suhu<span>sebaran spasial dan tren</span></div>', unsafe_allow_html=True)
        with st.container(key="mapCard"):
            s = summary()
            geo_ok = D["geo"] is not None and len(prep_geo(D["geo"], tuple(PROVS))) > 0
            with st.container(key="mapHead"):
                t1, t2 = st.columns([1, 1.25], vertical_alignment="center")
                t1.markdown('<div class="ct" style="padding-top:8px">Peta anomali per provinsi</div>', unsafe_allow_html=True)
                metric = "fc12"
                if geo_ok:
                    metric = t2.selectbox("Metrik peta", ["fc12", "fc1", "obs"], key="map_metric", label_visibility="collapsed",
                                          format_func=lambda m: {"fc12": "Forecast, rerata 12 bln", "fc1": "Forecast, bulan target 1", "obs": "Observasi terakhir"}[m])
            if geo_ok:
                plot(fig_map(s, metric), key="map_sel", on_select="rerun", selection_mode="points")
            else:
                plot(fig_bars(s), key="bars")
            sc = s if prov == "ALL" else s[s["prov"] == prov]
            top = s.loc[s["mean"].idxmax()]
            mxr = sc.loc[sc["max"].idxmax()]
            pk = str(mxr["peak"])
            pk = mon_label(pk[:7] + "-01") if len(pk) >= 7 else pk
            vals = [("Rerata anomali", fmt(sc["mean"].mean(), 2, True) + " °C"), ("Anomali maks", fmt(mxr["max"], 2, True) + " °C"),
                    ("Bulan puncak", pk + (f" ({pl(mxr['prov'])})" if prov == "ALL" else "")), ("Prov. tertinggi", f"{pl(top['prov'])} {fmt(top['mean'], 2, True)}")]
            st.markdown('<div class="sumw">' + "".join(f'<div class="sum"><div class="l">{l}</div><div class="v" title="{v}">{v}</div></div>' for l, v in vals) + "</div>",
                        unsafe_allow_html=True)
        with st.container(key="anCard"):
            fg, nm = fig_anom()
            st.markdown(f'<div class="ct">Anomali suhu, observasi dan forecast<span>{nm} · normal {norm_period}</span></div>', unsafe_allow_html=True)
            plot(fg, key="c_anom")

# ------------------------------------------------------------------ footer
st.markdown(
    f'<div class="foot"><div>Info data <span class="pill"><span class="dot"></span>Data terakhir: {mon_label(last_obs)} · Forecast s.d. {mon_label(fc_end)}</span></div>'
    f'<div><b>ERA5</b> · Normal {norm_period} · <span class="w">Eksperimental, bersyarat Niño 3.4 = {fmt(NINO_ASUMSI)}; bukan produk operasional BMKG</span> · Detail di tombol ⓘ Catatan</div></div>',
    unsafe_allow_html=True,
)
