import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import io from 'socket.io-client';
import { ChangeEvent } from 'react';
import api from '../../../utils/api';
import { useAuth } from '../../../contexts/AuthContext';

interface ClaimDetail {
  id: number;
  claim_number: string;
  claim_type: string;
  status: string;
  incident_date: string | null;
  incident_description: string | null;
  estimated_completion: string | null;
  created_at: string;
  updated_at: string;
}

interface ProgressStep {
  id: number;
  step_id: string;
  step_title: string;
  status: string;
  completed_at: string | null;
  description: string | null;
}

interface ChatMessage {
  id: number | string;
  message_type: string;
  message_text: string;
  created_at: string;
  attachment_url?: string | null;
  attachment_name?: string | null;
}

interface TypingEvent {
  from: string;
}

interface AISummary {
  summary: string;
  risk_score: number; // 0..1
  facts: Record<string, any> | Array<{ name: string; value: any }>;
}

interface ClaimDocument {
  id: number;
  file_name: string;
  file_url: string;
  document_type: string;
  status: string;
  validation_status: string;
  validation_confidence: number;
  validation_issues: string[]; // JSON parsed from backend
  validation_suggestions: string[]; // JSON parsed from backend
}

function normalizeFacts(
  facts: AISummary["facts"]
): Record<string, string> {
  if (Array.isArray(facts)) {
    const out: Record<string, string> = {};
    for (const f of facts) {
      if (f && typeof f === "object" && "name" in f) {
        const key = String(f.name ?? "").trim();
        if (key) out[key] = String((f as any).value ?? "");
      }
    }
    return out;
  }
  if (facts && typeof facts === "object") {
    // already a dictionary
    return Object.fromEntries(
      Object.entries(facts).map(([k, v]) => [k, String(v ?? "")])
    );
  }
  return {};
}

const getValidationStatusColor = (status: string | null | undefined) => {
  if (!status) return 'text-gray-400'; // Default for null/undefined
  switch (status) {
    case 'valid':
      return 'text-green-400';
    case 'invalid':
      return 'text-red-400';
    case 'pending_validation':
    case 'needs_review':
    case 'error':
      return 'text-yellow-400'; // Use yellow for warning/pending states
    default:
      return 'text-gray-400'; // Fallback for any other unexpected status
  }
};

export default function AgentClaimDetailPage() {
  const router = useRouter();
  const { id } = router.query;
  const { user } = useAuth();
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [progress, setProgress] = useState<ProgressStep[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [socket, setSocket] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typing, setTyping] = useState<TypingEvent | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<AISummary | null>(null);
  const [documents, setDocuments] = useState<ClaimDocument[]>([]);

  // Fetch claim, progress, and summary
  useEffect(() => {
    if (!id) return;
    const fetchData = async () => {
      try {
        const [claimRes, progressRes, historyRes, summaryRes, documentsRes] = await Promise.all([
          api.get(`/admin/claims/${id}`), // Use admin endpoint for claim details
          api.get(`/admin/claims/${id}/progress`), // Use admin endpoint for progress
          api.get(`/admin/chat/${id}/history`), // Use admin endpoint for chat history
          api.get(`/admin/claims/${id}/summary`),
          api.get(`/admin/claims/${id}/documents`),
        ]);
        setClaim(claimRes.data.claim);
        setProgress(progressRes.data.progress);
        setMessages(historyRes.data.history);
        setSummary(summaryRes.data);
        setDocuments(documentsRes.data.documents);
      } catch (err: any) {
        setError(err.response?.data?.error || 'Failed to load claim data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  // Initialize socket.io for real-time chat
  useEffect(() => {
    if (!id || socket) return;
    const s = io((process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api').replace(/\/api$/, ''));
    setSocket(s);
    s.on('connect', () => {
      console.log('Connected to socket server');
      s.emit('join_claim', id);
    });
    s.on('chat_message', (msg: ChatMessage) => {
      setMessages((prev: ChatMessage[]) => {
        if (msg.message_type === 'user') {
          // Find the optimistic message by its temporary ID or content
          const optimisticIndex = prev.findIndex(
            (m) => typeof m.id === 'string' && m.id.startsWith('temp-') && m.message_text === msg.message_text
          );

          if (optimisticIndex !== -1) {
            // Replace the optimistic message with the real one from the server
            const newMessages = [...prev];
            newMessages[optimisticIndex] = msg;
            return newMessages;
          }
        }
        // If not a user message, or no optimistic message found, just add it
        return [...prev, msg];
      });
      setTyping(null);
    });
    s.on('typing', (evt: TypingEvent) => {
      setTyping(evt);
    });
    s.on('claim_updated', (updated: any) => {
      setClaim((prev) => (prev ? { ...prev, status: updated.status } : prev));
      api.get(`/claims/${id}/progress`).then((res: { data: { progress: ProgressStep[] } }) => setProgress(res.data.progress));
    });
    return () => {
      if (s) {
        s.emit('leave_claim', id);
        s.disconnect();
      }
    };
  }, [id, socket]);

  const sendMessage = async () => {
    if (!newMessage.trim() && !file) return;

    const userMessage: ChatMessage = {
      id: 'temp-' + Date.now(), // Temporary ID for optimistic update
      message_type: 'user',
      message_text: newMessage,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setNewMessage('');
    setFile(null);

    try {
      const formData = new FormData();
      formData.append('message_text', newMessage);
      if (file) {
        formData.append('file', file);
      }
      await api.post(`/chat/${id}/messages`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    } catch (err) {
      console.error(err);
      setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
    }
  };

  const handleStatusUpdate = async (newStatus: string) => {
    try {
      await api.put(`/admin/claims/${id}/status`, { status: newStatus });
      setClaim((prev) => (prev ? { ...prev, status: newStatus } : null));
    } catch (err) {
      console.error(err);
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        await api.post(`/claims/${id}/documents`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      } catch (err) {
        console.error(err);
      }
    }
  };

  if (loading) return <p className="p-6">Loading claim...</p>;
  if (error) return <p className="p-6 text-red-500">{error}</p>;
  if (!claim) return null;

  return (
    <div className="min-h-screen bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-4xl font-extrabold text-text-secondary mb-8 text-center">Agent View: Claim {claim.claim_number}</h1>

        {/* AI Summary and Actions */}
        <div className="glassy-card p-10 rounded-lg shadow-lg">
          <h2 className="text-2xl font-semibold mb-4 text-text-secondary">AI Analysis</h2>
          {summary ? (
            <>
              <p className="text-lg text-gray-300 mb-4">{summary.summary}</p>
              <div className="mb-4">
                
                
              
  
              </div>
              <div>
                <h3 className="text-xl font-semibold text-text-secondary mb-2">Key Facts</h3>
                {(() => {
                  const factsDict = normalizeFacts(summary.facts);
                  const entries = Object.entries(factsDict);
                  if (entries.length === 0) {
                    return <p className="text-gray-400">No key facts available.</p>;
                  }
                  return (
                    <ul className="list-disc list-inside text-gray-300">
                      {entries.map(([key, value]) => (
                        <li key={key}>
                          <strong>{key.replace(/_/g, " ")}:</strong> {value}
                        </li>
                      ))}
                    </ul>
                  );
                })()}
              </div>
              <div className="mt-6 flex justify-end space-x-4">
                <button onClick={() => handleStatusUpdate('accepted')} className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600">Accept</button>
                <button onClick={() => handleStatusUpdate('rejected')} className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600">Reject</button>
                <button onClick={() => handleStatusUpdate('needs_info')} className="bg-yellow-500 text-white px-4 py-2 rounded hover:bg-yellow-600">Needs Info</button>
              </div>
            </>
          ) : (
            <p>Loading AI summary...</p>
          )}
        </div>

        {/* Documents Section */}
        <div className="glassy-card p-10 rounded-lg shadow-lg">
          <h2 className="text-2xl font-semibold mb-4 text-text-secondary">Uploaded Documents</h2>
          {documents.length === 0 ? (
            <p className="text-gray-400">No documents uploaded for this claim yet.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {documents.map((doc) => (
                <div key={doc.id} className="bg-gray-800/50 p-4 rounded-lg border border-gray-700/50 flex flex-col">
                  <p className="font-semibold text-white truncate" title={doc.file_name}>{doc.file_name}</p>
                  <p className="text-sm text-gray-400 capitalize">Type: {doc.document_type.replace(/_/g, ' ')}</p>
                  <p className="text-sm text-gray-400">Status: <span className={`font-medium ${getValidationStatusColor(doc.validation_status)}`}>{doc.validation_status ? doc.validation_status.replace(/_/g, ' ') : 'N/A'}</span></p>
                  {doc.validation_issues && doc.validation_issues.length > 0 && (
                    <ul className="text-xs text-red-300 list-disc list-inside mt-1">
                      {doc.validation_issues.map((issue, idx) => <li key={idx}>{issue}</li>)}
                    </ul>
                  )}
                  {doc.validation_suggestions && doc.validation_suggestions.length > 0 && (
                    <ul className="text-xs text-yellow-300 list-disc list-inside mt-1">
                      {doc.validation_suggestions.map((sugg, idx) => <li key={idx}>{sugg}</li>)}
                    </ul>
                  )}
                  <div className="mt-auto pt-3">
                    <a href={doc.file_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-purple-400 hover:text-purple-300 text-sm font-medium">
                      View Document
                      <svg xmlns="http://www.w3.org/2000/svg" className="ml-1 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* The rest of the component (claim summary, progress, chat) remains the same */}
        {/* ... */}
      </div>
    </div>
  );
}