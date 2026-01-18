import { create } from 'zustand';
import type { Project } from '@/types';

interface ProjectState {
  currentProject: Project | null;
  projects: Project[];
  isLoading: boolean;

  // Actions
  setCurrentProject: (project: Project | null) => void;
  setProjects: (projects: Project[]) => void;
  setLoading: (loading: boolean) => void;
  updateProject: (id: number, updates: Partial<Project>) => void;
  addProject: (project: Project) => void;
  removeProject: (id: number) => void;
}

export const useProjectStore = create<ProjectState>()((set) => ({
  currentProject: null,
  projects: [],
  isLoading: false,

  setCurrentProject: (project) =>
    set({ currentProject: project }),

  setProjects: (projects) =>
    set({ projects }),

  setLoading: (isLoading) =>
    set({ isLoading }),

  updateProject: (id, updates) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === id ? { ...p, ...updates } : p
      ),
      currentProject:
        state.currentProject?.id === id
          ? { ...state.currentProject, ...updates }
          : state.currentProject,
    })),

  addProject: (project) =>
    set((state) => ({
      projects: [project, ...state.projects],
    })),

  removeProject: (id) =>
    set((state) => ({
      projects: state.projects.filter((p) => p.id !== id),
      currentProject:
        state.currentProject?.id === id ? null : state.currentProject,
    })),
}));
