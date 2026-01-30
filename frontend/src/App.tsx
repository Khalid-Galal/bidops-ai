import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';

// Layouts
import MainLayout from '@/components/layout/MainLayout';
import AuthLayout from '@/components/layout/AuthLayout';

// Auth Pages
import LoginPage from '@/pages/auth/LoginPage';

// Main Pages
import DashboardPage from '@/pages/DashboardPage';
import ProjectsPage from '@/pages/projects/ProjectsPage';
import ProjectDetailPage from '@/pages/projects/ProjectDetailPage';
import DocumentsPage from '@/pages/documents/DocumentsPage';
import PackagesPage from '@/pages/packages/PackagesPage';
import PackageDetailPage from '@/pages/packages/PackageDetailPage';
import BOQPage from '@/pages/boq/BOQPage';
import SuppliersPage from '@/pages/suppliers/SuppliersPage';
import SupplierDetailPage from '@/pages/suppliers/SupplierDetailPage';
import OffersPage from '@/pages/offers/OffersPage';
import OfferDetailPage from '@/pages/offers/OfferDetailPage';
import PricingPage from '@/pages/pricing/PricingPage';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

function ProtectedRoute({ children }: ProtectedRouteProps) {
  // Auth disabled for demo - always allow access
  return <>{children}</>;
}

function PublicRoute({ children }: ProtectedRouteProps) {
  // Auth disabled - redirect login to home
  return <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            iconTheme: {
              primary: '#10B981',
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#EF4444',
              secondary: '#fff',
            },
          },
        }}
      />

      <Routes>
        {/* Auth Routes */}
        <Route
          path="/login"
          element={
            <PublicRoute>
              <AuthLayout>
                <LoginPage />
              </AuthLayout>
            </PublicRoute>
          }
        />

        {/* Protected Routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/:id" element={<ProjectDetailPage />} />
          <Route path="projects/:id/documents" element={<DocumentsPage />} />
          <Route path="projects/:id/boq" element={<BOQPage />} />
          <Route path="projects/:id/packages" element={<PackagesPage />} />
          <Route path="projects/:id/packages/:packageId" element={<PackageDetailPage />} />
          <Route path="projects/:id/pricing" element={<PricingPage />} />
          <Route path="suppliers" element={<SuppliersPage />} />
          <Route path="suppliers/:id" element={<SupplierDetailPage />} />
          <Route path="offers" element={<OffersPage />} />
          <Route path="offers/:id" element={<OfferDetailPage />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
