import type { AppProps } from "next/app";
import '@/styles/globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import Layout from '@/components/Layout';
import AuthRedirector from '@/components/AuthRedirector';

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <AuthProvider>
      <AuthRedirector />
      <Layout>
        <Component {...pageProps} />
      </Layout>
    </AuthProvider>
  );
}
