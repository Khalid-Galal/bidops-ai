// User and Auth Types
export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  organization_id: number;
  is_active: boolean;
  created_at: string;
}

export type UserRole = 'admin' | 'tender_manager' | 'estimator' | 'viewer';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

// Project Types
export interface Project {
  id: number;
  name: string;
  code?: string;
  description?: string;
  status: ProjectStatus;
  folder_path?: string;
  summary?: ProjectSummary;
  checklist?: ChecklistCategory[];
  created_at: string;
  updated_at: string;
}

export type ProjectStatus =
  | 'new'
  | 'ingesting'
  | 'ready'
  | 'in_progress'
  | 'submitted'
  | 'won'
  | 'lost'
  | 'cancelled';

export interface ProjectSummary {
  [key: string]: {
    value: string;
    confidence: number;
    source?: string;
  };
}

export interface ChecklistCategory {
  category: string;
  requirements: ChecklistRequirement[];
}

export interface ChecklistRequirement {
  requirement: string;
  mandatory: boolean;
  status: 'pending' | 'met' | 'not_met';
  evidence?: string;
}

// Document Types
export interface Document {
  id: number;
  project_id: number;
  filename: string;
  file_path: string;
  file_type: string;
  file_size: number;
  category?: DocumentCategory;
  status: DocumentStatus;
  page_count?: number;
  created_at: string;
}

export type DocumentCategory =
  | 'ITT'
  | 'SPECS'
  | 'BOQ'
  | 'DRAWINGS'
  | 'CONTRACT'
  | 'ADDENDUM'
  | 'CORRESPONDENCE'
  | 'SCHEDULE'
  | 'HSE'
  | 'GENERAL';

export type DocumentStatus =
  | 'pending'
  | 'processing'
  | 'indexed'
  | 'failed';

// BOQ Types
export interface BOQItem {
  id: number;
  project_id: number;
  package_id?: number;
  line_number: string;
  section?: string;
  description: string;
  unit: string;
  quantity: number;
  trade_category?: string;
  unit_rate?: number;
  total_price?: number;
  is_excluded: boolean;
}

export interface BOQStatistics {
  total_items: number;
  by_trade: Record<string, number>;
  by_section: Record<string, number>;
}

// Package Types
export interface Package {
  id: number;
  project_id: number;
  name: string;
  code: string;
  trade_category: string;
  description?: string;
  status: PackageStatus;
  total_items: number;
  offers_received: number;
  offers_evaluated: number;
  submission_deadline?: string;
  estimated_value?: number;
  currency?: string;
  folder_path?: string;
  created_at: string;
}

export type PackageStatus =
  | 'draft'
  | 'ready'
  | 'sent'
  | 'received'
  | 'evaluated'
  | 'awarded'
  | 'closed';

export interface PackageStatistics {
  total_packages: number;
  by_status: Record<string, number>;
  total_boq_items: number;
  assigned_items: number;
  unassigned_items: number;
  assignment_rate: number;
}

// Supplier Types
export interface Supplier {
  id: number;
  name: string;
  code?: string;
  emails: string[];
  trade_categories: string[];
  contact_name?: string;
  phone?: string;
  region?: string;
  country?: string;
  rating?: number;
  is_active: boolean;
  is_blacklisted: boolean;
  total_rfqs_sent: number;
  total_offers_received: number;
  total_awards: number;
}

// Offer Types
export interface Offer {
  id: number;
  package_id: number;
  supplier_id: number;
  supplier_name?: string;
  status: OfferStatus;
  total_price?: number;
  currency?: string;
  validity_days?: number;
  delivery_weeks?: number;
  payment_terms?: string;
  commercial_score?: number;
  technical_score?: number;
  overall_score?: number;
  rank?: number;
  exclusions?: string[];
  deviations?: Array<{ item: string; deviation: string }>;
  line_items?: OfferLineItem[];
  received_at: string;
  evaluated_at?: string;
}

export type OfferStatus =
  | 'received'
  | 'under_review'
  | 'compliant'
  | 'non_compliant'
  | 'evaluated'
  | 'selected'
  | 'rejected';

export interface OfferLineItem {
  description: string;
  unit: string;
  quantity: number;
  unit_rate: number;
  total: number;
}

export interface OfferComparison {
  package_id: number;
  package_name: string;
  total_boq_items: number;
  total_offers: number;
  evaluated_offers: number;
  price_statistics: {
    min: number;
    max: number;
    average: number;
    currency: string;
  };
  offers: Offer[];
}

// Dashboard Types
export interface DashboardStats {
  project_id: number;
  project_name: string;
  project_status: string;
  summary: {
    total_packages: number;
    total_items: number;
    priced_items: number;
    pricing_completion: number;
    total_value: number;
    total_offers: number;
  };
  packages_by_status: Record<string, number>;
  offers_by_status: Record<string, number>;
  value_by_trade: Record<string, number>;
}

// Pricing Types
export interface ProjectTotals {
  project_id: number;
  project_name: string;
  total_packages: number;
  total_items: number;
  priced_items: number;
  unpriced_items: number;
  total_value: number;
  by_trade: Record<string, { count: number; priced: number; total: number }>;
  completion_rate: number;
}

export interface CostBreakdown {
  project_id: number;
  grand_total: number;
  trades: Array<{
    trade: string;
    count: number;
    total: number;
    percentage: number;
    top_items: Array<{
      description: string;
      quantity: number;
      unit: string;
      unit_rate: number;
      total: number;
    }>;
  }>;
}

// Email Types
export interface EmailLog {
  id: number;
  package_id?: number;
  supplier_id?: number;
  email_type: EmailType;
  status: EmailStatus;
  to_addresses: string[];
  subject: string;
  sent_at?: string;
  created_at: string;
}

export type EmailType = 'rfq' | 'reminder' | 'clarification' | 'award' | 'regret';
export type EmailStatus = 'draft' | 'queued' | 'sent' | 'delivered' | 'failed';

// Common Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface MessageResponse {
  message: string;
  success: boolean;
  data?: Record<string, unknown>;
}

// Trade Categories
export const TRADE_CATEGORIES = [
  'CIVIL',
  'CONCRETE',
  'STRUCTURAL_STEEL',
  'MASONRY',
  'WATERPROOFING',
  'ROOFING',
  'DOORS_WINDOWS',
  'FINISHES',
  'MEP_MECHANICAL',
  'MEP_ELECTRICAL',
  'MEP_PLUMBING',
  'FIRE_PROTECTION',
  'ELEVATORS',
  'LANDSCAPING',
  'FURNITURE',
  'GENERAL',
] as const;

export type TradeCategory = typeof TRADE_CATEGORIES[number];
