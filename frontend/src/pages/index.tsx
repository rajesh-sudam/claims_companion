
import Link from 'next/link';
import { ShieldCheck, Bot, GanttChartSquare } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

const HomePage = () => {
  const { isAuthenticated } = useAuth();

  return (
    <div className="bg-transparent text-base-100">
      {/* Hero Section */}
      <div className="text-center py-24 px-4 sm:px-6 lg:px-8">
        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight text-text-secondary">
          The Future of Insurance Claims is <span className="text-primary">Here</span>
        </h1>
        <p className="mt-4 max-w-3xl mx-auto text-lg text-text-secondary">
          Experience a fast, fair, and transparent claims process, powered by cutting-edge artificial intelligence. Welcome to CogniClaim.
        </p>
        <div className="mt-10">
          {isAuthenticated && (
            <Link href="/claims/new" className="px-8 py-4 text-lg font-semibold text-text-primary bg-primary rounded-lg hover:opacity-90 transition-opacity">
              File a Claim
            </Link>
          )}
        </div>
      </div>

      {/* Features Section */}
      <div className="py-16 sm:py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-base font-semibold text-primary tracking-wide uppercase">A better experience</h2>
            <p className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">
              A Seamless Claims Journey
            </p>
          </div>
          <div className="mt-12 grid gap-10 sm:grid-cols-1 md:grid-cols-3">
            <div className="text-center p-8 glassy-card rounded-xl shadow-lg">
              <div className="flex items-center justify-center h-12 w-12 rounded-md bg-primary text-secondary mx-auto">
                <ShieldCheck />
              </div>
              <h3 className="mt-6 text-xl font-medium text-text-secondary">AI-Powered Validation</h3>
              <p className="mt-2 text-base text-text-secondary">
                Our AI analyzes your claim documents for completeness and accuracy, reducing errors and speeding up the process.
              </p>
            </div>
            <div className="text-center p-8 glassy-card rounded-xl shadow-lg">
              <div className="flex items-center justify-center h-12 w-12 rounded-md bg-primary text-text-primary mx-auto">
                <Bot />
              </div>
              <h3 className="mt-6 text-xl font-medium text-text-secondary">24/7 AI Chat Assistant</h3>
              <p className="mt-2 text-base text-text-secondary">
                Get instant answers to your policy questions and claim status inquiries any time of day from our smart assistant.
              </p>
            </div>
            <div className="text-center p-8 glassy-card rounded-xl shadow-lg">
              <div className="flex items-center justify-center h-12 w-12 rounded-md bg-primary text-text-primary mx-auto">
                <GanttChartSquare />
              </div>
              <h3 className="mt-6 text-xl font-medium text-text-secondary">Real-Time Progress Tracking</h3>
              <p className="mt-2 text-base text-text-secondary">
                Follow your claim's journey from submission to resolution with a clear, step-by-step progress timeline.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Testimonials Section */}
      <div className="py-16 sm:py-24 bg-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Trusted by thousands</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <div className="glassy-card p-6 rounded-lg shadow-lg">
              <p className="text-text-secondary">"The CogniClaim process was unbelievably fast and simple. I got my claim approved in record time!"</p>
              <div className="mt-4 flex items-center">
                <div className="font-semibold text-text-secondary">Sarah L.</div>
                <div className="ml-2 text-text-secondary">@sarah_l</div>
              </div>
            </div>
            <div className="glassy-card p-6 rounded-lg shadow-lg">
              <p className="text-text-secondary">"I never thought filing an insurance claim could be this stress-free. The AI assistant was incredibly helpful."</p>
              <div className="mt-4 flex items-center">
                <div className="font-semibold text-text-secondary">Mike R.</div>
                <div className="ml-2 text-text-secondary">@miker</div>
              </div>
            </div>
            <div className="glassy-card p-6 rounded-lg shadow-lg">
              <p className="text-text-secondary">"The transparency is amazing. I knew exactly where my claim was at every step of the way."</p>
              <div className="mt-4 flex items-center">
                <div className="font-semibold text-text-secondary">Jessica P.</div>
                <div className="ml-2 text-text-secondary">@jess_p</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="glassy-card">
        <div className="max-w-4xl mx-auto text-center py-16 px-4 sm:px-6 sm:py-20 lg:px-8 lg:py-24">
          <h2 className="text-3xl font-extrabold text-text-secondary sm:text-4xl">
            <span className="block">Ready to experience a better way to claim?</span>
          </h2>
          <p className="mt-4 text-lg leading-6 text-text-secondary">
            Get started today and let our AI-powered platform handle the rest.
          </p>
          {isAuthenticated && (
            <Link href="/claims/new" className="mt-8 w-full inline-flex items-center justify-center px-5 py-3 border border-transparent text-base font-medium rounded-md text-text-primary bg-primary hover:opacity-90 sm:w-auto">
              File Your Claim Today
            </Link>
          )}
        </div>
      </div>

    </div>
  );
};

export default HomePage;
