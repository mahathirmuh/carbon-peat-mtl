// ====================================================================
//  CONTOH CITRA UNTUK SLIDE — sebelum/sesudah preprocessing, fitur, label
//  Mahathir Muhammad (6025252008) · Pengolahan Citra, ITS
//
//  Cara pakai:
//  1. Tempel seluruh skrip ini ke Code Editor, lalu klik Run.
//  2. Lihat kotak MAGENTA di peta. Kalau sebagian besar jatuh di sungai
//     lebar atau lahan terbuka, geser angka di baris WIN (tetap di dalam
//     kotak kuning), lalu Run ulang.
//  3. Di tab Console muncul 10 gambar bernomor. Klik tulisan biru di atas
//     tiap gambar -> PNG ukuran penuh terbuka di tab baru -> simpan (Ctrl+S)
//     dengan nama yang sama, misalnya 01_s2_mentah.png.
// ====================================================================


// ---------- 1. Jendela contoh (±11 × 11 km di dalam AOI) ----------
var WIN = ee.Geometry.Rectangle([113.10, -2.90, 113.20, -2.80]);
var AOI = ee.Geometry.Rectangle([112.8, -3.4, 113.5, -2.3]);
var START = '2020-01-01';
var END = '2021-01-01';
var DIM = 1024;  // lebar gambar dalam piksel (±11 m per piksel)

Map.setOptions('SATELLITE');
Map.centerObject(WIN, 12);
Map.addLayer(ee.Image().paint(ee.FeatureCollection([ee.Feature(AOI)]), 0, 2),
  {palette: ['FFFF00']}, 'AOI (kuning)');
Map.addLayer(ee.Image().paint(ee.FeatureCollection([ee.Feature(WIN)]), 0, 3),
  {palette: ['FF00FF']}, 'Jendela contoh (magenta)');

// Tampilkan pratinjau kecil + link PNG ukuran penuh di Console
function tampilkan(nama, citraVis) {
  var url = citraVis.getThumbURL({region: WIN, dimensions: DIM, format: 'png'});
  print(ui.Label(nama + '  (klik untuk membuka PNG)', {color: '#1a73e8', fontWeight: 'bold'}, url));
  print(ui.Thumbnail({image: citraVis, params: {region: WIN, dimensions: 256, format: 'png'}}));
}


// ---------- 2. Sentinel-2: satu tanggal berawan vs komposit bermasker awan ----------
var csPlus = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');
var CLEAR = 0.60;  // ambang cs_cdf, sama dengan rencana penelitian

var s2col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(WIN)
  .filterDate(START, END)
  .linkCollection(csPlus, ['cs_cdf']);

// Pilih tanggal yang jendelanya tertutup penuh oleh citra dan ±50% berawan
var s2skor = s2col.map(function (img) {
  var stat = ee.Image.cat(
      img.select('cs_cdf').gte(CLEAR).rename('cerah'),
      img.select('B4').mask().rename('tutup')
    ).reduceRegion({reducer: ee.Reducer.mean(), geometry: WIN, scale: 60, maxPixels: 1e8});
  return img.set({fraksi_cerah: stat.get('cerah'), fraksi_tutup: stat.get('tutup')});
}).filter(ee.Filter.gt('fraksi_tutup', 0.95))
  .filter(ee.Filter.notNull(['fraksi_cerah']));

var s2mentah = ee.Image(s2skor.map(function (img) {
  return img.set('selisih', ee.Number(img.get('fraksi_cerah')).subtract(0.5).abs());
}).sort('selisih').first());

var s2komposit = s2col.map(function (img) {
  return img.updateMask(img.select('cs_cdf').gte(CLEAR));
}).median();

var rgbVis = {bands: ['B4', 'B3', 'B2'], min: 0, max: 1500, gamma: 1.1};  // reflektansi × 10000

print('Tanggal Sentinel-2 mentah:', s2mentah.date().format('YYYY-MM-dd'));
print('Jumlah citra Sentinel-2 di komposit:', s2col.size());


// ---------- 3. Sentinel-1 VH: satu tanggal (speckle) vs median tahunan ----------
var s1col = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(WIN)
  .filterDate(START, END)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .select('VH');

var s1mentah = ee.Image(s1col.filter(ee.Filter.contains('.geo', WIN)).first());
var s1median = s1col.median();
var vhVis = {min: -25, max: -10};

print('Tanggal Sentinel-1 mentah:', s1mentah.date().format('YYYY-MM-dd'));
print('Jumlah citra Sentinel-1 di median:', s1col.size());


// ---------- 4. DEM: asli vs low-pass (Gaussian) untuk bentuk kubah gambut ----------
var demCol = ee.ImageCollection('COPERNICUS/DEM/GLO30_2024_1');
var dem = demCol.filterBounds(WIN).select('DEM').mosaic()
  .setDefaultProjection(demCol.first().projection());
var demLowpass = dem.convolve(ee.Kernel.gaussian({radius: 1500, sigma: 500, units: 'meters'}));

var p = dem.reduceRegion({
  reducer: ee.Reducer.percentile([2, 98]), geometry: WIN, scale: 30, maxPixels: 1e8
}).getInfo();
var demVis = {min: p.DEM_p2, max: p.DEM_p98, palette: ['2C7BB6', 'FFFFBF', 'D7191C']};
print('Rentang elevasi di jendela (persentil 2–98, m):', p.DEM_p2, p.DEM_p98);


// ---------- 5. Fitur: NDVI, tekstur GLCM, PALSAR-2 HV ----------
var ndvi = s2komposit.normalizedDifference(['B8', 'B4']);

var glcmKontras = s2komposit.select('B8').divide(10000).multiply(255).toUint8()
  .glcmTexture({size: 3})
  .select('B8_contrast');

var palsar = ee.ImageCollection('JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH')
  .filterBounds(WIN)
  .filterDate(START, END)
  .mosaic();
var hv = palsar.select('HV').toFloat();
var hvDb = hv.pow(2).log10().multiply(10).subtract(83.0).updateMask(hv.gt(0));  // DN -> dB


// ---------- 6. Label: titik GEDI L4A (AGB) di atas komposit Sentinel-2 ----------
var gedi = ee.ImageCollection('LARSE/GEDI/GEDI04_A_002_MONTHLY')
  .filterBounds(WIN)
  .filterDate(START, END)
  .map(function (im) {
    return im.updateMask(im.select('l4_quality_flag').eq(1))
             .updateMask(im.select('degrade_flag').eq(0));
  })
  .select('agbd')
  .mosaic();

print('Jumlah titik GEDI L4A berkualitas di jendela:',
  gedi.reduceRegion({reducer: ee.Reducer.count(), geometry: WIN, scale: 25, maxPixels: 1e8}));

// Titik diperbesar (±75 m) agar terlihat di gambar; ukuran asli ±25 m
var gediDiAtasS2 = s2komposit.visualize(rgbVis).blend(
  gedi.focalMax(1).visualize({min: 0, max: 400, palette: ['FFFF00', 'FF8C00', 'FF0000']})
);


// ---------- 7. Tampilkan 10 gambar ----------
tampilkan('01_s2_mentah', s2mentah.visualize(rgbVis));
tampilkan('02_s2_komposit', s2komposit.visualize(rgbVis));
tampilkan('03_s1_vh_mentah', s1mentah.visualize(vhVis));
tampilkan('04_s1_vh_median', s1median.visualize(vhVis));
tampilkan('05_dem_asli', dem.visualize(demVis));
tampilkan('06_dem_lowpass', demLowpass.visualize(demVis));
tampilkan('07_ndvi', ndvi.visualize({min: 0.2, max: 0.9, palette: ['F4F1DE', '81B29A', '1B4332']}));
tampilkan('08_glcm_kontras', glcmKontras.visualize({min: 0, max: 50}));
tampilkan('09_palsar_hv', hvDb.visualize({min: -20, max: -8}));
tampilkan('10_gedi_titik', gediDiAtasS2);
