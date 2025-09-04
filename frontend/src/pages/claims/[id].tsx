import { useRouter } from 'next/router';
import { useEffect, useState, useRef, ChangeEvent } from 'react';
import io from 'socket.io-client';
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
  validation_progress?: number; // % from claim_updated
  validation_status?: string;   // short string from claim_updated
  manual_review_required?: boolean;
}

interface ProgressStep {
  id: number;
  step_id: string;
  step_title: string;
  status: string; // completed | active | pending
  completed_at: string | null;
  description: string | null;
}

type DocDetail = { file_name: string; file_url: string };

type ValidationItemDetails = {
  is_valid?: boolean;
  issues?: string[];
  suggestions?: string[];
  confidence?: number;
};

type ValidationItem = {
  key: string;
  title: string;
  required: boolean;
  state: string; // ok | missing | invalid | needs_review | needs_verification
  confidence?: number;
  doc_type?: string | null;
  evidence?: string[];
  validation_details?: Record<string, ValidationItemDetails>;
};

type ValidationSummary = {
  total_items: number;
  completed_items: number;
  missing_items: number;
  invalid_items: number;
  review_items: number;
  completion_rate: number; // might be 0-100 or 0-1; we normalize
};

type ValidationStatusPayload = {
  items?: ValidationItem[];
  progress?: number;                 // overall %
  overall_confidence?: number;       // optional
  decision_hint?: string;
  next_prompt?: string;
  claim_type?: string;
  validation_summary?: ValidationSummary;
};

interface ChatMessage {
  id: number;
  message_type: string; // 'user' | 'ai' | 'ai_request_documents' | ...
  message_text: string;
  created_at: string;
  attachment_url?: string | null;
  attachment_name?: string | null;

  // NEW: emitted by backend on AI responses
  validation_status?: ValidationStatusPayload;
  sources?: Array<{
    id?: string;
    doc_id?: string;
    chunk_id?: string;
    score?: number;
    snippet?: string;
  }>;
}

interface TypingEvent {
  from: string;
}

// helpers
const normState = (s?: string) => (s ?? '').toLowerCase().replace(/[-\s]/g, '_');
const pct = (n?: number) => (typeof n === 'number' ? `${Math.round(n)}%` : '—');
const safeRate = (r?: number) => {
  if (typeof r !== 'number') return '—';
  return r <= 1 ? `${Math.round(r * 100)}%` : `${Math.round(r)}%`;
};

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
  const [isAiReplying, setIsAiReplying] = useState(false);
  const [showSlowResponseWarning, setShowSlowResponseWarning] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [file, setFile] = useState<File | null>(null);

  // NEW: immediate next_step from POST response
  const [nextStepBanner, setNextStepBanner] = useState<string | null>(null);

  // NEW: filename -> url index (filled from claim_updated if backend includes documents)
  const [docIndex, setDocIndex] = useState<Record<string, string>>({});

  // Fetch claim, progress, history
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

  // Initialize socket.io
  useEffect(() => {
    if (!id) return;
    const s = io((process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api').replace(/\/api$/, ''));
    setSocket(s);

    s.on('connect', () => {
      s.emit('join_claim', id);
    });

    s.on('chat_message', (msg: ChatMessage) => {
      setMessages((prev) => {
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

      if (msg.message_type.startsWith('ai')) {
        if (timerRef.current) clearTimeout(timerRef.current);
        setShowSlowResponseWarning(false);
        setIsAiReplying(false);
      }
      setTyping(null);
    });

    s.on('typing', (evt: TypingEvent) => setTyping(evt));

    // Accept optional documents array to map evidence links
    s.on('claim_updated', (data: { claim: Partial<ClaimDetail>; progress: ProgressStep[]; documents?: DocDetail[] }) => {
      setClaim((prev) => (prev ? { ...prev, ...data.claim } : null));
      setProgress(data.progress);
      if (Array.isArray(data.documents)) {
        const idx: Record<string, string> = {};
        data.documents.forEach((d) => {
          idx[d.file_name] = d.file_url;
        });
        setDocIndex(idx);
      }
    });

    return () => {
      if (s) {
        s.emit('leave_claim', id);
        s.disconnect();
      }
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [id]);

  const sendMessage = async () => {
    if (!newMessage.trim() && !file) return;

    setIsAiReplying(true);
    timerRef.current = setTimeout(() => setShowSlowResponseWarning(true), 120000); // 2 min

    const userMessage: ChatMessage = {
      id: 'temp-' + Date.now(), // Temporary ID for optimistic update
      message_type: 'user',
      message_text: newMessage,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setNextStepBanner(null);
    const localFile = file;
    setNewMessage('');
    setFile(null);

    try {
      const formData = new FormData();
      formData.append('message_text', newMessage);
      if (localFile) formData.append('file', localFile);

      // IMPORTANT: use POST response to show immediate next_step
      const res = await api.post(`/chat/${id}/messages`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      const nextStep = res?.data?.next_step as string | undefined;
      if (nextStep) setNextStepBanner(nextStep);
      // AI response arrives via socket
    } catch (err) {
      console.error(err);
      if (timerRef.current) clearTimeout(timerRef.current);
      setShowSlowResponseWarning(false);
      setIsAiReplying(false);
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
      try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        await api.post(`/claims/${id}/documents`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        // claim_updated socket will update progress and (optionally) documents map
      } catch (err) {
        console.error(err);
      }
    }
  };

  // pick the latest AI message that contains validation_status for banners
  const lastAiWithVS = [...messages].reverse().find((m) => m.message_type !== 'user' && m.validation_status);
  const vs = lastAiWithVS?.validation_status;

  if (loading) return <p className="p-6">Loading claim...</p>;
  if (error) return <p className="p-6 text-red-500">{error}</p>;
  if (!claim) return null;

  return (
    <div className="min-h-screen bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-6">

        <h1 className="text-4xl font-extrabold text-text-secondary mb-8 text-center">
          Claim {claim.claim_number}
        </h1>

        {/* Claim summary */}
        <div className="glassy-card p-8 rounded-xl shadow-lg">
          <h2 className="text-2xl font-bold text-white mb-6">Claim Summary</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="flex items-center gap-4">
              <div className="bg-gray-800/50 p-3 rounded-lg">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" /></svg>
              </div>
              <div>
                <p className="text-sm text-gray-400">Claim Type</p>
                <p className="font-semibold text-white capitalize">{claim.claim_type}</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="bg-gray-800/50 p-3 rounded-lg">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
              </div>
              <div>
                <p className="text-sm text-gray-400">Incident Date</p>
                <p className="font-semibold text-white">
                  {claim.incident_date ? new Date(claim.incident_date).toLocaleDateString() : 'N/A'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="bg-gray-800/50 p-3 rounded-lg">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10h6c2 0 2.5-1.5 2.5-1.5S18 8 17.657 7.343A8 8 0 006.343 18.657zM9.5 12.5l-2.5 2.5" /></svg>
              </div>
              <div>
                <p className="text-sm text-gray-400">Status</p>
                <p className="font-semibold text-white capitalize">{claim.status.replace(/_/g, ' ')}</p>
                {/* NEW: show claim-level validation */}
                {typeof claim.validation_progress === 'number' && (
                  <p className="text-xs text-gray-400">
                    Validation: {claim.validation_status ?? 'pending'} ({claim.validation_progress}%)
                  </p>
                )}
                {claim.manual_review_required && (
                  <p className="text-xs text-yellow-300 mt-1">Escalated to human review</p>
                )}
              </div>
            </div>

{claim.estimated_completion && (
  <div className="flex items-center gap-4">
    <div className="bg-gray-800/50 p-3 rounded-lg">
      <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
    </div>
    <div>
      <p className="text-sm text-gray-400">Est. Completion</p>
      <p className="font-semibold text-white">{new Date(claim.estimated_completion).toLocaleDateString()}</p>
    </div>
  </div>
)}
{claim?.manual_review_required && (
  <div className="mb-3 rounded-md border border-emerald-400/40 bg-emerald-500/10 text-emerald-200 text-xs px-2 py-1">
      Sent to human verification
  </div>
)}
          </div>
        </div>

        {/* Progress timeline */}
        <div className="glassy-card p-8 rounded-xl shadow-lg">
          <h2 className="text-2xl font-bold text-white mb-6">Claim Progress</h2>
          <ol className="relative border-l-2 border-purple-500/30">
            {progress.map((step) => (
              <li key={step.id} className="mb-8 ml-8">
                <span
                  className={`absolute -left-4 flex items-center justify-center w-8 h-8 rounded-full ring-8 ring-gray-900/50 ${
                    step.status === 'completed'
                      ? 'bg-green-500'
                      : step.status === 'active'
                      ? 'bg-blue-500 animate-pulse'
                      : 'bg-gray-600'
                  }`}
                >
                  {step.status === 'completed' ? (
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                  ) : (
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                  )}
                </span>
                <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700/50 ml-4">
                  <h3 className="text-lg font-semibold text-white">{step.step_title}</h3>
                  <p className="text-sm text-gray-400 mt-1">{step.description}</p>
                  {step.completed_at && (
                    <time className="block mt-2 text-xs font-medium text-purple-400">
                      {new Date(step.completed_at).toLocaleString()}
                    </time>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>

        {/* Chat */}
        <div className="glassy-card p-10 rounded-lg shadow-lg max-w-2xl">
          <h2 className="text-2xl font-semibold mb-4 text-text-secondary">Chat with Claims Assistant</h2>

          {/* Top-of-chat banners from the most recent validation_status */}
          <div className="mb-3 space-y-2">
            {vs?.decision_hint && (
              <div className="inline-flex items-center gap-2 px-2 py-1 rounded border border-purple-500/40 bg-purple-500/10 text-purple-200 text-xs">
                {vs.decision_hint.replace(/_/g, ' ')}
                {typeof vs.progress === 'number' && <span className="ml-2 opacity-80">({pct(vs.progress)})</span>}
                {typeof vs.overall_confidence === 'number' && (
                  <span className="ml-2 opacity-80">AI conf: {vs.overall_confidence.toFixed(2)}</span>
                )}
              </div>
            )}
            {vs?.validation_summary && (
              <div className="text-xs text-gray-300">
                {vs.validation_summary.completed_items}/{vs.validation_summary.total_items} complete •{' '}
                {vs.validation_summary.review_items} need review •{' '}
                {vs.validation_summary.missing_items} missing •{' '}
                completion {safeRate(vs.validation_summary.completion_rate)}
              </div>
            )}
            {nextStepBanner && (
              <div className="rounded-md border border-blue-400/40 bg-blue-500/10 text-blue-200 text-xs px-2 py-1">
                Next: {nextStepBanner}
              </div>
            )}
          </div>

          <div className="h-96 overflow-y-auto bg-gray-900/50 p-4 rounded-lg space-y-4">
            {messages.map((msg) => (
              <div key={msg.id}>
                {msg.message_type === 'ai_request_documents' ? (
                  <div className="flex items-end gap-2 justify-start">
                    <div className="w-8 h-8 rounded-full bg-purple-500 flex-shrink-0"></div>
                    <div className="rounded-xl px-4 py-3 max-w-md shadow bg-gray-700 text-text-primary rounded-bl-none">
                      <p className="text-sm whitespace-pre-wrap mb-3">{msg.message_text}</p>
                      <label
                        htmlFor="chat-file-upload"
                        className="cursor-pointer mt-2 inline-block bg-primary text-text-primary px-4 py-2 rounded-lg hover:bg-accent-hover font-semibold transition-colors"
                      >
                        Upload Document
                      </label>
                    </div>
                  </div>
                ) : (
                  <div className={`flex items-end gap-2 ${msg.message_type === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {msg.message_type !== 'user' && <div className="w-8 h-8 rounded-full bg-purple-500 flex-shrink-0"></div>}
                    <div className={`rounded-xl px-4 py-2 max-w-md shadow ${msg.message_type === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-gray-700 text-text-primary rounded-bl-none'}`}>

                      {/* Attachment preview */}
                      {msg.attachment_url && (
                        <div className="mb-2">
                          {/\.(jpg|jpeg|png|gif)$/i.test(msg.attachment_url) ? (
                            <img src={msg.attachment_url} alt={msg.attachment_name || 'attachment'} className="max-w-full rounded-lg" />
                          ) : (
                            <a href={msg.attachment_url} target="_blank" rel="noopener noreferrer" className="underline text-blue-300 hover:text-blue-200">
                              {msg.attachment_name || 'View attachment'}
                            </a>
                          )}
                        </div>
                      )}

                      {/* Badge when needs_review present */}
                      {msg.message_type !== 'user' &&
                        msg.validation_status?.items?.some((i) => normState(i.state) === 'needs_review') && (
                          <span className="inline-block mb-2 px-2 py-0.5 text-[10px] rounded bg-amber-500/20 text-amber-200 border border-amber-400/40">
                            Needs review
                          </span>
                        )
                      }

                      {/* AI/user text */}
                      {msg.message_text && <p className="text-sm whitespace-pre-wrap">{msg.message_text}</p>}

                      {/* Detailed validation rendering for AI messages */}
                      {msg.message_type !== 'user' && msg.validation_status?.items && (() => {
                        // De-dupe noisy items from backend by key+title+doc_type
                        const seen = new Set<string>();
                        const items = msg.validation_status!.items!.filter((i) => {
                          const k = `${i.key}::${i.title}::${i.doc_type ?? ''}`;
                          if (seen.has(k)) return false;
                          seen.add(k);
                          return true;
                        });

                        const section = (filterFn: (i: ValidationItem) => boolean, title: string, boxClass: string) => {
                          const group = items.filter(filterFn);
                          if (group.length === 0) return null;
                          return (
                            <div className={`mt-3 rounded-md border p-3 ${boxClass}`}>
                              <div className="font-medium">{title}</div>
                              <ul className="list-disc ml-5 mt-1 space-y-1">
                                {group.map((i) => {
                                  const details = i.validation_details ? Object.values(i.validation_details)[0] : undefined;
                                  const issues = details?.issues ?? [];
                                  const suggestions = details?.suggestions ?? [];
                                  const conf = typeof i.confidence === 'number' ? i.confidence : details?.confidence;

                                  return (
                                    <li key={`${i.key}-${i.title}`} className="text-sm">
                                      <span className="font-semibold">{i.title}</span>
                                      {typeof conf === 'number' && (
                                        <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-200 border border-gray-700">
                                          conf: {conf.toFixed(2)}
                                        </span>
                                      )}
                                      {/* Evidence links */}
                                      {Array.isArray(i.evidence) && i.evidence.length > 0 && (
                                        <span className="block text-xs text-blue-200 mt-1">
                                          Evidence:{' '}
                                          {i.evidence.map((fname, idx) => {
                                            const url = docIndex[fname];
                                            return url ? (
                                              <a key={idx} href={url} className="underline hover:text-blue-100 mr-2" target="_blank" rel="noreferrer">
                                                {fname}
                                              </a>
                                            ) : (
                                              <span key={idx} className="mr-2">{fname}</span>
                                            );
                                          })}
                                        </span>
                                      )}
                                      {issues.length > 0 && (
                                        <ul className="list-disc ml-5 mt-1 text-xs text-amber-200">
                                          {issues.map((issue, idx) => <li key={idx}>{issue}</li>)}
                                        </ul>
                                      )}
                                      {suggestions.length > 0 && (
                                        <div className="mt-2 text-xs text-emerald-200">
                                          <div className="font-medium">Suggested fixes</div>
                                          <ul className="list-disc ml-5">
                                            {suggestions.map((s, idx) => <li key={idx}>{s}</li>)}
                                          </ul>
                                        </div>
                                      )}
                                      {/* Upload button helper for missing/review with doc_type */}
                                      {i.doc_type && (normState(i.state) === 'missing' || normState(i.state) === 'needs_review') && (
                                        <label htmlFor="chat-file-upload" className="inline-block mt-2 text-xs cursor-pointer px-2 py-1 rounded border border-gray-600 bg-gray-800 text-gray-200 hover:bg-gray-700">
                                          Upload {i.doc_type.replace(/_/g, ' ')}
                                        </label>
                                      )}
                                    </li>
                                  );
                                })}
                              </ul>
                              {/* next_prompt per message if provided */}
                              {msg.validation_status?.next_prompt && (
                                <p className="mt-2 text-xs opacity-80">Next: {msg.validation_status.next_prompt}</p>
                              )}
                            </div>
                          );
                        };

                        return (
                          <>
                            {section((i) => normState(i.state) === 'needs_review', 'Items needing review', 'border-amber-300 bg-amber-50/10 text-amber-100')}
                            {section((i) => normState(i.state) === 'missing' && !i.required, 'Optional items missing', 'border-gray-600 bg-gray-800/40 text-gray-100')}
                            {section((i) => normState(i.state) === 'invalid', 'Items marked invalid', 'border-red-400 bg-red-500/10 text-red-100')}
                          </>
                        );
                      })()}

                      {/* Sources (RAG) if any */}
                      {msg.sources && msg.sources.length > 0 && (
                        <details className="mt-2 text-xs">
                          <summary className="cursor-pointer text-blue-200">References</summary>
                          <ul className="ml-4 mt-1 list-disc">
                            {msg.sources.map((s, idx) => (
                              <li key={idx} className="opacity-80">
                                {s.snippet || `${s.doc_id ?? ''}#${s.chunk_id ?? ''}`} {typeof s.score === 'number' ? `(score: ${s.score.toFixed(2)})` : ''}
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}

                      <p className="text-xs text-gray-400 text-right mt-1">{new Date(msg.created_at).toLocaleTimeString()}</p>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {isAiReplying && !showSlowResponseWarning && (
              <div className="flex items-end gap-2 justify-start">
                <div className="w-8 h-8 rounded-full bg-purple-500 flex-shrink-0"></div>
                <div className="rounded-xl px-4 py-2 max-w-xs bg-gray-700 text-text-primary rounded-bl-none shadow">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse"></div>
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse [animation-delay:0.2s]"></div>
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse [animation-delay:0.4s]"></div>
                  </div>
                </div>
              </div>
            )}

            {showSlowResponseWarning && (
              <div className="flex justify-center my-2">
                <div className="rounded-lg px-3 py-2 max-w-xs bg-yellow-900/50 border border-yellow-700 text-yellow-200 text-center">
                  <p className="text-xs">Hang on tight, I'm just an MVP and my circuits are warming up!</p>
                </div>
              </div>
            )}
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
            <input type="file" onChange={handleFileChange} className="hidden" id="chat-file-upload" />
            <label htmlFor="chat-file-upload" className="cursor-pointer px-3 py-2 bg-gray-800 rounded border border-gray-600 text-sm text-text-secondary">
              📎
            </label>
            <button onClick={sendMessage} className="bg-accent text-text-primary px-4 py-2 rounded hover:bg-accent-hover">
              Send
            </button>
          </div>

          {file && <p className="text-xs text-gray-500 mt-1">Selected: {file.name}</p>}

          <button onClick={handleEscalate} className="mt-3 text-sm text-purple-600 underline">
            Escalate to human agent
          </button>
        </div>
      </div>
    </div>
  );
}

