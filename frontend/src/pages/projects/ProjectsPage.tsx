import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PlusIcon, FolderIcon } from '@heroicons/react/24/outline';
import { Card, CardBody, Button, DataTable, Modal, ModalFooter, Input, StatusBadge } from '@/components/ui';
import { useProjects, useCreateProject } from '@/hooks/useProjects';
import type { Project } from '@/types';
import type { Column } from '@/components/ui/DataTable';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', code: '', description: '' });

  const { data, isLoading } = useProjects();
  const createProject = useCreateProject();

  const columns: Column<Project>[] = [
    {
      key: 'name',
      header: 'Project Name',
      render: (project) => (
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary-50 rounded-lg">
            <FolderIcon className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <p className="font-medium text-gray-900">{project.name}</p>
            <p className="text-sm text-gray-500">{project.code || 'No code'}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (project) => <StatusBadge status={project.status} />,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (project) => (
        <span className="text-gray-500">
          {new Date(project.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'updated_at',
      header: 'Last Updated',
      render: (project) => (
        <span className="text-gray-500">
          {new Date(project.updated_at).toLocaleDateString()}
        </span>
      ),
    },
  ];

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await createProject.mutateAsync(newProject);
    setIsModalOpen(false);
    setNewProject({ name: '', code: '', description: '' });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="mt-1 text-gray-500">Manage your tender projects</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          <PlusIcon className="w-5 h-5 mr-2" />
          New Project
        </Button>
      </div>

      {/* Projects Table */}
      <Card>
        <CardBody className="p-0">
          <DataTable
            columns={columns}
            data={data?.items || []}
            keyExtractor={(project) => project.id}
            onRowClick={(project) => navigate(`/projects/${project.id}`)}
            isLoading={isLoading}
            emptyMessage="No projects found. Create your first project to get started."
          />
        </CardBody>
      </Card>

      {/* Pagination Info */}
      {data && data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>
            Showing {data.items.length} of {data.total} projects
          </span>
          <span>
            Page {data.page} of {data.pages}
          </span>
        </div>
      )}

      {/* Create Project Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create New Project"
        description="Enter the details for your new tender project"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Project Name"
            value={newProject.name}
            onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
            placeholder="e.g., Commercial Tower - Phase 1"
            required
          />
          <Input
            label="Project Code"
            value={newProject.code}
            onChange={(e) => setNewProject({ ...newProject, code: e.target.value })}
            placeholder="e.g., CT-2024-001"
          />
          <Input
            label="Description"
            value={newProject.description}
            onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
            placeholder="Brief description of the project"
          />
          <ModalFooter className="-mx-6 -mb-4 mt-6">
            <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createProject.isPending}>
              Create Project
            </Button>
          </ModalFooter>
        </form>
      </Modal>
    </div>
  );
}
