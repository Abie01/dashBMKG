"""Dashboard Magang BMKG x IPB: satu aplikasi, empat halaman.

Jalankan : streamlit run app.py           (dari folder ini)
Cangkang : file ini hanya mengurus tema, header, pilihan halaman, dan memanggil kode tiap halaman.
Halaman  : 1 = Hotspot Kalimantan (halaman/p1_hotspot_kalimantan/)   data: data_hotspot/
           2 = Forecast Suhu Jawa (halaman/p2_suhu_jawa/)            data: data_dashboard/
           3 = Proyeksi bulan kering Banten (halaman/p3_spi_banten/) data: data_dashboard/
           4 = kosong (menunggu isi)
Tampilan : seluruh CSS/tema ada di tema.py (satu sumber untuk semua halaman).

Kontrak halaman: tiap halaman adalah skrip Streamlit biasa yang dijalankan lewat runpy dengan dua variabel awal,
  EMBED = True            -> jangan panggil st.set_page_config / header; tema dan header ikut cangkang
  DATA_DIR = "<folder>"   -> folder data milik halaman itu
Menambah halaman 4: isi "file" dan "data" pada PAGES["4"] di bawah, lalu buat skripnya (lihat halaman/README.md).
"""
import json
import os
import runpy

import streamlit as st

st.set_page_config(page_title="Dashboard BMKG x IPB", layout="wide", initial_sidebar_state="collapsed")

from tema import CSS, header_html  # noqa: E402  (setelah set_page_config)

HERE = os.path.dirname(os.path.abspath(__file__))
HAL = os.path.join(HERE, "halaman")
DATA_DASHBOARD = os.environ.get("DASHBOARD_DATA", os.path.join(HERE, "data_dashboard"))   # halaman 2 dan 3
DATA_HOTSPOT = os.environ.get("HOTSPOT_DATA", os.path.join(HERE, "data_hotspot"))         # halaman 1


def _sub_spi():
    try:
        with open(os.path.join(DATA_DASHBOARD, "dashboard_meta.json"), encoding="utf-8") as f:
            m = json.load(f)
        return f'{m.get("gcm")} · {m.get("skenario")} · acuan {m.get("target")} · bulan kering = SPI ≤ −1 · vs 1981–2010'
    except Exception:
        return "Proyeksi frekuensi bulan kering (SPI ≤ −1) terhadap 1981–2010"


# ------------------------------------------------------------------ identitas tiap halaman (satu halaman = satu orang)
# "keep"  : key widget yang pilihannya dipertahankan saat pindah halaman dan kembali lagi.
# "file"  : skrip halaman (None = halaman kosong).   "data": folder data yang diberikan ke halaman sebagai DATA_DIR.
PAGES = {
    "1": {"judul": "Hotspot Kalimantan", "title": "Dashboard Peramalan Hotspot Kalimantan",
          "sub": "Hotspot kecamatan, iklim ERA5, dan performa model LightGBM untuk 5 provinsi",
          "nama": "Muhammad Rafif Danuja", "unit": "Statistika dan Sains Data · IPB",
          "file": os.path.join(HAL, "p1_hotspot_kalimantan", "app_hotspot.py"), "data": DATA_HOTSPOT,
          "keep": ["f_preset", "f_rng", "f_prov", "f_kab", "f_kec", "f_split", "agg_h", "basemap", "era_var"]},
    "2": {"judul": "Forecast suhu Jawa", "title": "Dashboard Forecast Suhu Udara Pulau Jawa",
          "sub": "Pemantauan t2m, anomali, dan performa model ML untuk 6 provinsi, ERA5 + Niño 3.4",
          "nama": "Abie Septian Wibowo", "unit": "Statistika dan Sains Data · IPB",
          "file": os.path.join(HAL, "p2_suhu_jawa", "app_suhu_jawa.py"), "data": DATA_DASHBOARD,
          "keep": ["prov", "algo", "src", "rng", "map_metric"]},
    "3": {"judul": "Proyeksi bulan kering Banten", "title": "Downscaling GCM Hujan untuk Proyeksi Kekeringan (SPI) di Banten",
          "sub": _sub_spi(), "nama": "Gemala Aleida Fitri", "unit": "Statistika dan Sains Data · IPB",
          "file": os.path.join(HAL, "p3_spi_banten", "app_dashboard_spi.py"), "data": DATA_DASHBOARD, "keep": []},
    "4": {"judul": "Halaman 4", "title": "Dashboard", "sub": "", "nama": "Nama Teman 4", "unit": "Magang BMKG · IPB",
          "file": None, "data": None, "keep": []},
}

SS = st.session_state

# Streamlit membuang pilihan widget yang tidak ditampilkan pada satu putaran, jadi filter sebuah halaman kembali ke bawaan
# setelah pindah halaman. Solusi: pilihan halaman aktif disalin ke SS["_keep"] di tiap putaran; bila halaman itu tampil
# lagi dan key-nya hilang, nilai ditulis ulang lewat session_state SEBELUM widget dibuat (hanya cara ini yang dipakai widget).
_cur = SS.get("page") or "1"
if _cur not in PAGES:
    _cur = "1"
_keep = SS.setdefault("_keep", {})
for _k in PAGES[_cur]["keep"]:
    if _k in SS:
        _keep[_k] = SS[_k]
    elif _k in _keep:
        SS[_k] = _keep[_k]

# ------------------------------------------------------------------ tema, header, pilihan halaman
PAGE = _cur
ID = PAGES[PAGE]
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(header_html(ID["title"], ID["sub"], ID["nama"], ID["unit"]), unsafe_allow_html=True)

with st.container(key="pgnav"):
    PAGE = st.selectbox("Halaman", list(PAGES), key="page", label_visibility="collapsed", format_func=lambda k: f"Halaman {k}")

# ------------------------------------------------------------------ isi halaman
ID = PAGES[PAGE]
if ID["file"]:
    with st.container(key=f"p{PAGE}"):
        runpy.run_path(ID["file"], init_globals={"EMBED": True, "DATA_DIR": ID["data"]})
    st.stop()

# halaman kosong
st.markdown(f'<div class="blank"><div><div class="bt">{ID["judul"]}</div><div class="bs">Konten menyusul</div></div></div>', unsafe_allow_html=True)
st.markdown('<div class="foot" style="grid-template-columns:1fr"><div>Halaman ini belum berisi dashboard. '
            'Cara menambahkan: lihat halaman/README.md</div></div>', unsafe_allow_html=True)
