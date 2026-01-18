import { useParams } from 'react-router-dom';
import {
  UserGroupIcon,
  EnvelopeIcon,
  PhoneIcon,
  MapPinIcon,
  StarIcon,
} from '@heroicons/react/24/outline';
import { Card, CardBody, CardHeader, Button, Badge, LoadingPage } from '@/components/ui';
import { useSupplier } from '@/hooks/useSuppliers';

export default function SupplierDetailPage() {
  const { id } = useParams<{ id: string }>();
  const supplierId = parseInt(id || '0');

  const { data: supplier, isLoading } = useSupplier(supplierId);

  if (isLoading) return <LoadingPage />;
  if (!supplier) return <div>Supplier not found</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-green-50 rounded-lg">
            <UserGroupIcon className="w-8 h-8 text-green-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{supplier.name}</h1>
            <p className="text-gray-500">{supplier.code}</p>
          </div>
          <Badge variant={supplier.is_blacklisted ? 'danger' : supplier.is_active ? 'success' : 'gray'}>
            {supplier.is_blacklisted ? 'Blacklisted' : supplier.is_active ? 'Active' : 'Inactive'}
          </Badge>
        </div>
        <div className="flex gap-3">
          <Button variant="outline">Edit</Button>
          <Button>Send RFQ</Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardBody className="text-center">
            <div className="flex items-center justify-center gap-1 mb-2">
              <StarIcon className={`w-6 h-6 ${supplier.rating ? 'text-yellow-400 fill-current' : 'text-gray-300'}`} />
              <span className="text-2xl font-semibold">{supplier.rating?.toFixed(1) || '-'}</span>
            </div>
            <p className="text-sm text-gray-500">Rating</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className="text-2xl font-semibold text-gray-900">{supplier.total_rfqs_sent}</p>
            <p className="text-sm text-gray-500">RFQs Sent</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className="text-2xl font-semibold text-gray-900">{supplier.total_offers_received}</p>
            <p className="text-sm text-gray-500">Offers Received</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className="text-2xl font-semibold text-green-600">{supplier.total_awards}</p>
            <p className="text-sm text-gray-500">Awards Won</p>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Contact Information */}
        <Card>
          <CardHeader title="Contact Information" />
          <CardBody className="space-y-4">
            {supplier.contact_name && (
              <div className="flex items-center gap-3">
                <UserGroupIcon className="w-5 h-5 text-gray-400" />
                <span>{supplier.contact_name}</span>
              </div>
            )}
            <div className="flex items-center gap-3">
              <EnvelopeIcon className="w-5 h-5 text-gray-400" />
              <div className="space-y-1">
                {supplier.emails.map((email) => (
                  <a key={email} href={`mailto:${email}`} className="block text-primary-600 hover:underline">
                    {email}
                  </a>
                ))}
              </div>
            </div>
            {supplier.phone && (
              <div className="flex items-center gap-3">
                <PhoneIcon className="w-5 h-5 text-gray-400" />
                <a href={`tel:${supplier.phone}`} className="text-primary-600 hover:underline">
                  {supplier.phone}
                </a>
              </div>
            )}
            {(supplier.region || supplier.country) && (
              <div className="flex items-center gap-3">
                <MapPinIcon className="w-5 h-5 text-gray-400" />
                <span>
                  {[supplier.region, supplier.country].filter(Boolean).join(', ')}
                </span>
              </div>
            )}
          </CardBody>
        </Card>

        {/* Trade Categories */}
        <Card>
          <CardHeader title="Trade Categories" />
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {supplier.trade_categories.map((trade) => (
                <Badge key={trade} variant="primary" size="md">
                  {trade.replace(/_/g, ' ')}
                </Badge>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader title="Recent Activity" />
        <CardBody>
          <p className="text-gray-500 text-center py-8">
            Activity history will be displayed here
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
