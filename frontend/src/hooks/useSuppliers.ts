import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import api, { uploadFile } from '@/services/api';
import type { Supplier, PaginatedResponse, MessageResponse } from '@/types';

const QUERY_KEY = 'suppliers';

export function useSuppliers(
  page = 1,
  pageSize = 50,
  filters?: { trade_category?: string; search?: string }
) {
  return useQuery({
    queryKey: [QUERY_KEY, page, pageSize, filters],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<Supplier>>('/suppliers', {
        params: { page, page_size: pageSize, ...filters },
      });
      return response.data;
    },
  });
}

export function useSupplier(id: number) {
  return useQuery({
    queryKey: [QUERY_KEY, id],
    queryFn: async () => {
      const response = await api.get<Supplier>(`/suppliers/${id}`);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateSupplier() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      name: string;
      code?: string;
      emails: string[];
      trade_categories: string[];
      contact_name?: string;
      phone?: string;
      region?: string;
      country?: string;
    }) => {
      const response = await api.post<Supplier>('/suppliers', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('Supplier created successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create supplier');
    },
  });
}

export function useUpdateSupplier() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<Supplier> }) => {
      const response = await api.put<Supplier>(`/suppliers/${id}`, data);
      return response.data;
    },
    onSuccess: (supplier) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, supplier.id] });
      toast.success('Supplier updated successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update supplier');
    },
  });
}

export function useDeleteSupplier() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete<MessageResponse>(`/suppliers/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('Supplier deleted successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to delete supplier');
    },
  });
}

export function useImportSuppliers() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      onProgress,
    }: {
      file: File;
      onProgress?: (progress: number) => void;
    }) => {
      const response = await uploadFile('/suppliers/import', file, onProgress);
      return response.data as MessageResponse;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('Suppliers imported successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to import suppliers');
    },
  });
}

export function useSuppliersByTrade(tradeCategory: string) {
  return useQuery({
    queryKey: [QUERY_KEY, 'by-trade', tradeCategory],
    queryFn: async () => {
      const response = await api.get<Supplier[]>(
        `/suppliers/by-trade/${tradeCategory}`
      );
      return response.data;
    },
    enabled: !!tradeCategory,
  });
}
