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
| 03 | Koreksi perspektif | belum | Buat fungsi yang menerima foto asli dan empat sudut dari detektor atau pilihan manual. Hitung homografi ke halaman persegi panjang dan lakukan warp pada foto asli. Detektor sudah memetakan titik ke resolusi asli, sehingga titik dapat langsung dipakai. Uji foto sintetis miring berpenanda untuk memeriksa orientasi, posisi isi, dan resolusi hasil. Titik tidak valid harus menghasilkan kegagalan eksplisit. |
| 04 | Perbaikan pencahayaan dan ketajaman | belum | Pada halaman yang sudah lurus, terapkan estimasi latar untuk mengurangi bayangan, CLAHE untuk kontras, dan unsharp mask untuk ketajaman. Uji dengan halaman sintetis berbayang dan bandingkan hasil dengan halaman referensi. Pertahankan jalur keluaran warna. |
| 05 | Binarisasi | belum | Sediakan fungsi dengan adaptive threshold sebagai default dan Otsu sebagai pembanding. Uji keduanya pada halaman sintetis dengan pencahayaan tidak merata. Periksa dimensi hasil dan nilai piksel hitam-putih. |
| 06 | Ekspor PDF | belum | Ekspor satu atau beberapa halaman dalam mode warna, grayscale, atau hitam-putih. Buka kembali PDF hasil uji dan periksa jumlah halaman, urutan penanda halaman, serta tampilan sesuai mode yang dipilih. |
| 07 | Kamera dan impor foto di browser | belum | Pengguna dapat mengambil foto atau memilih berkas lokal. Tangani izin kamera yang ditolak dengan menyediakan impor foto. Uji penolakan izin dan foto dengan orientasi EXIF yang diputar. Dokumentasikan perintah instalasi, start, build, dan tes yang berlaku saat memperkenalkan toolchain web. |
| 08 | Pratinjau dan koreksi sudut manual | belum | Tampilkan sudut deteksi di atas foto. Jika hasilnya `None`, minta pengguna menentukan empat sudut. Pengguna juga dapat mengoreksi deteksi yang keliru. Uji alur dari deteksi gagal sampai warp berhasil, termasuk pemetaan titik pratinjau ke piksel foto asli. |
| 09 | Alur pemindaian hingga unduh | belum | Hubungkan halaman terkoreksi, pilihan mode, penambahan dan pengurutan halaman, serta unduhan PDF. Uji alur browser dengan dua halaman sintetis yang ditukar urutannya dan cocokkan PDF unduhan dengan pratinjau. |
| 10 | Evaluasi alur lengkap | belum | Dokumentasikan lokasi dataset, variasi cahaya, latar dan sudut, serta cara mengulang evaluasi. Laporkan PSNR/SSIM terhadap referensi, akurasi OCR terhadap transkripsi acuan, dan waktu proses. Catat keterbatasan pada kertas melengkung atau terlipat, latar sewarna, cahaya ekstrem, dan silau. |

## Verifikasi selama pengerjaan

- Untuk setiap perubahan metode atau parameter pipeline, dokumentasikan perbandingan sebelum dan sesudah pada sampel sintetis yang sama dalam perubahan tersebut. Gunakan halaman referensi atau keluaran tahap sebelumnya sebagai pembanding saat menambahkan tahap baru. [Evaluasi awal detektor](../README.md#initial-evaluation)
- Untuk perubahan kamera atau tata letak, jalankan alurnya di browser seluler dan catat browser yang dipakai. Sertakan tangkapan layar dengan dokumen sintetis pada PR antarmuka.
- Gunakan fixture sintetis untuk tes. Proses gambar secara lokal, hindari layanan eksternal untuk gambar, dan jaga agar dokumen pengguna tidak masuk ke repositori.
