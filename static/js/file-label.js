/* Ganti teks bawaan "No file is chosen" dengan label yang tidak terpotong.
   Tanpa JavaScript input tetap memakai tampilan asli browser. */
(function () {
  function label(berkas) {
    return berkas.files && berkas.files.length
      ? berkas.files[0].name
      : 'Belum ada berkas dipilih';
  }

  function pasang(berkas) {
    var teks = document.createElement('span');
    teks.className = 'file-name';
    teks.textContent = label(berkas);
    berkas.classList.add('berkasan-berlabel');
    berkas.insertAdjacentElement('afterend', teks);
    berkas.addEventListener('change', function () {
      teks.textContent = label(berkas);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.form-card input[type="file"]').forEach(pasang);
  });
})();
