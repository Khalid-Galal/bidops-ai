import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { TableCellsIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { Card, CardBody, Button, DataTable, Select, Input } from '@/components/ui';
import { useBOQItems, useBOQStatistics, useUpdateBOQItem } from '@/hooks/usePackages';
import { TRADE_CATEGORIES } from '@/types';
import type { BOQItem } from '@/types';
import type { Column } from '@/components/ui/DataTable';

export default function BOQPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || '0');

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');

  const { data, isLoading } = useBOQItems(projectId, page, 50);
  const { data: stats } = useBOQStatistics(projectId);
  const updateBOQItem = useUpdateBOQItem(projectId);

  const tradeOptions = TRADE_CATEGORIES.map((cat) => ({
    value: cat,
    label: cat.replace(/_/g, ' '),
  }));

  const columns: Column<BOQItem>[] = [
    {
      key: 'line_number',
      header: 'Line #',
      render: (item) => (
        <span className="font-mono text-sm text-gray-600">{item.line_number}</span>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (item) => (
        <div className="max-w-md">
          <p className="text-gray-900 truncate" title={item.description}>
            {item.description}
          </p>
          {item.section && (
            <p className="text-xs text-gray-500 mt-1">{item.section}</p>
          )}
        </div>
      ),
    },
    {
      key: 'quantity',
      header: 'Qty',
      render: (item) => (
        <span className="font-mono">
          {item.quantity.toLocaleString()} {item.unit}
        </span>
      ),
    },
    {
      key: 'trade_category',
      header: 'Trade',
      render: (item) => (
        <Select
          options={tradeOptions}
          value={item.trade_category || ''}
          onChange={(e) => {
            updateBOQItem.mutate({
              itemId: item.id,
              data: { trade_category: e.target.value },
            });
          }}
          className="w-40"
        />
      ),
    },
    {
      key: 'unit_rate',
      header: 'Unit Rate',
      render: (item) => (
        <span className="font-mono">
          {item.unit_rate ? `$${item.unit_rate.toLocaleString()}` : '-'}
        </span>
      ),
    },
    {
      key: 'total_price',
      header: 'Total',
      render: (item) => (
        <span className="font-mono font-medium">
          {item.total_price ? `$${item.total_price.toLocaleString()}` : '-'}
        </span>
      ),
    },
    {
      key: 'package_id',
      header: 'Package',
      render: (item) => (
        <span className={item.package_id ? 'text-green-600' : 'text-gray-400'}>
          {item.package_id ? `PKG-${item.package_id}` : 'Unassigned'}
        </span>
      ),
    },
  ];

  const filteredItems = data?.items.filter((item) =>
    item.description.toLowerCase().includes(search.toLowerCase())
  ) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bill of Quantities</h1>
          <p className="mt-1 text-gray-500">
            {data?.total || 0} items - Manage BOQ items and assign to packages
          </p>
        </div>
        <Button variant="outline">
          <ArrowPathIcon className="w-5 h-5 mr-2" />
          Re-parse BOQ
        </Button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardBody className="flex items-center gap-4">
              <div className="p-3 bg-blue-50 rounded-lg">
                <TableCellsIcon className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-semibold text-gray-900">
                  {stats.total_items.toLocaleString()}
                </p>
                <p className="text-sm text-gray-500">Total Items</p>
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <p className="text-sm font-medium text-gray-500 mb-2">By Trade</p>
              <div className="space-y-1">
                {Object.entries(stats.by_trade).slice(0, 3).map(([trade, count]) => (
                  <div key={trade} className="flex justify-between text-sm">
                    <span className="text-gray-600">{trade.replace(/_/g, ' ')}</span>
                    <span className="font-medium">{count}</span>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <p className="text-sm font-medium text-gray-500 mb-2">By Section</p>
              <div className="space-y-1">
                {Object.entries(stats.by_section).slice(0, 3).map(([section, count]) => (
                  <div key={section} className="flex justify-between text-sm">
                    <span className="text-gray-600 truncate">{section}</span>
                    <span className="font-medium">{count}</span>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardBody className="flex gap-4">
          <Input
            placeholder="Search descriptions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
          />
          <Select
            options={[{ value: '', label: 'All Trades' }, ...tradeOptions]}
            className="w-48"
          />
          <Select
            options={[
              { value: '', label: 'All Assignments' },
              { value: 'assigned', label: 'Assigned' },
              { value: 'unassigned', label: 'Unassigned' },
            ]}
            className="w-48"
          />
        </CardBody>
      </Card>

      {/* BOQ Table */}
      <Card>
        <CardBody className="p-0">
          <DataTable
            columns={columns}
            data={filteredItems}
            keyExtractor={(item) => item.id}
            isLoading={isLoading}
            emptyMessage="No BOQ items found. Parse a BOQ document to import items."
          />
        </CardBody>
      </Card>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="text-sm text-gray-500">
            Page {page} of {data.pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
            disabled={page === data.pages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
