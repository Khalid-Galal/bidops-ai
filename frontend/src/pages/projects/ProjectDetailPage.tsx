import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  DocumentTextIcon,
  CubeIcon,
  TableCellsIcon,
  CurrencyDollarIcon,
  ArrowPathIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { Card, CardBody, CardHeader, Button, StatusBadge, LoadingPage } from '@/components/ui';
import { useProject, useIngestProject, useDeleteProject } from '@/hooks/useProjects';

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = parseInt(id || '0');

  const { data: project, isLoading } = useProject(projectId);
  const ingestProject = useIngestProject();
  const deleteProject = useDeleteProject();

  if (isLoading) return <LoadingPage />;
  if (!project) return <div>Project not found</div>;

  const handleIngest = () => {
    ingestProject.mutate(projectId);
  };

  const handleDelete = async () => {
    if (confirm('Are you sure you want to delete this project?')) {
      await deleteProject.mutateAsync(projectId);
      navigate('/projects');
    }
  };

  const quickLinks = [
    { name: 'Documents', href: `/projects/${projectId}/documents`, icon: DocumentTextIcon, count: 0 },
    { name: 'BOQ Items', href: `/projects/${projectId}/boq`, icon: TableCellsIcon, count: 0 },
    { name: 'Packages', href: `/projects/${projectId}/packages`, icon: CubeIcon, count: 0 },
    { name: 'Pricing', href: `/projects/${projectId}/pricing`, icon: CurrencyDollarIcon, count: 0 },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
            <StatusBadge status={project.status} />
          </div>
          <p className="mt-1 text-gray-500">
            {project.code && `${project.code} - `}
            Created {new Date(project.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={handleIngest}
            isLoading={ingestProject.isPending}
          >
            <ArrowPathIcon className="w-5 h-5 mr-2" />
            Process Documents
          </Button>
          <Button variant="danger" onClick={handleDelete}>
            <TrashIcon className="w-5 h-5 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {quickLinks.map((link) => (
          <Link key={link.name} to={link.href}>
            <Card className="hover:shadow-md transition-shadow cursor-pointer">
              <CardBody className="flex items-center gap-4">
                <div className="p-3 bg-primary-50 rounded-lg">
                  <link.icon className="w-6 h-6 text-primary-600" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-gray-900">{link.name}</p>
                  <p className="text-sm text-gray-500">{link.count} items</p>
                </div>
              </CardBody>
            </Card>
          </Link>
        ))}
      </div>

      {/* Project Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader title="Project Details" />
          <CardBody>
            <dl className="space-y-4">
              <div>
                <dt className="text-sm font-medium text-gray-500">Description</dt>
                <dd className="mt-1 text-gray-900">
                  {project.description || 'No description provided'}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Folder Path</dt>
                <dd className="mt-1 text-gray-900 font-mono text-sm">
                  {project.folder_path || 'Not set'}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Last Updated</dt>
                <dd className="mt-1 text-gray-900">
                  {new Date(project.updated_at).toLocaleString()}
                </dd>
              </div>
            </dl>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="AI Summary" />
          <CardBody>
            {project.summary ? (
              <dl className="space-y-4">
                {Object.entries(project.summary).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-sm font-medium text-gray-500 capitalize">
                      {key.replace(/_/g, ' ')}
                    </dt>
                    <dd className="mt-1 text-gray-900">
                      {value.value}
                      {value.confidence < 0.8 && (
                        <span className="ml-2 text-xs text-yellow-600">
                          (Low confidence: {Math.round(value.confidence * 100)}%)
                        </span>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-gray-500 text-center py-8">
                No summary available. Process documents to generate AI summary.
              </p>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Checklist */}
      {project.checklist && project.checklist.length > 0 && (
        <Card>
          <CardHeader title="Requirements Checklist" />
          <CardBody>
            <div className="space-y-6">
              {project.checklist.map((category) => (
                <div key={category.category}>
                  <h4 className="font-medium text-gray-900 mb-3">{category.category}</h4>
                  <ul className="space-y-2">
                    {category.requirements.map((req, index) => (
                      <li key={index} className="flex items-start gap-3">
                        <span
                          className={`mt-1 w-2 h-2 rounded-full ${
                            req.status === 'met'
                              ? 'bg-green-500'
                              : req.status === 'not_met'
                              ? 'bg-red-500'
                              : 'bg-gray-300'
                          }`}
                        />
                        <div className="flex-1">
                          <p className="text-sm text-gray-900">
                            {req.requirement}
                            {req.mandatory && (
                              <span className="ml-2 text-xs text-red-600">(Mandatory)</span>
                            )}
                          </p>
                          {req.evidence && (
                            <p className="text-xs text-gray-500 mt-1">{req.evidence}</p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
