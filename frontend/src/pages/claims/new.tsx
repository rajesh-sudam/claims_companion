import { useState, useEffect, ChangeEvent } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/utils/api';

type ClaimType = 'motor' | 'health' | 'property' | 'travel';

const LOCAL_STORAGE_KEY = 'new_claim_draft';

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

  // Load draft from localStorage on initial component mount
  useEffect(() => {
    const draft = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (draft) {
      try {
        const parsed = JSON.parse(draft);
        setClaimType(parsed.claimType || '');
        setIncidentDate(parsed.incidentDate || '');
        setIncidentDescription(parsed.incidentDescription || '');
        setContactPhone(parsed.contactPhone || user?.phone || '');
        // Note: Files cannot be restored from localStorage for security reasons.
      } catch (e) {
        console.error("Failed to parse claim draft from localStorage", e);
      }
    }
  }, [user?.phone]);

  // Save draft to localStorage whenever form data changes
  useEffect(() => {
    const draftData = {
      claimType,
      incidentDate,
      incidentDescription,
      contactPhone,
    };
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(draftData));
  }, [claimType, incidentDate, incidentDescription, contactPhone]);

  const nextStep = () => setStep((s) => s + 1);
  const prevStep = () => setStep((s) => s - 1);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles) {
      // Append new files to existing ones instead of replacing
      setFiles((prevFiles) => [...prevFiles, ...Array.from(selectedFiles)]);
    }
  };

  const handleRemoveFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async () => {
    if (!claimType || !incidentDescription) {
        setError("Claim Type and Incident Description are required to submit.");
        return;
    }
    setError(null);
    setLoading(true);
    
    try {
      const formData = new FormData();
      formData.append('claim_type', claimType);
      formData.append('incident_date', incidentDate || '');
      formData.append('incident_description', incidentDescription);
      formData.append('contact_phone', contactPhone);
      files.forEach((file) => formData.append('files', file));

      const response = await api.post('/claims', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const { claim } = response.data;
      localStorage.removeItem(LOCAL_STORAGE_KEY);
      router.push(`/claims/${claim.id}?submitted=true`);
    } catch (err: any) {
      console.error('Error submitting claim:', err);
      setError(
        err.response?.data?.error ||
        err.response?.data?.detail ||
        err.message ||
        'An unexpected error occurred. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const isSubmitDisabled = loading || !claimType || !incidentDescription;

  return (
    <div className="min-h-screen p-6 bg-background text-text-secondary">
      <h1 className="text-2xl font-semibold mb-4 text-text-secondary">New Claim Submission</h1>
      {error && <p className="text-red-500 bg-red-900/20 p-3 rounded-md mb-4">{error}</p>}
      <div className="glassy-card p-6 rounded-lg shadow-md">
        {/* Step navigation indicator */}
        <div className="flex items-center justify-between mb-8">
          {['Select Type', 'Incident Details', 'Documents', 'Contact Info', 'Review'].map((title, index) => {
            const current = index + 1;
            const isCompleted = step > current;
            const isActive = step === current;
            return (
              <div key={current} className="flex-1 flex flex-col items-center text-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center mb-1 transition-all duration-300 ${
                    isActive ? 'bg-primary text-text-primary' : isCompleted ? 'bg-primary text-text-primary' : 'bg-surface text-text-secondary'
                  }`}
                >
                  {isCompleted ? '✓' : current}
                </div>
                <span className={`text-xs ${step >= current ? 'font-semibold text-text-secondary' : 'text-text-secondary'}`}>{title}</span>
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
                  className={`border border-border rounded-lg p-4 cursor-pointer flex items-center justify-center transition-all duration-200 ${
                    claimType === type ? 'border-primary bg-primary/20 ring-2 ring-primary/50' : 'hover:border-pinkHighlight hover:bg-pinkHighlight/20'
                  }`}
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
            <div className="flex justify-between mt-8">
              <button disabled className="px-4 py-2 rounded bg-surface text-text-secondary cursor-not-allowed">Back</button>
              <button
                onClick={nextStep}
                disabled={!claimType}
                className={`px-4 py-2 rounded ${claimType ? 'bg-primary text-text-primary hover:bg-accent-hover' : 'bg-surface text-text-secondary cursor-not-allowed'}`}
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
              <label className="block text-sm font-medium text-text-secondary mb-1" htmlFor="incidentDate">Incident Date</label>
              <input
                id="incidentDate"
                type="date"
                value={incidentDate}
                onChange={(e) => setIncidentDate(e.target.value)}
                max={new Date().toISOString().split('T')[0]}
                className="w-full border border-border p-2 rounded-md bg-transparent text-text-secondary"
              />
            </div>
            <div className="mb-6">
              <label className="block text-sm font-medium text-text-secondary mb-1" htmlFor="incidentDescription">Description</label>
              <textarea
                id="incidentDescription"
                value={incidentDescription}
                onChange={(e) => setIncidentDescription(e.target.value)}
                className="w-full border border-border p-2 rounded-md bg-transparent text-text-secondary"
                rows={4}
                placeholder="Please describe the incident in detail..."
              ></textarea>
            </div>
            <div className="flex justify-between mt-8">
              <button onClick={prevStep} className="px-4 py-2 rounded bg-surface hover:bg-surface text-text-secondary">Back</button>
              <button
                onClick={nextStep}
                disabled={!incidentDescription}
                className={`px-4 py-2 rounded ${incidentDescription ? 'bg-primary text-text-primary hover:bg-accent-hover' : 'bg-surface text-text-secondary cursor-not-allowed'}`}
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
            <p className="text-sm text-text-secondary mb-4">Upload supporting documents (e.g., photos, receipts, PDFs).</p>
            <input
              type="file"
              multiple
              accept="image/*,.pdf,.doc,.docx"
              onChange={handleFileChange}
              className="mb-4 w-full border border-border p-2 rounded-md bg-transparent text-text-secondary"
            />
            {files.length > 0 && (
              <div className="mb-4">
                <h3 className="font-medium mb-2">Selected Files:</h3>
                <ul className="space-y-2">
                  {files.map((file, idx) => (
                    <li key={idx} className="flex items-center justify-between bg-surface p-2 rounded-md">
                      <span className="mr-2 text-sm truncate">{file.name}</span>
                      <button type="button" onClick={() => handleRemoveFile(idx)} className="text-xs text-red-500 hover:underline flex-shrink-0">Remove</button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex justify-between mt-8">
              <button onClick={prevStep} className="px-4 py-2 rounded bg-surface hover:bg-surface text-text-secondary">Back</button>
              <button onClick={nextStep} className="px-4 py-2 rounded bg-primary text-text-primary hover:bg-accent-hover">Next</button>
            </div>
          </div>
        )}

        {/* Step 4: Contact Info */}
        {step === 4 && (
          <div>
            <h2 className="text-xl font-semibold mb-4">Contact Information</h2>
            <div className="mb-6">
              <label className="block text-sm font-medium text-text-secondary mb-1" htmlFor="contactPhone">Phone Number</label>
              <input
                id="contactPhone"
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                className="w-full border border-border p-2 rounded-md bg-transparent text-text-secondary"
              />
            </div>
            <div className="flex justify-between mt-8">
              <button onClick={prevStep} className="px-4 py-2 rounded bg-surface hover:bg-surface text-text-secondary">Back</button>
              <button onClick={nextStep} className="px-4 py-2 rounded bg-primary text-text-primary hover:bg-accent-hover">Next</button>
            </div>
          </div>
        )}

        {/* Step 5: Review and Submit */}
        {step === 5 && (
          <div>
            <h2 className="text-xl font-semibold mb-4">Review & Submit</h2>
            <div className="mb-6 space-y-2 text-text-secondary">
              <p><strong>Claim Type:</strong> <span className="capitalize">{claimType || 'N/A'}</span></p>
              <p><strong>Incident Date:</strong> {incidentDate || 'N/A'}</p>
              <p><strong>Description:</strong> {incidentDescription || 'N/A'}</p>
              <p><strong>Contact Phone:</strong> {contactPhone || 'N/A'}</p>
              <div>
                <strong>Files:</strong> {files.length > 0 ? `${files.length} selected` : 'None'}
                {files.length > 0 && (
                  <ul className="list-disc list-inside mt-1 text-sm text-text-secondary">
                    {files.map((file, idx) => (
                      <li key={idx}>{file.name}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            <div className="flex justify-between mt-8">
              <button onClick={prevStep} className="px-4 py-2 rounded bg-surface hover:bg-surface text-text-secondary">Back</button>
              <button
                onClick={handleSubmit}
                disabled={isSubmitDisabled}
                className={`px-4 py-2 rounded ${isSubmitDisabled ? 'bg-surface text-text-secondary cursor-not-allowed' : 'bg-primary text-text-primary hover:bg-accent-hover'}`}
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