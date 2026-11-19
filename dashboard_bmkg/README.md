# Dashboard Magang BMKG × IPB

Satu aplikasi Streamlit dengan empat halaman. Setiap halaman dikerjakan satu orang; tampilan (header, filter, KPI, kartu, footer) seragam karena memakai tema yang sama.

| Halaman | Isi | Pemilik | Kode | Data |
|---|---|---|---|---|
| 1 | Peramalan hotspot kebakaran Kalimantan (LightGBM, ERA5) | Rafif Danuja | `halaman/p1_hotspot_kalimantan/` | `data_hotspot/` |
| 2 | Forecast suhu udara Pulau Jawa (ERA5 + Niño 3.4) | Abie Septian Wibowo | `halaman/p2_suhu_jawa/` | `data_dashboard/` |
| 3 | Proyeksi bulan kering (SPI) Banten, downscaling GCM | Gemala Aleida Fitri | `halaman/p3_spi_banten/` | `data_dashboard/` |
| 4 | Kosong, menunggu isi | – | – | – |

## Menjalankan
```bash
pip install -r requirements.txt
streamlit run app.py          # dari folder ini
```
Pilih halaman lewat kotak **Halaman** di kanan atas header. Pilihan filter tiap halaman dipertahankan saat berpindah halaman.

## Struktur
```
dashboard_bmkg/
├─ app.py              cangkang: tema, header, pilihan halaman, memanggil kode halaman (tidak berisi dashboard)
├─ tema.py             satu sumber tampilan: warna, CSS template, logo header, tombol layar penuh
├─ assets/             logo_bmkg.png, logo_ipb.png
├─ halaman/            kode tiap halaman (lihat halaman/README.md untuk menambah halaman)
├─ data_dashboard/     data halaman 2 dan 3 (hasil ekspor notebook)
├─ data_hotspot/       data halaman 1 (±62 MB)
└─ .streamlit/config.toml
```

## Aturan kerja
- **Ubah tampilan semua halaman** → `tema.py`. **Ubah nama/judul/unit di header** → `PAGES` di `app.py`.
- **Ubah isi sebuah halaman** → hanya file di `halaman/pN_*/` miliknya; halaman lain tidak terpengaruh.
- Halaman tidak dijalankan sendiri-sendiri: selalu lewat `streamlit run app.py`.
- Lokasi data bisa diganti lewat variabel lingkungan `DASHBOARD_DATA` (halaman 2–3) dan `HOTSPOT_DATA` (halaman 1).

## Deploy (Streamlit Community Cloud)
Main file path: `dashboard_bmkg/app.py` bila folder ini berada di dalam repo (atau `app.py` bila folder ini jadi akar repo). `requirements.txt` ikut terbaca otomatis. Tiap file data < 100 MB sehingga aman untuk GitHub tanpa Git LFS.
