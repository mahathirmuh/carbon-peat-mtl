# PLAN.md — Rencana Implementasi

Kerjakan **berurutan**. Setiap fase berisi tugas, output, dan kriteria "Selesai jika".
Setelah satu fase selesai: perbarui `docs/progress.md`, commit, lalu tunggu persetujuan sebelum lanjut.
Semua keputusan metodologi mengikuti `CLAUDE.md`.

---

## Fase 0 — Setup proyek

**Tugas**
- Buat struktur folder sesuai `CLAUDE.md`, `.gitignore` (`data/`, `outputs/`, `*.tif`, `.env`),
  `environment.yml`, dan `README.md` singkat.
- Buat `config/config.yaml` berisi: `gee_project`, `aoi_bbox`, `year`, `crs` (EPSG:32749), `scale` (10),
  semua ID dataset dari `CLAUDE.md`, `bands` (19 kanal berurutan sesuai tabel di `CLAUDE.md`), `smoke_bbox`,
  ambang `cs_cdf` (0.60), `patch_size` (256), `block_size_m` (5000),
  rasio split (0.70/0.15/0.15), `seed`, bobot loss `lambdas` (1, 1, 1), `peat_cd_kgc_m3` (61.6), dan
  `peat_classes`: kode kelas → kedalaman rendah/tengah/tinggi (m). Isi awal memakai skema kelas Kementan yang
  dipakai Warren et al. (2017): <50 cm / bukan gambut → kelas 0, kedalaman 0; 50–100 cm → 0.5/0.75/1.0;
  100–200 cm → 1.0/1.5/2.0; 200–300 cm → 2.0/2.5/3.0; >300 cm → 3.0/7.5/10.0.
  Sesuaikan dengan skema kelas peta Kementan 2019 saat peta diterima.
- Buat `src/config.py` untuk membaca config.
- Buat `gee/auth_check.py`: inisialisasi Earth Engine dengan `gee_project` dan cetak info singkat.

**Output:** repo siap; `python gee/auth_check.py` berhasil.

**Selesai jika:** environment terpasang, Earth Engine terinisialisasi, `pytest -q` berjalan.

---

## Fase 1 — Cek dan eksplorasi data

**Tugas**
- `gee/cek_data_gee.js` sudah dijalankan di Code Editor (15 Oktober 2026); hasilnya ada di `CLAUDE.md`,
  bagian Status.
- Port skrip itu ke Python `gee/check_data.py`:
  hitung jumlah citra Sentinel-2 dan Sentinel-1, tile PALSAR-2, titik GEDI L4A dan L2A berkualitas,
  fraksi AOI yang terisi komposit Sentinel-2, serta rata-rata PEATGRIDS.
  Simpan ke `outputs/data_check/summary.json`.
- Simpan quick-look PNG (Sentinel-2 RGB, Sentinel-1 VH, PALSAR-2 HV, DEM, titik GEDI) ke
  `outputs/data_check/` memakai `getThumbURL` atau geemap.

**Output:** `summary.json` dan quick-look PNG.

**Selesai jika:** jumlah citra dan titik GEDI dilaporkan dan dibandingkan dengan angka acuan di `CLAUDE.md`;
selisih besar dijelaskan sebabnya (filter, AOI, atau cara hitung). Kalau titik GEDI terlalu sedikit untuk training,
usulkan opsi (perluas AOI atau tambah tahun 2021–2022) dan diskusikan dulu sebelum mengubah config.

---

## Fase 2 — Stack fitur input (GEE)

**Tugas**
- `gee/build_features.py`:
  - Sentinel-2: komposit median dengan masker Cloud Score+; NDVI, EVI; tekstur GLCM (contrast, entropy,
    variance) dari band NIR: reflektansi B8 × 255 → `toUint8()` → `glcmTexture({size: 3})`, sama dengan
    `gee/cek_data_gee.js`.
  - Sentinel-1: median VV, VH, dan VH − VV.
  - PALSAR-2: HH dan HV dalam dB (rumus di `CLAUDE.md`).
  - DEM: elevasi, elevasi yang dihaluskan (low-pass Gaussian radius 1500 m, σ 500 m, seperti
    `gee/contoh_citra_slide.js`; dipakai untuk bentuk kubah karena DEM ini DSM yang memuat tajuk), dan kemiringan.
  - Total **19 band** dengan nama dan urutan persis seperti tabel di `CLAUDE.md`.
  - Semua di-resample ke 10 m, EPSG:32749, dengan urutan band tetap.
- Ekspor ke Google Drive per tile (`ee.batch.Export.image.toDrive`, `fileDimensions`), float32 atau int16
  berskala (catat faktor skala di config).
- **Smoke test** di jendela kecil `smoke_bbox` = `[113.10, -2.90, 113.20, -2.80]` (±11 × 11 km) sebelum AOI penuh.

**Output:** `data/raw/features_*.tif` dan `outputs/features/band_list.json` (nama dan urutan band).

**Selesai jika:** GeoTIFF terbuka di rasterio/QGIS, semua band terisi, statistik per band tercatat.

**Catatan ukuran:** AOI penuh (±77 × 122 km ≈ 94 juta piksel 10 m) dengan 19 band berukuran ±7 GB dalam float32
atau ±3,6 GB dalam int16 berskala.
Cek kuota Drive dan pertimbangkan int16.

---

## Fase 3 — Label dan strata

**Tugas**
- `gee/build_labels.py`:
  - Raster GEDI L4A `agbd` dan L2A `rh98` (dengan mask kualitas) pada grid 10 m yang sama dengan stack fitur;
    nodata di luar footprint.
  - Raster kelas kedalaman gambut dari asset Kementan (mapping kelas → indeks dan nilai tengah di config).
    Jika asset belum ada: buat label sementara dari PEATGRIDS `THICKNESS_CM_MEAN` yang dikelaskan dengan
    batas kelas yang sama, dan set `temporary_labels: true` (selama itu PEATGRIDS tidak dipakai sebagai
    pembanding SOC).
  - Raster strata penutupan lahan KLHK.
- Ekspor dengan CRS, transform, dan ukuran yang identik dengan stack fitur.
- **Perlu diputuskan bersama, jangan dipilih diam-diam:** satu footprint GEDI (piksel 25 m) menempati ±6 piksel
  di grid 10 m. Usulan: saat training, label dipakai di semua piksel footprint; saat evaluasi, metrik dihitung
  per footprint (rata-rata prediksi di dalam footprint), agar satu footprint tidak terhitung ±6 kali dan uji beda
  tidak terlalu optimis.

**Output:** `data/labels/*.tif` dan `outputs/labels/label_stats.json` (jumlah piksel GEDI, distribusi kelas).

**Selesai jika:** ada tes otomatis yang memastikan label dan fitur sejajar piksel demi piksel
(CRS, transform, dan ukuran sama).

---

## Fase 4 — Patch dan split spasial

**Tugas**
- `src/datasets/make_patches.py`: potong stack dan label menjadi patch 256 × 256 (stride 256).
- Bagi AOI ke blok persegi (default 5 km). Acak blok dengan seed tetap ke train/val/test 70/15/15.
  Setiap patch ikut split dari blok tempat pusatnya berada; buang patch yang memotong batas dua split.
- Hitung normalisasi per band (mean/std) **hanya dari train** → `outputs/norm_stats.json`.
- `src/datasets/dataset.py`: PyTorch Dataset yang mengembalikan input, label tinggi, label AGB, mask GEDI,
  dan label kelas gambut.

**Output:** `data/patches/manifest.csv` (patch_id, block_id, split, jumlah piksel GEDI, kelas dominan).

**Selesai jika:** ada tes yang memastikan tidak ada `block_id` di dua split, dan jumlah titik GEDI per split
dilaporkan.

---

## Fase 5 — Baseline

**Tugas**
- `baselines/random_forest.py`: RF regresi untuk tinggi dan AGB (sampel = piksel GEDI), RF klasifikasi untuk
  kelas gambut (sampel acak piksel berlabel). Fitur = band stack. Evaluasi di split test.
- `src/models/attention_unet.py`: Attention U-Net (Oktay et al., 2018) dengan jumlah kanal input dan output
  sebagai parameter.
- Latih tiga model single-task (tinggi, AGB, gambut) dengan pengaturan yang sama dengan model multi-task nanti.

**Output:** `outputs/metrics/baseline_*.json`.

**Selesai jika:** metrik semua baseline tercatat pada split test yang sama.

---

## Fase 6 — Multi-task Attention U-Net

**Tugas**
- `src/models/multitask.py`: encoder–decoder Attention U-Net bersama + tiga head konvolusi 1 × 1:
  tinggi (1 kanal), AGB (1 kanal), kelas gambut (K kanal).
- `src/losses.py`: masked Huber/MSE untuk tinggi dan AGB (hanya piksel GEDI), cross-entropy dengan
  `ignore_index` untuk gambut. Total L = λ1·L_tinggi + λ2·L_AGB + λ3·L_gambut (λ dari config;
  opsi uncertainty weighting Kendall et al., 2018).
- `src/train.py`: training loop, early stopping berdasarkan val, simpan checkpoint dan log ke
  `outputs/runs/<run>`; argumen `--mode single|multitask` dan `--task`.
- **Smoke test CPU:** 2 epoch pada 8 patch; pastikan loss turun dan tidak NaN.
- `notebooks/train_colab.ipynb`: clone repo, mount Drive, jalankan `train.py` di GPU Colab.
- Ablasi input: tanpa DEM; hanya optik; hanya SAR.
- Ablasi head: AGB + tinggi, AGB + gambut, dan tiga head, untuk memisahkan efek gambut dari efek tinggi.

**Output:** model terbaik dan `outputs/metrics/multitask_*.json`.

**Selesai jika:** perbandingan multi-task vs single-task vs RF, plus ablasi head, tersaji dalam satu tabel pada
split test yang sama, dengan uji beda berpasangan antar-fold (≥ 10 fold atau block bootstrap).

---

## Fase 7 — Evaluasi dan peta karbon

**Tugas**
- `src/evaluate.py`: R², RMSE, MAE untuk tinggi dan AGB di piksel GEDI test; OA, F1 makro, mIoU, dan
  confusion matrix untuk kelas gambut.
- `src/predict.py`: prediksi seluruh AOI dengan sliding window ber-overlap → peta tinggi, AGB, kelas gambut.
- `src/carbon.py`: AGC = AGB × 0,47; SOC = kedalaman × Cd × luas piksel (Cd = `peat_cd_kgc_m3`), dihitung
  untuk kedalaman rendah, tengah, dan tinggi dari `peat_classes`; total karbon (versi tengah + rentang);
  ringkasan (rata-rata dan total) per strata KLHK.
- Validasi independen: rata-rata AGB hutan di area beririsan vs 239,9 t/ha (Umarhadi et al., 2026).
- Cek konsistensi (turunan GEDI, bukan validasi independen): GEDI L4B (agregasi 1 km); tinggi vs peta ETH.
- SOC: uji kewajaran vs Warren et al. (2017); vs PEATGRIDS hanya bila `temporary_labels: false`.

**Output:** `outputs/maps/*.tif`, `outputs/metrics/final.json`, `outputs/figures/*.png`.

**Selesai jika:** semua metrik ada di `final.json` dan peta terbuka benar di QGIS.

---

## Fase 8 — Bahan laporan

**Tugas**
- `scripts/make_figures.py` dan `scripts/make_tables.py`: tabel perbandingan model, ablasi, ringkasan karbon
  per tipe vegetasi; peta dan scatter plot prediksi vs GEDI.
- Tulis temuan dan keterbatasan di `docs/progress.md`: label GEDI adalah estimasi model, label gambut
  mengikuti peta 1:50.000, dan SOC tanpa data lapangan.

**Selesai jika:** semua tabel dan gambar bisa dibuat ulang dengan satu perintah.

---

## Risiko dan cadangan

| Risiko | Cadangan |
|---|---|
| Peta gambut Kementan belum didapat | Label sementara dari PEATGRIDS (Fase 3), ganti saat peta tersedia |
| Peta penutupan lahan KLHK belum didapat | Strata sementara dari ESA WorldCover 2020 (`ESA/WorldCover/v100`) |
| Titik GEDI terlalu sedikit | Tambah tahun 2021–2022 atau perluas AOI (diskusikan dulu) |
| Kuota Drive atau Colab terbatas | AOI kecil, int16, baca patch on-the-fly |
| Awan tinggi di Sentinel-2 | Naikkan ambang `cs_cdf` atau perpanjang rentang komposit; radar tetap jadi tulang punggung |