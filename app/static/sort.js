document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('table.sortable').forEach(function (table) {
    var ths = table.querySelectorAll('th[data-sort]');
    ths.forEach(function (th) {
      th.style.cursor = 'pointer';
      th.addEventListener('click', function () {
        var type = th.getAttribute('data-sort');
        var tbody = table.tBodies[0];
        var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        var asc = th.getAttribute('data-dir') !== 'asc';
        ths.forEach(function (t) { t.removeAttribute('data-dir'); t.classList.remove('sorted-asc', 'sorted-desc'); });
        th.setAttribute('data-dir', asc ? 'asc' : 'desc');
        th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
        var cellIndex = Array.prototype.indexOf.call(th.parentNode.children, th);
        rows.sort(function (a, b) {
          var ac = a.children[cellIndex], bc = b.children[cellIndex];
          var av = ac.getAttribute('data-val'); if (av === null) av = ac.textContent.trim();
          var bv = bc.getAttribute('data-val'); if (bv === null) bv = bc.textContent.trim();
          if (type === 'num') {
            av = parseFloat(av) || 0; bv = parseFloat(bv) || 0;
            return asc ? av - bv : bv - av;
          }
          return asc ? av.localeCompare(bv) : bv.localeCompare(av);
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      });
    });
  });
});
