import { useParams, useNavigate } from 'react-router-dom';
import {
  DocumentDuplicateIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { Card, CardBody, CardHeader, Button, Badge, StatusBadge, LoadingPage, DataTable } from '@/components/ui';
import { useOffer, useEvaluateOffer, useSelectOffer, useRejectOffer } from '@/hooks/useOffers';
import type { OfferLineItem } from '@/types';
import type { Column } from '@/components/ui/DataTable';

export default function OfferDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const offerId = parseInt(id || '0');

  const { data: offer, isLoading } = useOffer(offerId);
  const evaluateOffer = useEvaluateOffer();
  const selectOffer = useSelectOffer();
  const rejectOffer = useRejectOffer();

  if (isLoading) return <LoadingPage />;
  if (!offer) return <div>Offer not found</div>;

  const lineItemColumns: Column<OfferLineItem>[] = [
    { key: 'description', header: 'Description' },
    { key: 'unit', header: 'Unit' },
    {
      key: 'quantity',
      header: 'Qty',
      render: (item) => <span className="font-mono">{item.quantity}</span>,
    },
    {
      key: 'unit_rate',
      header: 'Unit Rate',
      render: (item) => <span className="font-mono">${item.unit_rate.toLocaleString()}</span>,
    },
    {
      key: 'total',
      header: 'Total',
      render: (item) => (
        <span className="font-mono font-medium">${item.total.toLocaleString()}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-blue-50 rounded-lg">
            <DocumentDuplicateIcon className="w-8 h-8 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {offer.supplier_name || `Supplier #${offer.supplier_id}`}
            </h1>
            <p className="text-gray-500">
              Package #{offer.package_id} - Received {new Date(offer.received_at).toLocaleDateString()}
            </p>
          </div>
          <StatusBadge status={offer.status} />
        </div>
        <div className="flex gap-3">
          {offer.status === 'received' && (
            <Button
              variant="outline"
              onClick={() => evaluateOffer.mutate(offerId)}
              isLoading={evaluateOffer.isPending}
            >
              <ArrowPathIcon className="w-5 h-5 mr-2" />
              Evaluate
            </Button>
          )}
          {offer.status === 'evaluated' && (
            <>
              <Button
                variant="danger"
                onClick={() => rejectOffer.mutate(offerId)}
                isLoading={rejectOffer.isPending}
              >
                <XCircleIcon className="w-5 h-5 mr-2" />
                Reject
              </Button>
              <Button onClick={() => selectOffer.mutate(offerId)} isLoading={selectOffer.isPending}>
                <CheckCircleIcon className="w-5 h-5 mr-2" />
                Select
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardBody className="text-center">
            <p className="text-2xl font-semibold text-gray-900">
              {offer.total_price
                ? `${offer.currency || '$'}${offer.total_price.toLocaleString()}`
                : '-'}
            </p>
            <p className="text-sm text-gray-500">Total Price</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className="text-2xl font-semibold text-blue-600">
              {offer.commercial_score || '-'}%
            </p>
            <p className="text-sm text-gray-500">Commercial Score</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className="text-2xl font-semibold text-purple-600">
              {offer.technical_score || '-'}%
            </p>
            <p className="text-sm text-gray-500">Technical Score</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className="text-2xl font-semibold text-primary-600">
              {offer.overall_score || '-'}%
            </p>
            <p className="text-sm text-gray-500">Overall Score</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className={`text-2xl font-semibold ${offer.rank === 1 ? 'text-green-600' : 'text-gray-900'}`}>
              {offer.rank ? `#${offer.rank}` : '-'}
            </p>
            <p className="text-sm text-gray-500">Rank</p>
          </CardBody>
        </Card>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Offer Details */}
        <Card>
          <CardHeader title="Offer Details" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Validity</p>
                <p className="font-medium">{offer.validity_days || '-'} days</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Delivery</p>
                <p className="font-medium">{offer.delivery_weeks || '-'} weeks</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Payment Terms</p>
                <p className="font-medium">{offer.payment_terms || '-'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Evaluated</p>
                <p className="font-medium">
                  {offer.evaluated_at ? new Date(offer.evaluated_at).toLocaleString() : 'Not yet'}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Exclusions & Deviations */}
        <Card>
          <CardHeader title="Exclusions & Deviations" />
          <CardBody>
            {offer.exclusions && offer.exclusions.length > 0 ? (
              <div className="mb-4">
                <p className="text-sm font-medium text-gray-700 mb-2">Exclusions</p>
                <ul className="space-y-1">
                  {offer.exclusions.map((exc, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <span className="text-red-500">-</span>
                      <span>{exc}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {offer.deviations && offer.deviations.length > 0 ? (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Deviations</p>
                <ul className="space-y-2">
                  {offer.deviations.map((dev, i) => (
                    <li key={i} className="text-sm">
                      <span className="font-medium">{dev.item}:</span> {dev.deviation}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {(!offer.exclusions || offer.exclusions.length === 0) &&
              (!offer.deviations || offer.deviations.length === 0) && (
                <p className="text-gray-500 text-center py-4">
                  No exclusions or deviations noted
                </p>
              )}
          </CardBody>
        </Card>
      </div>

      {/* Line Items */}
      {offer.line_items && offer.line_items.length > 0 && (
        <Card>
          <CardHeader title="Line Items" />
          <CardBody className="p-0">
            <DataTable
              columns={lineItemColumns}
              data={offer.line_items}
              keyExtractor={(_, i) => i}
              emptyMessage="No line items"
            />
          </CardBody>
        </Card>
      )}
    </div>
  );
}
