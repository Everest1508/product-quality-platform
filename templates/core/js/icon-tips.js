/* Icon-only buttons and links get their name as a tooltip. */
/* Icon-only buttons and links get their name as a tooltip. */
(function(){function tip(root){(root||document).querySelectorAll('.icon-btn[aria-label],.tb-icon[aria-label],.topbar-burger[aria-label],button[aria-label].tb-btn').forEach(function(el){if(!el.hasAttribute('data-tip'))el.setAttribute('data-tip',el.getAttribute('aria-label'))})}
  tip(); document.body.addEventListener('htmx:afterSwap',function(e){tip(e.target)});})();
