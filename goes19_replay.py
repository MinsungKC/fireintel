import os
import numpy as np
import s3fs
import xarray as xr
import folium
from folium.plugins import TimestampedGeoJson
from datetime import datetime, timezone, timedelta

# ── Color scheme matching NOAA/NASA fire map style ────────────────────────────
# Border color = FRP intensity, thickness = confidence (DQF)

def pixel_style(frp_mw, dqf):
    # Border color by FRP intensity
    if   frp_mw > 500: color = '#FF0000'   # bright red
    elif frp_mw > 200: color = '#FF3300'
    elif frp_mw > 100: color = '#FF6600'   # orange
    elif frp_mw >  50: color = '#FF9900'
    elif frp_mw >  20: color = '#FFCC00'   # yellow
    else:              color = '#FFFF33'   # pale yellow

    # Border thickness by DQF (0=good → thick, 1=lower qual → medium, 2=cloud → thin dashed)
    weight  = max(1, 3 - int(dqf))
    opacity = 1.0 if dqf == 0 else (0.75 if dqf == 1 else 0.45)

    return {
        'color':       color,
        'weight':      weight,
        'opacity':     opacity,
        'fillOpacity': 0.07 if dqf == 0 else 0,
        'fillColor':   color,
        'dashArray':   '' if dqf < 2 else '4 4',
    }


# ── GOES fixed-grid → lat/lon (vectorized) ───────────────────────────────────

def scan_to_latlon(x, y, H, lon0, r_eq, r_pol):
    cx, sx = np.cos(x), np.sin(x)
    cy, sy = np.cos(y), np.sin(y)
    a   = sx**2 + cx**2 * (cy**2 + (r_eq / r_pol)**2 * sy**2)
    b   = -2 * H * cx * cy
    c   = H**2 - r_eq**2
    det = b**2 - 4 * a * c
    rs  = np.where(det >= 0, (-b - np.sqrt(np.where(det >= 0, det, 0))) / (2 * a), np.nan)
    Sx  = rs * cx * cy
    Sy  = -rs * sx
    Sz  = rs * cx * sy
    lat = np.degrees(np.arctan((r_eq / r_pol)**2 * Sz / np.sqrt((H - Sx)**2 + Sy**2)))
    lon = lon0 - np.degrees(np.arctan(Sy / (H - Sx)))
    return lat, lon


# ── Process one GOES-19 FDCC scan into GeoJSON polygon features ───────────────

def process_scan(local_path):
    with xr.open_dataset(local_path, engine='netcdf4') as ds:
        proj  = ds['goes_imager_projection']
        H     = proj.attrs['perspective_point_height'] + proj.attrs['semi_major_axis']
        lon0  = proj.attrs['longitude_of_projection_origin']
        r_eq  = proj.attrs['semi_major_axis']
        r_pol = proj.attrs['semi_minor_axis']
        x_arr = ds['x'].values.copy()
        y_arr = ds['y'].values.copy()
        frp   = ds['Power'].values.copy()
        dqf   = ds['DQF'].values.copy()
        scan_time = ds.attrs.get('time_coverage_start', '')

    fire = ~np.isnan(frp) & (frp > 0)
    rows, cols = np.where(fire)
    if len(rows) == 0:
        return [], scan_time

    dx = abs(x_arr[1] - x_arr[0]) if len(x_arr) > 1 else 5.6e-5
    dy = abs(y_arr[1] - y_arr[0]) if len(y_arr) > 1 else 5.6e-5

    xc = x_arr[cols]
    yc = y_arr[rows]
    fire_frp = frp[rows, cols]
    fire_dqf = dqf[rows, cols]

    # Compute 4 corners (SW SE NE NW) for every fire pixel at once
    pp = (H, lon0, r_eq, r_pol)
    corners = [
        scan_to_latlon(xc - dx/2, yc - dy/2, *pp),   # SW
        scan_to_latlon(xc + dx/2, yc - dy/2, *pp),   # SE
        scan_to_latlon(xc + dx/2, yc + dy/2, *pp),   # NE
        scan_to_latlon(xc - dx/2, yc + dy/2, *pp),   # NW
    ]

    features = []
    for i in range(len(rows)):
        frp_val = float(fire_frp[i])
        dqf_val = 0 if np.isnan(fire_dqf[i]) else int(fire_dqf[i])
        style   = pixel_style(frp_val, dqf_val)

        # GeoJSON uses [lon, lat] order
        ring = [[float(corners[j][1][i]), float(corners[j][0][i])] for j in range(4)]
        ring.append(ring[0])  # close polygon

        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Polygon', 'coordinates': [ring]},
            'properties': {
                'style':   style,
                'frp':     round(frp_val, 1),
                'dqf':     dqf_val,
                'tooltip': f'{frp_val:.0f} MW | DQF {dqf_val} | {scan_time[:16]} UTC',
            },
        })

    return features, scan_time


# ── Fetch scans (oldest → newest, max N frames) ───────────────────────────────

def fetch_scans(max_frames=12):
    fs    = s3fs.S3FileSystem(anon=True)
    now   = datetime.now(timezone.utc)
    local = os.path.join(os.path.dirname(__file__), '_goes19_tmp.nc')

    # Collect all available file paths across last 2 hours, newest last
    all_files = []
    for dh in range(2, -1, -1):
        t    = now - timedelta(hours=dh)
        path = f'noaa-goes19/ABI-L2-FDCC/{t:%Y/%j/%H}/'
        try:
            all_files.extend(sorted(fs.ls(path)))
        except Exception:
            pass

    # Deduplicate and thin to max_frames evenly spaced
    all_files = sorted(set(all_files))
    if len(all_files) > max_frames:
        step  = len(all_files) / max_frames
        idxs  = [int(i * step) for i in range(max_frames)]
        # Always include the very latest
        if (len(all_files) - 1) not in idxs:
            idxs[-1] = len(all_files) - 1
        all_files = [all_files[i] for i in sorted(set(idxs))]

    print(f'Loading {len(all_files)} scans...')
    frames = []  # list of (scan_time_str, features_list)
    for f in all_files:
        try:
            fs.get(f, local)
            features, scan_time = process_scan(local)
            frames.append((scan_time, features))
            print(f'  {scan_time[:19]}: {len(features)} fire pixels')
        except Exception as e:
            print(f'  error: {e}')

    return frames


# ── Wrap frames into TimestampedGeoJson structure ─────────────────────────────

def frames_to_geojson(frames):
    features = []
    for scan_time_str, frame_feats in frames:
        try:
            t0 = datetime.fromisoformat(scan_time_str.rstrip('Z').replace('Z', '+00:00'))
            if t0.tzinfo is None:
                t0 = t0.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        t1 = t0 + timedelta(minutes=5)
        ts = [t0.strftime('%Y-%m-%dT%H:%M:%S'), t1.strftime('%Y-%m-%dT%H:%M:%S')]

        for feat in frame_feats:
            f = {**feat, 'properties': {**feat['properties'], 'times': ts}}
            features.append(f)

    return {'type': 'FeatureCollection', 'features': features}


# ── Build map ─────────────────────────────────────────────────────────────────

def build_map(frames):
    # Center on fires
    all_lats, all_lons = [], []
    for _, feats in frames:
        for feat in feats:
            for lon, lat in feat['geometry']['coordinates'][0]:
                all_lats.append(lat)
                all_lons.append(lon)

    center = [np.mean(all_lats) if all_lats else 50.0,
              np.mean(all_lons) if all_lons else -100.0]

    m = folium.Map(location=center, zoom_start=5, tiles=None, control_scale=True)

    # Base layers
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    for label, layer, date, show in [
        (f'VIIRS NOAA-20 ({yesterday})',
         'VIIRS_NOAA20_CorrectedReflectance_TrueColor', yesterday, True),
        (f'MODIS Terra ({yesterday})',
         'MODIS_Terra_CorrectedReflectance_TrueColor', yesterday, False),
        ('Dark basemap', None, None, False),
    ]:
        if layer:
            url = (f'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/'
                   f'{layer}/default/{date}/GoogleMapsCompatible_Level9/{{z}}/{{y}}/{{x}}.jpg')
            folium.TileLayer(tiles=url, name=label, attr='NASA GIBS',
                             max_zoom=9, show=show).add_to(m)
        else:
            folium.TileLayer(tiles='CartoDB dark_matter', name=label,
                             attr='CartoDB', show=show).add_to(m)

    # Fire pixel timeline
    geojson = frames_to_geojson(frames)
    n = len(geojson['features'])
    latest = frames[-1][0][:16] if frames else ''

    if n > 0:
        TimestampedGeoJson(
            data=geojson,
            period='PT5M',
            duration='PT5M',
            transition_time=200,
            auto_play=False,
            loop=True,
            loop_button=True,
            date_options='YYYY-MM-DD HH:mm [UTC]',
            time_slider_drag_update=True,
            add_last_point=False,
        ).add_to(m)

    # Legend
    legend = f"""
    <div style="position:fixed;bottom:90px;left:10px;z-index:1000;
                background:rgba(10,10,20,0.88);color:#eee;padding:10px 14px;
                border-radius:8px;font-size:11px;font-family:monospace;line-height:2.0;
                border:1px solid #333">
      <b style="font-size:12px">GOES-19 FDCC Fire Pixels</b><br>
      <span style="color:#FF0000;font-size:15px">&#9632;</span> &gt;500 MW &nbsp;
      <span style="color:#FF6600;font-size:15px">&#9632;</span> 100-500 MW<br>
      <span style="color:#FFCC00;font-size:15px">&#9632;</span> 20-100 MW &nbsp;
      <span style="color:#FFFF33;font-size:15px">&#9632;</span> &lt;20 MW<br>
      Border thickness = confidence (DQF)<br>
      Dashed = cloud-affected<br>
      <hr style="border-color:#333;margin:5px 0">
      Each square &#8776; 2km GOES pixel<br>
      Latest scan: {latest} UTC<br>
      {n} features across {len(frames)} frames
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    return m


if __name__ == '__main__':
    frames = fetch_scans(max_frames=12)
    print(f'Loaded {len(frames)} scans total')
    m = build_map(frames)
    out = os.path.join(os.path.dirname(__file__), 'goes19_replay.html')
    m.save(out)
    print(f'Saved: {out}')
    import webbrowser
    webbrowser.open(os.path.abspath(out))
