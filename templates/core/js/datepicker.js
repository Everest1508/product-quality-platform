/* Custom datepicker. */
// Custom Datepicker Component Script
(function() {
  var activeInput = null;
  var currentMonth = new Date().getMonth();
  var currentYear = new Date().getFullYear();

  var popover = document.createElement('div');
  popover.className = 'pq-datepicker-popover';
  popover.innerHTML = `
    <div class="pq-datepicker-presets">
      <button type="button" class="pq-datepicker-preset" data-preset="today">Today</button>
      <button type="button" class="pq-datepicker-preset" data-preset="yesterday">Yesterday</button>
      <button type="button" class="pq-datepicker-preset" data-preset="7days">Last 7d</button>
      <button type="button" class="pq-datepicker-preset" data-preset="30days">Last 30d</button>
    </div>
    <div class="pq-datepicker-head">
      <div class="pq-datepicker-title"></div>
      <div class="pq-datepicker-nav">
        <button type="button" class="pq-prev">&larr;</button>
        <button type="button" class="pq-next">&rarr;</button>
      </div>
    </div>
    <div class="pq-datepicker-grid">
      <div class="pq-datepicker-day-name">Su</div>
      <div class="pq-datepicker-day-name">Mo</div>
      <div class="pq-datepicker-day-name">Tu</div>
      <div class="pq-datepicker-day-name">We</div>
      <div class="pq-datepicker-day-name">Th</div>
      <div class="pq-datepicker-day-name">Fr</div>
      <div class="pq-datepicker-day-name">Sa</div>
    </div>
    <div class="pq-datepicker-days pq-datepicker-grid"></div>
  `;
  document.body.appendChild(popover);

  var titleEl = popover.querySelector('.pq-datepicker-title');
  var daysEl = popover.querySelector('.pq-datepicker-days');
  var prevBtn = popover.querySelector('.pq-prev');
  var nextBtn = popover.querySelector('.pq-next');

  function renderCalendar(year, month, selectedValue) {
    titleEl.textContent = new Date(year, month).toLocaleString('default', { month: 'long', year: 'numeric' });
    daysEl.innerHTML = '';

    var firstDay = new Date(year, month, 1).getDay();
    var totalDays = new Date(year, month + 1, 0).getDate();
    var prevMonthDays = new Date(year, month, 0).getDate();
    var todayStr = new Date().toISOString().split('T')[0];

    for (var i = firstDay - 1; i >= 0; i--) {
      var d = document.createElement('div');
      d.className = 'pq-datepicker-day muted';
      d.textContent = prevMonthDays - i;
      daysEl.appendChild(d);
    }

    for (var day = 1; day <= totalDays; day++) {
      var d = document.createElement('div');
      d.className = 'pq-datepicker-day';
      d.textContent = day;
      var monthStr = String(month + 1).padStart(2, '0');
      var dayStr = String(day).padStart(2, '0');
      var dateStr = year + '-' + monthStr + '-' + dayStr;

      if (dateStr === todayStr) d.classList.add('today');
      if (dateStr === selectedValue) d.classList.add('selected');

      d.dataset.date = dateStr;
      d.addEventListener('click', function(e) {
        selectDate(this.dataset.date);
      });
      daysEl.appendChild(d);
    }
  }

  function selectDate(dateStr) {
    if (!activeInput) return;
    activeInput.value = dateStr;
    activeInput.dispatchEvent(new Event('input', { bubbles: true }));
    activeInput.dispatchEvent(new Event('change', { bubbles: true }));
    if (typeof activeInput.onchange === 'function') {
      activeInput.onchange();
    }
    hidePopover();
  }

  function positionPopover(input) {
    var rect = input.getBoundingClientRect();
    // A modal <dialog> sits in the top layer, above everything in <body>, so a
    // popover opened from inside one has to live inside it to be seen.
    var host = input.closest('dialog[open]') || document.body;
    if (popover.parentNode !== host) host.appendChild(popover);
    popover.style.position = 'fixed';
    popover.style.top = (rect.bottom + 6) + 'px';
    popover.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - 300)) + 'px';
    popover.style.display = 'block';
  }

  function hidePopover() {
    popover.style.display = 'none';
    activeInput = null;
  }

  prevBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    currentMonth--;
    if (currentMonth < 0) { currentMonth = 11; currentYear--; }
    renderCalendar(currentYear, currentMonth, activeInput ? activeInput.value : '');
  });

  nextBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    currentMonth++;
    if (currentMonth > 11) { currentMonth = 0; currentYear++; }
    renderCalendar(currentYear, currentMonth, activeInput ? activeInput.value : '');
  });

  popover.querySelectorAll('.pq-datepicker-preset').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      var preset = this.dataset.preset;
      var now = new Date();
      var target = new Date();

      if (preset === 'yesterday') target.setDate(now.getDate() - 1);
      else if (preset === '7days') target.setDate(now.getDate() - 6);
      else if (preset === '30days') target.setDate(now.getDate() - 29);

      var year = target.getFullYear();
      var month = String(target.getMonth() + 1).padStart(2, '0');
      var day = String(target.getDate()).padStart(2, '0');
      selectDate(year + '-' + month + '-' + day);
    });
  });

  document.addEventListener('click', function(e) {
    var target = e.target;
    if (target.tagName === 'INPUT' && target.type === 'date') {
      e.preventDefault();
      activeInput = target;
      var parts = target.value ? target.value.split('-') : [];
      if (parts.length === 3) {
        currentYear = parseInt(parts[0], 10);
        currentMonth = parseInt(parts[1], 10) - 1;
      } else {
        var now = new Date();
        currentYear = now.getFullYear();
        currentMonth = now.getMonth();
      }
      renderCalendar(currentYear, currentMonth, target.value);
      positionPopover(target);
    } else if (!popover.contains(target)) {
      hidePopover();
    }
  }, true);

  document.addEventListener('keydown', function(e) {
    if (e.target && e.target.tagName === 'INPUT' && e.target.type === 'date' && (e.key === ' ' || e.key === 'Enter')) {
      e.preventDefault();
      e.target.click();
    }
  });

  window.addEventListener('resize', hidePopover);
  window.addEventListener('scroll', function(e) { if (!popover.contains(e.target)) hidePopover(); }, true);
})();
