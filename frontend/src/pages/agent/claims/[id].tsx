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
  id: number;
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
  risk_score: number;
  facts: Record<string, any>;
}

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

  // Fetch claim, progress, and summary
  useEffect(() => {
    if (!id) return;
    const fetchData = async () => {
      try {
        const [claimRes, progressRes, historyRes, summaryRes] = await Promise.all([
          api.get(`/admin/claims/${id}`), // Use admin endpoint for claim details
          api.get(`/admin/claims/${id}/progress`), // Use admin endpoint for progress
          api.get(`/admin/chat/${id}/history`), // Use admin endpoint for chat history
          api.get(`/admin/claims/${id}/summary`),
        ]);
        setClaim(claimRes.data.claim);
        setProgress(progressRes.data.progress);
        setMessages(historyRes.data.history);
        setSummary(summaryRes.data);
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
      setMessages((prev: ChatMessage[]) => [...prev, msg]);
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
      id: Date.now(),
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
                <h3 className="text-xl font-semibold text-text-secondary mb-2">Risk Score</h3>
                <div className="w-full bg-gray-700 rounded-full h-4">
                  <div
                    className="bg-red-500 h-4 rounded-full"
                    style={{ width: `${summary.risk_score * 100}%` }}
                  ></div>
                </div>
                <p className="text-right text-sm text-gray-400">{(summary.risk_score * 100).toFixed(0)}% Risk</p>
              </div>
              <div>
                <h3 className="text-xl font-semibold text-text-secondary mb-2">Key Facts</h3>
                <ul className="list-disc list-inside text-gray-300">
                  {Object.entries(summary.facts).map(([key, value]) => (
                    <li key={key}>
                      <strong>{key.replace(/_/g, ' ')}:</strong> {String(value)}
                    </li>
                  ))}
                </ul>
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

        {/* The rest of the component (claim summary, progress, chat) remains the same */}
        {/* ... */}
      </div>
    </div>
  );
}