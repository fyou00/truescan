# Verifikasi ekspor PDF

Dua foto sintetis berukuran 800 × 600 piksel memuat halaman dengan label A dan B. Pada halaman A terdapat delapan garis biru di sisi kiri, sedangkan halaman B memuat delapan garis merah di sisi kanan. Keduanya diberi gradien cahaya dari 65% hingga 100% serta distorsi perspektif yang sama.

Foto diproses dengan `detectCorners`, `correctPerspective`, dan `enhancePage`. Hasil B dan A kemudian diberikan ke `exportPdf` dalam urutan tersebut untuk mode `color`, `grayscale`, dan `black-and-white`. Pembaca PDF independen, Apple Core Graphics, digunakan untuk menghitung halaman serta merender masing-masing ke RGB dengan lebar 600 piksel dan rasio aspek halaman asli.

Pengujian otomatis yang melengkapi pemeriksaan ini dapat diulang dengan `python -m unittest discover -s tests -p test_pdf.py -v` dalam virtual environment proyek.

## Hasil pembacaan ulang

Dua foto menghasilkan halaman terkoreksi berukuran 659 × 444 piksel. Ketiga PDF berisi dua halaman dan keenam render berukuran 600 × 404 piksel. Tabel menghitung piksel dengan grayscale di bawah 128 pada area garis, antara 37–70% tinggi halaman dan 5–95% lebarnya.

| Mode | Tinta kiri / kanan pada halaman 1 (B) | Tinta kiri / kanan pada halaman 2 (A) | Ukuran PDF dua halaman |
| --- | ---: | ---: | ---: |
| Warna | 0 / 5.447 | 6.256 / 0 | 105.985 byte |
| Grayscale | 0 / 5.442 | 6.259 / 0 | 56.029 byte |
| Hitam-putih | 0 / 6.886 | 6.972 / 0 | 5.661 byte |

Dalam mode warna, lebih dari 7.400 piksel per halaman pada area pengukuran memiliki selisih kanal RGB di atas 50. Dalam dua mode lainnya seluruh piksel area itu memiliki kanal RGB yang sama. Pada mode hitam-putih, 96,8% area berada dalam tujuh tingkat intensitas dari hitam atau putih setelah penskalaan oleh pembaca PDF.

Uji lebar ganjil menemukan goresan bergeser pada percobaan ekspor raster 1-bit dengan Flate. Pada halaman pertama, 4.120 piksel gelap muncul di sisi kiri yang seharusnya kosong. Penyimpanan sampel biner 0 dan 255 dalam kanal grayscale 8-bit dengan Flate menghasilkan urutan dan posisi yang ditunjukkan di tabel.
