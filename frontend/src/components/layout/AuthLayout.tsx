import { ReactNode } from 'react';

interface AuthLayoutProps {
  children: ReactNode;
}

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left Side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-primary-600 p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center">
              <span className="text-primary-600 font-bold text-xl">B</span>
            </div>
            <span className="text-2xl font-semibold text-white">BidOps AI</span>
          </div>
        </div>

        <div className="space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Streamline Your
            <br />
            Tender Management
          </h1>
          <p className="text-primary-100 text-lg max-w-md">
            AI-powered bid operations platform that automates document processing,
            BOQ extraction, supplier management, and offer evaluation.
          </p>
          <div className="flex gap-4 pt-4">
            <div className="text-center">
              <p className="text-3xl font-bold text-white">80%</p>
              <p className="text-sm text-primary-200">Time Saved</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-white">99%</p>
              <p className="text-sm text-primary-200">Accuracy</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-white">10x</p>
              <p className="text-sm text-primary-200">Faster Processing</p>
            </div>
          </div>
        </div>

        <div className="text-primary-200 text-sm">
          &copy; {new Date().getFullYear()} BidOps AI. All rights reserved.
        </div>
      </div>

      {/* Right Side - Auth Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {children}
        </div>
      </div>
    </div>
  );
}
