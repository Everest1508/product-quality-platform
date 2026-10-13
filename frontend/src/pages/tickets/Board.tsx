import type { BoardResponse } from './types';

export function Board({ data }: { data: BoardResponse }) {
  return <div>{data.total} tickets</div>;
}
