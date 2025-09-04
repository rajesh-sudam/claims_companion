import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import io from 'socket.io-client';
import { ChangeEvent } from 'react';
import api from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';

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
    s.on('chat_message', (msg: ChatMessage) => {
      setMessages((prev: ChatMessage[]) => {
        // Avoid duplicating optimistic message
        if (prev.find((m) => m.id === msg.id)) {
          return prev;
        }
        return [...prev, msg];
      });
      setTyping(null);
    });
    s.on('typing', (evt: TypingEvent) => {
      setTyping(evt);
    });
    s.on('claim_updated', (updated: any) => {
      setClaim((prev) => prev ? { ...prev, status: updated.status, incident_description: updated.incident_description, estimated_completion: updated.estimated_completion } : prev);
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
      id: Date.now(), // Temporary ID for optimistic update
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
      // The AI's response will be added via the socket event
    } catch (err) {
      console.error(err);
      // Optionally, show an error message to the user and remove the optimistic message
      setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
    }
  };

  const handleEscalate = async () => {
    try {
      await api.post(`/chat/${id}/escalate`);
    } catch (err) {
      console.error(err);
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      // Automatically upload the file
      try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        await api.post(`/claims/${id}/documents`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        // The backend will emit a 'claim_updated' event, which will trigger a re-fetch of the progress
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
      
        <h1 className="text-4xl font-extrabold text-text-secondary mb-8 text-center">Claim {claim.claim_number}</h1>

        {/* Claim summary */}
        <div className="glassy-card p-10 rounded-lg shadow-lg">
          <h2 className="text-xl font-semibold mb-2">Summary</h2>
          <p><strong>Type:</strong> {claim.claim_type}</p>
          <p><strong>Status:</strong> {claim.status.replace(/_/g, ' ')}</p>
          {claim.incident_date && <p><strong>Incident Date:</strong> {new Date(claim.incident_date).toLocaleDateString()}</p>}
          {claim.estimated_completion && <p><strong>Estimated Completion:</strong> {new Date(claim.estimated_completion).toLocaleDateString()}</p>}
        </div>
        {/* Progress timeline */}
        <div className="glassy-card p-10 rounded-lg shadow-lg">
          <h2 className="text-2xl font-semibold mb-4 text-text-secondary">Progress</h2>
          <ol className="relative border-l border-gray-700">{
            progress.map((step) => (
              <li key={step.id} className="mb-6 ml-6">
                <span
                  className={`absolute -left-3 flex items-center justify-center w-6 h-6 rounded-full text-white ${step.status === 'completed' ? 'bg-purple-500' : step.status === 'active' ? 'bg-pink-500' : 'bg-gray-500'}`}
                >
                  {step.status === 'completed' ? '✓' : '\u00A0'}
                </span>
                <h3 className="font-semibold leading-tight text-text-secondary">{step.step_title}</h3>
                <p className="text-sm text-gray-400">{step.description}</p>
                {step.completed_at && (
                  <time className="block text-xs text-gray-500">{new Date(step.completed_at).toLocaleString()}</time>
                )}
              </li>
            ))
          }</ol>
        </div>
        {/* ... claim summary, progress */}
        <div className="glassy-card p-10 rounded-lg shadow-lg max-w-2xl">
          <h2 className="text-2xl font-semibold mb-4 text-text-secondary">Chat with Claims Assistant</h2>
          <div className="h-64 overflow-y-auto border border-gray-700 p-3 mb-3 rounded">
            {messages.map((msg) => (
                            <div key={msg.id}>
                            {msg.message_type === 'ai_request_documents' ? (
                              <div className="flex justify-center my-4">
                                <div className="bg-gray-700 text-text-primary rounded px-4 py-3 max-w-md text-center shadow-lg">
                                  <p className="text-sm whitespace-pre-wrap mb-3">{msg.message_text}</p>
                                  <label
                                    htmlFor="chat-file-upload"
                                    className="cursor-pointer mt-2 inline-block bg-primary text-text-primary px-4 py-2 rounded hover:bg-accent-hover font-semibold"
                                  >
                                    Upload Documents
                                  </label>
                                </div>
                              </div>
                            ) : (
                              <div className={`mb-2 flex ${msg.message_type === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`rounded px-3 py-2 max-w-xs ${msg.message_type === 'user' ? 'bg-primary text-white' : 'bg-gray-700 text-text-primary'}`}>
                                  {msg.attachment_url ? (
                                    <div className="mb-2">
                                      {msg.attachment_url.match(/\.(jpg|jpeg|png|gif)$/i) ? (
                                        <img src={msg.attachment_url} alt={msg.attachment_name || 'attachment'} className="max-w-full rounded" />
                                      ) : (
                                        <a href={msg.attachment_url} target="_blank" rel="noopener noreferrer" className="underline text-blue-400">
                                          {msg.attachment_name || 'View attachment'}
                                        </a>
                                      )}
                                    </div>
                                  ) : null}
                                  {msg.message_text && <p className="text-sm whitespace-pre-wrap">{msg.message_text}</p>}
                                  <p className="text-xs text-gray-400 text-right">{new Date(msg.created_at).toLocaleTimeString()}</p>
                                </div>
                              </div>
                            )}
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
              className="flex-1 border border-gray-600 p-2 rounded bg-background text-text-secondary"
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
              className="cursor-pointer px-3 py-2 bg-gray-800 rounded border border-gray-600 text-sm text-text-secondary"
            >
              📎
            </label>
            <button
              onClick={sendMessage}
              className="bg-accent text-text-primary px-4 py-2 rounded hover:bg-accent-hover"
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
    </div>
  );
}