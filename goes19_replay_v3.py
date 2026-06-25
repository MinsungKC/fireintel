"""
GOES-19 fire replay — v3
  Fire data  : NOAA NGFS OGC API fetched live in the browser per frame
  Imagery    : GIBS WMS GOES-East_ABI_GeoColor
  Frames     : Generated in JS at page load — always ends at current UTC time
"""

import os


# ── HTML template ─────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>GOES-19 Fire Replay</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#07101a;font-family:'Consolas',monospace;color:#b0c4d0}
#map{position:absolute;top:0;left:0;right:200px;bottom:54px}

/* ── bottom playback bar ───────────────────────────────── */
#bar{position:fixed;bottom:0;left:0;right:200px;height:54px;
  background:#07101a;border-top:1px solid #0f1e2a;
  display:flex;align-items:center;gap:8px;padding:0 14px;z-index:9000}
#pbtn{background:none;color:#b0c4d0;border:1px solid #182a38;padding:3px 12px;
  border-radius:3px;cursor:pointer;font-size:11px;font-family:inherit;
  white-space:nowrap;min-width:66px;text-align:center;transition:border-color .1s,color .1s}
#pbtn:hover{border-color:#ff5500;color:#ff7700}
.spd{background:none;border:none;color:#2e4a5a;padding:3px 5px;cursor:pointer;
  font-size:11px;font-family:inherit;border-radius:2px;transition:color .1s}
.spd:hover{color:#b0c4d0}
.spd.on{color:#ff7700}
#slider{flex:1;min-width:140px;-webkit-appearance:none;height:2px;
  background:#0f1e2a;outline:none;cursor:pointer;border-radius:1px}
#slider::-webkit-slider-thumb{-webkit-appearance:none;width:10px;height:10px;
  border-radius:50%;background:#ff5500;cursor:pointer}
#tlbl{color:#3a6070;font-size:11px;white-space:nowrap;min-width:160px}
.live-dot{display:inline-block;width:5px;height:5px;border-radius:50%;
  background:#ff4444;margin-right:5px;animation:pulse 1.4s infinite;vertical-align:middle}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}

/* ── right control panel ───────────────────────────────── */
#ctrl{position:fixed;top:0;right:0;bottom:54px;width:200px;
  background:#07101a;border-left:1px solid #0f1e2a;overflow-y:auto;z-index:8000}
#ctrl::-webkit-scrollbar{width:2px}
#ctrl::-webkit-scrollbar-thumb{background:#0f1e2a}
.cs{border-bottom:1px solid #0b1822;padding:12px 14px 10px}
.cs:last-child{border-bottom:none}
.ch{font-size:9px;letter-spacing:1.8px;color:#1a3040;
  text-transform:uppercase;margin-bottom:7px;font-weight:600}
.cr{display:flex;align-items:center;justify-content:space-between;
  padding:5px 0;cursor:pointer}
.cr:hover .cl{color:#c8d8e0}
.cl{font-size:12px;color:#5a8090;user-select:none;transition:color .1s;line-height:1.3}
.cs2{font-size:10px;color:#1e3040;margin-left:3px}

/* toggle switch */
.tog{position:relative;width:28px;height:15px;flex-shrink:0}
.tog .tk{position:absolute;inset:0;border-radius:8px;
  background:#0a1620;border:1px solid #142030;transition:all .15s}
.tog .kn{position:absolute;top:3px;left:3px;width:9px;height:9px;
  border-radius:50%;background:#1e3040;transition:all .15s}
.tog.on .tk{background:#6a1e00;border-color:#cc4000}
.tog.on .kn{transform:translateX(13px);background:#ff7700}

/* background radio */
.bgo{display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer}
.bgo:hover .cl{color:#c8d8e0}
.bgd{width:7px;height:7px;border-radius:50%;flex-shrink:0;
  background:#0a1620;border:1px solid #142030;transition:all .12s}
.bgo.on .bgd{background:#ff5500;border-color:#ff7700}
.bgo.on .cl{color:#c8d8e0}

/* legend rows */
.lr{display:flex;align-items:center;gap:6px;padding:2px 0;font-size:10px;color:#2e4a5a}
.lsq{width:8px;height:8px;border-radius:1px;flex-shrink:0}
.lnote{font-size:10px;color:#182a38;margin-top:4px;line-height:1.6}

/* cam icons */
.cam-icon{font-size:13px;line-height:18px;text-align:center;cursor:pointer}
.cam-fire-icon{font-size:15px;line-height:24px;text-align:center;cursor:pointer}
.cam-fire-ring{display:inline-block;filter:drop-shadow(0 0 5px #ff4400);
  animation:cam-pulse 1.5s ease-in-out infinite}
@keyframes cam-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.25)}}

/* popups */
.leaflet-container{background:#07101a!important}
.ftip{background:rgba(5,10,20,0.95)!important;color:#c8d8e0!important;
  border:1px solid #1a2e3e!important;font-size:11px!important;white-space:nowrap!important}

/* ── aircraft detail panel ─────────────────────────────── */
#ac-panel{position:fixed;bottom:62px;right:208px;z-index:8500;width:232px;
  background:#08111e;border:1px solid #1a2e3e;border-radius:4px;
  padding:13px 15px 11px;color:#b0c4d0;font-size:12px;display:none}
#ac-panel.vis{display:block}
#acp-close{position:absolute;top:8px;right:10px;cursor:pointer;
  color:#1a2e3e;font-size:17px;line-height:1;transition:color .1s}
#acp-close:hover{color:#b0c4d0}
#acp-cs{font-size:20px;font-weight:700;color:#FF7700;letter-spacing:1px;
  padding-right:20px;line-height:1.1}
#acp-reg{color:#3a5a6a;font-size:11px;margin:2px 0 1px}
#acp-type{color:#2a6a9a;font-size:11px;margin-bottom:10px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.acp-row{display:flex;justify-content:space-between;align-items:center;
  padding:4px 0;border-bottom:1px solid #0f1e2a}
.acp-row:last-of-type{border-bottom:none}
.acp-lbl{color:#1e3040;font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.acp-val{color:#c8d8e0;font-weight:600;font-size:12px;text-align:right}
#acp-fire{color:#FF6600;font-size:11px;margin-top:9px;text-align:center;
  letter-spacing:.5px;border-top:1px solid #0f1e2a;padding-top:7px}
#acp-loading{color:#1e3040;font-size:11px;text-align:center;padding:6px 0}
</style>
</head>
<body>
<div id="map"></div>

<div id="bar">
  <button id="pbtn">&#9654; Play</button>
  <button class="spd" id="spd-05" onclick="setSpeed(2000)">0.5×</button>
  <button class="spd" id="spd-1"  onclick="setSpeed(1000)">1×</button>
  <button class="spd on" id="spd-2"  onclick="setSpeed(500)">2×</button>
  <button class="spd" id="spd-4"  onclick="setSpeed(250)">4×</button>
  <input type="range" id="slider" min="0" value="0">
  <span id="tlbl">—</span>
</div>

<div id="ctrl">
  <div class="cs">
    <div class="ch">Overlays</div>
    <div class="cr" onclick="toggleAircraft()">
      <span class="cl">Aircraft <span id="ac-status" class="cs2"></span></span>
      <span id="b-ac" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleRadar()">
      <span class="cl">Radar</span>
      <span id="b-radar" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleEchoTops()">
      <span class="cl">Echo Tops</span>
      <span id="b-etops" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleFirms()">
      <span class="cl">FIRMS VIIRS <span id="firms-status" class="cs2"></span></span>
      <span id="b-firms" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleFuel()">
      <span class="cl">Fuel Types</span>
      <span id="b-fuel" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleFireAlerts()">
      <span class="cl">Fire Alerts <span id="falerts-status" class="cs2"></span></span>
      <span id="b-falerts" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleFireZones()">
      <span class="cl">Zone Forecasts</span>
      <span id="b-fzones" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
  </div>
  <div class="cs">
    <div class="ch">Cameras</div>
    <div class="cr" onclick="toggleFireCams()">
      <span class="cl">Fire Cams <span id="fcam-status" class="cs2"></span></span>
      <span id="b-fcam" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleFireOnly()">
      <span class="cl">Fire Only</span>
      <span id="b-fonly" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleTrafficCams()">
      <span class="cl">Traffic Cams <span id="tcam-status" class="cs2"></span></span>
      <span id="b-tcam" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
  </div>
  <div class="cs">
    <div class="ch">Weather</div>
    <div class="cr" onclick="toggleWind()">
      <span class="cl">Wind</span>
      <span id="b-wind" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleTemp()">
      <span class="cl">Temperature</span>
      <span id="b-temp" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleHumidity()">
      <span class="cl">Humidity</span>
      <span id="b-rh" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
    <div class="cr" onclick="toggleStations()">
      <span class="cl">Stations</span>
      <span id="b-stations" class="tog"><span class="tk"></span><span class="kn"></span></span>
    </div>
  </div>
  <div class="cs">
    <div class="ch">Background</div>
    <div class="bgo on" id="b-geo"   onclick="setMode('geo')"><span class="bgd"></span><span class="cl">GeoColor</span></div>
    <div class="bgo"    id="b-viirs" onclick="setMode('viirs')"><span class="bgd"></span><span class="cl">VIIRS</span></div>
    <div class="bgo"    id="b-s2"    onclick="setMode('s2')"><span class="bgd"></span><span class="cl">Sentinel-2</span></div>
    <div class="bgo"    id="b-dark"  onclick="setMode('dark')"><span class="bgd"></span><span class="cl">Dark</span></div>
  </div>
  <div class="cs">
    <div class="ch">GOES Fire (NGFS)</div>
    <div class="lr"><span class="lsq" style="background:#fff"></span>&gt;2000 MW</div>
    <div class="lr"><span class="lsq" style="background:#f0f"></span>&gt;1000 MW</div>
    <div class="lr"><span class="lsq" style="background:#f00"></span>&gt;500 MW</div>
    <div class="lr"><span class="lsq" style="background:#f60"></span>100–500 MW</div>
    <div class="lr"><span class="lsq" style="background:#fc0"></span>20–100 MW</div>
    <div class="lr"><span class="lsq" style="background:#ff4"></span>&lt;20 MW</div>
    <div class="lnote">solid = robust<br>dashed = sub-threshold</div>
  </div>
  <div class="cs">
    <div class="ch">Echo Tops</div>
    <div class="lr"><span class="lsq" style="background:#0c4"></span>&lt;20 kft</div>
    <div class="lr"><span class="lsq" style="background:#cc0"></span>20–40 kft</div>
    <div class="lr"><span class="lsq" style="background:#c20"></span>&gt;40 kft · PyroCb</div>
  </div>
  <div class="cs">
    <div class="ch">FIRMS VIIRS</div>
    <div class="lr"><span class="lsq" style="background:#ff0"></span>&lt;1 hr</div>
    <div class="lr"><span class="lsq" style="background:#fa0"></span>1–3 hr</div>
    <div class="lr"><span class="lsq" style="background:#f50"></span>3–6 hr</div>
    <div class="lr"><span class="lsq" style="background:#d10"></span>6–12 hr</div>
    <div class="lr"><span class="lsq" style="background:#800"></span>12–24 hr</div>
    <div class="lnote">size = FRP · S-NPP + NOAA-20/21</div>
  </div>
</div>

<div id="ac-panel">
  <span id="acp-close" onclick="closeAcPanel()">&#x2715;</span>
  <div id="acp-cs">—</div>
  <div id="acp-reg">—</div>
  <div id="acp-type">—</div>
  <div class="acp-row"><span class="acp-lbl">Altitude</span><span class="acp-val" id="acp-alt">—</span></div>
  <div class="acp-row"><span class="acp-lbl">Speed</span><span class="acp-val" id="acp-spd">—</span></div>
  <div class="acp-row"><span class="acp-lbl">Heading</span><span class="acp-val" id="acp-hdg">—</span></div>
  <div class="acp-row"><span class="acp-lbl">Squawk</span><span class="acp-val" id="acp-sq">—</span></div>
  <div class="acp-row"><span class="acp-lbl">Operator</span><span class="acp-val" id="acp-op" style="max-width:155px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">—</span></div>
  <div id="acp-loading" style="display:none">fetching trail…</div>
  <div id="acp-fire">&#9733; Fire Aviation</div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script src="https://unpkg.com/leaflet.vectorgrid/dist/Leaflet.VectorGrid.bundled.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/leaflet-velocity@2.1.0/dist/leaflet-velocity.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet-velocity@2.1.0/dist/leaflet-velocity.min.css">
<script>
// Build frame list at page-load time so the timeline always ends at "now"
const GIBS = 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi';
// NESDIS own tile CDN — ~10 min lag vs GIBS which can be 20-30+ min behind
const NESDIS_SAT_URL = 'https://fire.data.nesdis.noaa.gov/api/ogc/imagery/collections/GOESEastCONUSGeoColor/map/tiles/WebMercatorQuad/{z}/{x}/{y}.webp';
function makeFrames(hours=4, stepMin=10) {
  const frames = [];
  const now = new Date();
  // Round down to nearest stepMin boundary in UTC
  const end = new Date(Date.UTC(
    now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(),
    now.getUTCHours(), Math.floor(now.getUTCMinutes()/stepMin)*stepMin
  ));
  for (let ms = end - hours*3600000; ms <= +end; ms += stepMin*60000) {
    const t    = new Date(ms);
    const yest = new Date(ms - 86400000).toISOString().slice(0,10);
    // ±7 min datetime range for NESDIS tile API (covers one GOES CONUS scan interval)
    const dtS  = new Date(ms - 7*60000).toISOString().replace(/\.\d+Z$/,'Z');
    const dtE  = new Date(ms + 7*60000).toISOString().replace(/\.\d+Z$/,'Z');
    frames.push({
      time:      t.toISOString().slice(0,19).replace('T',' '),
      nesdis_dt: `${dtS}/${dtE}`,
      viirs_wms: GIBS + '?TIME=' + yest,
    });
  }
  return frames;
}
const FRAMES = makeFrames();

const map = L.map('map', {center: [38, -98], zoom: 6, preferCanvas: true});
// Custom pane above overlay pane (400) so echo tops render over fire polygons
map.createPane('aboveOverlay');
map.getPane('aboveOverlay').style.zIndex = 450;
map.getPane('aboveOverlay').style.pointerEvents = 'none';
// FIRMS pane above echo tops so dots aren't buried under echo top tiles
map.createPane('firmsPane');
map.getPane('firmsPane').style.zIndex = 460;
map.getPane('firmsPane').style.pointerEvents = 'none';
// NGFS pane above FIRMS — needs pointer events for interactive tooltips
map.createPane('ngfsPane');
map.getPane('ngfsPane').style.zIndex = 462;

const darkBase = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  {subdomains:'abcd', maxZoom:19, opacity:0.55}).addTo(map);

const WMS_PNG = {format:'image/png', transparent:true, version:'1.1.1', tileSize:512, crossOrigin:''};
const wmsCache = {};
function wmsLayer(timeUrl, layerName, opacity) {
  const k = timeUrl + '|' + layerName;
  if (!wmsCache[k])
    wmsCache[k] = L.tileLayer.wms(timeUrl, Object.assign({}, WMS_PNG, {layers: layerName, opacity}));
  return wmsCache[k];
}

// Cache NESDIS satellite layers per datetime range — one per frame slot
const nesdisCache = {};
function getNESDISSatLayer(dt) {
  const key = dt || 'latest';
  if (!nesdisCache[key]) {
    const url = dt
      ? `${NESDIS_SAT_URL}?datetime=${encodeURIComponent(dt)}`
      : NESDIS_SAT_URL;
    nesdisCache[key] = L.tileLayer(url, {
      maxNativeZoom: 10, opacity: 0.92,
      attribution: 'NOAA GOES-East GeoColor (NESDIS)',
    });
  }
  return nesdisCache[key];
}

function getViirsLayer(baseUrl) {
  return wmsLayer(baseUrl, 'VIIRS_NOAA20_CorrectedReflectance_TrueColor', 0.90);
}

let activeBgLayers = [];

// ── NGFS fire detection — Mapbox Vector Tiles from NESDIS OGC tile API ───────
// Uses the same tile endpoint as fire.data.nesdis.noaa.gov/map — always current,
// no per-frame GeoJSON fetch, no 2000-feature limit.
const NGFS_TILE_BASE = 'https://fire.data.nesdis.noaa.gov/api/ogc/detections/collections';
// Two CONUS collections — GOES-19 east owns lon > -105°, GOES-18 west owns lon ≤ -105°.
// The MVT features include a 'longitude' property so we can split them in the style fn.
const NGFS_TILE_COLLS = [
  { coll: 'ngfs_schema.ngfs_detections_scene_east_conus', minLon: -105 },  // GOES-19
  { coll: 'ngfs_schema.ngfs_detections_scene_west_conus', maxLon: -105 },  // GOES-18
];

function fireColor(frp) {
  if (frp == null || frp <= 0) return '#FF6600';
  return frp>2000?'#FFFFFF':frp>1000?'#FF00FF':frp>500?'#FF0000':
         frp>200?'#FF3300':frp>100?'#FF6600':frp>50?'#FF9900':
         frp>20?'#FFCC00':'#FFFF44';
}

let ngfsGroup = null;
const ngfsFrameCache = {}; // frame idx → L.layerGroup — avoids rebuild on revisit

function buildNGFSTileLayer(dt) {
  const group = L.layerGroup();
  // dt = "startZ/endZ" for historical frames; null = latest (cache-bust by 5-min slot)
  const slot   = Math.floor(Date.now() / 300000);
  const dtParam = dt
    ? `?datetime=${encodeURIComponent(dt)}`
    : `?_t=${slot}`;

  for (const {coll, minLon, maxLon} of NGFS_TILE_COLLS) {
    const vl = L.vectorGrid.protobuf(
      `${NGFS_TILE_BASE}/${coll}/tiles/WebMercatorQuad/{z}/{x}/{y}${dtParam}`,
      {
        rendererFactory: L.canvas.tile,
        pane: 'ngfsPane',
        interactive: true,
        getFeatureId: f => f.properties.feature_tracking_id ?? Math.random(),
        vectorTileLayerStyles: {
          'default': props => {
            // Geographic split: each satellite only renders within its longitude zone
            const lon = parseFloat(props.longitude ?? 0);
            if (minLon != null && lon <= minLon) return { weight:0, opacity:0, fillOpacity:0, fill:false, stroke:false };
            if (maxLon != null && lon >  maxLon) return { weight:0, opacity:0, fillOpacity:0, fill:false, stroke:false };
            const frp    = parseFloat(props.frp ?? 0) || 0;
            const robust = parseInt(props.quality_flag ?? 0) === 1;
            const c      = fireColor(frp > 0 ? frp : null);
            return {
              fill: true,  fillColor: c, fillOpacity: 0.12,
              stroke: true, color: c,
              weight:    robust ? 2 : 1,
              opacity:   robust ? 1.0 : 0.65,
              dashArray: robust ? '' : '4 3',
            };
          }
        },
        maxNativeZoom: 10,
        minZoom: 3,
      }
    );

    vl.on('mouseover', e => {
      const p   = e.layer.properties;
      const lon = parseFloat(p.longitude ?? 0);
      // Don't show tooltip for out-of-zone (invisible) features
      if (minLon != null && lon <= minLon) return;
      if (maxLon != null && lon >  maxLon) return;
      const frp    = parseFloat(p.frp ?? 0) || 0;
      const name   = p.known_incident_name || p.type_description || 'Fire Detection';
      const loc    = [p.county, p.state].filter(Boolean).join(', ');
      const frpStr = frp > 0 ? `${frp.toFixed(0)} MW` : 'FRP N/A';
      const conf   = p.confidence ? ` · ${p.confidence}` : '';
      const time   = p.pixel_date_time ? `<br><span style="color:#aaa">${new Date(p.pixel_date_time).toUTCString().slice(0,-4)}</span>` : '';
      L.popup({ closeButton:false, autoPan:false, className:'ftip' })
        .setLatLng(e.latlng)
        .setContent(`<b>${name}</b><br>${frpStr}${loc ? ' · ' + loc : ''}${conf}${time}`)
        .openOn(map);
    });
    vl.on('mouseout', () => map.closePopup());

    group.addLayer(vl);
  }
  return group;
}

function loadNGFSFrame(idx) {
  if (ngfsGroup) { map.removeLayer(ngfsGroup); ngfsGroup = null; }
  if (ngfsFrameCache[idx]) {
    ngfsGroup = ngfsFrameCache[idx];
  } else {
    const isLatest = idx === FRAMES.length - 1;
    // Latest frame: always rebuild (no cache) so fresh detections show up
    // Historical frames: cache so re-visiting a frame doesn't reload tiles
    ngfsGroup = buildNGFSTileLayer(isLatest ? null : FRAMES[idx].nesdis_dt);
    if (!isLatest) ngfsFrameCache[idx] = ngfsGroup;
  }
  ngfsGroup.addTo(map);
}

// ── Background layers ─────────────────────────────────────────────────────────
let mode = 'geo';
function setMode(m) {
  mode = m;
  ['geo','viirs','s2','dark'].forEach(id => {
    const b = document.getElementById('b-'+id);
    if (b) b.classList.remove('on');
  });
  document.getElementById('b-'+m).classList.add('on');
  applyBg(cur);
}

const esriSat = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  {maxZoom:18, opacity:0.82, attribution:'Esri World Imagery'}
);

// EOX Sentinel-2 cloudless 2025 mosaic (10m, EPSG:3857, free, CORS open)
// URL format: /default/g/{z}/{TileRow}/{TileCol} where TileRow=y, TileCol=x
const s2Layer = L.tileLayer(
  'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/g/{z}/{y}/{x}.jpg',
  { maxNativeZoom: 14, maxZoom: 19, opacity: 0.90,
    attribution: 'Sentinel-2 cloudless 2025 &copy; <a href="https://eox.at">EOX IT Services</a>' }
);

// ── Satellite prefetch ────────────────────────────────────────────────────────
// Pre-adds next N satellite tile layers to the map at opacity 0 so the browser
// downloads the NESDIS WEBP tiles in the background. On frame switch the layer
// is already populated → just set opacity to 0.92, no visible loading gap.
let bgCleanupTimer = null;
const prefetchedSatLayers = new Set();

function prefetchSat(fromIdx) {
  if (mode !== 'geo') return;
  for (let i = 1; i <= 4; i++) {
    const idx = fromIdx + i;
    if (idx >= FRAMES.length) break;
    const layer = getNESDISSatLayer(FRAMES[idx].nesdis_dt);
    if (!map.hasLayer(layer)) {
      layer.setOpacity(0);
      layer.addTo(map);
      prefetchedSatLayers.add(layer);
    }
  }
}

// Pre-build NGFS VectorGrid objects for upcoming frames so addTo(map) is instant.
function prefetchNGFS(fromIdx) {
  for (let i = 1; i <= 4; i++) {
    const idx = fromIdx + i;
    if (idx >= FRAMES.length || ngfsFrameCache[idx]) continue;
    const isLatest = idx === FRAMES.length - 1;
    if (!isLatest) ngfsFrameCache[idx] = buildNGFSTileLayer(FRAMES[idx].nesdis_dt);
  }
}

function applyBg(idx) {
  if (bgCleanupTimer) { clearTimeout(bgCleanupTimer); bgCleanupTimer = null; }
  const f = FRAMES[idx];
  if (mode === 'geo') {
    if (!map.hasLayer(esriSat)) esriSat.addTo(map);
    if (map.hasLayer(darkBase)) map.removeLayer(darkBase);
    if (map.hasLayer(s2Layer))  map.removeLayer(s2Layer);
    const newSat = getNESDISSatLayer(f.nesdis_dt);
    prefetchedSatLayers.delete(newSat); // promote from prefetch to active
    if (!map.hasLayer(newSat)) newSat.addTo(map);
    newSat.setOpacity(0.92);
    // Keep previous layer on screen while new tiles render, then remove
    const toRemove = activeBgLayers.filter(l => l !== newSat);
    activeBgLayers = [newSat];
    bgCleanupTimer = setTimeout(() => {
      toRemove.forEach(l => { if (map.hasLayer(l)) map.removeLayer(l); });
      bgCleanupTimer = null;
    }, 600);
    prefetchSat(idx);
  } else if (mode === 's2') {
    // Leaving geo — purge prefetched sat layers
    prefetchedSatLayers.forEach(l => { if (map.hasLayer(l)) map.removeLayer(l); });
    prefetchedSatLayers.clear();
    activeBgLayers.forEach(l => { if (map.hasLayer(l)) map.removeLayer(l); });
    activeBgLayers = [];
    if (map.hasLayer(esriSat))  map.removeLayer(esriSat);
    if (map.hasLayer(darkBase)) map.removeLayer(darkBase);
    if (!map.hasLayer(s2Layer)) s2Layer.addTo(map);
  } else {
    prefetchedSatLayers.forEach(l => { if (map.hasLayer(l)) map.removeLayer(l); });
    prefetchedSatLayers.clear();
    activeBgLayers.forEach(l => { if (map.hasLayer(l)) map.removeLayer(l); });
    activeBgLayers = [];
    if (map.hasLayer(esriSat))  map.removeLayer(esriSat);
    if (map.hasLayer(s2Layer))  map.removeLayer(s2Layer);
    if (!map.hasLayer(darkBase)) darkBase.addTo(map);
    if (mode === 'viirs') {
      const vl = getViirsLayer(f.viirs_wms);
      activeBgLayers = [vl];
      vl.addTo(map);
    }
  }
}

// ── Aircraft layer (ADS-B) ────────────────────────────────────────────────────
const acLayer = L.layerGroup().addTo(map);
let acOn = false, acTimer = null;

// Callsign prefixes: TKR=firefighting reserved, CFR=CAL FIRE, CUL/CU=Coulson,
//   FTK=NC Forest Svc, GST=Global SuperTanker, HWK=Firehawk, FRLD=fire lead,
//   AA(?!L)=air attack (AAL is American Airlines — excluded), SEAT/ATGS/MAFFS=roles
// Callsign suffix: FD = fire department (LAFD, VCFD, OCFD, ...)
const FIRE_AC = /^(TKR|CFR|CUL?|FTK|GST|HWK|SEAT|ATGS|MAFFS|FRLD|LEAD|AA(?![LYR]))|(FD|DF)$/i;
// Block commercial carrier ICAO codes followed by digits (e.g. FDX1234, UAL890).
// NOTE: bare ^AA is intentionally excluded here — it would block air attack callsigns
// like AA01/AA7WY; AAL is already excluded inside FIRE_AC via AA(?![LYR]).
const FIRE_EXCL = /^(FDX|FDE|UPS|DAL|UAL|AAL|SWA|JBU|SKW|ASA|FFT|GTI|NKS|RPA|PDT)\d/i;
// Operator name fallback — covers gov agencies, contractors, and common abbreviations
const FIRE_OP = /cal\s*fire|california\s+dept|dept.*forest|forest\s*(serv|dept)|usda.*forest|bureau\s+of\s+land|nifc|usfs|blm\s*(fire|air|tanker|aviation)|wildland\s+fire|aerial\s+fire|fire\s+aviation|air\s+tanker|coulson|neptune\s+air|aero\s+flite|10\s+tanker/i;

function acIcon(hdg, fire) {
  const fill   = fire ? '#FF7700' : '#44AAFF';
  const glow   = fire ? 'drop-shadow(0 0 3px #FF3300) drop-shadow(0 0 1px #000)'
                      : 'drop-shadow(0 0 2px #0055CC) drop-shadow(0 0 1px #000)';
  // Airplane silhouette viewed from above, nose pointing up (north at hdg=0)
  const d = 'M0,-13 C0.8,-8 1.5,-2 1.5,2 L11,7 L9.5,9 L1.5,6 L1.5,9 L3.5,12.5 L2,13.5 L0,12 L-2,13.5 L-3.5,12.5 L-1.5,9 L-1.5,6 L-9.5,9 L-11,7 L-1.5,2 C-1.5,-2 -0.8,-8 0,-13 Z';
  return L.divIcon({
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="-16 -16 32 32" style="filter:${glow};overflow:visible">
      <path transform="rotate(${hdg||0})" d="${d}"
        fill="${fill}" stroke="rgba(255,255,255,0.7)" stroke-width="1" stroke-linejoin="round"/>
    </svg>`,
    iconSize: [32, 32], iconAnchor: [16, 16], className: ''
  });
}

const acMarkers   = new Map(); // hex → {marker, drTimer, lat, lon, track, gs, ...}
const trailHistory = new Map(); // hex → [{lat, lon}] — grows every 30 s poll, max 120 pts (1 hr)

// Dead-reckoning: advance position every second using last known track + ground speed.
// 1 knot = 1 nm/h; 1 nm = 1/60 degree lat; lon degrees shrink with cos(lat).
function startDR(hex) {
  const e = acMarkers.get(hex);
  if (!e) return;
  if (e.drTimer) clearInterval(e.drTimer);
  e.drTimer = setInterval(() => {
    const en = acMarkers.get(hex);
    if (!en) return;
    const gs  = en.gs || 0;
    if (gs < 10) return; // stationary / hovering — don't drift
    const rad = (en.track || 0) * Math.PI / 180;
    const nm  = gs / 3600;                         // nm per second
    en.lat   += (nm / 60) * Math.cos(rad);
    en.lon   += (nm / 60) * Math.sin(rad) / Math.cos(en.lat * Math.PI / 180);
    en.marker.setLatLng([en.lat, en.lon]);
  }, 1000);
}

// Aircraft via local Python proxy → OpenSky (one CONUS request, no CORS, no circle juggling)
// Falls back to airplanes.live multi-circle if proxy unreachable (e.g. opened as file://)
const AL_PTS = [
  [47,-122],[40,-122],[36,-119],[34,-117],[45,-110],
  [40,-109],[33,-111],[31,-99],[40,-98],[35,-92],[33,-83],[40,-78],[30,-90],
];

// Convert an OpenSky state-vector array to the same shape fetchAircraft expects
function osToAc(s) {
  if (!s[5] || !s[6]) return null;  // lon / lat required
  return {
    hex:      s[0],
    flight:   s[1] || '',
    r:        '',         // OpenSky does not expose registration
    ownOp:    '',
    lat:      s[6],
    lon:      s[5],
    alt_baro: s[7] != null ? Math.round(s[7] * 3.28084) : null,  // m → ft
    gs:       s[9] != null ? Math.round(s[9] * 1.94384) : null,  // m/s → kts
    track:    s[10],
    squawk:   s[14] || '',
    t:        '',
  };
}

async function fetchAircraft() {
  const lbl = document.getElementById('ac-status');
  if (lbl) lbl.textContent = '...';
  try {
    let all = [];
    // ── Primary: local proxy → OpenSky (one shot, full CONUS) ──────────────
    try {
      const d = await fetch('/api/aircraft', {cache:'no-store'}).then(r => r.ok ? r.json() : null);
      if (d && d.states) {
        for (const s of d.states) {
          const a = osToAc(s);
          if (a) all.push(a);
        }
      }
    } catch(_) {}

    // ── Fallback: airplanes.live circle queries (file:// or proxy down) ────
    if (all.length === 0) {
      const seen = new Set();
      for (let i = 0; i < AL_PTS.length; i += 4) {
        const batch = AL_PTS.slice(i, i + 4);
        const results = await Promise.all(
          batch.map(([la,lo]) =>
            fetch(`https://api.airplanes.live/v2/point/${la}/${lo}/250`, {cache:'no-store'})
              .then(r => r.ok ? r.json() : {ac:[]}).catch(() => ({ac:[]}))
          )
        );
        for (const res of results)
          for (const a of (res.ac || []))
            if (!seen.has(a.hex)) { seen.add(a.hex); all.push(a); }
        if (i + 4 < AL_PTS.length) await new Promise(r => setTimeout(r, 300));
      }
    }

    const activeHexes = new Set();
    let fires = 0;
    for (const a of all) {
      if (!a.lat || !a.lon) continue;
      const cs  = (a.flight || '').trim();
      const reg = (a.r      || '').trim();
      const op  = (a.ownOp  || '').trim();
      if (FIRE_EXCL.test(cs)) continue;
      if (!FIRE_AC.test(cs) && !FIRE_AC.test(reg) && !FIRE_OP.test(op)) continue;
      fires++;
      activeHexes.add(a.hex);
      // Accumulate trail history (one snapshot every 30 s poll)
      const th = trailHistory.get(a.hex) || [];
      th.push({lat: a.lat, lon: a.lon});
      if (th.length > 120) th.shift();
      trailHistory.set(a.hex, th);
      const label = cs || reg || a.hex;
      const alt = a.alt_baro != null ? Math.round(a.alt_baro).toLocaleString() + ' ft' : '— ft';
      const kts = a.gs != null ? Math.round(a.gs) + ' kts' : '—';
      const tip = `<b>${label}</b><br>${alt} | ${kts}<br><span style="color:#FF6600">&#9733; Fire Aviation</span>`;

      if (acMarkers.has(a.hex)) {
        const e = acMarkers.get(a.hex);
        e.lat = a.lat; e.lon = a.lon; e.track = a.track; e.gs = a.gs;
        e.alt = a.alt_baro; e.cs = cs; e.reg = reg; e.op = op;
        e.acType = a.t || ''; e.squawk = a.squawk || '';
        e.marker.setLatLng([a.lat, a.lon]);
        e.marker.setIcon(acIcon(a.track, true));
        e.marker.setTooltipContent(tip);
        startDR(a.hex);
        if (selectedHex === a.hex)
          fillPanel(cs, reg, a.t||'', a.alt_baro, a.gs, a.track, a.squawk, op);
      } else {
        const hex = a.hex;
        const marker = L.marker([a.lat, a.lon], {icon: acIcon(a.track, true), zIndexOffset: 1000})
          .bindTooltip(tip, {className:'ftip', sticky:true})
          .on('click', () => selectAircraft(hex))
          .addTo(acLayer);
        acMarkers.set(hex, {
          marker, drTimer: null,
          lat: a.lat, lon: a.lon, track: a.track, gs: a.gs,
          alt: a.alt_baro, cs, reg, op, acType: a.t||'', squawk: a.squawk||'',
        });
        startDR(hex);
      }
    }

    for (const [hex, e] of acMarkers) {
      if (!activeHexes.has(hex)) {
        if (e.drTimer) clearInterval(e.drTimer);
        acLayer.removeLayer(e.marker);
        acMarkers.delete(hex);
        if (selectedHex === hex) closeAcPanel();
      }
    }

    if (lbl) lbl.textContent = fires ? fires + ' 🔥' : '';
  } catch(e) {
    if (lbl) lbl.textContent = 'err';
    console.warn('ADS-B:', e);
  }
}

function toggleAircraft() {
  acOn = !acOn;
  document.getElementById('b-ac').classList.toggle('on', acOn);
  if (acOn) {
    fetchAircraft();
    acTimer = setInterval(fetchAircraft, 30000);
  } else {
    clearInterval(acTimer);
    closeAcPanel();
    for (const e of acMarkers.values()) if (e.drTimer) clearInterval(e.drTimer);
    acLayer.clearLayers();
    acMarkers.clear();
    trailHistory.clear();
    const acSt = document.getElementById('ac-status');
    if (acSt) acSt.textContent = '';
  }
}

// ── Aircraft detail panel + trail ────────────────────────────────────────────
const AC_TYPES = {
  'AT8T':'Air Tractor AT-802T (SEAT)','AT80':'Air Tractor AT-800',
  'AT82':'Air Tractor AT-802','AT7T':'Air Tractor AT-702T',
  'CL41':'Canadair CL-415 Scooper','CL4T':'Canadair CL-415 Scooper',
  'CL2T':'Canadair CL-215T Scooper',
  'C130':'Lockheed C-130 Hercules','C17':'Boeing C-17 Globemaster',
  'DC10':'Douglas DC-10 (VLAT)','B744':'Boeing 747-400 (VLAT)',
  'RJ85':'BAe Avro RJ-85 (NGAS)','S2TT':'Grumman S-2T Tracker',
  'C208':'Cessna 208 Caravan','BE20':'Beechcraft King Air 200',
  'BE99':'Beechcraft 99 (Lead Plane)','PA31':'Piper PA-31 Navajo (Lead)',
  'H60':'Sikorsky S-70 / Firehawk','S61':'Sikorsky S-61',
  'B212':'Bell 212','B214':'Bell 214 BigLifter','B06':'Bell 206 JetRanger',
  'AS32':'AS-332 Super Puma','EC35':'Airbus H135',
  'MD87':'McDonnell Douglas MD-87','SF34':'SAAB 340',
  'DH8D':'Bombardier Q400','E135':'Embraer ERJ-135','P3':'Lockheed P-3 Orion',
};

let selectedHex = null;
const trailPoly = [];

function clearTrail() {
  trailPoly.forEach(p => map.removeLayer(p));
  trailPoly.length = 0;
}

function normPt(p) {
  if (Array.isArray(p)) return p[0] != null ? {lat:p[0], lon:p[1]} : null;
  if (p && p.lat != null)  return {lat:p.lat, lon: p.lng ?? p.lon};
  return null;
}

function drawTrail(trail) {
  clearTrail();
  if (!trail || trail.length < 2) return;
  const n = trail.length;
  for (let i = 1; i < n; i++) {
    const a = normPt(trail[i-1]), b = normPt(trail[i]);
    if (!a || !b) continue;
    const frac = i / n;
    trailPoly.push(L.polyline([[a.lat, a.lon],[b.lat, b.lon]], {
      color: '#FF6600', weight: frac > 0.7 ? 3 : 2,
      opacity: 0.1 + 0.85 * frac, smoothFactor: 1, interactive: false,
    }).addTo(map));
  }
}

function fillPanel(cs, reg, type, alt, gs, track, squawk, op) {
  document.getElementById('acp-cs').textContent  = cs || reg || '—';
  document.getElementById('acp-reg').textContent = reg ? reg : (cs ? '' : '—');
  const tname = AC_TYPES[type] || '';
  document.getElementById('acp-type').textContent = type ? (type + (tname ? ' · ' + tname : '')) : '—';
  document.getElementById('acp-alt').textContent  = alt  != null ? Math.round(alt).toLocaleString() + ' ft' : '—';
  document.getElementById('acp-spd').textContent  = gs   != null ? Math.round(gs)  + ' kts' : '—';
  document.getElementById('acp-hdg').textContent  = track!= null ? Math.round(track) + '°'  : '—';
  document.getElementById('acp-sq').textContent   = squawk || '—';
  document.getElementById('acp-op').textContent   = op || '—';
}

async function selectAircraft(hex) {
  if (selectedHex === hex) { closeAcPanel(); return; }
  selectedHex = hex;
  const panel = document.getElementById('ac-panel');
  panel.classList.add('vis');
  // Immediate fill + draw what we already have locally
  const e = acMarkers.get(hex);
  if (e) fillPanel(e.cs, e.reg, e.acType, e.alt, e.gs, e.track, e.squawk, e.op);
  drawTrail(trailHistory.get(hex) || []);
  document.getElementById('acp-loading').style.display = 'block';
  try {
    const data = await fetch(
      `https://api.airplanes.live/v2/hex/${hex}`, {cache:'no-store'}
    ).then(r => r.ok ? r.json() : {ac:[]}).catch(() => ({ac:[]}));
    if (selectedHex !== hex) return;
    const a = (data.ac || [])[0];
    document.getElementById('acp-loading').style.display = 'none';
    if (!a) return;
    const cs  = (a.flight || '').trim();
    const reg = (a.r      || '').trim();
    const op  = (a.ownOp  || a.desc || '').trim();
    fillPanel(cs, reg, a.t||'', a.alt_baro, a.gs, a.track, a.squawk, op);
    // Prefer API trail if available (longer history), otherwise keep local
    const remoteTrail = a.trail;
    if (remoteTrail && remoteTrail.length > 1) drawTrail(remoteTrail);
  } catch(err) {
    document.getElementById('acp-loading').style.display = 'none';
    console.warn('AC detail:', err);
  }
}

function closeAcPanel() {
  selectedHex = null;
  document.getElementById('ac-panel').classList.remove('vis');
  clearTrail();
}

// ── Fuel Types (LANDFIRE 2024 FBFM40) ────────────────────────────────────────
// FBFM40 = Scott & Burgan 40 Fire Behavior Fuel Models — the standard for
// operational fire behavior modeling (FARSITE, FlamMap, etc.)
const LANDFIRE_WMS = 'https://edcintl.cr.usgs.gov/geoserver/landfire/wms';
let fuelLayer = null, fuelOn = false;

function toggleFuel() {
  fuelOn = !fuelOn;
  const btn = document.getElementById('b-fuel');
  btn.classList.toggle('on', fuelOn);
  if (fuelOn) {
    if (!fuelLayer) {
      fuelLayer = L.tileLayer.wms(LANDFIRE_WMS, {
        layers: 'LF2024_FBFM40_CONUS',
        format: 'image/png', transparent: true, version: '1.1.1',
        opacity: 0.60,
        attribution: 'LANDFIRE 2024 FBFM40 (USGS)',
        pane: 'overlayPane',
      });
    }
    fuelLayer.addTo(map);
  } else {
    if (fuelLayer) map.removeLayer(fuelLayer);
  }
}

// ── Radar (IEM NEXRAD live composite) ─────────────────────────────────────────
const IEM_WMS = 'https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q.cgi';
let radarLive = null, radarOn = false, radarTimer = null;

function syncRadarToFrame(_idx) {
  if (!radarOn) return;
  if (!radarLive) {
    radarLive = L.tileLayer.wms(IEM_WMS, {
      layers: 'nexrad-n0q-900913', format: 'image/png', transparent: true,
      version: '1.1.1', opacity: 0.65, pane: 'aboveOverlay',
      attribution: 'IEM NEXRAD (live)',
    });
    radarLive.addTo(map);
  }
}

function toggleRadar() {
  radarOn = !radarOn;
  document.getElementById('b-radar').classList.toggle('on', radarOn);
  if (radarOn) {
    syncRadarToFrame(cur);
    radarTimer = setInterval(() => { if (radarLive) radarLive.redraw(); }, 300000);
  } else {
    if (radarLive) { map.removeLayer(radarLive); radarLive = null; }
    clearInterval(radarTimer);
    document.getElementById('b-radar').innerHTML = '&#128225; Radar';
  }
}

// ── Echo Tops (NEXRAD NEET v18 — pyroCb/smoke column heights) ─────────────────
// conus_neet_v18 = NOAA MRMS composite echo tops, updated ~2 min, units = kft
// High values (>40 kft) over fires = pyroCb. Smoke lofted debris also visible.
const etLayer = L.tileLayer.wms('https://opengeo.ncep.noaa.gov/geoserver/conus/ows', {
  layers: 'conus_neet_v18',
  format: 'image/png',
  transparent: true,
  version: '1.3.0',
  opacity: 0.80,
  pane: 'aboveOverlay',
  attribution: 'NOAA MRMS Echo Tops',
  crossOrigin: '',
});
let etOn = false;

function toggleEchoTops() {
  etOn = !etOn;
  document.getElementById('b-etops').classList.toggle('on', etOn);
  if (etOn) etLayer.addTo(map);
  else map.removeLayer(etLayer);
}

// ── NASA FIRMS VIIRS NRT — raw canvas overlay, 20k+ points ──────────────────
// Direct canvas draw per frame — no Leaflet layer-per-point overhead.
// Click detection done in the map click handler via findNearest().
let firmsMarkerLayer = null, firmsOn = false, firmsCache = null;

const FirmsCanvasLayer = L.Layer.extend({
  initialize(pts) { this._pts = pts; },

  onAdd(map) {
    this._map = map;
    this._canvas = document.createElement('canvas');
    Object.assign(this._canvas.style, {
      position: 'absolute', top: '0', left: '0', pointerEvents: 'none',
    });
    map.getPane('firmsPane').appendChild(this._canvas);
    this._fn = () => this._draw();
    map.on('moveend zoomend resize', this._fn);
    this._draw();
  },

  onRemove(map) {
    map.off('moveend zoomend resize', this._fn);
    this._canvas.remove();
  },

  _draw() {
    const map = this._map, sz = map.getSize();
    const cv = this._canvas;
    cv.width = sz.x; cv.height = sz.y;
    const ctx = cv.getContext('2d');
    ctx.clearRect(0, 0, sz.x, sz.y);
    for (const p of this._pts) {
      // latLngToLayerPoint gives coords in pane-space (same origin as the canvas).
      // latLngToContainerPoint would be offset by the pane's CSS transform during pan.
      const pt = map.latLngToLayerPoint([p.lat, p.lon]);
      if (pt.x < -15 || pt.y < -15 || pt.x > sz.x + 15 || pt.y > sz.y + 15) continue;
      const r = firmsRadius(p.frp);
      ctx.globalAlpha = p.conf === 'high' ? 0.95 : p.conf === 'low' ? 0.55 : 0.80;
      ctx.fillStyle = firmsAgeColor(p.ageHrs);
      ctx.fillRect(pt.x - r, pt.y - r, r * 2, r * 2);
    }
    ctx.globalAlpha = 1;
  },

  findNearest(latlng) {
    const map = this._map, cp = map.latLngToContainerPoint(latlng);
    let best = null, bestD2 = 625; // 25px hit radius
    for (const p of this._pts) {
      const pt = map.latLngToContainerPoint([p.lat, p.lon]);
      const d2 = (pt.x - cp.x) ** 2 + (pt.y - cp.y) ** 2;
      if (d2 < bestD2) { bestD2 = d2; best = p; }
    }
    return best;
  },
});

function firmsAgeColor(ageHrs) {
  if (ageHrs <  1) return '#ffff00';   // < 1h  — white-yellow (hottest)
  if (ageHrs <  3) return '#ffaa00';   // 1-3h  — golden orange
  if (ageHrs <  6) return '#ff5500';   // 3-6h  — deep orange
  if (ageHrs < 12) return '#dd1100';   // 6-12h — fire red
  return '#880000';                     // 12-24h — dark red (cooling)
}

function firmsRadius(frp) {
  if (frp > 500) return 12;
  if (frp > 200) return  9;
  if (frp >  50) return  7;
  if (frp >  10) return  5;
  return 3;
}

async function loadFirmsData() {
  if (firmsCache) return firmsCache;
  const text = await fetch('/api/firms').then(r => r.text());
  const lines = text.trim().split('\n');
  if (lines.length < 2) return (firmsCache = []);
  const h = lines[0].split(',').map(s => s.trim());
  const fi = k => h.indexOf(k);
  const iLat = fi('latitude'), iLon = fi('longitude'), iFrp = fi('frp');
  const iConf = fi('confidence'), iDate = fi('acq_date'), iTime = fi('acq_time');
  const iSat = fi('satellite');
  const now = Date.now();
  const pts = [];
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    const c = lines[i].split(',');
    const lat = parseFloat(c[iLat]), lon = parseFloat(c[iLon]);
    if (!isFinite(lat) || !isFinite(lon)) continue;
    const frp  = parseFloat(c[iFrp]) || 0;
    const conf = (c[iConf] || '').trim();
    const ad   = (c[iDate] || '').trim();
    const at   = (c[iTime] || '').trim().padStart(4, '0');
    const sat  = (c[iSat]  || '').trim();
    const dt   = new Date(`${ad}T${at.slice(0,2)}:${at.slice(2)}:00Z`);
    const ageHrs = (now - dt.getTime()) / 3600000;
    pts.push({ lat, lon, frp, conf, ageHrs, dt, sat });
  }
  // Dedup at ~375m grid: keep highest-FRP detection per pixel
  const grid = new Map();
  for (const p of pts) {
    const key = `${Math.round(p.lat * 267)},${Math.round(p.lon * 267)}`;
    if (!grid.has(key) || p.frp > grid.get(key).frp) grid.set(key, p);
  }
  firmsCache = Array.from(grid.values());
  return firmsCache;
}

async function buildFirmsMarkerLayer() {
  const pts = await loadFirmsData();
  return new FirmsCanvasLayer(pts);
}

function firmsPopupHtml(p) {
  const satLabel = { N: 'S-NPP', N20: 'NOAA-20', N21: 'NOAA-21' };
  const ageStr = p.ageHrs < 1
    ? `${Math.round(p.ageHrs * 60)} min`
    : `${p.ageHrs.toFixed(1)} hr`;
  return (
    `<b>FIRMS VIIRS — ${satLabel[p.sat] || p.sat}</b><br>` +
    `<table style="font-size:11px;border-collapse:collapse;margin:3px 0">` +
    `<tr><td style="color:#aaa;padding-right:8px">FRP</td><td><b>${p.frp.toFixed(0)} MW</b></td></tr>` +
    `<tr><td style="color:#aaa;padding-right:8px">Age</td><td>${ageStr} ago</td></tr>` +
    `<tr><td style="color:#aaa;padding-right:8px">Confidence</td><td>${p.conf || '—'}</td></tr>` +
    `<tr><td style="color:#aaa;padding-right:8px">Detected</td><td>${p.dt.toUTCString()}</td></tr>` +
    `</table>`
  );
}

async function toggleFirms() {
  firmsOn = !firmsOn;
  const btn = document.getElementById('b-firms');
  btn.classList.toggle('on', firmsOn);
  if (firmsOn) {
    if (!firmsMarkerLayer) {
      const fs = document.getElementById('firms-status');
      if (fs) fs.textContent = '...';
      firmsMarkerLayer = await buildFirmsMarkerLayer();
      if (fs) fs.textContent = '';
    }
    firmsMarkerLayer.addTo(map);
  } else {
    if (firmsMarkerLayer) map.removeLayer(firmsMarkerLayer);
  }
}

// ── AlertWest fire cameras (CA, NV, OR, WA, UT, ID, MT, WY, NM…) ───────────
const AW_API       = 'https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc';
const AW_CDN       = 'https://img.cdn.prod.alertwest.com/data/img';
const WEST_STATES  = new Set(['CA','NV','OR','WA','UT','ID','MT','WY','CO','AZ','NM','AK']);

let awData = null, awLayer = null, awOn = false;
const awMarkers = {};  // camId → {marker, cam}

function azimuthToCompass(deg) {
  const dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
  return dirs[Math.round(((parseFloat(deg) % 360) + 360) % 360 / 22.5) % 16];
}

async function loadAlertWest() {
  if (awData) return awData;
  const j = await fetch(AW_API).then(r => r.json());
  const locMap = {};
  for (const loc of j.data.locs.data) {
    if (loc.lat && loc.lon && WEST_STATES.has(loc.st))
      locMap[loc.id] = { lat: parseFloat(loc.lat), lon: parseFloat(loc.lon), st: loc.st };
  }
  awData = [];
  for (const cam of j.data.cams.data) {
    const loc = locMap[cam.lid];
    if (!loc || !cam.img || cam.off === 1) continue;
    const epochMatch = cam.img.match(/_(\d{10})_/);
    if (!epochMatch) continue;
    const d  = new Date(parseInt(epochMatch[1]) * 1000);
    const yy = d.getUTCFullYear();
    const mo = String(d.getUTCMonth()+1).padStart(2,'0');
    const dy = String(d.getUTCDate()).padStart(2,'0');
    awData.push({
      id: cam.id, lat: loc.lat, lon: loc.lon, st: loc.st,
      name: cam.cn || '',
      azimuth:   cam.p   != null ? parseFloat(cam.p).toFixed(1)   : null,
      elevation: cam.t   != null ? parseFloat(cam.t).toFixed(1)   : null,
      zoom:      cam.z   != null ? cam.z                           : null,
      focus:     cam.foc != null ? cam.foc                         : null,
      autoFocus: cam.af  === 1,
      fov:       cam.fov != null ? parseFloat(cam.fov).toFixed(1) : null,
      hasPTZ:    cam.ptz === 1,
      imgUrl: `${AW_CDN}/${cam.id}/${yy}/${mo}/${dy}/${cam.img}`, ts: d,
    });
  }
  return awData;
}

const awNormalIcon = L.divIcon({ className:'cam-icon',      html:'📷', iconSize:[18,18], iconAnchor:[9,9] });
const awFireIcon   = L.divIcon({ className:'cam-fire-icon', html:'<div class="cam-fire-ring">🔥</div>', iconSize:[24,24], iconAnchor:[12,12] });

function _drawSmokeBoxes(cv, img, boxes) {
  const w = img.offsetWidth, h = img.offsetHeight;
  if (!w || !h || !boxes || !boxes.length) return;
  cv.width = w; cv.height = h;
  cv.style.width = w + 'px'; cv.style.height = h + 'px';
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, w, h);
  for (const b of boxes) {
    const x = b.x1*w, y = b.y1*h, bw = (b.x2-b.x1)*w, bh = (b.y2-b.y1)*h;
    ctx.fillStyle = 'rgba(255,102,0,0.15)';
    ctx.fillRect(x, y, bw, bh);
    ctx.strokeStyle = '#ff6600';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, bw, bh);
    ctx.fillStyle = '#ff6600';
    ctx.fillRect(x, y, 32, 15);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 10px monospace';
    ctx.fillText(`${(b.conf*100).toFixed(0)}%`, x + 3, y + 11);
  }
}

async function buildAWLayer() {
  const cams = await loadAlertWest();
  const cluster = L.markerClusterGroup({ maxClusterRadius: 60, disableClusteringAtZoom: 12 });
  for (const c of cams) {
    const m = L.marker([c.lat, c.lon], { icon: awNormalIcon });
    const azStr  = c.azimuth   != null ? `${c.azimuth}° (${azimuthToCompass(c.azimuth)})` : '—';
    const elvStr = c.elevation != null ? `${c.elevation}°` : '—';
    const zoomStr = c.zoom     != null ? c.zoom            : '—';
    const focStr = c.focus     != null
      ? (c.autoFocus ? `${c.focus} (auto)` : `${c.focus} (manual)`) : '—';
    const fovStr = c.fov       != null ? `${c.fov}°`       : '—';
    m.bindPopup(
      `<b>${c.name || 'AlertWest'} — ${c.st}</b><br>` +
      `<small>${c.ts.toUTCString()}</small><br>` +
      `<table style="font-size:11px;border-collapse:collapse;margin:4px 0">` +
      `<tr><td style="color:#aaa;padding-right:6px">Azimuth</td><td>${azStr}</td>` +
      `    <td style="color:#aaa;padding:0 6px">Elevation</td><td>${elvStr}</td></tr>` +
      `<tr><td style="color:#aaa;padding-right:6px">Zoom</td><td>${zoomStr}</td>` +
      `    <td style="color:#aaa;padding:0 6px">Focus</td><td>${focStr}</td></tr>` +
      `<tr><td style="color:#aaa;padding-right:6px">FOV</td><td>${fovStr}</td>` +
      `    <td style="color:#aaa;padding:0 6px">PTZ</td><td>${c.hasPTZ ? 'yes' : 'no'}</td></tr>` +
      `</table>` +
      `<img src="${c.imgUrl}" style="width:260px;display:block" ` +
      `onerror="this.style.display='none'">`,
      { maxWidth:300 }
    );
    awMarkers[c.id] = { marker: m, cam: c };
    cluster.addLayer(m);
  }
  // Kick off AI smoke scan in background after markers are visible
  setTimeout(() => scanCamsWithAI(cams), 300);
  return cluster;
}

async function toggleFireCams() {
  awOn = !awOn;
  const btn = document.getElementById('b-fcam');
  btn.classList.toggle('on', awOn);
  if (awOn) {
    if (!awLayer) {
      const fs = document.getElementById('fcam-status');
      if (fs) fs.textContent = '...';
      awLayer = await buildAWLayer();
      if (fs) fs.textContent = '';
    }
    awLayer.addTo(map);
  } else {
    if (awLayer) map.removeLayer(awLayer);
  }
}

// Scan all AlertWest cameras with YOLOv8 smoke model via local /api/cam-scan.
// Batches 100 at a time; markers with detections switch to 🔥 pulsing icon.
async function scanCamsWithAI(cams) {
  const BATCH = 100;
  for (let i = 0; i < cams.length; i += BATCH) {
    const batch = cams.slice(i, i + BATCH).map(c => ({ id: c.id, imgUrl: c.imgUrl }));
    try {
      const resp = await fetch('/api/cam-scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cameras: batch })
      });
      if (!resp.ok) continue;
      const detections = await resp.json();
      for (const det of detections) {
        const entry = awMarkers[det.id];
        if (!entry) continue;
        entry.detected = true;
        entry.boxes   = det.boxes || [];
        entry.marker.setIcon(awFireIcon);
        const c = entry.cam;
        entry.marker.setPopupContent(
          `<b style="color:#ff6600">&#128293; SMOKE DETECTED — ${c.st}</b><br>` +
          `Confidence: <b>${(det.conf * 100).toFixed(0)}%</b><br>` +
          `<small>${c.ts.toUTCString()}</small><br>` +
          `<table style="font-size:11px;border-collapse:collapse;margin:4px 0">` +
          `<tr><td style="color:#aaa;padding-right:6px">Camera</td><td>${c.name || c.id}</td></tr>` +
          `</table>` +
          `<div style="position:relative;display:inline-block;width:260px">` +
          `<img id="si-${c.id}" src="${c.imgUrl}" style="width:260px;display:block" onerror="this.style.display='none'">` +
          `<canvas id="sc-${c.id}" style="position:absolute;top:0;left:0;pointer-events:none"></canvas>` +
          `</div>`
        );
        entry.marker.off('popupopen.bbox');
        entry.marker.on('popupopen.bbox', () => {
          const img = document.getElementById('si-' + c.id);
          const cv  = document.getElementById('sc-' + c.id);
          if (!img || !cv) return;
          const draw = () => _drawSmokeBoxes(cv, img, entry.boxes);
          if (img.complete && img.naturalHeight > 0) draw();
          else img.addEventListener('load', draw, { once: true });
        });
      }
      applyFireFilter();
    } catch(e) { /* batch failed — server may not have ultralytics/onnxruntime installed */ }
    if (i + BATCH < cams.length) await new Promise(r => setTimeout(r, 400));
  }
}

let fireOnly = false;
function toggleFireOnly() {
  fireOnly = !fireOnly;
  document.getElementById('b-fonly').classList.toggle('on', fireOnly);
  applyFireFilter();
}
function applyFireFilter() {
  if (!awLayer) return;
  for (const entry of Object.values(awMarkers)) {
    if (fireOnly && !entry.detected) {
      if (awLayer.hasLayer(entry.marker)) awLayer.removeLayer(entry.marker);
    } else {
      if (!awLayer.hasLayer(entry.marker)) awLayer.addLayer(entry.marker);
    }
  }
}

// ── Caltrans highway cameras (CA only, evac routes) ───────────────────────────
let ctLayer = null, ctOn = false;

async function buildCaltransLayer() {
  const icon = L.divIcon({ className:'cam-icon', html:'🚦', iconSize:[18,18], iconAnchor:[9,9] });
  const results = await Promise.all([1,2,3,4,5,6,7,8,9,10,11,12].map(d =>
    fetch(`https://cwwp2.dot.ca.gov/data/d${d}/cctv/cctvStatusD0${d}.json`)
      .then(r => r.json()).catch(() => ({data:[]}))
  ));
  const markers = [];
  for (const res of results) {
    for (const item of (res.data || [])) {
      const c = item.cctv;
      if (!c || c.inService !== 'true') continue;
      const lat = parseFloat(c.location?.latitude);
      const lon = parseFloat(c.location?.longitude);
      if (!lat || !lon) continue;
      const imgUrl = c.imageData?.static?.currentImageURL;
      const name      = c.location?.locationName || '';
      const route     = c.location?.route || '';
      const direction = c.location?.direction || '';
      const elevation = c.location?.elevation ? `${c.location.elevation} ft` : '';
      const m = L.marker([lat, lon], { icon });
      m.bindPopup(
        `<b>${name}</b> <small>${route}</small><br>` +
        `<table style="font-size:11px;border-collapse:collapse;margin:4px 0">` +
        `<tr><td style="color:#aaa;padding-right:6px">Facing</td><td>${direction || '—'}</td>` +
        `    <td style="color:#aaa;padding:0 6px">Elevation</td><td>${elevation || '—'}</td></tr>` +
        `<tr><td style="color:#aaa;padding-right:6px">Zoom</td><td>—</td>` +
        `    <td style="color:#aaa;padding:0 6px">Focus</td><td>—</td></tr>` +
        `</table>` +
        (imgUrl ? `<img src="${imgUrl}" style="width:260px" onerror="this.style.display='none'">` : 'No image'),
        { maxWidth:300 }
      );
      markers.push(m);
    }
  }
  const cluster = L.markerClusterGroup({ maxClusterRadius: 60, disableClusteringAtZoom: 12 });
  cluster.addLayers(markers);
  return cluster;
}

async function toggleTrafficCams() {
  ctOn = !ctOn;
  const btn = document.getElementById('b-tcam');
  btn.classList.toggle('on', ctOn);
  if (ctOn) {
    if (!ctLayer) {
      const ts = document.getElementById('tcam-status');
      if (ts) ts.textContent = '...';
      ctLayer = await buildCaltransLayer();
      if (ts) ts.textContent = '';
    }
    ctLayer.addTo(map);
  } else {
    if (ctLayer) map.removeLayer(ctLayer);
  }
}

// ── Weather layers (Wind + Temperature) ──────────────────────────────────────
let windOn = false, tempOn = false, rhOn = false, stationsOn = false;
let velocityLayer = null, tempCanvasLayer = null, rhLayer = null, stationLayer = null;
const wxCache = {};  // "YYYY-MM-DDTHH" → Promise<payload>

function tempToRgb(t, tmin, tmax) {
  const n = Math.max(0, Math.min(1, (t - tmin) / (tmax - tmin || 1)));
  const stops = [[0,0,255],[0,200,255],[255,220,0],[255,40,0]];
  const pos = n * (stops.length - 1);
  const i = Math.min(Math.floor(pos), stops.length - 2);
  const f = pos - i;
  return stops[i].map((c, j) => Math.round(c + f * (stops[i+1][j] - c)));
}

const TempLayer = L.Layer.extend({
  onAdd(map) {
    this._map = map;
    this._canvas = L.DomUtil.create('canvas');
    this._canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;opacity:0.6';
    map.getPanes().overlayPane.appendChild(this._canvas);
    map.on('moveend zoomend resize', this._redraw, this);
    if (this._payload) this._redraw();
  },
  onRemove(map) {
    map.getPanes().overlayPane.removeChild(this._canvas);
    map.off('moveend zoomend resize', this._redraw, this);
  },
  setData(payload) {
    this._payload = payload;
    if (this._map) this._redraw();
  },
  _redraw() {
    if (!this._payload) return;
    const { lats, lons, temp } = this._payload;
    const map = this._map;
    const size = map.getSize();
    const c = this._canvas;
    c.width = size.x; c.height = size.y;
    const ctx = c.getContext('2d');
    const nx = lons.length, ny = lats.length;
    const valid = temp.filter(v => v != null);
    if (!valid.length) return;
    const tmin = Math.min(...valid), tmax = Math.max(...valid);
    const imgData = ctx.createImageData(size.x, size.y);
    const d = imgData.data;
    for (let py = 0; py < size.y; py++) {
      for (let px = 0; px < size.x; px++) {
        const ll = map.containerPointToLatLng([px, py]);
        const lat = ll.lat, lon = ll.lng;
        if (lat < lats[ny-1] || lat > lats[0] || lon < lons[0] || lon > lons[nx-1]) continue;
        const dx = nx > 1 ? lons[1]-lons[0] : 2.5, dy = ny > 1 ? lats[0]-lats[1] : 2.5;
        const ci = Math.min(Math.floor((lon - lons[0]) / dx), nx-2);
        const ri = Math.min(Math.floor((lats[0] - lat) / dy), ny-2);
        const fx = (lon - lons[ci]) / dx;
        const fy = (lats[ri] - lat) / dy;
        const i00=ri*nx+ci, i01=ri*nx+ci+1, i10=(ri+1)*nx+ci, i11=(ri+1)*nx+ci+1;
        const v00=temp[i00], v01=temp[i01], v10=temp[i10], v11=temp[i11];
        if (v00==null||v01==null||v10==null||v11==null) continue;
        const t = v00*(1-fx)*(1-fy) + v01*fx*(1-fy) + v10*(1-fx)*fy + v11*fx*fy;
        const [r, g, b] = tempToRgb(t, tmin, tmax);
        const idx = (py*size.x + px)*4;
        d[idx]=r; d[idx+1]=g; d[idx+2]=b; d[idx+3]=150;
      }
    }
    ctx.putImageData(imgData, 0, 0);
    L.DomUtil.setPosition(c, map.containerPointToLayerPoint([0,0]));
  }
});

function wxHour(frameIdx) {
  const t = FRAMES[frameIdx].time;  // "YYYY-MM-DD HH:MM"
  return t.replace(' ', 'T').slice(0, 13);  // "YYYY-MM-DDTHH"
}

async function fetchWeather(frameIdx) {
  const hr = wxHour(frameIdx);
  if (!wxCache[hr]) {
    wxCache[hr] = fetch(`/api/weather?dt=${hr}`).then(r => {
      if (!r.ok) throw new Error(`weather ${r.status}`);
      return r.json();
    });
  }
  return wxCache[hr];
}

function prefetchWeather(frameIdx) {
  // Kick off fetches for surrounding hours so timeline scrubbing hits cache
  const offsets = [-6, -3, 3, 6];  // ±1-2 hours in 10-min steps
  for (const off of offsets) {
    const i = Math.max(0, Math.min(FRAMES.length - 1, frameIdx + off));
    const hr = wxHour(i);
    if (!wxCache[hr]) {
      wxCache[hr] = fetch(`/api/weather?dt=${hr}`).then(r => {
        if (!r.ok) throw new Error(`weather ${r.status}`);
        return r.json();
      }).catch(() => null);
    }
  }
}

async function updateWeatherLayers(frameIdx) {
  if (!windOn && !tempOn && !rhOn && !stationsOn) return;
  let payload;
  try {
    payload = await fetchWeather(frameIdx);
    if (!payload) return;  // prefetch error stored as null
  } catch(e) { return; }
  prefetchWeather(frameIdx);  // warm adjacent hours in background

  if (windOn) {
    if (!velocityLayer) {
      velocityLayer = L.velocityLayer({
        displayValues: true,
        displayOptions: { velocityType: 'Wind', position: 'bottomleft', emptyString: 'No wind data' },
        data: payload.wind,
        maxVelocity: 20,
        colorScale: ['#b0c4d0','#60a0c0','#2070b0','#0040a0'],
        particleMultiplier: 0.003,
        lineWidth: 1.5,
        frameRate: 16,
      }).addTo(map);
    } else {
      velocityLayer.setData(payload.wind);
    }
  }
  if (tempOn) {
    if (!tempCanvasLayer) tempCanvasLayer = new TempLayer().addTo(map);
    tempCanvasLayer.setData(payload);
  }
  if (rhOn) {
    if (!rhLayer) rhLayer = new RHLayer().addTo(map);
    rhLayer.setData(payload);
  }
  if (stationsOn) {
    if (stationLayer) map.removeLayer(stationLayer);
    stationLayer = buildStationLayer(payload).addTo(map);
  }
}

function toggleWind() {
  windOn = !windOn;
  document.getElementById('b-wind').classList.toggle('on', windOn);
  if (!windOn && velocityLayer) { map.removeLayer(velocityLayer); velocityLayer = null; }
  else if (windOn) updateWeatherLayers(cur);
}

function toggleTemp() {
  tempOn = !tempOn;
  document.getElementById('b-temp').classList.toggle('on', tempOn);
  if (!tempOn && tempCanvasLayer) { map.removeLayer(tempCanvasLayer); tempCanvasLayer = null; }
  else if (tempOn) updateWeatherLayers(cur);
}

// ── RH (Humidity) canvas layer ────────────────────────────────────────────────
function rhToRgb(rh) {
  // red (dry/dangerous) → yellow → green → blue (moist/safe)
  const n = Math.max(0, Math.min(1, rh / 100));
  const stops = [[220,40,0],[255,180,0],[100,200,50],[0,120,220]];
  const pos = n * (stops.length - 1);
  const i = Math.min(Math.floor(pos), stops.length - 2);
  const f = pos - i;
  return stops[i].map((c, j) => Math.round(c + f * (stops[i+1][j] - c)));
}

const RHLayer = L.Layer.extend({
  onAdd(map) {
    this._map = map;
    this._canvas = L.DomUtil.create('canvas');
    this._canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;opacity:0.55';
    map.getPanes().overlayPane.appendChild(this._canvas);
    map.on('moveend zoomend resize', this._redraw, this);
    if (this._payload) this._redraw();
  },
  onRemove(map) {
    map.getPanes().overlayPane.removeChild(this._canvas);
    map.off('moveend zoomend resize', this._redraw, this);
  },
  setData(payload) { this._payload = payload; if (this._map) this._redraw(); },
  _redraw() {
    if (!this._payload) return;
    const { lats, lons, rh } = this._payload;
    const map = this._map, size = map.getSize();
    const c = this._canvas; c.width = size.x; c.height = size.y;
    const ctx = c.getContext('2d'), nx = lons.length, ny = lats.length;
    const valid = rh.filter(v => v != null);
    if (!valid.length) return;
    const imgData = ctx.createImageData(size.x, size.y);
    const d = imgData.data;
    const dx = nx > 1 ? lons[1]-lons[0] : 1.0, dy = ny > 1 ? lats[0]-lats[1] : 1.0;
    for (let py = 0; py < size.y; py++) {
      for (let px = 0; px < size.x; px++) {
        const ll = map.containerPointToLatLng([px, py]);
        const lat = ll.lat, lon = ll.lng;
        if (lat < lats[ny-1] || lat > lats[0] || lon < lons[0] || lon > lons[nx-1]) continue;
        const ci = Math.min(Math.floor((lon - lons[0]) / dx), nx-2);
        const ri = Math.min(Math.floor((lats[0] - lat) / dy), ny-2);
        const fx = (lon - lons[ci]) / dx, fy = (lats[ri] - lat) / dy;
        const v00=rh[ri*nx+ci], v01=rh[ri*nx+ci+1], v10=rh[(ri+1)*nx+ci], v11=rh[(ri+1)*nx+ci+1];
        if (v00==null||v01==null||v10==null||v11==null) continue;
        const val = v00*(1-fx)*(1-fy)+v01*fx*(1-fy)+v10*(1-fx)*fy+v11*fx*fy;
        const [r, g, b] = rhToRgb(val);
        const idx = (py*size.x+px)*4;
        d[idx]=r; d[idx+1]=g; d[idx+2]=b; d[idx+3]=140;
      }
    }
    ctx.putImageData(imgData, 0, 0);
    L.DomUtil.setPosition(c, map.containerPointToLayerPoint([0,0]));
  }
});

function toggleHumidity() {
  rhOn = !rhOn;
  document.getElementById('b-rh').classList.toggle('on', rhOn);
  if (!rhOn && rhLayer) { map.removeLayer(rhLayer); rhLayer = null; }
  else if (rhOn) updateWeatherLayers(cur);
}

// ── METAR station markers ─────────────────────────────────────────────────────
function buildStationLayer(payload) {
  const { stations, temp } = payload;
  if (!stations || !stations.length) return L.layerGroup([]);
  const valid = temp.filter(v => v != null);
  const tmin = valid.length ? Math.min(...valid) : 0;
  const tmax = valid.length ? Math.max(...valid) : 40;
  const markers = stations.map(s => {
    const [r, g, b] = tempToRgb(s.temp, tmin, tmax);
    const color = `rgb(${r},${g},${b})`;
    const m = L.circleMarker([s.lat, s.lon], {
      radius: 4, color: '#07101a', weight: 1,
      fillColor: color, fillOpacity: 0.9, pane: 'overlayPane'
    });
    const spd = Math.sqrt(s.u*s.u + s.v*s.v);
    const mph = (spd*2.237).toFixed(1);
    const wdDeg = Math.round((Math.atan2(-s.u,-s.v)*180/Math.PI+360)%360);
    const dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
    const dir = dirs[Math.round(wdDeg/22.5)%16];
    const gustLine = s.gust ? `<div style="display:flex;justify-content:space-between;margin:2px 0"><span style="color:#607880">Gust</span><span>${(s.gust*2.237).toFixed(1)} mph</span></div>` : '';
    const rhLine = s.rh != null ? `<div style="display:flex;justify-content:space-between;margin:2px 0"><span style="color:#607880">Humidity</span><span>${s.rh}%</span></div>` : '';
    m.bindPopup(`
      <div style="font-family:Consolas,monospace;font-size:12px;color:#b0c4d0;background:#07101a;padding:6px 10px;min-width:190px">
        <div style="color:#ff7700;font-weight:bold;margin-bottom:6px;border-bottom:1px solid #0f2030;padding-bottom:4px">${s.id}${s.network ? ' · '+s.network : ''}</div>
        <div style="display:flex;justify-content:space-between;margin:2px 0"><span style="color:#607880">Temperature</span><span>${(s.temp*9/5+32).toFixed(1)}°F <span style="color:#607880">${s.temp}°C</span></span></div>
        ${rhLine}
        <div style="display:flex;justify-content:space-between;margin:2px 0"><span style="color:#607880">Wind</span><span>${mph} mph from ${dir}</span></div>
        ${gustLine}
        <div style="color:#304050;font-size:10px;margin-top:6px">${s.lat.toFixed(2)}°N ${Math.abs(s.lon).toFixed(2)}°W · observed</div>
      </div>`, { maxWidth: 240 });
    return m;
  });
  return L.layerGroup(markers);
}

function toggleStations() {
  stationsOn = !stationsOn;
  document.getElementById('b-stations').classList.toggle('on', stationsOn);
  if (!stationsOn) { if (stationLayer) { map.removeLayer(stationLayer); stationLayer = null; } return; }
  fetchWeather(cur).then(payload => {
    if (stationLayer) map.removeLayer(stationLayer);
    stationLayer = buildStationLayer(payload).addTo(map);
  }).catch(() => {});
}

// ── NWS Fire Weather Alerts ───────────────────────────────────────────────────
let fireAlertsOn = false, fireAlertsLayer = null;
let fireZonesOn  = false, fireZonesLayer  = null;
const zoneFcCache = {};  // zoneId → forecast JSON

const ALERT_COLORS = {
  'Red Flag Warning':      { color: '#cc1100', fill: '#ff2200' },
  'Extreme Fire Behavior': { color: '#880000', fill: '#cc0000' },
  'Fire Weather Watch':    { color: '#cc6600', fill: '#ff8800' },
  'Fire Weather Advisory': { color: '#998800', fill: '#ddaa00' },
  'Blowing Dust Advisory': { color: '#776655', fill: '#aa9966' },
};

async function toggleFireAlerts() {
  fireAlertsOn = !fireAlertsOn;
  document.getElementById('b-falerts').classList.toggle('on', fireAlertsOn);
  if (!fireAlertsOn) {
    if (fireAlertsLayer) { map.removeLayer(fireAlertsLayer); fireAlertsLayer = null; }
    return;
  }
  try {
    const data = await fetch('/api/fire-alerts').then(r => r.json());
    if (fireAlertsLayer) map.removeLayer(fireAlertsLayer);
    const count = data.features ? data.features.length : 0;
    const st = document.getElementById('falerts-status');
    if (st) st.textContent = count ? `${count}` : '';
    fireAlertsLayer = L.geoJSON(data, {
      style: f => {
        const c = ALERT_COLORS[f.properties.event] || { color: '#aa8800', fill: '#ddaa00' };
        return { color: c.color, fillColor: c.fill, fillOpacity: 0.2, weight: 2, dashArray: '4 3' };
      },
      onEachFeature: (f, layer) => {
        const p = f.properties;
        const exp = p.expires ? new Date(p.expires).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—';
        const c = ALERT_COLORS[p.event] || { color: '#cc8800' };
        layer.bindPopup(`
          <div style="font-family:Consolas,monospace;font-size:12px;color:#b0c4d0;background:#07101a;padding:6px 10px;max-width:290px">
            <div style="color:${c.fill || '#ff8800'};font-weight:bold;margin-bottom:4px;border-bottom:1px solid #0f2030;padding-bottom:4px">${p.event}</div>
            <div style="color:#8090a0;font-size:11px;margin-bottom:4px">${p.areaDesc || ''}</div>
            <div style="font-size:11px;margin-bottom:6px">${p.headline || ''}</div>
            <div style="color:#405060;font-size:10px">Expires ${exp}</div>
          </div>`, { maxWidth: 310 });
      }
    }).addTo(map);
  } catch(e) { console.warn('Fire alerts fetch failed', e); }
}

async function toggleFireZones() {
  fireZonesOn = !fireZonesOn;
  document.getElementById('b-fzones').classList.toggle('on', fireZonesOn);
  if (!fireZonesOn) {
    if (fireZonesLayer) { map.removeLayer(fireZonesLayer); fireZonesLayer = null; }
    return;
  }
  try {
    const data = await fetch('/api/fire-zones').then(r => r.json());
    fireZonesLayer = L.geoJSON(data, {
      style: { color: '#8866bb', fillColor: '#6644aa', fillOpacity: 0.07, weight: 1, dashArray: '3 5' },
      onEachFeature: (feat, layer) => {
        const p = feat.properties || {};
        const rawId = p.id || (p['@id'] || '').split('/').pop() || '';
        const zoneId = rawId.replace(/^.*\//, '');  // strip URL prefix if present
        const zoneName = p.name || zoneId;
        const state    = p.state || '';
        layer.on('click', async function(e) {
          L.DomEvent.stopPropagation(e);
          const baseHtml = `<div style="font-family:Consolas,monospace;font-size:12px;color:#b0c4d0;background:#07101a;padding:6px 10px;max-width:310px">
            <div style="color:#9977cc;font-weight:bold;border-bottom:1px solid #0f2030;padding-bottom:4px;margin-bottom:5px">${zoneName}${state ? ' — '+state : ''}</div>`;
          const popup = L.popup({ maxWidth: 330 }).setLatLng(e.latlng)
            .setContent(baseHtml + '<div style="color:#304050;font-size:11px">Loading forecast…</div></div>')
            .openOn(map);
          if (!zoneId) return;
          try {
            if (!zoneFcCache[zoneId]) {
              const fc = await fetch(`/api/fire-zone-forecast?zone=${zoneId}`).then(r => r.json());
              zoneFcCache[zoneId] = fc;
            }
            const periods = (zoneFcCache[zoneId].properties || {}).periods || [];
            const isHistorical = wxHour(cur) < wxHour(FRAMES.length - 1).slice(0, 10);
            if (!periods.length || isHistorical) {
              popup.setContent(baseHtml + `<div style="color:#304050;font-size:11px">${isHistorical ? 'Forecast not available for historical dates' : 'No forecast available'}</div></div>`);
              return;
            }
            const rows = periods.slice(0, 3).map(pd =>
              `<div style="margin:5px 0">
                <div style="color:#9977cc;font-size:11px;margin-bottom:2px">${pd.name}</div>
                <div style="color:#8090a0;font-size:11px;line-height:1.4">${pd.detailedForecast}</div>
              </div>`
            ).join('<hr style="border-color:#0f2030;margin:4px 0">');
            popup.setContent(baseHtml + rows + '</div>');
          } catch(_) {
            popup.setContent(baseHtml + '<div style="color:#304050;font-size:11px">Forecast unavailable</div></div>');
          }
        });
        layer.bindTooltip(zoneName, { sticky: true, className: 'ftip', opacity: 0.85 });
      }
    }).addTo(map);
  } catch(e) { console.warn('Fire zones fetch failed', e); }
}

// ── Weather popup on map click ────────────────────────────────────────────────
map.on('click', async function(e) {
  const tgt = e.originalEvent.target;
  if (tgt.closest && tgt.closest('.leaflet-marker-icon,.leaflet-popup-content-wrapper,.leaflet-control')) return;

  // FIRMS hotspot click — check before weather popup
  if (firmsOn && firmsMarkerLayer) {
    const hit = firmsMarkerLayer.findNearest(e.latlng);
    if (hit) {
      L.popup({ maxWidth: 260 })
        .setLatLng([hit.lat, hit.lon])
        .setContent(firmsPopupHtml(hit))
        .openOn(map);
      return;
    }
  }

  const lat = e.latlng.lat, lon = e.latlng.lng;
  const popup = L.popup({ maxWidth: 240, className: 'wx-popup' })
    .setLatLng(e.latlng)
    .setContent('<div style="font-family:Consolas,monospace;font-size:12px;color:#b0c4d0;background:#07101a;padding:6px 8px">Loading weather…</div>')
    .openOn(map);

  let payload;
  try { payload = await fetchWeather(cur); } catch(_) {
    popup.setContent('<div style="font-family:Consolas,monospace;font-size:12px;color:#b0c4d0;background:#07101a;padding:6px 8px">Weather unavailable</div>');
    return;
  }

  const { lats, lons, temp, wind, rh: rhArr } = payload;
  const nx = lons.length, ny = lats.length;
  if (lat < lats[ny-1] || lat > lats[0] || lon < lons[0] || lon > lons[nx-1]) {
    popup.setContent('<div style="font-family:Consolas,monospace;font-size:12px;color:#b0c4d0;background:#07101a;padding:6px 8px">Outside CONUS grid</div>');
    return;
  }

  const dx = nx > 1 ? lons[1]-lons[0] : 1.0, dy = ny > 1 ? lats[0]-lats[1] : 1.0;
  const ci = Math.min(Math.floor((lon - lons[0]) / dx), nx-2);
  const ri = Math.min(Math.floor((lats[0] - lat) / dy), ny-2);
  const fx = (lon - lons[ci]) / dx;
  const fy = (lats[ri] - lat) / dy;

  function bilinear(arr) {
    const v00=arr[ri*nx+ci], v01=arr[ri*nx+ci+1], v10=arr[(ri+1)*nx+ci], v11=arr[(ri+1)*nx+ci+1];
    if (v00==null||v01==null||v10==null||v11==null) return null;
    return v00*(1-fx)*(1-fy) + v01*fx*(1-fy) + v10*(1-fx)*fy + v11*fx*fy;
  }

  const t   = bilinear(temp);
  const u   = bilinear(wind[0].data);
  const v2  = bilinear(wind[1].data);
  const rhi = rhArr ? bilinear(rhArr) : null;

  const tempF = t != null ? (t*9/5+32).toFixed(1)+'°F' : '—';
  const tempC = t != null ? t.toFixed(1)+'°C' : '';
  const rhLine = rhi != null ? `<div style="display:flex;justify-content:space-between;gap:12px;margin:3px 0"><span style="color:#607880">Humidity</span><span>${Math.round(rhi)}%</span></div>` : '';

  let windLine = '—';
  if (u != null && v2 != null) {
    const spd = Math.sqrt(u*u + v2*v2);
    const mph = (spd*2.237).toFixed(1);
    const wdDeg = (Math.atan2(-u,-v2)*180/Math.PI+360)%360;
    const dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
    const dir = dirs[Math.round(wdDeg/22.5)%16];
    windLine = `${mph} mph &middot; from ${dir} (${Math.round(wdDeg)}&deg;)`;
  }

  const hr = wxHour(cur).replace('T',' ');
  popup.setContent(`
    <div style="font-family:Consolas,monospace;font-size:12px;color:#b0c4d0;background:#07101a;padding:6px 10px;min-width:190px">
      <div style="color:#ff7700;font-weight:bold;margin-bottom:6px;border-bottom:1px solid #0f2030;padding-bottom:4px">Weather &middot; ${hr}Z</div>
      <div style="display:flex;justify-content:space-between;gap:12px;margin:3px 0">
        <span style="color:#607880">Temperature</span>
        <span>${tempF} <span style="color:#607880">${tempC}</span></span>
      </div>
      ${rhLine}
      <div style="display:flex;justify-content:space-between;gap:12px;margin:3px 0">
        <span style="color:#607880">Wind</span>
        <span style="text-align:right">${windLine}</span>
      </div>
      <div style="color:#304050;font-size:10px;margin-top:6px">${lat.toFixed(2)}&deg;N ${Math.abs(lon).toFixed(2)}&deg;W &middot; ${payload.src || 'METAR+HRRR 1°'}</div>
    </div>
  `);
});

map.on('zoomend moveend', () => syncRadarToFrame(cur));

// ── Frame control ─────────────────────────────────────────────────────────────
let cur = FRAMES.length - 1;

function showFrame(idx) {
  cur = Math.max(0, Math.min(idx, FRAMES.length - 1));
  slider.value = cur;

  const isLatest = (cur === FRAMES.length - 1);
  const dot = isLatest ? '<span class="live-dot"></span>' : '';
  document.getElementById('tlbl').innerHTML = dot + FRAMES[cur].time + ' UTC';

  applyBg(cur);
  syncRadarToFrame(cur);
  loadNGFSFrame(cur);
  prefetchNGFS(cur);
  updateWeatherLayers(cur);
}

const slider = document.getElementById('slider');
slider.max = FRAMES.length - 1;

let scrubTimer = null;
slider.addEventListener('input', e => {
  if (playing) pause();
  cur = Math.max(0, Math.min(+e.target.value, FRAMES.length - 1));
  // Update label instantly for feedback while scrubbing
  const isLatest = (cur === FRAMES.length - 1);
  const dot = isLatest ? '<span class="live-dot"></span>' : '';
  document.getElementById('tlbl').innerHTML = dot + FRAMES[cur].time + ' UTC';
  // Debounce the expensive layer swap — only fires on the frame you land on
  clearTimeout(scrubTimer);
  scrubTimer = setTimeout(() => showFrame(cur), 150);
});

let playing = false, timer = null, speed = 500;
function play() {
  playing = true;
  document.getElementById('pbtn').innerHTML = '&#9646;&#9646; Pause';
  timer = setInterval(() => showFrame((cur+1) % FRAMES.length), speed);
}
function pause() {
  playing = false;
  document.getElementById('pbtn').innerHTML = '&#9654; Play';
  clearInterval(timer);
}
document.getElementById('pbtn').addEventListener('click', () => playing ? pause() : play());

function setSpeed(ms) {
  speed = ms;
  const spdMap = {2000:'spd-05', 1000:'spd-1', 500:'spd-2', 250:'spd-4'};
  document.querySelectorAll('.spd').forEach(b => b.classList.remove('on'));
  const ab = document.getElementById(spdMap[ms]);
  if (ab) ab.classList.add('on');
  if (playing) { clearInterval(timer); timer = setInterval(() => showFrame((cur+1)%FRAMES.length), speed); }
}

// ── Timeline auto-refresh ─────────────────────────────────────────────────────
// GOES-19 publishes a new 10-min slot roughly every 10 min.
// Check every 5 min: if makeFrames() has new entries, append and auto-advance.
function refreshTimeline() {
  const newF = makeFrames();
  const existTimes = new Set(FRAMES.map(f => f.time));
  let added = 0;
  for (const f of newF) {
    if (!existTimes.has(f.time)) { FRAMES.push(f); added++; }
  }
  if (added === 0) return;
  slider.max = FRAMES.length - 1;
  const wasOnLatest = (cur === FRAMES.length - 1 - added);
  if (wasOnLatest) {
    showFrame(FRAMES.length - 1); // showFrame calls loadNGFSFrame which rebuilds latest
  }
}
setInterval(refreshTimeline, 5 * 60 * 1000);

// Refresh weather every 10 minutes for the current hour when on the latest frame
setInterval(() => {
  if (!windOn && !tempOn && !rhOn && !stationsOn) return;
  if (cur !== FRAMES.length - 1) return;  // only refresh when viewing live
  const hr = wxHour(cur);
  delete wxCache[hr];
  updateWeatherLayers(cur);
}, 10 * 60 * 1000);

showFrame(FRAMES.length - 1); // showFrame → loadNGFSFrame initializes hotspot layer
</script>
</body>
</html>
"""


# ── Server ────────────────────────────────────────────────────────────────────

import http.server
import socketserver
import urllib.request
import urllib.error
import json
import math
import re as _re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PORT = 8080

FIRMS_CSVS = [
    'https://firms.modaps.eosdis.nasa.gov/data/active_fire/'
    'suomi-npp-viirs-c2/USA_contiguous_and_Hawaii/'
    'SUOMI_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv',
    'https://firms.modaps.eosdis.nasa.gov/data/active_fire/'
    'noaa-20-viirs-c2/USA_contiguous_and_Hawaii/'
    'J1_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv',
    'https://firms.modaps.eosdis.nasa.gov/data/active_fire/'
    'noaa-21-viirs-c2/USA_contiguous_and_Hawaii/'
    'J2_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv',
]

# CONUS + AK southern tip bounding box
OPENSKY_URL = (
    'https://opensky-network.org/api/states/all'
    '?lamin=24.5&lamax=49.5&lomin=-124.8&lomax=-66.8'
)

# 1° CONUS weather grid: 61 cols × 27 rows = 1647 points
_WX_LONS = [round(-125 + i, 1) for i in range(61)]
_WX_LATS = [round(50 - i, 1)   for i in range(27)]
_wx_cache    = {}
_wx_cache_ts = {}   # hour_str → unix timestamp of when it was built
_wx_lock     = threading.Lock()
_iem_asos_cache = {}   # "YYYY-MM-DDTHH" → IEM ASOS station list
_iem_asos_lock  = threading.Lock()
_raws_cache     = {}   # "YYYY-MM-DDTHH" → IEM RAWS station list
_raws_lock      = threading.Lock()
_rtma_cache  = {}   # "YYYY-MM-DDTHH" → (u,v,t,rh) grid tuple
_rtma_lock   = threading.Lock()
_fire_zones_cache     = {'data': None, 'ts': 0.0}
_fire_zones_lock      = threading.Lock()
_zone_fc_cache        = {}   # zoneId → (payload_bytes, ts)
_zone_fc_lock         = threading.Lock()

# ── RTMA 2.5km LCC projection constants ───────────────────────────────────────
# NOAA RTMA CONUS grid (GRIB2 Grid 197): tangent Lambert Conformal, 2.5km
_LCC_R    = 6371229.0
_LCC_PHI1 = math.radians(25.0)   # standard parallel
_LCC_LAM0 = math.radians(-95.0)  # central meridian
_LCC_N    = math.sin(_LCC_PHI1)
_LCC_F    = math.cos(_LCC_PHI1) * math.tan(math.pi/4 + _LCC_PHI1/2)**_LCC_N / _LCC_N
_LCC_RHO0 = _LCC_R * _LCC_F / math.tan(math.pi/4 + _LCC_PHI1/2)**_LCC_N
_RTMA_DX  = 2539.703   # m
_RTMA_NJ  = 1377; _RTMA_NI = 2145
_RTMA_LA1 = 20.191999; _RTMA_LO1 = -121.554001  # SW grid corner

def _lcc_fwd(lat_deg, lon_deg):
    phi = math.radians(lat_deg); lam = math.radians(lon_deg)
    rho = _LCC_R * _LCC_F / math.tan(math.pi/4 + phi/2)**_LCC_N
    th  = _LCC_N * (lam - _LCC_LAM0)
    return rho * math.sin(th), _LCC_RHO0 - rho * math.cos(th)

def _lcc_inv(x, y):
    rho = math.copysign(math.sqrt(x*x + (_LCC_RHO0-y)**2), _LCC_N)
    if abs(rho) < 1: return None, None
    th  = math.atan2(x, _LCC_RHO0 - y)
    lat = 2*math.atan((_LCC_R*_LCC_F/rho)**(1/_LCC_N)) - math.pi/2
    lon = th/_LCC_N + _LCC_LAM0
    return math.degrees(lat), math.degrees(lon)

# Pre-compute origin in projection space (SW grid corner)
_RTMA_X0, _RTMA_Y0 = _lcc_fwd(_RTMA_LA1, _RTMA_LO1)


# ── AI camera smoke detection ─────────────────────────────────────────────────
# Loads best.onnx (YOLOv8) from the sibling fpm/ project.
# Tries ultralytics first (simpler), falls back to onnxruntime with manual pre-processing.

_cam_model      = None
_cam_model_lock = threading.Lock()
_CAM_MODEL_PATH = Path(__file__).parent.parent / 'fpm' / 'best.onnx'


def _get_cam_model():
    global _cam_model
    if _cam_model is not None:
        return _cam_model
    with _cam_model_lock:
        if _cam_model is not None:
            return _cam_model
        if not _CAM_MODEL_PATH.exists():
            return None
        try:
            from ultralytics import YOLO
            _cam_model = ('ul', YOLO(str(_CAM_MODEL_PATH)))
        except ImportError:
            try:
                import onnxruntime as ort
                _cam_model = ('ort', ort.InferenceSession(str(_CAM_MODEL_PATH)))
            except ImportError:
                return None
    return _cam_model


def _infer_one(cam):
    """Fetch one camera JPEG, run YOLOv8 inference, return {id, conf, boxes} or None.
    boxes is a list of {x1,y1,x2,y2,conf} with coords normalized 0-1 to the image."""
    try:
        import numpy as np
        req  = urllib.request.Request(cam['imgUrl'],
                                      headers={'User-Agent': 'Mozilla/5.0'})
        data = urllib.request.urlopen(req, timeout=6).read()
        kind_model = _get_cam_model()
        if kind_model is None:
            return None
        kind, model = kind_model
        if kind == 'ul':
            import cv2
            arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            results = model.predict(img, conf=0.40, verbose=False)
            b = results[0].boxes
            if not len(b):
                return None
            xyxyn = b.xyxyn.cpu().numpy()   # normalized 0-1 in original image space
            confs = b.conf.cpu().numpy()
            boxes = [{'x1': float(r[0]), 'y1': float(r[1]),
                      'x2': float(r[2]), 'y2': float(r[3]),
                      'conf': round(float(c), 3)}
                     for r, c in zip(xyxyn, confs)]
            return {'id': cam['id'], 'conf': round(float(confs.max()), 3), 'boxes': boxes}
        elif kind == 'ort':
            import cv2
            arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            img = cv2.resize(img, (640, 640))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = img.astype(np.float32) / 255.0
            img = img.transpose(2, 0, 1)[np.newaxis]
            out  = model.run(None, {model.get_inputs()[0].name: img})[0]
            # out shape: [1, 5, 8400]  — cx,cy,w,h,conf per anchor
            raw_conf = out[0, 4, :]
            mask = raw_conf >= 0.40
            if not mask.any():
                return None
            cx = out[0, 0, mask]; cy = out[0, 1, mask]
            bw = out[0, 2, mask]; bh = out[0, 3, mask]
            cs = raw_conf[mask]
            x1 = np.clip((cx - bw / 2) / 640, 0, 1)
            y1 = np.clip((cy - bh / 2) / 640, 0, 1)
            x2 = np.clip((cx + bw / 2) / 640, 0, 1)
            y2 = np.clip((cy + bh / 2) / 640, 0, 1)
            boxes = sorted(
                [{'x1': float(x1[i]), 'y1': float(y1[i]),
                  'x2': float(x2[i]), 'y2': float(y2[i]),
                  'conf': round(float(cs[i]), 3)}
                 for i in range(len(cs))],
                key=lambda d: d['conf'], reverse=True
            )[:5]
            return {'id': cam['id'], 'conf': round(float(cs.max()), 3), 'boxes': boxes}
    except Exception:
        pass
    return None


def _run_cam_scan(cameras):
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(_infer_one, cameras))
    return [r for r in results if r is not None]


# ── NWS Fire Weather Alerts cache ─────────────────────────────────────────────
import time as _time
_fire_alerts_cache = {'data': None, 'ts': 0.0}
_fire_alerts_lock  = threading.Lock()


# ── Weather: METAR stations + HRRR gap-fill ───────────────────────────────────

def _iem_parse_csv(text, target_epoch):
    """Parse IEM asos.py onlycomma CSV → station dicts, best obs per station within ±60 min."""
    best = {}
    header = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('station,'):
            header = line.split(',')
            continue
        if header is None:
            continue
        row = line.split(',')
        if len(row) < len(header):
            continue

        def _col(name):
            try:
                v = row[header.index(name)].strip()
                return None if v in ('M', 'T', '') else v
            except (ValueError, IndexError):
                return None

        sid     = row[0].strip()
        valid_s = row[1].strip() if len(row) > 1 else ''
        lon_s   = _col('lon');  lat_s  = _col('lat')
        tmpf_s  = _col('tmpf'); dwpf_s = _col('dwpf')
        sknt_s  = _col('sknt'); drct_s = _col('drct')
        gust_s  = _col('gust')

        if not all([sid, valid_s, lon_s, lat_s, tmpf_s, sknt_s, drct_s]):
            continue
        try:
            from datetime import datetime, timezone as _tz
            ot = int(datetime.strptime(valid_s, '%Y-%m-%d %H:%M')
                     .replace(tzinfo=_tz.utc).timestamp())
        except ValueError:
            continue

        delta = abs(ot - target_epoch)
        if delta > 3600:
            continue
        if sid in best and delta >= best[sid]['delta']:
            continue

        try:
            temp_c = round((float(tmpf_s) - 32) * 5 / 9, 1)
            spd_ms = float(sknt_s) * 0.514444
            rad    = math.radians(float(drct_s))
            u_v    = round(-spd_ms * math.sin(rad), 3)
            v_v    = round(-spd_ms * math.cos(rad), 3)
            rh = None
            if dwpf_s:
                t_c = (float(tmpf_s) - 32) * 5 / 9
                d_c = (float(dwpf_s) - 32) * 5 / 9
                rh = round(100 * math.exp(17.625 * d_c / (243.04 + d_c)) /
                                 math.exp(17.625 * t_c / (243.04 + t_c)), 1)
            gust = round(float(gust_s) * 0.514444, 2) if gust_s else None
        except (ValueError, TypeError):
            continue

        best[sid] = dict(id=sid, lat=float(lat_s), lon=float(lon_s),
                         temp=temp_c, u=u_v, v=v_v, rh=rh, gust=gust, delta=delta)
    return list(best.values())


def _fetch_iem_asos(hour_str):
    """IEM 5-min ASOS for all CONUS states → station dicts closest to hour_str."""
    from datetime import datetime, timezone, timedelta
    with _iem_asos_lock:
        if hour_str in _iem_asos_cache:
            return _iem_asos_cache[hour_str]

    dt = datetime.strptime(hour_str, '%Y-%m-%dT%H').replace(tzinfo=timezone.utc)
    t1 = dt - timedelta(minutes=65)
    t2 = dt + timedelta(minutes=65)
    target_epoch = int(dt.timestamp())

    CONUS = ['AL','AZ','AR','CA','CO','CT','DE','FL','GA','ID','IL','IN','IA',
             'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV',
             'NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD',
             'TN','TX','UT','VT','VA','WA','WV','WI','WY']
    state_q = '&'.join(f'state={s}' for s in CONUS)

    url = (
        'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'
        f'data=tmpf,dwpf,sknt,drct,gust&tz=UTC&format=onlycomma&latlon=yes'
        f'&missing=M&trace=T&direct=no&report_type=3,4'
        f'&year1={t1.year}&month1={t1.month:02d}&day1={t1.day:02d}'
        f'&hour1={t1.hour:02d}&minute1={t1.minute:02d}'
        f'&year2={t2.year}&month2={t2.month:02d}&day2={t2.day:02d}'
        f'&hour2={t2.hour:02d}&minute2={t2.minute:02d}'
        f'&{state_q}'
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        raw = urllib.request.urlopen(req, timeout=25).read().decode('utf-8', errors='replace')
        result = _iem_parse_csv(raw, target_epoch)
    except Exception:
        result = []

    with _iem_asos_lock:
        if len(_iem_asos_cache) > 48:
            del _iem_asos_cache[min(_iem_asos_cache)]
        _iem_asos_cache[hour_str] = result
    return result


def _fetch_iem_raws(hour_str):
    """IEM RAWS for western fire states → station dicts closest to hour_str."""
    from datetime import datetime, timezone, timedelta
    with _raws_lock:
        if hour_str in _raws_cache:
            return _raws_cache[hour_str]

    dt = datetime.strptime(hour_str, '%Y-%m-%dT%H').replace(tzinfo=timezone.utc)
    t1 = dt - timedelta(minutes=65)
    t2 = dt + timedelta(minutes=65)
    target_epoch = int(dt.timestamp())

    FIRE_STATES = ['CA','OR','WA','NV','AZ','NM','CO','UT','WY','MT','ID','TX','OK']
    time_q = (
        f'year1={t1.year}&month1={t1.month:02d}&day1={t1.day:02d}'
        f'&hour1={t1.hour:02d}&minute1={t1.minute:02d}'
        f'&year2={t2.year}&month2={t2.month:02d}&day2={t2.day:02d}'
        f'&hour2={t2.hour:02d}&minute2={t2.minute:02d}'
    )

    def _one(state):
        url = (
            f'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'
            f'network={state}_RAWS&data=tmpf,dwpf,sknt,drct,gust'
            f'&tz=UTC&format=onlycomma&latlon=yes&missing=M&trace=T&direct=no'
            f'&{time_q}'
        )
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            raw = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='replace')
            return _iem_parse_csv(raw, target_epoch)
        except Exception:
            return []

    all_st = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        for batch in ex.map(_one, FIRE_STATES):
            all_st.extend(batch)

    seen = {}
    for s in all_st:
        if s['id'] not in seen or s['delta'] < seen[s['id']]['delta']:
            seen[s['id']] = s
    result = list(seen.values())

    with _raws_lock:
        if len(_raws_cache) > 48:
            del _raws_cache[min(_raws_cache)]
        _raws_cache[hour_str] = result
    return result


def _get_stations(hour_str):
    """Combine IEM ASOS (all CONUS) + RAWS (fire country) fetched in parallel."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_asos = ex.submit(_fetch_iem_asos, hour_str)
        f_raws = ex.submit(_fetch_iem_raws, hour_str)
        asos = f_asos.result()
        raws = f_raws.result()
    asos_ids = {s['id'] for s in asos}
    return asos + [s for s in raws if s['id'] not in asos_ids]


def _idw_grid(stations):
    """IDW interpolation from METAR stations to _WX_LONS/_WX_LATS grid."""
    nx, ny = len(_WX_LONS), len(_WX_LATS)
    total = ny * nx
    if not stations:
        return [None]*total, [None]*total, [None]*total, [None]*total
    try:
        import numpy as np
        s_lats = np.array([s['lat']  for s in stations])
        s_lons = np.array([s['lon']  for s in stations])
        s_u    = np.array([s['u']    for s in stations])
        s_v    = np.array([s['v']    for s in stations])
        s_temp = np.array([s['temp'] for s in stations])
        s_rh   = np.array([s['rh'] if s['rh'] is not None else np.nan for s in stations])
        g_lats = np.repeat(np.array(_WX_LATS), nx)
        g_lons = np.tile(np.array(_WX_LONS), ny)
        RADIUS, POWER = 4.0, 2.0
        dlat = g_lats[:, None] - s_lats[None, :]
        dlon = g_lons[:, None] - s_lons[None, :]
        d = np.maximum(np.sqrt(dlat**2 + dlon**2), 0.001)
        w = np.where(d < RADIUS, 1.0 / d**POWER, 0.0)
        wsum = w.sum(axis=1)
        has_data = wsum > 0
        w_n = np.where(wsum[:, None] > 0, w / wsum[:, None], 0.0)
        u_out = (w_n * s_u).sum(axis=1)
        v_out = (w_n * s_v).sum(axis=1)
        t_out = (w_n * s_temp).sum(axis=1)
        rh_valid = ~np.isnan(s_rh)
        w_rh  = np.where((d < RADIUS) & rh_valid[None, :], w, 0.0)
        ws_rh = w_rh.sum(axis=1)
        rh_out = np.where(ws_rh > 0,
                          (w_rh * np.where(rh_valid, s_rh, 0.0)).sum(axis=1) / ws_rh,
                          np.nan)
        def _lst(arr, mask):
            return [round(float(x), 3) if m else None for x, m in zip(arr, mask)]
        return (_lst(u_out, has_data), _lst(v_out, has_data), _lst(t_out, has_data),
                [round(float(x), 1) if not np.isnan(x) else None for x in rh_out])
    except ImportError:
        import math
        RADIUS, POWER = 4.0, 2.0
        u_arr=[None]*total; v_arr=[None]*total; t_arr=[None]*total; rh_arr=[None]*total
        for ri, lat in enumerate(_WX_LATS):
            for ci, lon in enumerate(_WX_LONS):
                wu=wv=wt=wrh=ws=ws_rh=0.0
                for s in stations:
                    d = math.sqrt((s['lat']-lat)**2+(s['lon']-lon)**2)
                    if d >= RADIUS: continue
                    d = max(d, 0.001)
                    w = 1.0/d**POWER
                    wu+=w*s['u']; wv+=w*s['v']; wt+=w*s['temp']; ws+=w
                    if s['rh'] is not None: wrh+=w*s['rh']; ws_rh+=w
                if ws == 0: continue
                idx = ri*nx+ci
                u_arr[idx]=round(wu/ws,3); v_arr[idx]=round(wv/ws,3); t_arr[idx]=round(wt/ws,1)
                if ws_rh: rh_arr[idx]=round(wrh/ws_rh,1)
        return u_arr, v_arr, t_arr, rh_arr


def _fetch_rtma_grid(hour_str):
    """Fetch RTMA 2.5km analysis via NOMADS OPeNDAP ASCII (free, no key).
    Returns (u_arr, v_arr, t_arr, rh_arr) mapped onto _WX_LATS/_WX_LONS, or None."""
    from datetime import datetime, timezone
    with _rtma_lock:
        if hour_str in _rtma_cache:
            return _rtma_cache[hour_str]

    target_dt = datetime.strptime(hour_str, '%Y-%m-%dT%H').replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - target_dt).total_seconds() / 3600
    if age_h > 47 or age_h < -1:
        return None  # NOMADS keeps ~48h of RTMA

    date_str = hour_str[:10].replace('-', '')
    hh = hour_str[11:13]
    stride = 40  # ≈ 101 km ≈ 1° — matches our output grid resolution
    jmax = ((_RTMA_NJ - 1) // stride) * stride
    imax = ((_RTMA_NI - 1) // stride) * stride
    sl = f'[0][0:{stride}:{jmax}][0:{stride}:{imax}]'
    url = (
        f'https://nomads.ncep.noaa.gov/dods/rtma2p5/rtma2p5{date_str}'
        f'/rtma2p5_anal_{hh}z.ascii'
        f'?TMP2m{sl},DPT2m{sl},UGRD10m{sl},VGRD10m{sl}'
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        raw = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='replace')
    except Exception:
        # Cache the failure so repeated scrubbing doesn't re-hit NOMADS
        with _rtma_lock:
            _rtma_cache[hour_str] = None
        return None

    nj_sub = jmax // stride + 1
    ni_sub = imax // stride + 1
    n_exp  = nj_sub * ni_sub

    def _extract(text, vname):
        marker = vname + '.' + vname
        pos = text.find(marker)
        if pos < 0:
            return None
        section = text[pos:]
        end = section.find('\n\n')
        if end > 0:
            section = section[:end]
        vals = []
        for line in section.split('\n'):
            s = line.strip()
            if not s or s[0] not in '[0123456789-':
                continue
            s = _re.sub(r'^\[\d+\](\[\d+\])?,?\s*', '', s)
            for tok in s.split(','):
                tok = tok.strip()
                if tok:
                    try:
                        vals.append(float(tok))
                    except ValueError:
                        pass
        return vals if len(vals) >= int(n_exp * 0.8) else None

    tmp_k = _extract(raw, 'TMP2m')
    dpt_k = _extract(raw, 'DPT2m')
    u_raw = _extract(raw, 'UGRD10m')
    v_raw = _extract(raw, 'VGRD10m')

    if not tmp_k or not u_raw or not v_raw:
        with _rtma_lock:
            _rtma_cache[hour_str] = None
        return None

    # Build station-like list for IDW (avoids NN gaps in the bilinear canvas render)
    stations = []
    for jj in range(nj_sub):
        for ii in range(ni_sub):
            idx = jj * ni_sub + ii
            if idx >= len(tmp_k):
                break
            x = _RTMA_X0 + ii * stride * _RTMA_DX
            y = _RTMA_Y0 + jj * stride * _RTMA_DX
            lat, lon = _lcc_inv(x, y)
            if lat is None or not (23 <= lat <= 52 and -128 <= lon <= -62):
                continue
            t_c = tmp_k[idx] - 273.15
            rh  = None
            if dpt_k and idx < len(dpt_k):
                d_c = dpt_k[idx] - 273.15
                rh  = round(max(0.0, min(100.0,
                      100 * math.exp(17.625*d_c/(243.04+d_c)) /
                            math.exp(17.625*t_c/(243.04+t_c)))), 1)
            stations.append({'id': f'R{jj}_{ii}', 'lat': lat, 'lon': lon,
                             'temp': round(t_c, 1), 'u': round(u_raw[idx], 3),
                             'v': round(v_raw[idx], 3), 'rh': rh, 'gust': None})

    if len(stations) < 100:
        with _rtma_lock:
            _rtma_cache[hour_str] = None
        return None

    with _rtma_lock:
        if len(_rtma_cache) > 24:
            del _rtma_cache[min(_rtma_cache)]
        _rtma_cache[hour_str] = stations
    return stations


def _fetch_wx_point(lat, lon, hour_str):
    """Open-Meteo gap-fill for one grid point. Uses HRRR for recent, GFS for historical."""
    from datetime import datetime, timezone
    target_dt = datetime.strptime(hour_str, '%Y-%m-%dT%H').replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - target_dt).total_seconds() / 3600
    if age_h > 168:
        return None  # Open-Meteo free tier goes back 7 days
    if age_h <= 24:
        time_param = 'past_hours=24&forecast_hours=1&models=gfs_hrrr'
    else:
        past_days = min(7, int(age_h / 24) + 1)
        time_param = f'past_days={past_days}&forecast_hours=0&models=gfs'
    url = (
        f'https://api.open-meteo.com/v1/forecast'
        f'?latitude={lat}&longitude={lon}'
        f'&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,relative_humidity_2m'
        f'&{time_param}&timezone=UTC'
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        raw = urllib.request.urlopen(req, timeout=8).read()
        j = json.loads(raw)
        times = j['hourly']['time']
        idx = next((i for i, t in enumerate(times) if t.startswith(hour_str)), len(times)-1)
        spd = j['hourly']['wind_speed_10m'][idx]
        wd  = j['hourly']['wind_direction_10m'][idx]
        tmp = j['hourly']['temperature_2m'][idx]
        rh  = j['hourly'].get('relative_humidity_2m', [None]*len(times))[idx]
        if spd is None or wd is None or tmp is None:
            return None
        spd_ms = spd / 3.6
        rad = math.radians(wd)
        u = round(-spd_ms * math.sin(rad), 3)
        v = round(-spd_ms * math.cos(rad), 3)
        return (lat, lon, u, v, round(tmp, 1), round(rh, 1) if rh is not None else None)
    except Exception:
        return None


def _build_wx_grid(hour_str):
    """Build 1° CONUS grid.
    Priority: RTMA 2.5km (last 48h) → IEM ASOS+RAWS IDW → HRRR/GFS gap-fill.
    RTMA and obs station fetch run in parallel; RTMA points go through IDW to avoid banding."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_rtma = ex.submit(_fetch_rtma_grid, hour_str)
        f_obs  = ex.submit(_get_stations, hour_str)
        rtma_stations = f_rtma.result()
        obs_stations  = f_obs.result()

    if rtma_stations is not None:
        u_arr, v_arr, t_arr, rh_arr = _idw_grid(rtma_stations)
        src = 'RTMA 2.5km'
    else:
        u_arr, v_arr, t_arr, rh_arr = _idw_grid(obs_stations)
        src = 'IEM ASOS+RAWS'

    stations = obs_stations

    nx = len(_WX_LONS)
    missing = [(ri, ci) for ri in range(len(_WX_LATS))
               for ci in range(len(_WX_LONS)) if t_arr[ri*nx+ci] is None]
    if missing:
        def _fill(rc):
            ri, ci = rc
            return (ri, ci, _fetch_wx_point(_WX_LATS[ri], _WX_LONS[ci], hour_str))
        with ThreadPoolExecutor(max_workers=20) as ex:
            for ri, ci, r in ex.map(_fill, missing):
                if r is None: continue
                idx = ri*nx+ci
                _, _, u, v, tmp, rh = r
                u_arr[idx]=u; v_arr[idx]=v; t_arr[idx]=tmp
                if rh_arr[idx] is None: rh_arr[idx]=rh

    header = {
        'parameterCategory': 2, 'parameterNumber': 2,
        'nx': len(_WX_LONS), 'ny': len(_WX_LATS),
        'lo1': _WX_LONS[0], 'lo2': _WX_LONS[-1],
        'la1': _WX_LATS[0], 'la2': _WX_LATS[-1],
        'dx': 1.0, 'dy': 1.0,
        'refTime': hour_str + ':00:00',
    }
    wind_data = [
        {'header': {**header, 'parameterNumber': 2}, 'data': u_arr},
        {'header': {**header, 'parameterNumber': 3}, 'data': v_arr},
    ]
    st_out = [{'id':s['id'],'lat':s['lat'],'lon':s['lon'],'temp':s['temp'],
               'rh':s['rh'],'u':s['u'],'v':s['v'],'gust':s.get('gust')} for s in stations]
    return {'wind': wind_data, 'temp': t_arr, 'rh': rh_arr,
            'lats': _WX_LATS, 'lons': _WX_LONS, 'stations': st_out, 'src': src}


class FireHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the HTML and proxies aircraft data from OpenSky (bypassing CORS)."""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/aircraft':
            self._proxy_aircraft()
        elif self.path == '/api/firms':
            self._proxy_firms()
        elif self.path == '/api/fire-alerts':
            self._proxy_fire_alerts()
        elif self.path == '/api/fire-zones':
            self._proxy_fire_zones()
        elif self.path.startswith('/api/fire-zone-forecast'):
            self._proxy_fire_zone_forecast()
        elif self.path.startswith('/api/weather'):
            self._proxy_weather()
        elif self.path in ('/', '/index.html'):
            self.send_response(302)
            self.send_header('Location', '/goes19_replay_v3.html')
            self.end_headers()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/cam-scan':
            try:
                length  = int(self.headers.get('Content-Length', 0))
                body    = json.loads(self.rfile.read(length))
                cameras = body.get('cameras', [])[:150]  # cap per batch
                results = _run_cam_scan(cameras)
                payload = json.dumps(results).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', len(payload))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def _proxy_aircraft(self):
        try:
            req = urllib.request.Request(
                OPENSKY_URL,
                headers={'User-Agent': 'Mozilla/5.0 (FireMonitor/1.0)'},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.HTTPError as e:
            body = json.dumps({'error': f'OpenSky {e.code}', 'states': None}).encode()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = json.dumps({'error': str(e), 'states': None}).encode()
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)

    def _proxy_firms(self):
        """Fetch all 3 VIIRS 24h CSVs in parallel, return them combined (header once)."""
        def fetch_one(url):
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0 (FireMonitor/1.0)'})
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode('utf-8', errors='replace')

        try:
            combined = []
            header = None
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(fetch_one, u): u for u in FIRMS_CSVS}
                for fut in as_completed(futures):
                    try:
                        text = fut.result()
                    except Exception:
                        continue
                    lines = [l for l in text.splitlines() if l.strip()]
                    if not lines:
                        continue
                    if header is None:
                        header = lines[0]
                        combined.append(header)
                    combined.extend(lines[1:])
            if header is None:
                raise RuntimeError('all FIRMS fetches failed')
            body = '\n'.join(combined).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'max-age=300')
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            body = b'latitude,longitude,frp,confidence,acq_date,acq_time,satellite\n'
            self.send_response(502)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)

    def _proxy_fire_alerts(self):
        FIRE_EVENTS = {
            'Red Flag Warning', 'Fire Weather Watch', 'Extreme Fire Behavior',
            'Fire Weather Advisory', 'Blowing Dust Advisory', 'High Wind Warning',
            'High Wind Watch', 'Extreme Heat Warning', 'Heat Advisory',
        }
        # Western fire states — broad enough to catch all fire-relevant alerts
        AREAS = 'CA,OR,WA,NV,AZ,NM,UT,ID,MT,CO,WY,AK,HI,TX,OK,NE,SD,ND,MN'
        with _fire_alerts_lock:
            now = _time.time()
            if _fire_alerts_cache['data'] and now - _fire_alerts_cache['ts'] < 300:
                payload = _fire_alerts_cache['data']
            else:
                payload = None
        if payload is None:
            try:
                url = f'https://api.weather.gov/alerts/active?area={AREAS}&status=actual'
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'goes19-fire-monitor contact@example.com',
                    'Accept': 'application/geo+json',
                })
                raw = urllib.request.urlopen(req, timeout=20).read()
                j = json.loads(raw)
                # Filter server-side for fire/heat/wind events only
                j['features'] = [f for f in j.get('features', [])
                                  if f.get('properties', {}).get('event') in FIRE_EVENTS]
                payload = json.dumps(j).encode()
                with _fire_alerts_lock:
                    _fire_alerts_cache['data'] = payload
                    _fire_alerts_cache['ts'] = _time.time()
            except Exception as e:
                with _fire_alerts_lock:
                    payload = _fire_alerts_cache.get('data')
                if not payload:
                    self.send_error(502, str(e))
                    return
        self.send_response(200)
        self.send_header('Content-Type', 'application/geo+json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def _proxy_fire_zones(self):
        """NWS fire weather zone polygons — cached 24h, free, no key."""
        STATES = 'CA,OR,WA,NV,AZ,NM,UT,ID,MT,CO,WY,TX,OK,SD,ND,NE,MN,KS'
        with _fire_zones_lock:
            now = _time.time()
            if _fire_zones_cache['data'] and now - _fire_zones_cache['ts'] < 86400:
                payload = _fire_zones_cache['data']
            else:
                payload = None
        if payload is None:
            try:
                url = f'https://api.weather.gov/zones/fire?area={STATES}'
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'goes19-fire-monitor contact@example.com',
                    'Accept': 'application/geo+json',
                })
                raw = urllib.request.urlopen(req, timeout=25).read()
                payload = raw
                with _fire_zones_lock:
                    _fire_zones_cache['data'] = payload
                    _fire_zones_cache['ts'] = _time.time()
            except Exception as e:
                with _fire_zones_lock:
                    payload = _fire_zones_cache.get('data')
                if not payload:
                    self.send_error(502, str(e)); return
        self.send_response(200)
        self.send_header('Content-Type', 'application/geo+json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def _proxy_fire_zone_forecast(self):
        """NWS fire weather zone forecast for one zone (lazy-loaded per click)."""
        from urllib.parse import urlparse, parse_qs
        qs   = parse_qs(urlparse(self.path).query)
        zone = (qs.get('zone', [''])[0]).strip()
        if not zone or not zone.replace('_','').isalnum():
            self.send_error(400, 'zone param required'); return
        with _zone_fc_lock:
            entry = _zone_fc_cache.get(zone)
        if entry:
            payload, ts = entry
            if _time.time() - ts < 3600:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', len(payload))
                self.end_headers()
                self.wfile.write(payload); return
        try:
            url = f'https://api.weather.gov/zones/fire/{zone}/forecast'
            req = urllib.request.Request(url, headers={
                'User-Agent': 'goes19-fire-monitor contact@example.com',
                'Accept': 'application/json',
            })
            payload = urllib.request.urlopen(req, timeout=10).read()
            with _zone_fc_lock:
                _zone_fc_cache[zone] = (payload, _time.time())
                if len(_zone_fc_cache) > 500:
                    oldest = min(_zone_fc_cache, key=lambda k: _zone_fc_cache[k][1])
                    del _zone_fc_cache[oldest]
        except Exception as e:
            self.send_error(502, str(e)); return
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def _proxy_weather(self):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        hour_str = (qs.get('dt', [''])[0])[:13]  # "YYYY-MM-DDTHH"
        if not hour_str or len(hour_str) != 13:
            self.send_error(400, 'dt param required (YYYY-MM-DDTHH)')
            return
        with _wx_lock:
            cached = _wx_cache.get(hour_str)
            ts     = _wx_cache_ts.get(hour_str, 0)
        # Expire cache for hours within the last 2h so live METAR obs get refreshed
        from datetime import datetime, timezone as _tz
        age_h = (datetime.now(_tz.utc) -
                 datetime.strptime(hour_str, '%Y-%m-%dT%H').replace(tzinfo=_tz.utc)
                 ).total_seconds() / 3600
        if cached is not None and age_h < 2 and (_time.time() - ts) > 540:
            cached = None  # 9-minute TTL for recent hours
        if cached is None:
            try:
                cached = _build_wx_grid(hour_str)
            except Exception as e:
                self.send_error(500, str(e))
                return
            with _wx_lock:
                if len(_wx_cache) > 48:
                    oldest = min(_wx_cache)
                    del _wx_cache[oldest]
                _wx_cache[hour_str]    = cached
                _wx_cache_ts[hour_str] = _time.time()
        payload = json.dumps(cached).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass  # silence per-request noise


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'goes19_replay_v3.html')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(HTML)
    print(f'Saved  -> {out}')

    import webbrowser
    server = socketserver.ThreadingTCPServer(('', PORT), FireHandler)
    server.daemon_threads = True
    url = f'http://localhost:{PORT}/goes19_replay_v3.html'
    print(f'Server -> {url}')
    threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
