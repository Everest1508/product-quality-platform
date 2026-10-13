import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { AuditResponse, ProductDashboard, Report } from './types';

export const useReport = (query: string) =>
  useQuery({ queryKey: ['report', query], queryFn: () => api.get<Report>(`reports/${query ? `?${query}` : ''}`), placeholderData: keepPreviousData });
export const useAudit = (query: string) =>
  useQuery({ queryKey: ['audit', query], queryFn: () => api.get<AuditResponse>(`audit/${query ? `?${query}` : ''}`), placeholderData: keepPreviousData });
export const useProductDashboard = (id: number) =>
  useQuery({ queryKey: ['product-dashboard', id], queryFn: () => api.get<ProductDashboard>(`dashboards/product/${id}/`) });
