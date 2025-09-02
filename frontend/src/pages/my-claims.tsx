import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/utils/api'; // Import the API utility

interface Claim {
  id: string;
  claim_number: string; // Changed from 'type' to 'claim_number'
  claim_type: string; // Added 'claim_type'
  status: string;
  incident_date: string; // Changed from 'date' to 'incident_date'
  estimated_completion?: string; // Added optional 'estimated_completion'
}

const MyClaimsPage = () => {
  const { isAuthenticated, user } = useAuth();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchClaims = async () => {
      if (!isAuthenticated) { // Removed user?.userId check as it's not needed for this endpoint
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const response = await api.get('/claims'); // Changed API path
        const fetchedClaims = response.data.claims.map((c: any) => ({
          id: c.id,
          claim_number: c.claim_number,
          claim_type: c.claim_type,
          status: c.status,
          incident_date: c.incident_date,
          estimated_completion: c.estimated_completion,
        }));
        setClaims(fetchedClaims);

      } catch (err) {
        setError('Failed to fetch claims. Please try again.');
        console.error('Error fetching claims:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchClaims();
  }, [isAuthenticated]); // Refetch when authentication status changes

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <Head>
        <title>My Claims - CogniClaim</title>
      </Head>
        <div className="max-w-md w-full space-y-8 glassy-card p-10 rounded-lg shadow-lg text-center">
          <h2 className="mt-6 text-3xl font-extrabold text-text-secondary">
            Access Denied
          </h2>
          <p className="mt-2 text-gray-400">
            Please <Link href="/login" className="text-primary hover:underline">log in</Link> to view your claims.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background py-12 px-4 sm:px-6 lg:px-8">
      <Head>
        <title>My Claims - CogniClaim</title>
        <meta name="description" content="View your submitted insurance claims." />
      </Head>

      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-extrabold text-text-secondary mb-8 text-center">
          My Claims
        </h1>

        {loading ? (
          <div className="glassy-card p-10 rounded-lg shadow-lg text-center text-text-secondary">
            <p className="text-lg">Loading claims...</p>
          </div>
        ) : error ? (
          <div className="glassy-card p-10 rounded-lg shadow-lg text-center text-red-500">
            <p className="text-lg">{error}</p>
          </div>
        ) : claims.length === 0 ? (
          <div className="glassy-card p-10 rounded-lg shadow-lg text-center text-text-secondary">
            <p className="text-lg">You have no claims submitted yet.</p>
            <Link href="/claims/new" className="mt-4 inline-block px-6 py-3 border border-transparent text-base font-medium rounded-md text-text-primary bg-primary hover:opacity-90">
              File a New Claim
            </Link>
          </div>
        ) : (
          <div className="glassy-card p-6 rounded-lg shadow-lg">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-700">
                <thead className="glassy-card">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Claim Number
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Claim Type
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Incident Date
                    </th>
                    <th scope="col" className="relative px-6 py-3">
                      <span className="sr-only">View</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {claims.map((claim) => (
                    <tr key={claim.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-text-secondary">
                        {claim.claim_number}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                        {claim.claim_type}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          claim.status === 'approved' ? 'bg-green-100 text-green-800' :
                          claim.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {claim.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                        {new Date(claim.incident_date).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <Link href={`/claims/${claim.id}`} className="text-primary hover:text-primary-dark">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MyClaimsPage;
