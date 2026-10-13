import type { RouteObject } from 'react-router-dom';
import { Notifications } from '@/pages/Notifications';
import { TicketDetailPage } from '@/pages/ticket/TicketDetailPage';
import { TicketFormPage } from '@/pages/ticket/TicketFormPage';
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
  { path: '/tickets/create/', element: <TicketFormPage /> },
  { path: '/products/:pk/tickets/create/', element: <TicketFormPage /> },
  { path: '/tickets/:id/edit/', element: <TicketFormPage /> },
  { path: '/tickets/:id/', element: <TicketDetailPage /> },
  { path: '/products/:pk/tickets/:id/', element: <TicketDetailPage /> },
];
