// Mac shows ⌘ and ⌥; Windows and Linux show Ctrl and Alt. The handlers accept either key on every system.
export const isMac = () => typeof navigator !== 'undefined' && /mac|iphone|ipad|ipod/i.test(navigator.platform || navigator.userAgent || '');
export const modLabel = () => (isMac() ? '⌘' : 'Ctrl');
