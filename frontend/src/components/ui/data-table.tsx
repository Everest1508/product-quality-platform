import * as React from 'react';
import { Button } from './button';
import { Checkbox } from './checkbox';
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuTrigger } from './dropdown-menu';
import { ArrowDownIcon, ArrowUpIcon, EyeIcon, SearchIcon, SortIcon } from './icons';
import { Pagination } from './pagination';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './table';
import { cn } from '@/lib/utils';

export interface Column<T> {
  key: string;
  header: string;
  /** Value used for sorting and filtering. */
  value: (row: T) => string | number;
  /** Custom cell. Defaults to the value. */
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
  align?: 'left' | 'right';
}

/**
 * Table with click-to-sort headers, a filter box and pagination. You pass rows and columns; it holds the rest of the state.
 * Optional: `selectable` adds row checkboxes (with `bulkActions` shown while rows are picked), `columnMenu` lets people hide columns,
 * `maxHeight` scrolls the body under a sticky header, `toolbar` adds controls next to search, `rowActions` adds a trailing actions cell, `onRowClick` makes rows clickable.
 */
export function DataTable<T>({
  rows,
  columns,
  rowKey,
  pageSize = 5,
  filterPlaceholder = 'Filter rows',
  selectable = false,
  bulkActions,
  columnMenu = false,
  maxHeight,
  toolbar,
  rowActions,
  onRowClick,
  className,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  pageSize?: number;
  filterPlaceholder?: string;
  selectable?: boolean;
  /** Rendered in a bar next to the filter while at least one row is selected. */
  bulkActions?: (selected: T[], clear: () => void) => React.ReactNode;
  columnMenu?: boolean;
  /** CSS height, e.g. '20rem'. Body scrolls, header stays put. */
  maxHeight?: string;
  /** Extra controls beside the search box, e.g. a FilterBar. */
  toolbar?: React.ReactNode;
  /** Trailing cell for each row, e.g. a menu of actions. Clicks inside it do not trigger onRowClick. */
  rowActions?: (row: T) => React.ReactNode;
  /** Makes rows clickable (and keyboard focusable), e.g. to open a drawer. */
  onRowClick?: (row: T) => void;
  className?: string;
}) {
  const [q, setQ] = React.useState('');
  const [sort, setSort] = React.useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [page, setPage] = React.useState(1);
  const [picked, setPicked] = React.useState<Set<string>>(new Set());
  const [hidden, setHidden] = React.useState<Set<string>>(new Set());
  const cols = columns.filter((c) => !hidden.has(c.key));

  const data = React.useMemo(() => {
    const term = q.trim().toLowerCase();
    let out = term ? rows.filter((r) => columns.some((c) => String(c.value(r)).toLowerCase().includes(term))) : rows;
    const col = columns.find((c) => c.key === sort?.key);
    if (col && sort) out = [...out].sort((a, b) => {
      const x = col.value(a), y = col.value(b);
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))) * sort.dir;
    });
    return out;
  }, [rows, columns, q, sort]);

  const pageCount = Math.max(1, Math.ceil(data.length / pageSize));
  const current = Math.min(page, pageCount);
  const slice = data.slice((current - 1) * pageSize, current * pageSize);
  const pageKeys = slice.map(rowKey);
  const onPage = pageKeys.filter((k) => picked.has(k)).length;
  const flip = (set: Set<string>, keys: string[], on: boolean) => { const n = new Set(set); keys.forEach((k) => (on ? n.add(k) : n.delete(k))); return n; };
  const selectedRows = rows.filter((r) => picked.has(rowKey(r)));
  const toggle = (key: string) => setSort((s) => (s?.key !== key ? { key, dir: 1 } : s.dir === 1 ? { key, dir: -1 } : null));

  return (
    <div className={cn('grid gap-3', className)}>
      <div className="flex items-center gap-2">
        <div className="relative w-full max-w-xs">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder={filterPlaceholder} className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-4 focus-visible:ring-ring/15" />
        </div>
        {toolbar}
        {selectable && bulkActions && selectedRows.length > 0 && (
          <div className="flex items-center gap-2 rounded-md bg-accent px-3 py-1 text-xs font-medium animate-in">
            {selectedRows.length} selected
            {bulkActions(selectedRows, () => setPicked(new Set()))}
          </div>
        )}
        {columnMenu && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button variant="outline" size="sm" className="ml-auto"><EyeIcon /> Columns</Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              {columns.map((c) => (
                <DropdownMenuCheckboxItem key={c.key} checked={!hidden.has(c.key)} onSelect={(e) => e.preventDefault()} onCheckedChange={(on) => setHidden((h) => flip(h, [c.key], !on))}>{c.header}</DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      <div className="overflow-hidden rounded-xl border">
        <Table wrapperClassName={maxHeight ? 'overflow-y-auto' : undefined} wrapperStyle={maxHeight ? { maxHeight } : undefined}>
          <TableHeader className={maxHeight ? 'sticky top-0 z-10 bg-background' : undefined}>
            <TableRow>
              {selectable && (
                <TableHead className="w-10 pr-0">
                  <Checkbox aria-label="Select page" checked={onPage === 0 ? false : onPage === pageKeys.length ? true : 'indeterminate'} onCheckedChange={(on) => setPicked((s) => flip(s, pageKeys, !!on))} />
                </TableHead>
              )}
              {cols.map((c) => {
                const on = sort?.key === c.key;
                return (
                  <TableHead key={c.key} className={c.align === 'right' ? 'text-right' : undefined} aria-sort={on ? (sort!.dir === 1 ? 'ascending' : 'descending') : undefined}>
                    {c.sortable ? (
                      <button type="button" onClick={() => toggle(c.key)} className={cn('inline-flex items-center gap-1 rounded outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/40', on && 'text-foreground')}>
                        {c.header}
                        {on ? (sort!.dir === 1 ? <ArrowUpIcon className="size-3.5" /> : <ArrowDownIcon className="size-3.5" />) : <SortIcon className="size-3.5 opacity-40" />}
                      </button>
                    ) : c.header}
                  </TableHead>
                );
              })}
              {rowActions && <TableHead className="w-10"><span className="sr-only">Actions</span></TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {slice.map((r) => (
              <TableRow
                key={rowKey(r)}
                className={cn('animate-in', onRowClick && 'cursor-pointer')}
                data-state={picked.has(rowKey(r)) ? 'selected' : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(r) : undefined}
                onKeyDown={onRowClick ? (e) => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onRowClick(r); } } : undefined}
              >
                {selectable && (
                  <TableCell className="w-10 pr-0">
                    <Checkbox aria-label="Select row" checked={picked.has(rowKey(r))} onCheckedChange={(on) => setPicked((s) => flip(s, [rowKey(r)], !!on))} />
                  </TableCell>
                )}
                {cols.map((c) => <TableCell key={c.key} className={c.align === 'right' ? 'text-right tabular-nums' : undefined}>{c.render ? c.render(r) : c.value(r)}</TableCell>)}
                {rowActions && <TableCell className="w-10 pr-3 text-right" onClick={(e) => e.stopPropagation()}>{rowActions(r)}</TableCell>}
              </TableRow>
            ))}
            {slice.length === 0 && <TableRow><TableCell colSpan={cols.length + (selectable ? 1 : 0) + (rowActions ? 1 : 0)} className="py-10 text-center text-muted-foreground">No rows match.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{data.length} row{data.length === 1 ? '' : 's'}{selectable && picked.size > 0 && ` · ${picked.size} selected`}</span>
        {pageCount > 1 && <Pagination page={current} pageCount={pageCount} onPageChange={setPage} />}
      </div>
    </div>
  );
}
