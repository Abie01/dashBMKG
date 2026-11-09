"""Membuat dashboard_bmkg.html (1 file, data tertanam) dari folder data_dashboard/.
Pakai:  python build_dashboard.py            (membaca ./data_dashboard, menulis ./dashboard_bmkg.html)
        python build_dashboard.py <folder_csv> <output.html>
"""
import csv, json, os, sys

folder = sys.argv[1] if len(sys.argv) > 1 else "data_dashboard"
out = sys.argv[2] if len(sys.argv) > 2 else "dashboard_bmkg.html"
here = os.path.dirname(os.path.abspath(__file__))
NAMES = ["t2m_bulanan", "forecast", "metrik", "importance", "nino34", "normal_bulanan", "ringkasan_anomali",
         "ringkasan_anomali_provinsi", "anomali_gabungan", "prediksi_uji", "fitur_terpilih", "kamus_data"]
SKIP = {"anomali_gabungan", "prediksi_uji", "fitur_terpilih", "ringkasan_anomali_provinsi"}   # tidak dipakai dashboard, dibuang agar file ringan


def num(v):
    if v is None or v == "" or v.lower() == "nan":
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in v and "e" not in v.lower() else f
    except ValueError:
        return v


data = {}
for n in NAMES:
    p = os.path.join(folder, n + ".csv")
    if n in SKIP:
        continue
    if not os.path.exists(p):
        print("  (tidak ada)", n + ".csv")
        continue
    with open(p, encoding="utf-8-sig", newline="") as f:
        data[n] = [{k: num(v) for k, v in row.items()} for row in csv.DictReader(f)]
    print(f"  {n:22s} {len(data[n]):6d} baris")

need = ["t2m_bulanan", "forecast", "metrik", "importance", "nino34"]
miss = [n for n in need if n not in data]
if miss:
    sys.exit("File wajib belum ada: " + ", ".join(miss))

tpl = open(os.path.join(here, "dashboard_template.html"), encoding="utf-8").read()
html = tpl.replace("/*__EMBED__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))

# Tanam pustaka Plotly agar HTML jalan tanpa internet (butuh: pip install plotly)
a, z = html.index("<!--PLOTLY-START-->"), html.index("<!--PLOTLY-END-->") + len("<!--PLOTLY-END-->")
js = None
local = os.path.join(folder, "..", "plotly.min.js")
for cand in (os.path.join(here, "plotly.min.js"), local):
    if os.path.exists(cand):
        js = open(cand, encoding="utf-8").read(); break
if js is None:
    try:
        from plotly.offline import get_plotlyjs
        js = get_plotlyjs()
    except Exception:
        print("  PERINGATAN: paket plotly belum terpasang -> HTML akan memuat Plotly dari internet.")
        print("              Jalankan: pip install plotly   lalu ulangi agar file bisa dipakai offline.")
if js is not None:
    html = html[:a] + "<script>" + js.replace("</script>", "<\\/script>") + "</script>" + html[z:]
    print("  Plotly tertanam (offline).")
open(out, "w", encoding="utf-8").write(html)
print("Selesai ->", out, f"({len(html)/1e6:.1f} MB). Buka dengan klik dua kali.")