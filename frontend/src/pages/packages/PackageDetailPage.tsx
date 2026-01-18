import { useParams, useNavigate } from 'react-router-dom';
import {
  CubeIcon,
  EnvelopeIcon,
  DocumentDuplicateIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline';
import { Card, CardBody, CardHeader, Button, StatusBadge, LoadingPage, DataTable } from '@/components/ui';
import { usePackage } from '@/hooks/usePackages';
import { useOffers, useOfferComparison } from '@/hooks/useOffers';
import type { Offer } from '@/types';
import type { Column } from '@/components/ui/DataTable';

export default function PackageDetailPage() {
  const { id, packageId } = useParams<{ id: string; packageId: string }>();
  const navigate = useNavigate();
  const projectId = parseInt(id || '0');
  const pkgId = parseInt(packageId || '0');

  const { data: pkg, isLoading } = usePackage(projectId, pkgId);
  const { data: offersData } = useOffers(pkgId);
  const { data: comparison } = useOfferComparison(pkgId);

  if (isLoading) return <LoadingPage />;
  if (!pkg) return <div>Package not found</div>;

  const offerColumns: Column<Offer>[] = [
    {
      key: 'supplier_name',
      header: 'Supplier',
      render: (offer) => (
        <span className="font-medium text-gray-900">
          {offer.supplier_name || `Supplier #${offer.supplier_id}`}
        </span>
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
        <span className="font-mono">
          {offer.total_price
            ? `${offer.currency || '$'}${offer.total_price.toLocaleString()}`
            : '-'}
        </span>
      ),
    },
    {
      key: 'overall_score',
      header: 'Score',
      render: (offer) => (
        <span className={offer.overall_score && offer.overall_score >= 70 ? 'text-green-600' : 'text-gray-600'}>
          {offer.overall_score ? `${offer.overall_score}%` : '-'}
        </span>
      ),
    },
    {
      key: 'rank',
      header: 'Rank',
      render: (offer) => (
        <span className={offer.rank === 1 ? 'font-bold text-primary-600' : 'text-gray-600'}>
          {offer.rank ? `#${offer.rank}` : '-'}
        </span>
      ),
    },
    {
      key: 'received_at',
      header: 'Received',
      render: (offer) => new Date(offer.received_at).toLocaleDateString(),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary-50 rounded-lg">
              <CubeIcon className="w-6 h-6 text-primary-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{pkg.name}</h1>
              <p className="text-gray-500">
                {pkg.code} - {pkg.trade_category.replace(/_/g, ' ')}
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={pkg.status} />
          <Button variant="outline">
            <EnvelopeIcon className="w-5 h-5 mr-2" />
            Send RFQ
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardBody className="flex items-center gap-4">
            <div className="p-3 bg-blue-50 rounded-lg">
              <DocumentDuplicateIcon className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900">{pkg.total_items}</p>
              <p className="text-sm text-gray-500">BOQ Items</p>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="flex items-center gap-4">
            <div className="p-3 bg-green-50 rounded-lg">
              <UserGroupIcon className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900">{pkg.offers_received}</p>
              <p className="text-sm text-gray-500">Offers Received</p>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-2xl font-semibold text-gray-900">{pkg.offers_evaluated}</p>
            <p className="text-sm text-gray-500">Evaluated</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-2xl font-semibold text-primary-600">
              {pkg.estimated_value
                ? `${pkg.currency || '$'}${pkg.estimated_value.toLocaleString()}`
                : '-'}
            </p>
            <p className="text-sm text-gray-500">Estimated Value</p>
          </CardBody>
        </Card>
      </div>

      {/* Price Comparison */}
      {comparison && comparison.price_statistics && (
        <Card>
          <CardHeader title="Price Comparison" />
          <CardBody>
            <div className="grid grid-cols-3 gap-8 text-center">
              <div>
                <p className="text-sm text-gray-500 mb-1">Lowest</p>
                <p className="text-2xl font-semibold text-green-600">
                  {comparison.price_statistics.currency}
                  {comparison.price_statistics.min.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 mb-1">Average</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {comparison.price_statistics.currency}
                  {comparison.price_statistics.average.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 mb-1">Highest</p>
                <p className="text-2xl font-semibold text-red-600">
                  {comparison.price_statistics.currency}
                  {comparison.price_statistics.max.toLocaleString()}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Offers Table */}
      <Card>
        <CardHeader
          title="Offers"
          action={
            <Button variant="outline" size="sm">
              Upload Offer
            </Button>
          }
        />
        <CardBody className="p-0">
          <DataTable
            columns={offerColumns}
            data={offersData?.items || []}
            keyExtractor={(offer) => offer.id}
            onRowClick={(offer) => navigate(`/offers/${offer.id}`)}
            emptyMessage="No offers received yet."
          />
        </CardBody>
      </Card>

      {/* Package Details */}
      <Card>
        <CardHeader title="Package Details" />
        <CardBody>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm font-medium text-gray-500">Description</dt>
              <dd className="mt-1 text-gray-900">{pkg.description || 'No description'}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Submission Deadline</dt>
              <dd className="mt-1 text-gray-900">
                {pkg.submission_deadline
                  ? new Date(pkg.submission_deadline).toLocaleString()
                  : 'Not set'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Created</dt>
              <dd className="mt-1 text-gray-900">
                {new Date(pkg.created_at).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Folder Path</dt>
              <dd className="mt-1 text-gray-900 font-mono text-sm">
                {pkg.folder_path || 'Not set'}
              </dd>
            </div>
          </dl>
        </CardBody>
      </Card>
    </div>
  );
}
