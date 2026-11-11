/* Cmd on a Mac, Ctrl everywhere else. */
/* ⌘ on a Mac, Ctrl everywhere else. */
(function(){var mac=/mac|iphone|ipad|ipod/i.test(navigator.platform||navigator.userAgent||'');if(mac)document.querySelectorAll('.mod').forEach(function(k){k.textContent='⌘'});
  document.querySelectorAll('.tb-search kbd').forEach(function(k){if(mac)k.textContent='⌘ K'});})();
