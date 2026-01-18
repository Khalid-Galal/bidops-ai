import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PlusIcon,
  UserGroupIcon,
  ArrowUpTrayIcon,
  ArrowDownTrayIcon,
  StarIcon,
} from '@heroicons/react/24/outline';
import { Card, CardBody, Button, DataTable, Modal, ModalFooter, Input, Select, Badge } from '@/components/ui';
import { useSuppliers, useCreateSupplier, useImportSuppliers } from '@/hooks/useSuppliers';
import { TRADE_CATEGORIES } from '@/types';
import type { Supplier } from '@/types';
import type { Column } from '@/components/ui/DataTable';

export default function SuppliersPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [tradeFilter, setTradeFilter] = useState('');
  const [newSupplier, setNewSupplier] = useState({
    name: '',
    code: '',
    emails: [''],
    trade_categories: [] as string[],
    contact_name: '',
    phone: '',
    region: '',
    country: '',
  });

  const { data, isLoading } = useSuppliers(1, 50, {
    trade_category: tradeFilter || undefined,
    search: search || undefined,
  });
  const createSupplier = useCreateSupplier();
  const importSuppliers = useImportSuppliers();

  const tradeOptions = TRADE_CATEGORIES.map((cat) => ({
    value: cat,
    label: cat.replace(/_/g, ' '),
  }));

  const columns: Column<Supplier>[] = [
    {
      key: 'name',
      header: 'Supplier',
      render: (supplier) => (
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-50 rounded-lg">
            <UserGroupIcon className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <p className="font-medium text-gray-900">{supplier.name}</p>
            <p className="text-sm text-gray-500">{supplier.code || supplier.emails[0]}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'trade_categories',
      header: 'Trades',
      render: (supplier) => (
        <div className="flex flex-wrap gap-1">
          {supplier.trade_categories.slice(0, 2).map((trade) => (
            <Badge key={trade} variant="gray" size="sm">
              {trade.replace(/_/g, ' ')}
            </Badge>
          ))}
          {supplier.trade_categories.length > 2 && (
            <Badge variant="gray" size="sm">
              +{supplier.trade_categories.length - 2}
            </Badge>
          )}
        </div>
      ),
    },
    {
      key: 'rating',
      header: 'Rating',
      render: (supplier) => (
        <div className="flex items-center gap-1">
          <StarIcon className={`w-4 h-4 ${supplier.rating ? 'text-yellow-400 fill-current' : 'text-gray-300'}`} />
          <span>{supplier.rating?.toFixed(1) || '-'}</span>
        </div>
      ),
    },
    {
      key: 'stats',
      header: 'Performance',
      render: (supplier) => (
        <div className="text-sm">
          <span className="text-gray-500">RFQs: </span>
          <span className="font-medium">{supplier.total_rfqs_sent}</span>
          <span className="mx-2 text-gray-300">|</span>
          <span className="text-gray-500">Offers: </span>
          <span className="font-medium">{supplier.total_offers_received}</span>
          <span className="mx-2 text-gray-300">|</span>
          <span className="text-gray-500">Awards: </span>
          <span className="font-medium text-green-600">{supplier.total_awards}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (supplier) => (
        <Badge variant={supplier.is_blacklisted ? 'danger' : supplier.is_active ? 'success' : 'gray'}>
          {supplier.is_blacklisted ? 'Blacklisted' : supplier.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
  ];

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await createSupplier.mutateAsync({
      ...newSupplier,
      emails: newSupplier.emails.filter((e) => e.trim()),
    });
    setIsModalOpen(false);
    setNewSupplier({
      name: '',
      code: '',
      emails: [''],
      trade_categories: [],
      contact_name: '',
      phone: '',
      region: '',
      country: '',
    });
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await importSuppliers.mutateAsync({ file });
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Suppliers</h1>
          <p className="mt-1 text-gray-500">
            Manage your subcontractor and supplier database
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
            <ArrowUpTrayIcon className="w-5 h-5 mr-2" />
            Import
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={handleImport}
            className="hidden"
          />
          <Button variant="outline">
            <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
            Export
          </Button>
          <Button onClick={() => setIsModalOpen(true)}>
            <PlusIcon className="w-5 h-5 mr-2" />
            Add Supplier
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardBody className="flex gap-4">
          <Input
            placeholder="Search suppliers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
          />
          <Select
            options={[{ value: '', label: 'All Trades' }, ...tradeOptions]}
            value={tradeFilter}
            onChange={(e) => setTradeFilter(e.target.value)}
            className="w-48"
          />
        </CardBody>
      </Card>

      {/* Suppliers Table */}
      <Card>
        <CardBody className="p-0">
          <DataTable
            columns={columns}
            data={data?.items || []}
            keyExtractor={(supplier) => supplier.id}
            onRowClick={(supplier) => navigate(`/suppliers/${supplier.id}`)}
            isLoading={isLoading}
            emptyMessage="No suppliers found. Add or import suppliers to get started."
          />
        </CardBody>
      </Card>

      {/* Pagination */}
      {data && data.total > 0 && (
        <div className="text-sm text-gray-500">
          Showing {data.items.length} of {data.total} suppliers
        </div>
      )}

      {/* Create Supplier Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Add New Supplier"
        size="lg"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Company Name"
              value={newSupplier.name}
              onChange={(e) => setNewSupplier({ ...newSupplier, name: e.target.value })}
              required
            />
            <Input
              label="Supplier Code"
              value={newSupplier.code}
              onChange={(e) => setNewSupplier({ ...newSupplier, code: e.target.value })}
            />
          </div>
          <Input
            label="Email Address"
            type="email"
            value={newSupplier.emails[0]}
            onChange={(e) => setNewSupplier({ ...newSupplier, emails: [e.target.value] })}
            required
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Contact Name"
              value={newSupplier.contact_name}
              onChange={(e) => setNewSupplier({ ...newSupplier, contact_name: e.target.value })}
            />
            <Input
              label="Phone"
              value={newSupplier.phone}
              onChange={(e) => setNewSupplier({ ...newSupplier, phone: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Region"
              value={newSupplier.region}
              onChange={(e) => setNewSupplier({ ...newSupplier, region: e.target.value })}
            />
            <Input
              label="Country"
              value={newSupplier.country}
              onChange={(e) => setNewSupplier({ ...newSupplier, country: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Trade Categories
            </label>
            <div className="flex flex-wrap gap-2">
              {TRADE_CATEGORIES.map((trade) => (
                <button
                  key={trade}
                  type="button"
                  onClick={() => {
                    const trades = newSupplier.trade_categories.includes(trade)
                      ? newSupplier.trade_categories.filter((t) => t !== trade)
                      : [...newSupplier.trade_categories, trade];
                    setNewSupplier({ ...newSupplier, trade_categories: trades });
                  }}
                  className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                    newSupplier.trade_categories.includes(trade)
                      ? 'bg-primary-100 border-primary-500 text-primary-700'
                      : 'border-gray-300 text-gray-600 hover:border-gray-400'
                  }`}
                >
                  {trade.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>
          <ModalFooter className="-mx-6 -mb-4 mt-6">
            <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createSupplier.isPending}>
              Add Supplier
            </Button>
          </ModalFooter>
        </form>
      </Modal>
    </div>
  );
}
