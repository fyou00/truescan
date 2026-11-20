# Evaluasi perbaikan halaman

Jalankan perintah berikut dari root repo dalam virtual environment proyek.

```sh
python -m evaluation.enhancement
```

[Generator dataset dan pengukuran](../evaluation/enhancement.py) membuat satu halaman warna sintetis 640 × 480 piksel dengan empat baris teks tipis, garis, dan blok warna. Dua variasi pencahayaan mengalikan intensitas halaman dengan gradien samping dan bayangan berbentuk Gaussian. Keduanya mencapai intensitas minimum 55% dari acuan. Halaman dengan cahaya merata menjadi kontrol. Seluruh sampel dibuat dalam memori.

| Pencahayaan | PSNR warna sebelum → sesudah (dB) | SSIM grayscale sebelum → sesudah | Rentang kecerahan kertas sebelum → sesudah | Waktu median |
| --- | --- | --- | --- | --- |
| Merata | ∞ → 39,27 | 1,0000 → 0,9990 | 0 → 0 | 22,52 ms |
| Gradien samping | 12,22 → 32,05 | 0,9456 → 0,9982 | 100 → 1 | 20,15 ms |
| Bayangan lokal | 16,44 → 38,76 | 0,9748 → 0,9923 | 90 → 3 | 21,99 ms |

Kolom sebelum dan sesudah memakai acuan yang sama, yaitu halaman dengan cahaya merata. PSNR membandingkan seluruh kanal BGR. SSIM memakai jendela Gaussian 11 × 11 dengan sigma 1,5 pada grayscale serta mengabaikan batas selebar lima piksel. Rentang kecerahan mengukur selisih persentil 95 dan 5 di piksel kertas kosong menurut acuan, pada skala 0–255. Waktu lokal memakai OpenCV 5.1.0 dan median sepuluh pemanggilan setelah satu pemanasan.

Kedua sampel berbayang menjadi lebih dekat ke acuan. Pada kontrol dengan cahaya merata, pengaturan kontras dan ketajaman sedikit mengubah tampilan tinta. Evaluasi ini mengisolasi tahap 04 pada halaman datar yang sudah lurus. Akurasi OCR, lipatan kertas, dan silau berada di luar pengukuran ini.
