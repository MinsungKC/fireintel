import s3fs
import xarray as xr
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
import os

def fetch_latest_fdc():
    fs = s3fs.S3FileSystem(anon=True)
    now = datetime.now(timezone.utc)

    for delta_hours in range(0, 6):
        t = now - timedelta(hours=delta_hours)
        path = f"noaa-goes19/ABI-L2-FDCC/{t:%Y/%j/%H}/"
        try:
            files = fs.ls(path)
            if not files:
                continue
            latest = sorted(files)[-1]
            print(f"Downloading: {latest.split('/')[-1]}")
            local = os.path.join(os.path.dirname(__file__), '_goes19_tmp.nc')
            fs.get(latest, local)
            ds = xr.open_dataset(local, engine='netcdf4')
            return ds
        except Exception as e:
            print(f"  Error: {e}")
            continue

    raise RuntimeError("No GOES-19 FDC files found in last 6 hours")

def plot_hotspots(ds):
    # Fire mask: values >= 10 indicate detected fire
    mask = ds['Mask'].values
    lat = ds['latitude'].values if 'latitude' in ds else None
    lon = ds['longitude'].values if 'longitude' in ds else None

    # If lat/lon not embedded, compute from projection
    if lat is None or lon is None:
        # GOES fixed grid projection
        proj = ds['goes_imager_projection']
        H = proj.attrs['perspective_point_height'] + proj.attrs['semi_major_axis']
        lon_origin = proj.attrs['longitude_of_projection_origin']
        r_eq = proj.attrs['semi_major_axis']
        r_pol = proj.attrs['semi_minor_axis']

        x = ds['x'].values  # radians
        y = ds['y'].values

        xx, yy = np.meshgrid(x, y)
        sin_x = np.sin(xx)
        cos_x = np.cos(xx)
        sin_y = np.sin(yy)
        cos_y = np.cos(yy)

        a = sin_x**2 + cos_x**2 * (cos_y**2 + (r_eq/r_pol)**2 * sin_y**2)
        b = -2 * H * cos_x * cos_y
        c = H**2 - r_eq**2

        det = b**2 - 4*a*c
        valid = det >= 0
        rs = np.where(valid, (-b - np.sqrt(np.where(valid, det, 0))) / (2*a), np.nan)

        sx = rs * cos_x * cos_y
        sy = -rs * sin_x
        sz = rs * cos_x * sin_y

        lat = np.degrees(np.arctan((r_eq/r_pol)**2 * sz / np.sqrt((H - sx)**2 + sy**2)))
        lon = lon_origin - np.degrees(np.arctan(sy / (H - sx)))

    # Fire pixels: non-NaN FRP > 0
    frp_raw = ds['Power'].values if 'Power' in ds else None
    if frp_raw is not None:
        fire_mask = ~np.isnan(frp_raw) & (frp_raw > 0)
        frp = frp_raw[fire_mask]
    else:
        fire_mask = ~np.isnan(mask) & (mask >= 10) & (mask < 20)
        frp = None

    fire_lat = lat[fire_mask]
    fire_lon = lon[fire_mask]

    scan_time = ds.attrs.get('time_coverage_start', 'Unknown')
    print(f"Scan time: {scan_time}")
    print(f"Active fire pixels: {fire_mask.sum()}")

    if fire_mask.sum() == 0:
        print("No active fires detected in current frame.")
        return

    size = np.clip(frp / 5, 8, 35) if frp is not None else 8
    color = frp.tolist() if frp is not None else 'red'
    hover = (
        [f"Lat: {la:.3f}<br>Lon: {lo:.3f}<br>FRP: {p:.1f} MW"
         for la, lo, p in zip(fire_lat, fire_lon, frp)]
        if frp is not None
        else [f"Lat: {la:.3f}<br>Lon: {lo:.3f}" for la, lo in zip(fire_lat, fire_lon)]
    )

    fig = go.Figure(go.Scattergeo(
        lat=fire_lat,
        lon=fire_lon,
        mode='markers',
        marker=dict(
            size=size,
            color=color if frp is not None else 'red',
            colorscale='YlOrRd',
            colorbar=dict(title='FRP (MW)') if frp is not None else None,
            opacity=0.85,
            line=dict(width=0.3, color='white'),
        ),
        text=hover,
        hoverinfo='text',
        name='Fire hotspots'
    ))

    fig.update_geos(
        scope='north america',
        showland=True, landcolor='#1a1a2e',
        showocean=True, oceancolor='#0f3460',
        showlakes=True, lakecolor='#0f3460',
        showcountries=True, countrycolor='#444',
        showcoastlines=True, coastlinecolor='#555',
        showsubunits=True, subunitcolor='#333',
        bgcolor='#16213e',
        projection_type='natural earth',
    )

    fig.update_layout(
        title=dict(
            text=f'GOES-19 Active Fire Hotspots (CONUS)<br><sup>{scan_time} UTC</sup>',
            font=dict(color='white', size=16)
        ),
        paper_bgcolor='#16213e',
        geo_bgcolor='#16213e',
        margin=dict(l=0, r=0, t=60, b=0),
        height=650,
    )

    out = 'goes19_hotspots.html'
    fig.write_html(out)
    print(f"Map saved to {out}")
    fig.show()

if __name__ == '__main__':
    ds = fetch_latest_fdc()
    plot_hotspots(ds)
