// lightweight fetch helpers for JWT-based calls
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:4000";

export function authHeader() {
  const token = (typeof window !== "undefined") ? localStorage.getItem("token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function postJSON<T>(path: string, body: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { ...authHeader() } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
