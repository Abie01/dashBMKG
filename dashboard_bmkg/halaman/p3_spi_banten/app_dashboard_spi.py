"""Halaman 3: Proyeksi bulan kering (SPI) Banten 2026-2050 (Gemala Aleida Fitri).

Dijalankan oleh app.py (cangkang) lewat runpy dengan EMBED=True dan DATA_DIR=data_dashboard/. Header, tema/CSS, dan pilihan halaman ada di app.py dan tema.py.
Bisa juga dijalankan sendiri: streamlit run app_dashboard_spi.py (data di folder yang sama atau lewat HASIL_DIR; warna bawaan sama dengan tema.py).
Data   : ekspor notebook (sel 14d-14j): dashboard_*.csv/.gz/.json dan banten_kabkota.geojson.
Tampilan (mode mandiri): (biasa) dashboard satu layar  |  ?laporan=1 laporan naratif siap cetak PDF (berisi juga heatmap dan deret SPI)
URL tambahan (mode mandiri): ?embed=true (tanpa header/footer Streamlit)  |  ?tinggi=200 (paksa tinggi grafik kecil, px)  |  ?vh=900&vw=1600 (paksa ukuran jendela)
Ukuran layar: komponen ukuran_layar/ melaporkan tinggi dan lebar jendela, sehingga grafik dan huruf menyesuaikan diri (termasuk layar penuh).
Uji beda nyata: bila dashboard_uji.csv (notebook 14j) ada dan rentang tahun = seluruh horizon, dipakai uji formal (block bootstrap); selain itu pendekatan cepat 2 x galat baku.
Warna SPI: kelas dan warna mengikuti legenda peta SPI BMKG (SPI_KELAS di bawah).

Peta (v-sebelum-sesudah):
  - hanya satu peta: selisih proyeksi - masa lalu (pilihan Kering dan Bias dihapus)
  - pilihan Downscaling: "Sesudah (5 km)" = grid hasil downscaling; "Sebelum (GCM)" = sel GCM kasar dari hujan GCM mentah (berkas dashboard_gcm_sel.csv.gz dari notebook sel 14k). Skala warna keduanya sama

Perubahan legenda (v-legenda):
  - judul panel hanya berisi nama panel; arti garis/warna (gelap = rata-rata 5 tahun, putus = masa lalu, pekat = beda nyata, pucat = belum pasti, area abu = naik-turun alami, ★ = dipakai) pindah ke legenda grafik
  - warna chip "lebih jarang kering" disamakan menjadi hijau BMKG (#37a800), sama dengan batang, peta, dan kartu 3 jangka

Perubahan v-kontras:
  - kepastian = kepekatan warna, arah (merah/hijau) selalu terbaca; abu tidak lagi dipakai untuk "belum pasti"
  - skala warna peta mengikuti sebaran data, bukan batas naik-turun alami
  - peta dikunci (tidak bisa zoom/geser/scroll)
  - panel baru: deret SPI bulanan, heatmap peluang kering, ringkasan 3 jangka, tabel gerbang model, cara membaca tiap panel
"""
import json
import math
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots

# ------------------------------------------------------------------ pengaturan (boleh diubah)
PEMBUAT = "Gemala Aleida Fitri · Statistika dan Sains Data, IPB University"   # kosongkan bila tak perlu
JUDUL_PROYEK = "Downscaling GCM Hujan untuk Proyeksi Kekeringan (SPI) di Banten"   # ganti dengan judul proyekmu
H_KPI = 98                          # tinggi blok kartu angka (px)
H_BAN = 64                          # tinggi banner kesimpulan di atas kartu (px); banner ada DI DALAM iframe kartu supaya tidak tertimpa elemen lain
H_KECIL = 140                       # tinggi tiap grafik kecil (px); 2 baris grafik + banner + kartu muat di layar 1366x768 (bisa diubah lewat ?tinggi=)
H_SUM = 100                         # tinggi baris kartu ringkasan 3 jangka (px)
UKURAN_TEKS, UKURAN_TEKS_LAPORAN = 15, 15
LABEL_WILAYAH = "hover"               # nama kab/kota di peta: "hover" = titik kecil, nama muncul saat kursor diarahkan (interaktif); "teks" = tulisan tetap
PETA_STYLE = "carto-positron-nolabels"   # peta dasar tanpa nama kota di luar Banten (perlu plotly>=6)
PETA_AWAL = "Sesudah"               # tampilan awal peta: "Sesudah" (grid 5 km, setelah downscaling) atau "Sebelum" (sel GCM mentah, sebelum downscaling)

# [INTEGRASI] EMBED=True bila file ini dijalankan dari app.py utama (halaman 3); header, filter gelap, dan tema ikut app.py.
# Dijalankan sendiri (streamlit run app_dashboard_spi.py) tampilannya tetap seperti semula, termasuk ?laporan=1.
EMBED = bool(globals().get("EMBED", False))
if not EMBED: st.set_page_config(page_title="Bulan kering Banten 2026-2050", page_icon="🌧️", layout="wide", initial_sidebar_state="collapsed")
def _param(k): return str(st.query_params.get(k, "")).lower() in ("1", "true", "ya")
LAPORAN = False if EMBED else _param("laporan")

try:
    from tema import BLN, BLUE, BLUE_LINE, FONT, GRID, INK, INK2, ORANGE, TEAL, ZERO  # noqa: E402  (warna dan huruf satu sumber dengan halaman lain)
except ImportError:      # mode mandiri tanpa tema.py: nilai sama dengan tema.py
    BLUE, ORANGE, TEAL, BLUE_LINE, GRID, INK, INK2, ZERO = "#1f6fb5", "#e8710a", "#0f8b8d", "#9db4cc", "#e6ebf1", "#10243b", "#44566c", "#8793a3"
    BLN, FONT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"], "Poppins, 'Segoe UI', sans-serif"


def _angka(k, d, lo, hi):
    try: return int(np.clip(int(str(st.query_params.get(k, d))), lo, hi))
    except Exception: return d


def _ukuran_layar():
    """(tinggi, lebar) jendela aplikasi dalam px. Sumber: ?vh=&vw= (manual) atau komponen ukuran_layar/ (otomatis, ikut berubah saat layar penuh). (None, None) bila tak tersedia."""
    vh, vw = _angka("vh", 0, 0, 6000), _angka("vw", 0, 0, 10000)
    if vh and vw: return vh, vw
    try:
        komp = components.declare_component("ukuran_layar", path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "ukuran_layar"))
        v = komp(key="ukuran_layar", default=None)
        if isinstance(v, dict) and v.get("h") and v.get("w"): return int(v["h"]), int(v["w"])
    except Exception: pass
    return None, None


VH, VW = (None, None) if LAPORAN else _ukuran_layar()
FSKALA = float(np.clip(VW / 1366, 1.0, 1.45)) if VW else 1.0       # layar lebar (mis. layar penuh 1080p): huruf dan kartu ikut membesar
OVERHEAD_EMBED = 214                  # [INTEGRASI] header + bilah filter + footer app.py + jarak antar-elemen (px, tanpa kartu angka)
OVERHEAD = (OVERHEAD_EMBED if EMBED else 92) + (H_KPI + H_BAN + H_SUM + 8) * FSKALA                           # tinggi bagian atas (judul, kontrol, kartu), footer, dan jarak antar-elemen
if str(st.query_params.get("tinggi", "")).isdigit(): H_KECIL = _angka("tinggi", H_KECIL, 120, 700)       # paksa manual
elif VH: H_KECIL = int(np.clip((VH - OVERHEAD - 10) / 2, 120, 700))                                       # otomatis: dua baris grafik mengisi sisa tinggi layar
H_PETA = 2 * H_KECIL + 10           # peta = tinggi dua baris grafik
LEBAR_PETA = int(((VW or 1364) - 30) * 0.30)

CSS_UMUM = """<style>
header[data-testid="stHeader"], footer, #MainMenu, [data-testid="stToolbar"] {display:none !important;}
div[data-testid="stWidgetLabel"] {min-height:0; margin-bottom:0;}
@media print {
  html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"], section.main, .main, .block-container {height:auto !important; min-height:0 !important; max-height:none !important; overflow:visible !important;}
  [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {display:none !important;}
  * {-webkit-print-color-adjust:exact !important; print-color-adjust:exact !important;}
  .stPlotlyChart, [data-testid="stIFrame"], [data-testid="stTable"] {break-inside:avoid;}
}
</style>"""
CSS_DASH = """<style>
html {font-size: clamp(14px, 1.1vw, 21px);}
.stApp {background:#eef2f7;}
@page {size: A4 landscape; margin: 6mm;}
.block-container {padding:.45rem .8rem .2rem; max-width:100%;}
[data-testid="stVerticalBlock"] {gap:.3rem;}
div[data-baseweb="select"] > div {min-height:30px;}
[data-testid="stColumn"] {min-width:0;}
.ttl {font-size:clamp(.95rem, 1.2vw, 1.3rem); font-weight:700; color:#10243b; line-height:1.15; white-space:normal; overflow-wrap:anywhere;}
.sub {font-size:.72rem; color:#5b6b7f; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
div[data-testid="stWidgetLabel"] p {font-size:.65rem !important; font-weight:700; color:#5b6b7f; text-transform:uppercase; letter-spacing:.04em; margin:0 !important;}
.ttl, .sub, .foot {margin-bottom:0 !important;}
.foot {font-size:.68rem; color:#8793a3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.verd {background:#fff; border:1px solid #dde4ec; border-left:6px solid var(--c); border-radius:6px; padding:.3rem .7rem; font-size:.95rem; line-height:1.3; color:#10243b;}
.verd small {display:block; font-size:.74rem; color:#44566c; margin-top:.08rem;}
.pan {background:#fff; border:1px solid #dde4ec; border-left:4px solid #1f6fb5; border-radius:6px; padding:.4rem .65rem; margin-bottom:.4rem; font-size:.76rem; line-height:1.38; color:#44566c;}
.pan h4 {font-size:.74rem; text-transform:uppercase; letter-spacing:.04em; color:#10243b; margin:0 0 .15rem; padding:0;}
.pan .kes {background:#eef2f7; border-radius:4px; padding:.2rem .4rem; margin-top:.2rem; color:#10243b;}
.seksi {font-size:.8rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:#10243b; margin:.35rem 0 .05rem; padding:0;}
.seksi span {font-size:.72rem; font-weight:500; letter-spacing:0; text-transform:none; color:#5b6b7f; margin-left:.5rem;}
</style>"""
CSS_LAP = """<style>
html {font-size: __UT__px;}
.stApp {background:#fff;}
@page {size: A4 portrait; margin: 14mm;}
.block-container {max-width:920px; padding:1.2rem 1rem 2rem;}
h2 {color:#10243b; border-bottom:2px solid #1f6fb5; padding-bottom:.25rem; margin-top:1.3rem !important;}
h3 {color:#1f6fb5;}
.judul {font-size:1.7rem; font-weight:800; color:#10243b; line-height:1.2;}
.sublap {font-size:.85rem; color:#5b6b7f; margin-bottom:.6rem;}
.cara {font-size:.8rem; color:#44566c; background:#eef2f7; border-left:4px solid #1f6fb5; padding:.35rem .7rem; border-radius:4px; margin:.1rem 0 .6rem;}
.kes {font-size:.88rem; color:#10243b; background:#dbe8f5; border-left:4px solid #0f8b8d; padding:.4rem .7rem; border-radius:4px; margin:.1rem 0 .8rem;}
.jawab {font-size:1.1rem; background:#dbe8f5; border-left:6px solid #1f6fb5; border-radius:6px; padding:.7rem 1rem; line-height:1.5;}
</style>"""
if not EMBED: st.markdown((CSS_UMUM + (CSS_LAP if LAPORAN else CSS_DASH)).replace("__UT__", str(UKURAN_TEKS_LAPORAN if LAPORAN else UKURAN_TEKS)), unsafe_allow_html=True)

PROY, BASE, ABU = BLUE, INK2, "#7f95ad"      # biru = proyeksi, abu tua = masa lalu model, abu sedang = pembanding (lebih tegas dari BLUE_LINE)
TRANSF = TEAL                                # hijau-biru = model yang frekuensinya paling dekat pengamatan
# Palet kelas SPI mengikuti legenda BMKG (Indeks Presipitasi Terstandardisasi 1 bulanan)
SPI_KELAS = [(-99, -2.0, "Sangat kering", "#710201"), (-2.0, -1.5, "Kering", "#e60000"), (-1.5, -1.0, "Agak kering", "#e59901"), (-1.0, 1.0, "Normal", "#feffbe"),
             (1.0, 1.5, "Agak basah", "#99e702"), (1.5, 2.0, "Basah", "#37a800"), (2.0, 99, "Sangat basah", "#00a8e5")]


def spi_warna(v):
    """Kelas BMKG: SPI <= -2 sangat kering, <= -1,5 kering, <= -1 agak kering (sama dengan definisi bulan kering), -1 s/d 1 normal, >= 1 agak basah, >= 1,5 basah, >= 2 sangat basah."""
    if v <= -2.0: return SPI_KELAS[0][3]
    if v <= -1.5: return SPI_KELAS[1][3]
    if v <= -1.0: return SPI_KELAS[2][3]
    if v < 1.0: return SPI_KELAS[3][3]
    if v < 1.5: return SPI_KELAS[4][3]
    if v < 2.0: return SPI_KELAS[5][3]
    return SPI_KELAS[6][3]


ABU_N = "#c5d3e2"                               # (cadangan) abu lama; tidak dipakai lagi untuk batang
MERAH, BIRU = "#e60000", "#37a800"              # merah BMKG = lebih sering kering, hijau BMKG = lebih jarang kering (lebih basah)
MERAH_P, BIRU_P = "rgba(230,0,0,.42)", "rgba(55,168,0,.42)"      # pucat = belum beda nyata, tetapi arah tetap terbaca
WARNA_CHIP = {"red": MERAH, "blue": BIRU, "gray": ZERO, "amber": ORANGE, "green": TEAL}      # "blue" = lebih jarang kering = hijau BMKG (sama dengan batang, peta, dan kartu 3 jangka)
KERING = [[0, "#feffbe"], [0.33, "#e59901"], [0.66, "#e60000"], [1, "#710201"]]                    # persen bulan kering: normal (kuning pucat) -> agak kering -> kering -> sangat kering
SELISIH = [[0, "#37a800"], [0.25, "#99e702"], [0.5, "#feffbe"], [0.75, "#e59901"], [1, "#e60000"]]     # selisih / bias: hijau = lebih jarang kering, merah = lebih sering kering
PRESET = {"Sepanjang tahun": list(range(1, 13)), "Des-Feb": [12, 1, 2], "Mar-Mei": [3, 4, 5], "Jun-Agu": [6, 7, 8], "Sep-Nov": [9, 10, 11]}
NAMA_SKALA = {"SPI-3": "3 bln", "SPI-6": "6 bln", "SPI-12": "12 bln"}
NAMA_SKALA_PANJANG = {"SPI-3": "3 bulan (jangka pendek)", "SPI-6": "6 bulan (satu musim)", "SPI-12": "12 bulan (satu tahun)"}
ML = ["GLM Gamma", "Random Forest", "XGBoost", "Neural Net"]
SIM = {"sama": "●", "lebih": "▲", "kurang": "▼", "sedikit": "●"}
KATA = {"sama": "belum beda nyata", "lebih": "lebih sering kering", "kurang": "lebih jarang kering", "sedikit": "data terlalu sedikit"}
WARNA_KODE = {"sama": "gray", "lebih": "red", "kurang": "blue", "sedikit": "gray"}

# ------------------------------------------------------------------ data
FOLDER = os.environ.get("HASIL_DIR") or (globals().get("DATA_DIR") if EMBED else None) or os.path.dirname(os.path.abspath(__file__))      # [INTEGRASI] dari app.py: data_dashboard/


def jalur(nama):
    p, alt = os.path.join(FOLDER, nama), os.path.join(FOLDER, nama.replace(".csv.gz", "_csv.gz"))
    return p if os.path.exists(p) or not os.path.exists(alt) else alt


@st.cache_resource
def muat(ver):
    d = {"meta": json.load(open(jalur("dashboard_meta.json"), encoding="utf-8"))}
    for k, nm in [("b_grid", "dashboard_bulanan_per_grid.csv.gz"), ("b_base", "dashboard_baseline_bulan_grid.csv.gz"), ("grid", "dashboard_grid.csv"),
                  ("banding", "dashboard_model_banding.csv"), ("gerb", "dashboard_model_gerbang.csv"), ("reg", "dashboard_bulanan_regional.csv.gz"), ("sens", "dashboard_sensitivitas.csv"), ("kor", "dashboard_korelasi.csv"), ("uji", "dashboard_uji.csv"), ("gcm", "dashboard_gcm_sel.csv.gz")]:
        d[k] = pd.read_csv(jalur(nm)) if os.path.exists(jalur(nm)) else None
    d["gj"] = json.load(open(jalur("banten_kabkota.geojson"), encoding="utf-8")) if os.path.exists(jalur("banten_kabkota.geojson")) else None
    return d


try: D = muat(tuple(sorted((f, os.path.getmtime(os.path.join(FOLDER, f))) for f in os.listdir(FOLDER) if f.startswith("dashboard_") or f.endswith(".geojson"))))
except FileNotFoundError as e: st.error(f"Berkas data tidak ditemukan: {e.filename}"); st.stop()
meta, gj = D["meta"], D["gj"]
H0, H1 = int(meta["horizon"][0]), int(meta["horizon"][1])
if D["b_grid"] is None or D["b_base"] is None or D["grid"] is None: st.error("Data belum tersedia."); st.stop()
th_all = sorted(D["b_grid"]["tahun"].unique().tolist())
RO = bool(meta.get("rolling_origin"))      # True bila berkas hasil memuat uji rolling-origin (notebook lebih baru); notebook v23 hanya punya hold-out 2021-2025
UJI_TXT = "uji rolling-origin 1996-2020" if RO else "uji hold-out 2021-2025"
SEL_KECIL = "peringkat gabungan Tingkat 1 + 2" if RO else "CRPS Tingkat 1 terkecil"
SEL_PANJANG = "model dengan peringkat gabungan terbaik (CRPS Tingkat 1, QQ Tingkat 2, dan frekuensi bulan kering Tingkat 2) di antara model yang lebih baik daripada klimatologi pada Tingkat 1" if RO else "model dengan CRPS terkecil pada validasi sefase (Tingkat 1) di antara empat model"


def n(x, d=1, plus=False):
    s = f"{x:+.{d}f}" if plus else f"{x:.{d}f}"
    return s.replace(".", ",")


def se_kasar(v):
    v = pd.Series(v).dropna()
    return float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) >= 3 else float("nan")


def tafsir(sel, se):
    if not np.isfinite(se): return "sedikit"
    return "sama" if abs(sel) < 2 * se else ("lebih" if sel > 0 else "kurang")


# ------------------------------------------------------------------ peta
def _dalam(px, py, ring):
    x, y = ring[:, 0], ring[:, 1]; d = np.zeros(px.shape, bool)
    for xi, yi, xj, yj in zip(x, y, np.roll(x, -1), np.roll(y, -1)):
        if yi != yj: d ^= ((yi > py) != (yj > py)) & (px < (xj - xi) * (py - yi) / (yj - yi) + xi)
    return d


def nama_pendek(idx):
    """Buang awalan Kab./Kota; bila nama kembar (Tangerang, Serang) beri akhiran (Kab)/(Kota)."""
    inti = [x.replace("Kab. ", "").replace("Kota ", "") for x in idx]
    return [k + (" (Kab)" if x.startswith("Kab.") else " (Kota)") if inti.count(k) > 1 else k for k, x in zip(inti, idx)]


@st.cache_resource
def wilayah_grid(ver):
    gr = D["grid"].sort_values("grid_id").reset_index(drop=True); nama = pd.Series([None] * len(gr), dtype=object); lab = []
    if gj is None: return gr.assign(wilayah=nama), pd.DataFrame(columns=["nama", "lon", "lat"])
    px, py = gr["lon"].to_numpy(float), gr["lat"].to_numpy(float)
    for f in gj["features"]:
        nm = f["properties"].get("nama", "?"); dalam = np.zeros(len(px), bool); besar = None
        polys = [f["geometry"]["coordinates"]] if f["geometry"]["type"] == "Polygon" else list(f["geometry"]["coordinates"])
        for poly in polys:
            ext = np.asarray(poly[0], float); m = _dalam(px, py, ext)
            for h in poly[1:]: m &= ~_dalam(px, py, np.asarray(h, float))
            dalam |= m; luas = np.ptp(ext[:, 0]) * np.ptp(ext[:, 1])
            if besar is None or luas > besar[0]: besar = (luas, ext[:, 0].mean(), ext[:, 1].mean())
        nama[dalam & nama.isna().to_numpy()] = nm
        if besar: lab.append((nm, besar[1], besar[2]))
    lab = pd.DataFrame(lab, columns=["nama", "lon", "lat"]); lab["nama"] = nama_pendek(lab["nama"].tolist())
    return gr.assign(wilayah=nama.to_numpy()), lab


gr_ref, LAB = wilayah_grid(len(D["grid"]))


def _koord(g):
    if isinstance(g, (list, tuple)):
        if g and isinstance(g[0], (int, float)): yield g
        else:
            for x in g: yield from _koord(x)


def batas_peta(xs, ys, h):
    """(barat, timur, selatan, utara): gabungan seluruh kotak grid dan garis batas kab/kota, ditambah ruang 8-10%."""
    w, e, so, u = xs.min() - h, xs.max() + h, ys.min() - h, ys.max() + h
    if gj is not None:
        for f in gj["features"]:
            for c in _koord(f["geometry"]["coordinates"]): w, e, so, u = min(w, c[0]), max(e, c[0]), min(so, c[1]), max(u, c[1])
    px, py = (e - w) * 0.10, (u - so) * 0.08
    return w - px, e + px, so - py, u + py


def fig_peta(df, kol, zmin, zmax, satuan, warna, tinggi, lebar=400, zmid=None, mask=None, catatan=None, legenda=None, sel=None):
    """mask (Series bool): kotak True = beda nyata (warna pekat); kotak lain lebih pucat tetapi tetap berwarna sesuai arah. Peta dikunci: tidak bisa digeser/diperbesar.
    sel (DataFrame sel_gcm, lon_w, lon_e, lat_s, lat_n, selisih): bila diberikan, yang digambar adalah sel GCM kasar (sebelum downscaling), bukan grid 5 km; df tetap dipakai untuk pusat dan zoom peta.
    legenda: [(nama, warna)] -> entri legenda (penanda bulat tanpa data); arti pekat/pucat/merah/hijau dijelaskan di legenda, bukan di judul."""
    xs, ys = np.unique(df["lon"].round(4)), np.unique(df["lat"].round(4)); h = float(np.median(np.diff(xs)) / 2) if len(xs) > 1 else 0.025

    wmean = df.groupby("wilayah")[kol].mean() if "wilayah" in df and df["wilayah"].notna().any() else None
    def hov(d):
        t_ = []
        for i_, w_, z_ in zip(d.index, d["wilayah"], d[kol]):
            br = w_ if isinstance(w_, str) else "Di luar batas kab/kota"
            t = f"<b>{br}</b><br>kotak ini: {n(z_, 1, zmid is not None)} {satuan}"
            if wmean is not None and isinstance(w_, str): t += f"<br>rata-rata wilayah: {n(wmean[w_], 1, zmid is not None)} {satuan}"
            if mask is not None and i_ in mask.index: t += "<br>" + ("<b>beda nyata</b>" if bool(mask.loc[i_]) else "belum pasti")
            t_.append(t)
        return t_
    def trace(d, op, bar):
        kotak = {"type": "FeatureCollection", "features": [{"type": "Feature", "id": str(int(g)), "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[lo - h, la - h], [lo + h, la - h], [lo + h, la + h], [lo - h, la + h], [lo - h, la - h]]]}} for g, lo, la in zip(d["grid_id"], d["lon"], d["lat"])]}
        return go.Choroplethmap(geojson=kotak, locations=d["grid_id"].astype(int).astype(str), z=d[kol], text=hov(d), colorscale=warna, zmin=zmin, zmax=zmax, zmid=zmid, showscale=bar, showlegend=False,
                                marker=dict(opacity=op, line=dict(width=0)), colorbar=dict(title=dict(text=satuan, font=dict(size=10), side="top"), thickness=9, len=0.5, tickfont=dict(size=10), x=0.995),
                                hovertemplate="%{text}<extra></extra>")
    def trace_sel(d):
        kotak = {"type": "FeatureCollection", "features": [{"type": "Feature", "id": str(int(g)), "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[w, so], [e, so], [e, u], [w, u], [w, so]]]}} for g, w, e, so, u in zip(d["sel_gcm"], d["lon_w"], d["lon_e"], d["lat_s"], d["lat_n"])]}
        return go.Choroplethmap(geojson=kotak, locations=d["sel_gcm"].astype(int).astype(str), z=d[kol], text=[f"Sel GCM {int(g)}" for g in d["sel_gcm"]], colorscale=warna, zmin=zmin, zmax=zmax, zmid=zmid, showscale=True, showlegend=False,
                                marker=dict(opacity=0.88, line=dict(width=1.2, color="#33474a")), colorbar=dict(title=dict(text=satuan, font=dict(size=10), side="top"), thickness=9, len=0.5, tickfont=dict(size=10), x=0.995),
                                hovertemplate="<b>%{text}</b><br>%{z:+.1f} " + satuan + "<extra></extra>")
    fig = go.Figure()
    if sel is not None: fig.add_trace(trace_sel(sel))
    elif mask is None: fig.add_trace(trace(df, 0.88, True))
    elif not bool(mask.any()): fig.add_trace(trace(df, 0.82, True))
    else: fig.add_trace(trace(df, 0.62, True)); fig.add_trace(trace(df[mask.to_numpy()], 0.95, False))
    for nm_, wr_ in (legenda or []): fig.add_trace(go.Scattermap(lon=[None], lat=[None], mode="markers", marker=dict(size=11, color=wr_), name=nm_, showlegend=True, hoverinfo="skip"))      # warna transparan = hanya teks HTML berwarna di nama
    lon_r, lat_r = max(xs.max() - xs.min() + 2 * h, 0.2) * 1.08, max(ys.max() - ys.min() + 2 * h, 0.2) * 1.08 / np.cos(np.radians(float(ys.mean())))
    zoom = float(np.clip(min(np.log2(360 * lebar / (512 * lon_r)), np.log2(360 * tinggi / (512 * lat_r))), 5, 11))      # 512 px/tile (MapLibre)
    lay = dict(style=PETA_STYLE, center=dict(lat=float((ys.min() + ys.max()) / 2), lon=float((xs.min() + xs.max()) / 2)), zoom=zoom)
    if gj is not None: lay["layers"] = [dict(sourcetype="geojson", source=gj, type="line", color="#33474a", line=dict(width=1.3), below="")]
    w_, e_, s_, u_ = batas_peta(xs, ys, h); lay["bounds"] = dict(west=float(w_), east=float(e_), south=float(s_), north=float(u_))      # pas ke seluruh grid dan batas wilayah
    fig.update_layout(map=lay, dragmode=False)       # dragmode=False: tidak bisa digeser
    if len(LAB) and LABEL_WILAYAH == "teks": fig.add_trace(go.Scattermap(lon=LAB["lon"], lat=LAB["lat"], mode="text", text=LAB["nama"], textfont=dict(size=10, color="#10243b"), hoverinfo="skip", showlegend=False))
    elif len(LAB):      # interaktif: titik kecil di tiap kab/kota; nama dan ringkasan muncul saat kursor diarahkan (peta tetap bersih)
        wm = {} if (wmean is None or sel is not None) else dict(zip(nama_pendek(wmean.index.tolist()), wmean.values))
        info = [f"<b>{nm}</b>" + (f"<br>rata-rata wilayah: {n(wm[nm], 1, zmid is not None)} {satuan}" if nm in wm else "") for nm in LAB["nama"]]
        fig.add_trace(go.Scattermap(lon=LAB["lon"], lat=LAB["lat"], mode="markers", marker=dict(size=10, color="white", opacity=0.95), text=info, hovertemplate="%{text}<extra></extra>", showlegend=False))
    if catatan: fig.add_annotation(text=catatan, xref="paper", yref="paper", x=0.01, y=0.99, xanchor="left", yanchor="top", showarrow=False, align="left", font=dict(size=10.5, color="#44566c"), bgcolor="rgba(255,255,255,.88)", borderpad=3)
    return fig


def gambar(fig, h, judul=None, legenda=False, tetap=False, leg_pos="atas"):
    """tetap=True: grafik dikunci (tanpa scroll-zoom, double-click, dan geser); dipakai untuk peta.
    legenda=True: tampilkan legenda. leg_pos="atas": satu baris dengan judul panel (rata kanan; rata kiri bila tanpa judul); "dalam": kotak kecil di kiri-bawah (peta)."""
    fig.update_layout(height=h, margin=dict(l=2, r=2, t=2, b=2), font=dict(size=11, color=INK2, family=FONT), hoverlabel=dict(font_size=11, bgcolor="#fff", font_color=INK), plot_bgcolor="white", paper_bgcolor="white", separators=",.", showlegend=legenda, uniformtext=dict(minsize=9, mode="hide"))
    if leg_pos == "dalam": fig.update_layout(legend=dict(orientation="v", x=0.01, y=0.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,.88)", font_size=10, itemsizing="constant"))
    else: fig.update_layout(legend=dict(orientation="h", x=1 if judul else 0, xanchor="right" if judul else "left", y=1.0, yanchor="bottom", font_size=9.5, itemsizing="constant", tracegroupgap=0, itemwidth=30))      # di strip atas, sebaris dengan judul
    if judul or (legenda and leg_pos == "atas"): fig.update_layout(margin=dict(l=2, r=2, t=24, b=2))
    if judul: fig.update_layout(title=dict(text=judul.upper(), x=0.005, xanchor="left", y=0.99, yanchor="top", font=dict(size=11.5, color=INK)))      # judul panel DI DALAM grafik (hanya nama panel; arti garis/warna ada di legenda)
    fig.update_xaxes(showgrid=False, linecolor=GRID); fig.update_yaxes(gridcolor=GRID, zeroline=False)
    if FSKALA > 1.01:      # layar lebar: perbesar huruf grafik (sumbu, label batang, judul, catatan)
        fs = lambda v: round(v * FSKALA, 1); fig.update_layout(font_size=fs(11), legend_font_size=fs(9.5 if leg_pos == "atas" else 10)); fig.update_xaxes(tickfont_size=fs(10)); fig.update_yaxes(tickfont_size=fs(10))
        for tr in fig.data:
            try: tr.textfont.size = fs(10)
            except Exception: pass
        try: fig.layout.title.font.size = fs(11.5)
        except Exception: pass
        for an in fig.layout.annotations: an.font.size = fs(10.5)
    cfg = dict(displaylogo=False, displayModeBar=False)
    if tetap: cfg.update(scrollZoom=False, doubleClick=False, showAxisDragHandles=False)
    try: st.plotly_chart(fig, width="stretch", config=cfg)
    except TypeError: st.plotly_chart(fig, use_container_width=True, config=cfg)


def pilih(opsi, key, label, default=None, fmt=None):
    default = default or opsi[0]
    if hasattr(st, "segmented_control"):
        v = st.segmented_control(label, opsi, default=default, key=key, format_func=fmt or (lambda x: x))
        return default if v is None else v
    return st.radio(label, opsi, index=opsi.index(default), key=key, format_func=fmt or (lambda x: x), horizontal=True)


def iframe(html, tinggi):
    if hasattr(st, "iframe"): st.iframe(html, height=tinggi)          # Streamlit baru
    else: components.html(html, height=tinggi)                        # Streamlit lama


def seksi(judul, ket=""):
    """Judul seksi. Memakai <p> (bukan <div>): Streamlit memberi margin negatif pada wadah markdown yang hanya diimbangi oleh <p>; dengan <div> elemen berikutnya tertarik ke atas dan menimpa judul."""
    st.markdown(f'<p style="font-size:.8rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#10243b;line-height:1.4;margin:.45rem 0 1rem;padding:0">{judul}<span style="font-size:.72rem;font-weight:500;letter-spacing:0;text-transform:none;color:#5b6b7f;margin-left:.5rem">{ket}</span></p>', unsafe_allow_html=True)


# ------------------------------------------------------------------ analisis (dipakai dashboard dan laporan)
def _nyata_bh(sel, se, q=0.05):
    """Beda nyata dengan koreksi uji berganda (Benjamini-Hochberg, FDR q) dari z = selisih / galat baku (hampiran normal). Mengembalikan bool dengan indeks sama."""
    sel = pd.Series(sel).astype(float); se = pd.Series(se, index=sel.index).astype(float)
    z = (sel / se).abs(); ok = z.notna() & np.isfinite(z); p = pd.Series(np.nan, index=sel.index); p[ok] = [math.erfc(v / math.sqrt(2)) for v in z[ok]]
    out = pd.Series(False, index=sel.index); pv = p[ok].sort_values(); m = len(pv)
    if m:
        lolos = pv.to_numpy() <= q * np.arange(1, m + 1) / m
        if lolos.any(): out[pv.index[: int(np.max(np.where(lolos)[0])) + 1]] = True
    return out


def ringkas(skala, bulan, t0, t1):
    G = D["b_grid"][D["b_grid"]["SPI"] == skala]; B = D["b_base"][D["b_base"]["SPI"] == skala]
    gs = G[G["bulan"].isin(bulan) & G["tahun"].between(t0, t1)]; bs = B[B["bulan"].isin(bulan)]
    if gs.empty: return None
    R = dict(skala=skala, bulan=bulan, t0=t0, t1=t1)
    R["per_th"] = gs.groupby("tahun")["p_kering"].mean().mul(100)
    R["proy"], R["base"], R["ref"] = float(gs["p_kering"].mean() * 100), float(bs["kering_model_pct"].mean()), float(bs["kering_target_pct"].mean())
    R["sel"] = R["proy"] - R["base"]; R["se"] = se_kasar(R["per_th"]); R["amb"] = 2 * R["se"]; R["kode"] = tafsir(R["sel"], R["se"])
    agg = gs.groupby("grid_id")["p_kering"].mean().mul(100).rename("p_kering").reset_index().merge(bs.groupby("grid_id")[["kering_model_pct", "kering_target_pct"]].mean().reset_index(), on="grid_id").merge(gr_ref, on="grid_id")
    agg["selisih"] = agg["p_kering"] - agg["kering_model_pct"]
    yg = gs.groupby(["grid_id", "tahun"])["p_kering"].mean().mul(100).unstack("tahun")        # naik-turun antar-tahun tiap kotak
    se_g = (yg.std(axis=1, ddof=1) / np.sqrt(yg.notna().sum(axis=1))).rename("se_g").reset_index()
    agg = agg.merge(se_g, on="grid_id", how="left"); agg["nyata"] = _nyata_bh(agg["selisih"], agg["se_g"])     # kotak "beda nyata" bila selisih >= 2 x galat baku
    R["agg"] = agg[agg["wilayah"].notna()] if gj is not None else agg
    rk = R["agg"].dropna(subset=["wilayah"]).groupby("wilayah")[["p_kering", "kering_model_pct"]].mean().sort_values("p_kering") if gj is not None else pd.DataFrame()
    if len(rk): rk.index = nama_pendek(rk.index.tolist())
    R["rk"] = rk
    R["prof"] = G[G["tahun"].between(t0, t1)].groupby("bulan")["p_kering"].mean().mul(100); R["pb"] = B.groupby("bulan")["kering_model_pct"].mean().reindex(R["prof"].index)
    R["dbulan"] = R["prof"] - R["pb"]
    ym = G[G["tahun"].between(t0, t1)].groupby(["bulan", "tahun"])["p_kering"].mean().mul(100).unstack("tahun")
    se_m = ym.std(axis=1, ddof=1) / np.sqrt(ym.notna().sum(axis=1))
    R["bulan_nyata"] = _nyata_bh(R["dbulan"], se_m.reindex(R["dbulan"].index))      # bulan "beda nyata" bila selisih >= 2 x galat baku antar-tahun
    R["uji"], R["ci"] = "cepat", None
    U = D.get("uji"); MUSIM_KODE = {"Des-Feb": "DJF", "Mar-Mei": "MAM", "Jun-Agu": "JJA", "Sep-Nov": "SON"}
    if U is not None and t0 == H0 and t1 == H1 and {"SPI", "jenis", "unit", "nyata_fdr", "ci_lo", "ci_hi"} <= set(U.columns):      # uji formal dari notebook 14j (seluruh horizon)
        U = U[U["SPI"] == skala]; ub = U[U["jenis"] == "bulan"].set_index("bulan")
        if len(ub) == 12: R["bulan_nyata"] = ub["nyata_fdr"].astype(bool).reindex(R["dbulan"].index).fillna(False); R["uji"] = "resmi"
        semua = sorted(bulan) == list(range(1, 13)); kunci = next((k for k, v in PRESET.items() if sorted(v) == sorted(bulan) and k in MUSIM_KODE), None)
        ur = U[U["jenis"] == "wilayah"] if semua else U[(U["jenis"] == "musim") & (U["unit"] == MUSIM_KODE.get(kunci, "?"))]
        if len(ur):
            r0 = ur.iloc[0]; R["ci"] = (float(r0["ci_lo"]), float(r0["ci_hi"])); R["amb"] = (R["ci"][1] - R["ci"][0]) / 2
            R["kode"] = ("lebih" if R["sel"] > 0 else "kurang") if bool(r0["nyata_fdr"]) else "sama"; R["uji"] = "resmi"
        if semua:
            ug = U[U["jenis"] == "grid"].set_index("grid_id")["nyata_fdr"]
            if len(ug): R["agg"] = R["agg"].assign(nyata=R["agg"]["grid_id"].map(ug).fillna(False).astype(bool))
    return R


def model_selisih(skala, t0=None, t1=None, R=None):
    """Selisih per model (proyeksi - masa lalu model). Data pembanding per TAHUN (tanpa dimensi bulan), jadi mengikuti slider tahun tetapi TIDAK mengikuti pilihan musim.
    Bila seluruh bulan dipilih, model yang dipakai memakai angka yang sama dengan kartu Selisih supaya keduanya konsisten."""
    out = {}
    if D["banding"] is None: return out
    dm = D["banding"][(D["banding"]["SPI"] == skala) & D["banding"]["model"].isin(ML)]
    if t0 is not None: dm = dm[dm["tahun"].between(t0, t1)]
    for nm_, g_ in dm.groupby("model"):
        if g_["baseline_model_sendiri_pct"].notna().any() and g_["n_bulan_valid"].sum() > 0:
            out[nm_] = float(np.average(g_["kering_pct_mean"], weights=g_["n_bulan_valid"]) - g_["baseline_model_sendiri_pct"].dropna().iloc[0])
    if R is not None and UTAMA in out and sorted(R["bulan"]) == list(range(1, 13)): out[UTAMA] = float(R["sel"])
    return out


def arah_model(sm):
    v = list(sm.values()); pos, neg = sum(x > 0 for x in v), sum(x < 0 for x in v); N = len(v)
    return dict(N=N, pos=pos, neg=neg, n_s=max(pos, neg) if N else 0, arah=("kurang" if neg > pos else "lebih" if pos > neg else None))


UTAMA = next((m_ for m_ in ML if m_ in str(meta.get("model", ""))), None)
TRANSFER = (meta.get("model_transfer_terbaik") or {}).get("model")
if TRANSFER is None and D["gerb"] is not None and {"c_kering_pct", "acuan_c"} <= set(D["gerb"].columns): _g = D["gerb"].set_index("model"); TRANSFER = (_g["c_kering_pct"] - _g["acuan_c"]).abs().idxmin()


def keyakinan(R, am):
    ho = meta.get("holdout") or {}; rl = meta.get("rolling_origin") or {}; ka = (meta.get("konsistensi_arah") or {}).get("jendela") or []
    jd = next((j for j in ka if j["jendela"] == f"{H0}-{H1}"), None); luar = (meta.get("baris_prediktor_luar_rentang_pct") or {}).get(f"{H0}-{H1}")
    if RO: UJI_ITEM = ("Uji rolling-origin", "Lebih baik daripada klimatologi pada rolling-origin 1996-2020 (model dipakai)", bool(rl.get("lebih_baik")), f"CRPSS {n(rl['crpss'], 3, True)}, positif {rl['fold_positif']} dari {rl['n_fold']} lipatan")
    else: UJI_ITEM = ("Uji 2021-25", "Lebih baik daripada klimatologi pada hold-out 2021-2025", bool(ho.get("lebih_baik_dari_klimatologi")), f"CRPSS {n(ho['crpss_t1'], 3, True)}, positif {ho['tahun_positif']} dari {ho['n_tahun']} tahun" if ho else "belum tersedia di berkas hasil")
    cek = [("Model terbaik", "Model dipilih sebagai yang terbaik di antara empat model (tuning setara)", "terbaik dari 4" in str(meta.get("status_gerbang", "")), str(meta.get("status_gerbang", "-"))),
           UJI_ITEM,
           ("Arah GCM", "Arah perubahan hujan sejalan dengan hujan mentah GCM", jd is not None and not jd["berlawanan"], f"GCM mentah {n(jd['gcm_pr_mentah_pct'], 1, True)}% vs model {n(jd['model_pct'], 1, True)}%" if jd else "belum tersedia"),
           ("Input di luar rentang", "Data masukan yang di luar rentang latih < 10%", luar is not None and luar < 10, f"{n(luar, 0)}% baris prediktor di luar rentang" if luar is not None else "belum tersedia"),
           ("Bias model", "Baseline model dekat pengamatan (selisih ≤ 3 poin)", abs(R["base"] - R["ref"]) <= 3, f"model {n(R['base'], 0)} vs pengamatan {n(R['ref'], 0)} dari 100 bulan"),
           ("Model searah", "Semua model memberi arah yang sama", am["N"] >= 2 and am["n_s"] == am["N"], f"{am['n_s']} dari {am['N']} model searah")]
    n_ok = sum(c[2] for c in cek); yak, yak_c = (f"{n_ok}/6", "green" if n_ok >= 5 else "amber")      # merah khusus arah kering, bukan status keyakinan
    return cek, n_ok, yak, yak_c


KPI_CSS = """<style>
body {margin:0; padding:2px 1px 0; zoom:__Z__; background:__BG__; font-family:"Poppins", "Segoe UI", Arial, sans-serif; color:#10243b; -webkit-print-color-adjust:exact; print-color-adjust:exact;}
.kpi {display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:8px;}
.tile {background:#fff; border:1px solid #dde4ec; border-top:4px solid var(--c); border-radius:7px; padding:5px 10px 6px; height:88px; box-sizing:border-box; overflow:hidden;}
.k {font-size:10.5px; font-weight:700; color:#44566c; text-transform:uppercase; letter-spacing:.04em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.v {font-size:24px; font-weight:700; line-height:1.15; white-space:nowrap; color:#10243b;}
.v small {font-size:11px; font-weight:500; color:#5b6b7f;}
.s {font-size:11px; color:#44566c; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.chip {max-width:100%; overflow:hidden; text-overflow:ellipsis; vertical-align:top; display:inline-block; padding:0 8px; border-radius:9px; font-size:10px; font-weight:700; color:#fff; margin-top:2px; white-space:nowrap;}
.red {background:#e60000;} .blue {background:#37a800;} .gray {background:#5b6b7f;} .amber {background:#e8710a;} .green {background:#0f8b8d;}
.verd {background:#fff; border:1px solid #dde4ec; border-left:6px solid var(--c); border-radius:6px; padding:5px 10px; font-size:14px; line-height:1.3; margin:0 1px 7px;}
.verd small {display:block; font-size:11px; color:#44566c; margin-top:2px; line-height:1.3;}
.dot {display:inline-block; width:11px; height:11px; border-radius:50%; margin:0 2px 0 0; vertical-align:middle; background:#d9dee4;} .dot.ok {background:#0f8b8d;} .dot.no {background:#e8710a;}
.insrow {margin-top:7px; white-space:nowrap; overflow:hidden;}
.ins {display:inline-block; font-size:11px; color:#44566c; background:#fff; border:1px solid #dde4ec; border-radius:12px; padding:1px 9px 1px 7px; margin:0 5px 0 0;}
.ins i {display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px;}
</style>"""


PENDEK = {"Model terbaik": "model terbaik", "Uji rolling-origin": "uji rolling-origin", "Uji 2021-25": "uji 2021-25", "Arah GCM": "arah GCM", "Input di luar rentang": "input di luar rentang", "Bias model": "bias model", "Model searah": "model searah"}


def kartu_html(R, sm, chips=False, bg="#eef2f7", atas="", zoom=1.0):
    """Empat kartu: (1) selisih, (2) rentang 4 model, (3) ketepatan masa lalu model, (4) keyakinan (6 titik = 6 syarat). Angka mutlak proyeksi tidak ditampilkan."""
    am = arah_model(sm); cek, n_ok, yak, yak_c = keyakinan(R, am); kode = R["kode"]
    def tile(k, v, kecil, s_, chip, cls, warna, tip=""): return f'<div class="tile" style="--c:{warna}" title="{tip}"><div class="k">{k}</div><div class="v">{v} <small>{kecil}</small></div><div class="s">{s_}</div><span class="chip {cls}">{chip}</span></div>'
    bias = R["base"] - R["ref"]; gagal = [c[0] for c in cek if not c[2]]
    tip_y = " | ".join(("✓ " if c[2] else "✗ ") + c[1] for c in cek).replace('"', "'")
    def _titik(c): return '<span class="dot ' + ("ok" if c[2] else "no") + '" title="' + ("✓ " if c[2] else "✗ ") + c[1].replace('"', "'") + '"></span>'
    titik = "".join(_titik(c) for c in cek)
    if bias > 3: b_chip, b_cls = "▲ MODEL TERLALU KERING", "amber"
    elif bias < -3: b_chip, b_cls = "▼ MODEL TERLALU BASAH", "amber"
    else: b_chip, b_cls = "● DEKAT PENGAMATAN", "green"
    if len(sm) >= 2:
        searah = am["N"] >= 2 and am["n_s"] == am["N"]
        m_v, m_s = f'{n(min(sm.values()), 1, True)} s/d {n(max(sm.values()), 1, True)}', f'selisih menurut {am["N"]} model' + ("" if len(R["bulan"]) == 12 else " · seluruh bulan")
        m_chip, m_cls = ("● SEMUA MODEL SEARAH", "green") if searah else ("▲ MODEL TIDAK SEPAKAT", "amber")
    else: m_v, m_s, m_chip, m_cls = "-", "data perbandingan model belum ada", "● BELUM ADA", "gray"
    T = [tile("Selisih bulan kering", n(R["sel"], 1, True), "dari 100 bulan", (f'proyeksi − masa lalu · selang 95%: {n(R["ci"][0], 1, True)} s/d {n(R["ci"][1], 1, True)}' if R.get("ci") else f'proyeksi − masa lalu · naik-turun alami ±{n(R["amb"], 1)}') if np.isfinite(R["amb"]) else "proyeksi − masa lalu model", f'{SIM[kode]} {KATA[kode].upper()}', WARNA_KODE[kode], WARNA_CHIP[WARNA_KODE[kode]],
               "Selisih frekuensi bulan kering (proyeksi dikurangi masa lalu model). Bila lebih kecil dari batas naik-turun alami, belum bisa disebut perubahan."),
         tile("Rentang antar-model", m_v, "bln/100", m_s, m_chip, m_cls, WARNA_CHIP[m_cls], "Selisih yang sama dihitung dengan GLM, Random Forest, XGBoost, dan Neural Net."),
         tile("Masa lalu 1981-2010", f'{n(R["base"], 0)} vs {n(R["ref"], 0)}', "model vs nyata", "bulan kering per 100 bulan", b_chip, b_cls, WARNA_CHIP[b_cls], "Model dibandingkan pengamatan CHIRPS pada periode yang sama. Bila beda jauh, baca selisih, bukan angka mutlak."),
         tile("Syarat terpenuhi", f'{yak} {titik}', "", ("belum: " + ", ".join(PENDEK.get(g, g) for g in gagal)) if gagal else "semua syarat terpenuhi", f"{n_ok} DARI 6 SYARAT TERPENUHI", yak_c, WARNA_CHIP[yak_c], tip_y)]
    dm = R["dbulan"]; ny = R["bulan_nyata"].reindex(dm.index).fillna(False)
    naik = [BLN[m - 1] for m, v in dm.items() if v >= 3 and ny[m]]; turun = [BLN[m - 1] for m, v in dm.items() if v <= -3 and ny[m]]
    html = KPI_CSS.replace("__BG__", bg).replace("__Z__", str(round(zoom, 3))) + atas + '<div class="kpi">' + "".join(T) + "</div>"
    return html, cek, n_ok, yak, yak_c, am, naik, turun


def banner(R, sm, am):
    """Kalimat kesimpulan utama + catatan satu baris, dalam bahasa awam. Mengembalikan (html, warna)."""
    per, sel, amb, kode = f'{R["t0"]}-{R["t1"]}', R["sel"], R["amb"], R["kode"]; amb_t = (f"selang 95%: {n(R['ci'][0], 1, True)} s/d {n(R['ci'][1], 1, True)}" if R.get("ci") else f"±{n(amb, 1)}") if np.isfinite(amb) else "-"
    utama = {"sama": f'<b>Belum ada perubahan yang bisa dipastikan.</b> Bulan kering {per} hanya {n(abs(sel), 1)} dari 100 bulan {"lebih sering" if sel > 0 else "lebih jarang"} dibanding 1981-2010, masih di dalam naik-turun alami ({amb_t}).',
             "lebih": f'<b>Bulan kering diproyeksikan lebih sering</b> pada {per}: {n(sel, 1, True)} dari 100 bulan dibanding 1981-2010, melampaui naik-turun alami ({amb_t}).',
             "kurang": f'<b>Bulan kering diproyeksikan lebih jarang</b> pada {per}: {n(sel, 1, True)} dari 100 bulan dibanding 1981-2010, melampaui naik-turun alami ({amb_t}).',
             "sedikit": "<b>Data tahun terlalu sedikit untuk disimpulkan.</b> Pilih rentang tahun minimal 3 tahun."}[kode]
    kor = D.get("kor")
    if kor is not None and "lolos_fdr_gcm_target" in kor.columns:
        nk, nl = len(kor), int(kor["lolos_fdr_gcm_target"].astype(bool).sum())
        gcm_t = f"Model iklim (GCM) tidak sefase dengan hujan nyata ({nl} dari {nk} uji korelasi lolos)" if nl == 0 else f"Model iklim (GCM) hanya sefase dengan hujan nyata pada {nl} dari {nk} uji korelasi"
    else: gcm_t = "Model iklim (GCM) berjalan bebas dan tidak sefase dengan hujan nyata"
    ny_b, ny_g = int(R["bulan_nyata"].fillna(False).sum()), int(R["agg"]["nyata"].sum())
    cat = (f"Beda nyata: {ny_b} dari {len(R['bulan_nyata'])} bulan, {ny_g} dari {len(R['agg'])} kotak peta. " + gcm_t + ", jadi hanya selisih relatif yang dibaca." + (" " + str(meta.get("klaim_arah_teks", "")) if meta.get("klaim_arah") == "belum_dapat_disimpulkan" else "")
           + (" Model statistik tidak sepakat arahnya." if am["N"] >= 2 and am["n_s"] < am["N"] else ""))
    return f'<div class="verd" style="--c:{WARNA_CHIP[WARNA_KODE[kode]]}">{utama}<small>{cat}</small></div>', WARNA_CHIP[WARNA_KODE[kode]]


# ------------------------------------------------------------------ grafik
def tren_tahun(yr):
    """Kemiringan linear per dekade dan galat bakunya (kasar: mengabaikan autokorelasi antar-tahun)."""
    x, y = yr.index.to_numpy(float), yr.to_numpy(float)
    if len(y) < 5: return np.nan, np.nan
    xm = x - x.mean(); b = float((xm * (y - y.mean())).sum() / (xm ** 2).sum()); res = y - y.mean() - b * xm
    return 10 * b, 10 * float(np.sqrt((res ** 2).sum() / (len(y) - 2) / (xm ** 2).sum()))


def _ket(fig, items, h=False):
    """Entri legenda tanpa data. item = (nama, "kotak"|"garis", warna[, dash]). Penjelasan gaya (gelap, putus, pekat, pucat, area abu) ada di legenda, bukan di judul panel."""
    for it in items:
        nm_, jn_, wr_ = it[:3]
        if jn_ == "teks": fig.add_trace(go.Bar(x=[None], y=[None], orientation="h" if h else "v", name=nm_, marker=dict(color=TRANSPARAN), showlegend=True, hoverinfo="skip"))      # nama berisi kotak berwarna (HTML); swatch bawaan dibuat transparan
        elif jn_ == "kotak": fig.add_trace(go.Bar(x=[None], y=[None], orientation="h" if h else "v", name=nm_, marker=dict(color=wr_), showlegend=True, hoverinfo="skip"))
        else: fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=nm_, line=dict(color=wr_, width=2.5, dash=it[3] if len(it) > 3 else "solid"), showlegend=True, hoverinfo="skip"))


K_ABU, TRANSPARAN = "rgba(135,147,163,.35)", "rgba(0,0,0,0)"      # abu = area naik-turun alami (memang abu di grafik)
# Pekat/pucat bukan warna sendiri, melainkan KEPEKATAN warna arah (merah = lebih sering kering, hijau = lebih jarang). Legenda memakai kotak merah+hijau pada kepekatan yang sama dengan grafik.
NM_NYATA = '<span style="color:#e60000">■</span><span style="color:#37a800">■</span> beda nyata'
NM_PUCAT = '<span style="color:#f59494">■</span><span style="color:#abda94">■</span> belum pasti'
NM_LUAR = '<span style="color:#f9c9c9">■</span><span style="color:#cfe8bf">■</span> di luar musim'


def fig_tahun(R):
    """Batang = % bulan kering tiap tahun (satu realisasi, bukan ramalan); garis tebal = rata-rata bergulir 5 tahun; putus = masa lalu model."""
    yr = R["per_th"]; x = yr.index.astype(int); mv = yr.rolling(5, center=True, min_periods=3).mean()
    fig = go.Figure(); fig.add_trace(go.Bar(x=x, y=yr.values, name="tiap tahun", marker_color="rgba(31,111,181,.72)", hovertemplate="%{x}<br>%{y:.0f} dari 100 bulan kering<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=mv.values, mode="lines", name="rata-rata 5 tahun", line=dict(color=INK, width=3.2), hovertemplate="%{x}: rata-rata 5 tahun %{y:.1f}<extra></extra>"))
    fig.add_hline(y=R["base"], line_dash="dot", line_color=MERAH, line_width=2.5)
    _ket(fig, [("masa lalu model", "garis", MERAH, "dot")])
    fig.update_layout(bargap=0.22, yaxis_range=[0, max(float(yr.max()), R["base"]) * 1.12]); fig.update_xaxes(dtick=5, tickfont=dict(size=10)); return fig


def fig_bulan(R):
    """Merah/hijau pekat = selisih bulan itu beda nyata (>= 2 x galat baku antar-tahun); merah/hijau pucat = belum pasti tetapi arah tetap terbaca; batang transparan = di luar musim terpilih."""
    d = R["dbulan"]; ny = R["bulan_nyata"].reindex(d.index).fillna(False).astype(bool); pilih_ = [m in R["bulan"] for m in d.index]
    warna = [(MERAH if v > 0 else BIRU) if nn else (MERAH_P if v > 0 else BIRU_P) for v, nn in zip(d.values, ny.values)]
    fig = go.Figure(go.Bar(x=[BLN[m - 1] for m in d.index], y=d.values, showlegend=False, marker=dict(color=warna, opacity=[1 if p else 0.45 for p in pilih_], line=dict(color=[MERAH if v > 0 else BIRU for v in d.values], width=1)), customdata=np.where(ny.values, "beda nyata", "belum pasti"),
                           hovertemplate="%{x}<br>selisih %{y:+.1f} bulan per 100 (%{customdata})<extra></extra>"))
    _ket(fig, [(NM_NYATA, "teks", None), (NM_PUCAT, "teks", None)] + ([(NM_LUAR, "teks", None)] if not all(pilih_) else []))
    fig.add_hline(y=0, line_color="#555", line_width=1); fig.update_xaxes(tickfont=dict(size=10)); return fig


def fig_model(sm, compact=False, amb=None):
    urut = sorted(sm, key=sm.get); v = [sm[m_] for m_ in urut]; a_ = float(amb) if amb is not None and np.isfinite(amb) else 0.0
    if compact: lab = [m_ + (" ★" if m_ == UTAMA else "") for m_ in urut]; warna = [PROY if m_ == UTAMA else ABU for m_ in urut]
    else: lab = [m_ + ("<br>(dipakai)" if m_ == UTAMA else "<br>(dekat pengamatan)" if m_ == TRANSFER else "") for m_ in urut]; warna = [PROY if m_ == UTAMA else TRANSF if m_ == TRANSFER else ABU for m_ in urut]
    span = max(max(v) - min(v), a_, 1)
    fig = go.Figure(go.Bar(y=lab, x=v, orientation="h", marker_color=warna, showlegend=False, text=[n(x, 1, True) for x in v], textposition="outside", textfont_size=10, cliponaxis=False, hovertemplate="%{y}<br>%{x:+.1f} bulan per 100<extra></extra>"))
    _ket(fig, [("★ dipakai" if compact else "dipakai", "kotak", PROY)] + ([("dekat pengamatan", "kotak", TRANSF)] if not compact and TRANSFER in sm else []) + [("pembanding", "kotak", ABU)] + ([("naik-turun alami", "kotak", K_ABU)] if a_ > 0 else []), h=True)
    if a_ > 0: fig.add_vrect(x0=-a_, x1=a_, fillcolor="#8793a3", opacity=0.15, line_width=0, layer="below")      # area abu = naik-turun alami
    fig.add_vline(x=0, line_color="#555", line_width=1.2)
    fig.update_xaxes(zeroline=False, range=[min(min(v), -a_, 0) - 0.22 * span, max(max(v), a_, 0) + 0.25 * span]); fig.update_yaxes(type="category", tickfont=dict(size=10), automargin=True); return fig


def fig_kab(R):
    """Selisih (proyeksi − masa lalu model) per kab/kota; area abu = naik-turun alami; batang pucat = belum beda nyata."""
    rk = R["rk"]; d = (rk["p_kering"] - rk["kering_model_pct"]).sort_values(); a_ = float(R["amb"]) if np.isfinite(R["amb"]) else 0.0
    warna = [(MERAH if v > 0 else BIRU) if (a_ > 0 and abs(v) >= a_) else (MERAH_P if v > 0 else BIRU_P) for v in d]
    fig = go.Figure(go.Bar(y=list(d.index), x=d.values, orientation="h", showlegend=False, marker=dict(color=warna, line=dict(color=[MERAH if v > 0 else BIRU for v in d], width=1)), text=[n(v, 1, True) for v in d], textposition="outside", textfont_size=10, cliponaxis=False, hovertemplate="%{y}<br>selisih %{x:+.1f} bulan per 100<extra></extra>"))
    if a_ > 0: fig.add_vrect(x0=-a_, x1=a_, fillcolor="#8793a3", opacity=0.15, line_width=0, layer="below")
    _ket(fig, [(NM_NYATA, "teks", None), (NM_PUCAT, "teks", None)] + ([("naik-turun alami", "kotak", K_ABU)] if a_ > 0 else []), h=True)
    fig.add_vline(x=0, line_color="#555", line_width=1.2); lim = max(a_ * 1.15, float(d.abs().max()) * 1.4, 3.0)
    fig.update_xaxes(range=[-lim, lim]); fig.update_yaxes(type="category", tickmode="array", tickvals=list(d.index), ticktext=list(d.index), automargin=True, tickfont=dict(size=10)); return fig


def selisih_gcm(skala, bulan, t0, t1):
    """Selisih per sel GCM kasar (sebelum downscaling): % bulan SPI <= -1 pada t0-t1 dikurangi 1981-2010, dihitung dari hujan GCM mentah (SPI memakai acuan Gamma GCM sendiri).
    Butuh dashboard_gcm_sel.csv.gz (notebook sel 14k). None bila berkas belum ada."""
    S = D.get("gcm")
    if S is None or not {"sel_gcm", "lon_w", "lon_e", "lat_s", "lat_n", "SPI", "tahun", "bulan", "kering"} <= set(S.columns): return None
    S = S[(S["SPI"] == skala) & S["bulan"].isin(bulan)]
    if S.empty: return None
    base = S[S["tahun"].between(1981, 2010)].groupby("sel_gcm")["kering"].mean().mul(100).rename("base")
    proy = S[S["tahun"].between(t0, t1)].groupby("sel_gcm")["kering"].mean().mul(100).rename("proy")
    out = S.groupby("sel_gcm")[["lon_w", "lon_e", "lat_s", "lat_n"]].first().join(base).join(proy).dropna()
    out["selisih"] = out["proy"] - out["base"]
    return out.reset_index() if len(out) else None


def peta_dari(R, mode, tinggi, lebar=400, G=None):
    """Satu peta: selisih proyeksi - masa lalu. mode "Sesudah" = grid 5 km (hasil downscaling); "Sebelum" = sel GCM kasar (G dari selisih_gcm). Skala warna dibuat sama agar keduanya sebanding."""
    a = R["agg"]
    lim = max(2.5, float(np.ceil(np.nanpercentile(a["selisih"].abs(), 98) / 2.5) * 2.5))      # skala mengikuti sebaran data, supaya warna tidak menumpuk di tengah
    if G is not None: lim = max(lim, float(np.ceil(G["selisih"].abs().max() / 2.5) * 2.5))
    if mode == "Sebelum" and G is not None:
        return fig_peta(a, "selisih", -lim, lim, "bln/100", SELISIH, tinggi, lebar, zmid=0, sel=G, catatan=f"{len(G)} sel GCM, hujan GCM mentah<br>sebelum downscaling")
    kat = f"{int(a['nyata'].sum())} dari {len(a)} kotak beda nyata" if a["nyata"].any() else "belum ada kotak yang beda nyata<br>warna hanya menunjukkan arah"
    return fig_peta(a, "selisih", -lim, lim, "bln/100", SELISIH, tinggi, lebar, zmid=0, mask=a["nyata"], catatan=kat, legenda=[(NM_NYATA, TRANSPARAN), (NM_PUCAT, TRANSPARAN)])


# ------------------------------------------------------------------ teks "cara membaca" dan "kesimpulan" (menyesuaikan pilihan pengguna)
ISTILAH = ("<b>SPI</b> membandingkan hujan suatu periode dengan hujan biasanya (1981-2010): 0 = normal, negatif = lebih kering, dan <b>SPI ≤ −1 disebut bulan kering</b>. "
           "<b>Jangka</b> 3/6/12 bulan = hujan dijumlahkan selama 3/6/12 bulan terakhir (makin panjang, makin menggambarkan kekeringan berkepanjangan). "
           "<b>\"Bulan kering per 100\"</b> = dari 100 bulan, berapa yang kering; menurut definisi SPI, sekitar 16 dari 100 bulan kering pada periode acuan.")


def teks_panel(R, sm, am, cek, n_ok, yak, naik, turun, mode):
    """Kamus {kunci: (judul, cara membaca, kesimpulan)}. Semua angka dihitung dari pilihan aktif."""
    amb, sel, kode, bias = R["amb"], R["sel"], R["kode"], R["base"] - R["ref"]
    gagal = [c[1][0].lower() + c[1][1:] for c in cek if not c[2]]
    amb_t = (f"selang 95%: {n(R['ci'][0], 1, True)} s/d {n(R['ci'][1], 1, True)}" if R.get("ci") else f"±{n(amb, 1)}") if np.isfinite(amb) else "(tidak terhitung)"
    KODE_KES = {"sama": f"Selisih {n(sel, 1, True)} lebih kecil daripada batas naik-turun alami ({amb_t}), jadi <b>belum bisa disebut perubahan nyata</b>.",
                "lebih": f"Selisih {n(sel, 1, True)} lebih besar daripada batas naik-turun alami ({amb_t}): bulan kering diproyeksikan <b>lebih sering</b>.",
                "kurang": f"Selisih {n(sel, 1, True)} lebih besar daripada batas naik-turun alami ({amb_t}): bulan kering diproyeksikan <b>lebih jarang</b>.",
                "sedikit": "Data terlalu sedikit untuk disimpulkan."}
    T = {}
    am_t = (f"Rentang {n(min(sm.values()), 1, True)} s/d {n(max(sm.values()), 1, True)} bulan per 100. " + ("Semua model searah." if am["N"] >= 2 and am["n_s"] == am["N"] else "Model tidak sepakat arahnya, jadi <b>tanda perubahan bergantung pada model yang dipilih</b>.")) if len(sm) >= 2 else "Data perbandingan model belum ada."
    T["k_sel"] = ("Kartu: selisih", "Proyeksi dikurangi masa lalu model (bulan kering per 100 bulan). Angka ± adalah batas naik-turun alami antar-tahun (2 × galat baku): selisih di bawah batas ini belum bisa dipastikan.", KODE_KES[kode])
    T["k_model"] = ("Kartu: rentang model", "Selisih yang sama dihitung dengan empat model statistik (GLM, Random Forest, XGBoost, Neural Net). Bila rentangnya melewati 0, tanda perubahan bergantung pada model.", am_t)
    T["k_lalu"] = ("Kartu: masa lalu model vs nyata", "Dari 100 bulan pada 1981-2010, berapa yang kering menurut model dan menurut pengamatan (CHIRPS). Sebagai acuan, SPI dirancang agar sekitar 16 dari 100 bulan kering.",
                   (f"Model memberi {n(R['base'], 0)} vs {n(R['ref'], 0)} pengamatan: model <b>terlalu kering</b> sekitar {n(bias, 0)} bulan per 100. Karena itu angka mutlak proyeksi tidak ditampilkan; yang dibaca adalah <b>selisih</b> terhadap masa lalu model yang sama." if bias > 3
                    else f"Model memberi {n(R['base'], 0)} vs {n(R['ref'], 0)} pengamatan, cukup dekat." if bias > -3 else f"Model memberi {n(R['base'], 0)} vs {n(R['ref'], 0)} pengamatan: model <b>terlalu basah</b>; baca selisih, bukan angka mutlak."))
    T["k_yak"] = ("Kartu: syarat terpenuhi", f"Enam titik = enam syarat: model terbaik, {UJI_TXT}, arah sejalan hujan GCM, input di luar rentang latih, bias model, dan kesepakatan antar-model. Hijau = terpenuhi, oranye = belum.",
                  f"Syarat terpenuhi: <b>{n_ok} dari 6</b> (daftar periksa, bukan skor statistik)." + (" Belum terpenuhi: " + "; ".join(gagal) + "." if gagal else ""))
    # peta
    a, rk = R["agg"], R["rk"]
    cara_p = "Warna = proyeksi dikurangi masa lalu model per grid. Merah = lebih sering kering, hijau = lebih jarang, kuning pucat = tidak berubah (warna mengikuti legenda SPI BMKG). Garis hitam = batas kabupaten/kota."
    if len(a) and "wilayah" in a and a["wilayah"].notna().any():
        pos = float((a["selisih"] > 0).mean() * 100); rs = a.groupby("wilayah")["selisih"].mean(); rs.index = nama_pendek(rs.index.tolist())
        kes_p = f"{n(pos, 0)}% grid berwarna merah-oranye (naik) dan {n(100 - pos, 0)}% hijau (turun). Selisih rata-rata tertinggi di <b>{rs.idxmax()}</b> ({n(rs.max(), 1, True)}), terendah di <b>{rs.idxmin()}</b> ({n(rs.min(), 1, True)}). Baca sebagai kecenderungan wilayah, bukan angka pasti tiap kotak."
    else: kes_p = "Baca sebagai kecenderungan wilayah, bukan angka pasti tiap kotak."
    T["peta"] = ("Peta (selisih vs masa lalu)", cara_p, kes_p)
    if "nyata" in a:
        T["peta"] = (T["peta"][0], T["peta"][1] + " Warna pucat = selisih kotak itu belum melampaui naik-turun alaminya sendiri; warna pekat = beda nyata.", T["peta"][2] + f" Kotak yang beda nyata: <b>{int(a['nyata'].sum())} dari {len(a)}</b>. Pola kotak sebagian mengikuti sel GCM yang kasar (hanya 4 sel menutupi Banten), bukan detail 5 km.")
    # per tahun
    yr = R["per_th"]; mv = yr.rolling(5, center=True, min_periods=3).mean().dropna(); b10, se10 = tren_tahun(yr)
    kes_b = f"{int((yr > R['base']).sum())} dari {len(yr)} tahun berada di atas garis masa lalu model ({n(R['base'], 0)}). Tertinggi <b>{int(yr.idxmax())}</b> ({n(yr.max(), 0)}), terendah <b>{int(yr.idxmin())}</b> ({n(yr.min(), 0)})."
    if len(mv): kes_b += f" Rata-rata bergulir 5 tahun hanya berkisar {n(mv.min(), 0)}-{n(mv.max(), 0)}."
    if np.isfinite(b10): kes_b += f" Kecenderungan linear {n(b10, 1, True)} poin per dekade (selang kasar ±{n(2 * se10, 1)}): " + ("<b>tidak ada tren yang jelas</b>." if abs(b10) < 2 * se10 else "<b>ada kecenderungan naik</b>." if b10 > 0 else "<b>ada kecenderungan turun</b>.")
    kes_b += " Naik-turun antar tahun besar karena tiap tahun hanyalah satu realisasi model, bukan ramalan tahun itu."
    T["blok"] = ("Per tahun", "Tiap batang = bulan kering per 100 bulan pada satu tahun. Garis tebal gelap = rata-rata bergulir 5 tahun (meredam naik-turun antar tahun). Garis putus-putus merah = masa lalu model.", kes_b)
    # bulan
    d = R["dbulan"].dropna()
    if len(d) >= 2:
        top = d.nlargest(2); low = d.idxmin()
        kes_m = f"{int((d > 0).sum())} dari {len(d)} bulan menunjukkan kenaikan. Terbesar <b>{BLN[top.index[0] - 1]}</b> ({n(top.iloc[0], 1, True)}) dan <b>{BLN[top.index[1] - 1]}</b> ({n(top.iloc[1], 1, True)}); terendah {BLN[low - 1]} ({n(d.min(), 1, True)})."
        if set(top.index) <= {8, 9, 10, 11} and int(R["bulan_nyata"].reindex(d.index).fillna(False).sum()) > 0: kes_m += " Kenaikan terkonsentrasi di akhir musim kemarau."
        n_ny = int(R["bulan_nyata"].reindex(d.index).fillna(False).sum()); kes_m += f" Yang beda nyata hanya <b>{n_ny} dari {len(d)} bulan</b>; batang pucat = belum pasti, jadi pola musim ini belum bisa dipakai sebagai temuan."
    else: kes_m = "Data bulanan tidak cukup."
    T["bulan"] = ("Selisih per bulan", "Tiap batang = proyeksi dikurangi masa lalu model untuk satu bulan kalender (bulan per 100). Merah = lebih sering kering, hijau = lebih jarang; warna pekat = beda nyata, pucat = belum pasti; batang transparan = di luar musim yang dipilih.", kes_m)
    # model
    if len(sm) >= 2:
        v = list(sm.values()); kes_o = (f"Semua {am['N']} model searah ({'lebih sering' if am['arah'] == 'lebih' else 'lebih jarang'} kering): hasil tidak bergantung pada pilihan model." if am["arah"] and am["n_s"] == am["N"]
                                        else f"{am['n_s']} dari {am['N']} model searah ({'lebih sering' if am['arah'] == 'lebih' else 'lebih jarang'} kering), rentang {n(min(v), 1, True)} s/d {n(max(v), 1, True)}. <b>Tanda perubahan bergantung pada pilihan model</b>." if am["arah"]
                                        else f"Model terpecah, rentang {n(min(v), 1, True)} s/d {n(max(v), 1, True)}: hasil bergantung pada pilihan model.")
        if UTAMA in sm and am["arah"] and abs(sm[UTAMA]) >= 0.5 and (sm[UTAMA] > 0) != (am["arah"] == "lebih") and am["n_s"] < am["N"]: kes_o += f" Model yang dipakai ({UTAMA}, {n(sm[UTAMA], 1, True)}) berlawanan dengan mayoritas, jadi hasil utama sebaiknya tidak dibaca sebagai arah yang pasti."
        elif UTAMA in sm: kes_o += f" Model yang dipakai ({UTAMA}) = {n(sm[UTAMA], 1, True)}."
    else: kes_o = "Data perbandingan model belum ada."
    T["model"] = ("Apakah hasil tergantung model?", f"Tiap batang = selisih (proyeksi − masa lalu) menurut satu model statistik; kanan = lebih sering kering, kiri = lebih jarang. Biru = model yang dipakai ({SEL_KECIL}), ungu = model yang frekuensi keringnya paling dekat pengamatan, abu = pembanding.", kes_o)
    # kabupaten/kota
    if len(rk):
        dk = rk["p_kering"] - rk["kering_model_pct"]; arah_k = "semuanya naik" if (dk > 0).all() else "semuanya turun" if (dk < 0).all() else "arahnya campuran"
        kes_k = (f"Tertinggi <b>{rk.index[-1]}</b> ({n(rk['p_kering'].iloc[-1], 0)}), terendah <b>{rk.index[0]}</b> ({n(rk['p_kering'].iloc[0], 0)}). Selisih tiap wilayah {n(dk.min(), 1, True)} s/d {n(dk.max(), 1, True)} bulan per 100: {arah_k}, "
                 + ("masih di dalam" if np.isfinite(amb) and dk.abs().max() < amb else "sebagian melampaui") + " batas naik-turun alami. Perbedaan antarwilayah lebih mencerminkan klimatologi daripada sinyal perubahan.")
    else: kes_k = "Batas kab/kota belum tersedia."
    T["kab"] = ("Kabupaten/kota", "Batang = selisih (proyeksi − masa lalu model) rata-rata grid di dalam wilayah. Area abu = naik-turun alami; batang pucat = belum beda nyata; merah/hijau pekat = melampaui batas alami.", kes_k)
    return T


def teks_deret(sk):
    r = D["reg"]
    if r is None: return None
    s_ = r[r["SPI"] == sk].sort_values(["tahun", "bulan"]).dropna(subset=["spi_median"])
    if s_.empty: return None
    kr = (s_["spi_median"] <= -1).to_numpy(); run = best = 0
    for x in kr: run = run + 1 if x else 0; best = max(best, run)
    mn = s_.loc[s_["spi_median"].idxmin()]
    cara_ = f"Garis gelap = SPI bulanan ({sk}) dari median {meta.get('n_anggota_ensemble', 20)} simulasi; pita = sebaran p10-p90 antar-simulasi. Area merah muda di bawah garis putus-putus (−1) = daerah bulan kering, ditandai titik merah; titik berurutan = kekeringan berkepanjangan."
    kes = f"Median simulasi mencapai SPI ≤ −1 pada <b>{int(kr.sum())} dari {len(s_)} bulan</b>; paling kering {BLN[int(mn['bulan']) - 1]} {int(mn['tahun'])} (SPI {n(mn['spi_median'], 2)}), dan rangkaian terpanjang <b>{best} bulan berturut-turut</b>. Tahun-tahun kering berasal dari variabilitas internal satu simulasi model, bukan ramalan kejadian nyata."
    return cara_, kes


def fig_deret(sk, t0=None, t1=None):
    s_ = D["reg"][D["reg"]["SPI"] == sk]; s_ = s_ if t0 is None else s_[s_["tahun"].between(t0, t1)]; s_ = s_.sort_values(["tahun", "bulan"]); x = pd.to_datetime(dict(year=s_["tahun"], month=s_["bulan"], day=1))
    fig = go.Figure()
    fig.add_hrect(y0=-3.5, y1=-1, fillcolor="#e60000", opacity=0.07, line_width=0, layer="below")      # area bulan kering (SPI ≤ -1)
    fig.add_trace(go.Scatter(x=x, y=s_["spi_p90"], line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=s_["spi_p10"], fill="tonexty", fillcolor="rgba(135,147,163,.28)", line=dict(width=0), name="sebaran antar-simulasi (p10-p90)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=s_["spi_median"], line=dict(color=INK, width=1.6), name="SPI (median simulasi)", hovertemplate="%{x|%b %Y}<br>SPI %{y:.2f}<extra></extra>"))
    kr = s_["spi_median"] <= -1
    fig.add_trace(go.Scatter(x=x[kr], y=s_.loc[kr, "spi_median"], mode="markers", marker=dict(color="#e60000", size=6), name="bulan kering (SPI ≤ -1)", hoverinfo="skip"))
    fig.add_hline(y=-1, line_dash="dash", line_color="#e60000", line_width=1.3); fig.add_hline(y=0, line_color="#8793a3", line_width=1)
    fig.update_yaxes(title_text="SPI", range=[-3.5, 3.5]); return fig


def deret_info(sk, t0, t1):
    r = D["reg"]
    if r is None: return None
    s_ = r[(r["SPI"] == sk) & r["tahun"].between(t0, t1)].sort_values(["tahun", "bulan"]).dropna(subset=["spi_median"]).reset_index(drop=True)
    if s_.empty: return None
    kr = (s_["spi_median"] <= -1).to_numpy(); best = run = 0; end = -1
    for i, x in enumerate(kr):
        run = run + 1 if x else 0
        if run > best: best, end = run, i
    lab = lambda i: f"{BLN[int(s_.loc[i, 'bulan']) - 1]} {int(s_.loc[i, 'tahun'])}"
    mn = int(s_["spi_median"].idxmin())
    return dict(best=best, a=lab(end - best + 1) if best else "-", b=lab(end) if best else "-", mn=lab(mn), mn_v=float(s_.loc[mn, "spi_median"]), n_k=int(kr.sum()), N=len(s_))


def fig_heat(sk, t0, t1):
    G = D["b_grid"]; G = G[(G["SPI"] == sk) & G["tahun"].between(t0, t1)]
    pv = G.groupby(["bulan", "tahun"])["p_kering"].mean().mul(100).unstack("tahun").reindex(range(1, 13))
    zmax = max(30.0, float(np.ceil(np.nanpercentile(pv.values, 98) / 10) * 10))
    fig = go.Figure(go.Heatmap(z=pv.values, x=pv.columns, y=[BLN[m - 1] for m in pv.index], colorscale=KERING, zmin=0, zmax=zmax, xgap=1, ygap=1,
                               colorbar=dict(title=dict(text="% kering", font=dict(size=9), side="top"), thickness=8, len=0.9, tickfont=dict(size=9)), hovertemplate="%{y} %{x}<br>%{z:.0f}% simulasi kering<extra></extra>"))
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=9), gridcolor="white"); fig.update_xaxes(dtick=5, tickfont=dict(size=9)); return fig


def tabel_tiga_jangka(t0, t1, bulan):
    """Ringkasan SPI-3/6/12 sekaligus (mengikuti musim dan rentang tahun yang dipilih)."""
    rows = []
    for s_ in meta["spi_skala"]:
        Rk = ringkas(s_, bulan, t0, t1)
        if Rk: rows.append({"Jangka": NAMA_SKALA_PANJANG.get(s_, s_), "Masa lalu (model)": n(Rk["base"]), "Pengamatan": n(Rk["ref"]), f"Proyeksi {t0}-{t1}": n(Rk["proy"]), "Selisih": n(Rk["sel"], 1, True), "Naik-turun (±)": n(Rk["amb"]) if np.isfinite(Rk["amb"]) else "-", "Tafsir": f'{SIM[Rk["kode"]]} {KATA[Rk["kode"]]}'})
    return pd.DataFrame(rows).set_index("Jangka") if rows else None


def tabel_gerbang():
    gb = D["gerb"]
    if gb is None or not {"a_lolos", "b_lolos", "c_lolos", "a_crpss_t1", "b_qq_rasio", "c_kering_pct", "acuan_c"} <= set(gb.columns): return None
    ok = lambda v: "✓" if bool(v) else "✗"
    return pd.DataFrame({"Model": gb["model"] + np.where(gb["model"] == UTAMA, " (dipakai)", ""),
                         "A. Lebih baik dari klimatologi (CRPSS T1)": [f"{ok(l)}  {n(v, 3, True)}" for l, v in zip(gb["a_lolos"], gb["a_crpss_t1"])],
                         "B. Sebaran sesuai pengamatan (rasio QQ)": [f"{ok(l)}  {n(v, 2)}" for l, v in zip(gb["b_lolos"], gb["b_qq_rasio"])],
                         "C. Frekuensi kering dekat pengamatan (per 100)": [f"{ok(l)}  {n(v, 1)} vs {n(a_, 1)}" for l, v, a_ in zip(gb["c_lolos"], gb["c_kering_pct"], gb["acuan_c"])]}).set_index("Model")


# ------------------------------------------------------------------ laporan (?laporan=1)
def halaman_baru(): st.markdown('<div style="break-before:page"></div>', unsafe_allow_html=True)
def cara(t): st.markdown(f'<div class="cara">{t}</div>', unsafe_allow_html=True)


def kotak_html(isi, tinggi):
    iframe('<style>body{margin:0;font-family:"Poppins","Segoe UI",Arial,sans-serif;color:#10243b;-webkit-print-color-adjust:exact;print-color-adjust:exact}' + """
.row{display:flex;align-items:stretch;gap:0}.b{flex:1;border-radius:8px;padding:8px 10px;font-size:12px;line-height:1.3;text-align:center;display:flex;flex-direction:column;justify-content:center;color:#fff}
.b small{font-size:10px;opacity:.92}.ar{width:22px;display:flex;align-items:center;justify-content:center;color:#5b6b7f;font-size:18px}
.t{display:flex;height:38px;border-radius:8px;overflow:hidden;margin-top:4px}.t div{display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:700;white-space:nowrap;overflow:hidden}
.l{font-size:10px;color:#5b6b7f;margin:8px 0 2px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}.yr{display:flex;font-size:10px;color:#5b6b7f;margin-top:2px}</style>""" + isi, tinggi)


def halaman_laporan():
    sk = str(st.query_params.get("skala", "SPI-3")); sk = sk if sk in list(meta["spi_skala"]) else "SPI-3"
    R = ringkas(sk, PRESET["Sepanjang tahun"], th_all[0], th_all[-1]); sm = model_selisih(sk, th_all[0], th_all[-1], R=R); kh, cek, n_ok, yak, yak_c, am, naik, turun = kartu_html(R, sm, chips=False, bg="#ffffff")
    kode = R["kode"]; model_nama = str(meta.get("model", "-")).replace(" [mu+V1]", "").replace("P: ", "")
    TP = teks_panel(R, sm, am, cek, n_ok, yak, naik, turun, "Selisih")
    def cara2(k): st.markdown(f'<div class="cara"><b>Cara membaca:</b> {TP[k][1]}</div><div class="kes"><b>Kesimpulan:</b> {TP[k][2]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="judul">{JUDUL_PROYEK}</div><div class="sublap">Laporan hasil proyeksi · {PEMBUAT} · analisis versi {meta.get("versi_notebook", "-")} · dijalankan {meta.get("tanggal_run", "-")}</div>', unsafe_allow_html=True)

    st.markdown("## 1. Ringkasan")
    st.markdown(f'**Pertanyaan:** seberapa sering bulan kering (hujan jauh di bawah normal, SPI ≤ -1) terjadi di Banten pada {H0}-{H1} dibanding 1981-2010?')
    kal = {"sama": f"Selisih ini masih dalam naik-turun alami antar-tahun (±{n(R['amb'], 1)}), sehingga **belum ada perubahan yang bisa dipastikan**.", "lebih": "Bulan kering diproyeksikan **lebih sering** daripada masa lalu.", "kurang": "Bulan kering diproyeksikan **lebih jarang** daripada masa lalu.", "sedikit": "Data terlalu sedikit untuk disimpulkan."}[kode]
    st.markdown(f'<div class="jawab"><b>Jawaban:</b> menurut model terpilih ({model_nama}), sekitar <b>{n(R["proy"], 0)} dari 100 bulan</b> kering pada {H0}-{H1}, dibanding <b>{n(R["base"], 0)}</b> pada 1981-2010 menurut model yang sama (selisih {n(R["sel"], 1, True)}). Pengamatan nyata sekitar {n(R["ref"], 0)} dari 100 bulan. {kal.replace("**", "")}</div>', unsafe_allow_html=True)
    st.write(""); iframe(kh, 98)
    st.markdown("**Istilah dasar**"); st.markdown(f'<div class="cara">{ISTILAH}</div>', unsafe_allow_html=True)
    st.markdown("**Cara membaca keempat kartu angka**")
    for k_ in ("k_sel", "k_model", "k_lalu", "k_yak"): st.markdown(f"*{TP[k_][0].replace('Kartu: ', '').capitalize()}*"); cara2(k_)
    gagal = [c[1] for c in cek if not c[2]]
    st.markdown(f'**Syarat terpenuhi: {yak}** (daftar periksa, bukan skor statistik).' + (" Yang belum terpenuhi: " + "; ".join(g[0].lower() + g[1:] for g in gagal) + "." if gagal else ""))
    st.caption("Angka mutlak model melebihkan frekuensi bulan kering, jadi yang dibaca adalah selisih terhadap masa lalu menurut model yang sama. Ini gambaran kecenderungan, bukan ramalan cuaca.")

    st.markdown("## 2. Latar dan tujuan")
    st.markdown("Kekeringan memengaruhi pertanian, ketersediaan air bersih, dan pengelolaan waduk. Model iklim global (GCM) berskala kasar: hanya sekitar lima sel GCM yang menutupi Banten, sehingga hasilnya tidak bisa dipakai langsung untuk tingkat kabupaten/kota. "
                "Tujuan proyek ini adalah **memperhalus (downscaling) hujan GCM ke grid sekitar 5 km di Banten**, mengubahnya menjadi indeks kekeringan SPI, dan menilai **apakah frekuensi bulan kering berubah pada 2026-2050 dibanding 1981-2010**, "
                "sekaligus menilai seberapa bisa hasil itu dipercaya.")

    st.markdown("## 3. Data dan wilayah")
    st.table(pd.DataFrame([["Apa", "Frekuensi bulan kering (SPI ≤ -1) pada skala 3, 6, dan 12 bulan."], ["Mengapa", "Gambaran kecenderungan kekeringan untuk perencanaan, bukan prakiraan cuaca."], ["Siapa", PEMBUAT or "-"],
                           ["Di mana", "Provinsi Banten, grid sekitar 5 km dan enam kabupaten/kota."], ["Kapan", f"Proyeksi {H0}-{H1}; pembanding 1981-2010; latih/seleksi 1981-2020; hold-out 2021-2025."],
                           ["Data", f"Model iklim {meta.get('gcm')} (skenario {meta.get('skenario')}, satu anggota); hujan pengamatan {meta.get('target')}; prediktor ERA5."]], columns=["", "Keterangan"]).set_index(""))

    halaman_baru(); st.markdown("## 4. Metode")
    st.markdown("**Alur analisis**")
    kotak_html('<div class="row"><div class="b" style="background:#1f6fb5">Model iklim<br><small>' + str(meta.get("gcm")) + ' · ' + str(meta.get("skenario")) + '</small></div><div class="ar">→</div><div class="b" style="background:#1f6fb5">Prediktor skala besar<br><small>indeks regional</small></div><div class="ar">→</div>'
               '<div class="b" style="background:#0f8b8d">Model statistik<br><small>GLM, RF, XGBoost, NN</small></div><div class="ar">→</div><div class="b" style="background:#e8710a">Simulasi hujan bulanan<br><small>ensemble per grid</small></div><div class="ar">→</div><div class="b" style="background:#e60000">SPI → bulan kering<br><small>SPI ≤ -1</small></div></div>'
               '<div class="l">Model statistik dilatih pada data pengamatan nyata</div><div class="row"><div class="b" style="background:#0f8b8d">ERA5 (prediktor) + CHIRPS (hujan), 1981-2020 → dilatih lalu diterapkan ke prediktor GCM</div></div>', 150)
    st.markdown("**Pembagian periode**")
    kotak_html('<div class="l">Data model</div><div class="t"><div style="flex:40;background:#1f6fb5">1981-2020 · latih dan seleksi (CV blok-tahun)</div><div style="flex:5;background:#e8710a;font-size:9px">2021-25</div><div style="flex:25;background:#0f8b8d">2026-2050 · proyeksi</div></div>'
               '<div class="yr"><span style="flex:40">1981</span><span style="flex:5">2021</span><span style="flex:25">2026 – 2050</span></div><div class="l">Pembanding</div><div class="t"><div style="flex:30;background:#8793a3">1981-2010 · masa lalu (baseline)</div><div style="flex:40;background:transparent"></div></div>', 132)
    cara("Hold-out 2021-2025 (kuning) dikunci: tidak dipakai untuk tuning, memilih model, maupun menyetel ambang; dievaluasi satu kali setelah semua keputusan dikunci.")
    st.markdown("- **Tuning adil:** keempat model dituning dengan data, lipatan validasi, skor, dan anggaran pencarian yang sama.\n- **Pemilihan model:** " + SEL_PANJANG + "; ini berarti *terbaik di antara beberapa model*, bukan *terbukti lebih baik dari klimatologi*.\n"
                "- **Dua tingkat validasi:** Tingkat 1 (data pengamatan sefase) menilai skill sebenarnya; Tingkat 2 (prediktor GCM, tidak sefase) hanya bisa menilai sebaran.\n- **SPI** dihitung dari simulasi hujan bulanan; bulan dianggap kering bila SPI ≤ -1.")

    st.markdown("## 5. Validasi")
    ho, tr = meta.get("holdout") or {}, meta.get("model_transfer_terbaik") or {}
    if ho and tr:
        fig = make_subplots(rows=1, cols=3, subplot_titles=("Skill sefase, hold-out 2021-25 (CRPSS)", "Selisih frekuensi kering vs pengamatan (poin)", f"CRPSS per tahun, {UTAMA or 'model dipakai'}"), horizontal_spacing=0.1)
        sa = ho.get("semua_model_crpss_t1") or {}; mm = [m_ for m_ in ML if m_ in sa]
        fig.add_trace(go.Bar(x=mm, y=[sa[m_] for m_ in mm], marker_color=[PROY if m_ == UTAMA else ABU for m_ in mm], text=[n(sa[m_], 2, True) for m_ in mm], textposition="outside", textfont_size=9, cliponaxis=False), row=1, col=1)
        sb = tr.get("selisih_semua") or {}; mb = [m_ for m_ in ML if m_ in sb]
        fig.add_trace(go.Bar(x=mb, y=[sb[m_] for m_ in mb], marker_color=[PROY if m_ == UTAMA else TRANSF if m_ == TRANSFER else ABU for m_ in mb], text=[n(sb[m_], 1, True) for m_ in mb], textposition="outside", textfont_size=9, cliponaxis=False), row=1, col=2)
        for yy in (3, -3): fig.add_hline(y=yy, line_dash="dot", line_color="#8793a3", row=1, col=2)
        pt = ho.get("crpss_per_tahun") or {}
        fig.add_trace(go.Bar(x=list(pt), y=[pt[k] for k in pt], marker_color=["#0f8b8d" if v > 0 else "#e8710a" for v in pt.values()], text=[n(v, 2, True) for v in pt.values()], textposition="outside", textfont_size=9, cliponaxis=False), row=1, col=3)
        for c_ in (1, 3): fig.add_hline(y=0, line_color="#555", line_width=1, row=1, col=c_)
        fig.update_annotations(font_size=10); fig.update_xaxes(tickfont=dict(size=9)); gambar(fig, 270)
        cara("Kiri: skill pada data nyata sefase (CRPSS > 0 = lebih baik daripada klimatologi). Tengah: pada prediktor GCM, selisih frekuensi bulan kering terhadap pengamatan (garis putus = ±3 poin); biru = model dipakai, ungu = paling dekat pengamatan. Kanan: konsistensi per tahun hold-out.")
        st.markdown(f"- Hold-out 2021-2025: CRPSS **{n(ho['crpss_t1'], 3, True)}** untuk {UTAMA or 'model terpilih'}, positif di **{ho['tahun_positif']} dari {ho['n_tahun']}** tahun. Data ini sudah dilihat berulang selama pengembangan, jadi bukan uji independen. Hanya 5 tahun, jadi dibaca sebagai pemeriksaan arah, bukan bukti.\n"
                    "- Skill sefase **tidak otomatis terbawa** ke prediktor GCM: model yang paling terampil pada data nyata belum tentu paling cocok pada prediktor GCM. Karena itu hasil dibaca sebagai selisih terhadap baseline model sendiri.")
    else: st.info("Hasil validasi hold-out tidak tersedia pada berkas data ini.")

    if D["gerb"] is not None and {"a_lolos", "b_lolos", "c_lolos", "a_crpss_t1", "b_qq_rasio", "c_kering_pct", "acuan_c"} <= set(D["gerb"].columns):
        gb = D["gerb"]
        st.markdown("**Gerbang pemilihan model**")
        st.table(tabel_gerbang())
        lA = gb.loc[gb["a_lolos"].astype(bool), "model"].tolist(); lB = gb.loc[gb["b_lolos"].astype(bool), "model"].tolist(); lC = gb.loc[gb["c_lolos"].astype(bool), "model"].tolist(); semua = gb.loc[gb["lolos"].astype(bool), "model"].tolist()
        st.markdown(f"Lolos kriteria A: {', '.join(lA) or '-'}. Lolos B: {', '.join(lB) or '-'}. Lolos C: {', '.join(lC) or '-'}. " + (f"Lolos ketiganya: {', '.join(semua)}." if semua else "**Tidak ada model yang lolos ketiganya.**")
                    + f" {UTAMA or 'Model terpilih'} dipilih karena skill (CRPSS Tingkat 1) tertinggi di antara model yang lolos A, bukan karena satu-satunya yang lolos. Karena kriteria B dan C tidak terpenuhi, hasil dibaca sebagai selisih relatif terhadap masa lalu model.")

    if D["sens"] is not None and {"model", "varian", "delta_mu_pct"} <= set(D["sens"].columns):
        sv = D["sens"].pivot_table(index="model", columns="varian", values="delta_mu_pct", aggfunc="first")
        sv = sv.drop(index="Hujan GCM mentah", errors="ignore").round(1).map(lambda v: n(v, 1, True))
        st.markdown("**Uji sensitivitas prediktor** (perubahan rata-rata hujan, %)"); st.table(sv)

    halaman_baru(); st.markdown("## 6. Hasil")
    st.markdown("**Ringkasan tiga jangka kekeringan (sepanjang tahun)**")
    rows = []
    for s_ in meta["spi_skala"]:
        Rk = ringkas(s_, PRESET["Sepanjang tahun"], th_all[0], th_all[-1])
        if Rk: rows.append({"Jangka": NAMA_SKALA_PANJANG.get(s_, s_), "Masa lalu (model)": n(Rk["base"]), "Pengamatan": n(Rk["ref"]), f"Proyeksi {H0}-{H1}": n(Rk["proy"]), "Selisih": n(Rk["sel"], 1, True), "Naik-turun alami (±)": n(Rk["amb"]), "Tafsir": f'{SIM[Rk["kode"]]} {KATA[Rk["kode"]]}'})
    st.table(pd.DataFrame(rows).set_index("Jangka")); cara("Satuan: bulan kering dari 100 bulan. 'Naik-turun alami' = 2 × galat baku antar-tahun; selisih yang lebih kecil darinya belum bisa dipastikan.")
    st.markdown(f"**Peta: selisih frekuensi bulan kering terhadap masa lalu ({NAMA_SKALA_PANJANG.get(sk, sk)})**"); Gl = selisih_gcm(sk, PRESET["Sepanjang tahun"], th_all[0], th_all[-1]); gambar(peta_dari(R, "Sesudah", 400, 800, G=Gl), 400, tetap=True, legenda=True, leg_pos="dalam")
    if Gl is not None: st.markdown("**Pembanding: sebelum downscaling (sel GCM kasar, skala warna sama)**"); gambar(peta_dari(R, "Sebelum", 400, 800, G=Gl), 400, tetap=True)
    cara2("peta")
    st.markdown("**Per tahun**"); gambar(fig_tahun(R), 250, legenda=True); cara2("blok")
    st.markdown("**Selisih per bulan**"); gambar(fig_bulan(R), 230, legenda=True)
    cara2("bulan")
    if len(sm) >= 2:
        st.markdown("**Apakah hasilnya tergantung pada model?**"); gambar(fig_model(sm, amb=R["amb"]), 230, legenda=True)
        cara2("model")
    if len(R["rk"]): st.markdown("**Per kabupaten/kota**"); gambar(fig_kab(R), 230, legenda=True); cara2("kab")

    ts = teks_deret(sk)
    if ts: st.markdown(f"**Deret SPI bulanan {H0}-{H1} ({NAMA_SKALA_PANJANG.get(sk, sk)})**"); gambar(fig_deret(sk), 260, legenda=True); st.markdown(f'<div class="cara"><b>Cara membaca:</b> {ts[0]}</div><div class="kes"><b>Kesimpulan:</b> {ts[1]}</div>', unsafe_allow_html=True)

    st.markdown(f"**Peluang kering per tahun dan bulan ({NAMA_SKALA_PANJANG.get(sk, sk)})**"); gambar(fig_heat(sk, th_all[0], th_all[-1]), 260)
    cara("Tiap kotak = porsi simulasi yang kering pada bulan dan tahun itu (0-100%). Makin gelap makin sering kering. Pola ini berasal dari variabilitas internal satu simulasi GCM, bukan ramalan kejadian nyata; baca kumpulan banyak tahun, bukan satu kotak.")

    halaman_baru(); st.markdown("## 7. Keterbatasan")
    st.markdown("- **Bukan ramalan:** GCM berjalan bebas, sehingga tahun kering di grafik tidak sama dengan tahun kering yang akan terjadi.\n- **Satu GCM, satu skenario, satu anggota:** ketidakpastian model dan skenario tidak tercakup.\n"
                "- **Transfer ke GCM tidak teruji langsung:** skill sefase tidak otomatis terbawa ke prediktor GCM, dan model melebihkan frekuensi bulan kering.\n- **Hold-out hanya lima tahun:** daya statistik rendah.\n"
                f"- **Horizon dibatasi {H1}:** setelah itu prediktor semakin keluar dari rentang yang dipelajari model.\n- **Resolusi semu:** pola antar-grid lebih banyak berasal dari klimatologi pengamatan daripada sinyal GCM.\n- **Pergeseran musiman** adalah indikasi dari satu model dan belum diuji kebermaknaannya.")
    st.markdown("## 8. Kesimpulan dan saran")
    ksp = {"sama": "belum ada perubahan frekuensi bulan kering yang dapat dipastikan; selisih yang tampak masih dalam naik-turun alami", "lebih": "bulan kering diproyeksikan lebih sering", "kurang": "bulan kering diproyeksikan lebih jarang", "sedikit": "data terlalu sedikit untuk disimpulkan"}[kode]
    st.markdown(f"**Kesimpulan:** untuk Banten {H0}-{H1} (skala {sk}, {NAMA_SKALA.get(sk, sk).replace('bln', 'bulan')}), {ksp}. Syarat terpenuhi {yak} (daftar periksa)" + (f"; model statistik tidak sepakat arahnya ({n(min(sm.values()), 0, True)} sampai {n(max(sm.values()), 0, True)} bulan per 100)." if sm and am["n_s"] < am["N"] else ".")
                + (f" Ada indikasi pergeseran musim (▲ {', '.join(naik)}{'; ▼ ' + ', '.join(turun) if turun else ''}) yang perlu diuji lebih lanjut." if naik or turun else ""))
    st.markdown("**Saran tindak lanjut**\n1. Bandingkan sebaran frekuensi bulan kering tahunan CHIRPS 1981-2025 dengan model untuk memeriksa apakah ayunan antar-tahun wajar.\n2. Periksa SPI model per grid terhadap baseline sendiri dan buat peta bias baseline.\n"
                "3. Tambahkan pembanding sederhana (delta change atau QDM) sebagai jangkar.\n4. Tambahkan GCM dan skenario lain agar ketidakpastian model iklim ikut tercakup.\n5. Uji kebermaknaan pergeseran musiman sebelum dipakai untuk keputusan.\n6. Bandingkan target ERA5 dengan CHIRPS, dan hitung ulang ambang naik-turun alami dengan lebih banyak anggota ensemble.")

    halaman_baru(); st.markdown("## Lampiran")
    st.markdown("**A. Enam syarat keyakinan**")
    st.table(pd.DataFrame([{"Syarat": c[1], "Status": "✓ terpenuhi" if c[2] else "✗ belum", "Keterangan": c[3]} for c in cek]).set_index("Syarat"))
    st.markdown("**B. Istilah**")
    st.table(pd.DataFrame([["SPI", "Indeks yang membandingkan hujan suatu periode dengan hujan biasanya. 0 = normal, negatif = lebih kering."], ["Bulan kering", "Bulan dengan SPI ≤ -1."], ["Baseline / masa lalu", "1981-2010 menurut model yang sama, supaya bias model saling meniadakan."],
                           ["Hold-out", "Periode (2021-2025) yang disimpan dan tidak dipakai menyetel apa pun, dinilai satu kali."], ["CRPSS", "Ukuran skill terhadap klimatologi; > 0 berarti lebih baik daripada sekadar iklim rata-rata."],
                           ["Simulasi / ensemble", "Banyak realisasi hujan dari model; hasil dilaporkan sebagai rata-ratanya."], ["Tingkat 1 / 2", "Validasi pada data sefase (ERA5) / pada prediktor GCM yang tidak sefase."]], columns=["Istilah", "Arti"]).set_index("Istilah"))
    st.markdown(f"**C. Sumber dan versi:** {meta.get('gcm')} ({meta.get('skenario')}); {meta.get('target')}; ERA5. Notebook {meta.get('versi_notebook', '-')}, dijalankan {meta.get('tanggal_run', '-')}. Model: {meta.get('model', '-')}. Status: {meta.get('status_gerbang', '-')}.")


if LAPORAN: halaman_laporan(); st.stop()

# ------------------------------------------------------------------ susunan utama (dashboard)
LAYAR_PENUH = """<style>body{margin:0;font-family:"Poppins","Segoe UI",Arial,sans-serif}button{margin-top:19px;width:100%;height:30px;border:1px solid #d3dde9;border-radius:6px;background:#fff;color:#10243b;font-size:12px;cursor:pointer}button:hover{background:#eef2f7}</style>
<button id="b" onclick="go()">⛶ Layar penuh</button>
<script>function go(){var b=document.getElementById('b'),f=function(){b.textContent='Tekan F11';};try{var d=window.parent.document; if(d.fullscreenElement){d.exitFullscreen();}else{var p=d.documentElement.requestFullscreen(); if(p&&p.catch){p.catch(f);}}}catch(e){f();}}</script>"""

if EMBED: LAYAR_PENUH = LAYAR_PENUH.replace("border:1px solid #d3dde9;border-radius:6px;background:#fff;color:#10243b", "border:1px solid rgba(255,255,255,.35);border-radius:6px;background:transparent;color:#fff").replace("button:hover{background:#eef2f7}", "button:hover{background:rgba(255,255,255,.12)}")
if EMBED:      # [INTEGRASI] judul sudah ada di header app.py; kontrol masuk bilah filter gelap
    with st.container(key="filt2"): c_s, c_m, c_y, c_p, c_f = st.columns([2.0, 1.5, 2.2, 2.0, 1.1], gap="small")
else: c_t, c_s, c_m, c_y, c_p, c_f = st.columns([3.0, 1.9, 1.2, 1.5, 1.9, 1.05], gap="small")
with c_s: skala = pilih(list(meta["spi_skala"]), "p3_skala", "Jangka", fmt=lambda s: NAMA_SKALA.get(s, s))
with c_m: musim = st.selectbox("Musim", list(PRESET), key="p3_musim")
with c_y: t0, t1 = st.select_slider("Tahun", th_all, value=(th_all[0], th_all[-1]), key="p3_tahun")
with c_p: mode = pilih(["Sesudah", "Sebelum"], "p3_peta2", "Downscaling", default=PETA_AWAL, fmt=lambda m: {"Sesudah": "Sesudah (5 km)", "Sebelum": "Sebelum (GCM)"}[m])
with c_f: iframe(LAYAR_PENUH, 52)
if not EMBED: c_t.markdown(f'<div class="ttl">{JUDUL_PROYEK}</div><div class="sub">{meta.get("gcm")} · {meta.get("skenario")} · periode {t0}-{t1} · vs 1981-2010 · kering = SPI ≤ −1</div>', unsafe_allow_html=True)

R = ringkas(skala, PRESET[musim], t0, t1)
if R is None: st.warning("Tidak ada data untuk pilihan ini."); st.stop()
sm = model_selisih(skala, t0, t1, R=R); am0 = arah_model(sm)
kh, cek, n_ok, yak, yak_c, am, naik, turun = kartu_html(R, sm, atas=banner(R, sm, am0)[0], zoom=FSKALA)
iframe(kh, int((H_KPI + H_BAN) * FSKALA))

col_peta, col_b, col_c = st.columns([4.2, 3.9, 3.9], gap="small")
with col_peta:
    G_ = selisih_gcm(skala, PRESET[musim], t0, t1)
    if mode == "Sebelum" and G_ is None: st.info("Peta sebelum downscaling belum bisa ditampilkan: berkas sel GCM (dashboard_gcm_sel.csv.gz) belum ada di folder dashboard. Jalankan sel 14k di notebook, lalu taruh berkasnya di folder ini. Pilih Sesudah (5 km) untuk melihat peta hasil downscaling.")
    else: gambar(peta_dari(R, mode, H_PETA, LEBAR_PETA, G=G_), H_PETA, tetap=True, judul={"Sesudah": "Peta · selisih · sesudah downscaling (5 km)", "Sebelum": "Peta · selisih · sebelum downscaling (sel GCM)"}[mode], legenda=True, leg_pos="dalam")
with col_b:
    gambar(fig_tahun(R), H_KECIL, judul="Per tahun", legenda=True)
    gambar(fig_bulan(R), H_KECIL, judul="Per bulan", legenda=True)
with col_c:
    if len(R["rk"]): gambar(fig_kab(R), H_KECIL, judul="Per kab/kota", legenda=True)
    else: st.caption("Batas kab/kota belum tersedia.")
    if len(sm) >= 2: gambar(fig_model(sm, compact=True, amb=R["amb"]), H_KECIL, judul=("Per model" if len(R["bulan"]) == 12 else "Per model · semua bulan"), legenda=True)
    else: st.caption("Data perbandingan model belum ada.")

# ------------------------------------------------------------------ baris bawah: ringkasan tiga jangka (satu baris kartu)
SUM_CSS = """<style>
body {margin:0; padding:2px 1px 0; zoom:__Z__; background:#eef2f7; font-family:"Poppins","Segoe UI",Arial,sans-serif; color:#10243b;}
.g3 {display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:8px;}
.t3 {background:#fff; border:1px solid #dde4ec; border-left:5px solid var(--c); border-radius:7px; padding:5px 10px; height:92px; box-sizing:border-box; overflow:hidden;}
.t3.on {box-shadow:0 0 0 2px #1f6fb533; border-color:#1f6fb5; border-left-color:var(--c);}
.k {font-size:10.5px; font-weight:700; color:#44566c; text-transform:uppercase; letter-spacing:.04em; white-space:nowrap;}
.r {display:flex; align-items:baseline; gap:6px; white-space:nowrap;}
.v {font-size:22px; font-weight:700; line-height:1.2;} .v small {font-size:11px; font-weight:500; color:#5b6b7f;}
.chip {margin-left:auto; padding:0 8px; border-radius:9px; font-size:10px; font-weight:700; color:#fff; white-space:nowrap;}
.red {background:#e60000;} .blue {background:#37a800;} .gray {background:#5b6b7f;}
.br {display:flex; align-items:center; gap:6px; font-size:10.5px; color:#44566c; margin-top:3px;}
.br b {width:84px; font-weight:600; white-space:nowrap;} .br span {flex:1; height:7px; background:#e6ebf1; border-radius:4px; overflow:hidden;} .br i {display:block; height:100%; border-radius:4px;}
</style>"""


def ringkasan_html(t0, t1, bulan, aktif, zoom=1.0):
    rs = []
    for s_ in meta["spi_skala"]:
        Rk = ringkas(s_, bulan, t0, t1)
        if Rk: rs.append((s_, Rk))
    if not rs: return None
    mx = max(max(r["proy"], r["base"], r["ref"]) for _, r in rs) * 1.05
    t = []
    for s_, r in rs:
        k = r["kode"]; cls = {"sama": "gray", "lebih": "red", "kurang": "blue", "sedikit": "gray"}[k]
        t.append(f'<div class="t3{" on" if s_ == aktif else ""}" style="--c:{WARNA_CHIP[WARNA_KODE[k]]}"><div class="k">{s_.replace("SPI-", "SPI ")} · {NAMA_SKALA_PANJANG.get(s_, s_).split(" (")[0]}</div>'
                 f'<div class="r"><span class="v">{n(r["sel"], 1, True)} <small>dari 100 bulan</small></span><span class="chip {cls}">{SIM[k]} {KATA[k].upper()}</span></div>'
                 f'<div class="br"><b>Masa lalu {n(r["base"], 0)}</b><span><i style="width:{r["base"] / mx * 100:.0f}%;background:#7f95ad"></i></span></div>'
                 f'<div class="br"><b>Proyeksi {n(r["proy"], 0)}</b><span><i style="width:{r["proy"] / mx * 100:.0f}%;background:#1f6fb5"></i></span></div></div>')
    return SUM_CSS.replace("__Z__", str(round(zoom, 3))) + '<div class="g3">' + "".join(t) + "</div>"


_sh = ringkasan_html(t0, t1, PRESET[musim], skala, FSKALA)
if _sh: iframe(_sh, int((H_SUM) * FSKALA))

FA, FB, FC = (' style="grid-template-columns:1fr"', "<div>", "</div>") if EMBED else ("", "", "")      # [INTEGRASI] footer 1 kotak mengikuti gaya app.py
st.markdown(f'<div class="foot"{FA}>{FB}{meta.get("gcm")} {meta.get("skenario")} · acuan {meta.get("target")} · run {meta.get("tanggal_run", "-")} · gambaran kecenderungan, bukan ramalan cuaca · pola kotak peta mengikuti sel GCM yang kasar · uji beda nyata: {"formal (notebook, block bootstrap)" if R.get("uji") == "resmi" else "pendekatan cepat (rentang tahun bukan seluruh horizon)"}{" · " + PEMBUAT if PEMBUAT else ""}{FC}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ panel "Seberapa bisa dipercaya?" (angka dibaca dari meta; tidak dihitung ulang)
V_ = meta.get("validasi") or {}
if V_ and not LAPORAN:
    with st.expander("Seberapa bisa dipercaya? (validasi dan keterbatasan)"):
        def _v(k, d=3, plus=True):
            x = V_.get(k); return n(x, d, plus) if isinstance(x, (int, float)) else "-"
        st.markdown(
            f"- **Skill yang terbukti (prediktor ERA5, {V_.get('model', 'model dipakai')}):** CRPSS rolling-origin **{_v('crpss_t1_rolling')}**, CV blok-tahun {_v('crpss_t1_cv')}, hold-out 2021-2025 {_v('crpss_t1_holdout')} (hold-out = {V_.get('holdout_status', 'data pengembangan')}). Di atas 0 = lebih baik daripada klimatologi.\n"
            f"- **Setelah diberi prediktor GCM (yang dipakai untuk proyeksi):** CRPSS {_v('crpss_t2_oof')} (klimatologi stokastik {_v('crpss_t2_klim_stokastik')}). Skill di atas **tidak otomatis terbawa** ke hasil proyeksi.\n"
            f"- **Bulan kering SPI-3 pada 1981-2020:** model {_v('kering_t2_pct', 1, False)} vs pengamatan {_v('kering_obs_pct', 1, False)} dari 100 bulan, sebab itu angka mutlak tidak ditampilkan. SPI-12 terlalu lebar: SD {_v('spi12_sd_t2', 2, False)} vs {_v('spi12_sd_obs', 2, False)}.\n"
            f"- **Arah perubahan:** {meta.get('klaim_arah_teks', 'belum dihitung')}\n"
            f"- **Horizon sampai {H1}:** setelah itu lebih dari 20% baris prediktor GCM berada di luar rentang ERA5, sehingga hasilnya bukan lagi interpolasi.\n"
            f"- **Resolusi:** pola 5 km berasal dari klimatologi CHIRPS dan hanya {V_.get('n_sel_gcm', 4)} sel GCM; baca sebagai kecenderungan wilayah, bukan detail kotak.")
