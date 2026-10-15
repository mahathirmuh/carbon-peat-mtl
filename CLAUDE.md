# CLAUDE.md — Estimasi Stok Karbon Hutan Rawa Gambut Kalimantan

## Tentang proyek

Final project mata kuliah Pengolahan Citra (S2 Informatika ITS) — Mahathir Muhammad (6025252008).

**Judul kerja:** Multi-task Attention U-Net untuk Estimasi Stok Karbon di Kalimantan Tengah: Regresi Biomassa
Atas Permukaan dan Segmentasi Kedalaman Gambut dari Citra Optik dan SAR serta DEM.

**Tujuan:** memetakan stok karbon atas permukaan (AGC) dan karbon gambut (SOC) hutan rawa gambut
Kalimantan dari citra satelit gratis, memakai **satu model Multi-task Attention U-Net** dengan tiga keluaran:

1. **Head 1 — tinggi kanopi** (regresi, label GEDI L2A `rh98`)
2. **Head 2 — biomassa / AGB** (regresi, label GEDI L4A `agbd`)
3. **Head 3 — kelas kedalaman gambut** (segmentasi, label peta gambut Kementan)

**Hipotesis yang diuji:** model yang mempelajari biomassa dan kedalaman gambut sekaligus lebih akurat
daripada model single-task. Bagian AGC sendiri mengikuti SOTA (Perpinyà-Vallès et al., 2025), jadi
jangan diklaim sebagai kebaruan.

**Area & waktu:** AOI awal lanskap Katingan–Mentaya, Kalimantan Tengah
(bbox `[112.8, -3.4, 113.5, -2.3]`, lon/lat; ±77 × 122 km), tahun analisis 2020.
Proyeksi kerja **EPSG:32749** (UTM 49S), resolusi **10 m**.
Jendela kecil untuk smoke test: `[113.10, -2.90, 113.20, -2.80]` (±11 × 11 km; sama dengan jendela gambar
contoh di slide ETS).

Rencana kerja per fase ada di `PLAN.md`. Arti semua singkatan ada di bagian **Singkatan** di akhir file ini.

## Status (15 Oktober 2026)

- Desain di file ini adalah versi yang dipresentasikan di ETS (review literatur dan rencana final project).
- Ketersediaan data 2020 di AOI sudah dicek dengan `gee/cek_data_gee.js` di Code Editor. Hasilnya menjadi
  **angka acuan** untuk Fase 1:

| Data | Hasil cek 2020 |
|---|---|
| GEDI L4A lolos filter kualitas | 111.610 titik (dihitung sebagai piksel 25 m berisi footprint) |
| GEDI L2A lolos filter kualitas | 162.131 titik |
| Sentinel-2 SR | 365 citra; komposit median bebas awan menutup 99,9% AOI |
| Sentinel-1 GRD (IW, VV + VH) | 48 citra |
| ALOS PALSAR-2 | 1 mosaik tahunan |
| PEATGRIDS (rata-rata AOI) | tebal 275 cm; 0,243 Mg C/m² (≈ 2.430 Mg C/ha) |

- Peta gambut Kementan belum didapat (perlu surat permohonan) → sementara label Head 3 dari PEATGRIDS.
- Peta penutupan lahan KLHK belum ada di repo → sementara strata dari ESA WorldCover 2020.
- Implementasi dimulai dari Fase 0 di `PLAN.md`.

## Cara bekerja di proyek ini

- Kerjakan **satu fase `PLAN.md` dalam satu waktu**. Lanjut ke fase berikutnya hanya setelah kriteria
  "Selesai jika" terpenuhi dan saya menyetujuinya.
- Sebelum menulis kode besar, jelaskan rencananya singkat. Setelah selesai, jelaskan apa yang dibuat dan
  alasannya **dalam Bahasa Indonesia**. Saya harus bisa menjelaskannya ulang ke dosen.
- Uji setiap skrip di AOI kecil atau beberapa patch dulu (smoke test) sebelum menjalankan versi penuh.
- **Minta konfirmasi** sebelum: ekspor GEE berukuran besar, training lebih dari ±10 menit, menghapus data,
  atau mengubah keputusan metodologi di bawah.
- Commit git per langkah kecil dengan pesan yang jelas. Folder `data/` dan `outputs/` tidak di-commit.
- **Jangan pernah mengarang angka.** Semua angka untuk laporan harus berasal dari output skrip
  (`outputs/metrics/*.json`).
- Setelah tiap fase, tambahkan ringkasan ke `docs/progress.md`: apa yang dibuat, angka penting, masalah,
  dan keputusan yang diambil.
- Kode, nama variabel, dan komentar teknis dalam bahasa Inggris; penjelasan ke saya dalam Bahasa Indonesia.

## Keputusan metodologi (jangan diubah tanpa diskusi)

1. **Label sparse:** loss Head 1 dan Head 2 hanya dihitung di piksel yang punya titik GEDI valid
   (masked loss). Piksel tanpa GEDI **tidak boleh** diisi nol.
2. **Label dense:** Head 3 memakai cross-entropy per piksel dengan `ignore_index` untuk nodata.
3. **Peta kanopi ETH tidak boleh dipakai sebagai input.** Peta itu dilatih memakai GEDI 2019–2020 sehingga
   membocorkan data uji. Pakai hanya sebagai pembanding keluaran Head 1.
4. **Split spasial per blok**, bukan acak per piksel atau per patch: 70/15/15 train/val/test, plus spatial
   k-fold. Satu blok tidak boleh terbagi ke dua split.
5. **Pembanding:** Random Forest per tugas, Attention U-Net single-task per tugas, dan **ablasi head**
   (AGB + tinggi, AGB + gambut, tiga head) untuk memisahkan efek gambut dari efek tinggi; semuanya dengan
   split yang sama. Uji beda berpasangan antar-model per fold spasial (≥ 10 fold) atau block bootstrap;
   dengan 5 fold, uji Wilcoxon tidak mungkin mencapai p < 0,05.
6. **Konversi karbon:** AGC = AGB × 0,47 (IPCC). SOC = kedalaman × Cd × luas, dengan Cd = BD × C-organik
   = **61,6 kg C/m³** untuk Kalimantan Tengah (Warren et al., 2017, Tabel 1). Kedalaman per kelas mengikuti
   Warren et al. (2017): rendah = batas bawah, tengah = nilai tengah, tinggi = batas atas; kelas terbuka
   >300 cm = 300 / 750 / 1000 cm. Laporkan SOC versi tengah beserta rentang rendah–tinggi.
   PEATGRIDS sebagai pembanding SOC, kecuali bila dipakai sebagai label sementara Head 3 (hindari evaluasi sirkular).
7. **Peta penutupan lahan KLHK** hanya untuk strata analisis (ringkasan per tipe vegetasi), bukan target model.
8. **Validasi independen:** rata-rata AGB di area beririsan vs Umarhadi et al. (2026) = 239,9 t/ha.
   GEDI L4B 1 km dan peta ETH sama-sama turunan GEDI, jadi hanya **cek konsistensi**, bukan validasi independen.

## Data

### Google Earth Engine (ID sudah diverifikasi di katalog)

| Data | ID | Catatan |
|---|---|---|
| GEDI L4A (label Head 2) | `LARSE/GEDI/GEDI04_A_002_MONTHLY` | band `agbd` (Mg/ha); mask `l4_quality_flag == 1` dan `degrade_flag == 0`; 25 m |
| GEDI L2A (label Head 1) | `LARSE/GEDI/GEDI02_A_002_MONTHLY` | band `rh98` (m); mask `quality_flag == 1` dan `degrade_flag == 0`; 25 m |
| GEDI L4B (validasi) | `LARSE/GEDI/GEDI04_B_002` | AGBD grid 1 km |
| Sentinel-2 SR | `COPERNICUS/S2_SR_HARMONIZED` | B2, B3, B4, B8, B11, B12; bagi 10000; GLCM: B8 (reflektansi) × 255 → `toUint8()` → `glcmTexture({size: 3})`, ambil `B8_contrast`, `B8_ent`, `B8_var` |
| Cloud Score+ | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | `linkCollection(csPlus, ['cs_cdf'])`, mask `cs_cdf >= 0.60` |
| Sentinel-1 GRD | `COPERNICUS/S1_GRD` | mode IW, VV + VH (sudah dB); median tahunan; tanpa filter speckle spasial (median tahunan sudah meredam speckle) |
| ALOS PALSAR-2 tahunan | `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` | HH, HV dalam DN → γ⁰ (dB) = 10·log10(DN²) − 83.0; mask DN > 0; mosaic; 25 m |
| Copernicus DEM | `COPERNICUS/DEM/GLO30_2024_1` | koleksi tile, band `DEM` (DSM); `mosaic().setDefaultProjection(col.first().projection())` sebelum `ee.Terrain.slope`; DSM memuat tajuk, jadi tambahkan elevasi low-pass untuk bentuk kubah: `convolve(ee.Kernel.gaussian({radius: 1500, sigma: 500, units: 'meters'}))` |
| Peta kanopi ETH 2020 | `users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1` | **pembanding saja, bukan input** |
| PEATGRIDS | `projects/sat-io/open-datasets/PEATGRIDS/THICKNESS_CM`, `projects/sat-io/open-datasets/PEATGRIDS/C_STOCK_MGC_PER_M2` | `ee.Image`; band `THICKNESS_CM_MEAN`, `C_STOCK_MgC_per_m2_MEAN`; mask nilai < 0; 1 km |
| Batas kabupaten | `FAO/GAUL/2015/level2` | opsional untuk AOI |
| ESA WorldCover 2020 | `ESA/WorldCover/v100` | strata **cadangan** bila peta KLHK belum ada; `ImageCollection` → `.first()`, band `Map`; 10 m; tidak membedakan hutan primer/sekunder |

### Di luar GEE (upload ke GEE Assets, path dicatat di `config/config.yaml`)

- **Peta Lahan Gambut Indonesia 1:50.000, Kementan (2019)** → label Head 3. Belum tersedia sampai
  permohonan data disetujui. Sementara itu pakai PEATGRIDS yang dikelaskan sebagai label sementara, dan
  tandai jelas `temporary_labels: true`.
- **Peta Penutupan Lahan KLHK 2020 (1:250.000)** → strata analisis tipe vegetasi. Selama belum didapat,
  pakai ESA WorldCover 2020 sebagai strata sementara.

### Stack input: 19 kanal (urutan tetap)

| No. | Sumber | Kanal |
|---|---|---|
| 1–6 | Sentinel-2 | B2, B3, B4, B8, B11, B12 (reflektansi 0–1) |
| 7–8 | Sentinel-2 | NDVI, EVI |
| 9–11 | Sentinel-2 | B8_contrast, B8_ent, B8_var (tekstur GLCM band NIR) |
| 12–14 | Sentinel-1 | VV, VH, VH − VV (dB) |
| 15–16 | PALSAR-2 | HH_dB, HV_dB |
| 17–19 | Copernicus DEM | elevasi, elevasi low-pass, kemiringan |

Semua kanal di-resample ke grid 10 m EPSG:32749, dinormalisasi z-score dengan mean/std **dari split train
saja**, lalu dipotong menjadi patch 256 × 256. Simpan urutan ini sebagai `bands:` di `config/config.yaml`.
Mengubah urutan atau jumlah kanal berarti `norm_stats.json` dan semua model harus dibuat ulang.

## Lingkungan

- Python 3.11, conda env `carbon-peat` (lihat `environment.yml`).
- Library utama: `earthengine-api`, `geemap`, `rasterio`, `numpy`, `pandas`, `scikit-learn`, `torch`,
  `pyyaml`, `matplotlib`, `tqdm`, `pytest`.
- Earth Engine: autentikasi sekali dengan `earthengine authenticate`, lalu
  `ee.Initialize(project=<gee_project dari config>)`. Jangan menyimpan token atau kredensial di repo.
- Training penuh dijalankan di GPU (Colab atau server lab). Di laptop hanya smoke test di CPU.

## Struktur folder

```
carbon-peat-mtl/
├── CLAUDE.md
├── PLAN.md
├── README.md
├── environment.yml
├── config/config.yaml        # AOI, tahun, CRS, ID dataset, parameter model
├── gee/                      # skrip Earth Engine
│   ├── cek_data_gee.js       # Code Editor: cek ketersediaan data 2020 (sudah dijalankan)
│   ├── contoh_citra_slide.js # Code Editor: gambar contoh slide ETS (parameter fitur & visualisasi)
│   └── *.py                  # pipeline Python: cek data, fitur, label, ekspor
├── src/
│   ├── config.py
│   ├── datasets/             # pembuatan patch, split spasial, PyTorch Dataset
│   ├── models/               # attention_unet.py, multitask.py
│   ├── losses.py             # masked regression loss, cross-entropy
│   ├── train.py
│   ├── evaluate.py
│   ├── predict.py
│   └── carbon.py             # AGC, SOC, total, ringkasan per strata
├── baselines/                # random forest
├── notebooks/                # train_colab.ipynb, eksplorasi
├── scripts/                  # pembuat tabel dan gambar laporan
├── tests/
├── docs/progress.md
├── data/                     # (gitignored) raw/, labels/, patches/
└── outputs/                  # (gitignored) runs/, metrics/, maps/, figures/
```

## Perintah

```bash
conda env create -f environment.yml && conda activate carbon-peat
python gee/check_data.py --config config/config.yaml        # cek ketersediaan data
pytest -q                                                   # tes
python src/train.py --config config/config.yaml --mode multitask
python src/evaluate.py --config config/config.yaml --run outputs/runs/<nama_run>
```

## Yang perlu saya lengkapi

- ID proyek Cloud untuk Earth Engine (`gee_project`): `TODO`
- Folder Google Drive tujuan ekspor: `TODO`
- Lingkungan GPU (Colab / server lab): `TODO`
- Path asset peta gambut Kementan dan peta KLHK setelah di-upload: `TODO`
- Repo remote (mis. GitHub privat) untuk di-clone di Colab pada Fase 6: `TODO`

## Referensi kunci

- Perpinyà-Vallès et al. (2025). *Remote Sensing* 17(7):1268 — U-Net + GEDI untuk AGB. https://doi.org/10.3390/rs17071268
- Weber et al. (2025). *Remote Sensing* 17(9):1594 — model multi-task AGBD, tinggi, tutupan. https://doi.org/10.3390/rs17091594
- Umarhadi et al. (2026). *Remote Sensing* 18(16):2722 — AGB gambut Katingan–Mentaya. https://doi.org/10.3390/rs18162722
- Skye et al. (2026). *Biogeosciences* 23:2959–2983 — PeatDepth-ML. https://doi.org/10.5194/bg-23-2959-2026
- Rudiyanto et al. (2018). *Geoderma* 313:25–40 — ketebalan gambut dari DEM + radar. https://doi.org/10.1016/j.geoderma.2017.10.018
- Warren et al. (2017). *Carbon Balance and Management* 12 — kerapatan karbon gambut Indonesia. https://doi.org/10.1186/s13021-017-0080-2
- Lang et al. (2023). *Nature Ecology & Evolution* 7:1778–1789 — peta kanopi ETH. https://doi.org/10.1038/s41559-023-02206-6
- Oktay et al. (2018). Attention U-Net: Learning where to look for the pancreas. arXiv:1804.03999
- Kendall et al. (2018). Multi-task learning using uncertainty to weigh losses. arXiv:1705.07115

## Singkatan

| Singkatan | Kepanjangan |
|---|---|
| AGB | Aboveground Biomass — biomassa atas permukaan (Mg/ha) |
| AGBD | Aboveground Biomass Density — kerapatan biomassa; band `agbd` di GEDI L4A |
| AGC | Aboveground Carbon — karbon atas permukaan (Mg C/ha) |
| SOC | Soil Organic Carbon — karbon organik tanah, di sini karbon gambut |
| Cd | Carbon density — kerapatan karbon gambut (kg C/m³) = BD × kadar C-organik |
| BD | Bulk Density — berat isi tanah |
| GEDI | Global Ecosystem Dynamics Investigation — LiDAR satelit di Stasiun Luar Angkasa Internasional |
| L2A / L4A / L4B | produk GEDI Level 2A (tinggi per footprint) / Level 4A (biomassa per footprint) / Level 4B (biomassa grid 1 km) |
| rh98 | relative height 98% — tinggi kanopi dari GEDI L2A |
| LiDAR | Light Detection and Ranging — pengukuran jarak dengan laser |
| GEE | Google Earth Engine |
| SR | Surface Reflectance — reflektansi permukaan |
| NIR | Near Infrared — inframerah dekat (band B8 Sentinel-2) |
| NDVI | Normalized Difference Vegetation Index |
| EVI | Enhanced Vegetation Index |
| GLCM | Gray-Level Co-occurrence Matrix — dasar perhitungan tekstur |
| SAR | Synthetic Aperture Radar |
| GRD | Ground Range Detected — jenis produk Sentinel-1 |
| IW | Interferometric Wide swath — mode akuisisi Sentinel-1 |
| VV, VH, HH, HV | polarisasi radar kirim–terima (V = vertikal, H = horizontal) |
| ALOS | Advanced Land Observing Satellite (JAXA, Jepang) |
| PALSAR-2 | Phased Array type L-band Synthetic Aperture Radar-2 — radar L-band di ALOS-2 |
| DEM / DSM | Digital Elevation Model / Digital Surface Model (DSM ikut memuat tajuk) |
| UTM 49S, EPSG:32749 | Universal Transverse Mercator zona 49 Selatan; EPSG:32749 adalah kode sistem koordinatnya |
| AOI | Area of Interest — area kajian |
| PEATGRIDS | peta global ketebalan dan stok karbon gambut 1 km (Widyastuti et al., 2025) |
| ETH | ETH Zürich — pembuat peta tinggi kanopi global 10 m (Lang et al., 2023) |
| KLHK | Kementerian Lingkungan Hidup dan Kehutanan |
| Kementan | Kementerian Pertanian — penerbit Peta Lahan Gambut Indonesia 1:50.000 |
| IPCC | Intergovernmental Panel on Climate Change |
| RF | Random Forest |
| MTL | Multi-Task Learning (nama repo `carbon-peat-mtl`) |
| R², RMSE, MAE | koefisien determinasi, Root Mean Square Error, Mean Absolute Error |
| OA, F1, mIoU | Overall Accuracy, F1-score, mean Intersection over Union |
| Mg | megagram = ton |