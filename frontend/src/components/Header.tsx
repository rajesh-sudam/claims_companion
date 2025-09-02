import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/router';

// --- ICONS (included for self-containment) ---

const MenuIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" x2="20" y1="12" y2="12" />
    <line x1="4" x2="20" y1="6" y2="6" />
    <line x1="4" x2="20" y1="18" y2="18" />
  </svg>
);

// --- DATA (included for self-containment) ---

const navLinks = [
  { name: 'Features', href: '#features' },
  { name: 'About', href: '#about' },
  { name: 'Team', href: '#team' },
  { name: 'Testimonials', href: '#testimonials' },
  { name: 'Contact', href: '#contact' },
];

// --- HEADER COMPONENT ---

const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { isAuthenticated, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-secondary/50 backdrop-blur-md border-b border-white/10 shadow-lg">
      <div className="container mx-auto px-6 py-4 flex justify-between items-center">
        <Link href="/" className="text-2xl font-bold text-white">
          Cogni<span className="text-[#8A5EFF]">Claim</span>
        </Link>
        <div>
          <button onClick={() => setIsMenuOpen(!isMenuOpen)}>
            <MenuIcon className="h-6 w-6 text-white" />
          </button>
        </div>
      </div>
      {isMenuOpen && (
        <div className="absolute top-full right-0 w-full md:w-64 glassy-card py-4">
          <nav className="flex flex-col items-center space-y-4">
            {!isAuthenticated && navLinks.map((link) => (
              <Link key={link.name} href={link.href} className="text-[#F0F0F0] hover:text-[#A685FF] transition-colors" onClick={() => setIsMenuOpen(false)}>
                {link.name}
              </Link>
            ))}
            {isAuthenticated && (
              <Link href="/new-claim" className="text-[#F0F0F0] hover:text-[#A685FF] transition-colors" onClick={() => setIsMenuOpen(false)}>
                File a Claim
              </Link>
            )}
            {isAuthenticated && (
              <Link href="/my-claims" className="text-[#F0F0F0] hover:text-[#A685FF] transition-colors" onClick={() => setIsMenuOpen(false)}>
                My Claims
              </Link>
            )}
            {isAuthenticated ? (
              <button onClick={() => { handleLogout(); setIsMenuOpen(false); }} className="text-[#F0F0F0] hover:text-[#A685FF] transition-colors pt-2">
                Logout
              </button>
            ) : (
              <>
                <Link href="/login" className="text-[#F0F0F0] hover:text-[#A685FF] transition-colors pt-2" onClick={() => setIsMenuOpen(false)}>
                    Login
                </Link>
                <Link href="/signup" className="bg-[#8A5EFF] text-white w-3/4 text-center mt-2 py-2 px-6 rounded-lg hover:bg-[#A685FF] transition-colors" onClick={() => setIsMenuOpen(false)}>
                  Sign Up
                </Link>
              </>
            )}
          </nav>
        </div>
      )}
    </header>
  );
};

export default Header;
