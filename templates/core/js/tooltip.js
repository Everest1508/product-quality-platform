/* Tooltips: hover-intent, arrow, shortcut hints. */
// Custom Tooltip Component Script (Redesigned with hover-intent, dynamic micro-arrow, and shortcut parsing)
(function() {
  if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) {
    return; // Touch devices don't benefit from hover tooltips and they stick on tap
  }

  var tooltipEl = document.createElement('div');
  tooltipEl.className = 'pq-tooltip';
  tooltipEl.setAttribute('role', 'tooltip');
  tooltipEl.setAttribute('aria-hidden', 'true');
  tooltipEl.innerHTML = '<span class="pq-tooltip-text"></span><div class="pq-tooltip-arrow top"></div>';
  document.body.appendChild(tooltipEl);

  var textEl = tooltipEl.querySelector('.pq-tooltip-text');
  var arrowEl = tooltipEl.querySelector('.pq-tooltip-arrow');
  var currentTarget = null;
  var showTimer = null;
  var hideTimer = null;
  var isWarm = false;
  var warmTimer = null;

  function parseShortcut(str) {
    if (!str) return '';
    return str.replace(/\s*\(([⌘⌃⌥⇧A-Za-z0-9+–— -]+)\)$/, function(_, kbd) {
      return ' <kbd class="pq-kbd">' + kbd + '</kbd>';
    });
  }

  function showTooltip(el, immediate) {
    clearTimeout(hideTimer);
    clearTimeout(showTimer);

    if (!el || !el.isConnected) return;

    var text = el.getAttribute('data-tooltip') || el.getAttribute('title') || el.getAttribute('data-native-title');
    var plain = !text && (el.getAttribute('data-peek') || el.getAttribute('data-tip'));
    if (plain) text = plain;
    if (!text || !text.trim()) return;

    if (el.hasAttribute('title')) {
      el.setAttribute('data-native-title', el.getAttribute('title'));
      el.removeAttribute('title');
    }

    var delay = (immediate || isWarm) ? 0 : 120;

    showTimer = setTimeout(function() {
      if (!el.isConnected) return;
      currentTarget = el;
      tooltipEl.classList.toggle('peek', !!el.hasAttribute('data-peek') && !el.getAttribute('data-tooltip'));

      if (plain) {
        textEl.textContent = text;
      } else {
        textEl.innerHTML = parseShortcut(text);
      }

      tooltipEl.style.display = 'block';
      tooltipEl.setAttribute('aria-hidden', 'false');

      var rect = el.getBoundingClientRect();
      var tooltipRect = tooltipEl.getBoundingClientRect();

      var top = rect.top - tooltipRect.height - 7;
      var position = 'top';

      if (top < 8) {
        top = rect.bottom + 7;
        position = 'bottom';
      }

      var targetCenter = rect.left + (rect.width / 2);
      var left = targetCenter - (tooltipRect.width / 2);

      // Clamp tooltip inside viewport with 8px margin
      var clampedLeft = Math.max(8, Math.min(left, window.innerWidth - tooltipRect.width - 8));

      // Arrow position relative to tooltip box so it points directly at target center
      var arrowLeft = targetCenter - clampedLeft;
      arrowLeft = Math.max(10, Math.min(arrowLeft, tooltipRect.width - 10));

      arrowEl.className = 'pq-tooltip-arrow ' + position;
      arrowEl.style.left = Math.round(arrowLeft) + 'px';

      tooltipEl.style.top = Math.round(top) + 'px';
      tooltipEl.style.left = Math.round(clampedLeft) + 'px';

      requestAnimationFrame(function() {
        tooltipEl.classList.add('show');
      });

      isWarm = true;
      clearTimeout(warmTimer);
    }, delay);
  }

  function hideTooltip() {
    clearTimeout(showTimer);
    tooltipEl.classList.remove('show');
    tooltipEl.setAttribute('aria-hidden', 'true');

    hideTimer = setTimeout(function() {
      if (!tooltipEl.classList.contains('show')) {
        tooltipEl.style.display = 'none';
      }
    }, 150);

    if (currentTarget && currentTarget.hasAttribute('data-native-title')) {
      currentTarget.setAttribute('title', currentTarget.getAttribute('data-native-title'));
    }
    currentTarget = null;

    clearTimeout(warmTimer);
    warmTimer = setTimeout(function() {
      isWarm = false;
    }, 280);
  }

  var SEL = '[data-tooltip], [title], [data-native-title], [data-tip], [data-peek]';
  document.addEventListener('mouseover', function(e) {
    var target = e.target.closest(SEL);
    if (target) {
      showTooltip(target, false);
    }
  }, true);

  document.addEventListener('mouseout', function(e) {
    var target = e.target.closest(SEL);
    if (target) {
      hideTooltip();
    }
  }, true);

  // Keyboard accessibility
  document.addEventListener('focusin', function(e) {
    var target = e.target.closest(SEL);
    if (target && target.matches(':focus-visible')) showTooltip(target, true);
  });
  document.addEventListener('focusout', hideTooltip);

  window.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') hideTooltip();
  });

  window.addEventListener('scroll', hideTooltip, true);
})();
