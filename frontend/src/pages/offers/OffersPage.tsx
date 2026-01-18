import { useNavigate } from 'react-router-dom';
import { DocumentDuplicateIcon } from '@heroicons/react/24/outline';
import { Card, CardBody, DataTable, StatusBadge, Input, Select } from '@/components/ui';
import { useOffers } from '@/hooks/useOffers';
import type { Offer } from '@/types';
import type { Column } from '@/components/ui/DataTable';

export default function OffersPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useOffers();

  const columns: Column<Offer>[] = [
    {
      key: 'supplier',
      header: 'Supplier',
      render: (offer) => (
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-50 rounded-lg">
            <DocumentDuplicateIcon className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="font-medium text-gray-900">
              {offer.supplier_name || `Supplier #${offer.supplier_id}`}
            </p>
            <p className="text-sm text-gray-500">Package #{offer.package_id}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (offer) => <StatusBadge status={offer.status} />,
    },
    {
      key: 'total_price',
      header: 'Total Price',
      render: (offer) => (
        <span className="font-mono font-medium">
          {offer.total_price
            ? `${offer.currency || '$'}${offer.total_price.toLocaleString()}`
            : '-'}
        </span>
      ),
    },
    {
      key: 'scores',
      header: 'Scores',
      render: (offer) => (
        <div className="flex gap-4 text-sm">
          <span title="Commercial">
            C: <span className="font-medium">{offer.commercial_score || '-'}%</span>
          </span>
          <span title="Technical">
            T: <span className="font-medium">{offer.technical_score || '-'}%</span>
          </span>
          <span title="Overall" className="font-medium text-primary-600">
            O: {offer.overall_score || '-'}%
          </span>
        </div>
      ),
    },
    {
      key: 'rank',
      header: 'Rank',
      render: (offer) => (
        <span className={offer.rank === 1 ? 'font-bold text-green-600' : 'text-gray-600'}>
          {offer.rank ? `#${offer.rank}` : '-'}
        </span>
      ),
    },
    {
      key: 'received_at',
      header: 'Received',
      render: (offer) => (
        <span className="text-gray-500">
          {new Date(offer.received_at).toLocaleDateString()}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Offers</h1>
        <p className="mt-1 text-gray-500">View and evaluate supplier offers</p>
      </div>

      {/* Filters */}
      <Card>
        <CardBody className="flex gap-4">
          <Input placeholder="Search offers..." className="max-w-sm" />
          <Select
            options={[
              { value: '', label: 'All Statuses' },
              { value: 'received', label: 'Received' },
              { value: 'under_review', label: 'Under Review' },
              { value: 'evaluated', label: 'Evaluated' },
              { value: 'selected', label: 'Selected' },
              { value: 'rejected', label: 'Rejected' },
            ]}
            className="w-48"
          />
        </CardBody>
      </Card>

      {/* Offers Table */}
      <Card>
        <CardBody className="p-0">
          <DataTable
            columns={columns}
            data={data?.items || []}
            keyExtractor={(offer) => offer.id}
            onRowClick={(offer) => navigate(`/offers/${offer.id}`)}
            isLoading={isLoading}
            emptyMessage="No offers received yet."
          />
        </CardBody>
      </Card>

      {/* Pagination */}
      {data && data.total > 0 && (
        <div className="text-sm text-gray-500">
          Showing {data.items.length} of {data.total} offers
        </div>
      )}
    </div>
  );
}
