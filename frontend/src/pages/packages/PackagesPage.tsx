import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { PlusIcon, CubeIcon, SparklesIcon } from '@heroicons/react/24/outline';
import { Card, CardBody, Button, DataTable, Modal, ModalFooter, Input, Select, StatusBadge } from '@/components/ui';
import { usePackages, usePackageStatistics, useCreatePackage, useAutoCreatePackages } from '@/hooks/usePackages';
import { TRADE_CATEGORIES } from '@/types';
import type { Package } from '@/types';
import type { Column } from '@/components/ui/DataTable';

export default function PackagesPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = parseInt(id || '0');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newPackage, setNewPackage] = useState({
    name: '',
    code: '',
    trade_category: '',
    description: '',
  });

  const { data, isLoading } = usePackages(projectId);
  const { data: stats } = usePackageStatistics(projectId);
  const createPackage = useCreatePackage(projectId);
  const autoCreatePackages = useAutoCreatePackages(projectId);

  const tradeOptions = TRADE_CATEGORIES.map((cat) => ({
    value: cat,
    label: cat.replace(/_/g, ' '),
  }));

  const columns: Column<Package>[] = [
    {
      key: 'name',
      header: 'Package',
      render: (pkg) => (
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary-50 rounded-lg">
            <CubeIcon className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <p className="font-medium text-gray-900">{pkg.name}</p>
            <p className="text-sm text-gray-500">{pkg.code}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'trade_category',
      header: 'Trade',
      render: (pkg) => (
        <span className="text-gray-600">
          {pkg.trade_category.replace(/_/g, ' ')}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (pkg) => <StatusBadge status={pkg.status} />,
    },
    {
      key: 'total_items',
      header: 'BOQ Items',
      render: (pkg) => (
        <span className="font-mono">{pkg.total_items}</span>
      ),
    },
    {
      key: 'offers',
      header: 'Offers',
      render: (pkg) => (
        <span>
          {pkg.offers_received} received / {pkg.offers_evaluated} evaluated
        </span>
      ),
    },
    {
      key: 'estimated_value',
      header: 'Est. Value',
      render: (pkg) => (
        <span className="font-mono">
          {pkg.estimated_value
            ? `${pkg.currency || '$'}${pkg.estimated_value.toLocaleString()}`
            : '-'}
        </span>
      ),
    },
  ];

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await createPackage.mutateAsync(newPackage);
    setIsModalOpen(false);
    setNewPackage({ name: '', code: '', trade_category: '', description: '' });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Packages</h1>
          <p className="mt-1 text-gray-500">
            Manage subcontractor packages and RFQs
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={() => autoCreatePackages.mutate()}
            isLoading={autoCreatePackages.isPending}
          >
            <SparklesIcon className="w-5 h-5 mr-2" />
            Auto-Create
          </Button>
          <Button onClick={() => setIsModalOpen(true)}>
            <PlusIcon className="w-5 h-5 mr-2" />
            New Package
          </Button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardBody>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.total_packages}
              </p>
              <p className="text-sm text-gray-500">Total Packages</p>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.assigned_items}
              </p>
              <p className="text-sm text-gray-500">Assigned Items</p>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.unassigned_items}
              </p>
              <p className="text-sm text-gray-500">Unassigned Items</p>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <p className="text-2xl font-semibold text-primary-600">
                {Math.round(stats.assignment_rate * 100)}%
              </p>
              <p className="text-sm text-gray-500">Assignment Rate</p>
            </CardBody>
          </Card>
        </div>
      )}

      {/* Packages Table */}
      <Card>
        <CardBody className="p-0">
          <DataTable
            columns={columns}
            data={data?.items || []}
            keyExtractor={(pkg) => pkg.id}
            onRowClick={(pkg) => navigate(`/projects/${projectId}/packages/${pkg.id}`)}
            isLoading={isLoading}
            emptyMessage="No packages created yet. Create a package or use auto-create."
          />
        </CardBody>
      </Card>

      {/* Create Package Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create New Package"
        description="Enter the details for the subcontractor package"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Package Name"
            value={newPackage.name}
            onChange={(e) => setNewPackage({ ...newPackage, name: e.target.value })}
            placeholder="e.g., Structural Steel Works"
            required
          />
          <Input
            label="Package Code"
            value={newPackage.code}
            onChange={(e) => setNewPackage({ ...newPackage, code: e.target.value })}
            placeholder="e.g., STL-001"
            required
          />
          <Select
            label="Trade Category"
            options={tradeOptions}
            value={newPackage.trade_category}
            onChange={(e) => setNewPackage({ ...newPackage, trade_category: e.target.value })}
            placeholder="Select a trade..."
            required
          />
          <Input
            label="Description"
            value={newPackage.description}
            onChange={(e) => setNewPackage({ ...newPackage, description: e.target.value })}
            placeholder="Brief description of the package scope"
          />
          <ModalFooter className="-mx-6 -mb-4 mt-6">
            <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createPackage.isPending}>
              Create Package
            </Button>
          </ModalFooter>
        </form>
      </Modal>
    </div>
  );
}
