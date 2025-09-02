import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import Link from "next/link";

type Metrics = { total: number; by_status: Record<string, number> };

export default function EmployeeDashboard() {
  const [m, setM] = useState<Metrics | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getJSON<Metrics>("/api/admin/metrics").then(setM).catch(e=>setErr(e.message));
  }, []);

  return (
    <main style={{ maxWidth: 1000, margin: "30px auto", fontFamily: "sans-serif" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Claims Dashboard</h1>
        <nav style={{ display: "flex", gap: 10 }}>
          <Link href="/employee/claims">Queue</Link>
        </nav>
      </header>

      {err && <div style={{ color: "crimson" }}>{err}</div>}
      {!m ? <p>Loading metrics…</p> : (
        <section style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: 20 }}>
          <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
            <h3>Total Claims</h3>
            <div style={{ fontSize: 32, fontWeight: 700 }}>{m.total}</div>
          </div>
          {Object.entries(m.by_status).map(([k,v]) => (
            <div key={k} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
              <h3>{k}</h3>
              <div style={{ fontSize: 28, fontWeight: 700 }}>{v}</div>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
