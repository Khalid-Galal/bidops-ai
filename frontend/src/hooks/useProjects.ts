import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import api from '@/services/api';
import { useProjectStore } from '@/store/projectStore';
import type { Project, PaginatedResponse, MessageResponse } from '@/types';

const QUERY_KEY = 'projects';

export function useProjects(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: [QUERY_KEY, page, pageSize],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<Project>>('/projects', {
        params: { page, page_size: pageSize },
      });
      return response.data;
    },
  });
}

export function useProject(id: number) {
  const setCurrentProject = useProjectStore((state) => state.setCurrentProject);

  return useQuery({
    queryKey: [QUERY_KEY, id],
    queryFn: async () => {
      const response = await api.get<Project>(`/projects/${id}`);
      setCurrentProject(response.data);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  const addProject = useProjectStore((state) => state.addProject);

  return useMutation({
    mutationFn: async (data: { name: string; code?: string; description?: string }) => {
      const response = await api.post<Project>('/projects', data);
      return response.data;
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      addProject(project);
      toast.success('Project created successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create project');
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  const updateProject = useProjectStore((state) => state.updateProject);

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<Project> }) => {
      const response = await api.put<Project>(`/projects/${id}`, data);
      return response.data;
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, project.id] });
      updateProject(project.id, project);
      toast.success('Project updated successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update project');
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  const removeProject = useProjectStore((state) => state.removeProject);

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete<MessageResponse>(`/projects/${id}`);
      return { id, ...response.data };
    },
    onSuccess: ({ id }) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      removeProject(id);
      toast.success('Project deleted successfully');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to delete project');
    },
  });
}

export function useIngestProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await api.post<MessageResponse>(`/projects/${id}/ingest`);
      return response.data;
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, id] });
      toast.success('Project ingestion started');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to start ingestion');
    },
  });
}
