# Halaman 1: Dashboard Peramalan Hotspot Kalimantan

Sumber asli: github.com/rafifdanuja15/Dashboard-Kebakaran-Hutan (dashboard/app.py). Di sini dipakai sebagai halaman 1 dashboard gabungan; logika data dan grafik tidak diubah, tampilan mengikuti template bersama (`tema.py`).

## Data (`../../data_hotspot/`)
| File | Asal di repo Rafif |
|---|---|
| `kecamatan_kalimantan.geojson` | `kecamatan_kalimantan.geojson` |
| `hotspot_kecamatan_harian.csv` | `data/hotspot_kecamatan_harian.csv` |
| `outlook_harian_kecamatan.csv`, `forecast_7hari_kecamatan.csv` | `forecast/` |
| `evaluasi_model_vs_pembanding.csv`, `pentingnya_fitur_gain.csv`, `prediksi_evaluasi_kecamatan.parquet` | `tables/` |
| `era5_harian_provinsi.parquet`, `era5_kecamatan_61..65.parquet` | hasil `build_data.py` |

Yang **tidak** ikut (tetap di repo Rafif): data mentah ERA5 `data/year=*/` (±200 MB), `models/`, `figures/`, `docs/`, tabel evaluasi lain.

## Memperbarui data
1. Ganti CSV/parquet hasil notebook di `data_hotspot/` (nama file sama).
2. Bila ERA5 berubah: `python halaman/p1_hotspot_kalimantan/build_data.py --src <repo Rafif>/data` (dari folder `dashboard_bmkg`).
3. Tanggal akhir ERA5 (`ERA5_END`) pada `app_hotspot.py` ditulis manual; sesuaikan bila data diperbarui.
