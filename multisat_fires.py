import os
import numpy as np
import s3fs
import xarray as xr
import folium
from folium import LayerControl
import pystac_client
import planetary_computer as pc
import requests
from datetime import datetime, timezone, timedelta
from shapely.geometry import Point, box
import json

# ── GOES-19 fire fetch ────────────────────────────────────────────────────────

def _decode_goes_fires(local_path):
    """Return (lat_grid, lon_grid, frp_array, scan_time) from a GOES FDC NetCDF file."""
    with xr.open_dataset(local_path, engine='netcdf4') as ds:
        proj = ds['goes_imager_projection']
        H   = proj.attrs['perspective_point_height'] + proj.attrs['semi_major_axis']
        lon0 = proj.attrs['longitude_of_projection_origin']
        r_eq = proj.attrs['semi_major_axis']
        r_pol = proj.attrs['semi_minor_axis']

        xx, yy = np.meshgrid(ds['x'].values, ds['y'].values)
        cx, sx_a = np.cos(xx), np.sin(xx)
        cy, sy_a = np.cos(yy), np.sin(yy)

        a   = sx_a**2 + cx**2 * (cy**2 + (r_eq/r_pol)**2 * sy_a**2)
        b   = -2 * H * cx * cy
        c   = H**2 - r_eq**2
        det = b**2 - 4*a*c
        rs  = np.where(det >= 0, (-b - np.sqrt(np.where(det >= 0, det, 0))) / (2*a), np.nan)

        Sx = rs * cx * cy
        Sy = -rs * sx_a
        Sz = rs * cx * sy_a

        lat = np.degrees(np.arctan((r_eq/r_pol)**2 * Sz / np.sqrt((H - Sx)**2 + Sy**2)))
        lon = lon0 - np.degrees(np.arctan(Sy / (H - Sx)))

        frp = ds['Power'].values.copy()
        scan_time = ds.attrs.get('time_coverage_start', 'Unknown')

    fire = ~np.isnan(frp) & (frp > 0)
    return lat[fire], lon[fire], frp[fire], scan_time


def fetch_goes19_fires(accumulate_hours=2):
    """Accumulate fire pixels across the last N hours of FDCC scans for a richer picture."""
    fs = s3fs.S3FileSystem(anon=True)
    now = datetime.now(timezone.utc)
    local = os.path.join(os.path.dirname(__file__), '_goes19_tmp.nc')

    all_lats, all_lons, all_frps = [], [], []
    latest_scan_time = None
    scans_loaded = 0

    for delta in range(0, accumulate_hours + 1):
        t = now - timedelta(hours=delta)
        path = f"noaa-goes19/ABI-L2-FDCC/{t:%Y/%j/%H}/"
        try:
            files = sorted(fs.ls(path))
            if not files:
                continue
            for f in files:
                try:
                    fs.get(f, local)
                    lats, lons, frps, scan_time = _decode_goes_fires(local)
                    all_lats.append(lats)
                    all_lons.append(lons)
                    all_frps.append(frps)
                    if latest_scan_time is None:
                        latest_scan_time = scan_time
                    scans_loaded += 1
                except Exception as e:
                    pass
        except Exception as e:
            print(f"  skip hour -{delta}: {e}")

    if not all_lats:
        raise RuntimeError("No GOES-19 data found")

    lats = np.concatenate(all_lats)
    lons = np.concatenate(all_lons)
    frps = np.concatenate(all_frps)

    # Deduplicate: round to ~2km grid and keep max FRP per cell
    keys = np.round(lats, 2).astype(str) + ',' + np.round(lons, 2).astype(str)
    unique_keys, idx = np.unique(keys, return_index=True)
    lats, lons, frps = lats[idx], lons[idx], frps[idx]

    print(f"GOES-19: {scans_loaded} scans, {len(lats)} unique fire pixels (last {accumulate_hours}h)")
    return lats, lons, frps, latest_scan_time


# ── Sentinel-2 via Microsoft Planetary Computer ───────────────────────────────

def find_best_sentinel2(fire_lats, fire_lons, days_back=7, max_cloud=45):
    if len(fire_lats) == 0:
        return []

    # bounding box around all fire pixels (with padding)
    pad = 1.5
    bbox = [
        float(fire_lons.min()) - pad,
        float(fire_lats.min()) - pad,
        float(fire_lons.max()) + pad,
        float(fire_lats.max()) + pad,
    ]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )

    print(f"Sentinel-2: searching MSPC ({start:%Y-%m-%d} to {end:%Y-%m-%d}, cloud<{max_cloud}%)")
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        sortby="-datetime",
        max_items=20,
    )

    items = list(search.items())
    print(f"Sentinel-2: {len(items)} scenes found")
    return items


def sentinel2_preview_overlay(item):
    """Return (image_url, bounds, date, cloud_pct) for a Sentinel-2 scene."""
    signed = pc.sign(item)
    date = item.datetime.strftime("%Y-%m-%d") if item.datetime else "unknown"
    cloud = item.properties.get("eo:cloud_cover", "?")
    geom = item.geometry
    coords = geom["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]

    # Use rendered_preview asset (pre-composited JPEG, ~320m resolution)
    if "rendered_preview" in signed.assets:
        url = signed.assets["rendered_preview"].href
        return url, bounds, date, cloud

    return None, bounds, date, cloud


# ── NASA GIBS tile layers (no auth, daily) ────────────────────────────────────

def gibs_tile_url(layer, date_str):
    base = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
    return f"{base}/{layer}/default/{date_str}/GoogleMapsCompatible_Level9/{{z}}/{{y}}/{{x}}.jpg"


# ── Build map ─────────────────────────────────────────────────────────────────

def build_map(fire_lats, fire_lons, fire_frps, scan_time, s2_items):
    center_lat = float(fire_lats.mean()) if len(fire_lats) else 50.0
    center_lon = float(fire_lons.mean()) if len(fire_lons) else -100.0

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=5,
        tiles=None,
        control_scale=True,
    )

    # ── Base layers (NASA GIBS, daily) ───────────────────────────────────────
    today = datetime.now(timezone.utc)
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    two_days_ago = (today - timedelta(days=2)).strftime("%Y-%m-%d")

    # Try yesterday first; GIBS sometimes lags a day
    for label, layer, date in [
        (f"VIIRS NOAA-20 ({yesterday})", "VIIRS_NOAA20_CorrectedReflectance_TrueColor", yesterday),
        (f"MODIS Terra ({yesterday})", "MODIS_Terra_CorrectedReflectance_TrueColor", yesterday),
        (f"VIIRS NOAA-20 ({two_days_ago})", "VIIRS_NOAA20_CorrectedReflectance_TrueColor", two_days_ago),
        (f"MODIS Terra ({two_days_ago})", "MODIS_Terra_CorrectedReflectance_TrueColor", two_days_ago),
    ]:
        folium.TileLayer(
            tiles=gibs_tile_url(layer, date),
            name=f"🛰 {label}",
            attr="NASA GIBS / EOSDIS",
            max_zoom=9,
            show=(label.startswith("VIIRS NOAA-20") and date == yesterday),
        ).add_to(m)

    # ── Sentinel-2 overlays (best available per scene) ────────────────────────
    s2_group = folium.FeatureGroup(name="🔭 Sentinel-2 scenes (10m)", show=True)
    added_s2 = 0

    # Deduplicate by tile ID so we don't stack identical scenes
    seen_tiles = set()
    for item in s2_items:
        tile_id = item.properties.get("s2:mgrs_tile", item.id)
        if tile_id in seen_tiles:
            continue
        seen_tiles.add(tile_id)

        url, bounds, date, cloud = sentinel2_preview_overlay(item)
        if url is None:
            continue

        folium.raster_layers.ImageOverlay(
            image=url,
            bounds=bounds,
            opacity=0.85,
            name=f"S2 {tile_id} {date}",
            cross_origin=True,
            zindex=10,
        ).add_to(s2_group)

        # Label the scene footprint
        mid_lat = (bounds[0][0] + bounds[1][0]) / 2
        mid_lon = (bounds[0][1] + bounds[1][1]) / 2
        folium.Marker(
            location=[mid_lat, mid_lon],
            icon=folium.DivIcon(
                html=f'<div style="font-size:9px;color:#00ffcc;background:rgba(0,0,0,0.5);padding:2px 4px;border-radius:3px;white-space:nowrap">'
                     f'S2 {date} ☁{cloud:.0f}%</div>',
                icon_size=(120, 18),
                icon_anchor=(60, 9),
            ),
        ).add_to(s2_group)

        added_s2 += 1

    s2_group.add_to(m)
    print(f"Sentinel-2: added {added_s2} scene overlays")

    # ── GOES-19 fire markers ──────────────────────────────────────────────────
    goes_group = folium.FeatureGroup(name=f"Fire GOES-19 fires (2h window, latest {scan_time[:16]} UTC)", show=True)

    max_frp = float(fire_frps.max()) if len(fire_frps) else 1.0
    for la, lo, frp in zip(fire_lats, fire_lons, fire_frps):
        norm = float(frp) / max(max_frp, 1.0)
        r = int(255)
        g = int(255 * (1 - norm * 0.8))
        b = 0
        size = max(5, min(16, int(frp / 15)))
        color = f"rgb({r},{g},{b})"

        folium.CircleMarker(
            location=[float(la), float(lo)],
            radius=size,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            weight=0.5,
            tooltip=f"FRP: {frp:.0f} MW",
        ).add_to(goes_group)

    goes_group.add_to(m)

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_html = f"""
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
                background:rgba(0,0,0,0.75);color:white;padding:12px 16px;
                border-radius:8px;font-size:12px;font-family:monospace;line-height:1.8">
        <b>Best Available Imagery Stack</b><br>
        🔭 Sentinel-2 L2A &nbsp; 10m &nbsp; ≤7 days ({added_s2} scenes)<br>
        🛰 VIIRS / MODIS &nbsp; 250–375m &nbsp; daily (NASA GIBS)<br>
        Fire GOES-19 FDC &nbsp; 500m &nbsp; 2h accumulation, {len(fire_lats)} pixels<br>
        <hr style="border-color:#444;margin:6px 0">
        <span style="color:#aaa">Use layer control (top-right) to switch</span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    LayerControl(collapsed=False, position="topright").add_to(m)
    return m


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    fire_lats, fire_lons, fire_frps, scan_time = fetch_goes19_fires()
    s2_items = find_best_sentinel2(fire_lats, fire_lons)
    m = build_map(fire_lats, fire_lons, fire_frps, scan_time, s2_items)
    out = "multisat_fires.html"
    m.save(out)
    print(f"\nMap saved: {out}")
    import webbrowser
    webbrowser.open(os.path.abspath(out))
