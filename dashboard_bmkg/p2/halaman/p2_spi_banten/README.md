# dashboard-spi-banten

Dashboard Streamlit proyeksi bulan kering (SPI ≤ −1) Banten, hasil downscaling GCM (CMCC-ESM2, SSP370).

## Tampilan
| URL | Isi |
|---|---|
| `/` | Dashboard satu layar: kesimpulan, 4 kartu, peta, per tahun, per bulan, per kab/kota, per model |
| `/?laporan=1` | Laporan naratif siap cetak PDF (termasuk heatmap tahun × bulan dan deret SPI, untuk pemahaman sendiri) |
| `/?embed=true` | Tanpa header/footer Streamlit (lebih bersih saat dipresentasikan) |
| `/?tinggi=210` | Tinggi grafik kecil dalam px (default 178; naikkan di monitor besar/layar penuh) |

Parameter bisa digabung: `/?embed=true&tinggi=210`.

## Layar penuh
Tombol **⛶ Layar penuh** di kanan atas. Jika browser memblokir, tekan **F11** (Windows/Linux) atau **Ctrl+Cmd+F** (Mac).

## Cara membaca singkat
- Kalimat di atas kartu = kesimpulan utama. Warna samping: abu = belum beda nyata, merah = lebih sering kering, biru = lebih jarang.
- **Naik-turun alami** = 2 × galat baku antar-tahun. Selisih di bawahnya belum bisa dipastikan (abu/pudar).
- Titik pada kartu *Keyakinan* = 6 syarat (hijau = terpenuhi, oranye = belum). Arahkan kursor untuk melihat isinya.
- Angka mutlak proyeksi sengaja tidak ditampilkan karena model terlalu kering di masa lalu (lihat kartu *Masa lalu*); yang dibaca adalah selisih.

## Berkas
`app_dashboard_spi.py` (aplikasi) · `dashboard_*.csv/.gz/.json` (ekspor notebook sel 14d-14f) · `banten_kabkota.geojson` · `config.toml` (tema; salin ke `.streamlit/config.toml`) · `requirements.txt`

## Otomatis menyesuaikan layar
Folder `ukuran_layar/` berisi komponen kecil yang melaporkan tinggi dan lebar jendela. Grafik mengisi sisa tinggi layar dan huruf membesar di layar lebar, termasuk saat tombol **⛶ Layar penuh** ditekan. Bila komponen tidak termuat, tampilan memakai ukuran tetap. Manual: `?vh=900&vw=1600` (paksa ukuran jendela) atau `?tinggi=200` (paksa tinggi grafik).
