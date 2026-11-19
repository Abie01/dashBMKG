# Menambah / mengisi sebuah halaman

Tiap halaman adalah skrip Streamlit biasa yang dijalankan `app.py` lewat `runpy`. Kontraknya hanya dua variabel yang sudah tersedia di skrip:

- `EMBED` (selalu `True`): jangan memanggil `st.set_page_config`, header, atau `st.markdown(CSS)`; semuanya sudah dikerjakan cangkang.
- `DATA_DIR`: folder data halaman itu (diatur di `PAGES` pada `app.py`).

## Langkah mengisi halaman 4
1. Buat folder dan skrip, mis. `halaman/p4_judul_anda/app_judul.py`, dan folder data `data_judul/` di sebelah `app.py`.
2. Di `app.py`, ubah `PAGES["4"]`: isi `judul`, `title`, `sub`, `nama`, `unit`, `"file"` (path skrip), `"data"` (path folder data), dan `"keep"` (daftar key widget yang pilihannya ingin dipertahankan saat pindah halaman).
3. Kerangka skrip minimal:

```python
import streamlit as st
if not globals().get("EMBED"):
    st.error("Jalankan lewat app.py"); st.stop()
from tema import NAVY, BLUE, ORANGE, TEAL, INK, INK2, GRID, fullscreen_btn

DATA = globals()["DATA_DIR"]

with st.container(key="filt"):                    # bilah filter navy (tinggi 80 px, menempel di atas)
    c1, c2, c3 = st.columns([1.2, 1.2, .8])
    c1.selectbox("Wilayah", ["A", "B"], key="p4_wilayah")
    with c3:
        fullscreen_btn()

st.markdown('<div class="kpis"><div class="kpi key"><div class="l">Contoh</div><div class="v">12,3</div><div class="s">keterangan</div></div></div>',
            unsafe_allow_html=True)
# kartu: st.container(key="card_xxx") + CSS tinggi; contoh lengkap ada di halaman/p1_hotspot_kalimantan/app_hotspot.py
```

## Catatan teknis
- Kelas CSS siap pakai dari `tema.py`: `.kpis/.kpi(.key/.hot)`, `.sec`, `.ct`, `.ins`, `.note`, `.sumw/.sum`, `table.ev`, `.foot/.pill/.dot`, `.chip`, `.tp`.
- Gunakan key widget yang unik antarhalaman (awali dengan nama halaman, mis. `p4_`), karena session_state dipakai bersama.
- Tambahan CSS khusus halaman cukup disuntik dari skrip halaman itu sendiri (`st.markdown("<style>...</style>", unsafe_allow_html=True)`); hanya aktif saat halaman itu tampil.
- Bila tinggi header/filter/footer di `tema.py` diubah, halaman 3 perlu menyesuaikan `OVERHEAD_EMBED` (di `app_dashboard_spi.py`).
