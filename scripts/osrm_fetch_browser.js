// Fetch OSRM driving distances for all New York fast-charging sites from a browser.
//
// This is the exact procedure used on Nov 19, 2026 to build
// data/derived/road_miles_pairs_le60.u16.gz (the cloud workspace could not reach
// router.project-osrm.org, so the requests were made from a browser tab).
//
// How to run:
//   1. Open https://router.project-osrm.org/ in a browser tab (same origin, so no CORS issue).
//   2. Paste into the developer console:
//        window.PTS = [[lon, lat], ...]   // 754 pairs, in the row order of data/derived/sites.csv
//      e.g. generated with:
//        python -c "import pandas as pd, json; s=pd.read_csv('data/derived/sites.csv');
//                   print(json.dumps([[round(a,6),round(b,6)] for a,b in zip(s.Longitude,s.Latitude)]))"
//   3. Paste this file. It sends 256 table requests (50 x 50 blocks, 1 s apart), then
//      downloads road_miles_pairs_le60.u16.gz.
//   4. Move the file to data/derived/ and run scripts/run_all.py; evnet.data.unpack_road_miles
//      rebuilds the 754 x 754 matrix (pairs farther than 60 straight-line miles are set to 1e6).
//
// File format: gzip of little-endian uint16 = round(road miles x 20) (0.05-mile resolution),
// for every pair i < j with straight-line distance <= 60 miles, in row-major upper-triangle order.
// The road distance used is min(d(i->j), d(j->i)).

(async () => {
  const n = PTS.length, B = 50;
  const RM = new Float64Array(n * n).fill(NaN);
  const blocks = [];
  for (let a = 0; a < n; a += B) for (let b = 0; b < n; b += B) blocks.push([a, b]);

  for (const [a, b] of blocks) {
    const src = [...Array(Math.min(B, n - a)).keys()].map(k => a + k);
    const dst = [...Array(Math.min(B, n - b)).keys()].map(k => b + k);
    const ids = src.concat(dst);
    const pts = ids.map(k => PTS[k][0] + ',' + PTS[k][1]).join(';');
    const s = src.map((_, k) => k).join(';');
    const d = dst.map((_, k) => src.length + k).join(';');
    const url = `/table/v1/driving/${pts}?sources=${s}&destinations=${d}&annotations=distance`;
    for (let tr = 0; tr < 4; tr++) {
      try {
        const j = await (await fetch(url)).json();
        if (j.code !== 'Ok') throw new Error(j.code);
        j.distances.forEach((row, i) => row.forEach((v, jj) => { RM[src[i] * n + dst[jj]] = v == null ? NaN : v; }));
        break;
      } catch (e) { console.warn(a, b, e.message); await new Promise(r => setTimeout(r, 3000)); }
    }
    await new Promise(r => setTimeout(r, 1000));
  }

  // pack pairs within 60 straight-line miles
  const rad = x => x * Math.PI / 180, vals = [];
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
    const la1 = rad(PTS[i][1]), lo1 = rad(PTS[i][0]), la2 = rad(PTS[j][1]), lo2 = rad(PTS[j][0]);
    const h = Math.sin((la1 - la2) / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin((lo1 - lo2) / 2) ** 2;
    const straight = 2 * 3958.8 * Math.asin(Math.sqrt(Math.min(1, h)));
    if (straight <= 60) {
      const m = Math.min(RM[i * n + j], RM[j * n + i]);
      vals.push(Number.isNaN(m) ? 65535 : Math.min(65534, Math.round(m / 1609.34 * 20)));
    }
  }
  const cs = new CompressionStream('gzip'), w = cs.writable.getWriter();
  w.write(new Uint8Array(new Uint16Array(vals).buffer)); w.close();
  const gz = await new Response(cs.readable).blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(gz);
  a.download = 'road_miles_pairs_le60.u16.gz';
  document.body.appendChild(a); a.click();
  console.log('pairs', vals.length);   // 54737 for the September 23, 2026 sites
})();
