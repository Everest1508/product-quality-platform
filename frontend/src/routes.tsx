import type { RouteObject } from 'react-router-dom';
import { Notifications } from '@/pages/Notifications';
import { TicketsPage } from '@/pages/tickets/TicketsPage';

export const shellRoutes: RouteObject[] = [
  { path: '/notifications/', element: <Notifications /> },
  ...[
    '/tickets/',
    '/tickets/kanban/',
    '/tickets/list/',
    '/products/:pk/tickets/',
    '/products/:pk/tickets/kanban/',
    '/products/:pk/tickets/list/',
  ].map((path) => ({ path, element: <TicketsPage /> })),
];
