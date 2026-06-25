"""
Generates a self-contained HTML with:
  - Custom Leaflet timeline slider (bottom bar)
  - Per-frame GOES-19 fire pixel squares (colored by FRP/DQF)
  - Per-frame GIBS GOES GeoColor satellite imagery (synced with fire data)
  - Layer switcher: GOES GeoColor | VIIRS daily | Dark
"""

import os, json, math
import numpy as np
import s3fs
import xarray as xr
from datetime import datetime, timezone, timedelta

# ── GOES projection ───────────────────────────────────────────────────────────

def scan_to_latlon(x, y, H, lon0, r_eq, r_pol):
    cx, sx = np.cos(x), np.sin(x)
    cy, sy = np.cos(y), np.sin(y)
    a   = sx**2 + cx**2 * (cy**2 + (r_eq/r_pol)**2 * sy**2)
    b   = -2*H*cx*cy
    c   = H**2 - r_eq**2
    det = b**2 - 4*a*c
    rs  = np.where(det >= 0, (-b - np.sqrt(np.where(det>=0, det, 0)))/(2*a), np.nan)
    Sx  = rs*cx*cy;  Sy = -rs*sx;  Sz = rs*cx*sy
    lat = np.degrees(np.arctan((r_eq/r_pol)**2 * Sz / np.sqrt((H-Sx)**2 + Sy**2)))
    lon = lon0 - np.degrees(np.arctan(Sy / (H-Sx)))
    return lat, lon

# ── Fire pixel style ──────────────────────────────────────────────────────────

def pixel_style(frp, dqf):
    if   frp > 500: color = '#FF0000'
    elif frp > 200: color = '#FF3300'
    elif frp > 100: color = '#FF6600'
    elif frp >  50: color = '#FF9900'
    elif frp >  20: color = '#FFCC00'
    else:           color = '#FFFF44'
    weight  = max(1, 3 - int(dqf))
    opacity = 1.0 if dqf == 0 else (0.75 if dqf == 1 else 0.5)
    return {
        'color': color, 'weight': weight, 'opacity': opacity,
        'fillOpacity': 0.08 if dqf == 0 else 0, 'fillColor': color,
        'dashArray': '' if dqf < 2 else '4 4',
    }

# ── Process one scan ──────────────────────────────────────────────────────────

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
    xc, yc = x_arr[cols], y_arr[rows]
    fire_frp = frp[rows, cols]
    fire_dqf = dqf[rows, cols]

    pp = (H, lon0, r_eq, r_pol)
    corners = [
        scan_to_latlon(xc-dx/2, yc-dy/2, *pp),
        scan_to_latlon(xc+dx/2, yc-dy/2, *pp),
        scan_to_latlon(xc+dx/2, yc+dy/2, *pp),
        scan_to_latlon(xc-dx/2, yc+dy/2, *pp),
    ]

    features = []
    for i in range(len(rows)):
        fv  = float(fire_frp[i])
        dv  = 0 if np.isnan(fire_dqf[i]) else int(fire_dqf[i])
        ring = [[float(corners[j][1][i]), float(corners[j][0][i])] for j in range(4)]
        ring.append(ring[0])
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Polygon', 'coordinates': [ring]},
            'properties': {
                'style':   pixel_style(fv, dv),
                'tooltip': f'{fv:.0f} MW &nbsp;|&nbsp; DQF {dv}',
            },
        })
    return features, scan_time

# ── Fetch scans ───────────────────────────────────────────────────────────────

def fetch_scans(max_frames=12):
    fs    = s3fs.S3FileSystem(anon=True)
    now   = datetime.now(timezone.utc)
    local = os.path.join(os.path.dirname(__file__), '_goes19_tmp.nc')

    all_files = []
    for dh in range(2, -1, -1):
        t = now - timedelta(hours=dh)
        try:
            all_files.extend(sorted(fs.ls(f'noaa-goes19/ABI-L2-FDCC/{t:%Y/%j/%H}/')))
        except Exception:
            pass

    all_files = sorted(set(all_files))
    if len(all_files) > max_frames:
        step  = len(all_files) / max_frames
        idxs  = sorted(set([int(i*step) for i in range(max_frames)] + [len(all_files)-1]))
        all_files = [all_files[i] for i in idxs]

    print(f'Loading {len(all_files)} scans...')
    frames = []
    for f in all_files:
        try:
            fs.get(f, local)
            features, scan_time = process_scan(local)
            frames.append((scan_time, features))
            print(f'  {scan_time[:19]}: {len(features)} fire pixels')
        except Exception as e:
            print(f'  error: {e}')
    return frames

# ── GIBS tile URLs ────────────────────────────────────────────────────────────

GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best'

def goes_geocolor_url(scan_time_str):
    """GIBS GOES East GeoColor — updates every 10 min, works day & night."""
    try:
        t = datetime.fromisoformat(scan_time_str.rstrip('Z'))
        # Round to nearest 10 min for GIBS availability
        t = t.replace(minute=(t.minute // 10)*10, second=0, microsecond=0)
        ts = t.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        ts = '2026-06-21T00:00:00Z'
    return f'{GIBS}/GOES-East_ABI_GeoColor/default/{ts}/250m/{{z}}/{{y}}/{{x}}.jpg'

def goes_ir_url(scan_time_str):
    """GIBS GOES East Band 13 (thermal IR) — works at night, shows fire heat."""
    try:
        t = datetime.fromisoformat(scan_time_str.rstrip('Z'))
        t = t.replace(minute=(t.minute // 10)*10, second=0, microsecond=0)
        ts = t.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        ts = '2026-06-21T00:00:00Z'
    return f'{GIBS}/GOES-East_ABI_Band13_Clean_IR/default/{ts}/2km/{{z}}/{{y}}/{{x}}.png'

def viirs_url(scan_time_str):
    try:
        t = datetime.fromisoformat(scan_time_str.rstrip('Z'))
        day = (t - timedelta(days=1)).strftime('%Y-%m-%d')
    except Exception:
        day = '2026-06-20'
    return f'{GIBS}/VIIRS_NOAA20_CorrectedReflectance_TrueColor/default/{day}/GoogleMapsCompatible_Level9/{{z}}/{{y}}/{{x}}.jpg'

# ── Build frames JSON for JS ──────────────────────────────────────────────────

def build_frames_json(frames):
    out = []
    for scan_time, feats in frames:
        out.append({
            'time':      scan_time[:19].replace('T', ' '),
            'count':     len(feats),
            'goes_url':  goes_geocolor_url(scan_time),
            'ir_url':    goes_ir_url(scan_time),
            'viirs_url': viirs_url(scan_time),
            'features':  feats,
        })
    return out

# ── HTML template ─────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>GOES-19 Fire Replay</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#050510;font-family:monospace}
#map{position:absolute;top:0;left:0;right:0;bottom:74px}
#bar{position:fixed;bottom:0;left:0;right:0;height:74px;
     background:rgba(5,5,20,0.96);border-top:1px solid #223;
     display:flex;align-items:center;gap:10px;padding:0 16px;z-index:9000}
#slider{flex:1;-webkit-appearance:none;height:5px;border-radius:3px;
        background:#1a2a3a;outline:none;cursor:pointer}
#slider::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;
  border-radius:50%;background:#ff6600;cursor:pointer;border:2px solid #ff9900}
#time-label{min-width:220px;color:#ff9900;font-size:12px;white-space:nowrap}
#fire-count{color:#ff4444;font-size:11px;min-width:90px}
.btn{background:#0d1b2a;color:#7bc;border:1px solid #234;padding:5px 11px;
     border-radius:4px;cursor:pointer;font-size:12px;white-space:nowrap}
.btn:hover{background:#1a2a3a}
.btn.active{background:#1a3a5a;color:#5df;border-color:#46a}
#legend{position:fixed;top:12px;right:12px;z-index:8000;
        background:rgba(5,5,20,0.9);color:#ddd;padding:10px 14px;
        border-radius:8px;font-size:11px;line-height:2;border:1px solid #223}
#layer-row{display:flex;gap:5px;margin-top:6px;flex-wrap:wrap}
.leaflet-container{background:#050510}
</style>
</head>
<body>
<div id="map"></div>

<div id="bar">
  <button class="btn" id="play-btn">&#9654; Play</button>
  <button class="btn" onclick="setSpeed(2000)">0.5x</button>
  <button class="btn" onclick="setSpeed(1000)">1x</button>
  <button class="btn active" id="spd500" onclick="setSpeed(500)">2x</button>
  <button class="btn" onclick="setSpeed(250)">4x</button>
  <input type="range" id="slider" min="0" value="0">
  <span id="time-label">—</span>
  <span id="fire-count">—</span>
</div>

<div id="legend">
  <b>GOES-19 Fire Pixels (2km)</b><br>
  <span style="color:#FF0000">&#9632;</span>&gt;500 MW &nbsp;
  <span style="color:#FF6600">&#9632;</span>100-500 MW<br>
  <span style="color:#FFCC00">&#9632;</span>20-100 MW &nbsp;
  <span style="color:#FFFF44">&#9632;</span>&lt;20 MW<br>
  Thickness = DQF confidence<br>
  Dashed = cloud-affected<br>
  <hr style="border-color:#223;margin:5px 0">
  <b>Imagery</b>
  <div id="layer-row">
    <button class="btn active" id="btn-goes" onclick="setMode('goes')">GOES GeoColor</button>
    <button class="btn" id="btn-ir"   onclick="setMode('ir')">GOES IR</button>
    <button class="btn" id="btn-viirs" onclick="setMode('viirs')">VIIRS daily</button>
    <button class="btn" id="btn-dark" onclick="setMode('dark')">Dark only</button>
  </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
// ── Injected data ─────────────────────────────────────────────────────────
const FRAMES = %%FRAMES%%;
const CENTER = [%%LAT%%, %%LON%%];
const ZOOM   = %%ZOOM%%;

// ── Map init ──────────────────────────────────────────────────────────────
const map = L.map('map', {center: CENTER, zoom: ZOOM, zoomControl: true,
                           preferCanvas: true});

const darkBase = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  {attribution:'CartoDB', subdomains:'abcd', maxZoom:19}
).addTo(map);

// ── Per-frame layers ──────────────────────────────────────────────────────
const goesLayers  = [];
const irLayers    = [];
const viirsFired  = {};  // date -> tileLayer (reuse same layer for same date)
const fireLayers  = [];

FRAMES.forEach(frame => {
  goesLayers.push(L.tileLayer(frame.goes_url, {
    attribution:'NASA GIBS / NOAA GOES-19', maxZoom:9, opacity:0.9, errorTileUrl:''}));

  irLayers.push(L.tileLayer(frame.ir_url, {
    attribution:'NASA GIBS / NOAA GOES-19', maxZoom:9, opacity:0.85, errorTileUrl:''}));

  fireLayers.push(L.geoJSON(
    {type:'FeatureCollection', features: frame.features},
    {
      style: f => f.properties.style,
      onEachFeature: (f, layer) => {
        layer.bindTooltip(f.properties.tooltip, {sticky:true, opacity:0.92, className:'fire-tip'});
      }
    }
  ));
});

// ── Layer mode ────────────────────────────────────────────────────────────
let mode = 'goes';
let currentFrame = FRAMES.length - 1;
let activeBg  = null;   // current satellite tile layer on map

function setMode(m) {
  mode = m;
  ['goes','ir','viirs','dark'].forEach(id =>
    document.getElementById('btn-'+id).classList.remove('active'));
  document.getElementById('btn-'+m).classList.add('active');
  applyBg(currentFrame);
}

function applyBg(idx) {
  if (activeBg) { map.removeLayer(activeBg); activeBg = null; }

  if (mode === 'dark')  return;
  if (mode === 'goes')  { activeBg = goesLayers[idx];  }
  else if (mode === 'ir')    { activeBg = irLayers[idx];    }
  else if (mode === 'viirs') {
    const vurl = FRAMES[idx].viirs_url;
    if (!viirsFired[vurl]) {
      viirsFired[vurl] = L.tileLayer(vurl, {
        attribution:'NASA GIBS', maxZoom:9, opacity:0.9});
    }
    activeBg = viirsFired[vurl];
  }
  if (activeBg) activeBg.addTo(map);
  // fire layer always on top
  if (fireLayers[currentFrame]) fireLayers[currentFrame].addTo(map);
}

// ── Timeline ──────────────────────────────────────────────────────────────
const slider   = document.getElementById('slider');
const timeLabel = document.getElementById('time-label');
const fireCount = document.getElementById('fire-count');
slider.max = FRAMES.length - 1;

function showFrame(idx) {
  // remove old fire layer
  if (fireLayers[currentFrame]) map.removeLayer(fireLayers[currentFrame]);

  currentFrame = Math.max(0, Math.min(idx, FRAMES.length-1));
  slider.value = currentFrame;

  const f = FRAMES[currentFrame];
  timeLabel.textContent = f.time + ' UTC';
  fireCount.textContent = f.count + ' fire pixels';

  applyBg(currentFrame);
  fireLayers[currentFrame].addTo(map);
}

slider.addEventListener('input', e => {
  if (playing) pause();
  showFrame(parseInt(e.target.value));
});

// ── Playback ──────────────────────────────────────────────────────────────
let playing = false, timer = null, speed = 500;

function play() {
  playing = true;
  document.getElementById('play-btn').innerHTML = '&#9646;&#9646; Pause';
  timer = setInterval(() => showFrame((currentFrame+1) % FRAMES.length), speed);
}
function pause() {
  playing = false;
  clearInterval(timer);
  document.getElementById('play-btn').innerHTML = '&#9654; Play';
}

document.getElementById('play-btn').addEventListener('click', () =>
  playing ? pause() : play());

function setSpeed(ms) {
  speed = ms;
  document.querySelectorAll('#bar .btn').forEach(b => {
    if (b.textContent.includes('x')) b.classList.remove('active');
  });
  if (playing) { clearInterval(timer); timer = setInterval(() => showFrame((currentFrame+1)%FRAMES.length), speed); }
}

// ── Init ──────────────────────────────────────────────────────────────────
showFrame(FRAMES.length - 1);
</script>
</body>
</html>
"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    frames = fetch_scans(max_frames=12)
    if not frames:
        raise RuntimeError("No frames loaded")

    frames_data = build_frames_json(frames)

    # Center on fires
    all_lats, all_lons = [], []
    for _, feats in frames:
        for f in feats:
            for lon, lat in f['geometry']['coordinates'][0]:
                all_lats.append(lat); all_lons.append(lon)
    clat = round(float(np.mean(all_lats)) if all_lats else 50.0, 3)
    clon = round(float(np.mean(all_lons)) if all_lons else -100.0, 3)

    html = (HTML
        .replace('%%FRAMES%%', json.dumps(frames_data))
        .replace('%%LAT%%',    str(clat))
        .replace('%%LON%%',    str(clon))
        .replace('%%ZOOM%%',   '5'))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'goes19_replay_v2.html')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(html)

    print(f'Saved: {out}')
    import webbrowser
    webbrowser.open(out)

if __name__ == '__main__':
    main()
