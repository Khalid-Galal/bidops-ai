import { useParams } from 'react-router-dom';
import {
  CurrencyDollarIcon,
  ChartBarIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline';
import { Card, CardBody, CardHeader, Button, LoadingPage } from '@/components/ui';
import { useProjectTotals, useCostBreakdown } from '@/hooks/useDashboard';

export default function PricingPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || '0');

  const { data: totals, isLoading: loadingTotals } = useProjectTotals(projectId);
  const { data: breakdown, isLoading: loadingBreakdown } = useCostBreakdown(projectId);

  if (loadingTotals || loadingBreakdown) return <LoadingPage />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pricing Summary</h1>
          <p className="mt-1 text-gray-500">
            {totals?.project_name} - Cost breakdown and pricing status
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline">
            <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
            Export BOQ
          </Button>
          <Button>
            <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
            Generate Report
          </Button>
        </div>
      </div>

      {/* Stats */}
      {totals && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardBody className="flex items-center gap-4">
              <div className="p-3 bg-green-50 rounded-lg">
                <CurrencyDollarIcon className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-semibold text-gray-900">
                  ${totals.total_value.toLocaleString()}
                </p>
                <p className="text-sm text-gray-500">Total Value</p>
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <p className="text-2xl font-semibold text-gray-900">
                {totals.priced_items} / {totals.total_items}
              </p>
              <p className="text-sm text-gray-500">Items Priced</p>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <p className="text-2xl font-semibold text-gray-900">
                {totals.unpriced_items}
              </p>
              <p className="text-sm text-gray-500">Unpriced Items</p>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <p className={`text-2xl font-semibold ${totals.completion_rate >= 0.9 ? 'text-green-600' : 'text-yellow-600'}`}>
                {Math.round(totals.completion_rate * 100)}%
              </p>
              <p className="text-sm text-gray-500">Completion Rate</p>
            </CardBody>
          </Card>
        </div>
      )}

      {/* By Trade */}
      {totals && Object.keys(totals.by_trade).length > 0 && (
        <Card>
          <CardHeader title="Pricing by Trade" />
          <CardBody>
            <div className="space-y-4">
              {Object.entries(totals.by_trade).map(([trade, data]) => (
                <div key={trade} className="flex items-center gap-4">
                  <div className="w-40 text-sm font-medium text-gray-900">
                    {trade.replace(/_/g, ' ')}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="flex-1 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-primary-600 h-2 rounded-full"
                          style={{ width: `${(data.priced / data.count) * 100}%` }}
                        />
                      </div>
                      <span className="text-sm text-gray-500 w-16">
                        {data.priced}/{data.count}
                      </span>
                    </div>
                  </div>
                  <div className="w-32 text-right font-mono font-medium">
                    ${data.total.toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Cost Breakdown */}
      {breakdown && breakdown.trades.length > 0 && (
        <Card>
          <CardHeader
            title="Cost Breakdown by Trade"
            action={
              <div className="text-lg font-semibold text-gray-900">
                Grand Total: ${breakdown.grand_total.toLocaleString()}
              </div>
            }
          />
          <CardBody>
            <div className="space-y-6">
              {breakdown.trades.map((trade) => (
                <div key={trade.trade} className="border-b border-gray-200 pb-6 last:border-0 last:pb-0">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-primary-50 rounded-lg">
                        <ChartBarIcon className="w-5 h-5 text-primary-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">
                          {trade.trade.replace(/_/g, ' ')}
                        </p>
                        <p className="text-sm text-gray-500">{trade.count} items</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-mono font-semibold text-gray-900">
                        ${trade.total.toLocaleString()}
                      </p>
                      <p className="text-sm text-gray-500">{trade.percentage.toFixed(1)}%</p>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
                    <div
                      className="bg-primary-600 h-2 rounded-full"
                      style={{ width: `${trade.percentage}%` }}
                    />
                  </div>

                  {/* Top Items */}
                  {trade.top_items.length > 0 && (
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm font-medium text-gray-700 mb-2">Top Items</p>
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-gray-500">
                            <th className="text-left py-1">Description</th>
                            <th className="text-right py-1">Qty</th>
                            <th className="text-right py-1">Unit Rate</th>
                            <th className="text-right py-1">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {trade.top_items.map((item, i) => (
                            <tr key={i}>
                              <td className="py-1 pr-4 truncate max-w-xs" title={item.description}>
                                {item.description}
                              </td>
                              <td className="py-1 text-right font-mono">
                                {item.quantity} {item.unit}
                              </td>
                              <td className="py-1 text-right font-mono">
                                ${item.unit_rate.toLocaleString()}
                              </td>
                              <td className="py-1 text-right font-mono font-medium">
                                ${item.total.toLocaleString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Empty State */}
      {(!breakdown || breakdown.trades.length === 0) && (
        <Card>
          <CardBody className="text-center py-12">
            <CurrencyDollarIcon className="w-12 h-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">
              No pricing data available. Price BOQ items to see cost breakdown.
            </p>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
