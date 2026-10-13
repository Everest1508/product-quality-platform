import { useEffect, useState } from 'react';

// Counts a whole number up from 0 once, when it first shows. Anything that is not a plain number is shown as it is.
export function CountUp({ value, ms = 700 }: { value: number | string; ms?: number }) {
  const num = typeof value === 'number' ? value : NaN;
  const still = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [shown, setShown] = useState(still || !Number.isFinite(num) ? num : 0);
  useEffect(() => {
    if (still || !Number.isFinite(num)) return setShown(num);
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setShown(Math.round(num * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [num, ms, still]);
  return <>{Number.isFinite(num) ? shown : value}</>;
}
