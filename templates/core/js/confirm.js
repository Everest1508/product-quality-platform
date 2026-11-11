/* Confirm modal: window.confirmAction(form, message). */
(function() {
  var modal = document.getElementById('pq-confirm-modal');
  var messageEl = document.getElementById('pq-confirm-message');
  var okBtn = document.getElementById('pq-confirm-ok');
  var cancelBtn = document.getElementById('pq-confirm-cancel');
  var pendingForm = null;

  window.confirmAction = function(form, message) {
    if (form.dataset.pqConfirmed === '1') {
      delete form.dataset.pqConfirmed;
      return true;
    }
    pendingForm = form;
    messageEl.textContent = message || 'Are you sure?';
    modal.style.display = 'flex';
    return false;
  };

  function closeConfirmModal() {
    modal.style.display = 'none';
    pendingForm = null;
  }
  window.closeConfirmModal = closeConfirmModal;

  okBtn.addEventListener('click', function() {
    if (pendingForm) {
      pendingForm.dataset.pqConfirmed = '1';
      try {
        pendingForm.requestSubmit();
      } catch (e) {
        pendingForm.submit();
      }
    }
  });
  cancelBtn.addEventListener('click', closeConfirmModal);
  modal.addEventListener('click', function(e) {
    if (e.target === modal) closeConfirmModal();
  });
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeConfirmModal();
  });
})();
