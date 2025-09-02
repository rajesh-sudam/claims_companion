import { useRouter } from "next/router";
import { useEffect } from "react";

export default function EmployeeAuthPage() {
  const router = useRouter();

  useEffect(() => {
    // if you already have a shared login page, just route admins there
    router.replace("/login?role=admin");
  }, [router]);

  return <p>Redirecting to admin login…</p>;
}
