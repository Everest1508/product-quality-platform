/* Bulk ticket delete with selection mode. */
// Bulk ticket delete with selection mode
(function() {
  var bulkBtn = document.getElementById('bulk-delete-btn');
  var bulkCount = document.getElementById('bulk-delete-count');
  var selectAll = document.getElementById('select-all-tickets');
  var selectModeBtn = document.getElementById('select-mode-btn');
  var bulkDeleteUrl = bulkBtn ? bulkBtn.getAttribute('onclick').match(/'([^']+)'/)[1] : null;

  function updateBulkBtn() {
    var checked = document.querySelectorAll('.ticket-select:checked');
    if (checked.length > 0) {
      bulkBtn.style.display = 'inline-flex';
      bulkCount.textContent = checked.length;
    } else {
      bulkBtn.style.display = 'none';
    }
  }

  function isSelectionMode() {
    return document.body.classList.contains('selection-mode');
  }

  document.querySelectorAll('.ticket-select').forEach(function(cb) {
    cb.addEventListener('change', function() {
      updateBulkBtn();
      if (selectAll) {
        var all = document.querySelectorAll('.ticket-select');
        selectAll.checked = all.length > 0 && document.querySelectorAll('.ticket-select:checked').length === all.length;
      }
    });
  });

  if (selectAll) {
    selectAll.addEventListener('change', function() {
      var val = this.checked;
      document.querySelectorAll('.ticket-select').forEach(function(cb) { cb.checked = val; });
      updateBulkBtn();
    });
  }

  window.toggleSelectMode = function() {
    if (isSelectionMode()) {
      document.body.classList.remove('selection-mode');
      if (selectModeBtn) selectModeBtn.textContent = 'Select';
      bulkBtn.style.display = 'none';
      document.querySelectorAll('.ticket-select').forEach(function(cb) { cb.checked = false; });
      if (selectAll) selectAll.checked = false;
      document.querySelectorAll('.kanban-card').forEach(function(card) { card.setAttribute('draggable', 'true'); });
    } else {
      document.body.classList.add('selection-mode');
      if (selectModeBtn) selectModeBtn.textContent = 'Cancel';
      document.querySelectorAll('.kanban-card').forEach(function(card) { card.setAttribute('draggable', 'false'); });
    }
  };

  function toast(text, tags) {
    window.dispatchEvent(new CustomEvent('django-message', {detail: {text: text, tags: tags}}));
  }
  window.bulkDeleteTickets = function(url) {
    var checked = document.querySelectorAll('.ticket-select:checked');
    if (checked.length === 0) return;
    var msg = 'Delete ' + checked.length + ' ticket' + (checked.length > 1 ? 's' : '') + '? This cannot be undone.';
    if (!confirm(msg)) return;
    var ids = [];
    checked.forEach(function(cb) { ids.push(cb.value); });
    var formData = new FormData();
    ids.forEach(function(id) { formData.append('ticket_ids[]', id); });
    var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrf) {
      var metaCsrf = document.querySelector('meta[name=csrf-token]');
      if (metaCsrf) csrf = { value: metaCsrf.content };
    }
    fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf ? csrf.value : '' },
      body: formData
    }).then(function(r) { return r.json(); }).then(function(data) {
      if (data.deleted > 0) {
        checked.forEach(function(cb) {
          var card = cb.closest('.kanban-card') || cb.closest('tr');
          if (card) card.remove();
        });
        document.querySelectorAll('.kanban-cards').forEach(function(cards) {
          if (cards.querySelectorAll('.kanban-card').length === 0 && !cards.querySelector('.kanban-empty')) {
            var empty = document.createElement('div');
            empty.className = 'kanban-empty';
            empty.textContent = 'No tickets';
            cards.appendChild(empty);
          }
        });
        var countEl = document.querySelector('.count');
        if (countEl) {
          var total = parseInt(countEl.textContent) - data.deleted;
          if (total < 0) total = 0;
          countEl.textContent = total + ' ticket' + (total !== 1 ? 's' : '');
        }
        document.body.dispatchEvent(new Event('htmx:afterSwap'));
        toast(data.deleted + ' ticket' + (data.deleted > 1 ? 's' : '') + ' deleted.', 'success');
      } else {
        toast(data.error || 'No tickets were deleted.', 'error');
      }
    }).catch(function() { toast('Could not delete tickets.', 'error'); });
  };
})();
