import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import api from '@/services/api';
import type {
  Package,
  BOQItem,
  PackageStatistics,
  BOQStatistics,
  PaginatedResponse,
  MessageResponse,
} from '@/types';

const PACKAGES_KEY = 'packages';
const BOQ_KEY = 'boq';

// Package Hooks
export function usePackages(projectId: number, page = 1, pageSize = 50) {
  return useQuery({
    queryKey: [PACKAGES_KEY, projectId, page, pageSize],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<Package>>(
        `/projects/${projectId}/packages`,
        { params: { page, page_size: pageSize } }
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function usePackage(projectId: number, packageId: number) {
  return useQuery({
    queryKey: [PACKAGES_KEY, projectId, packageId],
    queryFn: async () => {
      const response = await api.get<Package>(
        `/projects/${projectId}/packages/${packageId}`
      );
      return response.data;
    },
    enabled: !!projectId && !!packageId,
  });
}

export function usePackageStatistics(projectId: number) {
  return useQuery({
    queryKey: [PACKAGES_KEY, projectId, 'statistics'],
    queryFn: async () => {
      const response = await api.get<PackageStatistics>(
        `/projects/${projectId}/packages/statistics`
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function useCreatePackage(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      name: string;
      code: string;
      trade_category: string;
      description?: string;
    }) => {
      const response = await api.post<Package>(
        `/projects/${projectId}/packages`,
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PACKAGES_KEY, projectId] });
      toast.success('Package created successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create package');
    },
  });
}

export function useAutoCreatePackages(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const response = await api.post<MessageResponse>(
        `/projects/${projectId}/packages/auto-create`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PACKAGES_KEY, projectId] });
      toast.success('Packages created automatically');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to auto-create packages');
    },
  });
}

export function useLinkBOQToPackage(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      packageId,
      boqItemIds,
    }: {
      packageId: number;
      boqItemIds: number[];
    }) => {
      const response = await api.post<MessageResponse>(
        `/projects/${projectId}/packages/${packageId}/link-boq`,
        { boq_item_ids: boqItemIds }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PACKAGES_KEY, projectId] });
      queryClient.invalidateQueries({ queryKey: [BOQ_KEY, projectId] });
      toast.success('BOQ items linked successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to link BOQ items');
    },
  });
}

// BOQ Hooks
export function useBOQItems(projectId: number, page = 1, pageSize = 100) {
  return useQuery({
    queryKey: [BOQ_KEY, projectId, page, pageSize],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<BOQItem>>(
        `/projects/${projectId}/boq`,
        { params: { page, page_size: pageSize } }
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function useBOQStatistics(projectId: number) {
  return useQuery({
    queryKey: [BOQ_KEY, projectId, 'statistics'],
    queryFn: async () => {
      const response = await api.get<BOQStatistics>(
        `/projects/${projectId}/boq/statistics`
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function useParseBOQ(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: number) => {
      const response = await api.post<MessageResponse>(
        `/projects/${projectId}/boq/parse/${documentId}`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [BOQ_KEY, projectId] });
      toast.success('BOQ parsing started');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to parse BOQ');
    },
  });
}

export function useUpdateBOQItem(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ itemId, data }: { itemId: number; data: Partial<BOQItem> }) => {
      const response = await api.put<BOQItem>(
        `/projects/${projectId}/boq/${itemId}`,
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [BOQ_KEY, projectId] });
      toast.success('BOQ item updated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update BOQ item');
    },
  });
}
