const KEY = 'pq:seen-version';

// The release this browser has already been shown. Without storage the dialog is simply shown each visit.
export const seenVersion = () => {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
};

export const markSeen = (version: string) => {
  try {
    localStorage.setItem(KEY, version);
  } catch {
    /* not remembered */
  }
};
