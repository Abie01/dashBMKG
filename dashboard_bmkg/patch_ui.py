#!/usr/bin/env python3
"""Terapkan revisi UI ke app.py -> app_v2.py (app.py asli tidak diubah).

Pakai (taruh file ini di folder yang sama dengan app.py):
    python patch_ui.py
atau  python patch_ui.py path/ke/app.py
"""
import os
import re
import sys

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
dst = os.path.join(os.path.dirname(os.path.abspath(src)), "app_v2.py")
s = open(src, encoding="utf-8").read()
miss, done = [], 0


def rep(name, old, new):
    """Ganti tepat satu kemunculan; kalau tidak ketemu, catat dan lanjut."""
    global s, done
    n = s.count(old)
    if n != 1:
        miss.append(f"{name} (ditemukan {n}x)")
        return
    s = s.replace(old, new)
    done += 1


# ------------------------------------------------------------ 1. header: lebih lega, logo tidak mepet
rep("tinggi header + KPI", ":root{--hdr:56px; --flt:80px; --kpi:80px;", ":root{--hdr:64px; --flt:80px; --kpi:94px;")
rep("tinggi isi kolom (panel luar dihapus)", "--A:calc(var(--M) - 52px);", "--A:calc(var(--M) - 40px);")
rep("logo", ".hdr .lg {width:44px;height:44px;flex:none;border-radius:8px;",
    ".hdr .lg {width:50px;height:50px;padding:3px;box-sizing:border-box;flex:none;border-radius:8px;")
rep("judul header", ".hdr h1 {font-size:18px;", ".hdr h1 {font-size:20px;")
rep("subjudul header", ".hdr .sub {font-size:10.5px;", ".hdr .sub {font-size:11.5px;")
rep("posisi dropdown halaman", ".st-key-pgnav {position:absolute !important; top:14px;",
    ".st-key-pgnav {position:absolute !important; top:19px;")

# ------------------------------------------------------------ 2. filter bar: terang (hanya satu blok gelap, yaitu tombol/tab aktif)
rep("filter bar terang",
    ".st-key-filt {height:var(--flt); background:§NAVY; border:1px solid #0b2a4a; border-radius:8px; padding:4px 12px !important;",
    ".st-key-filt {height:var(--flt); background:#fff; border:1px solid #dde4ec; border-radius:8px; padding:4px 12px !important;")
NEW_FILT = ('.st-key-filt [data-baseweb="select"] button, .st-key-filt div[role="group"] button '
            '{border:0 !important; background:transparent !important;}\n')
pat = re.compile(r'/\* filter bergaya gelap \*/.*?(?=\[data-testid="stSelectbox"\] \*, \[data-testid="stDateInput"\] \* \{font-size:12px !important;\})', re.S)
if len(pat.findall(s)) == 1:
    s = pat.sub(lambda m: NEW_FILT, s)
    done += 1
else:
    miss.append("blok CSS filter gelap")
rep("label filter",
    '[data-testid="stWidgetLabel"] p {font-size:10px !important; color:#7a8a9d; text-transform:uppercase; letter-spacing:.4px; font-weight:600;}',
    '[data-testid="stWidgetLabel"] p {font-size:11px !important; color:#5b6b7f; letter-spacing:0; font-weight:600;}')

# ------------------------------------------------------------ 3. KPI: teks lebih besar, kartu forecast lebih menonjol
rep("kpi border+padding", "border-top:3px solid §BLUE;border-radius:8px;padding:5px 11px;", "border-top:3px solid §NAVY;border-radius:8px;padding:5px 12px;")
rep("kpi label", ".kpi .l {font-size:10.5px;color:§INK2;font-weight:600;text-transform:uppercase;letter-spacing:.3px;",
    ".kpi .l {font-size:11.5px;color:§INK2;font-weight:600;")
rep("kpi nilai", ".kpi .v {font-size:21px;font-weight:700;line-height:1.2;color:§INK;white-space:nowrap;}",
    ".kpi .v {font-size:23px;font-weight:700;line-height:1.2;color:§INK;white-space:nowrap;}")
rep("kpi sub", ".kpi .s {font-size:10px;line-height:1.25;color:§INK2;white-space:normal;max-height:25px;overflow:hidden;}",
    ".kpi .s {font-size:11px;line-height:1.25;color:§INK2;white-space:normal;max-height:28px;overflow:hidden;}")
rep("kpi forecast = hero", '("acc", f"Forecast {mon_label(ref)}"', '("acc hero", f"Forecast {mon_label(ref)}"')
rep("kpi puncak = hero", '("acc", "Puncak anomali forecast",', '("acc hero", "Puncak anomali forecast",')
rep("glosarium Niño", "def tip(txt, key=None):",
    'GLOSS["Niño34"] = ("Niño 3.4 bulan target adalah skenario dari plume IRI/CCSR, bukan observasi. Indeks konvensional "\n'
    '                   "(basis 1991–2020) lebih tinggi daripada indeks relatif; samakan definisinya dengan data latih.")\n\n\n'
    "def tip(txt, key=None):")
rep("kpi Niño + tooltip", """f"Niño 3.4 · {mon_label(ref)}", f'{fmt(nino_ref)}""", """f"Niño 3.4 · {mon_label(ref)}" + I("Niño34"), f'{fmt(nino_ref)}""")

# ------------------------------------------------------------ 4. seksi: judul rata kiri, tanpa kotak luar (hindari kartu di dalam kartu)
rep("judul seksi", ".sec {height:24px; line-height:20px; font-size:12.5px; font-weight:700; color:§NAVY; text-align:center; letter-spacing:.3px; text-transform:uppercase;}",
    ".sec {height:24px; line-height:22px; font-size:14px; font-weight:700; color:§NAVY; text-align:left; padding-left:2px; letter-spacing:0; "
    "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}")
rep("subjudul seksi", ".sec span {font-weight:500; color:#7a8a9d; text-transform:none; letter-spacing:0; margin-left:6px; font-size:10.5px;}",
    ".sec span {font-weight:500; color:§INK2; text-transform:none; letter-spacing:0; margin-left:10px; font-size:12px;}")
rep("panel luar", ".st-key-secL, .st-key-secR {height:var(--M); border:1px solid #cdd8e4; border-radius:10px; padding:6px 8px !important; box-sizing:border-box; overflow:hidden; background:rgba(255,255,255,.45);}",
    ".st-key-secL, .st-key-secR {height:var(--M); border:0; padding:0 !important; box-sizing:border-box; overflow:hidden; background:transparent;}")
rep("header seksi kiri + insight",
    """st.markdown('<div class="sec">Forecast dan Performa Model<span>observasi, prediksi, evaluasi</span></div>', unsafe_allow_html=True)""",
    """_fp = fc_for(prov)
        if len(_fp):
            _pk = _fp.loc[_fp["a"].idxmax()]
            _ins = (f"{'6 provinsi' if prov == 'ALL' else pl(prov)}: anomali positif di {int((_fp['a'] >= 0).sum())} dari {len(_fp)} bulan forecast, "
                    f"puncak {mon_label(_pk['d'])} ({fmt(_pk['a'], 2, True)} °C)")
        else:
            _ins = "observasi, prediksi, evaluasi"
        st.markdown(f'<div class="sec">Forecast dan performa model<span>{_ins}</span></div>', unsafe_allow_html=True)""")
rep("header seksi kanan", """<div class="sec">Anomali Suhu<span>sebaran spasial dan tren</span></div>""",
    """<div class="sec">Anomali suhu<span>sebaran spasial dan tren</span></div>""")

# ------------------------------------------------------------ 5. ukuran teks minimum ~11 px
rep("judul kartu", ".ct {font-size:12px;font-weight:650;", ".ct {font-size:13px;font-weight:650;")
rep("subjudul kartu", ".ct span {font-weight:500;color:#7a8a9d;font-size:10.5px;margin-left:6px;}",
    ".ct span {font-weight:500;color:#5b6b7f;font-size:11px;margin-left:8px;}")
rep("catatan kartu", ".note {font-size:9.5px;line-height:1.3;color:#6a7b8f;", ".note {font-size:10.5px;line-height:1.3;color:#5b6b7f;")
rep("header tabel", "table.ev th {font-size:10px;text-transform:uppercase;color:#7a8a9d;font-weight:600;",
    "table.ev th {font-size:11px;color:#5b6b7f;font-weight:600;")
rep("ringkasan label", ".sum .l {font-size:9.5px;color:#7a8a9d;text-transform:uppercase;", ".sum .l {font-size:11px;color:#5b6b7f;")
rep("ringkasan nilai", ".sum .v {font-size:13px;font-weight:700;", ".sum .v {font-size:14px;font-weight:700;")
rep("ringkasan sub", ".sum .s {font-size:10px;color:#4a5b70;", ".sum .s {font-size:11px;color:#4a5b70;")
rep("tick sumbu x", "bx = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=10))",
    "bx = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=11))")
rep("tick sumbu y", "by = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=10))",
    "by = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=11))")
rep("legenda", "font=dict(size=10, color=INK2), tracegroupgap=0, itemwidth=30))", "font=dict(size=11, color=INK2), tracegroupgap=0, itemwidth=30))")
rep("label bar importance", "textfont=dict(size=10, color=INK), customdata=", "textfont=dict(size=11, color=INK), customdata=")
rep("label sumbu importance", "tickfont=dict(size=10, color=INK)", "tickfont=dict(size=11, color=INK)")

# ------------------------------------------------------------ 6. teks terpotong
rep("teks ringkasan terpotong", """f"forecast 12 bln · {who}\"""", """f"12 bln · {'6 prov.' if prov == 'ALL' else pl(prov)}\"""")
rep("footer lebih ringkas",
    """<span class="w">Eksperimental, bersyarat {NINO_NOTE}; bukan produk operasional BMKG</span> · Detail di tombol ⓘ Catatan""",
    """<span class="w">Eksperimental · bersyarat skenario Niño 3.4 · bukan produk operasional BMKG</span> · Detail di ⓘ Catatan""")

# ------------------------------------------------------------ 7. warna punya peran: navy = observasi/model utama, teal = forecast, oranye = anomali positif
rep("warna bar importance", 'marker_color=BLUE, text=[fmt(v, 3) for v in r["importance"]],',
    'marker_color=[NAVY if i == len(r) - 1 else "#8aa3bd" for i in range(len(r))], text=[fmt(v, 3) for v in r["importance"]],')

# ------------------------------------------------------------ 8. grafik anomali & peta lebih bersih
rep("whisker lebih tipis", "color=TEAL, thickness=1.4, width=4),", 'color="rgba(15,139,141,.5)", thickness=1, width=2),')
rep("marker forecast", 'marker=dict(color=TEAL, size=7, line=dict(color="#fff", width=1)),', 'marker=dict(color=TEAL, size=5, line=dict(color="#fff", width=1)),')
rep("judul skala warna peta", "colorbar=dict(thickness=8, len=.85, tickfont=dict(size=9), outlinewidth=0,",
    'colorbar=dict(thickness=8, len=.8, title=dict(text="°C", side="top", font=dict(size=10)), tickfont=dict(size=10), outlinewidth=0,')

# ------------------------------------------------------------ 9. CSS tambahan (kartu hero, angka sejajar)
rep("css tambahan", "/* tinggi grafik */",
    ".kpi.hero {background:#f0f9f9; border-top-color:§TEAL;}\n"
    ".kpi.hero .v {font-size:25px;}\n"
    ".kpi .v, .sum .v, table.ev td {font-variant-numeric:tabular-nums;}\n"
    "/* tinggi grafik */")

# ------------------------------------------------------------ simpan + cek sintaks
try:
    compile(s, dst, "exec")
    ok = True
except SyntaxError as e:
    ok = False
    print(f"PERINGATAN: hasil patch punya error sintaks di baris {e.lineno}: {e.msg}")
open(dst, "w", encoding="utf-8").write(s)
print(f"{done} perubahan diterapkan -> {dst}")
if miss:
    print("Tidak ditemukan (dilewati):")
    for m in miss:
        print("  -", m)
if ok and not miss:
    print("Semua OK. Jalankan: streamlit run app_v2.py")
