# carbon-peat-mtl

Estimasi stok karbon hutan rawa gambut Kalimantan Tengah (karbon atas permukaan dan karbon gambut) dengan
satu **Multi-task Attention U-Net**: tinggi kanopi, biomassa (AGB), dan kelas kedalaman gambut, dari citra
Sentinel-2, Sentinel-1, ALOS PALSAR-2, dan Copernicus DEM.

Final project Pengolahan Citra, S2 Informatika ITS — Mahathir Muhammad (6025252008).

- Konteks, keputusan metodologi, dan data: [CLAUDE.md](CLAUDE.md)
- Rencana kerja per fase: [PLAN.md](PLAN.md)
- Catatan kemajuan: [docs/progress.md](docs/progress.md)

## Mulai

Di Windows, jalankan dari **Miniforge Prompt**.

```bash
conda env create -f environment.yml
conda activate carbon-peat
earthengine authenticate        # sekali saja, login lewat browser
# isi gee_project di config/config.yaml, lalu:
python gee/auth_check.py        # cek akses Earth Engine dan ID dataset
pytest -q                       # tes
```

## Struktur

| Folder | Isi |
|---|---|
| `config/` | `config.yaml`: AOI, tahun, CRS, ID dataset, urutan band, parameter split, loss, dan karbon |
| `gee/` | skrip Earth Engine: Code Editor (`.js`) dan pipeline Python |
| `src/` | kode utama: config, dataset, model, loss, training, evaluasi, prediksi, karbon |
| `baselines/` | Random Forest |
| `notebooks/` | notebook training di Colab |
| `scripts/` | skrip pendukung, pembuat tabel dan gambar laporan |
| `tests/` | tes `pytest` |
| `docs/` | catatan kemajuan |
| `data/`, `outputs/` | data dan hasil (tidak di-commit) |
