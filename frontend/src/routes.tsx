import type { RouteObject } from 'react-router-dom';
import { ErrorDetailPage } from '@/pages/errors/ErrorDetailPage';
import { ErrorFormPage } from '@/pages/errors/ErrorFormPage';
import { ErrorsPage } from '@/pages/errors/ErrorsPage';
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
  { path: '/errors/', element: <ErrorsPage /> },
  { path: '/products/:pk/errors/', element: <ErrorsPage /> },
  { path: '/errors/create/', element: <ErrorFormPage /> },
  { path: '/products/:pk/errors/create/', element: <ErrorFormPage /> },
  { path: '/errors/:id/', element: <ErrorDetailPage /> },
  { path: '/products/:pk/errors/:error_pk/', element: <ErrorDetailPage /> },
];
