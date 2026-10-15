// ====================================================================
//  CEK KETERSEDIAAN DATA — Estimasi Stok Karbon Hutan Rawa Gambut
//  Mahathir Muhammad (6025252008) · Pengolahan Citra, ITS
//
//  Cara pakai: buka https://code.earthengine.google.com, tempel seluruh
//  skrip ini ke editor, lalu klik Run. Angka ringkasan muncul di tab
//  Console (kanan), layer data muncul di peta (bawah).
// ====================================================================


// ---------- 1. AOI dan periode ----------
// AOI awal: PERKIRAAN lanskap Katingan–Mentaya, Kalimantan Tengah.
// Sesuaikan: gambar poligon sendiri dengan ikon "Draw a shape" di peta,
// lalu ganti baris di bawah dengan:  var aoi = geometry;
var aoi = ee.Geometry.Rectangle([112.8, -3.4, 113.5, -2.3]);

// Alternatif: batas kabupaten dari FAO GAUL (cek nama di tab Inspector)
// var aoi = ee.FeatureCollection('FAO/GAUL/2015/level2')
//   .filter(ee.Filter.inList('ADM2_NAME', ['Katingan', 'Kotawaringin Timur']))
//   .geometry();

var START = '2020-01-01';
var END   = '2021-01-01';

Map.centerObject(aoi, 9);


// ---------- 2. Sentinel-2 SR + masker awan Cloud Score+ ----------
var csPlus = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');
var CLEAR = 0.60;  // ambang cs_cdf; naikkan (mis. 0.65) bila awan masih tersisa

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(aoi)
  .filterDate(START, END)
  .linkCollection(csPlus, ['cs_cdf'])
  .map(function (img) {
    return img.updateMask(img.select('cs_cdf').gte(CLEAR))
              .select(['B2', 'B3', 'B4', 'B8', 'B11', 'B12'])
              .divide(10000);  // reflektansi 0–1
  });

var s2med = s2.median().clip(aoi);
var ndvi = s2med.normalizedDifference(['B8', 'B4']).rename('NDVI');
var evi = s2med.expression(
  '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
  {NIR: s2med.select('B8'), RED: s2med.select('B4'), BLUE: s2med.select('B2')}
).rename('EVI');

// Tekstur GLCM dari band NIR (proxy struktur tajuk)
var glcm = s2med.select('B8').multiply(255).toUint8()
  .glcmTexture({size: 3})
  .select(['B8_contrast', 'B8_ent', 'B8_var']);

print('Jumlah citra Sentinel-2 tahun ini:', s2.size());
print('Fraksi AOI yang terisi komposit S2 (0–1):',
  s2med.select('B8').mask().reduceRegion({
    reducer: ee.Reducer.mean(), geometry: aoi, scale: 100, maxPixels: 1e10
  }));


// ---------- 3. Sentinel-1 GRD (radar C-band) ----------
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoi)
  .filterDate(START, END)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .select(['VV', 'VH']);

// Median multi-temporal sekaligus meredam speckle; Refined Lee bisa ditambah nanti
var s1med = s1.median().clip(aoi);
var s1ratio = s1med.select('VH').subtract(s1med.select('VV')).rename('VH_minus_VV');

print('Jumlah citra Sentinel-1 tahun ini:', s1.size());


// ---------- 4. ALOS PALSAR-2 mosaik tahunan (radar L-band) ----------
var palsarCol = ee.ImageCollection('JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH')
  .filterBounds(aoi)
  .filterDate(START, END);
var palsar = palsarCol.mosaic();

// DN -> gamma0 (dB) = 10*log10(DN^2) - 83.0  (rumus dari katalog GEE)
var toDb = function (band) {
  var dn = palsar.select(band).toFloat();
  return dn.pow(2).log10().multiply(10).subtract(83.0)
    .updateMask(dn.gt(0))
    .rename(band + '_dB');
};
var palsarDb = toDb('HH').addBands(toDb('HV')).clip(aoi);

print('Jumlah tile PALSAR-2 tahun ini:', palsarCol.size());


// ---------- 5. Copernicus DEM GLO-30 (topografi kubah gambut) ----------
// Catatan: ini DSM (termasuk tajuk). Untuk topografi kubah, pakai elevasi
// relatif dan kemiringan, atau DSM dikurangi tinggi kanopi sebagai perkiraan.
var demCol = ee.ImageCollection('COPERNICUS/DEM/GLO30_2024_1');
var demProj = demCol.first().projection();
var dem = demCol.filterBounds(aoi).select('DEM').mosaic()
  .setDefaultProjection(demProj).rename('elevasi');
var slope = ee.Terrain.slope(dem).rename('kemiringan');
dem = dem.clip(aoi);
slope = slope.clip(aoi);


// ---------- 6. GEDI: label Head 1 (tinggi) dan Head 2 (AGB) ----------
var gediL4a = ee.ImageCollection('LARSE/GEDI/GEDI04_A_002_MONTHLY')
  .filterBounds(aoi)
  .filterDate(START, END)
  .map(function (im) {
    return im.updateMask(im.select('l4_quality_flag').eq(1))
             .updateMask(im.select('degrade_flag').eq(0));
  })
  .select('agbd')
  .mosaic()
  .clip(aoi);

var gediL2a = ee.ImageCollection('LARSE/GEDI/GEDI02_A_002_MONTHLY')
  .filterBounds(aoi)
  .filterDate(START, END)
  .map(function (im) {
    return im.updateMask(im.select('quality_flag').eq(1))
             .updateMask(im.select('degrade_flag').eq(0));
  })
  .select('rh98')
  .mosaic()
  .clip(aoi);

print('Jumlah titik GEDI L4A (AGB) berkualitas:',
  gediL4a.reduceRegion({
    reducer: ee.Reducer.count(), geometry: aoi, scale: 25,
    maxPixels: 1e10, tileScale: 4
  }));
print('Jumlah titik GEDI L2A (tinggi rh98) berkualitas:',
  gediL2a.reduceRegion({
    reducer: ee.Reducer.count(), geometry: aoi, scale: 25,
    maxPixels: 1e10, tileScale: 4
  }));


// ---------- 7. Peta kanopi ETH 2020 (hanya pembanding, bukan input) ----------
var eth = ee.Image('users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1').clip(aoi);


// ---------- 8. PEATGRIDS (cadangan/pembanding ketebalan & stok C gambut) ----------
var peatThick = ee.Image('projects/sat-io/open-datasets/PEATGRIDS/THICKNESS_CM')
  .select('THICKNESS_CM_MEAN');
peatThick = peatThick.updateMask(peatThick.gte(0)).clip(aoi);

var peatC = ee.Image('projects/sat-io/open-datasets/PEATGRIDS/C_STOCK_MGC_PER_M2')
  .select('C_STOCK_MgC_per_m2_MEAN');
peatC = peatC.updateMask(peatC.gte(0)).clip(aoi);

print('PEATGRIDS — rata-rata ketebalan gambut di AOI (cm):',
  peatThick.reduceRegion({
    reducer: ee.Reducer.mean(), geometry: aoi, scale: 1000, maxPixels: 1e10
  }));
print('PEATGRIDS — rata-rata stok karbon gambut di AOI (Mg C/m²):',
  peatC.reduceRegion({
    reducer: ee.Reducer.mean(), geometry: aoi, scale: 1000, maxPixels: 1e10
  }));


// ---------- 9. Data dari luar GEE (aktifkan setelah di-upload ke Assets) ----------
// Upload SHP lewat tab Assets > NEW > Shapefiles, lalu ganti NAMA_PROYEK:
// var gambutKementan = ee.FeatureCollection('projects/NAMA_PROYEK/assets/gambut_kementan_2019');
// var tutupanKLHK   = ee.FeatureCollection('projects/NAMA_PROYEK/assets/penutupan_lahan_2020');
// Map.addLayer(gambutKementan, {color: '8B4513'}, 'Peta gambut Kementan');
// Map.addLayer(tutupanKLHK, {color: '2E7D32'}, 'Penutupan lahan KLHK');


// ---------- 10. Tampilkan di peta ----------
Map.addLayer(s2med, {bands: ['B4', 'B3', 'B2'], min: 0, max: 0.2}, 'Sentinel-2 RGB');
Map.addLayer(ndvi, {min: 0, max: 1, palette: ['F4F1DE', '81B29A', '1B4332']}, 'NDVI', false);
Map.addLayer(glcm.select('B8_contrast'), {min: 0, max: 50}, 'GLCM contrast (NIR)', false);
Map.addLayer(s1med.select('VH'), {min: -25, max: -10}, 'Sentinel-1 VH (dB)', false);
Map.addLayer(palsarDb.select('HV_dB'), {min: -20, max: -8}, 'PALSAR-2 HV (dB)', false);
Map.addLayer(dem, {min: 0, max: 40, palette: ['2C7BB6', 'FFFFBF', 'D7191C']}, 'Elevasi DSM (m)', false);
Map.addLayer(eth, {min: 0, max: 40, palette: ['FFFFE5', '78C679', '004529']}, 'Tinggi kanopi ETH 2020 (m)', false);
Map.addLayer(peatThick, {min: 0, max: 1000, palette: ['FFF7BC', 'FEC44F', '993404']}, 'PEATGRIDS ketebalan (cm)', false);
// Titik GEDI hanya 25 m; diperbesar agar terlihat saat zoom jauh
Map.addLayer(gediL4a.focalMax(2), {min: 0, max: 400, palette: ['FFFFCC', '41AB5D', '00441B']}, 'GEDI L4A AGBD (Mg/ha)');
Map.addLayer(ee.Image().paint(ee.FeatureCollection([ee.Feature(aoi)]), 0, 2), {palette: ['FFFF00']}, 'AOI');


// ---------- 11. (Opsional) Ekspor stack input ke Google Drive ----------
// Hapus tanda komentar untuk mengekspor; proses berjalan di tab Tasks.
// var stack = ee.Image.cat([
//   s2med, ndvi, evi, glcm, s1med, s1ratio, palsarDb, dem, slope
// ]).toFloat();
// Export.image.toDrive({
//   image: stack,
//   description: 'stack_input_2020',
//   region: aoi,
//   scale: 10,
//   maxPixels: 1e13
// });
