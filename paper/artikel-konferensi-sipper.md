# Evaluating Duplicate Detection and Record Update Consistency in a Migrant Resident Registry

Muhammad Ai Nur Haaq (3125521052); Yafet Wenda (3125521058)

Politeknik Elektronika Negeri Surabaya — Workshop Pemrograman Framework

## Abstrak

Pendataan penduduk perantau sebagai *supporting system* membutuhkan jaminan bahwa satu orang hanya tercatat sekali dan setiap perubahan data meninggalkan jejak yang dapat diperiksa. Penelitian ini mengevaluasi apakah SIPPER (Sistem Informasi Penduduk Perantauan) mencegah data ganda tanpa menyamakan orang yang berbeda, serta menjaga perubahan data tetap terverifikasi dan dapat ditelusuri. Evaluasi dilakukan dengan 100 entri sintetis yang dimasukkan lewat jalur aplikasi sebenarnya — 70 unik, 15 duplikat dari identitas sebelumnya, dan 15 orang berbeda dengan nama mirip — ditambah 20 skenario siklus pembaruan (sah, tidak lengkap, menunggu verifikasi, ditolak, dan oleh akun lain) pada basis data uji MySQL. Hasilnya: 15/15 duplikat terdeteksi (0 terlewat), 15/15 nama mirip diterima sebagai orang berbeda (0 salah gabung), dan 20/20 skenario pembaruan berjalan sesuai aturan — nilai aktif, versi lama, waktu, dan pelaku tercatat, sementara perubahan tanpa hak ditolak (404/302/403). Kesimpulannya, aturan kesamaan NIK persis ditambah batasan unik basis data efektif mencegah duplikat pada cakupan identitas yang sama persis; cakupan itu tidak menjangkau kesalahan ketik NIK, dan pengujian teknis ini tidak membuktikan kebenaran faktual alamat yang dilaporkan warga.

**Kata kunci:** registri penduduk, deteksi duplikat, NIK, konsistensi pemutakhiran, audit, Django

## 1. Pendahuluan

Perpindahan penduduk antar daerah untuk pendidikan, pekerjaan, dan usaha bersifat dinamis sehingga pemerintah daerah membutuhkan gambaran taktis tentang warga pendatang di wilayahnya. Administrasi kependudukan resmi — KTP-el, Kartu Keluarga, dan Surat Keterangan Pindah — adalah kewenangan Dukcapil dengan NIK 16 digit sebagai pengenal tunggal warga (UU No. 24 Tahun 2013; [5]). SIPPER sengaja dibangun bukan sebagai pengganti registri resmi itu, melainkan sebagai *supporting system* berbasis web yang menghubungkan partisipasi warga perantau dengan verifikasi petugas: warga mendaftar dan mengunggah KTP/KK, petugas memverifikasi, dan warga yang disetujui mendapat kartu digital ber-QR [dokumen proyek]. Kebutuhan yang sama — registrasi penduduk sebagai instrumen tata kelola — juga muncul dalam kajian pelayanan administrasi kependudukan [6].

Pada pendataan semacam ini dua risiko data saling bertolak belakang: data ganda (orang yang sama tercatat dua kali) dan penggabungan keliru (dua orang berbeda dianggap satu). Data ganda menggembungkan statistik dan berpotensi menerbitkan dua kartu untuk satu orang; penggabungan keliru justru menghapus hak warga yang sah. Risiko kedua menyangkut perubahan data: alamat dan tujuan domisili warga berubah seiring waktu, dan tanpa jejak riwayat tidak ada yang bisa menjawab kapan nilai aktif berubah, oleh siapa, dan atas dasar verifikasi yang mana. Kebutuhan-kebutuhan ini terdokumentasi pada rancangan proyek — khususnya aturan NIK unik 16 digit, siklus status pengajuan (Menunggu, Disetujui, Ditolak, Perlu perbaikan), riwayat pemutakhiran, dan log audit. Karena studi ini tidak melakukan wawancara atau observasi lapangan ke instansi mana pun, seluruh kebutuhan di atas dinyatakan sebagai kebutuhan prototipe/skenario dari dokumentasi proyek, bukan sebagai temuan instansi.

Kajian terdahulu tentang registri digital umumnya menilai sistem dari jumlah fitur dasbor, bukan dari kualitas data yang dihasilkannya. Padahal literatur *record linkage* menunjukkan bahwa masalah sesungguhnya terletak pada kualitas pencocokan: seberapa banyak pasangan yang benar ditemukan (recall), seberapa banyak pasangan yang salah digabung (false positive), dan berapa biaya komputasinya [1], [2]. Sejalan dengan itu, literatur *provenance* dan basis data bitemporal menekankan bahwa catatan riwayat — siapa mengubah apa, kapan, dengan versi lama yang tersimpan — adalah syarat untuk mempercayai data aktif [3], [4]. Evaluasi SIPPER pada artikel ini mengikuti ukuran kualitas data tersebut, bukan menghitung fitur.

Kontribusi artikel ini adalah evaluasi empiris atas dua sifat SIPPER: (1) deteksi data ganda — apakah aturan kesamaan NIK persis plus batasan unik basis data mencegah duplikat tanpa salah menolak orang berbeda, dan (2) konsistensi siklus pemutakhiran — apakah nilai aktif, versi lama, status verifikasi, waktu, dan pelaku selalu tercatat, serta apakah perubahan oleh akun lain ditolak. Evaluasi memakai identitas sintetis, tabel acuan yang ditetapkan sebelum uji, dan pengukuran terhadap basis data uji MySQL, sehingga setiap klaim ditopang angka hasil nyata.

## 2. Kajian Pustaka

Penelitian tentang pencocokan dan deduplikasi catatan (*record linkage*) telah matang. Christen [1] mensurvei teknik *indexing* untuk *record linkage* skala besar dan menegaskan bahwa tanpa *blocking*, pencocokan berpasangan tumbuh kuadratik; survei itu juga membedakan pencocokan deterministik berbasis kunci dengan pencocokan probabilistik berbasis kemiripan. Christen dan Goiser [2] melengkapi dengan ukuran mutu: jumlah pasangan benar/salah, recall, precision, dan false positive — ukuran yang sama dipakai artikel ini untuk melaporkan hasil Uji 1. Untuk kebutuhan jejak perubahan, Simmhan dkk. [3] mensurvei teknik *data provenance* dan menempatkan audit trail sebagai bentuk provenance yang paling umum dipakai sistem informasi; kajian basis data bitemporal [4] menambahkan dimensi waktu sah (*valid time*) dan waktu transaksi (*transaction time*) sehingga nilai lama tidak pernah hilang ketika nilai aktif berubah. Pada konteks Indonesia, NIK 16 digit ditetapkan sebagai pengenal tunggal penduduk oleh UU No. 24 Tahun 2013, dan arsitektur identitas yang berpusat pada NIK dibahas antara lain pada [5]; peran registrasi kependudukan bagi tata kelola pemerintahan diulas pada [6].

Tabel berikut membandingkan pendekatan-pendekatan itu dengan SIPPER pada lima aspek yang relevan dengan pertanyaan penelitian.

| Referensi | Identitas kunci | Penanganan data mirip | Mekanisme verifikasi/pembaruan | Audit/provenance | Evaluasi false positive |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Christen 2012 [1] | kunci + pemblokiran untuk pencocokan probabilistik | kemiripan string, bobot | tidak dibahas | tidak dibahas | dibahas sebagai ukuran mutu |
| Christen & Goiser 2007 [2] | pasangan rekaman | ukuran kemiripan | tidak dibahas | tidak dibahas | diukur eksplisit (recall/precision) |
| Simmhan dkk. 2005 [3] | objek data umum | tidak dibahas | tidak dibahas | audit trail, lineage | tidak dibahas |
| Neelamegam dkk. 2026 [4] | skema bitemporal | tidak dibahas | versi waktu sah + waktu transaksi | riwayat versi tersimpan | tidak dibahas |
| SSRN 6987638 [5] | NIK 16 digit (pengenal tunggal) | tidak dibahas | arsitektur identitas nasional | tidak dibahas | tidak dibahas |
| SIPPER (artikel ini) | NIK 16 digit, kesamaan persis | nama mirip **tidak** dianggap sama | status pengajuan oleh petugas; pemutakhiran mandiri + riwayat | AuditLog + Pemutakhiran | diukur lewat 15 pasang nama mirip |

Kesenjangan yang diisi artikel ini: sebagian besar kajian mengevaluasi pencocokan probabilistik pada data skala besar, sementara sistem pendukung taktis seperti SIPPER memilih aturan minimal — kesamaan NIK persis — demi kepastian hukum dan kesederhanaan. Evaluasi yang menguji apakah aturan minimal itu cukup, berapa biaya historinya, dan apa batas cakupannya, belum banyak dilakukan pada sistem web Django untuk konteks perantau.

## 3. Metodologi

### 3.1 Sistem yang dievaluasi

SIPPER adalah aplikasi web Django 5.2 dengan basis data MariaDB 10.4 (driver PyMySQL), berjalan di belakang Apache + waitress pada bentuk produksi lokal. Empat model menentukan perilaku yang diuji: `Penduduk` (profil perantau; `nik` CHAR(16) **unik** dengan validator 16 digit angka), `Pengajuan` (siklus status `menunggu → disetujui | ditolak | perlu_perbaikan`, dengan `verified_by` dan `verified_at`), `Pemutakhiran` (versi perubahan: `data_lama` dan `data_baru` sebagai JSON, plus `created_at`), dan `AuditLog` (pelaku, aksi, deskripsi, waktu). Warga mengirim pengajuan lewat `/pengajuan/` (KTP dan KK wajib), mengubah domisili lewat `/pemutakhiran/`, dan petugas memutuskan status lewat `/petugas/`.

### 3.2 Definisi pencocokan dan aturan siklus data

Aturan pencocokan ditetapkan **sebelum** label dibuat, sesuai panduan:

- **Dua record adalah orang yang sama** jika dan hanya jika NIK-nya identik (string 16 digit yang sama persis). Tidak ada pencocokan nama, alamat, maupun kemiripan lain.
- **Nama mirip saja tidak pernah membuat dua orang dianggap sama**; dua record dengan NIK berbeda selalu orang berbeda.
- Duplikat ditolak dua lapis: aturan di view (`Penduduk.objects.filter(nik=...)` menolak sebelum penulisan) dan batasan `unique` di basis data (menangkap kondisi lomba lewat `IntegrityError`).
- Field wajib pengajuan: nama, NIK, daerah asal, kota tujuan, tujuan (pilihan resmi), plus lampiran KTP dan KK. NIK harus 16 digit angka.
- **Kapan perubahan efektif:** pemutakhiran domisili oleh warga diterapkan langsung ke record aktif, dan setiap kali versi lama disimpan ke `Pemutakhiran` serta aksi dicatat ke `AuditLog`. Perubahan status pengajuan hanya lewat jalur keputusan petugas (`terapkan_status`), yang mengisi `verified_by`, `verified_at`, menerbitkan kartu saat disetujui, dan mewajibkan catatan untuk keputusan tolak/perlu-perbaikan.
- **Siapa memverifikasi:** akun petugas (`is_staff` atau `UserRole` petugas); warga hanya bisa mengubah record milik akunnya sendiri.

### 3.3 Lingkungan dan bahan uji

Seluruh skenario berjalan lewat jalur HTTP sistem yang sebenarnya (Django *test client* memanggil view/URL produksi) terhadap basis data uji MySQL `test_sipper_db` di `127.0.0.1:3306` (MariaDB 10.4) — bukan basis data operasional. Identitas seluruhnya sintetis: NIK berpola `0000000000xxxxxx` (16 digit berawalan nol, mustahil milik orang nyata) dan nama rekaan; tidak ada data pribadi asli yang disentuh. Tabel acuan (hasil yang diharapkan per kasus) ditulis di dalam kode eksperimen sebelum dijalankan. OCR di-mock karena pengenalan gambar bukan variabel yang diuji, dan akun uji memakai hasher MD5 agar pembuatan 100+ akun tidak membebani durasi uji (peng-hash-an sandi tidak terlibat pada jalur yang diukur). Angka latensi yang dilaporkan adalah latensi sisi server dalam proses uji lokal (*in-process*), bukan latensi jaringan produksi.

### 3.4 Rancangan pengujian

**Uji 1 — Data ganda dan nama mirip.** 100 entri dimasukkan lewat `POST /pengajuan/` dalam urutan tercatat: (a) 70 entri unik — 15 di antaranya memakai nama yang belakangan diberi "kembaran" mirip, (b) 15 duplikat yang memakai NIK identitas sebelumnya (10 dengan nama sama, 5 dengan nama berbeda), (c) 15 orang berbeda dengan nama mirip dan NIK baru. Setiap entri memakai akun baru, sehingga record pembanding selalu sudah tersedia saat duplikat datang.

**Uji 2 — Siklus pembaruan.** 20 skenario (Tabel 1) dimulai dari record terverifikasi yang diketahui: empat pembaruan sah, lima pembaruan tidak lengkap, tiga skenario menunggu verifikasi, tiga skenario penolakan, dan lima skenario percobaan oleh akun lain. Setiap skenario mencatat nilai sebelum/usulan/sesudah, status pengajuan, verifikator, waktu verifikasi, jumlah baris `Pemutakhiran` baru, aksi audit, dan latensi.

**Tabel 1. Data, kasus, dan kondisi eksperimen**

| Kelompok | Jumlah | Definisi kasus | Kondisi awal | Hasil acuan |
| :--- | :--- | :--- | :--- | :--- |
| Uji 1 — unik | 70 | NIK baru, nama bervariasi (15 di antaranya punya kembaran nama mirip) | akun baru, pengajuan lengkap | diterima |
| Uji 1 — duplikat | 15 | NIK sama dengan entri unik ke-1..15 (10 nama sama, 5 nama beda) | record pembanding sudah ada | ditolak |
| Uji 1 — nama mirip | 15 | NIK baru, nama sangat mirip dengan 15 entri unik pertama | akun baru, pengajuan lengkap | diterima (orang berbeda) |
| Uji 2 — sah (S01–S04) | 4 | ubah kota tujuan; ubah tiga field; kirim ulang nilai sama; ubah tujuan | record disetujui | diterapkan + riwayat |
| Uji 2 — tidak lengkap (S05–S09) | 5 | kota kosong; asal kosong; semua kosong; tujuan tidak resmi; tujuan kosong | record disetujui | ditolak, tanpa perubahan |
| Uji 2 — menunggu verifikasi (S10–S12) | 3 | ubah domisili saat menunggu; observasi data aktif; persetujuan petugas | pengajuan `menunggu` | sesuai aturan sistem |
| Uji 2 — ditolak (S13–S15) | 3 | tolak dengan catatan; tolak tanpa catatan; pemutakhiran setelah ditolak | pengajuan `menunggu` / `ditolak` | sesuai aturan sistem |
| Uji 2 — akun lain (S16–S20) | 5 | ubah data sendiri (A utuh); kirim ulang milik A; tanpa login; API petugas; ubah status A | akun B (warga) | ditolak / A utuh |
| Lingkungan | — | Django 5.2 + MariaDB 10.4, basis data uji `test_sipper_db`, jalur HTTP nyata, OCR di-mock, NIK sintetis `0000000000xxxxxx` | — | — |

## 4. Hasil

### 4.1 Uji 1 — Data ganda dan nama mirip

Dari 100 entri, 70/70 entri unik diterima (masing-masing menciptakan satu baris `Penduduk` dan satu `Pengajuan`), 15/15 duplikat ditolak dengan pesan "NIK tersebut sudah terdaftar." dan **tanpa** baris baru, serta 15/15 orang bernama mirip diterima sebagai orang berbeda. Tidak ada duplikat terlewat dan tidak ada orang berbeda yang salah ditolak. Pada akhir uji, basis data berisi tepat 85 baris `Penduduk` dan 85 baris `Pengajuan` (70 unik + 15 nama mirip; 15 duplikat tidak meninggalkan baris). Seluruh 15 duplikat tertangkap lapis aturan di view — lapis kedua (`IntegrityError` dari batasan unik) tidak sampai terpicu pada uji berurutan ini, tetapi tetap diverifikasi keberadaannya oleh 170 pengujian otomatis proyek.

### 4.2 Uji 2 — Siklus pembaruan

Ke-20 skenario berjalan sesuai aturan (20/20 sesuai). Pembaruan sah (S01–S04) selalu diterapkan dan setiap kali menulis satu baris `Pemutakhiran` (versi lama vs baru) plus `AuditLog` berpelaku warga; kirim ulang nilai yang sama (S03) tetap diterapkan dan tercatat. Pembaruan tidak lengkap (S05–S09) ditolak tanpa perubahan data dan tanpa baris riwayat. Pada skenario menunggu verifikasi, pemutakhiran domisili langsung mengubah data aktif sementara status pengajuan tetap `menunggu` dan `verified_by`/`verified_at` kosong (S10–S11); setelah petugas menyetujui, `verified_by`, `verified_at`, dan kartu digital terisi (S12). Penolakan dengan catatan tersimpan lengkap (S13); penolakan tanpa catatan ditolak sistem sehingga status tetap `menunggu` (S14); pemutakhiran valid tetap diterapkan setelah pengajuan ditolak (S15) — perilaku yang memang dirancang (pemutakhiran tidak dikunci status pengajuan). Percobaan akun lain seluruhnya gagal dengan cara yang dirancang: data A utuh ketika B mengubah datanya sendiri (S16), kirim ulang milik A berbalas 404 (S17), akses tanpa login diarahkan ke halaman masuk (302, S18), API khusus petugas berbalas 403 (S19), dan upaya mengubah status A dari antrean petugas diarahkan ke halaman masuk tanpa efek (302, S20).

**Tabel 2. Hasil per kategori dan kondisi**

| Uji | Kategori | Diuji | Hasil | Kesesuaian | Latensi (median / p95) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | unik | 70 | 70 diterima | 70/70 | — |
| 1 | duplikat | 15 | 15 terdeteksi, 0 terlewat, 0 baris baru | 15/15 | — |
| 1 | nama mirip | 15 | 15 diterima, 0 salah tolak | 15/15 | — |
| 1 | total | 100 | 85 baris Penduduk & 85 Pengajuan | 100/100 | 6,7 ms / 11,9 ms |
| 2 | sah | 4 | 4 diterapkan + riwayat | 4/4 | — |
| 2 | tidak lengkap | 5 | 5 ditolak tanpa perubahan | 5/5 | — |
| 2 | menunggu verifikasi | 3 | 3 sesuai aturan | 3/3 | — |
| 2 | ditolak | 3 | 3 sesuai aturan | 3/3 | — |
| 2 | akun lain | 5 | 5 ditolak, data A utuh | 5/5 | — |
| 2 | total | 20 | 7 baris Pemutakhiran baru | 20/20 | 3,5 ms / 16,2 ms |

Latensi pada Tabel 2 adalah latensi sisi server dalam proses uji lokal (*in-process test client*), dicatat sebagai indikator beban relatif antarkelompok, bukan angka kinerja produksi.

## 5. Pembahasan

**Apakah penolakan duplikat mengurangi entri ganda dengan risiko salah menolak orang berbeda?** Pada uji ini jawabannya ya, dengan cakupan yang harus dinyatakan jujur: aturan kesamaan NIK persis menolak 15/15 duplikat dan tidak pernah salah menolak 15 pasang nama mirip, tetapi itu juga berarti sistem **tidak** mendeteksi orang yang sama dengan NIK berbeda (misalnya salah ketik satu digit) — cakupan deteksi adalah kesamaan ID persis, sesuai definisi pada Subbab 3.2. Risiko salah tolak praktis nol selama NIK yang dimasukkan berbeda; sebaliknya, risiko duplikat tersisa ada pada kesalahan input NIK, yang di luar cakupan aturan ini. Untuk sistem pendukung taktis dengan verifikasi petugas di hilir, pertukaran ini dapat diterima: deteksi probabilistik berbasis nama/alamat [1], [2] bisa menangkap kesalahan ketik, tetapi membuka risiko menggabungkan dua orang berbeda — justru yang ingin dihindari pendataan kependudukan.

**Beban verifikasi dan pemeliharaan histori.** Setiap pembaruan yang diterima menulis satu baris `Pemutakhiran` dan satu baris `AuditLog` — 7 baris dari 7 pembaruan pada uji ini — termasuk kirim ulang nilai yang sama (S03). Beban penyimpanan itu linier terhadap jumlah aksi dan sepadan dengan manfaatnya: versi lama selalu bisa dibandingkan dengan nilai aktif. Dua temuan perlu digarisbawahi. Pertama, data aktif berubah **segera** saat warga mengirim pemutakhiran, bahkan ketika pengajuannya masih `menunggu` (S10–S11); nilai lama tersimpan, tetapi keputusan verifikasi petugas tidak pernah meninjau perubahan itu. Kedua, penolakan tanpa catatan dicegah di sisi server (S14) sehingga warga selalu tahu alasan dan tombol kirim ulang hanya terbuka untuk status yang memang boleh dikirim ulang. Keduanya adalah pilihan rancangan yang konsisten, tetapi keduanya juga batas konteks: "perubahan terverifikasi" pada SIPPER berarti status pengajuan yang diverifikasi dan perubahan domisili yang tercatat, bukan bahwa setiap perubahan domisili melewati persetujuan petugas.

**Tabel 3. Contoh kegagalan beserta penyebab** — pada uji ini tidak ada pelanggaran sistem yang teramati; tabel berikut mendokumentasikan upaya pelanggaran yang ditolak beserta lapisan yang menolaknya.

| Kasus | Upaya | Hasil aktual | Lapisan yang menolak |
| :--- | :--- | :--- | :--- |
| Uji 1 #71–#85 | mendaftarkan NIK yang sudah terdaftar (15 kasus) | ditolak, "NIK tersebut sudah terdaftar.", tanpa baris baru | aturan NIK di view + batasan `unique` basis data |
| S05–S09 | pemutakhiran tidak lengkap / tujuan tidak resmi | ditolak, data aktif tidak berubah | validasi server `update_data` |
| S14 | petugas menolak pengajuan tanpa catatan | status tetap `menunggu`, `verified_by`/`verified_at` kosong | `STATUS_WAJIB_CATATAN` di jalur keputusan |
| S17 | warga B kirim ulang pengajuan milik A lewat URL langsung | HTTP 404 | penyaringan `penduduk__user` pada `get_object_or_404` |
| S18 | mengubah data tanpa login | HTTP 302 ke halaman masuk | `login_required` |
| S19 | warga B memanggil API khusus petugas | HTTP 403 | pemeriksaan `is_officer` pada endpoint |
| S20 | warga B mengubah status pengajuan A dari antrean petugas | HTTP 302, status A tetap `disetujui` | `user_passes_test(is_officer)` |

Ketiadaan pelanggaran pada uji ini bukan jaminan mutlak: seluruh hasil diperoleh pada satu basis data, satu urutan permintaan (tanpa perlombaan antarpermintaan yang sebenarnya), dan beban terbatas. Uji 3 (tugas verifikasi petugas pembanding aplikasi vs lembar kerja) tidak dijalankan, sehingga artikel ini **tidak** mengklaim efisiensi kerja petugas.

## 6. Kesimpulan

Menjawab pertanyaan penelitian: pada cakupan yang diuji, SIPPER mencegah data ganda tanpa menyamakan orang berbeda, dan perubahan data berjalan konsisten serta tercatat. Angkanya: 15/15 duplikat terdeteksi (0 terlewat), 15/15 orang bernama mirip diterima sebagai orang berbeda (0 salah tolak), dan 20/20 skenario pembaruan sesuai aturan — nilai aktif, versi lama, waktu, dan pelaku tercatat pada 7 pembaruan yang diterima, sementara percobaan akun lain ditolak (404/302/403) tanpa mengubah data pemilik. Batas konteksnya: (1) deteksi hanya mencakup kesamaan NIK persis — kesalahan ketik NIK tidak terdeteksi; (2) pemutakhiran domisili efektif segera tanpa gerbang persetujuan, dengan riwayat sebagai pengimbangnya; (3) hasil diperoleh pada satu basis data uji dengan beban terbatas, dan nol kegagalan teramati bukan jaminan mutlak; (4) pengujian teknis ini tidak membuktikan bahwa alamat yang dilaporkan warga benar secara faktual — validasi lapangan adalah persoalan berbeda.

## Daftar Pustaka

[1] P. Christen, "A Survey of Indexing Techniques for Scalable Record Linkage and Deduplication," IEEE Transactions on Knowledge and Data Engineering, vol. 24, no. 9, pp. 1537–1555, 2012. https://www.computer.org/csdl/journal/tk/2012/09/ttk2012091537/13rRUwkfAZB

[2] P. Christen and K. Goiser, "Quality and Complexity Measures for Data Linkage and Deduplication," dalam Quality Measures in Data Mining, Springer, 2007, hlm. 127–151. https://www.semanticscholar.org/paper/Quality-and-Complexity-Measures-for-Data-Linkage-Christen-Goiser/1c0c26a72a6c1578121c2a43a3fe43a9688dfacd

[3] Y. L. Simmhan, B. Plale, dan D. Gannon, "A Survey of Data Provenance Techniques," Technical Report IUB-CS-TR618, Indiana University, 2005. https://scholarworks.iu.edu/dspace/bitstreams/ca836db4-e8d1-4817-9a50-1a20debe0c0d/download

[4] G. Neelamegam et al., "Comprehensive insights into bitemporal databases: a PRISMA-based systematic review," 2026. https://link.springer.com/article/10.1007/s42488-026-00162-x

[5] "Toward a Platform State: NIK-Centric Identity Architecture," SSRN Preprint No. 6987638. https://papers.ssrn.com/sol3/Delivery.cfm/6987638.pdf?abstractid=6987638&mirid=1

[6] R. Saputra, "Population and Civil Registration as the Spearhead of Governance," Journal of E-Government and Civil Services, 2026. https://ejecs.org/index.php/JECS/article/view/2974

[7] Undang-Undang Republik Indonesia Nomor 24 Tahun 2013 tentang Administrasi Kependudukan.

---

## Lampiran: artefak eksperimen yang diserahkan

| Artefak | Isi |
| :--- | :--- |
| `core/tests_paper.py` | kode eksperimen Uji 1 & Uji 2 beserta tabel acuan |
| `paper/uji1-kasus.csv` | log 100 kasus Uji 1 (urutan, kategori, hasil acuan vs aktual, pesan sistem, latensi) |
| `paper/uji2-kasus.csv` | log 20 skenario Uji 2 (nilai sebelum/usulan/sesudah, status, verifikator, riwayat, latensi) |
| `paper/ringkasan-eksperimen.json` | agregat hasil dan lingkungan uji |
