import { HTMLAttributes } from 'react';
import { clsx } from 'clsx';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'gray';
  size?: 'sm' | 'md';
}

const variantStyles = {
  primary: 'bg-primary-100 text-primary-800',
  success: 'bg-green-100 text-green-800',
  warning: 'bg-yellow-100 text-yellow-800',
  danger: 'bg-red-100 text-red-800',
  gray: 'bg-gray-100 text-gray-800',
};

const sizeStyles = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-0.5 text-sm',
};

export default function Badge({
  className,
  variant = 'gray',
  size = 'sm',
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full font-medium',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

// Status badge helper
export function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { variant: BadgeProps['variant']; label: string }> = {
    // Project statuses
    new: { variant: 'gray', label: 'New' },
    ingesting: { variant: 'primary', label: 'Ingesting' },
    ready: { variant: 'success', label: 'Ready' },
    in_progress: { variant: 'primary', label: 'In Progress' },
    submitted: { variant: 'success', label: 'Submitted' },
    won: { variant: 'success', label: 'Won' },
    lost: { variant: 'danger', label: 'Lost' },
    cancelled: { variant: 'gray', label: 'Cancelled' },
    // Document statuses
    pending: { variant: 'gray', label: 'Pending' },
    processing: { variant: 'primary', label: 'Processing' },
    indexed: { variant: 'success', label: 'Indexed' },
    failed: { variant: 'danger', label: 'Failed' },
    // Package statuses
    draft: { variant: 'gray', label: 'Draft' },
    sent: { variant: 'primary', label: 'Sent' },
    received: { variant: 'success', label: 'Received' },
    evaluated: { variant: 'success', label: 'Evaluated' },
    awarded: { variant: 'success', label: 'Awarded' },
    closed: { variant: 'gray', label: 'Closed' },
    // Offer statuses
    under_review: { variant: 'primary', label: 'Under Review' },
    compliant: { variant: 'success', label: 'Compliant' },
    non_compliant: { variant: 'danger', label: 'Non-Compliant' },
    selected: { variant: 'success', label: 'Selected' },
    rejected: { variant: 'danger', label: 'Rejected' },
  };

  const config = statusConfig[status] || { variant: 'gray' as const, label: status };

  return <Badge variant={config.variant}>{config.label}</Badge>;
}
