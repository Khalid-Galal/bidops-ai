import { useNavigate } from 'react-router-dom';
import {
  FolderIcon,
  DocumentTextIcon,
  CubeIcon,
  UserGroupIcon,
  CurrencyDollarIcon,
  ArrowTrendingUpIcon,
} from '@heroicons/react/24/outline';
import { Card, CardBody, Button } from '@/components/ui';
import { useProjects } from '@/hooks/useProjects';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
}

function StatCard({ title, value, icon: Icon, change, changeType = 'neutral' }: StatCardProps) {
  const changeColors = {
    positive: 'text-green-600',
    negative: 'text-red-600',
    neutral: 'text-gray-500',
  };

  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500">{title}</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
            {change && (
              <p className={`mt-1 text-sm ${changeColors[changeType]}`}>
                {change}
              </p>
            )}
          </div>
          <div className="p-3 bg-primary-50 rounded-lg">
            <Icon className="w-6 h-6 text-primary-600" />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data: projectsData, isLoading } = useProjects(1, 5);

  const stats = [
    { title: 'Total Projects', value: projectsData?.total || 0, icon: FolderIcon },
    { title: 'Active Tenders', value: 3, icon: DocumentTextIcon },
    { title: 'Total Packages', value: 24, icon: CubeIcon },
    { title: 'Suppliers', value: 156, icon: UserGroupIcon },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-1 text-gray-500">Overview of your tender operations</p>
        </div>
        <Button onClick={() => navigate('/projects')}>
          View All Projects
        </Button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <StatCard key={stat.title} {...stat} />
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Projects */}
        <Card>
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Recent Projects</h3>
            <Button variant="ghost" size="sm" onClick={() => navigate('/projects')}>
              View All
            </Button>
          </div>
          <CardBody className="p-0">
            {isLoading ? (
              <div className="p-6 space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse flex space-x-4">
                    <div className="rounded-lg bg-gray-200 h-10 w-10"></div>
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                      <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : projectsData?.items.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No projects yet. Create your first project to get started.
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {projectsData?.items.map((project) => (
                  <li
                    key={project.id}
                    className="px-6 py-4 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/projects/${project.id}`)}
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-2 bg-primary-50 rounded-lg">
                        <FolderIcon className="w-5 h-5 text-primary-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {project.name}
                        </p>
                        <p className="text-sm text-gray-500">
                          {project.code || 'No code'} - {project.status}
                        </p>
                      </div>
                      <span className="text-xs text-gray-400">
                        {new Date(project.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        {/* Quick Actions */}
        <Card>
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Quick Actions</h3>
          </div>
          <CardBody>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => navigate('/projects')}
                className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left transition-colors"
              >
                <FolderIcon className="w-8 h-8 text-primary-600 mb-2" />
                <p className="font-medium text-gray-900">New Project</p>
                <p className="text-sm text-gray-500">Create a new tender</p>
              </button>

              <button
                onClick={() => navigate('/suppliers')}
                className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left transition-colors"
              >
                <UserGroupIcon className="w-8 h-8 text-green-600 mb-2" />
                <p className="font-medium text-gray-900">Manage Suppliers</p>
                <p className="text-sm text-gray-500">View and edit suppliers</p>
              </button>

              <button
                onClick={() => navigate('/offers')}
                className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left transition-colors"
              >
                <DocumentTextIcon className="w-8 h-8 text-blue-600 mb-2" />
                <p className="font-medium text-gray-900">Review Offers</p>
                <p className="text-sm text-gray-500">Evaluate submissions</p>
              </button>

              <button
                className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left transition-colors"
              >
                <ArrowTrendingUpIcon className="w-8 h-8 text-purple-600 mb-2" />
                <p className="font-medium text-gray-900">View Reports</p>
                <p className="text-sm text-gray-500">Analytics & insights</p>
              </button>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Activity Feed */}
      <Card>
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Recent Activity</h3>
        </div>
        <CardBody>
          <div className="text-center py-8 text-gray-500">
            <CurrencyDollarIcon className="w-12 h-12 mx-auto text-gray-300 mb-3" />
            <p>Activity feed will show recent actions here</p>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
