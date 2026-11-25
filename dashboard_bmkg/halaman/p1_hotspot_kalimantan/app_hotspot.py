"""Halaman 1: Dashboard Peramalan Hotspot Kalimantan (Rafif Danuja).

Dijalankan oleh app.py (cangkang) lewat runpy dengan EMBED=True dan DATA_DIR=data_hotspot/.
Header, tema/CSS, dan pilihan halaman ada di app.py dan tema.py; file ini hanya berisi filter, KPI, dan kartu halaman.
Data (folder data_hotspot/): geojson kecamatan, hotspot harian, outlook dan forecast model, tabel evaluasi, ERA5 ringan.
Bila data ERA5 perlu dibuat ulang dari data mentah: python halaman/p1_hotspot_kalimantan/build_data.py --help
"""
import html
import json
import os
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pyarrow.parquet as pq
import streamlit as st

if not globals().get("EMBED"):   # halaman ini tidak berdiri sendiri: tema, header, dan navigasi ada di app.py
    st.set_page_config(page_title="Dashboard BMKG x IPB", layout="wide")
    st.error("Halaman ini dijalankan lewat cangkang. Dari folder dashboard_bmkg: `streamlit run app.py` (Halaman 1).")
    st.stop()

from tema import BLN, BLUE, FONT, GRID, INK, INK2, NAVY, ORANGE, TEAL, fullscreen_btn  # noqa: E402

# ----------------------------------------------------------------------------------
# Konstanta
# ----------------------------------------------------------------------------------
DATA = globals().get("DATA_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data_hotspot")
P = {
    "geojson": os.path.join(DATA, "kecamatan_kalimantan.geojson"),
    "hotspot": os.path.join(DATA, "hotspot_kecamatan_harian.csv"),
    "outlook": os.path.join(DATA, "outlook_harian_kecamatan.csv"),
    "siaga": os.path.join(DATA, "forecast_7hari_kecamatan.csv"),
    "metrik": os.path.join(DATA, "evaluasi_model_vs_pembanding.csv"),
    "fitur": os.path.join(DATA, "pentingnya_fitur_gain.csv"),
    "avp": os.path.join(DATA, "prediksi_evaluasi_kecamatan.parquet"),
    "era5_prov": os.path.join(DATA, "era5_harian_provinsi.parquet"),
}
PROV_NAMA = {"61": "Kalimantan Barat", "62": "Kalimantan Tengah", "63": "Kalimantan Selatan",
             "64": "Kalimantan Timur", "65": "Kalimantan Utara"}
PROV_SHORT = {"Kalimantan Barat": "Kalbar", "Kalimantan Tengah": "Kalteng", "Kalimantan Selatan": "Kalsel",
              "Kalimantan Timur": "Kaltim", "Kalimantan Utara": "Kaltara"}
# kunci: (nama lengkap, warna, nama pendek, satuan)
ERA5_VARS = {
    "rain_mm": ("Curah hujan", "#1f6fb5", "Hujan", "mm/hari"),
    "t2m_c": ("Suhu udara 2 m", "#e8710a", "Suhu", "°C"),
    "d2m_c": ("Titik embun", "#0f8b8d", "Embun", "°C"),
    "wind_ms": ("Kecepatan angin 10 m", "#7b61a8", "Angin", "m/s"),
    "swvl1": ("Kelembapan tanah", "#9a7b2f", "Tanah", "m³/m³"),
}
C_UP, C_DOWN, C_FLAT = "#d62728", "#2e9e4f", "#7f7f7f"      # naik = merah, turun = hijau

# Status kecamatan dari prediksi hotspot 7 hari ke depan (pred_hotspot_7d), empat tingkat.
# Ambang bawah Waspada = kolom ambang_siaga di forecast_7hari_kecamatan.csv (±1,9 hotspot/7 hari, ikut data bila diperbarui).
# Siaga dan Awas memakai batas tetap di bawah; makna tiap tingkat dihitung ulang dari data evaluasi (lihat kalibrasi_status()).
AMBANG_SIAGA, AMBANG_AWAS = 5.0, 20.0                        # hotspot per 7 hari
STATUS = ["Normal", "Waspada", "Siaga", "Awas"]
S_COL = {"Normal": ("#e8ecf1", "#5b6b7f"), "Waspada": ("#fbefc4", "#7a5a00"),
         "Siaga": ("#fde0c2", "#a04a00"), "Awas": ("#fbd3d3", "#a51616")}      # (latar, teks)

GLOSS = {
    "AUC": "ROC-AUC: kemampuan membedakan kecamatan-hari yang ada hotspot vs tidak. 1 = sempurna, 0,5 = acak.",
    "PR-AUC": "Presisi-recall pada kejadian hotspot yang jarang (±1% sel kecamatan-hari). Lebih jujur daripada AUC untuk data tidak seimbang.",
    "RMSE": "Galat kuadrat rata-rata (hotspot per 7 hari). Menghukum meleset besar di puncak. Makin kecil makin baik.",
    "MAE": "Galat absolut rata-rata (hotspot per 7 hari). Pada data 99% nol, prediktor nol pun bisa kecil MAE-nya; baca bersama metrik lain.",
    "Siaga": "Status dari prediksi hotspot 7 hari ke depan: Waspada ≥ ambang dasar, Siaga ≥ 5, Awas ≥ 20 hotspot/7 hari. "
             "Angka besar = kecamatan berstatus Siaga atau Awas.",
}


def fmt(x, d=0):
    """Format angka gaya Indonesia: 1.234,5"""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def tgl(d):
    d = pd.Timestamp(d)
    return f"{d.day:02d} {BLN[d.month - 1]} {d.year}"


def esc(x):
    return html.escape(str(x))


def tip(txt, key):
    return f'<span class="tp" title="{html.escape(GLOSS.get(key, ""), quote=True)}">{txt}</span>'



# ----------------------------------------------------------------------------------
# Gaya khusus halaman ini. Tema dasar (header, bilah filter navy, KPI, kartu, footer) ada di tema.py.
# ----------------------------------------------------------------------------------
_CSS = """
<style>
/* Satu layar: tinggi area kartu = var(--M) dari tema.py (layar - header - filter - KPI - footer - jarak).
   Dua baris kartu: baris 1 = 58% (--R1), baris 2 = sisanya (--R2). Semua selector dibatasi ke .st-key-p1 (wadah halaman 1). */
.st-key-p1 {--M:max(380px, calc(100vh - var(--hdr) - var(--flt) - var(--kpi) - var(--ftr) - 5*var(--gap) - 8px));
  --R1:calc((var(--M) - var(--gap)) * .58); --R2:calc(var(--M) - var(--gap) - var(--R1)); --HD:30px; --IN:20px; --NT:30px;}
/* bilah filter: 6 kolom berlabel, tombol mulai kolom ke-7 */
.st-key-p1 .st-key-filt [data-testid="stColumn"]:nth-child(-n+6) {padding-top:0 !important;}
.st-key-p1 .st-key-filt [data-testid="stColumn"]:nth-child(n+7) {padding-top:16px !important;}
/* KPI: 4 metrik model, total hotspot (lebih lebar), status */
@media (min-width:1201px) {.st-key-p1 .kpis {grid-template-columns:repeat(4,1fr) 1.3fr 1.25fr;}}
.st-key-p1 .chip.up {background:#fde3e3; color:#b01e1e; margin:0 4px 0 0;} .st-key-p1 .chip.down {background:#dff3e5; color:#1d7a3a; margin:0 4px 0 0;} .st-key-p1 .chip.flat {background:#e8ecf1; color:#5b6b7f; margin:0 4px 0 0;}
/* kartu */
.st-key-p1 [class*="st-key-card_"], .st-key-p1 [class*="st-key-head_"] {flex:0 0 auto !important;}
.st-key-p1 [class*="st-key-card_"] > *, .st-key-p1 [class*="st-key-head_"] > * {flex-shrink:0 !important;}
.st-key-p1 [class*="st-key-card_"] {background:#fff; border:1px solid #dde4ec; border-radius:10px; box-shadow:0 1px 2px rgba(11,42,74,.06); overflow:hidden; gap:0 !important; padding:0 !important; box-sizing:border-box;}
.st-key-p1 [class*="st-key-card_"] [data-testid="stVerticalBlockBorderWrapper"] {border:0 !important;}
.st-key-p1 .st-key-card_ts, .st-key-p1 .st-key-card_map, .st-key-p1 .st-key-card_siaga {height:var(--R1);}
.st-key-p1 .st-key-card_avp, .st-key-p1 .st-key-card_era, .st-key-p1 .st-key-card_fi {height:var(--R2);}
.st-key-p1 [class*="st-key-head_"] {height:var(--HD); padding:0 !important; overflow:hidden;}
.st-key-p1 [class*="st-key-head_"] [data-testid="stHorizontalBlock"] {align-items:center; padding-right:8px; flex-wrap:nowrap;}
.st-key-p1 [class*="st-key-head_"] [data-testid="stHorizontalBlock"] > div:last-child {display:flex; justify-content:flex-end;}
.st-key-p1 [class*="st-key-head_"] [data-testid="stHorizontalBlock"] > div:last-child > div {width:auto !important;}
.st-key-p1 .st-key-card_era [class*="st-key-head_"] [data-testid="stButtonGroup"] {padding:0 10px;}
.st-key-p1 [class*="st-key-head_"] .ct {padding-top:7px; height:var(--HD);}
/* kontrol segmen: navy, aktif biru (sama dengan halaman 2) */
.st-key-p1 [class*="st-key-head_"] [data-testid="stButtonGroup"] button, .st-key-p1 [class*="st-key-head_"] [data-baseweb="button-group"] button {min-height:22px !important; height:24px !important; padding:0 8px !important; background:§NAVY !important; border:1px solid §NAVY !important;}
.st-key-p1 [class*="st-key-head_"] button p, .st-key-p1 [class*="st-key-head_"] button div, .st-key-p1 [class*="st-key-head_"] button span {color:#fff !important; -webkit-text-fill-color:#fff !important; font-size:11px !important;}
.st-key-p1 [class*="st-key-head_"] button[aria-checked="true"], .st-key-p1 [class*="st-key-head_"] button[aria-pressed="true"], .st-key-p1 [class*="st-key-head_"] button[data-testid="stBaseButton-segmented_controlActive"] {background:§BLUE !important; border-color:§BLUE !important;}
/* baris teks berukuran tetap supaya tinggi grafik bisa dihitung; teks lengkap ada di tooltip */
.st-key-p1 [class*="st-key-card_"] .ins {height:var(--IN); line-height:var(--IN); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:0 12px;}
.st-key-p1 [class*="st-key-card_"] .note {height:var(--NT); overflow:hidden; padding:2px 12px 0; box-sizing:border-box;}
.st-key-p1 .sumw {height:58px; padding:6px 12px 0;}
.st-key-p1 [data-testid="stPlotlyChart"] {padding:0 4px; box-sizing:border-box;}
.st-key-p1 .fleg {display:flex; flex-wrap:nowrap; overflow:hidden; gap:4px 10px; padding:0 12px; height:20px; line-height:20px; font-size:10.5px; color:§INK2; white-space:nowrap;}
.st-key-p1 .fleg i {display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:4px; vertical-align:middle;}
/* tinggi isi kartu = tinggi kartu - kepala - baris info - catatan - border */
§CHARTS
.st-key-p1 .st-key-fi_scroll {height:calc(var(--R2) - var(--HD) - 20px - 4px) !important; max-height:none !important;}
/* tabel status */
.st-key-p1 .slv {display:flex; gap:6px; padding:0 10px; height:var(--IN); align-items:center; font-size:11px; color:§INK2; white-space:nowrap; overflow:hidden;}
.st-key-p1 .st {display:inline-block; font-size:10.5px; font-weight:700; padding:0 7px; border-radius:9px; line-height:16px;}
.st-key-p1 .tbw {height:calc(var(--R1) - var(--HD) - 2*var(--IN) - 8px); overflow-y:auto; padding:0 8px 4px; box-sizing:border-box;}
.st-key-p1 .tbw table.ev {font-size:11px; table-layout:fixed;}
.st-key-p1 .tbw table.ev th {position:sticky; top:0; background:#fff; font-size:10px; padding:3px 6px;}
.st-key-p1 .tbw table.ev th:nth-child(-n+3), .st-key-p1 .tbw table.ev td:nth-child(-n+3) {text-align:left;}
.st-key-p1 .tbw table.ev td {padding:3px 6px; overflow:hidden; text-overflow:ellipsis;}
.st-key-p1 .tbw table.ev th, .st-key-p1 .tbw table.ev td {border-left:0 !important; border-right:0 !important;}
.st-key-p1 .tbw table.ev th {border-top:0 !important;}
.st-key-p1 .tbw table.ev tr:hover td {background:#f4f8fc;}
.st-key-p1 .tbw .bar {background:§TEAL; opacity:.7; margin-right:5px;}
/* layar sempit/pendek: kartu bertinggi tetap dan halaman boleh bergulir */
/* layar pendek (mis. laptop 1366x768): catatan di bawah grafik disembunyikan (teks tetap di tombol Catatan/tooltip) */
@media (max-height:760px) {.st-key-p1 {--NT:0px;} .st-key-p1 .note.cn {display:none;}}
@media (max-width:1200px) {.st-key-p1 {--R1:400px; --R2:300px;}}
</style>
"""


def _tinggi(key, expr):
    """Paksa tinggi grafik Plotly ber-key `key` (pola sama dengan tema._h)."""
    sel = ", ".join(f".st-key-p1 .st-key-{key}{x}" for x in ("", ' [data-testid="stPlotlyChart"]', " .js-plotly-plot", " .plot-container",
                                                          " .svg-container", " .main-svg"))
    return f".st-key-p1 .st-key-{key} {{flex:0 0 auto !important;}} {sel} {{height:{expr} !important;}}\n"


_CHARTS = (_tinggi("c1_ts", "calc(var(--R1) - var(--HD) - var(--IN) - var(--NT) - 2px)")
           + _tinggi("peta", "calc(var(--R1) - var(--HD) - 58px - 2px)")
           + _tinggi("c1_avp", "calc(var(--R2) - var(--HD) - var(--IN) - var(--NT) - 2px)")
           + _tinggi("c1_era", "calc(var(--R2) - var(--HD) - var(--IN) - var(--NT) - 2px)"))
for _k, _v in {"§INK2": INK2, "§NAVY": NAVY, "§BLUE": BLUE, "§TEAL": TEAL, "§CHARTS": _CHARTS}.items():
    _CSS = _CSS.replace(_k, _v)
st.markdown(_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------------
# Pemuatan data (di-cache)
# ----------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_geojson():
    with open(P["geojson"], encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_meta():
    gj = load_geojson()
    return pd.DataFrame([f["properties"] for f in gj["features"]])[["district_id", "kecamatan", "kabupaten", "provinsi"]]


@st.cache_data(show_spinner=False)
def load_hotspot():
    h = pd.read_csv(P["hotspot"], parse_dates=["tanggal"])
    return h.rename(columns={"kec_pcode": "district_id", "tanggal": "date", "hotspot_count": "v"})[["district_id", "date", "v"]]


@st.cache_data(show_spinner=False)
def load_outlook():
    o = pd.read_csv(P["outlook"], parse_dates=["tanggal"])
    return o.rename(columns={"tanggal": "date", "pred_hotspot_harian": "v"})[["district_id", "date", "v"]]


@st.cache_data(show_spinner=False)
def load_combined():
    """Aktual (s.d. tanggal data terakhir) + prediksi outlook sesudahnya, satu tabel kecamatan-hari."""
    a, o = load_hotspot().copy(), load_outlook().copy()
    a["is_pred"], o["is_pred"] = False, True
    return pd.concat([a, o], ignore_index=True)


def batas_status(ambang_dasar):
    """Batas bawah tiap tingkat (hotspot/7 hari); Siaga/Awas tidak boleh di bawah ambang dasar."""
    w = float(ambang_dasar)
    return [0.0, w, max(AMBANG_SIAGA, w), max(AMBANG_AWAS, w)]


def ke_status(pred, batas):
    """Prediksi 7 hari -> Normal/Waspada/Siaga/Awas (prediksi kosong dianggap Normal)."""
    idx = np.searchsorted(np.asarray(batas[1:]), np.nan_to_num(np.asarray(pred, dtype=float), nan=0.0), side="right")
    return pd.Categorical(np.asarray(STATUS)[idx], categories=STATUS, ordered=True)


@st.cache_data(show_spinner=False)
def load_siaga():
    """Forecast 7 hari per kecamatan. Status dihitung ulang dari pred_hotspot_7d (kolom status bawaan hanya dua tingkat)."""
    s = pd.read_csv(P["siaga"])
    s["status"] = ke_status(s["pred_hotspot_7d"], batas_status(s["ambang_siaga"].iloc[0]))
    return s


@st.cache_data(show_spinner=False)
def load_metrik():
    return pd.read_csv(P["metrik"])


@st.cache_data(show_spinner=False)
def load_fitur():
    return pd.read_csv(P["fitur"])


@st.cache_data(show_spinner="Memuat data aktual vs prediksi…")
def load_avp():
    df = pq.read_table(P["avp"], columns=["date", "district_id", "actual_7d", "pred_final"]).to_pandas()
    df["district_id"] = df["district_id"].astype("category")
    return df


@st.cache_data(show_spinner=False)
def kalibrasi_status(ambang_dasar):
    """Arti tiap tingkat pada data evaluasi 2015–2026: peluang aktual 7 hari ≥ 1 / ≥ 5 / ≥ 20 hotspot, per tingkat prediksi."""
    d = pq.read_table(P["avp"], columns=["actual_7d", "pred_final"]).to_pandas()
    k = ke_status(d["pred_final"], batas_status(ambang_dasar))
    a = d["actual_7d"].to_numpy()
    g = pd.DataFrame({"k": k, "p1": a >= 1, "p5": a >= 5, "p20": a >= 20})
    return g.groupby("k", observed=False)[["p1", "p5", "p20"]].mean().mul(100)


@st.cache_data(show_spinner="Memuat data iklim ERA5…")
def load_era5(ids: tuple, start: str, end: str, level_prov: str | None):
    """Rata-rata ERA5 harian untuk wilayah terpilih (agregat provinsi bila seluruh provinsi/Kalimantan)."""
    cols = list(ERA5_VARS)
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if level_prov is not None:
        a = pd.read_parquet(P["era5_prov"])
        a = a[(a["provinsi"] == level_prov) & (a["date"] >= s) & (a["date"] <= e)]
        return a.set_index("date")[cols].sort_index()
    frames = []
    for kode in sorted({i[2:4] for i in ids}):
        fp = os.path.join(DATA, f"era5_kecamatan_{kode}.parquet")
        if not os.path.exists(fp):
            continue
        sel = [i for i in ids if i[2:4] == kode]
        frames.append(pq.read_table(fp, filters=[("district_id", "in", sel), ("date", ">=", s), ("date", "<=", e)]).to_pandas())
    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames).groupby("date")[cols].mean().sort_index()


# ----------------------------------------------------------------------------------
# Pemeriksaan file
# ----------------------------------------------------------------------------------
missing = [k for k, v in P.items() if not os.path.exists(v)]
kec_files = [os.path.join(DATA, f"era5_kecamatan_{k}.parquet") for k in PROV_NAMA]
if missing or not all(os.path.exists(f) for f in kec_files):
    st.error("File data halaman ini belum lengkap. Pastikan folder `data_hotspot/` ada di sebelah app.py dan berisi semua file "
             "(lihat halaman/p1_hotspot_kalimantan/README.md). ERA5 ringan dibuat dengan `build_data.py`.")
    if missing:
        st.write("File yang tidak ditemukan:", {k: P[k] for k in missing})
    st.stop()

meta = load_meta()
combined = load_combined()
hot_all = load_hotspot()
LAST_OBS = hot_all["date"].max()
LAST_FC = load_outlook()["date"].max()
FIRST_OBS = hot_all["date"].min()
ERA5_END = pd.Timestamp("2026-09-23")
ids_data = set(hot_all["district_id"].unique())
meta_d = meta[meta["district_id"].isin(ids_data)].copy()
info = meta.set_index("district_id")

# ----------------------------------------------------------------------------------
# Filter (bar navy)
# ----------------------------------------------------------------------------------
PRESETS = ["90 hari terakhir data", "30 hari terakhir data", "Musim kebakaran 2026 (Jun–Des)",
           "Tahun 2026", "Tahun 2023", "Seluruh data", "Kustom"]
ALL_PROV, ALL_KAB, ALL_KEC = "Semua Kalimantan", "Semua kabupaten/kota", "Semua kecamatan"


def preset_range(name):
    if name == "90 hari terakhir data":
        return LAST_OBS - pd.Timedelta(days=89), LAST_OBS
    if name == "30 hari terakhir data":
        return LAST_OBS - pd.Timedelta(days=29), LAST_OBS
    if name == "Musim kebakaran 2026 (Jun–Des)":
        return pd.Timestamp("2026-06-01"), LAST_FC
    if name == "Tahun 2026":
        return pd.Timestamp("2026-01-01"), LAST_FC
    if name == "Tahun 2023":
        return pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31")
    return FIRST_OBS, LAST_FC


def _set_preset_rng():
    n = st.session_state["f_preset"]
    if n != "Kustom":
        a, b = preset_range(n)
        st.session_state["f_rng"] = (a.date(), b.date())


def _custom():
    st.session_state["f_preset"] = "Kustom"


def _reset_kab():
    st.session_state["f_kab"], st.session_state["f_kec"] = ALL_KAB, ALL_KEC


def _reset_kec():
    st.session_state["f_kec"] = ALL_KEC


def _reset_all():
    st.session_state["f_preset"] = PRESETS[0]
    a, b = preset_range(PRESETS[0])
    st.session_state["f_rng"] = (a.date(), b.date())
    st.session_state["f_prov"], st.session_state["f_kab"], st.session_state["f_kec"] = ALL_PROV, ALL_KAB, ALL_KEC


if "f_preset" not in st.session_state:
    _reset_all()

prov_opts = [ALL_PROV] + [PROV_NAMA[k] for k in sorted(PROV_NAMA)]
m1 = meta_d if st.session_state["f_prov"] == ALL_PROV else meta_d[meta_d["provinsi"] == st.session_state["f_prov"]]
kab_opts = [ALL_KAB] + sorted(m1["kabupaten"].unique())
if st.session_state["f_kab"] not in kab_opts:
    st.session_state["f_kab"] = ALL_KAB
m2 = m1 if st.session_state["f_kab"] == ALL_KAB else m1[m1["kabupaten"] == st.session_state["f_kab"]]
m2 = m2.sort_values("kecamatan")
_lab = {r.district_id: r.kecamatan for r in m2.itertuples()}
_dup = pd.Series(list(_lab.values())).duplicated(keep=False).tolist()
kec_label = {k: (v if not d else f"{v} ({k})") for (k, v), d in zip(_lab.items(), _dup)}
kec_opts = [ALL_KEC] + list(kec_label.values())
if st.session_state["f_kec"] not in kec_opts:
    st.session_state["f_kec"] = ALL_KEC

SPLITS = ["Holdout 2026", "Walk-forward 2015–25"]
if st.session_state.get("f_split") not in SPLITS:
    st.session_state["f_split"] = SPLITS[0]
sg = load_siaga()
BATAS = batas_status(sg["ambang_siaga"].iloc[0])
KAL = kalibrasi_status(BATAS[1])


def _pct(lv, col):
    return fmt(float(KAL.loc[lv, col]), 0) + "%"


with st.container(key="filt"):
    f1, f2, f3, f4, f5, f6, f7, f8, f9 = st.columns([1.15, 1.45, 1.1, 1.3, 1.15, 1.1, .48, .7, .75])
    f1.selectbox("Preset periode", PRESETS, key="f_preset", on_change=_set_preset_rng)
    f2.date_input("Rentang waktu", key="f_rng", min_value=FIRST_OBS.date(), max_value=LAST_FC.date(),
                  format="DD/MM/YYYY", on_change=_custom)
    f3.selectbox("Provinsi", prov_opts, key="f_prov", on_change=_reset_kab)
    f4.selectbox("Kabupaten/Kota", kab_opts, key="f_kab", on_change=_reset_kec,
                 disabled=(st.session_state["f_prov"] == ALL_PROV))
    f5.selectbox("Kecamatan", kec_opts, key="f_kec", disabled=(st.session_state["f_kab"] == ALL_KAB))
    f6.selectbox("Evaluasi model", SPLITS, key="f_split")
    f7.button("Reset", on_click=_reset_all, width="stretch")
    with f8.popover("ⓘ Catatan", width="stretch"):
        st.markdown(
            "- **Total hotspot**: aktual sampai data terakhir; hari sesudahnya memakai prediksi outlook model.\n"
            "- **Perubahan di peta**: total paruh akhir periode dibanding paruh awal. Naik = merah, turun = hijau.\n"
            f"- **Status kecamatan** dari prediksi hotspot 7 hari ke depan: **Waspada** ≥ {fmt(BATAS[1], 1)}, "
            f"**Siaga** ≥ {fmt(BATAS[2], 0)}, **Awas** ≥ {fmt(BATAS[3], 0)} hotspot/7 hari. Pada data evaluasi 2015–2026, "
            f"kecamatan-hari Waspada {_pct('Waspada', 'p1')} benar ada hotspot; Siaga {_pct('Siaga', 'p5')} benar ≥ 5 hotspot; "
            f"Awas {_pct('Awas', 'p20')} benar ≥ 20 hotspot (Normal: {_pct('Normal', 'p1')} ada hotspot).\n"
            "- **Aktual vs prediksi**: tiap titik = tanggal asal prediksi, nilainya total hotspot 7 hari sesudahnya.\n"
            "- Model memprediksi rata-rata bersyarat (Tweedie): cenderung **meremehkan puncak** di tahun api besar "
            "dan melebihkan di tahun tenang.\n"
            "- Hotspot di luar 7 hari pertama adalah skenario klimatologis (tanpa cuaca masa depan).\n"
            "- Data hotspot hanya baris positif; hari tanpa hotspot dianggap 0.")
    with f9:
        fullscreen_btn()

rng = st.session_state["f_rng"]
if not isinstance(rng, (tuple, list)) or len(rng) != 2:
    st.info("Pilih tanggal akhir pada kalender untuk melengkapi rentang waktu.")
    st.stop()
start, end = pd.Timestamp(rng[0]), pd.Timestamp(rng[1])

sel_prov, sel_kab, sel_kec = st.session_state["f_prov"], st.session_state["f_kab"], st.session_state["f_kec"]
is_all_region = sel_prov == ALL_PROV
if sel_kec != ALL_KEC:
    sel_ids = [k for k, v in kec_label.items() if v == sel_kec]
    region_name = f"{sel_kec}, {sel_kab}"
elif sel_kab != ALL_KAB:
    sel_ids, region_name = list(m2["district_id"]), f"{sel_kab}, {sel_prov}"
elif not is_all_region:
    sel_ids, region_name = list(m2["district_id"]), sel_prov
else:
    sel_ids, region_name = list(meta_d["district_id"]), "Seluruh Kalimantan"
sel_ids_t = tuple(sorted(sel_ids))
sel_set = set(sel_ids)
n_fc_days = max(0, (min(end, LAST_FC) - max(start, LAST_OBS + pd.Timedelta(days=1))).days + 1)
n_days_p = (end - start).days + 1


def period_slice(df, s, e, ids=None):
    m = (df["date"] >= s) & (df["date"] <= e)
    if ids is not None:
        m &= df["district_id"].isin(ids)
    return df[m]


def total_in(s, e, ids):
    return float(period_slice(combined, s, e, ids)["v"].sum())


def style_fig(fig, h=None, legend=True):
    """h=None: tinggi grafik mengikuti CSS kartu (tata letak satu layar)."""
    fig.update_layout(
        height=h, autosize=True, margin=dict(l=8, r=8, t=26 if legend else 6, b=6), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.",
        font=dict(family=FONT, size=11, color=INK2), hovermode="x unified",
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, size=11, color=INK)),
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=11)) if legend else dict(visible=False))
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="outside", tickcolor=GRID, automargin=True, tickfont=dict(color=INK2, size=11))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)", automargin=True, tickfont=dict(color=INK2, size=11))
    return fig


CFG = dict(displaylogo=False, displayModeBar=False)
PLOT = dict(width="stretch", config=CFG, theme=None)

# ----------------------------------------------------------------------------------
# KPI
# ----------------------------------------------------------------------------------
split_pick = st.session_state["f_split"]
split_key = "holdout" if split_pick.startswith("Holdout") else "walk-forward"
mt = load_metrik()
mm = mt[(mt["split"] == split_key) & (mt["model"] == "Model")].iloc[0]


def model_card(label, key, col, sub):
    return (f'<div class="kpi key"><div class="l">{tip(label, key)}</div><div class="v">{fmt(mm[col], 3)}</div>'
            f'<div class="s">{sub}</div></div>')


tot_now = total_in(start, end, sel_ids)
prev_len = n_days_p
prev_s, prev_e = start - pd.Timedelta(days=prev_len), start - pd.Timedelta(days=1)
tot_prev = total_in(prev_s, prev_e, sel_ids)
if tot_prev > 0:
    chg = (tot_now - tot_prev) / tot_prev * 100
    kind = "up" if chg > 0.05 else ("down" if chg < -0.05 else "flat")
    arrow = {"up": "▲ +", "down": "▼ ", "flat": "– "}[kind]
    prev_chip = f'<span class="chip {kind}">{arrow}{fmt(chg, 1)}%</span>vs periode sebelumnya'
else:
    prev_chip = '<span class="chip flat">–</span>periode sebelumnya tanpa hotspot'
sg_sel = sg[sg["district_id"].isin(sel_ids)]
n_lv = sg_sel["status"].value_counts().reindex(STATUS, fill_value=0)
n_siaga = int(n_lv["Siaga"] + n_lv["Awas"])
lv_txt = " · ".join(f'<span style="color:{S_COL[k][1]};font-weight:700">{k} {int(n_lv[k])}</span>' for k in ("Awas", "Siaga", "Waspada"))
pred_note = f"termasuk {n_fc_days} hari prediksi · " if n_fc_days else ""
st.markdown(
    '<div class="kpis">'
    + model_card("AUC", "AUC", "roc_auc", f"ROC-AUC · {split_pick.lower()}")
    + model_card("PR-AUC", "PR-AUC", "pr_auc", "presisi-recall kejadian hotspot")
    + model_card("RMSE", "RMSE", "rmse", "hotspot per 7 hari")
    + model_card("MAE", "MAE", "mae", "hotspot per 7 hari")
    + f'<div class="kpi key hot"><div class="l">Total hotspot periode</div><div class="v">{fmt(tot_now, 1 if n_fc_days else 0)}</div>'
      f'<div class="s">{pred_note}{prev_chip}</div></div>'
    + f'<div class="kpi"><div class="l">{tip("Kecamatan Siaga + Awas", "Siaga")}</div><div class="v">{n_siaga} <small style="font-size:13px;color:{INK2}">dari {len(sg_sel)}</small></div>'
      f'<div class="s">{lv_txt}</div></div>'
    + "</div>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------------
# Peta: statistik periode
# ----------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def map_stats(s_iso: str, e_iso: str):
    s, e = pd.Timestamp(s_iso), pd.Timestamp(e_iso)
    n = (e - s).days + 1
    out = pd.DataFrame({"total": period_slice(combined, s, e).groupby("district_id")["v"].sum()})
    if n >= 2:
        mid = s + pd.Timedelta(days=n // 2 - 1)
        out["first"] = period_slice(combined, s, mid).groupby("district_id")["v"].sum()
        out["second"] = period_slice(combined, mid + pd.Timedelta(days=1), e).groupby("district_id")["v"].sum()
    else:
        out["first"], out["second"] = np.nan, np.nan
    return out.fillna({"total": 0.0, "first": 0.0, "second": 0.0})


stats = map_stats(str(start.date()), str(end.date()))
dec = 1 if n_fc_days else 0


def change_of(f1_, f2_):
    if n_days_p < 2:
        return "pendek", None
    if f1_ == 0 and f2_ == 0:
        return "kosong", None
    if f1_ == 0:
        return "baru", None
    pct = (f2_ - f1_) / f1_ * 100
    return ("sama" if abs(pct) < 0.05 else ("naik" if pct > 0 else "turun")), pct


def change_text(f1_, f2_, html_=True):
    k, pct = change_of(f1_, f2_)
    t, c = {"naik": (f"▲ +{fmt(pct, 1)}%" if pct is not None else "", C_UP), "turun": (f"▼ {fmt(pct, 1)}%" if pct is not None else "", C_DOWN),
            "baru": ("▲ baru muncul", C_UP), "sama": ("– tidak berubah", C_FLAT), "kosong": ("– tidak ada hotspot", C_FLAT),
            "pendek": ("– periode terlalu pendek", C_FLAT)}[k]
    return f"<span style='color:{c}'>{t}</span>" if html_ else t


def f12(did):
    if did in stats.index:
        r = stats.loc[did]
        return float(r["first"]), float(r["second"])
    return 0.0, 0.0


# ----------------------------------------------------------------------------------
# Label fitur, kelompok, dan warna kartu
# ----------------------------------------------------------------------------------
LABEL = {
    "days_since_hotspot": "Hari sejak hotspot terakhir", "prov_sum_7d": "Hotspot provinsi, 7 hari",
    "prov_sum_30d": "Hotspot provinsi, 30 hari", "prov_sum_90d": "Hotspot provinsi, 90 hari",
    "kal_sum_90d": "Hotspot Kalimantan, 90 hari", "kal_sum_30d": "Hotspot Kalimantan, 30 hari",
    "hotspot_sum_3d": "Hotspot kecamatan, 3 hari", "hotspot_sum_7d": "Hotspot kecamatan, 7 hari",
    "hotspot_sum_14d": "Hotspot kecamatan, 14 hari", "hotspot_sum_28d": "Hotspot kecamatan, 28 hari",
    "hotspot_sum_365d": "Hotspot kecamatan, 365 hari", "hotspot_max_14d": "Hotspot harian maks., 14 hari",
    "hotspot_hist_rate_7d": "Laju historis hotspot (7 hari)", "active_days_7d": "Hari aktif hotspot, 7 hari",
    "neighbor_hotspot_sum_lag_0d": "Hotspot kecamatan tetangga", "day_cos": "Musim (kosinus hari)",
    "day_sin": "Musim (sinus hari)", "day_of_year": "Hari dalam tahun", "rain_mm_lag_0d": "Curah hujan hari ini",
    "centroid_lat": "Lintang kecamatan", "centroid_lon": "Bujur kecamatan"}


def grup(n):
    if n in ("day_cos", "day_sin", "day_of_year") or n.startswith(("hot_season", "month")):
        return "Kalender"
    if n.startswith("centroid"):
        return "Lokasi"
    if n.startswith(("prov_", "kal_", "neighbor", "share_of")):
        return "Agregat spasial"
    if n.startswith(("hotspot", "days_since", "active_days")):
        return "Riwayat hotspot"
    return "Cuaca/iklim"


G_COL = {"Riwayat hotspot": NAVY, "Agregat spasial": BLUE, "Cuaca/iklim": TEAL, "Kalender": ORANGE, "Lokasi": "#9db4cc"}
MSG = 'style="padding:14px 12px"'

def ins(html_txt):
    """Baris info satu baris; teks lengkap muncul sebagai tooltip bila terpotong."""
    plain = html.escape(re.sub(r"<[^>]+>", "", html_txt), quote=True)
    st.markdown(f'<div class="ins" title="{plain}">{html_txt}</div>', unsafe_allow_html=True)


def note(txt):
    st.markdown(f'<div class="note cn" title="{html.escape(txt, quote=True)}">{txt}</div>', unsafe_allow_html=True)


def chip(lv):
    bg, fg = S_COL[lv]
    return f'<span class="st" style="background:{bg};color:{fg}">{lv}</span>'


# Tata letak satu layar: 2 baris x 3 kartu. Baris 1: historis+forecast | peta | status 7 hari. Baris 2: aktual vs prediksi | ERA5 | fitur.
WC = [1.35, 1.1, .9]

# ======================= BARIS 1 =======================
c1, c2, c3 = st.columns(WC, gap="small")
with c1.container(key="card_ts"):
    with st.container(key="head_ts"):
        h1, h2 = st.columns([1.7, 1.5], vertical_alignment="center")
        h1.markdown(f'<div class="ct" title="{esc(region_name)} · {tgl(start)} – {tgl(end)}">Hotspot historis dan forecast '
                    f'<span>{esc(region_name)} · {tgl(start)} – {tgl(end)}</span></div>', unsafe_allow_html=True)
        st.session_state.setdefault("agg_h", "Otomatis")
        agg_h = h2.segmented_control("Agregasi", ["Otomatis", "Harian", "Mingguan", "Bulanan"],
                                     key="agg_h", label_visibility="collapsed") or "Otomatis"
    act = hot_all[hot_all["district_id"].isin(sel_ids)].groupby("date")["v"].sum()
    a_s, a_e = max(start, FIRST_OBS), min(end, LAST_OBS)
    act_s = act.reindex(pd.date_range(a_s, a_e), fill_value=0.0) if a_s <= a_e else pd.Series(dtype=float)
    fc_all = load_outlook()
    fc = fc_all[fc_all["district_id"].isin(sel_ids)].groupby("date")["v"].sum()
    f_s, f_e = max(start, LAST_OBS + pd.Timedelta(days=1)), min(end, LAST_FC)
    fc_s = fc[(fc.index >= f_s) & (fc.index <= f_e)] if f_s <= f_e else pd.Series(dtype=float)
    rule_h = {"Harian": None, "Mingguan": "W", "Bulanan": "MS"}.get(agg_h)
    if agg_h == "Otomatis":
        rule_h = None if n_days_p <= 150 else ("W" if n_days_p <= 900 else "MS")
    if rule_h:
        act_s = act_s.resample(rule_h).sum() if len(act_s) else act_s
        fc_s = fc_s.resample(rule_h).sum() if len(fc_s) else fc_s
    unit = "per hari" if not rule_h else ("per minggu" if rule_h == "W" else "per bulan")
    if act_s.empty and fc_s.empty:
        st.markdown(f'<div class="note" {MSG}>Tidak ada data pada periode ini.</div>', unsafe_allow_html=True)
    else:
        parts = []
        if len(act_s):
            parts.append(f"Aktual: <b>{fmt(float(act_s.sum()))}</b> hotspot")
        if len(fc_s):
            parts.append(f"Prediksi: <b>{fmt(float(fc_s.sum()))}</b> hotspot")
        ins(f'{" · ".join(parts)} · satuan {unit}')
        fig = go.Figure()
        if len(fc_s):
            fig.add_vrect(x0=LAST_OBS if len(act_s) else fc_s.index[0], x1=fc_s.index[-1], fillcolor=TEAL, opacity=0.07, line_width=0)
        if len(act_s):
            fig.add_trace(go.Scatter(x=act_s.index, y=act_s.values, name="Aktual", mode="lines", line=dict(color=NAVY, width=1.8)))
        if len(fc_s):
            fx, fy = list(fc_s.index), list(fc_s.values)
            if len(act_s):
                fx, fy = [act_s.index[-1]] + fx, [act_s.values[-1]] + fy
            fig.add_trace(go.Scatter(x=fx, y=fy, name="Forecast", mode="lines", line=dict(color=TEAL, width=2, dash="dash")))
        if start <= LAST_OBS <= end and len(fc_s):
            fig.add_annotation(x=LAST_OBS, y=1.0, yref="paper", text="origin forecast →", showarrow=False, xanchor="right",
                               yanchor="bottom", font=dict(size=10, color=TEAL))
        style_fig(fig)
        st.plotly_chart(fig, key="c1_ts", **PLOT)
        note("Garis putus-putus = prediksi model. Di luar 7 hari pertama model tidak mengenal cuaca masa depan, "
             "jadi kurva bersifat skenario klimatologis; andalkan tren mingguan/bulanan.")

with c2.container(key="card_map"):
    with st.container(key="head_map"):
        m1_, m2_ = st.columns([1.5, 1.1], vertical_alignment="center")
        m1_.markdown('<div class="ct">Peta sebaran hotspot <span>total periode</span></div>', unsafe_allow_html=True)
        st.session_state.setdefault("basemap", "Polos")
        bm = m2_.segmented_control("Peta dasar", ["Polos", "OpenStreetMap", "Carto"], key="basemap", label_visibility="collapsed",
                                   format_func=lambda k: "OSM" if k == "OpenStreetMap" else k) or "Polos"
    BASEMAP = {"Polos": "white-bg", "OpenStreetMap": "open-street-map", "Carto": "carto-positron"}[bm]
    ids_list = [i for i in meta["district_id"] if i in ids_data]
    tot_vals = np.array([float(stats["total"].get(i, 0.0)) for i in ids_list])
    zmax = float(np.log1p(np.quantile(tot_vals, 0.98))) if tot_vals.max() > 0 else 1.0
    zmax = max(zmax, 1e-6)
    sg_i = sg.set_index("district_id")
    st_map = sg_i["status"]
    hover = []
    for i, tv in zip(ids_list, tot_vals):
        r = info.loc[i]
        lv = st_map.get(i)
        hover.append(f"<b>{esc(r['kecamatan'])}</b><br>{esc(r['kabupaten'])}, {esc(r['provinsi'])}<br>"
                     f"Total hotspot: <b>{fmt(tv, dec)}</b><br>Rata-rata/hari: <b>{fmt(tv / n_days_p, 2)}</b><br>"
                     f"Perubahan awal→akhir: {change_text(*f12(i))}"
                     + (f"<br>Status 7 hari ke depan: <b>{lv}</b>" if isinstance(lv, str) else ""))
    no_data = [i for i in meta["district_id"] if i not in ids_data]
    gj = load_geojson()
    tick_cand = [t for t in [0, 1, 10, 100, 1000, 10000] if np.log1p(t) <= zmax * 1.001]
    fig = go.Figure()
    if no_data:
        fig.add_trace(go.Choroplethmap(
            geojson=gj, locations=no_data, featureidkey="properties.district_id", z=[0] * len(no_data),
            colorscale=[[0, "#bdbdbd"], [1, "#bdbdbd"]], showscale=False, marker=dict(opacity=0.8, line=dict(width=0.3, color="#777")),
            text=[f"{info.loc[i]['kecamatan']}: tanpa data" for i in no_data], hoverinfo="text"))
    fig.add_trace(go.Choroplethmap(
        geojson=gj, locations=ids_list, featureidkey="properties.district_id", z=np.clip(np.log1p(tot_vals), 0, zmax),
        zmin=0, zmax=zmax, colorscale=[[0, "#2e9e4f"], [0.5, "#f4d03f"], [1, "#d62728"]],
        marker=dict(opacity=0.88, line=dict(width=0.3, color="#555")), hovertext=hover, hoverinfo="text",
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, color=INK, size=11), align="left"),
        colorbar=dict(title=dict(text="hotspot", font=dict(size=10, color=INK2)), thickness=10, len=0.7, x=1.0,
                      tickfont=dict(size=10, color=INK2), tickvals=[float(np.log1p(t)) for t in tick_cand],
                      ticktext=[fmt(t) for t in tick_cand])))
    if not is_all_region:
        fig.add_trace(go.Choroplethmap(
            geojson=gj, locations=sel_ids, featureidkey="properties.district_id", z=[0] * len(sel_ids),
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
            marker=dict(line=dict(width=2.6, color="#000")), hoverinfo="skip"))

    def bbox(feature_ids):
        xs, ys = [], []

        def walk(c):
            if c and isinstance(c[0], (int, float)):
                xs.append(c[0]); ys.append(c[1])
            else:
                for k in c:
                    walk(k)
        fs = set(feature_ids)
        for ft in gj["features"]:
            if ft["properties"]["district_id"] in fs:
                walk(ft["geometry"]["coordinates"])
        return (min(xs), max(xs), min(ys), max(ys)) if xs else (108.8, 119.1, -4.3, 4.4)

    w_, e_, s_, n_ = bbox(sel_ids if not is_all_region else meta["district_id"])
    px_, py_ = (e_ - w_) * 0.05 + 0.02, (n_ - s_) * 0.05 + 0.02
    fig.update_layout(map=dict(style=BASEMAP, bounds=dict(west=w_ - px_, east=e_ + px_, south=s_ - py_, north=n_ + py_)),
                      autosize=True, margin=dict(l=0, r=0, t=0, b=0), clickmode="event+select", paper_bgcolor="rgba(0,0,0,0)",
                      separators=",.", font=dict(family=FONT, color=INK2))
    ev = st.plotly_chart(fig, on_select="rerun", selection_mode="points", key="peta", width="stretch", theme=None,
                         config=dict(displaylogo=False, displayModeBar=False, scrollZoom=True))
    picked_id = None
    try:
        pts = ev.selection.points
        if pts:
            picked_id = pts[0].get("location")
    except Exception:
        picked_id = None
    if picked_id in info.index and picked_id in ids_data:
        r = info.loc[picked_id]
        tv = float(stats["total"].get(picked_id, 0.0))
        lv = st_map.get(picked_id)
        cells = [("Kecamatan", esc(r["kecamatan"]), f"{esc(r['kabupaten'])}, {esc(PROV_SHORT.get(r['provinsi'], r['provinsi']))}"),
                 ("Total hotspot", fmt(tv, dec), f"{tgl(start)} – {tgl(end)}"),
                 ("Perubahan", change_text(*f12(picked_id)), "paruh akhir vs awal"),
                 ("Status 7 hari", chip(lv) if isinstance(lv, str) else "–",
                  f"prediksi {fmt(float(sg_i.loc[picked_id, 'pred_hotspot_7d']), 1)} hotspot" if isinstance(lv, str) else "tanpa forecast")]
    else:
        sub = stats.reindex(sel_ids).fillna(0.0)
        tot_r = float(sub["total"].sum())
        top_id = sub["total"].idxmax() if len(sub) and sub["total"].max() > 0 else None
        cells = [("Wilayah", esc(region_name), f"{len(sel_ids)} kecamatan"),
                 ("Total hotspot", fmt(tot_r, dec), f"{fmt(tot_r / n_days_p, 1)} per hari"),
                 ("Kecamatan terpanas", esc(info.loc[top_id]["kecamatan"]) if top_id else "–",
                  f"{fmt(sub.loc[top_id, 'total'], dec)} hotspot" if top_id else "tidak ada hotspot"),
                 ("Perubahan", change_text(float(sub["first"].sum()), float(sub["second"].sum())), "klik peta untuk rincian")]
    st.markdown('<div class="sumw">' + "".join(
        f'<div class="sum"><div class="l">{l}</div><div class="v">{v}</div><div class="s">{s_}</div></div>' for l, v, s_ in cells) + "</div>",
        unsafe_allow_html=True)

with c3.container(key="card_siaga"):
    w_s, w_e = pd.Timestamp(sg["window_start"].iloc[0]), pd.Timestamp(sg["window_end"].iloc[0])
    with st.container(key="head_siaga"):
        st.markdown(f'<div class="ct" title="Prediksi {tgl(w_s)} – {tgl(w_e)}">Status kecamatan 7 hari ke depan '
                    f'<span>{tgl(w_s)} – {tgl(w_e)}</span></div>', unsafe_allow_html=True)
    sg_show = sg_sel[sg_sel["status"] != "Normal"].sort_values("pred_hotspot_7d", ascending=False)
    ins(f'<b>{len(sg_show)}</b> dari {len(sg_sel)} kecamatan Waspada ke atas · {esc(region_name)}')
    st.markdown('<div class="slv">' + "".join(
        f'<span title="{k}: prediksi ≥ {fmt(BATAS[i], 1)} hotspot/7 hari">{chip(k)} {int(n_lv[k])}</span>'
        for i, k in enumerate(STATUS) if k != "Normal")
        + f'<span style="margin-left:auto" title="Batas tingkat, hotspot per 7 hari">≥{fmt(BATAS[1], 1)} · ≥{fmt(BATAS[2], 0)} · ≥{fmt(BATAS[3], 0)}</span></div>',
        unsafe_allow_html=True)
    if sg_show.empty:
        st.markdown(f'<div class="note" {MSG}>Tidak ada kecamatan berstatus Waspada, Siaga, atau Awas di wilayah ini.</div>',
                    unsafe_allow_html=True)
    else:
        vmax = float(sg["pred_hotspot_7d"].max())
        rows = "".join(
            f"<tr><td>{int(r.peringkat)}</td><td title='{esc(r.kecamatan)}, {esc(r.provinsi)}'>{esc(r.kecamatan)}</td><td>{chip(r.status)}</td>"
            f"<td><span class='bar' style='width:{max(2, int(r.pred_hotspot_7d / vmax * 22))}px'></span>{fmt(r.pred_hotspot_7d, 1)}</td>"
            f"<td>{fmt(r.aktual_7h_terakhir, 0)}</td></tr>" for r in sg_show.itertuples())
        st.markdown(
            '<div class="tbw"><table class="ev"><colgroup><col style="width:36px"><col><col style="width:76px"><col style="width:74px">'
            '<col style="width:50px"></colgroup><thead><tr><th title="Peringkat se-Kalimantan">#</th><th>Kecamatan</th><th>Status</th>'
            '<th title="Prediksi hotspot 7 hari ke depan">Prediksi</th><th title="Hotspot aktual 7 hari terakhir">Aktual</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

# ======================= BARIS 2 =======================
c4, c5, c6 = st.columns(WC, gap="small")
with c4.container(key="card_avp"):
    with st.container(key="head_avp"):
        st.markdown(f'<div class="ct">Aktual vs prediksi model <span>hotspot 7 hari ke depan · {esc(region_name)}</span></div>',
                    unsafe_allow_html=True)
    avp = load_avp()
    AV_S, AV_E = avp["date"].min(), avp["date"].max()
    v_s, v_e = max(start, AV_S), min(end, AV_E)
    if v_s > v_e:
        st.markdown(f'<div class="note" {MSG}>Evaluasi tersedia {tgl(AV_S)} – {tgl(AV_E)}. Pilih periode di dalam rentang itu.</div>',
                    unsafe_allow_html=True)
    else:
        d = avp[(avp["date"] >= v_s) & (avp["date"] <= v_e) & (avp["district_id"].isin(sel_ids))]
        g = d.groupby("date", observed=True)[["actual_7d", "pred_final"]].mean()
        if g.empty:
            st.markdown(f'<div class="note" {MSG}>Tidak ada data evaluasi untuk wilayah ini.</div>', unsafe_allow_html=True)
        else:
            one = len(sel_ids) == 1
            mean_a, mean_p = float(g["actual_7d"].mean()), float(g["pred_final"].mean())
            bias = (mean_p - mean_a) / mean_a * 100 if mean_a > 0 else np.nan
            ins(f'Rata-rata aktual <b>{fmt(mean_a, 2)}</b> · prediksi <b>{fmt(mean_p, 2)}</b> '
                f'{"per hari" if one else "per kecamatan-hari"} · bias <b>{fmt(bias, 1) + "%" if not np.isnan(bias) else "–"}</b> '
                f'(negatif = meremehkan)')
            span_v = (v_e - v_s).days + 1
            rv = None if span_v <= 150 else ("W" if span_v <= 900 else "MS")
            gg = g.resample(rv).mean() if rv else g
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=gg.index, y=gg["actual_7d"], name="Aktual", mode="lines", line=dict(color=NAVY, width=1.8)))
            fig.add_trace(go.Scatter(x=gg.index, y=gg["pred_final"], name="Prediksi model", mode="lines", line=dict(color=TEAL, width=1.8)))
            if v_s < pd.Timestamp("2026-01-01") <= v_e:
                fig.add_vrect(x0="2026-01-01", x1=v_e, fillcolor=ORANGE, opacity=0.06, line_width=0)
                fig.add_annotation(x="2026-01-01", y=1.0, yref="paper", text="holdout murni →", showarrow=False, xanchor="left",
                                   yanchor="bottom", font=dict(size=10, color=ORANGE))
            style_fig(fig)
            st.plotly_chart(fig, key="c1_avp", **PLOT)
            note(f"Titik = tanggal asal prediksi. Evaluasi {tgl(AV_S)} – {tgl(AV_E)}; mulai 1 Jan 2026 holdout murni, sebelumnya walk-forward.")

with c5.container(key="card_era"):
    with st.container(key="head_era"):
        e1, e2 = st.columns([1, 1.6], vertical_alignment="center")
        e1.markdown(f'<div class="ct" title="Rata-rata {esc(region_name)}">Iklim ERA5 <span>{esc(region_name)}</span></div>',
                    unsafe_allow_html=True)
        st.session_state.setdefault("era_var", "rain_mm")
        var = e2.segmented_control("Variabel iklim", list(ERA5_VARS), key="era_var",
                                   format_func=lambda k: ERA5_VARS[k][2], label_visibility="collapsed") or "rain_mm"
    vname, vcol, _vshort, vunit = ERA5_VARS[var]
    e_start, e_end = max(start, pd.Timestamp("2000-11-01")), min(end, ERA5_END)
    if e_start > e_end:
        st.markdown(f'<div class="note" {MSG}>Data ERA5 tersedia sampai {tgl(ERA5_END)}. Pilih periode yang lebih awal.</div>', unsafe_allow_html=True)
    else:
        lvl = "Kalimantan" if is_all_region else (sel_prov if sel_kab == ALL_KAB else None)
        e = load_era5(sel_ids_t, str(e_start.date()), str(e_end.date()), lvl)
        if e.empty:
            st.markdown(f'<div class="note" {MSG}>Tidak ada data ERA5 untuk wilayah ini.</div>', unsafe_allow_html=True)
        else:
            ser = e[var].dropna()
            if ser.empty:
                st.markdown(f'<div class="note" {MSG}>Tidak ada data untuk variabel ini.</div>', unsafe_allow_html=True)
            else:
                dp = 3 if var == "swvl1" else 2
                ins(f'<b>{vname}</b> ({vunit}) · rata-rata <b>{fmt(float(ser.mean()), dp)}</b> · '
                    f'maks <b>{fmt(float(ser.max()), dp)}</b> ({tgl(ser.idxmax())}) · '
                    f'min <b>{fmt(float(ser.min()), dp)}</b> ({tgl(ser.idxmin())})')
                nd = (e_end - e_start).days + 1
                rule = None if nd <= 200 else ("W" if nd <= 1100 else "MS")
                plot_s = ser.resample(rule).mean() if rule else ser
                fig = go.Figure(go.Scatter(
                    x=plot_s.index, y=plot_s.values, mode="lines", name=vname, line=dict(color=vcol, width=1.8),
                    fill="tozeroy" if var == "rain_mm" else None, fillcolor="rgba(31,111,181,0.12)" if var == "rain_mm" else None,
                    hovertemplate="%{y:." + str(dp) + "f} " + vunit + "<extra></extra>"))
                style_fig(fig, legend=False)
                fig.update_yaxes(title=dict(text=vunit, font=dict(size=10, color=INK2)))
                st.plotly_chart(fig, key="c1_era", **PLOT)
                agg_txt = "harian" if not rule else ("mingguan" if rule == "W" else "bulanan")
                note(f"Rata-rata {agg_txt}, seluruh kecamatan terpilih. ERA5 tersedia s.d. {tgl(ERA5_END)}.")

with c6.container(key="card_fi"):
    with st.container(key="head_fi"):
        st.markdown('<div class="ct" title="Kontribusi gain (%), geser untuk melihat semua">Fitur terpenting, top 20 '
                    '<span>gain (%) · geser</span></div>', unsafe_allow_html=True)
    fi = load_fitur().sort_values("gain_persen", ascending=False).head(20).copy()
    fi["Fitur"] = fi["fitur"].map(lambda n: LABEL.get(n, n))
    fi["Kelompok"] = fi["fitur"].map(grup)
    used = [g_ for g_ in G_COL if g_ in set(fi["Kelompok"])]
    st.markdown('<div class="fleg">' + "".join(f'<span><i style="background:{G_COL[g_]}"></i>{g_}</span>' for g_ in used) + "</div>",
                unsafe_allow_html=True)
    with st.container(height=200, border=False, key="fi_scroll"):
        fig = go.Figure(go.Bar(
            x=fi["gain_persen"], y=fi["Fitur"], orientation="h", marker_color=[G_COL[k] for k in fi["Kelompok"]],
            text=[fmt(v, 1) for v in fi["gain_persen"]], textposition="outside", cliponaxis=False, customdata=fi[["fitur", "Kelompok"]],
            hovertemplate="<b>%{y}</b><br>Gain: %{x:.2f}%<br>%{customdata[1]} · %{customdata[0]}<extra></extra>"))
        fig.update_yaxes(autorange="reversed", automargin=True, title=None, tickfont=dict(size=10.5, color=INK))
        fig.update_xaxes(showgrid=True, gridcolor=GRID, title=None, showticklabels=False, zeroline=False)
        style_fig(fig, 20 * 22 + 12, legend=False)
        fig.update_layout(hovermode="closest", margin=dict(l=8, r=36, t=4, b=4), bargap=0.3)
        st.plotly_chart(fig, **PLOT)

# ----------------------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------------------
bias26 = float(mt[(mt["split"] == "holdout") & (mt["model"] == "Model")].iloc[0]["bias_pct"])
_full = html.escape(
    f"Model memprediksi rata-rata bersyarat (Tweedie): cenderung meremehkan puncak di tahun api besar (bias holdout 2026 ≈ {fmt(bias26, 0)}%) "
    "dan melebihkan di tahun tenang. Hotspot di luar 7 hari pertama forecast adalah skenario klimatologis (tanpa cuaca masa depan). "
    "Sumber: hotspot MODIS FIRMS, iklim ERA5, batas kecamatan BPS ADM3. Detail metode dan istilah ada di tombol Catatan.", quote=True)
st.markdown(
    f'<div class="foot"><div>Info data <span class="pill"><span class="dot"></span>Hotspot terakhir: {tgl(LAST_OBS)} · Forecast s.d. {tgl(LAST_FC)}</span></div>'
    f'<div><b>MODIS FIRMS</b> · ERA5 · BPS ADM3 · <span class="w">Model cenderung meremehkan puncak tahun api besar (bias holdout 2026 ≈ {fmt(bias26, 0)}%)</span>'
    f' · <span class="tp" title="{_full}">Selengkapnya ⓘ</span></div></div>', unsafe_allow_html=True)
