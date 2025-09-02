import { useState } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import { postJSON } from "@/lib/api";

type LoginResponse = {
  token: string;
  user: {
    id: number;
    email: string;
    first_name?: string;
    last_name?: string;
    phone?: string;
  };
};

const EMPLOYEE_EMAILS = new Set(["manager@cc.io", "analyst@cc.io"]);

export default function EmployeeLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await postJSON<LoginResponse>("/api/auth/login", {
        email,
        password,
      });

      // Save token and user
      localStorage.setItem("token", res.token);
      localStorage.setItem("user", JSON.stringify(res.user));

      // Check if this is an employee email since role is not in response
      if (EMPLOYEE_EMAILS.has(email)) {
        router.replace("/employee");
      } else {
        setError("This account is not authorized for the employee portal.");
      }
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        "Login failed. Please check your credentials.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <form
        onSubmit={handleSubmit}
        className="bg-white w-full max-w-md p-8 rounded-2xl shadow"
      >
        <h1 className="text-2xl font-semibold mb-2 text-center">
          Employee Portal
        </h1>
        <p className="text-sm text-gray-500 mb-6 text-center">
          Manager & Analyst access
        </p>
        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 text-red-700 text-sm">
            {error}
          </div>
        )}
        <label
          htmlFor="email"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Work Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="manager@cc.io"
          required
        />
        <label
          htmlFor="password"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-6 w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="••••••••"
          required
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-60"
        >
          {loading ? "Signing in..." : "Sign In"}
        </button>
        <div className="mt-6 text-center text-sm text-gray-600">
          Not an employee?{" "}
          <Link href="/login" className="text-blue-600 hover:underline">
            Go to user login
          </Link>
        </div>
      </form>
    </div>
  );
}