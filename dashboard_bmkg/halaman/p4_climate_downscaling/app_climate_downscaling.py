from pathlib import Path
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import xarray as xr
try:
    from shapely import contains_xy
except ImportError:
    from shapely.vectorized import contains as contains_xy

if not globals().get("EMBED"):   # halaman ini tidak berdiri sendiri: tema, header, dan navigasi ada di app.py
    st.set_page_config(page_title="Dashboard BMKG", layout="wide")
    st.error(
        "Halaman ini dijalankan lewat cangkang. Jalankan dashboard melalui app.py utama.")
    st.stop()

from tema import BLUE, GRID, INK, INK2, NAVY, ORANGE, TEAL, ZERO, fullscreen_btn  # noqa: E402

# ------------------------------------------------------------------ konstanta
BASE_DIR = Path(globals()["DATA_DIR"]).resolve()
FORECAST_DIR = BASE_DIR / "data" / "processed" / "forecast_s2020"
BOUNDARY_FILE = BASE_DIR / "data" / "boundaries" / "countries.geojson"

# Tinggi grafik (px) — sesuaikan dengan CSS tema bila perlu
H_TS, H_FI, H_MAP, H_AN = 215, 150, 215, 150

FILES = {
    "TAS": {"raw": FORECAST_DIR / "tas_dcppB_forecast_s2020_regridded_to_era5.nc",
            "corrected": FORECAST_DIR / "cnn_corrected" / "tas_cnn_corrected_dcppB_s2020.nc",
            "raw_variable": "tas", "corrected_variable": "tas_cnn_corrected",
            "label": "Suhu Udara (TAS)", "short_label": "Suhu udara", "unit": "°C",
            "obs": "ERA5 (0,25°)", "model": "CNN (U-Net)", "scale": "RdYlBu_r"},
    "PR": {"raw": FORECAST_DIR / "pr_dcppB_forecast_s2020_regridded_to_chirps025.nc",
           "corrected": FORECAST_DIR / "rf_corrected" / "pr_rf_corrected_dcppB_s2020.nc",
           "raw_variable": "pr", "corrected_variable": "pr_rf_corrected",
           "label": "Curah Hujan (PR)", "short_label": "Curah hujan", "unit": "mm/hari",
           "obs": "CHIRPS v2.0 (~0,25°)", "model": "Random Forest", "scale": "YlGnBu"},
}
MEMBER_OPTIONS = {"Ensemble Mean (r1–r5)": "mean", "r1i1p1f1": "r1i1p1f1", "r2i1p1f1": "r2i1p1f1",
                  "r3i1p1f1": "r3i1p1f1", "r4i1p1f1": "r4i1p1f1", "r5i1p1f1": "r5i1p1f1"}

# Evaluasi historis holdout DCPP-A (BUKAN akurasi forecast DCPP-B s2020)
# Evaluasi historis holdout DCPP-A.
# Angka ini BUKAN akurasi forecast DCPP-B s2020.
# Nilai Raw dan model berasal dari populasi evaluasi yang sama
# di masing-masing variabel (TAS: n=420.000; PR: n=110.700).

HISTORICAL_METRICS = {
    "TAS": {
        "Raw": {
            "RMSE": 1.3321810130,
            "MAE": 1.0558805497,
            "Korelasi": 0.6505991325,
            "Bias": 0.8457310769,
        },
        "CNN (U-Net)": {
            "RMSE": 0.3157472274,
            "MAE": 0.2381506738,
            "Korelasi": 0.9757628949,
            "Bias": -0.1484367926,
        },
    },
    "PR": {
        "Raw": {
            "RMSE": 2.9404251780,
            "MAE": 2.2719264923,
            "Korelasi": 0.4387417450,
            "Bias": 0.7556474085,
        },
        "Random Forest": {
            "RMSE": 1.4586103039,
            "MAE": 1.0729052693,
            "Korelasi": 0.8345950525,
            "Bias": 0.0838378079,
        },
    },
}

# (Model, Kelompok, RMSE, MAE, Korelasi, Bias)
# Kelompok A = ML; Kelompok B = DL.
MODEL_COMPARISON = {
    "TAS": [
        ("Random Forest", "ML",
         0.3338086951, 0.2305428066, 0.9701871527, -0.1265807970),

        ("XGBoost", "ML",
         0.4122423416, 0.2778397735, 0.9492154865, -0.0862429211),

        ("ANN", "ML",
         0.3237863529, 0.2312258680, 0.9682100427, -0.0589974001),

        ("CNN (U-Net)", "DL",
         0.3157472274, 0.2381506738, 0.9757628949, -0.1484367926),

        ("ConvLSTM", "DL",
         0.3605587628, 0.2599810974, 0.9609855881, -0.0778852145),
    ],

    "PR": [
        ("Random Forest", "ML",
         1.4586103039, 1.0729052693, 0.8345950525, 0.0838378079),

        ("XGBoost", "ML",
         1.4798608056, 1.1222479036, 0.8272333359, 0.1375285139),

        ("ANN", "ML",
         1.5324731043, 1.1681379525, 0.8179326207, 0.0108321432),

        ("CNN (grid penuh)", "DL",
         1.4340780885, 1.0917004366, 0.8395209504, -0.0952801708),

        ("ConvLSTM", "DL",
         1.7258580810, 1.3085044638, 0.7626431547, -0.2093408660),
    ],
}


GLOSS = {
    "RMSE": "Root Mean Squared Error: akar rata-rata kuadrat selisih prediksi dan observasi. Makin kecil makin baik; error besar dihukum lebih berat.",
    "MAE": "Mean Absolute Error: rata-rata selisih mutlak prediksi dan observasi. Makin kecil makin baik.",
    "Korelasi": "Kesesuaian pola variasi prediksi dan observasi. Makin mendekati +1 makin baik.",
    "Bias": "Kecenderungan overestimate (+) atau underestimate (−). Idealnya mendekati nol.",
    "Raw": "Keluaran mentah model iklim DCPP-B (CMCC-CM2-SR5) yang sudah di-regrid ke grid observasi, sebelum dikoreksi.",
    "Corrected": "Raw setelah koreksi bias dengan model ML/DL (TAS: CNN berbasis U-Net, PR: Random Forest).",    "Difference": "Corrected − Raw. Besarnya perubahan akibat koreksi, bukan error terhadap observasi.",
    "Lead Year": "Tahun ke-n sejak forecast diinisialisasi (s2020). Lead Year 1 = tahun pertama.",
    "Ensemble": "Anggota ensemble r1–r5 dari simulasi DCPP-B. Ensemble Mean = rata-rata kelimanya.",
    "DCPP": "Decadal Climate Prediction Project (CMIP6): prediksi iklim dekadal. DCPP-A = hindcast historis, DCPP-B = forecast.",
}


def tip(txt, key=None):
    return f'<span class="tp" title="{GLOSS.get(key or txt, "").replace(chr(34), chr(39))}">{txt}</span>'


def fmt(x, d=2, sign=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    s = f"{x:+,.{d}f}" if sign else f"{x:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".").replace("-", "−")


# ------------------------------------------------------------------ data
@st.cache_resource(show_spinner="Membuka dataset NetCDF...")
def open_dataset(path_string):
    path = Path(path_string)

    if not path.exists():
        raise FileNotFoundError(f"File NetCDF tidak ditemukan: {path}")

    return xr.open_dataset(path)


def find_dim(da, cands):
    return next((n for n in cands if n in da.dims), None)


def find_coord(da, cands):
    for n in cands:
        if n in da.coords:
            return n
    return next((n for n in cands if n in da.dims), None)


def get_variable(ds, name):
    if name in ds.data_vars:
        return ds[name]
    if len(ds.data_vars) == 1:
        return ds[next(iter(ds.data_vars))]
    raise KeyError(
        f"Variabel '{name}' tidak ditemukan. Tersedia: {list(ds.data_vars)}")


def get_lat_lon(da):
    la, lo = find_coord(da, ["lat", "latitude", "y"]), find_coord(
        da, ["lon", "longitude", "x"])
    if la is None or lo is None:
        raise ValueError("Koordinat latitude/longitude tidak ditemukan.")
    lat, lon = np.asarray(da[la].values, float), np.asarray(
        da[lo].values, float)
    if lat.ndim != 1 or lon.ndim != 1:
        raise ValueError("Dashboard membutuhkan koordinat lat/lon 1-dimensi.")
    return lat, lon, la, lo


def select_lead(da, lead_year):
    ld = find_dim(da, ["lead_year", "lead", "year"])
    if ld is None:
        raise ValueError(
            f"Dimensi lead year tidak ditemukan. Dimensi: {da.dims}")
    coord = np.asarray(da[ld].values) if ld in da.coords else np.arange(
        1, da.sizes[ld] + 1)
    m = np.where(coord.astype(str) == str(lead_year))[0]
    if len(m):
        return da.isel({ld: int(m[0])})
    if 0 <= int(lead_year) - 1 < da.sizes[ld]:
        return da.isel({ld: int(lead_year) - 1})
    raise ValueError(f"Lead year {lead_year} tidak tersedia.")


def select_member(da, member_value):
    md = find_dim(da, ["sample", "member", "ensemble",
                  "realization", "variant"])
    if md is None:
        return da
    if member_value == "mean":
        return da.mean(dim=md, skipna=True)
    coords = np.asarray(
        da[md].values) if md in da.coords else np.arange(da.sizes[md])
    for i, v in enumerate(coords):
        if str(v) == str(member_value):
            return da.isel({md: i})
    if str(member_value).startswith("r") and str(member_value)[1:2].isdigit():
        i = int(str(member_value)[1]) - 1
        if 0 <= i < da.sizes[md]:
            return da.isel({md: i})
    raise ValueError(
        f"Ensemble {member_value} tidak ditemukan. Tersedia: {coords}")


def convert_units(values, da, variable):
    values = np.asarray(values, float)
    units = str(da.attrs.get("units", "")).strip().lower().replace(" ", "")
    fin = values[np.isfinite(values)]
    if fin.size == 0:
        return values
    if variable == "TAS":
        if units in {"k", "kelvin"} or (units not in {"c", "degc", "deg_c", "celsius", "°c"} and np.nanmedian(fin) > 100):
            return values - 273.15
    elif variable == "PR":
        if any(t in units for t in ("mm/day", "mm/d", "mmd-1", "mmday-1", "mm/hari")):
            return values
        if any(t in units for t in ("s-1", "s^-1", "s**-1", "/s")) or (not units and np.nanmax(fin) < 0.02):
            return values * 86400.0
    return values


def as_lat_lon_array(da, la, lo):
    rem = [d for d in da.dims if d not in (la, lo)]
    if rem:
        raise ValueError(f"Dimensi belum dipilih sepenuhnya: {rem}")
    arr = np.asarray(da.transpose(la, lo).values, float)
    lat, lon = np.asarray(da[la].values, float), np.asarray(
        da[lo].values, float)
    if lat[0] > lat[-1]:
        arr = arr[::-1, :]
    if lon[0] > lon[-1]:
        arr = arr[:, ::-1]
    return arr


@st.cache_data(show_spinner="Membaca poligon wilayah Indonesia & sekitar...")
def load_geometries(boundary_path):
    path = Path(boundary_path)
    if not path.exists():
        raise FileNotFoundError(f"File batas wilayah tidak ditemukan: {path}")
    gdf = gpd.read_file(path)
    col = next((c for c in ["ADMIN", "admin", "name", "NAME", "name_en",
               "NAME_EN", "COUNTRY", "country", "SOVEREIGNT"] if c in gdf.columns), None)
    if col is None:
        raise ValueError(
            f"Kolom nama negara tidak ditemukan di GeoJSON. Kolom: {list(gdf.columns)}")
    is_indo = gdf[col].astype(str).str.contains(
        "Indonesia", case=False, na=False)
    if gdf[is_indo].empty:
        raise ValueError("Poligon Indonesia tidak ditemukan di GeoJSON.")

    def union(g): return g.union_all() if hasattr(
        g, "union_all") else g.unary_union
    nb = gdf[~is_indo].cx[92.0:144.0, -13.0:9.0]
    return union(gdf[is_indo].geometry), (union(nb.geometry) if not nb.empty else None)


@st.cache_data(show_spinner="Menyiapkan mask daratan Indonesia...")
def make_land_mask(lat_t, lon_t, boundary_path):
    g, _ = load_geometries(boundary_path)
    lo, la = np.meshgrid(np.asarray(lon_t), np.asarray(lat_t))
    return np.asarray(contains_xy(g, lo, la), bool)


@st.cache_data(show_spinner="Menyiapkan grid visualisasi batas pulau...")
def make_fine_land_mask(lon_min, lon_max, lat_min, lat_max, step, boundary_path):
    g, _ = load_geometries(boundary_path)
    flon = np.round(np.arange(lon_min, lon_max + step * .5, step), 4)
    flat = np.round(np.arange(lat_min, lat_max + step * .5, step), 4)
    fx, fy = np.meshgrid(flon, flat)
    return flon, flat, np.asarray(contains_xy(g, fx, fy), bool)


@st.cache_resource(show_spinner="Memuat data forecast & memverifikasi koordinat...")
def load_forecast(variable):
    cfg = FILES[variable]
    rda = get_variable(open_dataset(str(cfg["raw"])), cfg["raw_variable"])
    cda = get_variable(open_dataset(
        str(cfg["corrected"])), cfg["corrected_variable"])
    rlat, rlon, rla, rlo = get_lat_lon(rda)
    clat, clon, cla, clo = get_lat_lon(cda)
    if not (np.allclose(np.sort(rlat), np.sort(clat)) and np.allclose(np.sort(rlon), np.sort(clon))):
        raise ValueError(
            "Koordinat latitude/longitude antara raw dan corrected tidak cocok.")
    if find_dim(rda, ["lead_year", "lead", "year"]) is None or find_dim(cda, ["lead_year", "lead", "year"]) is None:
        raise ValueError(
            "Dimensi lead_year tidak ditemukan pada salah satu file.")
    mem = ["sample", "member", "ensemble", "realization", "variant"]
    rm, cm = find_dim(rda, mem), find_dim(cda, mem)
    if rm and cm and rda.sizes[rm] != cda.sizes[cm]:
        raise ValueError("Jumlah ensemble raw dan corrected tidak sama.")
    return dict(raw=rda, corrected=cda, lat=np.sort(rlat), lon=np.sort(rlon),
                raw_lat_name=rla, raw_lon_name=rlo, corr_lat_name=cla, corr_lon_name=clo)


def get_selected_arrays(ds, variable, lead_year, member_value):
    rda = select_member(select_lead(ds["raw"], lead_year), member_value)
    cda = select_member(select_lead(ds["corrected"], lead_year), member_value)

    rf = convert_units(
        as_lat_lon_array(rda, ds["raw_lat_name"], ds["raw_lon_name"]),
        rda,
        variable,
    )
    cf = convert_units(
        as_lat_lon_array(cda, ds["corr_lat_name"], ds["corr_lon_name"]),
        cda,
        variable,
    )

    if rf.shape != cf.shape:
        raise ValueError(
            f"Dimensi raw {rf.shape} berbeda dari corrected {cf.shape}."
        )

    lm = make_land_mask(
        tuple(float(v) for v in ds["lat"]),
        tuple(float(v) for v in ds["lon"]),
        str(BOUNDARY_FILE),
    )

    # Hanya grid daratan yang valid pada KEDUA data.
    pair_mask = lm & np.isfinite(rf) & np.isfinite(cf)

    raw_pair = np.where(pair_mask, rf, np.nan)
    corr_pair = np.where(pair_mask, cf, np.nan)
    diff_pair = np.where(pair_mask, cf - rf, np.nan)

    return {
        "raw": raw_pair,
        "corrected": corr_pair,
        "difference": diff_pair,
        "raw_visual": raw_pair,
        "corrected_visual": corr_pair,
        "difference_visual": diff_pair,
        "land_mask": lm,
        "pair_mask": pair_mask,
    }


@st.cache_data(show_spinner="Menghitung profil Lead Year 1–10...")
def compute_lead_year_profile(variable, member_value):
    ds = load_forecast(variable)
    rows = []
    for ly in range(1, 11):
        s = get_selected_arrays(ds, variable, ly, member_value)
        def m(a): return float(np.nanmean(
            a[np.isfinite(a)])) if np.isfinite(a).any() else np.nan
        rows.append(dict(ly=ly, raw=m(s["raw"]), cor=m(
            s["corrected"]), dif=m(s["difference"])))
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def build_csv(variable, lead_year, member_value):
    ds = load_forecast(variable)
    s = get_selected_arrays(ds, variable, lead_year, member_value)
    lo, la = np.meshgrid(ds["lon"], ds["lat"])
    df = pd.DataFrame({"latitude": la.ravel(), "longitude": lo.ravel(), "raw": s["raw"].ravel(),
                       "corrected": s["corrected"].ravel(), "difference_corrected_minus_raw": s["difference"].ravel(),
                       "inside_indonesia_land_mask": s["land_mask"].ravel()})
    return df[df["inside_indonesia_land_mask"]].dropna(subset=["raw", "corrected"]).to_csv(index=False).encode("utf-8")


def interpolate_bilinear_numpy(lon, lat, z, flon, flat, fmask):
    """Interpolasi visual bilinear (NumPy murni); hanya untuk tampilan peta."""
    ix1 = np.clip(np.searchsorted(lon, flon, side="right"), 1, len(lon) - 1)
    ix0 = ix1 - 1
    iy1 = np.clip(np.searchsorted(lat, flat, side="right"), 1, len(lat) - 1)
    iy0 = iy1 - 1
    dx = np.where(lon[ix1] != lon[ix0], lon[ix1] - lon[ix0], 1.0)
    dy = np.where(lat[iy1] != lat[iy0], lat[iy1] - lat[iy0], 1.0)
    wx = np.clip((flon - lon[ix0]) / dx, 0, 1)[None, :]
    wy = np.clip((flat - lat[iy0]) / dy, 0, 1)[:, None]
    corners = [(z[np.ix_(iy0, ix0)], (1 - wy) * (1 - wx)), (z[np.ix_(iy0, ix1)], (1 - wy) * wx),
               (z[np.ix_(iy1, ix0)], wy * (1 - wx)), (z[np.ix_(iy1, ix1)], wy * wx)]
    num = np.zeros((len(flat), len(flon)))
    den = np.zeros_like(num)
    for v, w in corners:
        ok = np.isfinite(v)
        num += np.where(ok, v * w, 0.0)
        den += np.where(ok, w, 0.0)
    out = np.where(den > 1e-12, num / np.where(den > 1e-12, den, 1.0), np.nan)
    miss = fmask & ~np.isfinite(out)
    if np.any(miss):
        gx, gy = np.meshgrid(lon, lat)
        ok = np.isfinite(z)
        if np.any(ok):
            fx, fy = np.meshgrid(flon, flat)
            d2 = (fx[miss][:, None] - gx[ok][None, :]) ** 2 + \
                (fy[miss][:, None] - gy[ok][None, :]) ** 2
            out[miss] = z[ok][np.argmin(d2, axis=1)]
    return np.where(fmask, out, np.nan)


def geometry_to_xy_lines(geom):
    if geom is None:
        return [], []
    xs, ys = [], []
    for poly in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
        if poly.is_empty or not hasattr(poly, "exterior"):
            continue
        bx, by = poly.exterior.xy
        xs += list(bx) + [None]
        ys += list(by) + [None]
    return xs, ys


# ------------------------------------------------------------------ state
SS = st.session_state
DEFAULTS = {"var": "TAS", "lead": 1, "member": "Ensemble Mean (r1–r5)"}
for k, v in DEFAULTS.items():
    SS.setdefault(k, v)


def reset_all():
    for k, v in DEFAULTS.items():
        SS[k] = v


# ------------------------------------------------------------------ filter
filt = st.container(key="filt")
c1, c2, c3, c4, c5, c6, c7 = filt.columns([1.3, .8, 1.4, 1.0, .5, .62, .68])
variable = c1.selectbox("Variabel Iklim", [
                        "TAS", "PR"], key="var", format_func=lambda x: FILES[x]["label"])
lead_year = c2.selectbox("Lead Year", list(range(1, 11)), key="lead")
member_label = c3.selectbox("Ensemble Member", list(
    MEMBER_OPTIONS.keys()), key="member")
export_ph = c4.empty()
c5.button("Reset", on_click=reset_all, use_container_width=True)
with c6.popover("ⓘ Catatan", use_container_width=True):
    st.markdown(
        f"""**Catatan metode dan batasan**
- **Sumber.** CMIP6-DCPP-B (CMCC-CM2-SR5), forecast s2020, Lead Year 1–10, ensemble r1–r5. Variabel: suhu udara (TAS, acuan ERA5 0,25°) dan curah hujan (PR, acuan CHIRPS v2.0).
- **Koreksi.** TAS dikoreksi dengan CNN (U-Net), PR dengan Random Forest. Difference = Corrected − Raw, **bukan** error terhadap observasi.
- **Evaluasi.** Angka evaluasi berasal dari uji historis holdout DCPP-A, **bukan** verifikasi forecast DCPP-B s2020. Kandidat dengan RMSE terendah ditandai ★; N/A = belum tersedia pada rekap eksperimen.
- **Peta.** Interpolasi dan pemotongan poligon hanya untuk tampilan visual, bukan peningkatan resolusi ilmiah. Mask daratan Indonesia berdasarkan GeoJSON.
- **Profil dan KPI.** Statistik Raw, Corrected, dan Difference dihitung pada pasangan grid daratan Indonesia yang valid pada kedua data. Rata-rata spasial tidak berbobot luas sel.

**Istilah**
- **Raw / Corrected / Difference:** keluaran mentah model / setelah koreksi / selisihnya.
- **RMSE, MAE:** ukuran error (makin kecil makin baik). **Korelasi:** makin mendekati +1 makin baik. **Bias:** idealnya mendekati nol.
- **Lead Year:** tahun ke-n sejak inisialisasi forecast. **Ensemble Mean:** rata-rata anggota r1–r5.""")
with c7:
    fullscreen_btn()

member_value = MEMBER_OPTIONS[member_label]
cfg = FILES[variable]
U = cfg["unit"]

# ------------------------------------------------------------------ pemuatan data
try:
    DS = load_forecast(variable)
    SEL = get_selected_arrays(DS, variable, lead_year, member_value)
    PROF = compute_lead_year_profile(variable, member_value)
except Exception as exc:
    export_ph.button("Unduh CSV Grid", disabled=True, use_container_width=True)
    st.error(f"Data forecast {variable} gagal dimuat: {exc}")
    st.caption("Periksa path NetCDF, nama variabel, dan GeoJSON.")
    st.stop()

export_ph.download_button("Unduh CSV Grid", data=build_csv(variable, lead_year, member_value),
                          file_name=f"{variable.lower()}_dcppB_s2020_ly{lead_year}_{member_value}.csv",
                          mime="text/csv", use_container_width=True)

raw_v = SEL["raw"][SEL["pair_mask"]]
cor_v = SEL["corrected"][SEL["pair_mask"]]
dif_v = SEL["difference"][SEL["pair_mask"]]

if raw_v.size == 0:
    st.warning(
        "Tidak ditemukan pasangan grid Raw dan Corrected yang valid "
        "di daratan Indonesia untuk kombinasi filter ini."
    )
    st.stop()

pair_n = int(SEL["pair_mask"].sum())


def layout(fig, h, **kw):
    base = dict(height=h, separators=",.", font=dict(size=11, color=INK2, family="Poppins, Segoe UI, sans-serif"),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=42, r=12, t=30, b=26),
                hoverlabel=dict(font_size=11, bgcolor="#fff", font_color=INK),
                legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom", font=dict(size=11, color=INK2), tracegroupgap=0, itemwidth=30))
    base.update(kw)
    fig.update_layout(**base)
    return fig


def unit(fig, txt):
    fig.add_annotation(xref="paper", yref="paper", x=0, y=1, xanchor="right", yanchor="bottom", text=txt,
                       showarrow=False, xshift=-4, yshift=2, font=dict(size=11, color=INK2))


def axes(fig, x=None, y=None):
    bx = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(size=11), showspikes=True, spikemode="across",
              spikethickness=1, spikecolor="#9aa8b8", spikedash="dot")
    by = dict(gridcolor=GRID, zeroline=False,
              linecolor=GRID, tickfont=dict(size=11))
    bx.update(x or {})
    by.update(y or {})
    fig.update_xaxes(**bx)
    fig.update_yaxes(**by)

def plot(fig, key=None, interactive=False, **kw):
    # Kontrol interaktif hanya untuk peta; grafik lain tetap ringkas.
    c = dict(displaylogo=False, displayModeBar=interactive, scrollZoom=interactive)
    if interactive:
        # Zoom in, zoom out, dan reset sudah bawaan Plotly 2D. Cukup buang tombol
        # yang tidak dipakai, jangan ditambah lagi lewat modeBarButtonsToAdd (jadi dobel).
        c["modeBarButtonsToRemove"] = ["select2d", "lasso2d", "autoScale2d", "zoom2d"]
        c["toImageButtonOptions"] = dict(format="png", filename="peta_bmkg_dcpp", scale=2)
    try:
        return st.plotly_chart(fig, width="stretch", config=c, key=key, **kw)
    except TypeError:
        return st.plotly_chart(fig, use_container_width=True, config=c, key=key, **kw)

def active_marker(fig):
    fig.add_vline(x=lead_year, line=dict(color=NAVY, width=1.2, dash="dot"))
    fig.add_annotation(x=lead_year, xref="x", y=1, yref="paper", text=f"LY {lead_year}", showarrow=False,
                       xanchor="left", yanchor="top", xshift=4, font=dict(size=10, color=NAVY))


# ------------------------------------------------------------------ grafik
def fig_profile():
    fig = go.Figure()
    fig.add_scatter(x=PROF["ly"], y=PROF["raw"], mode="lines+markers", name="Raw (DCPP-B)", line=dict(color="#6b7a8d", width=2, dash="dot"),
                    marker=dict(size=5), hovertemplate=f"LY %{{x}}<br>Raw: %{{y:.2f}} {U}<extra></extra>")
    fig.add_scatter(x=PROF["ly"], y=PROF["cor"], mode="lines+markers", name=f"Corrected ({cfg['model']})",
                    line=dict(color=TEAL, width=2.6), marker=dict(size=6, color=TEAL), customdata=PROF["dif"],
                    hovertemplate=f"LY %{{x}}<br>Corrected: %{{y:.2f}} {U}<br>Corrected − Raw: %{{customdata:+.2f}} {U}<extra></extra>")
    active_marker(fig)
    vals = pd.concat([PROF["raw"], PROF["cor"]]).dropna()
    rg = max(vals.max() - vals.min(), .3)
    layout(fig, H_TS, hovermode="x unified")
    axes(fig, x=dict(dtick=1, range=[.7, 10.3], title=dict(text="Lead Year", font=dict(size=10), standoff=2)),
         y=dict(range=[vals.min() - .1 * rg, vals.max() + .18 * rg]))
    unit(fig, U)
    return fig


def fig_dist():
    ok = SEL["pair_mask"]
    rv, cv = SEL["raw"][ok], SEL["corrected"][ok]
    fig = go.Figure()
    fig.add_histogram(x=rv, name="Raw", nbinsx=35, histnorm="probability", bingroup="d", opacity=.65, marker=dict(color="#8fa6bf"),
                      hovertemplate="Raw: %{x:.2f}<br>Proporsi: %{y:.3f}<extra></extra>")
    fig.add_histogram(x=cv, name="Corrected", nbinsx=35, histnorm="probability", bingroup="d", opacity=.65, marker=dict(color=TEAL),
                      hovertemplate="Corrected: %{x:.2f}<br>Proporsi: %{y:.3f}<extra></extra>")
    layout(fig, H_FI, barmode="overlay", margin=dict(l=42, r=8, t=26, b=24))
    axes(fig, x=dict(showspikes=False, title=dict(
        text=U, font=dict(size=10), standoff=2)), y=dict(rangemode="tozero"))
    unit(fig, "Proporsi")
    return fig, int(rv.size)


def fig_diff_bars():
    fig = go.Figure(go.Bar(x=PROF["ly"], y=PROF["dif"], marker=dict(color=[ORANGE if v >= 0 else BLUE for v in PROF["dif"]],
                           opacity=[1 if l == lead_year else .55 for l in PROF["ly"]]),
                           hovertemplate=f"LY %{{x}}<br>Corrected − Raw: %{{y:+.2f}} {U}<extra></extra>"))
    active_marker(fig)
    layout(fig, H_AN, showlegend=False, bargap=.25,
           margin=dict(l=42, r=12, t=22, b=26))
    axes(fig, x=dict(dtick=1, range=[.4, 10.6], showspikes=False, title=dict(text="Lead Year", font=dict(size=10), standoff=2)),
         y=dict(zeroline=True, zerolinecolor="#44566c", zerolinewidth=1.4))
    unit(fig, U)
    return fig


def map_arrays(metric):
    if metric == "raw":
        return SEL["raw_visual"], SEL["raw"], "Raw"
    if metric == "diff":
        return SEL["difference_visual"], SEL["difference"], "Corrected − Raw"
    return SEL["corrected_visual"], SEL["corrected"], "Corrected"


def fig_map(metric):
    zsrc, zland, title = map_arrays(metric)
    flon, flat, fmask = make_fine_land_mask(
        94.0, 142.0, -11.5, 6.8, 0.08, str(BOUNDARY_FILE))
    fz = interpolate_bilinear_numpy(
        DS["lon"], DS["lat"], zsrc, flon, flat, fmask)
    vals = fz[np.isfinite(fz)]
    if vals.size == 0:
        return None
    if metric == "diff":
        m = max(float(np.nanpercentile(np.abs(vals), 98)), .25)
        zmin, zmax, scale = -m, m, [[0, BLUE], [.5, "#f4f4f4"], [1, ORANGE]]
    else:
        both = np.concatenate([SEL["raw_visual"][np.isfinite(
            SEL["raw_visual"])], SEL["corrected_visual"][np.isfinite(SEL["corrected_visual"])]])
        zmin, zmax = float(np.nanpercentile(both, 2)), float(
            np.nanpercentile(both, 98))
        if variable == "PR":
            zmin = min(0.0, zmin)
        if np.isclose(zmin, zmax):
            zmin, zmax = zmin - .5, zmax + .5
        scale = cfg["scale"]
    ig, ng = load_geometries(str(BOUNDARY_FILE))
    fig = go.Figure()
    nx, ny = geometry_to_xy_lines(ng)
    if nx:
        fig.add_scatter(x=nx, y=ny, mode="lines", fill="toself", fillcolor="#E8EDF2", line=dict(color="#C2CCD6", width=.5),
                        hoverinfo="skip", showlegend=False)
    fig.add_trace(go.Heatmap(x=flon, y=flat, z=fz, colorscale=scale, zsmooth="best", zmin=zmin, zmax=zmax, connectgaps=False,
                             hoverongaps=False,
                             colorbar=dict(thickness=8, len=.85, tickfont=dict(size=10.5), outlinewidth=0, x=1.0, xpad=0,
                                           title=dict(text=U if metric != "diff" else f"Δ {U}", side="right", font=dict(size=10.5, color=INK2))),
                             hovertemplate=f"Lintang: %{{y:.2f}}°<br>Bujur: %{{x:.2f}}°<br>{title}: %{{z:.2f}} {U}<extra></extra>"))
    ix, iy = geometry_to_xy_lines(ig)
    fig.add_scatter(x=ix, y=iy, mode="lines", line=dict(
        color="#263B50", width=.8), hoverinfo="skip", showlegend=False)
    layout(fig, H_MAP, margin=dict(l=2, r=64, t=2, b=2), showlegend=False,
       hovermode="closest", dragmode="pan", uirevision="peta",
       modebar=dict(orientation="v", bgcolor="rgba(255,255,255,.8)",
                    color=INK2, activecolor=NAVY),
       xaxis=dict(range=[94.2, 141.8], showgrid=False, zeroline=False, tickfont=dict(size=9), ticksuffix="°"),
       yaxis=dict(range=[-11.4, 6.6], showgrid=False, zeroline=False, tickfont=dict(size=9), ticksuffix="°",
                  scaleanchor="x", scaleratio=1))
    return fig


def eval_table():
    hist = HISTORICAL_METRICS[variable]
    selected_model = cfg["model"]

    rows = [
        (
            "Raw",
            "Baseline",
            hist["Raw"]["RMSE"],
            hist["Raw"]["MAE"],
            hist["Raw"]["Korelasi"],
            hist["Raw"]["Bias"],
        )
    ]
    rows += [
        (m, g, rmse, mae, corr, bias)
        for m, g, rmse, mae, corr, bias
        in MODEL_COMPARISON[variable]
    ]

    cols = {
        "RMSE": 2,
        "MAE": 3,
        "Korelasi": 4,
        "Bias": 5,
    }

    def is_better(value, candidates, metric):
        if not candidates:
            return False

        if metric == "Korelasi":
            best_value = max(candidates)
        elif metric == "Bias":
            best_value = min(candidates, key=abs)
        else:
            best_value = min(candidates)

        return bool(np.isclose(value, best_value, rtol=1e-8, atol=1e-10))

    # Pemenang dihitung di dalam kelompok ML atau DL,
    # bukan dibandingkan secara global.
    group_winners = {}

    for group in ("ML", "DL"):
        group_rows = [r for r in rows if r[1] == group]

        for metric, col in cols.items():
            candidates = [
                r[col] for r in group_rows
                if np.isfinite(r[col])
            ]
            group_winners[(group, metric)] = candidates

    h = (
        '<div class="evw"><table class="ev">'
        '<thead><tr>'
        f'<th>Model</th>'
        f'<th>{tip("RMSE")} ({U})</th>'
        f'<th>{tip("MAE")} ({U})</th>'
        f'<th>{tip("Korelasi")}</th>'
        f'<th>{tip("Bias")} ({U})</th>'
        '</tr></thead><tbody>'
    )

    for mname, grp, *vals in rows:
        is_selected = mname == selected_model

        row_classes = []
        if grp == "Baseline":
            row_classes.append("base")
        if is_selected:
            row_classes.append("act")

        class_attr = " ".join(row_classes)

        model_label = mname
        if grp == "Baseline":
            model_label += " (baseline)"
        else:
            model_label += f" · {grp}"

        if is_selected:
            model_label += " ✓ forecast"

        h += f'<tr class="{class_attr}"><td>{model_label}</td>'

        for metric, value in zip(cols, vals):
            if not np.isfinite(value):
                h += '<td>N/A</td>'
                continue

            winner = (
                grp in ("ML", "DL")
                and is_better(
                    value,
                    group_winners[(grp, metric)],
                    metric,
                )
            )

            classes = "min" if winner else ""
            display = fmt(value, 3, metric == "Bias")

            marker = ""
            if winner:
                marker = " ★"

            bar = ""
            if metric == "RMSE":
                all_rmse = [
                    r[2] for r in rows
                    if np.isfinite(r[2]) and r[2] > 0
                ]
                max_rmse = max(all_rmse) if all_rmse else 1
                bar_width = max(0, min(40, value / max_rmse * 40))
                bar = (
                    f'<span class="bar" '
                    f'style="width:{bar_width:.0f}px"></span>'
                )

            h += (
                f'<td class="{classes}">'
                f'{bar}{display}{marker}'
                '</td>'
            )

        h += "</tr>"

    return h + "</tbody></table></div>"

    def best(k):
        v = [r[cols[k]] for r in rows if not np.isnan(r[cols[k]])]
        if not v:
            return None
        return max(v) if k == "Korelasi" else min(v, key=abs) if k == "Bias" else min(v)

    bst = {k: best(k) for k in cols}
    mx = max([r[2] for r in rows if not np.isnan(r[2])] or [1])
    h = (f'<div class="evw"><table class="ev"><thead><tr><th>Model</th><th>{tip("RMSE")} ({U})</th><th>{tip("MAE")} ({U})</th>'
         f'<th>{tip("Korelasi")}</th><th>{tip("Bias")} ({U})</th></tr></thead><tbody>')
    for mname, grp, *vals in rows:
        act = mname == cfg["model"]
        h += f'<tr class="{"base" if grp == "Baseline" else ""} {"act" if act else ""}"><td>{mname}{" (baseline)" if grp == "Baseline" else f" · {grp}"}</td>'
        for k, v in zip(cols, vals):
            if np.isnan(v):
                h += '<td>N/A</td>'
                continue
            star = bst[k] is not None and v == bst[k]
            bar = f'<span class="bar" style="width:{v / mx * 40:.0f}px"></span>' if k == "RMSE" else ""
            h += f'<td class="{"min" if star else ""}">{bar}{fmt(v, 3, k == "Bias")}{" ★" if star else ""}</td>'
        h += "</tr>"
    return h + "</tbody></table></div>"


# ------------------------------------------------------------------ KPI
def sg(v): return "pos" if v >= 0 else "neg"
def chip(
    v): return f'<span class="chip {sg(v)}">{"Positif" if v >= 0 else "Negatif"}</span>'


def I(k): return f' <span class="tp" title="{GLOSS[k]}">ⓘ</span>'


dmean = float(np.nanmean(dif_v)) if dif_v.size else np.nan
hist = HISTORICAL_METRICS[variable]
ckey = cfg["model"]
rmse_drop = (hist["Raw"]["RMSE"] - hist[ckey]["RMSE"]) / \
    hist["Raw"]["RMSE"] * 100
pmax = PROF.loc[PROF["dif"].abs().idxmax()]

cards = [
    ("", f"Raw rerata · LY {lead_year}" + I("Raw"), f'{fmt(np.nanmean(raw_v))} <small>{U}</small>',
     f'{member_label} · rentang {fmt(np.nanpercentile(raw_v, 5))} – {fmt(np.nanpercentile(raw_v, 95))}'),
    ("key", f"Corrected rerata · LY {lead_year}" + I("Corrected"), f'{fmt(np.nanmean(cor_v))} <small>{U}</small>',
     f'Koreksi {cfg["model"]} · rentang {fmt(np.nanpercentile(cor_v, 5))} – {fmt(np.nanpercentile(cor_v, 95))}'),
    ("", "Difference" + I("Difference"), f'<span class="{sg(dmean)}">{fmt(dmean, 2, True)}</span> <small>{U}</small>{chip(dmean)}',
     "Corrected − Raw, rata-rata daratan"),
    ("key hot", "Selisih terbesar antar-LY", f'<span class="{sg(pmax["dif"])}">{fmt(pmax["dif"], 2, True)}</span> <small>{U}</small>',
     f'Lead Year {int(pmax["ly"])} · rata-rata spasial'),
    ("", "RMSE historis turun" + I("RMSE"), f'{fmt(rmse_drop, 1)}<small>%</small>',
     f'{fmt(hist["Raw"]["RMSE"], 3)} → {fmt(hist[ckey]["RMSE"], 3)} {U} · {ckey} (DCPP-A)'),
    ("", "Grid daratan valid", f'{pair_n:,}'.replace(
        ",", "."), f'pasangan Raw & Corrected · {cfg["obs"]}'),
]
st.markdown('<div class="kpis">' + "".join(
    f'<div class="kpi {c}"><div class="l">{l}</div><div class="v">{v}</div><div class="s" title="{re.sub("<[^>]+>", "", s_)}">{s_}</div></div>'
    for c, l, v, s_ in cards) + "</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ susunan utama
with st.container(key="main"):
    L, R = st.columns([1.56, 1])

    # ---------------- kiri: profil, distribusi, evaluasi
    with L.container(key="secL"):
        st.markdown(
            '<div class="sec">Forecast dan Performa Model<span>profil lead year, distribusi, evaluasi</span></div>', unsafe_allow_html=True)
        with st.container(key="tsCard"):
            st.markdown(f'<div class="ct">{tip("Profil forecast", "Lead Year")} {cfg["short_label"].lower()}, Raw vs Corrected'
                        f'<span>rata-rata spasial daratan Indonesia · {member_label} · Lead Year 1–10</span></div>', unsafe_allow_html=True)
            arah = "lebih tinggi" if dmean >= 0 else "lebih rendah"
            st.markdown(f'<div class="ins">Pada Lead Year {lead_year}, Corrected rata-rata <b>{arah} {fmt(abs(dmean))} {U}</b> dari Raw; '
                        f'selisih antar-LY terbesar pada <b>LY {int(pmax["ly"])} ({fmt(pmax["dif"], 2, True)} {U})</b>.</div>', unsafe_allow_html=True)
            plot(fig_profile(), key="c_prof")
        with st.container(key="rowL"):
            a, b = st.columns(2)
            with a.container(key="fiCard"):
                fg, n_ok = fig_dist()
                st.markdown(f'<div class="ct">Distribusi nilai grid<span>Raw vs Corrected · LY {lead_year} · {n_ok:,} grid</span></div>'.replace(
                    ",", "."), unsafe_allow_html=True)
                plot(fg, key="c_dist")
            with b.container(key="evCard"):
                st.markdown(
                    f'<div class="ct">Evaluasi historis kandidat model {tip("ⓘ", "DCPP")}<span>{variable} · DCPP-A vs {cfg["obs"]}</span></div>', unsafe_allow_html=True)
                st.markdown(eval_table(), unsafe_allow_html=True)
st.markdown(
    '<div class="note">'
    '★ = terbaik dalam kelompok ML atau DL untuk metrik tersebut · '
    '✓ forecast = model yang digunakan pada forecast variabel terpilih · '
    'N/A = data tidak tersedia · evaluasi historis DCPP-A, '
    'bukan verifikasi forecast DCPP-B s2020'
    '</div>',
    unsafe_allow_html=True,
)
# ---------------- kanan: peta dan selisih
with R.container(key="secR"):
    st.markdown('<div class="sec">Sebaran Spasial<span>peta dan perubahan akibat koreksi</span></div>',
                unsafe_allow_html=True)
    with st.container(key="mapCard"):
        with st.container(key="mapHead"):
            t1, t2 = st.columns([1, 1.25], vertical_alignment="center")
            t1.markdown(
                f'<div class="ct" style="padding-top:8px">Peta {cfg["short_label"].lower()} · LY {lead_year}</div>',
                unsafe_allow_html=True)
            metric = t2.selectbox(
                "Metrik peta", ["corr", "raw", "diff"], key="map_metric",
                label_visibility="collapsed",
                format_func=lambda m: {"corr": "Corrected", "raw": "Raw",
                                       "diff": "Difference (Corrected − Raw)"}[m])

        fm = fig_map(metric)
        if fm is None:
            st.warning("Gagal memetakan nilai pada poligon daratan Indonesia.")
        else:
            plot(fm, key="c_map", interactive=True)   

        _, land, ttl = map_arrays(metric)
        lv = land[np.isfinite(land)]
        sm = [("Rerata daratan", f"{fmt(np.nanmean(lv), 2, metric == 'diff')} {U}", ttl),
              ("Maksimum", f"{fmt(np.nanmax(lv), 2, metric == 'diff')} {U}", "sel daratan"),
              ("Minimum", f"{fmt(np.nanmin(lv), 2, metric == 'diff')} {U}", "sel daratan"),
              ("Sebaran (SD)", f"{fmt(np.nanstd(lv), 2)} {U}", "spasial")]
        st.markdown('<div class="sumw">' + "".join(
            f'<div class="sum"><div class="l">{l}</div><div class="v" title="{v} · {t}">{v}</div><div class="s">{t}</div></div>'
            for l, v, t in sm) + "</div>", unsafe_allow_html=True)

    with st.container(key="anCard"):
        st.markdown(
            f'<div class="ct">Selisih Corrected − Raw per Lead Year {tip("ⓘ", "Difference")}'
            f'<span>rata-rata spasial · {cfg["model"]}</span></div>', unsafe_allow_html=True)
        plot(fig_diff_bars(), key="c_diff")
# ------------------------------------------------------------------ footer
_full = ("Forecast DCPP-B s2020 (CMIP6-DCPP, CMCC-CM2-SR5). Difference = Corrected − Raw, bukan error terhadap observasi. "
         "Evaluasi berasal dari uji historis DCPP-A. Interpolasi peta hanya untuk visual. Detail metode ada di tombol Catatan.").replace(chr(34), chr(39))
st.markdown(
    f'<div class="foot"><div>Info data <span class="pill"><span class="dot"></span>Forecast s2020 · Lead Year 1–10 · {cfg["label"]}</span></div>'
    f'<div><b>{cfg["obs"].split(" ")[0]}</b> · BMKG Direktorat Perubahan Iklim · <span class="w">Evaluasi historis, bukan verifikasi s2020</span> · '
    f'<span class="tp" title="{_full}">Selengkapnya ⓘ</span></div></div>', unsafe_allow_html=True)
