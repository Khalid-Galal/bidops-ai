import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import api, { uploadFile } from '@/services/api';
import type { Document, PaginatedResponse, MessageResponse } from '@/types';

const QUERY_KEY = 'documents';

export function useDocuments(projectId: number, page = 1, pageSize = 50) {
  return useQuery({
    queryKey: [QUERY_KEY, projectId, page, pageSize],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<Document>>(
        `/projects/${projectId}/documents`,
        { params: { page, page_size: pageSize } }
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function useDocument(projectId: number, documentId: number) {
  return useQuery({
    queryKey: [QUERY_KEY, projectId, documentId],
    queryFn: async () => {
      const response = await api.get<Document>(
        `/projects/${projectId}/documents/${documentId}`
      );
      return response.data;
    },
    enabled: !!projectId && !!documentId,
  });
}

export function useUploadDocument(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      onProgress,
    }: {
      file: File;
      onProgress?: (progress: number) => void;
    }) => {
      const response = await uploadFile(
        `/projects/${projectId}/documents/upload`,
        file,
        onProgress
      );
      return response.data as Document;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, projectId] });
      toast.success('Document uploaded successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to upload document');
    },
  });
}

export function useUploadFolder(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (folderPath: string) => {
      const response = await api.post<MessageResponse>(
        `/projects/${projectId}/documents/upload-folder`,
        { folder_path: folderPath }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, projectId] });
      toast.success('Folder uploaded successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to upload folder');
    },
  });
}

export function useDeleteDocument(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: number) => {
      const response = await api.delete<MessageResponse>(
        `/projects/${projectId}/documents/${documentId}`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, projectId] });
      toast.success('Document deleted successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to delete document');
    },
  });
}

export function useReprocessDocument(projectId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: number) => {
      const response = await api.post<MessageResponse>(
        `/projects/${projectId}/documents/${documentId}/reprocess`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, projectId] });
      toast.success('Document reprocessing started');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to reprocess document');
    },
  });
}
