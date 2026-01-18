import { NavLink, useParams } from 'react-router-dom';
import {
  HomeIcon,
  FolderIcon,
  DocumentTextIcon,
  CubeIcon,
  TableCellsIcon,
  UserGroupIcon,
  DocumentDuplicateIcon,
  CurrencyDollarIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';
import { useProjectStore } from '@/store/projectStore';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  projectRequired?: boolean;
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Projects', href: '/projects', icon: FolderIcon },
];

const projectNavigation: NavItem[] = [
  { name: 'Documents', href: '/documents', icon: DocumentTextIcon, projectRequired: true },
  { name: 'BOQ', href: '/boq', icon: TableCellsIcon, projectRequired: true },
  { name: 'Packages', href: '/packages', icon: CubeIcon, projectRequired: true },
  { name: 'Pricing', href: '/pricing', icon: CurrencyDollarIcon, projectRequired: true },
];

const globalNavigation: NavItem[] = [
  { name: 'Suppliers', href: '/suppliers', icon: UserGroupIcon },
  { name: 'Offers', href: '/offers', icon: DocumentDuplicateIcon },
];

export default function Sidebar() {
  const { id: projectId } = useParams<{ id: string }>();
  const currentProject = useProjectStore((state) => state.currentProject);

  const getNavLinkClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'sidebar-link-active' : 'sidebar-link-inactive';

  return (
    <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 flex flex-col">
      {/* Logo */}
      <div className="h-16 flex items-center px-6 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-lg">B</span>
          </div>
          <span className="text-xl font-semibold text-gray-900">BidOps AI</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
        {/* Main Navigation */}
        <div className="space-y-1">
          {navigation.map((item) => (
            <NavLink key={item.name} to={item.href} end className={getNavLinkClass}>
              <item.icon className="w-5 h-5" />
              {item.name}
            </NavLink>
          ))}
        </div>

        {/* Current Project Section */}
        {(projectId || currentProject) && (
          <div className="pt-4">
            <div className="px-3 py-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Current Project
              </p>
              {currentProject && (
                <p className="mt-1 text-sm font-medium text-gray-900 truncate">
                  {currentProject.name}
                </p>
              )}
            </div>
            <div className="mt-2 space-y-1">
              {projectNavigation.map((item) => {
                const href = `/projects/${projectId || currentProject?.id}${item.href}`;
                return (
                  <NavLink key={item.name} to={href} className={getNavLinkClass}>
                    <item.icon className="w-5 h-5" />
                    {item.name}
                  </NavLink>
                );
              })}
            </div>
          </div>
        )}

        {/* Global Section */}
        <div className="pt-4">
          <div className="px-3 py-2">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Global
            </p>
          </div>
          <div className="mt-2 space-y-1">
            {globalNavigation.map((item) => (
              <NavLink key={item.name} to={item.href} className={getNavLinkClass}>
                <item.icon className="w-5 h-5" />
                {item.name}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>

      {/* Settings */}
      <div className="p-3 border-t border-gray-200">
        <NavLink to="/settings" className={getNavLinkClass}>
          <Cog6ToothIcon className="w-5 h-5" />
          Settings
        </NavLink>
      </div>
    </aside>
  );
}
