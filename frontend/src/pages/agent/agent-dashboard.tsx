import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/router';
import api from '@/utils/api';
import Link from 'next/link';

interface Claim {
  id: string;
  claim_number: string;
  claim_type: string;
  status: string;
  incident_date: string;
  estimated_completion?: string;
}

const AgentDashboard = () => {
  const { isAuthenticated, user, isLoading } = useAuth();
  const router = useRouter();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loadingClaims, setLoadingClaims] = useState<boolean>(true);
  const [claimsError, setClaimsError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isLoading, isAuthenticated, router]);

  useEffect(() => {
    if (user?.role && user.role !== 'agent') {
      router.push('/my-claims');
    }
  }, [user, router]);

  useEffect(() => {
    if (isAuthenticated && user?.role === 'agent') {
      const fetchUnprocessedClaims = async () => {
        setLoadingClaims(true);
        setClaimsError(null);
        try {
          const response = await api.get('/admin/claims', { params: { status: ['pending_human_review', 'awaiting_documents'] } });
          setClaims(response.data.claims);
        } catch (err: any) {
          setClaimsError(err.response?.data?.detail || 'Failed to fetch unprocessed claims.');
          console.error('Error fetching unprocessed claims:', err);
        } finally {
          setLoadingClaims(false);
        }
      };

      fetchUnprocessedClaims();
    }
  }, [isAuthenticated, user]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending_human_review':
        return 'bg-blue-100 text-blue-800';
      case 'awaiting_documents':
        return 'bg-yellow-100 text-yellow-800';
      case 'documents_under_review':
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (isLoading || !isAuthenticated || user?.role !== 'agent') {
    return <p className="p-6">Loading...</p>;
  }

  return (
    <div className="min-h-screen bg-background py-12 px-4 sm:px-6 lg:px-8">
      <Head>
        <title>Agent Dashboard - CogniClaim</title>
        <meta name="description" content="Agent Dashboard for managing claims." />
      </Head>

      <div className="max-w-4xl mx-auto space-y-6 glassy-card p-10 rounded-lg shadow-lg">
        <h1 className="text-4xl font-extrabold text-text-secondary mb-8 text-center">Agent Dashboard</h1>
        <p className="text-lg text-gray-300">Welcome, Agent {user?.email}!</p>
        <p className="text-lg text-gray-300">This is where you can manage claims assigned to you.</p>

        <h2 className="text-3xl font-bold text-text-secondary mt-8 mb-4">Unprocessed Claims</h2>
        {loadingClaims ? (
          <p className="text-lg text-gray-300">Loading unprocessed claims...</p>
        ) : claimsError ? (
          <p className="text-lg text-red-500">{claimsError}</p>
        ) : claims.length === 0 ? (
          <p className="text-lg text-gray-300">No unprocessed claims found.</p>
        ) : (
          <div className="overflow-x-auto bg-gray-900/50 rounded-lg border border-gray-700/50">
            <table className="min-w-full divide-y divide-gray-800">
              <thead className="bg-gray-800/50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Claim Number
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Claim Type
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Incident Date
                  </th>
                  <th scope="col" className="relative px-6 py-3">
                    <span className="sr-only">View</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {claims.map((claim) => (
                  <tr key={claim.id} className="hover:bg-gray-800/50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">
                      {claim.claim_number}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300 capitalize">
                      {claim.claim_type}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(claim.status)}`}>
                        {claim.status.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                      {new Date(claim.incident_date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <Link href={`/agent/claims/${claim.id}`} className="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                        View Claim
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentDashboard;