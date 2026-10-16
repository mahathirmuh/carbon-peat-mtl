# Catatan kemajuan

## Fase 0 — Setup proyek (15 Oktober 2026)

**Dibuat**

- Repo git, remote di https://github.com/mahathirmuh/carbon-peat-mtl. File awal (CLAUDE.md, PLAN.md, dua skrip
  `.js`) menjadi baseline di branch `main`. Pekerjaan Fase 0 ada di branch `fase-0` dan di-merge ke `main`
  setelah disetujui.
- Struktur folder sesuai CLAUDE.md, `.gitignore`, `.gitattributes` (akhir baris LF supaya sama di Windows dan
  Colab), `README.md`, `environment.yml`, `pytest.ini`.
- `config/config.yaml`: AOI, jendela smoke test, tahun, CRS, skala, semua ID dataset, urutan 19 band, ambang
  `cs_cdf`, nilai nodata, parameter patch dan split, bobot loss, konversi karbon, serta kelas kedalaman gambut.
- `src/config.py`: membaca config, lalu menolak config yang melanggar aturan pipeline (blok tidak sejajar dengan
  patch, rasio split tidak berjumlah 1, kelas gambut bercelah atau bertumpuk, jendela smoke test di luar AOI).
- `gee/auth_check.py`: inisialisasi Earth Engine dengan `gee_project`, mencetak versi API dan luas AOI, lalu
  mengecek bahwa setiap ID dataset di config bisa dibaca.
- `scripts/check_block_alignment.py`: simulasi aturan split Fase 4 untuk membandingkan ukuran blok; hasilnya di
  `outputs/metrics/block_alignment.json`.
- Tes: `tests/test_config.py`, `tests/test_auth_check.py`, `tests/test_block_alignment.py`.

**Lingkungan**

- Miniforge 26.7.2-0 dipasang per user di `C:\Users\itsupport\miniforge3`, tanpa mengubah PATH. Jalankan
  perintah dari **Miniforge Prompt** setelah `conda activate carbon-peat`.
- Env `carbon-peat`: Python 3.11.17, earthengine-api 1.7.48, geemap 0.37.1, rasterio 1.4.4 (GDAL 3.12.3),
  numpy 2.4.6, pandas 3.0.6, scikit-learn 1.9.1, torch 2.14.1 (CPU, tanpa CUDA), PyYAML 6.0.3,
  matplotlib 3.11.2, tqdm 4.70.1, pytest 9.1.1.

**Angka penting**

- `pytest -q`: 14 passed.
- `gee/auth_check.py` (project `pcd-research-511612`): earthengine-api 1.7.48, luas AOI 9.509 km², dan ke-13 ID
  dataset di config terbaca semua (8 ImageCollection, 4 Image, 1 Table). Asset Kementan dan KLHK masih TODO.
- `scripts/check_block_alignment.py` (grid AOI 7807 × 12181 piksel 10 m, patch 256 piksel, rata-rata 20 seed):

| Ukuran blok | Skema split | Patch terbuang | Patch tersisa train / val / test | Rasio efektif train / val / test |
|---|---|---|---|---|
| 5000 m | 70/15/15 | 42,8% | 68% / 32% / 32% | 83 / 8 / 8 |
| 5000 m | 10-fold | 70,9% | – | – |
| 5120 m | 70/15/15 | 0% | 100% / 100% / 100% | 70 / 15 / 15 |
| 5120 m | 10-fold | 0% | – | – |

**Keputusan**

1. `block_size_m` = 5120 m (2 × 2 patch), bukan 5000 m. Dengan blok 5000 m, batas blok tidak sejajar dengan grid
   patch, sehingga aturan "buang patch yang memotong batas dua split" membuang 42,8% patch, terutama di val/test.
   Dengan 5120 m tidak ada patch yang terbuang. `src/config.py` menolak ukuran blok yang bukan kelipatan ukuran
   patch. PLAN.md ikut diperbarui.
2. Nilai nodata ekspor eksplisit: −9999 (float32) dan −32768 (int16), ditulis dengan `unmask()` sebelum ekspor.
   Tujuannya agar piksel tanpa GEDI tidak tersimpan sebagai 0 (keputusan metodologi #1).
3. Nama band dalam bahasa Inggris: `elevation`, `elevation_lowpass`, `slope`; band lain mengikuti skrip JS
   (`VH_minus_VV`, `HH_dB`, `HV_dB`, `B8_contrast`, `B8_ent`, `B8_var`).
4. `seed` = 42. `peat_ignore_index` = 255, yaitu nilai nodata pada label gambut yang diabaikan cross-entropy.
   `temporary_labels: true` selama label Head 3 berasal dari PEATGRIDS.
5. Kedalaman kelas >300 cm (3 / 7,5 / 10 m) dicek ke Warren et al. (2017), bagian Methods: "values of 300, 750,
   and 1000 were used for low, medium and high estimates". Nilai 750 cm adalah titik tengah 300–1200 cm (batas
   bawah kelas terdalam peta MoA sampai batas atas kelas terdalam peta WI Kalimantan), dan 1000 cm adalah titik
   tengah kelas WI 800–1200 cm. Jadi 7,5 m benar dan tidak diubah. Di paper tertulis "In the >200 cm depth class",
   tetapi dari konteksnya (batas bawah 300 cm = batas atas kedalaman peta MoA) yang dimaksud adalah kelas >300 cm.
   Cd 61,6 kg C/m³ untuk Kalimantan Tengah juga cocok dengan Tabel 1 paper.

**Status kriteria Fase 0**

Semua kriteria "Selesai jika" terpenuhi: environment terpasang, Earth Engine terinisialisasi dengan project
`pcd-research-511612`, dan `pytest -q` berjalan (14 passed). Login Earth Engine dilakukan pada 15 Oktober 2026;
tokennya tersimpan di profil Windows (`~/.config/earthengine`), bukan di repo.

**Belum selesai**

- `drive_folder` serta path asset Kementan dan KLHK masih TODO.

## Fase 1 — Cek dan eksplorasi data (15 Oktober 2026)

**Dibuat**

- `gee/sources.py`: modul bersama untuk sumber data Earth Engine, yaitu Sentinel-2 + Cloud Score+, Sentinel-1,
  PALSAR-2 (DN → dB), Copernicus DEM, GEDI L4A/L2A dengan filter kualitas, PEATGRIDS, dan masker daratan dari ESA
  WorldCover 2020. Filternya sama dengan `gee/cek_data_gee.js`, dan modul ini dipakai lagi di Fase 2 dan 3 supaya
  cek data, stack fitur, dan label memakai citra yang sama.
- `gee/check_data.py`: versi Python dari `cek_data_gee.js`, ditambah fraksi daratan AOI, sebaran titik GEDI per sel
  seukuran patch, dan quick-look PNG (`s2_rgb`, `s1_vh`, `palsar2_hv`, `dem`, `gedi_l4a`). Output AOI penuh ada di
  `outputs/data_check/`, sedangkan smoke test di `outputs/data_check/smoke/`.
- Tes: `tests/test_check_data.py`. Total `pytest -q`: 17 passed.

**Angka penting** (AOI penuh, 2020, dari `outputs/data_check/summary.json`)

| Data | Hasil Python | Acuan CLAUDE.md (skrip JS) | Selisih |
|---|---|---|---|
| Citra Sentinel-2 | 365 | 365 | 0 |
| Fraksi AOI tertutup komposit Sentinel-2 | 0,9991 | 0,999 | +0,01% |
| Citra Sentinel-1 (IW, VV + VH) | 48 | 48 | 0 |
| Mosaik PALSAR-2 | 1 | 1 | 0 |
| Piksel GEDI L4A lolos filter kualitas | 111.610 | 111.610 | 0 |
| Piksel GEDI L2A lolos filter kualitas | 162.131 | 162.131 | 0 |
| PEATGRIDS, tebal rata-rata (cm) | 275,08 | 275 | +0,03% |
| PEATGRIDS, stok karbon rata-rata (Mg C/m²) | 0,2428 | 0,243 | −0,07% |

Semua angka sama dengan acuan. Selisih kecil hanya karena angka di CLAUDE.md dibulatkan, jadi tidak ada selisih
besar yang perlu dijelaskan. Cara hitung "titik GEDI": jumlah piksel 25 m yang berisi minimal satu footprint lolos
filter kualitas setelah 12 citra bulanan di-mosaic. Footprint dari bulan berbeda yang jatuh di piksel yang sama
hanya terhitung sekali.

Tambahan yang tidak ada di skrip JS:

- Fraksi daratan AOI: 0,775. Artinya ±22,5% AOI berupa laut dan perairan (Laut Jawa dan muara Mentaya–Katingan).
- Piksel GEDI L4A per sel 2,56 km (seukuran patch). Sel diambil dari grid EPSG:32749 dan hanya sel yang seluruhnya
  di dalam AOI yang dihitung:

| Sel | Jumlah sel | Sel yang punya GEDI | Median piksel GEDI per sel | Persentil 90 |
|---|---|---|---|---|
| Semua | 1.334 | 67,7% | 34 | 213 |
| Daratan (≥ 50% darat) | 1.053 | 83,7% | 78 | 237 |

- Smoke test (jendela 11 × 11 km): 144 citra Sentinel-2, 24 citra Sentinel-1, 2.887 piksel L4A, 3.390 piksel L2A,
  100% daratan, dan ke-12 sel punya GEDI (median 166).

**Penilaian: apakah titik GEDI cukup untuk training?**

Cukup, sehingga config tidak diubah. Ada 111.610 footprint L4A berkualitas yang tersebar di 83,7% sel daratan, dengan
median 78 footprint per sel. Sekitar 16% sel daratan tidak punya GEDI karena celah antar-jalur orbit dan footprint
yang tersaring kualitasnya. Sel seperti itu tetap berguna untuk Head 3 (label gambut padat) di training multi-task;
loss tinggi dan AGB-nya otomatis tidak dihitung karena masked loss. Opsi menambah tahun 2021–2022 atau memperluas AOI
baru perlu dibahas kalau jumlah titik GEDI di split val/test (Fase 4) ternyata terlalu sedikit.

**Temuan untuk fase berikutnya**

- AOI memuat ±22,5% laut dan perairan. Sebelum ekspor Fase 2 perlu diputuskan: (a) bbox tetap, piksel air diberi
  nodata, dan patch yang sebagian besar air dibuang di Fase 4; (b) batas selatan bbox dipotong; atau (c) AOI diganti
  poligon daratan. Usulan: (a), karena paling sederhana dan tidak mengubah AOI di CLAUDE.md.
- Quick-look DEM memperlihatkan kubah gambut dengan jelas di antara S. Mentaya dan S. Katingan. Ini mendukung kanal
  elevasi low-pass.
- Masker daratan (`sources.land_mask`) siap dipakai untuk menyaring patch di Fase 4.

**Keputusan**

- Ditambahkan metrik sebaran GEDI per sel seukuran patch dan masker daratan ESA WorldCover. Tujuannya agar kecukupan
  label dinilai tanpa terpengaruh sel laut.
- Config tidak diubah: AOI, tahun, dan filter GEDI tetap.

## Fase 2 — Stack fitur input (15–16 Oktober 2026)

**Dibuat**

- `src/grid.py`: grid kerja bersama (EPSG:32749, 10 m). Titik awalnya di kelipatan 10 m, sehingga grid AOI dan grid
  smoke saling sejajar, dan piksel 10 m sejajar dengan grid Sentinel-2. Grid AOI: x0 = 699.970, y0 = 9.745.660,
  7.809 × 12.183 piksel. Grid smoke: 1.115 × 1.109 piksel. Grid yang sama dipakai label (Fase 3) dan patch (Fase 4).
- `gee/build_features.py`: membangun 19 band sesuai urutan config, lalu mengekspornya ke Google Drive tepat di grid
  kerja (crs + crsTransform + dimensions) sebagai float32 dengan nodata −9999. Urutan band dicek dengan `bandNames()`
  sebelum ekspor. Ekspor AOI penuh baru jalan dengan flag `--yes`. Opsi `--download` mengambil citra smoke langsung
  dari Earth Engine dalam tile 512 piksel.
- `scripts/check_features.py`: memeriksa tile GeoTIFF terhadap grid kerja (CRS, ukuran piksel, titik awal, jumlah
  band, cakupan) dan menghitung statistik per band. Opsi `--write-tags` menulis nodata dan nama band ke salinan lokal
  supaya terbaca benar di QGIS.
- `outputs/features/band_list.json`: nama, urutan, dan satuan ke-19 band.
- Config: `drive_folder: carbon-peat-mtl`, `glcm_size`, `dem_lowpass`, `export_tile_px`.
- Tes: `tests/test_grid.py`, `tests/test_check_features.py`. Total `pytest -q`: 29 passed.

**Cara pengolahan**

- Sentinel-2: median 2020 dengan masker Cloud Score+ (`cs_cdf` ≥ 0,60), NDVI, EVI, dan tekstur GLCM (contrast,
  entropy, variance) dari B8 × 255 (uint8) dengan ukuran 3, sama dengan `cek_data_gee.js`.
- Sentinel-1: median VV, VH, dan VH − VV (dB). PALSAR-2: HH dan HV dikonversi ke dB.
- DEM: elevasi, elevasi low-pass (Gaussian radius 1500 m, σ 500 m), dan kemiringan.
- Data yang resolusinya lebih kasar dari 10 m (B11/B12 20 m, PALSAR-2 25 m, DEM 30 m) di-resample **bilinear** per
  citra sebelum dikomposit. Resampling bawaan Earth Engine (nearest neighbour) membuat pola kotak-kotak dan artefak
  pada kemiringan.
- Elevasi low-pass dihitung di grid 100 m: DEM 30 m dirata-rata ke 100 m, dihaluskan Gaussian, lalu diinterpolasi
  bilinear ke 10 m. Dengan σ = 500 m hasilnya praktis sama dengan menghitung langsung di 10 m, tetapi sekitar 100×
  lebih ringan.

**Angka penting: smoke test** (jendela 11 × 11 km, dari `outputs/features/band_stats_smoke.json`)

- Ekspor ke Drive selesai (COMPLETED) dalam ±11 menit.
- 9 tile menutup grid 1.115 × 1.109 piksel dengan tepat tanpa masalah, dan ke-19 band 100% terisi.

| Band | Min | Max | Rata-rata | Std |
|---|---|---|---|---|
| B2 | 0,0159 | 0,0707 | 0,0371 | 0,0051 |
| B3 | 0,0281 | 0,1028 | 0,0508 | 0,0057 |
| B4 | 0,0138 | 0,0653 | 0,0306 | 0,0045 |
| B8 | 0,1700 | 0,4784 | 0,2754 | 0,0217 |
| B11 | 0,0804 | 0,1679 | 0,1151 | 0,0075 |
| B12 | 0,0342 | 0,0799 | 0,0504 | 0,0047 |
| NDVI | 0,6115 | 0,8986 | 0,7999 | 0,0266 |
| EVI | 0,3422 | 0,8250 | 0,5179 | 0,0371 |
| B8_contrast | 2,65 | 138,43 | 20,13 | 10,60 |
| B8_ent | 3,014 | 4,337 | 3,949 | 0,158 |
| B8_var | 1,64 | 278,24 | 16,42 | 10,84 |
| VV (dB) | −12,73 | −3,09 | −7,61 | 0,91 |
| VH (dB) | −18,74 | −9,55 | −13,52 | 0,82 |
| VH_minus_VV (dB) | −8,92 | −2,78 | −5,91 | 0,62 |
| HH_dB | −15,64 | 1,23 | −6,79 | 1,35 |
| HV_dB | −19,62 | −3,69 | −11,19 | 1,34 |
| elevation (m) | 8,07 | 33,32 | 22,70 | 3,13 |
| elevation_lowpass (m) | 16,36 | 28,36 | 22,68 | 2,63 |
| slope (°) | 0,0016 | 12,70 | 2,32 | 1,38 |

Nilai-nilai ini wajar untuk hutan rawa gambut yang rapat: NDVI tinggi, NIR sekitar 0,28, dan backscatter radar khas
hutan. Rentang elevasi low-pass 16–28 m menggambarkan bentuk kubah gambut.

**Keputusan**

1. Satu grid kerja (`src/grid.py`) dengan titik awal di kelipatan 10 m untuk fitur, label, dan patch.
2. Resampling bilinear untuk input yang lebih kasar dari 10 m. Elevasi low-pass dihitung di grid 100 m.
3. Laut tidak di-mask di stack fitur (opsi a), karena U-Net butuh input lengkap, termasuk di sungai. Patch yang
   sebagian besar air dibuang di Fase 4 dengan bantuan WorldCover.
4. Ekspor float32 (lossless), sekitar 7,23 GB untuk AOI penuh. Disetujui 16 Oktober 2026.
5. Ekspor Earth Engine masuk ke Drive milik akun Earth Engine, yang bukan akun Google Drive for desktop di laptop
   ini. Karena itu file smoke untuk pengecekan diambil langsung dari Earth Engine (`--download`), dengan citra dan
   grid yang sama persis dengan ekspor Drive.

**Belum selesai**

- Ekspor AOI penuh sedang berjalan (task `T4TUZGCGIHAOBJER6MK7G2HL`, mulai 16 Oktober 2026 pukul 11.07). Setelah
  selesai, keenam tile perlu diverifikasi dengan `check_features.py`. Untuk
  itu dibutuhkan akses ke Drive akun Earth Engine: tambahkan akun itu ke Google Drive for desktop, atau periksa dari
  Colab.
