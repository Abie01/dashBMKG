"""Beranda: ringkasan keempat proyek. Kontrak halaman: dijalankan lewat runpy dengan EMBED=True (tanpa set_page_config/header).

Untuk mengubah isi kartu, edit daftar PROYEK di bawah (angka diambil dari dashboard masing-masing halaman).
Tombol "Buka" memindahkan pilihan halaman di cangkang (app.py) lewat st.session_state["page"].
"""
import html

import streamlit as st

NAVY, INK, INK2 = "#0b2a4a", "#10243b", "#44566c"

# kpi = [(nilai, label)], boleh kosong. tag = chip metode/data. temuan = satu kalimat inti.
PROYEK = [
    {"k": "1", "warna": "#e8710a", "wilayah": "Kalimantan", "judul": "Hotspot kebakaran hutan dan lahan",
     "nama": "Muhammad Rafif Danuja", "mentor": "Firmansyah, S.Tr.Klim",
     "tanya": "Kecamatan mana yang diperkirakan punya hotspot dalam 7 hari ke depan?",
     "kpi": [("0,982", "ROC-AUC"), ("0,646", "PR-AUC"), ("142 / 591", "kecamatan siaga")],
     "temuan": "Model LightGBM mengalahkan persistensi 7 hari (PR-AUC 0,646 vs 0,527) pada data uji 2026, tetapi cenderung meremehkan puncak di tahun api besar.",
     "tag": ["LightGBM", "ERA5", "591 kecamatan", "5 provinsi"]},
    {"k": "2", "warna": "#1f6fb5", "wilayah": "Pulau Jawa", "judul": "Forecast suhu udara dan anomali",
     "nama": "Abie Septian Wibowo", "mentor": "Adityo Wicaksono, S.ST",
     "tanya": "Seberapa hangat suhu 12 bulan ke depan dibanding normal 1991–2020?",
     "kpi": [("0,337 °C", "RMSE final test"), ("+0,77 °C", "rerata anomali"), ("+1,04 °C", "puncak, Des 2026")],
     "temuan": "XGBoost pooled mengalahkan persistence (RMSE 0,441) dan seasonal naive (0,593); anomali diperkirakan positif sepanjang Sep 2026–Agu 2027.",
     "tag": ["XGBoost", "HGB", "ERA5 + Niño 3.4", "6 provinsi"]},
    {"k": "3", "warna": "#0f8b8d", "wilayah": "Banten", "judul": "Proyeksi bulan kering (SPI)",
     "nama": "Gemala Aleida Fitri", "mentor": "Agus Sabana Hadi, S.Si., M.Si",
     "tanya": "Seberapa sering bulan kering (SPI ≤ −1) terjadi pada 2026–2050?",
     "kpi": [("26,3%", "bulan kering SPI-3"), ("16,2%", "acuan CHIRPS"), ("20", "anggota ensemble")],
     "temuan": "Frekuensi bulan kering proyeksi lebih tinggi dari acuan pengamatan; satu GCM dan satu skenario, jadi dibaca sebagai proyeksi bersyarat, bukan prediksi.",
     "tag": ["CMCC-ESM2 · SSP370", "XGBoost", "SPI-3/6/12", "CHIRPS"]},
    {"k": "4", "warna": "#7b61a8", "wilayah": "Indonesia", "judul": "Climate downscaling DCPP-B CMIP6",
     "nama": "Danella Nur Aisyah Latief", "mentor": "Kadarsah, M.Si",
     "tanya": "Dapatkah keluaran model iklim kasar diturunkan ke resolusi lebih halus untuk suhu dan hujan?",
     "kpi": [("2", "variabel: TAS, PR"), ("2", "metode"), ("CMIP6", "DCPP-B")],
     "temuan": "Downscaling suhu udara (TAS) dan curah hujan (PR) dari keluaran model iklim DCPP-B CMIP6 dengan CNN/U-Net dan Random Forest. Ringkasan hasil menyusul (diisi pemilik halaman).",
     "tag": ["CNN / U-Net", "Random Forest", "TAS", "PR"]},
]

st.markdown("""<style>
.hm-intro {display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin:0;}
.hm-intro .t {font-size:13px; font-weight:700; color:§NAVY; text-transform:uppercase; letter-spacing:.3px;}
.hm-intro .s {font-size:11.5px; color:§INK2;}
.hm-intro .st {margin-left:auto; display:flex; gap:8px;}
.hm-pill {background:#fff; border:1px solid #dde4ec; border-radius:12px; padding:2px 11px; font-size:11px; color:§INK2;}
.hm-pill b {color:§NAVY;}
[class*="st-key-hmc_"] {background:#fff; border:1px solid #dde4ec; border-top:4px solid var(--ac); border-radius:12px;
  box-shadow:0 1px 3px rgba(11,42,74,.07); padding:11px 14px 10px !important; gap:.5rem !important;}
.hm-top {display:flex; align-items:center; gap:8px; font-size:10.5px; font-weight:700; letter-spacing:.4px; text-transform:uppercase;}
.hm-top .n {background:var(--ac); color:#fff; border-radius:10px; padding:1px 9px;}
.hm-top .w {color:§INK2;}
.hm-h {font-size:16px; font-weight:700; color:§NAVY; line-height:1.25; margin-top:2px;}
.hm-o {font-size:11px; color:§INK2; line-height:1.4;} .hm-o b {color:§INK; font-weight:600;}
.hm-q {font-size:12px; color:§INK; line-height:1.4; font-style:italic; border-left:3px solid var(--ac); padding-left:9px; margin:4px 0 2px; min-height:38px;}
.hm-kpi {display:grid; grid-template-columns:repeat(3,1fr); gap:6px; min-height:58px;}
.hm-kpi div {background:#f4f7fb; border-radius:8px; padding:5px 8px; min-width:0;}
.hm-kpi b {display:block; font-size:16px; color:§NAVY; line-height:1.2; white-space:nowrap;}
.hm-kpi span {display:block; font-size:10px; color:§INK2; text-transform:uppercase; letter-spacing:.2px; line-height:1.2;}
.hm-kpi.kosong div {background:transparent; padding:0; grid-column:1/-1;}
.hm-t {font-size:11.5px; color:§INK; line-height:1.45; min-height:54px;}
.hm-tags {display:flex; flex-wrap:wrap; gap:4px;}
.hm-tags span {font-size:10px; color:§INK2; background:#eef2f7; border-radius:9px; padding:1px 8px; white-space:nowrap;}
[class*="st-key-hmc_"] button {background:var(--ac) !important; border:0 !important; border-radius:8px !important; min-height:34px !important;}
[class*="st-key-hmc_"] button, [class*="st-key-hmc_"] button * {color:#fff !important; -webkit-text-fill-color:#fff !important; font-weight:600 !important; font-size:12px !important;}
[class*="st-key-hmc_"] button:hover {filter:brightness(1.1);}
.hm-id {display:grid; grid-template-columns:1.25fr 1.25fr .9fr .9fr; gap:8px; margin:2px 0 8px;}
.hm-id > div {background:#fff; border:1px solid #dde4ec; border-left:4px solid §NAVY; border-radius:10px; padding:6px 12px; min-width:0;}
.hm-id .l {font-size:10px; color:§INK2; text-transform:uppercase; letter-spacing:.3px; font-weight:600;}
.hm-id .v {font-size:12.5px; font-weight:700; color:§NAVY; line-height:1.3;}
.hm-id .s {font-size:10.5px; color:§INK2; line-height:1.3;}
.hm-goal {background:§NAVY; color:#dbe8f5; border-radius:10px; padding:8px 14px; font-size:12px; line-height:1.45; margin-bottom:8px;}
.hm-goal b {color:#fff;}
.hm-bot {display:grid; grid-template-columns:1.35fr 1fr; gap:8px; margin-top:8px;}
.hm-bot > div {background:#fff; border:1px solid #dde4ec; border-radius:10px; padding:8px 14px;}
.hm-bot .h {font-size:11px; font-weight:700; color:§NAVY; text-transform:uppercase; letter-spacing:.3px; margin-bottom:6px;}
.hm-flow {display:grid; grid-template-columns:repeat(5,1fr); gap:6px;}
.hm-flow .s1 {background:#f4f7fb; border-radius:8px; padding:6px 8px; position:relative; min-width:0;}
.hm-flow .s1:not(:last-child)::after {content:"›"; position:absolute; right:-7px; top:50%; transform:translateY(-55%); color:§INK2; font-size:16px; z-index:1;}
.hm-flow b {display:block; font-size:11.5px; color:§NAVY;} .hm-flow span {font-size:10.5px; color:§INK2; line-height:1.3; display:block;}
.hm-ul div {font-size:11px; color:§INK; line-height:1.4; padding:2px 0 2px 9px; border-left:3px solid #c5d3e2; margin-bottom:4px;}
.hm-foot {background:#fff; border:1px solid #dde4ec; border-radius:8px; padding:7px 12px; font-size:11px; color:§INK2; margin-top:4px;}
@media (max-width:1100px) {.hm-q, .hm-t {min-height:0;}}
</style>""".replace("§NAVY", NAVY).replace("§INK2", INK2).replace("§INK", INK), unsafe_allow_html=True)


st.markdown("<style>" + "".join(f".st-key-hmc_{p['k']} {{--ac:{p['warna']};}}" for p in PROYEK) + "</style>", unsafe_allow_html=True)


def _buka(k):
    st.session_state["page"] = k


esc = html.escape
st.markdown("""<div class="hm-id">
<div><div class="l">Program</div><div class="v">Magang SSMI IPB University di BMKG</div><div class="s">Sekolah Sains Data, Matematika dan Informatika · 10 SKS (450 learning hours)</div></div>
<div><div class="l">Unit BMKG</div><div class="v">Analisis Perubahan Iklim</div><div class="s">Kedeputian Klimatologi</div></div>
<div><div class="l">Periode</div><div class="v">September – Desember 2026</div><div class="s">4 bulan</div></div>
<div><div class="l">Peserta</div><div class="v">4 mahasiswa · 4 proyek</div><div class="s">Statistika dan Sains Data · IPB</div></div></div>
<div class="hm-goal"><b>Tujuan:</b> menerapkan kompetensi sains data pada permasalahan nyata klimatologi di BMKG, sekaligus melatih komunikasi, kerja sama tim, dan etika profesi.</div>""", unsafe_allow_html=True)

st.markdown(f"""<div class="hm-intro"><span class="t">Ringkasan empat proyek magang</span>
<span class="s">Satu halaman satu peserta. Pilih kartu untuk membuka dashboard lengkapnya.</span>
</div>""", unsafe_allow_html=True)

cols = st.columns(4, gap="small")
for col, p in zip(cols, PROYEK):
    with col.container(key=f"hmc_{p['k']}"):
        kp = "".join(f"<div><b>{esc(v)}</b><span>{esc(l)}</span></div>" for v, l in p["kpi"])
        kp_html = f'<div class="hm-kpi">{kp}</div>' if kp else '<div class="hm-kpi kosong"><div><span>Ringkasan angka ada di dashboard halaman ini</span></div></div>'
        tags = "".join(f"<span>{esc(t)}</span>" for t in p["tag"])
        st.markdown(f"""<div>
<div class="hm-top"><span class="n">Halaman {p['k']}</span><span class="w">{esc(p['wilayah'])}</span></div>
<div class="hm-h">{esc(p['judul'])}</div><div class="hm-o"><b>{esc(p['nama'])}</b><br>Mentor: {esc(p['mentor'])}</div>
<div class="hm-q">{esc(p['tanya'])}</div>{kp_html}
<div class="hm-t" style="padding-top:8px">{esc(p['temuan'])}</div>
<div class="hm-tags" style="padding-top:6px">{tags}</div><div style="height:8px"></div></div>""", unsafe_allow_html=True)
        st.button(f"Buka halaman {p['k']}", key=f"go_{p['k']}", on_click=_buka, args=(p["k"],), width="stretch")

st.markdown("""<div class="hm-bot"><div><div class="h">Alur kerja bersama</div><div class="hm-flow">
<div class="s1"><b>1 · Data</b><span>ERA5, hotspot, CHIRPS, GCM CMIP6</span></div>
<div class="s1"><b>2 · Pra-proses</b><span>QC, normal/baseline, fitur</span></div>
<div class="s1"><b>3 · Pemodelan</b><span>Boosting, ensemble, CNN/U-Net</span></div>
<div class="s1"><b>4 · Evaluasi</b><span>Data uji vs baseline sederhana</span></div>
<div class="s1"><b>5 · Dashboard</b><span>Satu aplikasi, empat halaman</span></div></div></div>
<div><div class="h">Temuan lintas proyek</div><div class="hm-ul">
<div>Model ML mengungguli baseline sederhana pada hotspot dan suhu.</div>
<div>Puncak kejadian cenderung diremehkan; proyeksi iklim bersyarat skenario.</div>
<div>Semua luaran eksperimental, bukan produk operasional.</div></div></div></div>""", unsafe_allow_html=True)

st.markdown('<div class="hm-foot">Hasil kegiatan magang BMKG × IPB. Seluruh luaran bersifat eksperimental dan bukan produk operasional BMKG; '
            'angka pada kartu diambil dari dashboard tiap halaman.</div>', unsafe_allow_html=True)
