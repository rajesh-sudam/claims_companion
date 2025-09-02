import type { AppProps } from "next/app";
// import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import '@/styles/globals.css';
import { AuthProvider } from '@/contexts/AuthContext';

// const client = new QueryClient();

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <AuthProvider>
      <Component {...pageProps} />
    </AuthProvider>
  );
}
