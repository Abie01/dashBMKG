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
TEAL = "#0f8b8d"   # warna khusus forecast (oranye = anomali positif)
GLOSS = {
    "RMSE": "Root Mean Squared Error: akar rata-rata kuadrat selisih prediksi dan ERA5 (°C). Makin kecil makin baik; error besar dihukum lebih berat.",
    "MAE": "Mean Absolute Error: rata-rata selisih mutlak prediksi dan ERA5 (°C). Makin kecil makin baik.",
    "MAPE": "Mean Absolute Percentage Error: rata-rata selisih mutlak dalam persen dari nilai ERA5. Makin kecil makin baik.",
    "Pooled": "Satu model dilatih dengan data gabungan 6 provinsi.",
    "Per-provinsi": "Satu model terpisah untuk tiap provinsi.",
    "XGBoost": "XGBoost: algoritma gradient boosting berbasis pohon keputusan.",
    "HGB": "HistGradientBoosting: algoritma gradient boosting berbasis pohon keputusan (scikit-learn).",
    "Persistence": "Baseline sederhana: prediksi suhu bulan depan = suhu bulan ini. Model ML harus mengalahkan ini.",
    "Seasonal naive": "Baseline sederhana: prediksi = suhu bulan yang sama tahun lalu.",
    "Anomali": "Selisih suhu terhadap normal bulanan (rata-rata 30 tahun). Positif = lebih hangat dari normal. Berbeda dari error model.",
    "Lag": "Nilai variabel pada beberapa bulan sebelum bulan input (lag 1 = 1 bulan sebelumnya).",
    "ERA5": "Reanalisis ERA5 (ECMWF): gabungan model cuaca dan pengamatan; bukan pengamatan stasiun langsung.",
    "Importance": "Kenaikan RMSE saat sebuah fitur diacak. Menunjukkan seberapa dipakai model, bukan hubungan sebab-akibat.",
}


GLOSS["Niño34"] = ("Niño 3.4 bulan target adalah skenario dari plume IRI/CCSR, bukan observasi. Indeks konvensional "
                   "(basis 1991–2020) lebih tinggi daripada indeks relatif; samakan definisinya dengan data latih.")


def tip(txt, key=None):
    return f'<span class="tp" title="{GLOSS.get(key or txt, "").replace(chr(34), chr(39))}">{txt}</span>'


SHORT = {"t2m": "Suhu", "sp": "Tekanan permukaan", "msl": "Tekanan muka laut", "strd": "Radiasi gel. panjang", "ssrd": "Radiasi gel. pendek",
         "slhf": "Panas laten", "sshf": "Panas sensibel", "swvl1": "Kadar air tanah", "tcwv": "Uap air kolom", "tcc": "Tutupan awan",
         "tp": "Curah hujan", "u10": "Angin zonal", "v10": "Angin meridional", "d2m": "Suhu titik embun", "sst": "Suhu laut"}


def friendly(f):
    m = re.match(r"^(.+)_lag(\d+)$", f)
    if m:
        v, k = m.group(1), int(m.group(2))
        if v == "nino34":
            return "Niño 3.4, bulan input" if k == 0 else f"Niño 3.4, {k} bln lalu"
        return f"{SHORT.get(v, v)}, {k} bln lalu"
    m = re.match(r"^(.+)_roll(\d+)_(mean|std)$", f)
    if m:
        return f"{'Rerata' if m.group(3) == 'mean' else 'Variasi'} {m.group(2)} bln: {SHORT.get(m.group(1), m.group(1)).lower()}"
    if f == "month_sin":
        return "Musim (sinus bulan)"
    if f == "month_cos":
        return "Musim (kosinus bulan)"
    if f.startswith("prov_"):
        return "Provinsi: " + f[5:]
    if f.startswith("t2m_trend"):
        return f"Tren suhu {f[9:]} bln"
    return f


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
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
:root{--hdr:64px; --flt:80px; --kpi:94px; --ftr:32px; --gap:8px;
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
.hdr .lg {width:50px;height:50px;padding:3px;box-sizing:border-box;flex:none;border-radius:8px;background:transparent;color:§NAVY;display:grid;place-items:center;font-weight:800;font-size:9px;text-align:center;line-height:1.1;overflow:hidden;}
.hdr .lg img {width:100%;height:100%;object-fit:contain;}
.hdr .ttl {flex:1; text-align:center; min-width:0;}
.hdr h1 {font-size:20px; margin:0; padding:0; font-weight:700; color:§NAVY; line-height:1.15; letter-spacing:.2px;}
.hdr .sub {font-size:11.5px; color:#5b6b7f; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.hdr .bx {flex:none; border:1px solid #d3dde9; border-radius:8px; padding:3px 12px; font-size:11px; line-height:1.25; text-align:center; color:#41546b; background:#f4f7fb;}
.hdr .bx b {color:§NAVY; font-size:12px;}
.hdr .pg {width:150px; height:38px; box-sizing:border-box; position:relative;}
.hdr .pgl {position:absolute; top:2px; left:0; right:0; font-size:9.5px; text-transform:uppercase; letter-spacing:.6px; color:#7a8a9d;}
[data-testid="stMainBlockContainer"] {position:relative !important;}
.hdr .pgl {display:none !important;}
.st-key-pgnav {position:absolute !important; top:19px; right:calc(.6rem + 225px); width:140px; z-index:999990; height:26px; gap:0 !important;}
.st-key-pgnav [data-testid="stSelectbox"] > div, .st-key-pgnav [data-testid="stSelectbox"] div[role="group"], .st-key-pgnav [data-baseweb="select"] > div {min-height:26px !important; height:26px !important; background:§NAVY !important; border-color:§NAVY !important; border-radius:6px !important;}
.st-key-pgnav input, .st-key-pgnav button, .st-key-pgnav [data-baseweb="select"] div, .st-key-pgnav [data-baseweb="select"] span {height:24px !important; min-height:0 !important; font-size:12px !important; font-weight:600 !important; color:#fff !important; -webkit-text-fill-color:#fff !important; background:transparent !important; text-align:center; line-height:24px !important; padding-top:0 !important; padding-bottom:0 !important;}
.st-key-pgnav input {text-align:center !important; padding-left:22px !important; caret-color:transparent; cursor:pointer;}
.st-key-pgnav svg {width:14px !important; height:14px !important; fill:#fff !important; color:#fff !important;}
.blank {height:calc(var(--flt) + var(--kpi) + var(--M) + 2*var(--gap) - 16px); border:2px dashed #b9c7d8; border-radius:10px; display:grid; place-items:center; text-align:center; background:rgba(255,255,255,.4);}
.blank .bt {font-size:20px; font-weight:700; color:§NAVY;} .blank .bs {font-size:12px; color:#7a8a9d; margin-top:4px;} .hdr .idn {width:210px;}
/* filter */
.st-key-filt {height:var(--flt); background:#fff; border:1px solid #dde4ec; border-radius:8px; padding:4px 12px !important; box-sizing:border-box; overflow:hidden; justify-content:center;}
.st-key-filt [data-testid="stHorizontalBlock"] {align-items:flex-start;}
.st-key-filt [data-testid="stColumn"]:nth-child(n+5) {padding-top:16px;}
.st-key-filt [data-baseweb="select"] button, .st-key-filt div[role="group"] button {border:0 !important; background:transparent !important;}
[data-testid="stSelectbox"] *, [data-testid="stDateInput"] * {font-size:12px !important;}
[data-testid="stWidgetLabel"] p {font-size:11px !important; color:#5b6b7f; letter-spacing:0; font-weight:600;}
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
.kpi {background:#fff;border:1px solid #dde4ec;border-top:3px solid §NAVY;border-radius:8px;padding:5px 12px;min-width:0;overflow:hidden;box-sizing:border-box;}
.kpi.acc {border-top-color:§TEAL;}
.kpi .l {font-size:11.5px;color:§INK2;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.kpi .v {font-size:23px;font-weight:700;line-height:1.2;color:§INK;white-space:nowrap;}
.kpi .v small {font-size:12px;font-weight:600;color:§INK2;}
.kpi .s {font-size:11px;line-height:1.25;color:§INK2;white-space:normal;max-height:28px;overflow:hidden;}
.tp {border-bottom:1px dotted #7a8a9d; cursor:help;}
.kpi .l .tp {border-bottom:none;}
.pos {color:§ORANGE;} .neg {color:§BLUE;}
.chip {display:inline-block;font-size:10px;font-weight:700;padding:0 6px;border-radius:9px;vertical-align:middle;margin-left:4px;}
.chip.pos {background:#fdebd9;} .chip.neg {background:#dbe8f5;}
/* seksi */
.st-key-main {height:var(--M);}
.st-key-secL, .st-key-secR {height:var(--M); border:0; padding:0 !important; box-sizing:border-box; overflow:hidden; background:transparent;}
.sec {height:24px; line-height:22px; font-size:14px; font-weight:700; color:§NAVY; text-align:left; padding-left:2px; letter-spacing:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.sec span {font-weight:500; color:§INK2; text-transform:none; letter-spacing:0; margin-left:10px; font-size:12px;}
.st-key-tsCard > *, .st-key-mapCard > *, .st-key-anCard > *, .st-key-fiCard > *, .st-key-evCard > * {flex-shrink:0 !important;}
.st-key-tsCard, .st-key-mapCard, .st-key-anCard, .st-key-fiCard, .st-key-evCard {background:#fff; border:1px solid #dde4ec; border-radius:8px; overflow:hidden; gap:0 !important; box-sizing:border-box;}
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
.ct {font-size:13px;font-weight:650;color:§NAVY;padding:6px 10px 0;height:28px;box-sizing:border-box;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.ct span {font-weight:500;color:#5b6b7f;font-size:11px;margin-left:8px;}
.note {font-size:10.5px;line-height:1.3;color:#5b6b7f;padding:2px 10px 0;height:30px;overflow:hidden;}
table.ev {border-collapse:collapse;width:100%;font-size:11px;}
table.ev th {font-size:11px;color:#5b6b7f;font-weight:600;text-align:right;padding:2px 8px;border-bottom:1px solid #dde4ec;}
table.ev th:first-child, table.ev td:first-child {text-align:left;}
table.ev td {padding:3px 8px;text-align:right;border-bottom:1px solid #eef2f7;white-space:nowrap;color:§INK;}
table.ev tr.act td {background:#dbe8f5;font-weight:600;}
table.ev tr.base td:first-child {color:§INK2;}
table.ev td.min {color:§ORANGE;font-weight:700;}
.bar {display:inline-block;height:6px;background:§BLUE;border-radius:3px;vertical-align:middle;margin-right:5px;opacity:.6;}
.evw {padding:0 8px;}
.sumw {display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:6px 10px 0;height:58px;box-sizing:border-box;}
.sum {border-left:3px solid §BLUE;padding-left:7px;min-width:0;overflow:hidden;}
.sum .l {font-size:11px;color:#5b6b7f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sum .v {font-size:14px;font-weight:700;color:§INK;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;}
.sum .s {font-size:11px;color:#4a5b70;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
/* footer */
.foot {height:var(--ftr); display:grid; grid-template-columns:auto 1fr; gap:var(--gap); box-sizing:border-box;}
.foot > div {background:#fff; border:1px solid #dde4ec; border-radius:8px; display:flex; align-items:center; padding:0 12px; font-size:10.5px; color:§INK2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; gap:8px;}
.foot .pill {background:§NAVY; color:#d7e4f2; padding:3px 10px; border-radius:12px; font-size:10.5px;}
.foot .dot {display:inline-block;width:7px;height:7px;border-radius:50%;background:#5ad18f;margin-right:6px;}
.foot .w {color:#8a4300;}
@media (max-height: 830px) {
  table.ev td {padding:1px 8px !important; font-size:10.5px !important;} table.ev th {padding:1px 8px !important;}
  .bar {height:5px;}
}
.kpi.hero {background:#f0f9f9; border-top-color:§TEAL;}
.kpi.hero .v {font-size:25px;}
.kpi .v, .sum .v, table.ev td {font-variant-numeric:tabular-nums;}
/* tinggi grafik */
§CHARTS
</style>
"""
_CHARTS = (_h("c_temp", "calc(var(--Tt) - 34px)") + _h("c_anom", "calc(var(--Rb) - 30px)") + _h("c_fi", "calc(var(--Tb) - 40px)")
           + _h("map_sel", "calc(var(--Rt) - 30px - 58px - 4px)") + _h("bars", "calc(var(--Rt) - 30px - 58px - 4px)"))
for _k, _v in {"§NAVY": NAVY, "§BLUE": BLUE, "§ORANGE": ORANGE, "§INK2": INK2, "§INK": INK, "§TEAL": TEAL, "§CHARTS": _CHARTS}.items():
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
    for n, k in (("ringkasan_anomali", "ring"), ("normal_bulanan", "norm"), ("nino34_skenario", "nsk"), ("prediksi_uji", "pu")):
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
# skenario Niño 3.4 untuk forecast (opsional: nino34_skenario.csv berisi tanggal, nino34, skenario)
if D["nsk"] is not None and len(D["nsk"]):
    _n = D["nsk"].copy()
    _n["tanggal"] = pd.to_datetime(_n["tanggal"])
    _n = _n.sort_values("tanggal")
    _sk = str(_n["skenario"].iloc[0]) if "skenario" in _n.columns else "plume IRI"
    NINO_TXT = f"IRI {fmt(_n['nino34'].iloc[0])} → {fmt(_n['nino34'].iloc[-1])}"
    NINO_NOTE = f"skenario Niño 3.4 dari plume IRI/CCSR ({_sk}), bukan nilai tetap"
else:
    NINO_TXT = f"asumsi {fmt(NINO_ASUMSI)} (tetap)"
    NINO_NOTE = f"asumsi Niño 3.4 = {fmt(NINO_ASUMSI)} (tetap)"
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
# Satu halaman = satu orang. Ganti judul, nama, dan unit tiap halaman di sini (nama di header ikut berubah per halaman).
PAGES = {
    "1": {"judul": "Dashboard utama", "nama": "Nama Anda", "unit": "Magang BMKG · IPB"},
    "2": {"judul": "Halaman 2", "nama": "Nama Teman 2", "unit": "Magang BMKG · IPB"},
    "3": {"judul": "Halaman 3", "nama": "Nama Teman 3", "unit": "Magang BMKG · IPB"},
    "4": {"judul": "Halaman 4", "nama": "Nama Teman 4", "unit": "Magang BMKG · IPB"},
}


def _logo(fn, txt):
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", f"{fn}.{ext}")
        if os.path.exists(p):
            import base64
            return f'<div class="lg"><img src="data:image/{ext};base64,{base64.b64encode(open(p, "rb").read()).decode()}"></div>'
    return f'<div class="lg">{txt}</div>'


PAGE = SS.get("page") or "1"   # nilai pilihan halaman (widget-nya dibuat setelah header)
ID = PAGES[PAGE]
st.markdown(
    f"""<div class="hdr">{_logo("logo_bmkg", "logo<br>BMKG")}{_logo("logo_ipb", "logo<br>IPB")}
<div class="ttl"><h1>Dashboard Forecast Suhu Udara Pulau Jawa</h1>
<div class="sub">Pemantauan t2m, anomali, dan performa model ML untuk 6 provinsi, ERA5 + Niño 3.4</div></div>
<div class="bx pg"><span class="pgl">Halaman</span></div><div class="bx idn"><b>{ID["nama"]}</b><br>{ID["unit"]}</div></div>""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ halaman (2-4 masih kosong)
with st.container(key="pgnav"):
    PAGE = st.selectbox("Halaman", list(PAGES), key="page", label_visibility="collapsed", format_func=lambda k: f"Halaman {k}")

def footer():
    st.markdown(
        f'<div class="foot"><div>Info data <span class="pill"><span class="dot"></span>Data terakhir: {mon_label(last_obs)} · Forecast s.d. {mon_label(fc_end)}</span></div>'
        f'<div><b>ERA5</b> · Normal {norm_period} · <span class="w">Eksperimental · bersyarat skenario Niño 3.4 · bukan produk operasional BMKG</span> · Detail di ⓘ Catatan</div></div>',
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
- **Sumber dan periode.** ERA5 (reanalisis) dan indeks Niño 3.4, 6 provinsi di Pulau Jawa. ERA5 {mon_label(first_obs)} – {mon_label(last_obs)}; normal klimatologis {norm_period}; forecast {mon_label(fc_start)} – {mon_label(fc_end)}, 1 bulan ke depan (input bulan t, target t+1).
- **Forecast.** Eksperimental dan bersyarat pada {NINO_NOTE}, dengan variabel pendukung klimatologis. Bukan prediksi ENSO sendiri dan bukan produk operasional BMKG.
- **Interval {level}%.** Kuantil empiris dari 12 residual uji, lebarnya konstan, kemungkinan terlalu sempit. Pada "Semua Provinsi" interval adalah rata-rata batas antarprovinsi (aproksimasi).
- **Anomali.** Suhu ERA5/prediksi dikurangi normal bulanan ({norm_period}). Berbeda dari error prediksi (prediksi − ERA5).
- **Angka "rata-rata 6 provinsi".** Rata-rata tak berbobot 6 provinsi di Pulau Jawa, bukan seluruh Indonesia.
- **Evaluasi.** Hasil final test 12 bulan, tanpa cross-validation. Selisih antarmodel sering kecil; jangan dibaca sebagai keunggulan pasti. ★ menandai nilai terendah (terbaik).
- **Feature Importance.** Kenaikan RMSE ketika fitur diacak. Kontribusi prediktif relatif, bukan hubungan sebab-akibat.

**Istilah**
- **Pooled / Per-provinsi:** satu model untuk semua provinsi / satu model per provinsi.
- **XGBoost, HGB (HistGradientBoosting):** algoritma gradient boosting berbasis pohon keputusan.
- **Lag:** nilai variabel beberapa bulan sebelum bulan input.
- **RMSE, MAE, MAPE:** ukuran error prediksi (makin kecil makin baik); RMSE lebih menghukum error besar, MAPE dalam persen.
- **Persistence:** baseline, suhu bulan depan dianggap sama dengan bulan ini. **Seasonal naive:** baseline, sama dengan bulan yang sama tahun lalu."""
    )

if isinstance(rng, (tuple, list)) and len(rng) == 2:
    d0, d1 = pd.Timestamp(rng[0]).to_period("M").to_timestamp(), pd.Timestamp(rng[1]).to_period("M").to_timestamp("M")
else:
    d0, d1 = pd.Timestamp(DEFAULTS["rng"][0]), pd.Timestamp(DEFAULTS["rng"][1])


# ------------------------------------------------------------------ halaman 2-4 (kosong). Filter tetap dirender (disembunyikan) agar pilihannya tidak hilang.
if PAGE != "1":
    st.markdown("<style>.st-key-filt {display:none !important;}</style>", unsafe_allow_html=True)
    st.markdown(f'<div class="blank"><div><div class="bt">{ID["judul"]}</div><div class="bs">Konten menyusul</div></div></div>', unsafe_allow_html=True)
    footer()
    st.stop()


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
    base = dict(separators=",.", font=dict(size=11, color=INK2, family="Poppins, Segoe UI, sans-serif"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=42, r=12, t=34, b=28), hoverlabel=dict(font_size=11, bgcolor="#fff", font_color=INK),
                legend=dict(orientation="h", x=0, y=1, yanchor="bottom", font=dict(size=11, color=INK2), tracegroupgap=0, itemwidth=30))
    base.update(kw)
    fig.update_layout(**base)
    return fig


def axes(fig, x=None, y=None):
    bx = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=11))
    by = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=11))
    bx.update(x or {})
    by.update(y or {})
    fig.update_xaxes(**bx)
    fig.update_yaxes(**by)


def divider(fig, bottom=False):
    b = pd.Timestamp(last_obs) + pd.Timedelta(days=15)
    fig.add_vrect(x0=b, x1=pd.Timestamp("2100-01-01"), fillcolor="rgba(15,139,141,.06)", line_width=0, layer="below")
    fig.add_vline(x=b, line=dict(color=TEAL, width=1, dash="dot"))
    if bottom:
        fig.add_annotation(x=b, xref="x", y=0, yref="paper", text="Forecast →", showarrow=False, xanchor="left", yanchor="bottom",
                           xshift=4, yshift=2, bgcolor="rgba(255,255,255,.8)", font=dict(size=10, color=TEAL))
    else:
        fig.add_annotation(x=b, xref="x", y=1, yref="paper", text="Forecast →", showarrow=False, xanchor="left", yanchor="top",
                           xshift=4, font=dict(size=10, color=TEAL))


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
    fig.add_scatter(x=o["d"], y=o["t"], mode="lines", name=f"ERA5: {nm}", line=dict(color=NAVY, width=2.2), customdata=o["a"],
                    hovertemplate=f"<b>{nm}</b><br>ERA5: %{{y:.2f}} °C · anomali %{{customdata:+.2f}} °C<extra></extra>")
    fig.add_scatter(x=o["d"], y=o["n"], mode="lines", name=f"Normal {norm_period}", line=dict(color="#6b7a8d", width=1.4, dash="dash"),
                    hovertemplate="Normal: %{y:.2f} °C<extra></extra>")
    if len(f):
        fig.add_scatter(x=f["d"], y=f["hi"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip", legendgroup="ci")
        fig.add_scatter(x=f["d"], y=f["lo"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(15,139,141,.16)",
                        name=f"Interval {level}%", legendgroup="ci", hoverinfo="skip")
        fig.add_scatter(x=f["d"], y=f["p"], mode="lines+markers", name=f"Forecast: {nm}", line=dict(color=TEAL, width=2, dash="dash"),
                        marker=dict(size=5, color=TEAL), customdata=np.stack([f["lo"], f["hi"], f["a"]], axis=-1),
                        hovertemplate=(f"<b>{nm}</b><br>Forecast: %{{y:.2f}} °C · anomali %{{customdata[2]:+.2f}} °C"
                                       f"<br>Interval {level}%: %{{customdata[0]:.2f}} – %{{customdata[1]:.2f}} °C<extra></extra>"))
    divider(fig)
    layout(fig, hovermode="x unified", margin=dict(l=42, r=12, t=40, b=28))
    axes(fig, x=dict(range=[d0, d1]), y=dict(title=dict(text="°C", standoff=4)))
    return fig, nm


def fig_back():
    """Backtest: prediksi model vs ERA5 pada 12 bulan uji (data prediksi_uji.csv)."""
    pu = D["pu"].copy()
    pu["tanggal_target"] = pd.to_datetime(pu["tanggal_target"])
    m = ALGO_NAME[algo]
    a = pu[(pu["pendekatan"] == src) & (pu["model"] == m)]
    b = pu[(pu["pendekatan"] == "Baseline") & (pu["model"] == "Persistence")]
    if prov != "ALL":
        a, b = a[a["provinsi"] == prov], b[b["provinsi"] == prov]
    nm = "Rata-rata 6 provinsi" if prov == "ALL" else pl(prov)
    ga = a.groupby("tanggal_target")[["aktual", "prediksi", "error"]].mean().reset_index().sort_values("tanggal_target")
    gb = b.groupby("tanggal_target")[["prediksi"]].mean().reset_index().sort_values("tanggal_target")
    rm = lambda df: float(np.sqrt((df["error"] ** 2).mean())) if len(df) else float("nan")
    info = f"RMSE {m} {fmt(rm(a), 3)} · Persistence {fmt(rm(b), 3)} °C"
    fig = go.Figure()
    fig.add_scatter(x=ga["tanggal_target"], y=ga["aktual"], mode="lines+markers", name=f"ERA5: {nm}", line=dict(color=NAVY, width=2.2), marker=dict(size=5),
                    hovertemplate="ERA5: %{y:.2f} °C<extra></extra>")
    fig.add_scatter(x=ga["tanggal_target"], y=ga["prediksi"], mode="lines+markers", name=f"Prediksi {m} ({src})", line=dict(color=TEAL, width=2),
                    marker=dict(size=5), customdata=ga["error"], hovertemplate="Prediksi: %{y:.2f} °C · error %{customdata:+.2f} °C<extra></extra>")
    if len(gb):
        fig.add_scatter(x=gb["tanggal_target"], y=gb["prediksi"], mode="lines", name="Persistence (suhu bulan lalu)", line=dict(color=ZERO, width=1.4, dash="dot"),
                        hovertemplate="Persistence: %{y:.2f} °C<extra></extra>")
    layout(fig, hovermode="x unified", margin=dict(l=42, r=12, t=40, b=28))
    tv = list(ga["tanggal_target"])[::2]
    axes(fig, x=dict(tickmode="array", tickvals=tv, ticktext=[f"{BLN[t.month - 1]} {t.year}" for t in tv]), y=dict(title=dict(text="°C", standoff=4)))
    return fig, nm, info


def fig_anom():
    o = obs_for(prov)
    o = o[(o["d"] >= d0) & (o["d"] <= d1)]
    f = fc_for(prov)
    f = f[(f["d"] >= d0) & (f["d"] <= d1)]
    nm = "Rata-rata 6 provinsi" if prov == "ALL" else pl(prov)
    fig = go.Figure()

    def bars(df, pos, name):
        a = df[df["a"] >= 0] if pos else df[df["a"] < 0]
        fig.add_bar(x=a["d"], y=a["a"], name=name, marker=dict(color=ORANGE if pos else BLUE),
                    hovertemplate=f"<b>{nm}</b><br>ERA5: anomali %{{y:+.2f}} °C<extra></extra>")

    bars(o, True, "ERA5, positif")
    bars(o, False, "ERA5, negatif")
    fig.add_scatter(x=f["d"], y=f["a"], mode="lines+markers", name=f"Forecast (± interval {level}%)",
                    line=dict(color=TEAL, width=1.6), marker=dict(color=TEAL, size=5, line=dict(color="#fff", width=1)),
                    error_y=dict(type="data", symmetric=False, array=(f["ahi"] - f["a"]).values, arrayminus=(f["a"] - f["alo"]).values,
                                 color="rgba(15,139,141,.5)", thickness=1, width=2),
                    customdata=np.stack([f["alo"], f["ahi"]], axis=-1),
                    hovertemplate=(f"<b>{nm}</b><br>Forecast: anomali %{{y:+.2f}} °C<br>Interval {level}%: "
                                   "%{customdata[0]:+.2f} – %{customdata[1]:+.2f} °C<extra></extra>"))
    divider(fig, bottom=True)
    fig.add_hline(y=0, line=dict(color=ZERO, width=1))
    layout(fig, barmode="overlay", bargap=.15, hovermode="x unified", margin=dict(l=42, r=12, t=40, b=28))
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
    r = r.sort_values("importance", ascending=False).head(8).iloc[::-1]
    if not len(r):
        fig = go.Figure(); layout(fig, margin=dict(l=8, r=8, t=6, b=8), showlegend=False)
        fig.add_annotation(text="Importance belum tersedia untuk kombinasi ini", xref="paper", yref="paper", x=.5, y=.5, showarrow=False, font=dict(size=12, color="#7a8a9d"))
        fig.update_xaxes(visible=False); fig.update_yaxes(visible=False)
        return fig, note
    names = [friendly(f) for f in r["fitur"]]
    fig = go.Figure(go.Bar(x=r["importance"], y=names, orientation="h", marker_color=[NAVY if i == len(r) - 1 else "#8aa3bd" for i in range(len(r))], text=[fmt(v, 3) for v in r["importance"]],
                           textposition="outside", cliponaxis=False, textfont=dict(size=11, color=INK), customdata=np.stack([[describe(f) for f in r["fitur"]], list(r["fitur"])], axis=-1),
                           hovertemplate="<b>%{y}</b> (%{customdata[1]})<br>Importance: %{x:.4f}<br>%{customdata[0]}<extra></extra>"))
    layout(fig, margin=dict(l=8, r=44, t=6, b=28), showlegend=False)
    axes(fig, x=dict(title=dict(text="Kenaikan RMSE bila fitur diacak (°C)", font=dict(size=10), standoff=2),
                     range=[0, (r["importance"].max() if len(r) else 1) * 1.3]),
         y=dict(automargin=True, gridcolor="rgba(0,0,0,0)", tickmode="array", tickvals=names, ticktext=names, tickfont=dict(size=11, color=INK)))
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


def _hx(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def color_scale(lo, hi):
    """Skala warna dinamis. Semua positif -> oranye bertingkat; semua negatif -> biru bertingkat; campuran -> divergen simetris."""
    # skala tetap divergen (biru = negatif, oranye = positif), simetris di sekitar 0, supaya legenda selalu berisi biru dan oranye
    m = max(abs(lo), abs(hi), 0.3)
    m = float(np.ceil(m / 0.25) * 0.25)
    return -m, m, [[0, BLUE], [.5, "#f4f4f4"], [1, ORANGE]]


def scale_rgb(v, cmin, cmax, stops):
    t = max(0.0, min(1.0, (v - cmin) / (cmax - cmin if cmax > cmin else 1)))
    for (t0, c0), (t1, c1) in zip(stops[:-1], stops[1:]):
        if t <= t1:
            a, b, u = _hx(c0), _hx(c1), (t - t0) / (t1 - t0)
            return [round(a[i] + (b[i] - a[i]) * u) for i in range(3)]
    return _hx(stops[-1][1])


def map_values(metric, s):
    if metric == "obs":
        return {p: dict(v=float(obs_for(p)["a"].iloc[-1]), t="ERA5 " + mon_label(obs_for(p)["d"].iloc[-1])) for p in PROVS}
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
    vv = [mv[f["prov"]]["v"] for f in feats]
    cmin, cmax, stops = color_scale(min(vv), max(vv))
    fig = go.Figure()
    for f in feats:
        o = mv[f["prov"]]
        dim = prov != "ALL" and prov != f["prov"]
        rgb = scale_rgb(o["v"], cmin, cmax, stops)
        hov = f"<b>{pl(f['prov'])}</b><br>{o['t']}: {fmt(o['v'], 2, True)} °C"
        if "mx" in o:
            pk = o["peak"]
            pk = mon_label(pk[:7] + "-01") if len(pk) >= 7 else pk
            hov += f"<br>Maks: {fmt(o['mx'], 2, True)} °C ({pk})<br>Bulan negatif: {o['neg']}"
        fig.add_scatter(x=f["x"], y=f["y"], mode="lines", fill="toself", fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{.18 if dim else 1})",
                        line=dict(color="#fff", width=.8), hoveron="fills", hoverinfo="text", text=hov, showlegend=False)
    if prov != "ALL":
        for f in feats:
            if f["prov"] == prov:
                fig.add_scatter(x=f["x"], y=f["y"], mode="lines", line=dict(color=NAVY, width=1.2), hoverinfo="skip", showlegend=False)
    lbl = {"Banten": "Banten", "Jakarta": "DKI", "Jawa Barat": "Jabar", "Jawa Tengah": "Jateng", "Jawa Timur": "Jatim", "Yogyakarta": "DIY"}
    pos = {"Jakarta": "top center", "Banten": "bottom left", "Yogyakarta": "bottom center", "Jawa Barat": "bottom center"}
    # provinsi sangat kecil (DKI): titik penanda agar tetap terlihat
    for f in feats:
        xs_ = [v for v in f["x"] if v is not None]
        if max(xs_) - min(xs_) < 0.5:
            rgb = scale_rgb(mv[f["prov"]]["v"], cmin, cmax, stops)
            dim = prov != "ALL" and prov != f["prov"]
            fig.add_scatter(x=[f["c"][0]], y=[f["c"][1]], mode="markers", hoverinfo="skip", showlegend=False,
                            marker=dict(size=9, color=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{.25 if dim else 1})",
                                        line=dict(color=NAVY if prov == f["prov"] else "#fff", width=1.2)))

    def _lab(f):
        n = lbl.get(f["prov"], pl(f["prov"]))
        if prov != "ALL" and prov != f["prov"]:
            return n  # provinsi lain: angka disembunyikan, nama dipudarkan
        return f"{n}<br><b>{fmt(mv[f['prov']]['v'], 2, True)}</b>"
    fig.add_scatter(x=[f["c"][0] for f in feats], y=[f["c"][1] for f in feats], mode="text",
                    text=[_lab(f) for f in feats], cliponaxis=False,
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
                    marker=dict(size=.1, color=[cmin], cmin=cmin, cmax=cmax, colorscale=stops, showscale=True,
                                colorbar=dict(thickness=8, len=.8, title=dict(text="°C", side="top", font=dict(size=10)), tickfont=dict(size=10), outlinewidth=0, tickformat="+.2f", x=1.0, xpad=0,
                                              tickvals=[round(v, 2) for v in np.linspace(cmin, cmax, 5)])))
    layout(fig, margin=dict(l=2, r=44, t=2, b=2), showlegend=False, hovermode="closest", dragmode=False,
           clickmode="event+select", xaxis=dict(visible=False, range=[x0 - (x1 - x0) * .03, x1 + (x1 - x0) * .03], constrain="domain", fixedrange=True),
           yaxis=dict(visible=False, range=[y0 - (y1 - y0) * .16, y1 + (y1 - y0) * .22], scaleanchor="x", scaleratio=1, constrain="domain", fixedrange=True))
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
# bulan acuan KPI forecast = bulan berjalan (atau isi manual, mis. "2026-11"), dibatasi pada horizon forecast
BULAN_ACUAN = None
_ref = pd.Timestamp(BULAN_ACUAN + "-01") if BULAN_ACUAN else pd.Timestamp.today().to_period("M").to_timestamp()
ref = min(max(_ref, fc_start), fc_end)
fr = f_nat[f_nat["d"] == ref]
fr = fr.iloc[0] if len(fr) else f0
h_ref = (ref.year - pd.Timestamp(last["tanggal"]).year) * 12 + ref.month - pd.Timestamp(last["tanggal"]).month   # jarak (bulan) dari data terakhir
pk = f_nat.loc[f_nat["a"].idxmax()]
I = lambda k: f' <span class="tp" title="{GLOSS[k]}">ⓘ</span>'
if D["nsk"] is not None and len(D["nsk"]):
    _r = D["nsk"].assign(tanggal=pd.to_datetime(D["nsk"]["tanggal"]))
    _r = _r[_r["tanggal"] == ref]
    nino_ref = float(_r["nino34"].iloc[0]) if len(_r) else None
else:
    nino_ref = NINO_ASUMSI
cards = [
    ("", f"ERA5 terakhir · {mon_label(last['tanggal'])}" + I("ERA5"), f'{fmt(last["t2m"])} <small>°C</small>',
     f'Anomali <b class="{sg(last["anomali"])}">{fmt(last["anomali"], 2, True)} °C</b> terhadap normal {norm_period} · rata-rata 6 prov.'),
    ("acc hero", f"Forecast {mon_label(ref)}" + (" (bulan ini)" if not BULAN_ACUAN and ref == _ref else ""), f'{fmt(fr["p"])} <small>°C</small>',
     f'Anomali <b class="{sg(fr["a"])}">{fmt(fr["a"], 2, True)} °C</b> · {h_ref} bln setelah data terakhir · rata-rata 6 prov.'),
    ("acc", "Rerata anomali 12 bulan", f'<span class="{sg(f_nat["a"].mean())}">{fmt(f_nat["a"].mean(), 2, True)}</span> <small>°C</small>{chip(f_nat["a"].mean())}',
     f'{mon_label(f_nat["d"].iloc[0])} – {mon_label(f_nat["d"].iloc[-1])} · suhu rerata {fmt(f_nat["p"].mean())} °C · rata-rata 6 prov.'),
    ("acc hero", "Puncak anomali forecast", f'<span class="{sg(pk["a"])}">{fmt(pk["a"], 2, True)}</span> <small>°C</small>',
     f'{mon_label(pk["d"])} · suhu {fmt(pk["p"])} °C · rata-rata 6 prov.'),
    ("", "Model terbaik (RMSE)" + I("RMSE"), f'{fmt(best["RMSE"], 3)} <small>°C</small>',
     f'{best["pendekatan"]} · {str(best["model"]).replace("HistGradientBoosting", "HGB")} · selisih ke peringkat 2: {fmt(second["RMSE"] - best["RMSE"], 3)} °C'),
]
if nino_ref is not None and D["nsk"] is not None:
    cards.append(("acc", f"Niño 3.4 · {mon_label(ref)}" + I("Niño34"), f'{fmt(nino_ref)} <small>°C · skenario</small>',
                  f'Plume IRI · data terakhir {mon_label(nn["tanggal"])}: {fmt(nn["nino34"])} °C ({nn["fase"]})'))
else:
    cards.append(("acc", "Niño 3.4 terakhir dan fase", f'{fmt(nn["nino34"])} <small>°C · {nn["fase"]}</small>',
                  f'{mon_label(nn["tanggal"])} (data) · forecast memakai {NINO_TXT}'))
st.markdown('<div class="kpis">' + "".join(f'<div class="kpi {c}"><div class="l">{l}</div><div class="v">{v}</div><div class="s" title="{re.sub("<[^>]+>", "", s_)}">{s_}</div></div>' for c, l, v, s_ in cards) + "</div>",
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
    h = f'<div class="evw"><table class="ev"><thead><tr><th>Model</th><th>{tip("RMSE")} (°C)</th><th>{tip("MAE")} (°C)</th><th>{tip("MAPE")} (%)</th></tr></thead><tbody>'
    for pe, mo, r in rows:
        nmz = tip(mo, mo) + " (baseline)" if pe == "Baseline" else f'{tip(pe)} · {tip(mo.replace("HistGradientBoosting", "HGB"), mo.replace("HistGradientBoosting", "HGB"))}'
        if r is None:
            h += f'<tr><td>{nmz}</td><td colspan="3">n/a</td></tr>'
            continue
        act = pe == src and mo == ALGO_NAME[algo]
        cl = lambda k, d: f'<td class="{"min" if r[k] == mn[k] else ""}">{fmt(r[k], d)}{" ★" if r[k] == mn[k] else ""}</td>'
        h += (f'<tr class="{"base" if pe == "Baseline" else ""} {"act" if act else ""}"><td>{nmz}</td>'
              f'<td class="{"min" if r["RMSE"] == mn["RMSE"] else ""}"><span class="bar" style="width:{r["RMSE"] / mx * 40:.0f}px"></span>{fmt(r["RMSE"], 3)}{" ★" if r["RMSE"] == mn["RMSE"] else ""}</td>'
              f'{cl("MAE", 3)}{cl("MAPE_%", 2)}</tr>')
    h += "</tbody></table></div>"
    n = ok[0][2]["n"] if ok else None
    return h, scope, n


with st.container(key="main"):
    L, R = st.columns([1.56, 1])

    # ---------------- kiri: model
    with L.container(key="secL"):
        _fp = fc_for(prov)
        if len(_fp):
            _pk = _fp.loc[_fp["a"].idxmax()]
            _ins = (f"{'6 provinsi' if prov == 'ALL' else pl(prov)}: anomali positif di {int((_fp['a'] >= 0).sum())} dari {len(_fp)} bulan forecast, "
                    f"puncak {mon_label(_pk['d'])} ({fmt(_pk['a'], 2, True)} °C)")
        else:
            _ins = "observasi, prediksi, evaluasi"
        st.markdown(f'<div class="sec">Forecast dan performa model<span>{_ins}</span></div>', unsafe_allow_html=True)
        with st.container(key="tsCard"):
            with st.container(key="tsHead"):
                h1, h2 = st.columns([2.4, 1.6], vertical_alignment="center")
                has_bt = D["pu"] is not None and len(D["pu"])
                view = "Forecast"
                if has_bt:
                    try:
                        view = h2.segmented_control("Tampilan", ["Forecast", "Backtest 12 bln"], default="Forecast", key="tsview", label_visibility="collapsed") or "Forecast"
                    except Exception:
                        view = h2.radio("Tampilan", ["Forecast", "Backtest 12 bln"], horizontal=True, key="tsview_r", label_visibility="collapsed")
            if view == "Forecast":
                fg, nm = fig_temp()
                h1.markdown(f'<div class="ct">Suhu udara 2 m, ERA5 dan forecast<span>{nm} · {ALGO_NAME[algo]} · {src}</span></div>', unsafe_allow_html=True)
            else:
                fg, nm, info = fig_back()
                h1.markdown(f'<div class="ct">Backtest 12 bulan uji: prediksi vs ERA5<span>{nm} · {info}</span></div>', unsafe_allow_html=True)
            plot(fg, key="c_temp")
        with st.container(key="rowL"):
            a, b = st.columns(2)
            with a.container(key="fiCard"):
                fg, note = fig_fi()
                st.markdown(f'<div class="ct">Feature Importance, Top 8 {tip("ⓘ", "Importance")}<span>{ALGO_NAME[algo]} · {src}</span></div>', unsafe_allow_html=True)
                plot(fg, key="c_fi")
                n_feat = int(imp[(imp["model"] == ALGO_NAME[algo]) & (imp["pendekatan"] == src)]["fitur"].nunique())
                pass
            with b.container(key="evCard"):
                h, scope, n = eval_table()
                st.markdown(f'<div class="ct">Evaluasi model, final test 12 bulan<span>{"semua provinsi" if prov == "ALL" else pl(prov)}</span></div>', unsafe_allow_html=True)
                st.markdown(h, unsafe_allow_html=True)
                st.markdown(f'<div class="note">{f"n = {int(n)} · " if n else ""}★ = terendah (terbaik) · selisih antarmodel sering kecil</div>', unsafe_allow_html=True)

    # ---------------- kanan: anomali
    with R.container(key="secR"):
        st.markdown('<div class="sec">Anomali suhu<span>sebaran spasial dan tren</span></div>', unsafe_allow_html=True)
        with st.container(key="mapCard"):
            s = summary()
            geo_ok = D["geo"] is not None and len(prep_geo(D["geo"], tuple(PROVS))) > 0
            with st.container(key="mapHead"):
                t1, t2 = st.columns([1, 1.25], vertical_alignment="center")
                t1.markdown('<div class="ct" style="padding-top:8px">Peta anomali per provinsi</div>', unsafe_allow_html=True)
                metric = "fc12"
                if geo_ok:
                    metric = t2.selectbox("Metrik peta", ["fc12", "fc1", "obs"], key="map_metric", label_visibility="collapsed",
                                          format_func=lambda m: {"fc12": "Forecast, rerata 12 bln", "fc1": "Forecast, bulan target 1", "obs": "ERA5 terakhir"}[m])
            if geo_ok:
                plot(fig_map(s, metric), key="map_sel", on_select="rerun", selection_mode="points")
            else:
                plot(fig_bars(s), key="bars")
            sc = s if prov == "ALL" else s[s["prov"] == prov]
            lo_, hi_ = s.loc[s["mean"].idxmin()], s.loc[s["mean"].idxmax()]
            mxr = sc.loc[sc["max"].idxmax()]
            pk = str(mxr["peak"])
            pk = mon_label(pk[:7] + "-01") if len(pk) >= 7 else pk
            who = "rata-rata 6 prov." if prov == "ALL" else pl(prov)
            vals = [("Rerata anomali", fmt(sc["mean"].mean(), 2, True) + " °C", f"12 bln · {'6 prov.' if prov == 'ALL' else pl(prov)}"),
                    ("Anomali maks", fmt(mxr["max"], 2, True) + " °C", f"{pl(mxr['prov'])} · {pk}"),
                    ("Rerata tertinggi", pl(hi_["prov"]), fmt(hi_["mean"], 2, True) + " °C"),
                    ("Rerata terendah", pl(lo_["prov"]), fmt(lo_["mean"], 2, True) + " °C")]
            st.markdown('<div class="sumw">' + "".join(f'<div class="sum"><div class="l">{l}</div><div class="v" title="{v} · {t}">{v}</div><div class="s">{t}</div></div>' for l, v, t in vals) + "</div>",
                        unsafe_allow_html=True)
        with st.container(key="anCard"):
            fg, nm = fig_anom()
            st.markdown(f'<div class="ct">Anomali suhu, ERA5 dan forecast<span>{nm} · terhadap normal {norm_period}</span></div>', unsafe_allow_html=True)
            plot(fg, key="c_anom")

# ------------------------------------------------------------------ footer
footer()
