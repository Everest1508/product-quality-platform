// ui-fix: text stress test. Run in the page (browser JS tool or devtools console). Reversible.
// MODE:
//   'expand'      pseudo-localize visible text (+~40% length, accented) — finds truncation/overflow from translation
//   'script'      swap labels/buttons/headings for text in another script (set SCRIPT) — finds font fallback,
//                 clipped diacritics, line-height and wrapping issues
//   'rtl'         flip the page to right-to-left — finds layouts, icons and alignment that don't mirror
//   'long-values' fill text inputs with long but realistic values (never submits)
//   'restore'     put everything back (text, values, placeholders, direction)
// After any mode, take screenshots, then read the returned overflow report. Then run 'restore'.
(() => {
  const MODE = 'expand';       // 'expand' | 'script' | 'rtl' | 'long-values' | 'restore'
  const SCRIPT = 'devanagari'; // for MODE 'script': 'devanagari' | 'arabic' | 'cjk' | 'thai' | 'cyrillic'
  const ROOT = null;           // e.g. 'form'
  const root = (ROOT && document.querySelector(ROOT)) || document.body;
  const store = window.__uifixStress = window.__uifixStress || { text: new Map(), values: new Map(), ph: new Map(), dir: null };

  const setNativeValue = (el, v) => {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  };

  if (MODE === 'restore') {
    store.text.forEach((v, node) => { if (node.isConnected) node.nodeValue = v; });
    store.values.forEach((v, el) => { if (el.isConnected) setNativeValue(el, v); });
    store.ph.forEach((v, el) => { if (el.isConnected) el.setAttribute('placeholder', v); });
    if (store.dir !== null) { document.documentElement.setAttribute('dir', store.dir); if (!store.dir) document.documentElement.removeAttribute('dir'); }
    const n = store.text.size + store.values.size + store.ph.size;
    window.__uifixStress = null;
    console.log(`ui-fix stress: restored ${n} items`);
    return { restored: n };
  }

  const ACCENT = { a: 'á', e: 'é', i: 'í', o: 'ö', u: 'ü', c: 'ç', n: 'ñ', A: 'Å', E: 'É', I: 'Î', O: 'Ø', U: 'Û', C: 'Ç', N: 'Ñ', s: 'š', y: 'ý' };
  const pseudo = s => {
    const core = s.replace(/[aeioucnAEIOUCNsy]/g, ch => ACCENT[ch] || ch);
    const pad = Math.max(2, Math.round(s.trim().length * 0.4));
    return `[${core} ${'·'.repeat(pad)}]`;
  };
  // Generic UI phrases (name, email, address, city, choose, save, cancel, yes, no, required, search, settings)
  const PHRASES = {
    devanagari: ['पूर्ण नाव', 'ईमेल पत्ता', 'पत्ता ओळ १', 'शहर निवडा', 'जतन करा', 'रद्द करा', 'होय', 'नाही', 'आवश्यक माहिती भरा', 'शोधा', 'सेटिंग्ज'],
    arabic: ['الاسم الكامل', 'عنوان البريد الإلكتروني', 'سطر العنوان ١', 'اختر المدينة', 'حفظ', 'إلغاء', 'نعم', 'لا', 'يرجى ملء الحقول المطلوبة', 'بحث', 'الإعدادات'],
    cjk: ['氏名', 'メールアドレス', '住所 1 行目', '市区町村を選択', '保存', 'キャンセル', 'はい', 'いいえ', '必須項目を入力してください', '検索', '設定'],
    thai: ['ชื่อเต็ม', 'ที่อยู่อีเมล', 'ที่อยู่บรรทัดที่ 1', 'เลือกเมือง', 'บันทึก', 'ยกเลิก', 'ใช่', 'ไม่ใช่', 'กรุณากรอกข้อมูลที่จำเป็น', 'ค้นหา', 'การตั้งค่า'],
    cyrillic: ['Полное имя', 'Адрес электронной почты', 'Адресная строка 1', 'Выберите город', 'Сохранить', 'Отменить', 'Да', 'Нет', 'Заполните обязательные поля', 'Поиск', 'Настройки'],
  };
  const P = PHRASES[SCRIPT] || PHRASES.devanagari;
  const other = (s, i) => { const base = P[i % P.length]; return s.trim().length > 18 ? `${base} — ${P[(i + 3) % P.length]}` : base; };

  if (MODE === 'rtl') {
    if (store.dir === null) store.dir = document.documentElement.getAttribute('dir') || '';
    document.documentElement.setAttribute('dir', 'rtl');
  }

  if (MODE === 'expand' || MODE === 'script') {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: n => {
        const p = n.parentElement;
        if (!p || !n.nodeValue.trim() || /^(SCRIPT|STYLE|NOSCRIPT|OPTION|TEXTAREA)$/.test(p.tagName)) return NodeFilter.FILTER_REJECT;
        if (MODE === 'script' && !p.closest('label, button, legend, h1, h2, h3, h4, h5, h6, th, [role=tab], [class*=label], [class*=title]')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let n, i = 0;
    while ((n = walker.nextNode())) {
      if (!store.text.has(n)) store.text.set(n, n.nodeValue);
      const orig = store.text.get(n);
      n.nodeValue = MODE === 'expand' ? pseudo(orig) : other(orig, i++);
    }
    root.querySelectorAll('[placeholder]').forEach((el, k) => {
      if (!store.ph.has(el)) store.ph.set(el, el.getAttribute('placeholder'));
      const o = store.ph.get(el);
      el.setAttribute('placeholder', MODE === 'expand' ? pseudo(o) : other(o, k));
    });
  }

  if (MODE === 'long-values') {
    const LONG = {
      email: 'maria.gonzalez-fitzgerald.accounts@international-distribution-group.example.com',
      tel: '+44 20 7946 0958 ext. 4521',
      url: 'https://customer-portal.example-international.com/accounts/2026/orders/very-long-path',
      text: 'Wolfeschlegelsteinhausen-Bergerdorff International Trading Company Ltd., Building 7',
      search: 'wireless noise cancelling over-ear headphones with long battery life',
    };
    root.querySelectorAll('input[type=text], input:not([type]), input[type=email], input[type=tel], input[type=url], input[type=search], textarea').forEach(el => {
      if (el.disabled || el.readOnly) return;
      if (!store.values.has(el)) store.values.set(el, el.value);
      const kind = el.tagName === 'TEXTAREA' ? 'text' : (el.type || 'text');
      setNativeValue(el, el.tagName === 'TEXTAREA' ? Array(4).fill(LONG.text).join('. ') : (LONG[kind] || LONG.text));
    });
  }

  // overflow report
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const clipped = [...root.querySelectorAll('label, button, a, h1, h2, h3, h4, h5, h6, legend, th, td, [role=tab], span, p, div')]
    .filter(el => vis(el) && !el.children.length && (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 4) && /hidden|clip|ellipsis/.test(getComputedStyle(el).overflow + getComputedStyle(el).textOverflow))
    .slice(0, 25).map(el => (el.innerText || '').trim().slice(0, 50));
  const offscreen = [...root.querySelectorAll('*')].filter(el => { const r = el.getBoundingClientRect(); return vis(el) && r.right > innerWidth + 2; }).slice(0, 15).map(el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + ' ' + ((el.innerText || '').trim().slice(0, 30)));
  const result = { mode: MODE, horizontalScroll: document.documentElement.scrollWidth > innerWidth, clippedText: clipped, pastRightEdge: offscreen, next: "Screenshot now, then run with MODE = 'restore'." };
  console.log(JSON.stringify(result, null, 2));
  return result;
})();
