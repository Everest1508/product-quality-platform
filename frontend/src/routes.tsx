import type { RouteObject } from 'react-router-dom';
import { Notifications } from '@/pages/Notifications';

export const shellRoutes: RouteObject[] = [{ path: '/notifications/', element: <Notifications /> }];
