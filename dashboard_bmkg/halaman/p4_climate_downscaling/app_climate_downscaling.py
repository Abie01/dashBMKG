from pathlib import Path


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

from tema import fullscreen_btn
# ============================================================

# 1. KONFIGURASI PROYEK & METRIK AKTUAL

# ============================================================

# ============================================================
# 1. KONFIGURASI PROYEK & METRIK AKTUAL
# ============================================================

# Halaman ini dijalankan melalui app.py utama.
if not globals().get("EMBED", False):
    st.error("Jalankan dashboard melalui app.py utama.")
    st.stop()

# DATA_DIR diberikan oleh app.py utama.
# Lokasi ini menunjuk ke root proyek magangproject.
BASE_DIR = Path(globals()["DATA_DIR"]).resolve()

FORECAST_DIR = (
    BASE_DIR / "data" / "processed" / "forecast_s2020"
)

BOUNDARY_FILE = (
    BASE_DIR / "data" / "boundaries" / "countries.geojson"
)

FILES = {

    "TAS": {

        "raw": FORECAST_DIR / "tas_dcppB_forecast_s2020_regridded_to_era5.nc",

        "corrected": FORECAST_DIR / "cnn_corrected" / "tas_cnn_corrected_dcppB_s2020.nc",

        "raw_variable": "tas",

        "corrected_variable": "tas_cnn_corrected",

        "label": "Suhu Udara (TAS)",

        "short_label": "Suhu Udara",

        "unit": "°C",

        "obs": "ERA5 (0,25°)",

        "model": "CNN / U-Net",

        "scale": "RdYlBu_r",

    },

    "PR": {

        "raw": FORECAST_DIR / "pr_dcppB_forecast_s2020_regridded_to_chirps025.nc",

        "corrected": FORECAST_DIR / "rf_corrected" / "pr_rf_corrected_dcppB_s2020.nc",

        "raw_variable": "pr",

        "corrected_variable": "pr_rf_corrected",

        "label": "Curah Hujan (PR)",

        "short_label": "Curah Hujan",

        "unit": "mm/hari",

        "obs": "CHIRPS v2.0 (~0,25°)",

        "model": "Random Forest",

        "scale": "YlGnBu",

    },

}


MEMBER_OPTIONS = {

    "Ensemble Mean (r1–r5)": "mean",

    "r1i1p1f1": "r1i1p1f1",

    "r2i1p1f1": "r2i1p1f1",

    "r3i1p1f1": "r3i1p1f1",

    "r4i1p1f1": "r4i1p1f1",

    "r5i1p1f1": "r5i1p1f1",

}


# Evaluasi historis holdout DCPP-A yang tercatat pada eksperimen proyek.

# Bukan metrik akurasi forecast DCPP-B s2020.

HISTORICAL_METRICS = {

    "TAS": {

        "Raw": {"RMSE": 1.2857, "MAE": 1.0298, "Korelasi": 0.6625, "Bias": 0.8207},

        "CNN / U-Net": {"RMSE": 0.3202, "MAE": 0.2485, "Korelasi": 0.9762, "Bias": -0.1789},

    },

    "PR": {

        "Raw": {"RMSE": 2.9050, "MAE": 2.2434, "Korelasi": 0.4498, "Bias": 0.8965},

        "Random Forest": {"RMSE": 1.9016, "MAE": 1.4301, "Korelasi": 0.8070, "Bias": 0.9053},

    },

}


# Rekap perbandingan seluruh kandidat model historis (ML vs DL).

# Nilai yang belum tersedia dibiarkan np.nan (ditampilkan sebagai N/A, tidak dikarang).

MODEL_ORDER = ["Random Forest", "XGBoost", "ANN", "CNN / U-Net", "ConvLSTM"]


MODEL_COMPARISON = {

    "TAS": pd.DataFrame([

        {"Model": "Random Forest", "Kelompok": "Machine Learning",
            "RMSE": np.nan, "MAE": np.nan, "Korelasi": np.nan, "Bias": np.nan},

        {"Model": "XGBoost", "Kelompok": "Machine Learning", "RMSE": np.nan,
            "MAE": np.nan, "Korelasi": np.nan, "Bias": np.nan},

        {"Model": "ANN", "Kelompok": "Machine Learning", "RMSE": np.nan,
            "MAE": np.nan, "Korelasi": np.nan, "Bias": np.nan},

        {"Model": "CNN / U-Net", "Kelompok": "Deep Learning", "RMSE": 0.3202,
            "MAE": 0.2485, "Korelasi": 0.9762, "Bias": -0.1789},

        {"Model": "ConvLSTM", "Kelompok": "Deep Learning", "RMSE": 0.3586267,
            "MAE": 0.2561920, "Korelasi": 0.9618377, "Bias": -0.0777299},

    ]),

    "PR": pd.DataFrame([

        {"Model": "Random Forest", "Kelompok": "Machine Learning",
            "RMSE": 1.459, "MAE": np.nan, "Korelasi": 0.835, "Bias": np.nan},

        {"Model": "XGBoost", "Kelompok": "Machine Learning", "RMSE": 1.480,
            "MAE": np.nan, "Korelasi": 0.827, "Bias": np.nan},

        {"Model": "ANN", "Kelompok": "Machine Learning", "RMSE": 1.532,
            "MAE": np.nan, "Korelasi": 0.818, "Bias": np.nan},

        {"Model": "CNN / U-Net", "Kelompok": "Deep Learning", "RMSE": np.nan,
            "MAE": np.nan, "Korelasi": np.nan, "Bias": np.nan},

        {"Model": "ConvLSTM", "Kelompok": "Deep Learning", "RMSE": 1.7258580,
            "MAE": 1.3085045, "Korelasi": 0.7626432, "Bias": -0.2093409},

    ]),

}


# ============================================================

# 2. STYLE CSS (SINGLE-SCREEN OPERATIONAL BMKG THEME)

# ============================================================

st.markdown("""

<style>

    :root {

        --navy: #142B45;

        --blue: #245B83;

        --teal: #087F8C;

        --bg: #EDF2F6;

        --panel: #FFFFFF;

        --ink: #172B3A;

        --muted: #52677A;

        --border: #CBD6E0;

    }



    html, body, [class*="css"] {

        font-family: "Aptos", "Segoe UI", Arial, sans-serif;

    }



    .stApp {

        background-color: #EDF2F6;

        color: #172B3A;

    }





.block-container {

    max-width: 1920px;

    padding: 0.8rem 1.2rem 0.8rem 1.2rem;

}



div[data-testid="stVerticalBlock"] {

    gap: 0.7rem;

}



div[data-testid="stHorizontalBlock"] {

    gap: 0.85rem;

}





    header[data-testid="stHeader"] {

        height: 1.75rem;

        background: transparent;

    }



    [data-testid="stToolbar"] {

        right: 0.8rem;

    }





    /* HEADER */

    .hero {

        display: flex;

        align-items: center;

        justify-content: space-between;

        gap: 1rem;

        padding: 0.48rem 1rem;

        border-radius: 9px;

        background: linear-gradient(105deg, #142B45 0%, #245B83 65%, #087F8C 100%);

        color: #FFFFFF;

        box-shadow: 0 2px 10px rgba(20, 43, 69, 0.14);

    }



    .hero * {

        color: #FFFFFF !important;

    }



    .hero-kicker {

        font-size: 0.62rem;

        letter-spacing: 0.11em;

        text-transform: uppercase;

        font-weight: 700;

        color: #CFE2EE !important;

        margin-bottom: 0.1rem;

    }



    .hero h1 {

        font-size: 1.22rem;

        line-height: 1.15;

        margin: 0 0 0.1rem 0;

        font-weight: 800;

    }



    .hero p {

        font-size: 0.72rem;

        margin: 0;

        color: #E7F1F7 !important;

    }



    .hero-meta {

        text-align: right;

        white-space: nowrap;

        font-size: 0.69rem;

        color: #E7F1F7 !important;

    }



    .hero-meta strong {

        display: block;

        font-size: 0.86rem;

        letter-spacing: 0.02em;

    }





[data-testid="stVerticalBlockBorderWrapper"] {

    background-color: #FFFFFF;

    border: 1px solid #CBD6E0 !important;

    border-radius: 10px !important;

    padding: 0.75rem 0.85rem !important;

    box-shadow: 0 2px 8px rgba(20, 43, 69, 0.05);

}



.panel-title {

    font-size: 0.98rem;

    font-weight: 800;

    color: #142B45;

    margin-bottom: 0.25rem;

    line-height: 1.4;

}



.panel-sub {

    font-size: 0.76rem;

    color: #52677A;

    margin-bottom: 0.4rem;

    line-height: 1.4;

}





    /* FILTER CONTROLS */

    [data-testid="stSelectbox"] label {

        font-size: 0.69rem !important;

        font-weight: 700 !important;

        color: #172B3A !important;

        margin-bottom: 0.1rem !important;

    }



    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {

        min-height: 1.95rem;

        background-color: #FFFFFF !important;

        border: 1px solid #A9BAC8 !important;

        border-radius: 6px !important;

        font-size: 0.78rem !important;

    }



    [data-testid="stSelectbox"] div[data-baseweb="select"] * {

        color: #172B3A !important;

    }





/* KPI CARDS - READABLE SIZE */

[data-testid="stMetric"] {

    background-color: #FFFFFF;

    border: 1px solid #CBD6E0;

    border-top: 4px solid #087F8C;

    border-radius: 10px;

    padding: 0.75rem 0.9rem;

    min-height: 90px;

    box-shadow: 0 2px 7px rgba(20, 43, 69, 0.07);

}



[data-testid="stMetricLabel"] {

    color: #52677A !important;

    font-size: 0.78rem !important;

    font-weight: 700 !important;

}



[data-testid="stMetricValue"] {

    color: #142B45 !important;

    font-size: 1.55rem !important;

    font-weight: 800 !important;

    line-height: 1.3 !important;

    white-space: normal !important;

}





    /* DOWNLOAD BUTTON */

    [data-testid="stDownloadButton"] button {

        background-color: #142B45 !important;

        color: #FFFFFF !important;

        border: 1px solid #142B45 !important;

        border-radius: 6px !important;

        font-size: 0.73rem !important;

        font-weight: 700 !important;

        min-height: 1.95rem;

        width: 100%;

    }



    [data-testid="stDownloadButton"] button:hover {

        background-color: #245B83 !important;

        border-color: #245B83 !important;

    }



    /* INFO STRIPS & NOTES */



.note-box {

    background-color: #F4F8FB;

    border-left: 4px solid #087F8C;

    border-radius: 6px;

    padding: 0.65rem 0.8rem;

    font-size: 0.78rem;

    color: #172B3A;

    line-height: 1.55;

}



.warn-box {

    background-color: #F7F9FB;

    border: 1px solid #CBD6E0;

    border-radius: 6px;

    padding: 0.55rem 0.75rem;

    font-size: 0.75rem;

    color: #52677A;

    line-height: 1.5;

}



.sci-guide {

    font-size: 0.82rem;

    color: #172B3A;

    line-height: 1.6;

}





    /* TABS COMPACT */

    button[data-baseweb="tab"] {

        font-size: 0.71rem !important;

        font-weight: 700 !important;

        padding: 0.25rem 0.6rem !important;

        color: #52677A !important;

    }



    button[data-baseweb="tab"][aria-selected="true"] {

        color: #142B45 !important;

        border-bottom-color: #087F8C !important;

    }



    /* DATAFRAME & CAPTION */

    [data-testid="stDataFrame"] {

        border: 1px solid #CBD6E0;

        border-radius: 6px;

    }



    [data-testid="stCaptionContainer"] {

        color: #52677A !important;

        font-size: 0.64rem !important;

        line-height: 1.25 !important;

    }



    .footer-bar {

        text-align: center;

        font-size: 0.64rem;

        color: #52677A;

        padding: 0.1rem 0 0 0;

    }

</style>

""", unsafe_allow_html=True)


def panel_box():
    """Wrapper container dengan fallback kompatibilitas versi Streamlit."""

    try:

        return st.container(border=True)

    except TypeError:

        return st.container()


# ============================================================

# 3. FUNGSI PEMBACAAN DATA, UNIT, & MASKING

# ============================================================

@st.cache_resource(show_spinner="Membuka dataset NetCDF...")
def open_dataset(path_string: str) -> xr.Dataset:

    path = Path(path_string)

    if not path.exists():

        raise FileNotFoundError(f"File NetCDF tidak ditemukan: {path}")

    return xr.open_dataset(path)


def find_dim(da: xr.DataArray, candidates: list[str]) -> str | None:

    for name in candidates:

        if name in da.dims:

            return name

    return None


def find_coord(da: xr.DataArray, candidates: list[str]) -> str | None:

    for name in candidates:

        if name in da.coords:

            return name

    for name in candidates:

        if name in da.dims:

            return name

    return None


def get_variable(ds: xr.Dataset, preferred_name: str) -> xr.DataArray:

    if preferred_name in ds.data_vars:

        return ds[preferred_name]

    if len(ds.data_vars) == 1:

        return ds[next(iter(ds.data_vars))]

    raise KeyError(

        f"Variabel '{preferred_name}' tidak ditemukan. Tersedia: {list(ds.data_vars)}"

    )


def get_lat_lon(da: xr.DataArray):

    lat_name = find_coord(da, ["lat", "latitude", "y"])

    lon_name = find_coord(da, ["lon", "longitude", "x"])

    if lat_name is None or lon_name is None:

        raise ValueError("Koordinat latitude/longitude tidak ditemukan.")

    lat = np.asarray(da[lat_name].values, dtype=float)

    lon = np.asarray(da[lon_name].values, dtype=float)

    if lat.ndim != 1 or lon.ndim != 1:

        raise ValueError("Dashboard membutuhkan koordinat lat/lon 1-dimensi.")

    return lat, lon, lat_name, lon_name


def select_lead(da: xr.DataArray, lead_year: int) -> xr.DataArray:

    lead_dim = find_dim(da, ["lead_year", "lead", "year"])

    if lead_dim is None:

        raise ValueError(
            f"Dimensi lead year tidak ditemukan. Dimensi: {da.dims}")

    coord = (

        np.asarray(da[lead_dim].values)

        if lead_dim in da.coords

        else np.arange(1, da.sizes[lead_dim] + 1)

    )

    matches = np.where(coord.astype(str) == str(lead_year))[0]

    if len(matches):

        return da.isel({lead_dim: int(matches[0])})

    if 0 <= int(lead_year) - 1 < da.sizes[lead_dim]:

        return da.isel({lead_dim: int(lead_year) - 1})

    raise ValueError(
        f"Lead year {lead_year} tidak tersedia pada dimensi {lead_dim}.")


def select_member(da: xr.DataArray, member_value: str) -> xr.DataArray:

    member_dim = find_dim(
        da, ["sample", "member", "ensemble", "realization", "variant"])

    if member_dim is None:

        return da

    if member_value == "mean":

        return da.mean(dim=member_dim, skipna=True)

    coords = (

        np.asarray(da[member_dim].values)

        if member_dim in da.coords

        else np.arange(da.sizes[member_dim])

    )

    requested = str(member_value)

    for idx, val in enumerate(coords):

        if str(val) == requested:

            return da.isel({member_dim: idx})

    if requested.startswith("r") and requested[1:2].isdigit():

        idx = int(requested[1]) - 1

        if 0 <= idx < da.sizes[member_dim]:

            return da.isel({member_dim: idx})

    raise ValueError(
        f"Ensemble {requested} tidak ditemukan. Tersedia: {coords}")


def convert_units(values: np.ndarray, da: xr.DataArray, variable: str) -> np.ndarray:

    values = np.asarray(values, dtype=float)

    units_raw = str(da.attrs.get("units", "")).strip()

    units = units_raw.lower().replace(" ", "")

    finite = values[np.isfinite(values)]

    if finite.size == 0:

        return values

    if variable == "TAS":

        if units in {"k", "kelvin"}:

            return values - 273.15

        if units in {"c", "degc", "deg_c", "celsius", "°c"}:

            return values

        if np.nanmedian(finite) > 100.0:

            return values - 273.15

        return values

    if variable == "PR":

        if any(tok in units for tok in ("mm/day", "mm/d", "mmd-1", "mmday-1", "mm/hari")):

            return values

        if any(tok in units for tok in ("s-1", "s^-1", "s**-1", "/s")):

            return values * 86400.0

        # Fallback hanya jika atribut units kosong dan skala jelas berupa laju per detik.

        if not units and np.nanmax(finite) < 0.02:

            return values * 86400.0

        return values

    return values


def as_lat_lon_array(da: xr.DataArray, lat_name: str, lon_name: str) -> np.ndarray:

    remaining = [d for d in da.dims if d not in (lat_name, lon_name)]

    if remaining:

        raise ValueError(f"Dimensi belum dipilih sepenuhnya: {remaining}")

    arr = np.asarray(da.transpose(lat_name, lon_name).values, dtype=float)

    lat = np.asarray(da[lat_name].values, dtype=float)

    lon = np.asarray(da[lon_name].values, dtype=float)

    if lat[0] > lat[-1]:

        arr = arr[::-1, :]

    if lon[0] > lon[-1]:

        arr = arr[:, ::-1]

    return arr


@st.cache_data(show_spinner="Membaca poligon wilayah Indonesia & sekitar...")
def load_geometries(boundary_path: str):

    path = Path(boundary_path)

    if not path.exists():

        raise FileNotFoundError(f"File batas wilayah tidak ditemukan: {path}")

    gdf = gpd.read_file(path)

    possible_names = [

        "ADMIN", "admin", "name", "NAME", "name_en", "NAME_EN",

        "COUNTRY", "country", "SOVEREIGNT",

    ]

    name_col = next((c for c in possible_names if c in gdf.columns), None)

    if name_col is None:

        raise ValueError(
            f"Kolom nama negara tidak ditemukan di GeoJSON. Kolom: {list(gdf.columns)}")

    is_indo = gdf[name_col].astype(str).str.contains(
        "Indonesia", case=False, na=False)

    indo_gdf = gdf[is_indo]

    if indo_gdf.empty:

        raise ValueError("Poligon Indonesia tidak ditemukan di GeoJSON.")

    try:

        indo_geom = indo_gdf.geometry.union_all()

    except AttributeError:

        indo_geom = indo_gdf.geometry.unary_union

    # Negara tetangga di dalam kotak tampilan peta Indonesia untuk konteks geografis.

    neighbors_gdf = gdf[~is_indo].cx[92.0:144.0, -13.0:9.0]

    try:

        neighbors_geom = neighbors_gdf.geometry.union_all(
        ) if not neighbors_gdf.empty else None

    except AttributeError:

        neighbors_geom = neighbors_gdf.geometry.unary_union if not neighbors_gdf.empty else None

    return indo_geom, neighbors_geom


@st.cache_data(show_spinner="Menyiapkan mask daratan Indonesia...")
def make_land_mask(lat_tuple: tuple[float, ...], lon_tuple: tuple[float, ...], boundary_path: str) -> np.ndarray:

    indo_geom, _ = load_geometries(boundary_path)

    lon_grid, lat_grid = np.meshgrid(
        np.asarray(lon_tuple), np.asarray(lat_tuple))

    return np.asarray(contains_xy(indo_geom, lon_grid, lat_grid), dtype=bool)


@st.cache_data(show_spinner="Menyiapkan grid visualisasi batas pulau...")
def make_fine_land_mask(

    lon_min: float, lon_max: float, lat_min: float, lat_max: float, step: float, boundary_path: str

):

    indo_geom, _ = load_geometries(boundary_path)

    fine_lon = np.round(np.arange(lon_min, lon_max + step * 0.5, step), 4)

    fine_lat = np.round(np.arange(lat_min, lat_max + step * 0.5, step), 4)

    fx, fy = np.meshgrid(fine_lon, fine_lat)

    mask = np.asarray(contains_xy(indo_geom, fx, fy), dtype=bool)

    return fine_lon, fine_lat, mask


@st.cache_resource(show_spinner="Memuat data forecast & memverifikasi koordinat...")
def load_forecast(variable: str):

    cfg = FILES[variable]

    raw_ds = open_dataset(str(cfg["raw"]))

    corr_ds = open_dataset(str(cfg["corrected"]))

    raw_da = get_variable(raw_ds, cfg["raw_variable"])

    corr_da = get_variable(corr_ds, cfg["corrected_variable"])

    raw_lat, raw_lon, raw_lat_name, raw_lon_name = get_lat_lon(raw_da)

    corr_lat, corr_lon, corr_lat_name, corr_lon_name = get_lat_lon(corr_da)

    raw_lat_sorted = np.sort(raw_lat)

    raw_lon_sorted = np.sort(raw_lon)

    corr_lat_sorted = np.sort(corr_lat)

    corr_lon_sorted = np.sort(corr_lon)

    if not (np.allclose(raw_lat_sorted, corr_lat_sorted) and np.allclose(raw_lon_sorted, corr_lon_sorted)):

        raise ValueError(
            "Koordinat latitude/longitude antara raw dan corrected tidak cocok.")

    raw_lead = find_dim(raw_da, ["lead_year", "lead", "year"])

    corr_lead = find_dim(corr_da, ["lead_year", "lead", "year"])

    if raw_lead is None or corr_lead is None:

        raise ValueError(
            "Dimensi lead_year tidak ditemukan pada salah satu file.")

    raw_m = find_dim(raw_da, ["sample", "member",
                     "ensemble", "realization", "variant"])

    corr_m = find_dim(corr_da, ["sample", "member",
                      "ensemble", "realization", "variant"])

    if raw_m and corr_m and raw_da.sizes[raw_m] != corr_da.sizes[corr_m]:

        raise ValueError("Jumlah ensemble raw dan corrected tidak sama.")

    return {

        "raw": raw_da,

        "corrected": corr_da,

        "lat": raw_lat_sorted,

        "lon": raw_lon_sorted,

        "raw_lat_name": raw_lat_name,

        "raw_lon_name": raw_lon_name,

        "corr_lat_name": corr_lat_name,

        "corr_lon_name": corr_lon_name,

    }

def inspect_ensemble_structure(variable: str):
    dataset = load_forecast(variable)

    for label in ["raw", "corrected"]:
        da = dataset[label]

        print(f"\n===== {label.upper()} =====")
        print("Dimensi:", da.dims)
        print("Ukuran:", da.sizes)

        member_dim = find_dim(
            da,
            ["sample", "member", "ensemble", "realization", "variant"]
        )

        if member_dim is None:
            print("Dimensi ensemble: TIDAK DITEMUKAN")
        else:
            print("Nama dimensi ensemble:", member_dim)
            print("Koordinat ensemble:", da[member_dim].values)

        lead_dim = find_dim(da, ["lead_year", "lead", "year"])

        if lead_dim is not None:
            print("Koordinat lead year:", da[lead_dim].values)


def compute_lead_year_profile(
    dataset: dict,
    variable: str,
    member_value: str,
) -> pd.DataFrame:
    """
    Menghitung profil rata-rata forecast Raw dan Corrected
    untuk Lead Year 1–10 pada grid daratan Indonesia.

    Satuan mengikuti konfigurasi FILES.
    """

    records = []

    for lead_year in range(1, 11):
        selected = get_selected_arrays(
            dataset,
            variable,
            lead_year,
            member_value,
        )

        raw_valid = selected["raw"][
            np.isfinite(selected["raw"])
        ]

        corrected_valid = selected["corrected"][
            np.isfinite(selected["corrected"])
        ]

        difference_valid = selected["difference"][
            np.isfinite(selected["difference"])
        ]

        if (
            raw_valid.size == 0
            or corrected_valid.size == 0
            or difference_valid.size == 0
        ):
            raw_mean = np.nan
            corrected_mean = np.nan
            difference_mean = np.nan

        else:
            raw_mean = float(np.nanmean(raw_valid))
            corrected_mean = float(np.nanmean(corrected_valid))
            difference_mean = float(np.nanmean(difference_valid))

        records.append({
            "Lead Year": lead_year,
            "Raw": raw_mean,
            "Corrected": corrected_mean,
            "Difference": difference_mean,
        })

    return pd.DataFrame(records)


def get_selected_arrays(dataset: dict, variable: str, lead_year: int, member_value: str) -> dict:

    raw_da = select_member(select_lead(
        dataset["raw"], lead_year), member_value)

    corr_da = select_member(select_lead(
        dataset["corrected"], lead_year), member_value)

    raw_full = convert_units(

        as_lat_lon_array(
            raw_da, dataset["raw_lat_name"], dataset["raw_lon_name"]),

        raw_da,

        variable,

    )

    corr_full = convert_units(

        as_lat_lon_array(
            corr_da, dataset["corr_lat_name"], dataset["corr_lon_name"]),

        corr_da,

        variable,

    )

    if raw_full.shape != corr_full.shape:

        raise ValueError(
            f"Dimensi raw {raw_full.shape} berbeda dari corrected {corr_full.shape}.")

    land_mask = make_land_mask(

        tuple(float(v) for v in dataset["lat"]),

        tuple(float(v) for v in dataset["lon"]),

        str(BOUNDARY_FILE),

    )

    raw_land = np.where(land_mask, raw_full, np.nan)

    corr_land = np.where(land_mask, corr_full, np.nan)

    return {

        "raw": raw_land,

        "corrected": corr_land,

        "difference": corr_land - raw_land,

        # Grid penuh hanya untuk interpolasi visual peta sebelum dipotong poligon Indonesia.

        "raw_visual": raw_full,

        "corrected_visual": corr_full,

        "difference_visual": corr_full - raw_full,

        "land_mask": land_mask,

    }


def interpolate_bilinear_numpy(

    lon: np.ndarray,

    lat: np.ndarray,

    z: np.ndarray,

    fine_lon: np.ndarray,

    fine_lat: np.ndarray,

    fine_mask: np.ndarray,

) -> np.ndarray:
    """

    Interpolasi visual bilinear berbasis NumPy murni (bebas SciPy) untuk grid rektilinear,

    dengan fallback tetangga terdekat pada tepi pulau yang sel aslinya bernilai NaN.

    Hanya digunakan untuk tampilan peta, tidak mengubah nilai grid asli.

    """

    ix1 = np.clip(np.searchsorted(
        lon, fine_lon, side="right"), 1, len(lon) - 1)

    ix0 = ix1 - 1

    iy1 = np.clip(np.searchsorted(
        lat, fine_lat, side="right"), 1, len(lat) - 1)

    iy0 = iy1 - 1

    dx = np.where(lon[ix1] != lon[ix0], lon[ix1] - lon[ix0], 1.0)

    dy = np.where(lat[iy1] != lat[iy0], lat[iy1] - lat[iy0], 1.0)

    wx = np.clip((fine_lon - lon[ix0]) / dx, 0.0, 1.0)[None, :]

    wy = np.clip((fine_lat - lat[iy0]) / dy, 0.0, 1.0)[:, None]

    z00 = z[np.ix_(iy0, ix0)]

    z01 = z[np.ix_(iy0, ix1)]

    z10 = z[np.ix_(iy1, ix0)]

    z11 = z[np.ix_(iy1, ix1)]

    corners = [

        (z00, (1.0 - wy) * (1.0 - wx)),

        (z01, (1.0 - wy) * wx),

        (z10, wy * (1.0 - wx)),

        (z11, wy * wx),

    ]

    num = np.zeros((len(fine_lat), len(fine_lon)), dtype=float)

    den = np.zeros((len(fine_lat), len(fine_lon)), dtype=float)

    for val, w in corners:

        valid = np.isfinite(val)

        num += np.where(valid, val * w, 0.0)

        den += np.where(valid, w, 0.0)

    out = np.where(den > 1e-12, num / np.where(den > 1e-12, den, 1.0), np.nan)

    # Fallback nearest-valid khusus titik daratan yang belum tercakup (misal pesisir/pulau sempit).

    missing = fine_mask & ~np.isfinite(out)

    if np.any(missing):

        gx, gy = np.meshgrid(lon, lat)

        valid_src = np.isfinite(z)

        if np.any(valid_src):

            src_x = gx[valid_src]

            src_y = gy[valid_src]

            src_v = z[valid_src]

            fx, fy = np.meshgrid(fine_lon, fine_lat)

            miss_x = fx[missing]

            miss_y = fy[missing]

            d2 = (miss_x[:, None] - src_x[None, :]) ** 2 + \
                (miss_y[:, None] - src_y[None, :]) ** 2

            out[missing] = src_v[np.argmin(d2, axis=1)]

    return np.where(fine_mask, out, np.nan)


def geometry_to_xy_lines(geom):
    """Menggabungkan batas poligon menjadi satu trace Scatter dengan pemisah None."""

    if geom is None:

        return [], []

    geoms = list(geom.geoms) if hasattr(geom, "geoms") else [geom]

    xs, ys = [], []

    for poly in geoms:

        if poly.is_empty or not hasattr(poly, "exterior"):

            continue

        bx, by = poly.exterior.xy

        xs.extend(list(bx) + [None])

        ys.extend(list(by) + [None])

    return xs, ys


# ============================================================

# 4. FUNGSI VISUALISASI

# ============================================================

def render_forecast_map(
    dataset: dict,
    arrays: dict,
    variable: str,
    display_mode: str,
    lead_year: int,
    member_label: str,
):
    cfg = FILES[variable]

    # ----------------------------------------------------------
    # 1. Tentukan data dan palet warna
    # ----------------------------------------------------------
    if display_mode == "Raw":
        z_source = arrays["raw_visual"]
        z_land = arrays["raw"]
        color_scale = cfg["scale"]
        color_title = f"Raw ({cfg['unit']})"

    elif display_mode == "Corrected":
        z_source = arrays["corrected_visual"]
        z_land = arrays["corrected"]
        color_scale = cfg["scale"]
        color_title = f"Corrected ({cfg['unit']})"

    else:
        z_source = arrays["difference_visual"]
        z_land = arrays["difference"]
        color_scale = "RdBu_r"
        color_title = f"Corrected − Raw ({cfg['unit']})"

    if not np.isfinite(z_land).any():
        st.warning(
            "Tidak ada nilai valid di daratan Indonesia untuk kombinasi filter ini."
        )
        return

    # ----------------------------------------------------------
    # 2. Siapkan grid visualisasi Indonesia
    # ----------------------------------------------------------
    fine_lon, fine_lat, fine_mask = make_fine_land_mask(
        94.0, 142.0, -11.5, 6.8, 0.06, str(BOUNDARY_FILE)
    )

    fine_z = interpolate_bilinear_numpy(
        dataset["lon"],
        dataset["lat"],
        z_source,
        fine_lon,
        fine_lat,
        fine_mask,
    )

    valid_vals = fine_z[np.isfinite(fine_z)]

    if valid_vals.size == 0:
        st.warning(
            "Gagal memetakan nilai pada poligon daratan Indonesia."
        )
        return

    # ----------------------------------------------------------
    # 3. Rentang warna
    # ----------------------------------------------------------
    if display_mode == "Difference":
        # Skala simetris dengan pusat nol.
        vmax = float(np.nanpercentile(np.abs(valid_vals), 98))
        vmax = max(vmax, 0.25)

        zmin, zmax = -vmax, vmax

    else:
        # Raw dan Corrected menggunakan rentang warna bersama.
        raw_values = np.asarray(
            arrays["raw_visual"], dtype=float
        )
        corrected_values = np.asarray(
            arrays["corrected_visual"], dtype=float
        )

        raw_values = raw_values[np.isfinite(raw_values)]
        corrected_values = corrected_values[
            np.isfinite(corrected_values)
        ]

        common_values = np.concatenate(
            [raw_values, corrected_values]
        )

        if common_values.size == 0:
            st.warning("Tidak tersedia nilai valid untuk skala warna.")
            return

        zmin = float(np.nanpercentile(common_values, 2))
        zmax = float(np.nanpercentile(common_values, 98))

        # Curah hujan memiliki batas bawah fisik nol.
        if variable == "PR":
            zmin = min(0.0, zmin)

        # Hindari rentang warna nol.
        if np.isclose(zmin, zmax):
            padding = max(abs(zmin) * 0.01, 0.5)
            zmin -= padding
            zmax += padding

    # ----------------------------------------------------------
    # 4. Siapkan batas wilayah
    # ----------------------------------------------------------
    fig = go.Figure()

    indo_geom, neighbors_geom = load_geometries(
        str(BOUNDARY_FILE)
    )

    # Daratan negara tetangga.
    nx, ny = geometry_to_xy_lines(neighbors_geom)

    if nx:
        fig.add_trace(
            go.Scatter(
                x=nx,
                y=ny,
                mode="lines",
                fill="toself",
                fillcolor="#E8EDF2",
                line=dict(
                    color="#C2CCD6",
                    width=0.6,
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # ----------------------------------------------------------
    # 5. Layer raster forecast
    # ----------------------------------------------------------
    fig.add_trace(
        go.Heatmap(
            x=fine_lon,
            y=fine_lat,
            z=fine_z,
            colorscale=color_scale,
            zsmooth="best",
            zmin=zmin,
            zmax=zmax,
            connectgaps=False,
            hoverongaps=False,
            colorbar=dict(
                title=dict(
                    text=color_title,
                    font=dict(
                        color="#172B3A",
                        size=11,
                    ),
                ),
                tickfont=dict(
                    color="#52677A",
                    size=10,
                ),
                thickness=13,
                len=0.86,
                outlinewidth=0,
                x=1.02,
            ),
            hovertemplate=(
                "Lintang: %{y:.2f}°"
                "<br>Bujur: %{x:.2f}°"
                f"<br>Nilai: %{{z:.2f}} {cfg['unit']}"
                "<extra></extra>"
            ),
        )
    )

    # ----------------------------------------------------------
    # 6. Garis batas Indonesia
    # ----------------------------------------------------------
    ix, iy = geometry_to_xy_lines(indo_geom)

    if ix:
        fig.add_trace(
            go.Scatter(
                x=ix,
                y=iy,
                mode="lines",
                line=dict(
                    color="#263B50",
                    width=0.9,
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # ----------------------------------------------------------
    # 7. Layout peta
    # ----------------------------------------------------------
    fig.update_layout(
        height=390,
        margin=dict(
            l=8,
            r=42,
            t=8,
            b=30,
        ),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#F2F5F8",
        font=dict(
            family="Aptos, Segoe UI, Arial",
            color="#172B3A",
            size=10,
        ),
        xaxis=dict(
            title=dict(
                text="Bujur (°BT)",
                font=dict(
                    size=10,
                    color="#52677A",
                ),
            ),
                range=[94.2, 141.8],
                gridcolor="#DFE7EE",
                tickfont=dict(
                    size=9,
                    color="#52677A",
                ),
                zeroline=False,
            ),
        yaxis=dict(
            title=dict(
                text="Lintang (°)",
                font=dict(
                    size=10,
                    color="#52677A",
                ),
            ),
                range=[-11.4, 6.6],
                gridcolor="#DFE7EE",
                tickfont=dict(
                    size=9,
                    color="#52677A",
               ),
                scaleanchor="x",
                scaleratio=1,
                zeroline=False,
            ),
            dragmode="pan",
            showlegend=False,
        )

    st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": True,
                "scrollZoom": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": [
                    "lasso2d",
                    "select2d",
                ],
        },
    )


def render_lead_year_chart(profile_df: pd.DataFrame, variable: str, active_lead: int):

    cfg = FILES[variable]

    fig = go.Figure()

    fig.add_trace(go.Scatter(

        x=profile_df["Lead Year"],

        y=profile_df["Raw"],

        mode="lines+markers",

        name="Raw (DCPP-B)",

        line=dict(color="#6B7D8E", width=2, dash="dot"),

        marker=dict(size=5),

        customdata=profile_df["Difference"],

        hovertemplate=f"Lead Year %{{x}}<br>Raw: %{{y:.2f}} {cfg['unit']}<extra></extra>",

    ))

    fig.add_trace(go.Scatter(

        x=profile_df["Lead Year"],

        y=profile_df["Corrected"],

        mode="lines+markers",

        name=f"Corrected ({cfg['model']})",

        line=dict(color="#087F8C", width=2.5),

        marker=dict(size=6),

        customdata=profile_df["Difference"],

        hovertemplate=(

            f"Lead Year %{{x}}<br>Corrected: %{{y:.2f}} {cfg['unit']}"

            f"<br>Corrected − Raw: %{{customdata:+.2f}} {cfg['unit']}<extra></extra>"

        ),

    ))

    # Penanda vertikal Lead Year yang sedang dipilih pada filter.

    fig.add_vline(

        x=active_lead,

        line_width=1.4,

        line_dash="dash",

        line_color="#142B45",

        annotation_text=f"LY {active_lead}",

        annotation_position="top right",

        annotation_font=dict(size=9, color="#142B45"),

    )

    fig.update_layout(

        height=155,

        margin=dict(l=8, r=8, t=22, b=6),

        paper_bgcolor="#FFFFFF",

        plot_bgcolor="#FFFFFF",

        font=dict(family="Aptos, Segoe UI, Arial", size=10, color="#172B3A"),

        legend=dict(

            orientation="h",

            yanchor="bottom",

            y=1.02,

            xanchor="left",

            x=0,

            font=dict(size=9),

        ),

        xaxis=dict(

            title=dict(text="Lead Year", font=dict(size=9, color="#52677A")),

            dtick=1,

            gridcolor="#E6EDF3",

            tickfont=dict(size=9),

        ),

        yaxis=dict(

            title=dict(text=cfg["unit"], font=dict(size=9, color="#52677A")),

            gridcolor="#E6EDF3",

            tickfont=dict(size=9),

        ),

    )

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})


def render_model_comparison_chart(comparison_df: pd.DataFrame, metric_choice: str, variable: str):

    cfg = FILES[variable]

    df = comparison_df.copy()

    df["Model"] = pd.Categorical(
        df["Model"], categories=MODEL_ORDER, ordered=True)

    df = df.sort_values("Model")

    fig = go.Figure()

    color_map = {"Machine Learning": "#245B83", "Deep Learning": "#087F8C"}

    for group_name in ["Machine Learning", "Deep Learning"]:
        # Hanya gambar nilai yang benar-benar tersedia; N/A tidak dibuat menjadi batang nol.
        sub = df[(df["Kelompok"] == group_name) &
                 df[metric_choice].notna()].copy()
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            x=sub["Model"].astype(str),
            y=sub[metric_choice].astype(float),
            name=group_name,
            marker_color=color_map[group_name],
            marker_line=dict(color=color_map[group_name], width=1),
            text=sub[metric_choice].map(lambda v: f"{v:.3f}"),
            textposition="outside",
            cliponaxis=False,
            customdata=sub[metric_choice].map(lambda v: f"{v:.4f}"),
            hovertemplate=f"<b>%{{x}}</b> ({group_name})<br>{metric_choice}: %{{customdata}}<extra></extra>",
        ))

    unit_suffix = f" ({cfg['unit']})" if metric_choice in {
        "RMSE", "MAE", "Bias"} else ""

    valid_series = df.dropna(subset=[metric_choice])

    if not valid_series.empty:

        max_abs = max(abs(valid_series[metric_choice].max()), abs(
            valid_series[metric_choice].min()), 0.1)

        if metric_choice == "Bias":

            fig.update_yaxes(
                range=[-max_abs * 1.35, max_abs * 1.35], zeroline=True, zerolinecolor="#52677A")

        else:

            fig.update_yaxes(range=[0, max_abs * 1.28])

    fig.update_layout(

        height=155,

        barmode="group",

        margin=dict(l=8, r=8, t=22, b=6),

        paper_bgcolor="#FFFFFF",

        plot_bgcolor="#FFFFFF",

        font=dict(family="Aptos, Segoe UI, Arial", size=9, color="#172B3A"),

        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, x=0, font=dict(size=9)),

        xaxis=dict(

            title=None,

            categoryorder="array",

            categoryarray=MODEL_ORDER,

            tickfont=dict(size=8.5, color="#172B3A"),

        ),

        yaxis=dict(

            title=dict(text=f"{metric_choice}{unit_suffix}",
                       font=dict(size=9, color="#52677A")),

            gridcolor="#E6EDF3",

            tickfont=dict(size=8.5),

        ),

    )

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})

    # Penentuan model terbaik secara objektif dari data yang tersedia.

    if valid_series.empty:

        return f"Belum ada nilai {metric_choice} yang tersedia untuk {variable}."

    if metric_choice in {"RMSE", "MAE"}:

        best_row = valid_series.loc[valid_series[metric_choice].idxmin()]

    elif metric_choice == "Korelasi":

        best_row = valid_series.loc[valid_series[metric_choice].idxmax()]

    else:  # Bias: paling mendekati nol

        best_row = valid_series.loc[valid_series[metric_choice].abs().idxmin()]

    missing = df.loc[df[metric_choice].isna(), "Model"].astype(str).tolist()

    na_text = f" | N/A: {', '.join(missing)}" if missing else ""

    return f"Terbaik ({metric_choice}): <b>{best_row['Model']}</b> ({best_row[metric_choice]:.3f}){na_text}"


# ============================================================

def render_distribution_chart(selected, variable):
    """
    Distribusi nilai Raw dan Corrected pada grid daratan Indonesia.
    Hanya menggunakan pasangan grid yang valid pada kedua dataset.
    """
    raw = np.asarray(selected["raw"], dtype=float)
    corrected = np.asarray(selected["corrected"], dtype=float)
    land_mask = np.asarray(selected["land_mask"], dtype=bool)

    valid_mask = (
        land_mask
        & np.isfinite(raw)
        & np.isfinite(corrected)
    )

    raw_values = raw[valid_mask]
    corrected_values = corrected[valid_mask]

    if raw_values.size == 0:
        st.info("Tidak tersedia grid valid untuk membuat distribusi.")
        return

    cfg = FILES[variable]

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=raw_values,
        name="Raw (DCPP-B)",
        nbinsx=35,
        histnorm="probability",
        bingroup="climate_distribution",
        opacity=0.65,
        marker=dict(
            color="#6686A5",
            line=dict(color="#496985", width=0.5)
        ),
        hovertemplate=(
            "Raw: %{x:.2f}<br>"
            "Proporsi grid: %{y:.3f}<extra></extra>"
        ),
    ))

    fig.add_trace(go.Histogram(
        x=corrected_values,
        name=f"Corrected ({cfg['model']})",
        nbinsx=35,
        histnorm="probability",
        bingroup="climate_distribution",
        opacity=0.65,
        marker=dict(
            color="#078B91",
            line=dict(color="#066D73", width=0.5)
        ),
        hovertemplate=(
            "Corrected: %{x:.2f}<br>"
            "Proporsi grid: %{y:.3f}<extra></extra>"
        ),
    ))

    fig.update_layout(
        height=265,
        barmode="overlay",
        margin=dict(l=42, r=15, t=28, b=42),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(
            family="Aptos, Segoe UI, Arial",
            size=10,
            color="#172B3A"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            font=dict(size=9)
        ),
        xaxis=dict(
            title=f"{cfg['short_label']} ({cfg['unit']})",
            gridcolor="#E6EDF3",
            zeroline=False,
        ),
        yaxis=dict(
            title="Proporsi grid",
            gridcolor="#E6EDF3",
            rangemode="tozero",
        ),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )

    st.caption(
        f"Distribusi dihitung dari {raw_values.size:,} grid daratan "
        "yang memiliki pasangan nilai Raw dan Corrected valid. "
        "Histogram menunjukkan distribusi spasial, bukan distribusi temporal."
    )



# ============================================================
# 5. DASHBOARD — FORECAST DCPP-B s2020
# ============================================================


# Filter utama: ensemble mean menjadi tampilan awal, tetapi anggota ensemble tetap dapat dipilih.
# Filter utama: ensemble mean menjadi tampilan awal,
# tetapi anggota ensemble tetap dapat dipilih.
filt = st.container(key="filt")
f1, f2, f3, f4, f5 = filt.columns(
    [1.45, 0.8, 1.45, 1.0, 0.68],
    gap="small"
)

with f1:
    variable = st.selectbox(
        "Variabel Iklim",
        ["TAS", "PR"],
        format_func=lambda x: FILES[x]["label"]
    )

with f2:
    lead_year = st.selectbox(
        "Lead Year",
        list(range(1, 11)),
        index=0
    )

with f3:
    member_label = st.selectbox(
        "Ensemble Member",
        list(MEMBER_OPTIONS.keys()),
        index=0
    )

with f4:
    st.markdown(
        '<div style="height:1.18rem"></div>',
        unsafe_allow_html=True
    )
    export_placeholder = st.empty()

with f5:
    fullscreen_btn()

member_value = MEMBER_OPTIONS[member_label]
cfg = FILES[variable]
forecast_error = None
forecast_dataset = None
selected = None

try:
    forecast_dataset = load_forecast(variable)
    selected = get_selected_arrays(
        forecast_dataset, variable, lead_year, member_value)
except Exception as exc:
    forecast_error = str(exc)

if forecast_error is None:
    lon_grid, lat_grid = np.meshgrid(
        forecast_dataset["lon"], forecast_dataset["lat"])
    export_df = pd.DataFrame({
        "latitude": lat_grid.ravel(),
        "longitude": lon_grid.ravel(),
        "raw": selected["raw"].ravel(),
        "corrected": selected["corrected"].ravel(),
        "difference_corrected_minus_raw": selected["difference"].ravel(),
        "inside_indonesia_land_mask": selected["land_mask"].ravel(),
    })
    export_df = export_df[export_df["inside_indonesia_land_mask"]].dropna(subset=[
                                                                          "raw", "corrected"])
    export_placeholder.download_button(
        "Unduh CSV Grid",
        data=export_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{variable.lower()}_dcppB_s2020_ly{lead_year}_{member_value}.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    export_placeholder.button(
        "Unduh CSV Grid", disabled=True, use_container_width=True)

if forecast_error:
    st.error(f"Data forecast {variable} gagal dimuat: {forecast_error}")
    st.caption("Periksa path NetCDF, nama variabel, dan GeoJSON. Bagian visualisasi akan aktif setelah data berhasil dibaca.")
else:
    raw_valid = selected["raw"][np.isfinite(selected["raw"])]
    corr_valid = selected["corrected"][np.isfinite(selected["corrected"])]
    diff_valid = selected["difference"][np.isfinite(selected["difference"])]

    if raw_valid.size == 0 or corr_valid.size == 0:
        st.warning(
            "Tidak ditemukan titik grid valid di daratan Indonesia untuk pilihan ini.")
    else:
        # KPI forecast aktual DCPP-B — bukan hasil evaluasi terhadap observasi.
        k1, k2, k3, k4 = st.columns(4, gap="small")
        k1.metric(f"Rata-rata Raw ({cfg['unit']})",
                  f"{np.nanmean(raw_valid):.2f}")
        k2.metric(
            f"Rata-rata Corrected ({cfg['unit']})", f"{np.nanmean(corr_valid):.2f}")
        k3.metric(
            f"Selisih rata-rata ({cfg['unit']})", f"{np.nanmean(diff_valid):+.2f}")
        k4.metric("Grid daratan valid",
                  f"{int((np.isfinite(selected['raw']) & np.isfinite(selected['corrected'])).sum()):,}")

        # Dua peta utama: nilai hasil koreksi dan besarnya perubahan terhadap raw.
        map1, map2 = st.columns(2, gap="medium")
        with map1:
            with panel_box():
                st.markdown(
                    f'<div class="panel-title">01 · Forecast Corrected — {cfg["short_label"]}</div>'
                    f'<div class="panel-sub">Lead Year {lead_year} · {member_label} · {cfg["model"]}</div>',
                    unsafe_allow_html=True,
                )
                render_forecast_map(forecast_dataset, selected,
                                    variable, "Corrected", lead_year, member_label)
        with map2:
            with panel_box():
                st.markdown(
                    f'<div class="panel-title">02 · Perubahan Corrected − Raw</div>'
                    f'<div class="panel-sub">Selisih hasil koreksi terhadap forecast mentah · satuan {cfg["unit"]}</div>',
                    unsafe_allow_html=True,
                )
                render_forecast_map(
                    forecast_dataset, selected, variable, "Difference", lead_year, member_label)

        st.caption(
            "Catatan peta: interpolasi dan pemotongan poligon hanya untuk tampilan visual, bukan peningkatan resolusi ilmiah. "
            "Difference = Corrected − Raw, bukan error terhadap observasi."
        )

        # Profil 10 lead years menggunakan anggota ensemble yang dipilih.

        # Profil forecast dan distribusi nilai dalam satu baris.
        profile_col, distribution_col = st.columns(
            [1.15, 1],
            gap="medium"
        )

        with profile_col:
            with panel_box():
                st.markdown(
                    f'<div class="panel-title">03 · Profil Forecast 10 Tahun — {cfg["short_label"]}</div>'
                    f'<div class="panel-sub">Rata-rata spasial daratan Indonesia · {member_label}</div>',
                    unsafe_allow_html=True,
                )

                profile_df = compute_lead_year_profile(
                    forecast_dataset, variable, member_value
                )

                render_lead_year_chart(
                    profile_df, variable, lead_year
                )

        with distribution_col:
            with panel_box():
                st.markdown(
                    f'<div class="panel-title">04 · Distribusi Raw vs Corrected — {cfg["short_label"]}</div>'
                    f'<div class="panel-sub">Distribusi nilai grid daratan Indonesia · Lead Year {lead_year} · {member_label}</div>',
                    unsafe_allow_html=True,
                )

                render_distribution_chart(
                    selected, variable
                )


        # Evaluasi historis dan perbandingan kandidat dipertahankan sebagai konteks,
        # bukan dianggap sebagai verifikasi forecast DCPP-B s2020.
        hist_col, cmp_col = st.columns([1, 1.35], gap="medium")
        with hist_col:
            with panel_box():
                st.markdown(
                    f'<div class="panel-title">05 · Evaluasi Historis {variable} (DCPP-A)</div>'
                    f'<div class="panel-sub">Uji historis terhadap {cfg["obs"]} · bukan verifikasi forecast s2020</div>',
                    unsafe_allow_html=True,
                )
                hist = HISTORICAL_METRICS[variable]
                corr_key = "CNN / U-Net" if variable == "TAS" else "Random Forest"
                raw_h, corr_h = hist["Raw"], hist[corr_key]
                hist_table = pd.DataFrame([
                    {"Metrik": m,
                        "Raw": f"{raw_h[m]:.3f}", corr_key: f"{corr_h[m]:.3f}"}
                    for m in ["RMSE", "MAE", "Korelasi", "Bias"]
                ])
                st.dataframe(hist_table, use_container_width=True,
                             hide_index=True, height=138)
                rmse_drop = (raw_h["RMSE"] - corr_h["RMSE"]
                             ) / raw_h["RMSE"] * 100.0
                bias_note = "Bias absolut sedikit meningkat pada hasil RF PR." if variable == "PR" else "Bias hasil koreksi lebih dekat ke nol."
                st.markdown(
                    f'<div class="note-box"><b>Model terpilih:</b> {corr_key}<br>'
                    f'Penurunan RMSE historis: <b>{rmse_drop:.1f}%</b> '
                    f'({raw_h["RMSE"]:.3f} → {corr_h["RMSE"]:.3f} {cfg["unit"]}).<br>{bias_note}</div>',
                    unsafe_allow_html=True,
                )

        with cmp_col:
            with panel_box():
                st.markdown(
                    f'<div class="panel-title">06 · Perbandingan Kandidat Model ML vs DL ({variable})</div>'
                    '<div class="panel-sub">Rekap evaluasi historis · nilai yang belum tersedia tidak ditampilkan sebagai nol</div>',
                    unsafe_allow_html=True,
                )
                tab_chart, tab_guide = st.tabs(
                    ["Grafik Metrik", "Panduan Membaca"])
                with tab_chart:
                    metric_choice = st.selectbox(
                        "Pilih Metrik Evaluasi", [
                            "RMSE", "MAE", "Korelasi", "Bias"],
                        key="p4_cmp_metric_select", label_visibility="collapsed",
                    )
                    summary_text = render_model_comparison_chart(
                        MODEL_COMPARISON[variable], metric_choice, variable)
                    st.markdown(
                        f'<div class="warn-box">{summary_text}</div>', unsafe_allow_html=True)
                with tab_guide:
                    st.markdown("""
                    <div class="sci-guide">
                    <b>ML:</b> RF, XGBoost, dan ANN memodelkan hubungan fitur pada titik grid/tabel.<br>
                    <b>DL:</b> CNN/U-Net dan ConvLSTM mempelajari pola spasial; ConvLSTM juga memanfaatkan urutan waktu.<br><br>
                    <b>RMSE &amp; MAE:</b> besar error, semakin kecil semakin baik.<br>
                    <b>Korelasi:</b> kesesuaian pola variasi, semakin mendekati +1 semakin baik.<br>
                    <b>Bias:</b> kecenderungan overestimate (+) atau underestimate (−), idealnya mendekati nol.<br>
                    <b>N/A:</b> metrik belum tersedia pada rekap eksperimen.
                    </div>
                    """, unsafe_allow_html=True)

st.markdown(
    '<div class="footer-bar">'
    'BMKG · Direktorat Perubahan Iklim | CMIP6-DCPP (CMCC-CM2-SR5) | ERA5 (TAS) · CHIRPS v2.0 (PR) | '
    'Mask daratan Indonesia berdasarkan GeoJSON | Difference = Corrected − Raw'
    '</div>',
    unsafe_allow_html=True,
)
