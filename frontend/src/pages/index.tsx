import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/utils/api';

interface Claim {
  id: number;
  claim_number: string;
  claim_type: string;
  status: string;
  incident_date: string | null;
  estimated_completion: string | null;
}

export default function Dashboard() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/login');
    }
  }, [user, isLoading, router]);

  useEffect(() => {
    const fetchClaims = async () => {
      if (!user) return;
      setLoading(true);
      try {
        const response = await api.get('/claims');
        setClaims(response.data.claims);
      } catch (err: any) {
        setError(err.response?.data?.error || 'Failed to load claims');
      } finally {
        setLoading(false);
      }
    };
    fetchClaims();
  }, [user]);

  const handleNewClaim = () => {
    router.push('/claims/new');
  };

  if (!user) return null;

  return (
    <div className="min-h-screen p-6">
      <h1 className="text-3xl font-bold mb-6">Welcome, {user.first_name || user.email}</h1>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">Your Claims</h2>
        <button
          onClick={handleNewClaim}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          New Claim
        </button>
      </div>
      {loading && <p>Loading claims...</p>}
      {error && <p className="text-red-500 mb-4">{error}</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {claims.map((claim) => (
          <div
            key={claim.id}
            className="bg-white p-4 rounded shadow cursor-pointer hover:bg-gray-50"
            onClick={() => router.push(`/claims/${claim.id}`)}
          >
            <h3 className="font-semibold mb-1">{claim.claim_number}</h3>
            <p className="text-sm text-gray-600 capitalize">Type: {claim.claim_type}</p>
            <p className="text-sm text-gray-600">Status: {claim.status.replace(/_/g, ' ')}</p>
            {claim.estimated_completion && (
              <p className="text-sm text-gray-600">
                Estimated Completion: {new Date(claim.estimated_completion).toLocaleDateString()}
              </p>
            )}
          </div>
        ))}
      </div>
      {claims.length === 0 && !loading && <p>No claims submitted yet.</p>}
    </div>
  );
}