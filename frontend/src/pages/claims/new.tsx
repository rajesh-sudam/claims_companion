import { useState } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/utils/api';

type ClaimType = 'motor' | 'health' | 'property' | 'travel';

export default function NewClaimPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [claimType, setClaimType] = useState<ClaimType | ''>('');
  const [incidentDate, setIncidentDate] = useState('');
  const [incidentDescription, setIncidentDescription] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [contactPhone, setContactPhone] = useState(user?.phone || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nextStep = () => setStep((s) => s + 1);
  const prevStep = () => setStep((s) => s - 1);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles) {
      setFiles(Array.from(selectedFiles));
    }
  };

  const handleSubmit = async () => {
    setError(null);
    setLoading(true);
    try {
      const response = await api.post('/claims', {
        claim_type: claimType,
        incident_date: incidentDate || null,
        incident_description: incidentDescription,
      });
      const { claim } = response.data;
      // TODO: handle file uploads separately using claim.id
      router.push(`/claims/${claim.id}`);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to submit claim');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-6">
      <h1 className="text-2xl font-semibold mb-4">New Claim Submission</h1>
      {error && <p className="text-red-500 mb-4">{error}</p>}
      <div className="bg-white p-6 rounded shadow-md">
        {/* Step navigation indicator */}
        <div className="flex items-center justify-between mb-6">
          {['Select Type', 'Incident Details', 'Documents', 'Contact Info', 'Review'].map((title, index) => {
            const current = index + 1;
            return (
              <div key={current} className="flex-1 flex flex-col items-center text-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center mb-1 ${step === current ? 'bg-blue-600 text-white' : step > current ? 'bg-green-500 text-white' : 'bg-gray-300 text-gray-700'}`}
                >
                  {current}
                </div>
                <span className={`text-xs ${step >= current ? 'font-semibold' : 'text-gray-500'}`}>{title}</span>
              </div>
            );
          })}
        </div>
        {/* Step 1: Claim Type Selection */}
        {step === 1 && (
          <div>
            <h2 className="text-xl font-semibold mb-4">Select Claim Type</h2>
            <div className="grid grid-cols-2 gap-4 mb-6">
              {(['motor', 'health', 'property', 'travel'] as ClaimType[]).map((type) => (
                <label
                  key={type}
                  className={`border rounded p-4 cursor-pointer flex items-center justify-center ${claimType === type ? 'border-blue-600 bg-blue-50' : 'border-gray-300'}`}
                >
                  <input
                    type="radio"
                    name="claimType"
                    value={type}
                    checked={claimType === type}
                    onChange={() => setClaimType(type)}
                    className="hidden"
                  />
                  <span className="capitalize font-medium">{type}</span>
                </label>
              ))}
            </div>
            <div className="flex justify-between">
              <button
                disabled
                className="px-4 py-2 rounded bg-gray-300 text-gray-500 cursor-not-allowed"
              >
                Back
              </button>
              <button
                onClick={nextStep}
                disabled={!claimType}
                className={`px-4 py-2 rounded ${claimType ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-300 text-gray-500 cursor-not-allowed'}`}
              >
                Next
              </button>
            </div>
          </div>
        )}
        {/* Step 2: Incident Details */}
        {step === 2 && (
          <div>
            <h2 className="text-xl font-semibold mb-4">Incident Details</h2>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="incidentDate">Incident Date</label>
              <input
                id="incidentDate"
                type="date"
                value={incidentDate}
                onChange={(e) => setIncidentDate(e.target.value)}
                className="w-full border border-gray-300 p-2 rounded"
              />
            </div>
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="incidentDescription">Description</label>
              <textarea
                id="incidentDescription"
                value={incidentDescription}
                onChange={(e) => setIncidentDescription(e.target.value)}
                className="w-full border border-gray-300 p-2 rounded"
                rows={4}
              ></textarea>
            </div>
            <div className="flex justify-between">
              <button onClick={prevStep} className="px-4 py-2 rounded bg-gray-200">Back</button>
              <button
                onClick={nextStep}
                disabled={!incidentDescription}
                className={`px-4 py-2 rounded ${incidentDescription ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-300 text-gray-500 cursor-not-allowed'}`}
              >
                Next
              </button>
            </div>
          </div>
        )}
        {/* Step 3: Documents */}
        {step === 3 && (
          <div>
            <h2 className="text-xl font-semibold mb-4">Document Upload</h2>
            <p className="text-sm text-gray-600 mb-4">Upload supporting documents (e.g. photos, receipts). This feature is not functional in the MVP skeleton.</p>
            <input
              type="file"
              multiple
              onChange={handleFileChange}
              className="mb-6"
            />
            <div className="flex justify-between">
              <button onClick={prevStep} className="px-4 py-2 rounded bg-gray-200">Back</button>
              <button onClick={nextStep} className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700">Next</button>
            </div>
          </div>
        )}
        {/* Step 4: Contact Info */}
        {step === 4 && (
          <div>
            <h2 className="text-xl font-semibold mb-4">Contact Information</h2>
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="contactPhone">Phone Number</label>
              <input
                id="contactPhone"
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                className="w-full border border-gray-300 p-2 rounded"
              />
            </div>
            <div className="flex justify-between">
              <button onClick={prevStep} className="px-4 py-2 rounded bg-gray-200">Back</button>
              <button onClick={nextStep} className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700">Next</button>
            </div>
          </div>
        )}
        {/* Step 5: Review and Submit */}
        {step === 5 && (
          <div>
            <h2 className="text-xl font-semibold mb-4">Review & Submit</h2>
            <div className="mb-4">
              <p><strong>Claim Type:</strong> {claimType}</p>
              <p><strong>Incident Date:</strong> {incidentDate || 'N/A'}</p>
              <p><strong>Description:</strong> {incidentDescription}</p>
              <p><strong>Contact Phone:</strong> {contactPhone || 'N/A'}</p>
              <p><strong>Files:</strong> {files.length} selected (not uploaded)</p>
            </div>
            <div className="flex justify-between">
              <button onClick={prevStep} className="px-4 py-2 rounded bg-gray-200">Back</button>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="px-4 py-2 rounded bg-green-600 text-white hover:bg-green-700"
              >
                {loading ? 'Submitting...' : 'Submit Claim'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}