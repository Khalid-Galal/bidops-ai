import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import api, { uploadFile } from '@/services/api';
import type { Offer, OfferComparison, PaginatedResponse, MessageResponse } from '@/types';

const QUERY_KEY = 'offers';

export function useOffers(packageId?: number, page = 1, pageSize = 50) {
  return useQuery({
    queryKey: [QUERY_KEY, packageId, page, pageSize],
    queryFn: async () => {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (packageId) params.package_id = packageId;

      const response = await api.get<PaginatedResponse<Offer>>('/offers', { params });
      return response.data;
    },
  });
}

export function useOffer(id: number) {
  return useQuery({
    queryKey: [QUERY_KEY, id],
    queryFn: async () => {
      const response = await api.get<Offer>(`/offers/${id}`);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useOfferComparison(packageId: number) {
  return useQuery({
    queryKey: [QUERY_KEY, 'comparison', packageId],
    queryFn: async () => {
      const response = await api.get<OfferComparison>(
        `/offers/comparison/${packageId}`
      );
      return response.data;
    },
    enabled: !!packageId,
  });
}

export function useUploadOffer(packageId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      supplierId,
      onProgress,
    }: {
      file: File;
      supplierId: number;
      onProgress?: (progress: number) => void;
    }) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('supplier_id', supplierId.toString());

      const response = await api.post(`/offers/upload/${packageId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (onProgress && progressEvent.total) {
            const progress = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            onProgress(progress);
          }
        },
      });
      return response.data as Offer;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('Offer uploaded successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to upload offer');
    },
  });
}

export function useEvaluateOffer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (offerId: number) => {
      const response = await api.post<Offer>(`/offers/${offerId}/evaluate`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('Offer evaluated successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to evaluate offer');
    },
  });
}

export function useSelectOffer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (offerId: number) => {
      const response = await api.post<Offer>(`/offers/${offerId}/select`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('Offer selected successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to select offer');
    },
  });
}

export function useRejectOffer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (offerId: number) => {
      const response = await api.post<Offer>(`/offers/${offerId}/reject`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('Offer rejected');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to reject offer');
    },
  });
}

export function useEvaluateAllOffers(packageId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const response = await api.post<MessageResponse>(
        `/offers/evaluate-all/${packageId}`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('All offers evaluated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to evaluate offers');
    },
  });
}
