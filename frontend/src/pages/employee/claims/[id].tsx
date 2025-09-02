import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { getJSON, postJSON } from "@/lib/api";

type Claim = {
  id: number;
  claim_number: string;
  status: string;
  claim_type: string;
  incident_description: string;
  created_at: string;
  user_id: number;
  ai_summary: string;
};

export default function ClaimDetailPage() {
  const router = useRouter();
  const { id } = router.query;
  const [c, setC] = useState<Claim | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    getJSON<Claim>(`/api/admin/claims/${id}`).then(setC).catch(e=>setErr(e.message));
  }, [id]);

  async function decide(decision: "approve" | "reject" | "needs_info") {
    if (!id) return;
    setBusy(true);
    try {
      await postJSON(`/api/admin/claims/${id}/decision`, { decision });
      // refresh
      const fresh = await getJSON<Claim>(`/api/admin/claims/${id}`);
      setC(fresh);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (err) return <main style={{maxWidth:900,margin:"30px auto"}}><p style={{color:"crimson"}}>{err}</p></main>;
  if (!c) return <main style={{maxWidth:900,margin:"30px auto"}}><p>Loading…</p></main>;

  return (
    <main style={{ maxWidth: 900, margin: "30px auto", fontFamily: "sans-serif" }}>
      <h1>Claim {c.claim_number}</h1>
      <p><b>Status:</b> {c.status}</p>
      <p><b>Type:</b> {c.claim_type}</p>
      <p><b>Created:</b> {new Date(c.created_at).toLocaleString()}</p>

      <section style={{ marginTop: 20 }}>
        <h3>Incident Description</h3>
        <p style={{ whiteSpace: "pre-wrap" }}>{c.incident_description}</p>
      </section>

      <section style={{ marginTop: 20 }}>
        <h3>AI Summary</h3>
        <div style={{ background: "#f8f8f8", padding: 12, borderRadius: 8 }}>
          {c.ai_summary}
        </div>
      </section>

      <section style={{ marginTop: 20, display: "flex", gap: 8 }}>
        <button disabled={busy} onClick={() => decide("approve")}>Approve</button>
        <button disabled={busy} onClick={() => decide("reject")}>Reject</button>
        <button disabled={busy} onClick={() => decide("needs_info")}>Needs Info</button>
      </section>
    </main>
  );
}
