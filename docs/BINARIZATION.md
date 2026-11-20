# Evaluasi binarisasi

Jalankan `python -m evaluation.binarization` dari root repo dalam virtual environment proyek. [Generator](../evaluation/binarization.py) menggambar empat baris teks pada acuan biner 640 × 480 piksel. Untuk mensimulasikan foto, generator memberi warna abu-abu pada tinta (40 dan 150) dan kertas (240), lalu menambahkan sedikit blur, pencahayaan tidak merata, dan derau deterministik. Kedua sampel melewati `enhancePage` sebelum binarisasi.

| Pencahayaan | Hasil | PSNR (dB) | SSIM | F1 piksel tinta | Waktu binarisasi |
| --- | --- | ---: | ---: | ---: | ---: |
| Gradien samping | Grayscale tahap 04 | 18,88 | 0,8289 | 0,7280 | — |
| Gradien samping | Adaptif awal, C=7 | 15,25 | 0,3542 | 0,6744 | — |
| Gradien samping | Adaptif, C=14 | 41,45 | 0,9979 | 0,9988 | 2,34 ms |
| Gradien samping | Otsu | 28,88 | 0,9934 | 0,9786 | 0,26 ms |
| Bayangan lokal | Grayscale tahap 04 | 19,52 | 0,8518 | 0,7275 | — |
| Bayangan lokal | Adaptif awal, C=7 | 16,50 | 0,4628 | 0,7338 | — |
| Bayangan lokal | Adaptif, C=14 | 40,25 | 0,9958 | 0,9985 | 2,46 ms |
| Bayangan lokal | Otsu | 29,13 | 0,9939 | 0,9798 | 0,26 ms |

PSNR dan SSIM membandingkan intensitas dengan acuan biner. F1 menilai kecocokan posisi tinta dengan mengelompokkan nilai di bawah 128 sebagai tinta. Kolom waktu memakai median sepuluh pemanggilan binarisasi setelah satu pemanasan, pada OpenCV 5.1.0.

Pada dua sampel ini, menaikkan offset dari 7 ke 14 pada jendela Gaussian 31 × 31 mengurangi bintik tinta palsu. Parameter dipilih menggunakan kedua sampel ini sehingga hasilnya perlu diuji lagi pada dokumen lain. Goresan yang nyaris sewarna kertas dapat hilang ketika offset naik. Bagian dalam blok tinta yang lebih besar daripada jendela lokal juga dapat memutih. Otsu tersedia sebagai pembanding. Akurasi OCR dan hasil pada foto kamera belum diukur.
