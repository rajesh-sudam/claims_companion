import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@/contexts/AuthContext';

const protectedRoutes = ['/my-claims', '/new-claim'];
const authRoutes = ['/login', '/signup'];

const AuthRedirector = () => {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated && protectedRoutes.includes(router.pathname)) {
      router.push('/login');
    } else if (isAuthenticated && authRoutes.includes(router.pathname)) {
      router.push('/my-claims');
    }
  }, [isAuthenticated, router.pathname, router]);

  return null; // This component doesn't render anything
};

export default AuthRedirector;
