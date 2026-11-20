# Rencana pengerjaan TrueScan

TrueScan memindai dokumen dari kamera atau foto lokal, meluruskan dan memperjelas halaman, lalu mengekspornya sebagai PDF. Fungsi pemrosesan gambar dan ekspor berjalan di Python dan dapat diuji terpisah dari interaksi browser. Ikuti [panduan repositori](../AGENTS.md) dan lihat [README](../README.md) untuk cara menjalankan kode.

## Cara menjalankan satu item

1. Saat diminta **“kerjakan item berikutnya di PLAN.md”**, jalankan `git status --short` dan baca tabel dari atas. Lanjutkan item berstatus `sedang`. Jika tidak ada, ambil item `belum` pertama dan ubah statusnya menjadi `sedang`. Kerjakan satu item per permintaan.
2. Gunakan kolom kriteria selesai sebagai target. Jalankan tes yang relevan dan suite Python dengan `python -m unittest discover -s tests -v` dari root repo dalam virtual environment proyek.
3. Setelah kriteria terpenuhi dan verifikasi lulus, ubah status menjadi `selesai` dan cantumkan lokasi kode, tes, atau laporan pada baris tersebut. Jika pekerjaan terhenti, pertahankan status `sedang` dan tulis hasil terakhir, kendala, serta langkah lanjutan di baris yang sama.
4. Setelah menyelesaikan satu item, tambahkan satu fitur lanjutan yang belum tercakup di akhir tabel dengan status `belum` dan kriteria yang bisa diuji.
5. Buat commit untuk setiap perubahan yang utuh dengan subjek imperatif dalam bahasa Inggris. Stage hanya berkas terkait dan jalankan `git diff --cached --check` sebelum commit.

## Urutan pengerjaan

| Item | Tahap | Status | Kriteria selesai dan bukti |
| --- | --- | --- | --- |
| 01 | Praproses | selesai | `_prepare_detection_image` membatasi sisi terpanjang hingga 800 piksel, mengubah gambar berwarna menjadi grayscale, dan menerapkan Gaussian blur. Fungsi ini digunakan oleh detektor dan tercakup melalui [tes deteksi](../tests/test_corners.py). [Implementasi](../truescan/corners.py) |
| 02 | Deteksi empat sudut | selesai | `detectCorners` memakai Canny, penutupan morfologis, lalu memilih kontur terbesar yang memenuhi kriteria segi empat cembung dengan `approxPolyDP`. Hasilnya empat titik dalam koordinat foto asli, berurutan kiri atas, kanan atas, kanan bawah, kiri bawah. Hasil `None` menandakan deteksi gagal. [Kode](../truescan/corners.py) dan [tes dokumen lurus, miring, dan tanpa batas terlihat](../tests/test_corners.py) |
| 03 | Koreksi perspektif | selesai | [correctPerspective](../truescan/perspective.py) meluruskan foto asli dari empat sudut otomatis atau manual. [Tes sintetis](../tests/test_perspective.py) memverifikasi posisi penanda, resolusi, pemilihan manual, dan penolakan geometri tidak valid. [Perbandingan crop dan warp](../README.md#perspective-correction) |
| 04 | Perbaikan pencahayaan dan ketajaman | selesai | [enhancePage](../truescan/enhance.py) mengurangi bayangan, memperbaiki kontras dengan CLAHE, dan menajamkan detail dengan unsharp mask. [Tes sintetis](../tests/test_enhance.py) memeriksa latar, teks tipis, warna, dan alpha. [Evaluasi sebelum dan sesudah](ENHANCEMENT.md) |
| 05 | Binarisasi | selesai | [binarizePage](../truescan/binarize.py) menghasilkan satu kanal hitam-putih dengan ambang adaptif Gaussian atau Otsu. [Tes sintetis](../tests/test_binarize.py) mencakup cahaya tidak merata, format kanal, dan nilai piksel. [Perbandingan hasil](BINARIZATION.md) |
| 06 | Ekspor PDF | selesai | [exportPdf](../truescan/pdf.py) menyusun halaman dalam urutan yang dipilih pada mode warna, grayscale, atau hitam-putih. [Tes render PDFium](../tests/test_pdf.py) memeriksa ukuran dan isi. [Verifikasi alur gambar ke PDF](PDF_EXPORT.md) |
| 07 | Kamera dan impor foto di browser | belum | Pengguna dapat mengambil foto atau memilih berkas lokal. Tangani izin kamera yang ditolak dengan menyediakan impor foto. Uji penolakan izin dan foto dengan orientasi EXIF yang diputar. Dokumentasikan perintah instalasi, start, build, dan tes yang berlaku saat memperkenalkan toolchain web. |
| 08 | Pratinjau dan koreksi sudut manual | belum | Tampilkan sudut deteksi di atas foto. Jika hasilnya `None`, minta pengguna menentukan empat sudut. Pengguna juga dapat mengoreksi deteksi yang keliru. Uji alur dari deteksi gagal sampai warp berhasil, termasuk pemetaan titik pratinjau ke piksel foto asli. |
| 09 | Alur pemindaian hingga unduh | belum | Hubungkan halaman terkoreksi, pilihan mode, penambahan dan pengurutan halaman, serta unduhan PDF. Uji alur browser dengan dua halaman sintetis yang ditukar urutannya dan cocokkan PDF unduhan dengan pratinjau. |
| 10 | Evaluasi alur lengkap | belum | Dokumentasikan lokasi dataset, variasi cahaya, latar dan sudut, serta cara mengulang evaluasi. Laporkan PSNR/SSIM terhadap referensi, akurasi OCR terhadap transkripsi acuan, dan waktu proses. Catat keterbatasan pada kertas melengkung atau terlipat, latar sewarna, cahaya ekstrem, dan silau. |
| 11 | Rotasi halaman sebelum ekspor | belum | Pengguna dapat memutar satu halaman 90° di pratinjau. Uji dua halaman dengan penanda arah dan pastikan hanya halaman terpilih yang berubah orientasi pada pratinjau dan PDF. |
| 12 | Hapus halaman sebelum ekspor | belum | Pengguna dapat menghapus hasil pemindaian yang keliru dari pratinjau. Uji penghapusan halaman tengah dari tiga halaman dan pastikan dua halaman yang tersisa muncul di PDF dalam urutan semula. |
| 13 | Beri nama berkas PDF | belum | Pengguna dapat mengisi nama dokumen sebelum mengunduh PDF. Uji nama dengan spasi, ekstensi .pdf, dan kolom kosong yang menghasilkan nama bawaan. |
| 14 | Ekspor pada kertas A4 | belum | Pengguna dapat memilih ukuran A4 saat mengekspor. Buka kembali PDF dan periksa ukuran halaman, rasio aspek, serta keutuhan keempat penanda sudut pada foto potret dan lanskap. |

## Verifikasi selama pengerjaan

- Untuk setiap perubahan metode atau parameter pipeline, dokumentasikan perbandingan sebelum dan sesudah pada sampel sintetis yang sama dalam perubahan tersebut. Gunakan halaman referensi atau keluaran tahap sebelumnya sebagai pembanding saat menambahkan tahap baru. [Evaluasi awal detektor](../README.md#initial-evaluation)
- Untuk perubahan kamera atau tata letak, jalankan alurnya di browser seluler dan catat browser yang dipakai. Sertakan tangkapan layar dengan dokumen sintetis pada PR antarmuka.
- Gunakan fixture sintetis untuk tes. Proses gambar secara lokal, hindari layanan eksternal untuk gambar, dan jaga agar dokumen pengguna tidak masuk ke repositori.
