const COLORS = ['#f59e0b', '#10b981', '#3b82f6', '#ec4899', '#8b5cf6', '#ef4444'];

// A short burst of paper from a point (default: the middle of the window). Plain DOM, no library; skipped for reduced motion.
export function confetti(origin?: { x: number; y: number }, count = 36) {
  if (typeof document === 'undefined' || (typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
  const x0 = origin?.x ?? window.innerWidth / 2;
  const y0 = origin?.y ?? window.innerHeight / 3;
  const layer = document.createElement('div');
  layer.setAttribute('aria-hidden', 'true');
  layer.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:100;overflow:hidden';
  for (let i = 0; i < count; i++) {
    const p = document.createElement('i');
    const a = Math.random() * Math.PI * 2;
    const d = 80 + Math.random() * 160;
    p.style.cssText = `position:absolute;left:${x0}px;top:${y0}px;width:${6 + Math.random() * 5}px;height:${4 + Math.random() * 6}px;background:${COLORS[i % COLORS.length]};border-radius:2px`;
    p.animate(
      [
        { transform: 'translate(0,0) rotate(0)', opacity: 1 },
        { transform: `translate(${Math.cos(a) * d}px,${Math.sin(a) * d - 60}px) rotate(${Math.random() * 360}deg)`, opacity: 1, offset: 0.45 },
        { transform: `translate(${Math.cos(a) * d * 1.2}px,${Math.sin(a) * d + 220}px) rotate(${Math.random() * 720}deg)`, opacity: 0 },
      ],
      { duration: 1300 + Math.random() * 500, easing: 'cubic-bezier(.2,.7,.4,1)', fill: 'forwards' },
    );
    layer.appendChild(p);
  }
  document.body.appendChild(layer);
  setTimeout(() => layer.remove(), 2000);
}
