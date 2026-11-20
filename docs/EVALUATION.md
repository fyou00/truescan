# Evaluasi foto hingga PDF

**Pada PDF warna, akurasi karakter naik dari 71,83% ke 92,17% (169 menjadi 47 kesalahan dari 600 karakter).** Enam dari delapan foto memakai sudut otomatis. Dua memakai titik acuan manual. Median waktu proses inti per halaman adalah 184,2 ms.

Tolok ukur ini menggunakan delapan foto sintetis dengan ukuran 960 × 850 piksel. Empat foto pertama menguji pemindaian kertas datar pada variasi cahaya, latar, dan sudut. Empat sisanya menguji batas metode. Semua halaman memakai satu tata letak, satu jenis huruf, dan enam baris bahasa Inggris. [Deskripsi dataset dan anotasi](../evaluation/dataset/README.md)

## Cara mengulang

Dari root repo, aktifkan virtual environment proyek dan pasang dependensi pengujian. Sediakan Tesseract 5 dengan data bahasa Inggris pada PATH. Perintah berikut memeriksa bahasanya, menulis dataset yang dapat diinspeksi, dan mengevaluasi tiga mode secara berurutan.

```sh
python -m pip install -r requirements-test.txt
tesseract --list-langs
python -m evaluation.dataset --output evaluation/dataset/generated
python -m evaluation.pipeline --mode color
python -m evaluation.pipeline --mode grayscale
python -m evaluation.pipeline --mode black-and-white
```

Dataset memiliki seed tetap. Runner membangkitkan sampel langsung di memori. Direktori keluaran berisi foto, referensi bersih, dan manifest anotasi. OCR berjalan lokal untuk evaluasi dan bersifat opsional bagi aplikasi. [Runner](../evaluation/pipeline.py)

## Metode

- **Sebelum** memakai potongan persegi panjang terkecil yang mencakup keempat sudut acuan, dengan pencahayaan dan perspektif dari foto.
- **Sesudah** menjalankan deteksi, koreksi perspektif pada resolusi asli, perbaikan halaman, konversi mode, ekspor PDF satu halaman, dan render ulang dengan PDFium pada 300 dpi. Jika sudut hilang atau simpangan titik terburuk melebihi 1% diagonal foto (12,82 px), runner memakai empat titik acuan sebagai simulasi pilihan manual. Pada aplikasi, pengguna yang menilai dan memperbaiki sudut.
- Kedua gambar disesuaikan ke ukuran referensi 600 × 720 piksel dengan interpolasi bilinear. PSNR mengukur perbedaan intensitas, SSIM mengukur kemiripan struktur pada luminansi. Mode hitam-putih memakai referensi bersih dengan ambang 128. PSNR antar-mode dapat merujuk pada target berbeda.
- Tesseract membaca satu blok teks Inggris dengan model LSTM. Skor membandingkan transkripsi setelah normalisasi Unicode NFKC dan spasi. Huruf besar dan tanda baca dihitung. CER adalah jumlah minimum sisipan, penghapusan, dan substitusi dibagi jumlah karakter acuan. Akurasi karakter adalah maksimum dari nol dan 1 − CER. Agregasi menjumlahkan kesalahan dan karakter sebelum menghitung persentase.
- Waktu per foto adalah median tiga pemindaian setelah satu pemanasan, dari deteksi sampai PDF selesai dirender kembali. Pengukuran mengecualikan interaksi pengguna, HTTP, pembuatan dataset, OCR, dan perhitungan metrik.

## Hasil per kondisi pada mode warna

Setiap baris berisi 75 karakter acuan. Pasangan angka menunjukkan sebelum → sesudah. Simpangan sudut adalah jarak terjauh antara titik otomatis dan titik acuan dalam foto.

| Skenario | Sudut | Simpangan (px) | PSNR (dB) | SSIM | Kesalahan OCR | Waktu (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| flat-dark | Otomatis | 0,12 | 48,62 → 35,47 | 0,9876 → 0,9690 | 0 → 0 | 206,9 |
| angled-side | Otomatis | 0,66 | 7,47 → 19,85 | 0,6524 → 0,9653 | 32 → 0 | 164,5 |
| angled-shadow | Otomatis | 1,05 | 8,25 → 25,13 | 0,6655 → 0,9647 | 28 → 0 | 178,1 |
| keystone-grain | Otomatis | 0,52 | 8,53 → 26,30 | 0,6853 → 0,9701 | 9 → 0 | 203,3 |
| curved-sheet | Otomatis | 0,12 | 10,73 → 11,56 | 0,7093 → 0,6950 | 11 → 7 | 190,4 |
| matching-paper | Manual | — | 13,17 → 31,17 | 0,7902 → 0,9789 | 21 → 0 | 159,0 |
| underexposure | Manual | — | 1,26 → 1,78 | 0,1102 → 0,1945 | 20 → 11 | 218,9 |
| glare | Otomatis | 1,05 | 9,39 → 16,14 | 0,7152 → 0,9066 | 48 → 29 | 93,6 |

## Perbandingan mode

PSNR dan SSIM berikut adalah rata-rata delapan skenario dengan bobot yang sama. Akurasi OCR dihitung atas semua 600 karakter. Untuk mode abu-abu dan hitam-putih, baseline OCR memakai potongan foto grayscale. Mode warna memakai potongan foto BGR.

| Mode | PSNR sebelum → sesudah (dB) | SSIM sebelum → sesudah | Akurasi karakter sebelum → sesudah | Kesalahan PDF | Waktu median (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warna | 13,43 → 20,93 | 0,6645 → 0,8305 | 71,83% → 92,17% | 47/600 | 184,2 |
| Abu-abu | 13,43 → 20,91 | 0,6645 → 0,8305 | 68,00% → 90,17% | 59/600 | 134,4 |
| Hitam-putih | 9,28 → 19,32 | 0,6531 → 0,9229 | 68,00% → 56,33% | 262/600 | 66,5 |

### Kondisi yang memengaruhi pembacaan

- Pada empat halaman datar standar, OCR warna membaik dari 69 kesalahan menjadi 0 dari 300 karakter. Halaman depan yang sudah terang memperlihatkan bahwa pengolahan dapat menurunkan PSNR sekalipun OCR sudah benar sejak awal.
- Empat sudut luar lembar melengkung masih terdeteksi dengan simpangan maksimum 0,12 piksel. Homografi merapikan batas, tetapi lengkungan teks tetap menghasilkan tujuh kesalahan pada PDF warna. Dataset mensimulasikan lengkungan. Lipatan tajam belum diukur tersendiri.
- Latar sewarna kertas menghilangkan garis batas. Hasil OCR warna menjadi tepat setelah runner memberikan sudut acuan. Pemotretan nyata tetap memerlukan penempatan sudut oleh pengguna.
- Pada foto sangat gelap, pemakaian sudut acuan masih menyisakan 11 kesalahan OCR warna. Pada keluaran hitam-putih terdapat 172 kesalahan untuk 75 karakter, termasuk karakter tambahan. Karena itu akurasi OCR hitam-putih untuk seluruh dataset turun menjadi 56,33% meskipun SSIM rata-ratanya meningkat.
- Pada foto bersilau, sudut terdeteksi tetapi pantulan menjenuhkan sebagian tinta. PDF warna masih mengandung 29 kesalahan dari 75 karakter.

Pengukuran lokal menggunakan Intel Core i5-8250U, macOS 15.8.2, OpenCV 5.1.0, PDFium melalui pypdfium2 5.15.2, fpdf2 2.9.0, dan Tesseract 5.5.4 (bahasa `eng`, OEM 1, PSM 6). SHA-256 model Inggris adalah `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`. Waktu merupakan median dari delapan median per skenario pada mesin ini. Dataset sintetis dan sudut acuan manual membatasi penerapan hasil ke foto kamera, dokumen berbahasa lain, atau tata letak lain.
