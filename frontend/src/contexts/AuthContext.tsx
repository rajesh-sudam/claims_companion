import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface AuthContextType {
  isAuthenticated: boolean;
  user: { name: string } | null;
  login: (username: string, token: string) => void; // Modified to accept token
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ name: string } | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    const storedUsername = localStorage.getItem('username');
    if (token && storedUsername) {
      // In a real app, you would validate the token with your backend
      // For this example, we'll assume presence means valid
      setIsAuthenticated(true);
      setUser({ name: storedUsername });
    }
  }, []);

  const login = (username: string, token: string) => {
    localStorage.setItem('jwt_token', token);
    localStorage.setItem('username', username);
    setIsAuthenticated(true);
    setUser({ name: username });
    console.log('User logged in:', username);
  };

  const logout = () => {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('username');
    setIsAuthenticated(false);
    setUser(null);
    console.log('User logged out');
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};