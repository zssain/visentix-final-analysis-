/**
 * Pagination arithmetic, as a pure function.
 *
 * The reason this is not three expressions inline: the page index is state, and
 * the list under it can change (a refresh, a filter, a deletion). A reader
 * sitting on page 5 of 5 when the list shrinks to 12 rows would otherwise get an
 * empty table — which on this screen is indistinguishable from "you have no
 * assessments". Clamping is the whole job, so it is worth being able to test it
 * without a browser.
 */
export interface Page<T> {
  /** The rows to render. */
  rows: T[];
  /** The page actually shown — clamped into range, which may differ from the requested one. */
  page: number;
  pageCount: number;
  /** 1-based index of the first row shown; 0 when there are no rows at all. */
  first: number;
  /** 1-based index of the last row shown; 0 when there are no rows at all. */
  last: number;
}

export function paginate<T>(items: T[], requestedPage: number, size: number): Page<T> {
  const pageCount = Math.max(1, Math.ceil(items.length / size));
  const page = Math.min(Math.max(0, Math.trunc(requestedPage) || 0), pageCount - 1);
  const rows = items.slice(page * size, page * size + size);
  return {
    rows,
    page,
    pageCount,
    first: rows.length === 0 ? 0 : page * size + 1,
    last: rows.length === 0 ? 0 : page * size + rows.length,
  };
}
