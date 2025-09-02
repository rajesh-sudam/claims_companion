import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

const MyClaimsPage = () => {
  const { isAuthenticated, user } = useAuth();

  // Dummy data for claims
  const claims = [
    { id: 'CLM001', type: 'Auto', status: 'Pending', date: '2023-01-15' },
    { id: 'CLM002', type: 'Home', status: 'Approved', date: '2023-02-20' },
    { id: 'CLM003', type: 'Health', status: 'Rejected', date: '2023-03-10' },
  ];

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

        {claims.length === 0 ? (
          <div className="glassy-card p-10 rounded-lg shadow-lg text-center text-text-secondary">
            <p className="text-lg">You have no claims submitted yet.</p>
            <Link href="/new-claim" className="mt-4 inline-block px-6 py-3 border border-transparent text-base font-medium rounded-md text-text-primary bg-primary hover:opacity-90">
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
                      Claim ID
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Type
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Date
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
                        {claim.id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                        {claim.type}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          claim.status === 'Approved' ? 'bg-green-100 text-green-800' :
                          claim.status === 'Pending' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {claim.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                        {claim.date}
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
