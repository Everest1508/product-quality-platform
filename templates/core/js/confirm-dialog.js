/* Anything with data-confirm asks first. */
/* Anything with data-confirm asks first: <form data-confirm="Delete this entry?" data-confirm-text="This cannot be undone."> or a submit button carrying the same. */
(function(){
  var dlg=document.getElementById('pq-confirm'); if(!dlg||!dlg.showModal) return; var pending=null;
  function ask(el,go){
    dlg.querySelector('[data-title]').textContent=el.dataset.confirm||'Are you sure?';
    var txt=el.dataset.confirmText||'';
    if(el.dataset.confirmSince){var ms=Date.now()-Number(el.dataset.confirmSince);if(ms>0){var m=Math.floor(ms/60000);txt+=(txt?' ':'')+'Time worked so far: '+Math.floor(m/60)+'h '+String(m%60).padStart(2,'0')+'m.'}}
    dlg.querySelector('[data-text]').textContent=txt;
    var danger=el.dataset.confirmTone!=='primary', ok=dlg.querySelector('[data-ok]');
    ok.textContent=el.dataset.confirmLabel||'Confirm'; ok.className='btn '+(danger?'btn-danger':'btn-primary');
    dlg.querySelector('[data-icon]').classList.toggle('danger',danger); pending=go; dlg.showModal();
  }
  dlg.querySelector('[data-cancel]').onclick=function(){pending=null;dlg.close()};
  dlg.querySelector('[data-ok]').onclick=function(){var g=pending;pending=null;dlg.close();if(g)g()};
  /* hx-confirm on an htmx request opens this window instead of the browser's own box. */
  document.addEventListener('htmx:confirm',function(e){
    if(!e.detail.question) return; e.preventDefault();
    var el=e.detail.elt; el.dataset.confirm=e.detail.question; ask(el,function(){e.detail.issueRequest(true)});
  });
  document.addEventListener('submit',function(e){
    var f=e.target, src=e.submitter, el=(src&&src.dataset.confirm)?src:(f.dataset&&f.dataset.confirm?f:null);
    if(!el||f.dataset.confirmed) return; e.preventDefault();
    ask(el,function(){f.dataset.confirmed='1'; if(src&&src.name){var h=document.createElement('input');h.type='hidden';h.name=src.name;h.value=src.value;f.appendChild(h)} f.requestSubmit?f.submit():f.submit()});
  },true);
})();
