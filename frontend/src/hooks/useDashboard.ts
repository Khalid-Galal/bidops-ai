import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';
import type { DashboardStats, ProjectTotals, CostBreakdown } from '@/types';

export function useDashboardStats(projectId: number) {
  return useQuery({
    queryKey: ['dashboard', projectId],
    queryFn: async () => {
      const response = await api.get<DashboardStats>(
        `/dashboard/project/${projectId}`
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function useProjectTotals(projectId: number) {
  return useQuery({
    queryKey: ['pricing', 'totals', projectId],
    queryFn: async () => {
      const response = await api.get<ProjectTotals>(
        `/pricing/project/${projectId}/totals`
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function useCostBreakdown(projectId: number) {
  return useQuery({
    queryKey: ['pricing', 'breakdown', projectId],
    queryFn: async () => {
      const response = await api.get<CostBreakdown>(
        `/pricing/project/${projectId}/breakdown`
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}
