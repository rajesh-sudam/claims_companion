import { useRouter } from 'next/router';
import { useAuth } from '@/contexts/AuthContext';
import { useEffect, useState } from 'react';
import api from '@/utils/api';
import io from 'socket.io-client';
import { ChangeEvent } from 'react';
import LoginPage from '../login';

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
  attachment_url?: string | null;   // new field for attachments
  attachment_name?: string | null;
}

interface TypingEvent {
  from: string;
}

export default function ClaimDetailPage() {
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


  // Fetch claim and progress
  useEffect(() => {
    if (!id) return;
    const fetchData = async () => {
      try {
        const [claimRes, progressRes, historyRes] = await Promise.all([
          api.get(`/claims/${id}`),
          api.get(`/claims/${id}/progress`),
          api.get(`/chat/${id}/history`),
        ]);
        setClaim(claimRes.data.claim);
        setProgress(progressRes.data.progress);
        setMessages(historyRes.data.history);
      } catch (err: any) {
        setError(err.response?.data?.error || 'Failed to load claim');
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
      // Join claim-specific room
      s.emit('join_claim', id);
    });
    // Listen for incoming messages
    s.on('chat_message', (msg: ChatMessage) => {
      setMessages((prev) => [...prev, msg]);
      // Clear typing indicator when message received from ai
      setTyping(null);
    });
    // Listen for typing indicator
    s.on('typing', (evt: TypingEvent) => {
      setTyping(evt);
    });
    // Listen for claim updates
    s.on('claim_updated', (updated: any) => {
      // Update claim status and fetch latest progress
      setClaim((prev) => prev ? { ...prev, status: updated.status, incident_description: updated.incident_description, estimated_completion: updated.estimated_completion } : prev);
      // Optionally fetch progress again
      api.get(`/claims/${id}/progress`).then((res) => setProgress(res.data.progress));
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
    try {
      const formData = new FormData();
      formData.append('message_text', newMessage);
      if (file) {
        formData.append('file', file);
      }
      const res = await api.post(`/chat/${id}/messages`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const msg = res.data.message as ChatMessage;
      setMessages((prev) => [...prev, msg]);
      setNewMessage('');
      setFile(null);
    } catch (err) {
      console.error(err);
    }
  };

  const handleEscalate = async () => {
    try {
      await api.post(`/chat/${id}/escalate`);
    } catch (err) {
      console.error(err);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };


  if (loading) return <p className="p-6">Loading claim...</p>;
  if (error) return <p className="p-6 text-red-500">{error}</p>;
  if (!claim) return null;

  return (
    <div className="min-h-screen p-6 space-y-6"> 
    <button onClick={() => router.api(LoginPage)} className="text-blue-600 hover:underline">Logout</button>
      <h1 className="text-3xl font-bold">Claim {claim.claim_number}</h1>
      {/* Claim summary */}
        <div className="bg-white p-4 rounded shadow">
          <h2 className="text-xl font-semibold mb-2">Summary</h2>
          <p><strong>Type:</strong> {claim.claim_type}</p>
          <p><strong>Status:</strong> {claim.status.replace(/_/g, ' ')}</p>
          {claim.incident_date && <p><strong>Incident Date:</strong> {new Date(claim.incident_date).toLocaleDateString()}</p>}
          {claim.estimated_completion && <p><strong>Estimated Completion:</strong> {new Date(claim.estimated_completion).toLocaleDateString()}</p>}
        </div>
        {/* Progress timeline */}
        <div className="bg-white p-4 rounded shadow">
          <h2 className="text-xl font-semibold mb-2">Progress</h2>
          <ol className="relative border-l border-gray-200">{
            progress.map((step) => (
              <li key={step.id} className="mb-6 ml-6">
                <span
                  className={`absolute -left-3 flex items-center justify-center w-6 h-6 rounded-full ${step.status === 'completed' ? 'bg-green-500' : step.status === 'active' ? 'bg-blue-500' : 'bg-gray-300'}`}
                >
                  &nbsp;
                </span>
                <h3 className="font-semibold leading-tight">{step.step_title}</h3>
                <p className="text-sm text-gray-600">{step.description}</p>
                {step.completed_at && (
                  <time className="block text-xs text-gray-500">{new Date(step.completed_at).toLocaleString()}</time>
                )}
              </li>
            ))
          }</ol>
        </div>
      {/* ... claim summary, progress */}
      <div className="bg-white p-4 rounded shadow max-w-2xl">
        <h2 className="text-xl font-semibold mb-2">Chat with Claims Assistant</h2>
        <div className="h-64 overflow-y-auto border border-gray-200 p-3 mb-3 rounded">
          {messages.map((msg) => (
            <div key={msg.id} className={`mb-2 flex ${msg.message_type === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`rounded px-3 py-2 max-w-xs ${msg.message_type === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-900'}`}>
                {msg.attachment_url ? (
                  <div className="mb-2">
                    {msg.attachment_url.match(/\.(jpg|jpeg|png|gif)$/i) ? (
                      <img src={msg.attachment_url} alt={msg.attachment_name || 'attachment'} className="max-w-full rounded" />
                    ) : (
                      <a href={msg.attachment_url} target="_blank" rel="noopener noreferrer" className="underline text-blue-700">
                        {msg.attachment_name || 'View attachment'}
                      </a>
                    )}
                  </div>
                ) : null}
                {msg.message_text && <p className="text-sm whitespace-pre-wrap">{msg.message_text}</p>}
                <p className="text-xs text-gray-400 text-right">{new Date(msg.created_at).toLocaleTimeString()}</p>
              </div>
            </div>
          ))}
        </div>
        {typing && (
          <p className="text-sm text-gray-500 mb-2">
            {typing.from === 'ai' ? 'Claims Assistant is typing...' : ''}
          </p>
        )}
        <div className="flex space-x-2 items-center">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 border border-gray-300 p-2 rounded"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
          />
          <input
            type="file"
            onChange={handleFileChange}
            className="hidden"
            id="chat-file-upload"
          />
          <label
            htmlFor="chat-file-upload"
            className="cursor-pointer px-3 py-2 bg-gray-100 rounded border border-gray-300 text-sm"
          >
            📎
          </label>
          <button
            onClick={sendMessage}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Send
          </button>
        </div>
        {file && (
          <p className="text-xs text-gray-500 mt-1">Selected: {file.name}</p>
        )}
        <button
          onClick={handleEscalate}
          className="mt-3 text-sm text-purple-600 underline"
        >
          Escalate to human agent
        </button>
      </div>
    </div>
  );
}