// One place that navigates the whole page, so tests can replace it.
export const go = (url: string) => window.location.assign(url);
