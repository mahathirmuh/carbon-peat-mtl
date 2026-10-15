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

**Belum selesai**

- **Earth Engine belum terinisialisasi** karena `gee_project` masih TODO. Ini satu-satunya kriteria Fase 0 yang
  belum terpenuhi. Login (`earthengine authenticate`) sudah dilakukan pada 15 Oktober 2026, dan tokennya tersimpan
  di profil Windows (`~/.config/earthengine`), bukan di repo. Tinggal mengisi `gee_project` di
  `config/config.yaml`, lalu menjalankan `python gee/auth_check.py`.
- `drive_folder` serta path asset Kementan dan KLHK masih TODO.
