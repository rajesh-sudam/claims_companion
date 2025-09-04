import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface AuthContextType {
  isAuthenticated: boolean;
  user: { id: string; email: string; first_name?: string; last_name?: string; phone?: string; role: string } | null;
  login: (email: string, token: string, userId: string, role: string) => void;
  logout: () => void;
  isLoading: boolean; // Added loading state
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<AuthContextType['user'] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true); // Initialize as true

  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    const storedEmail = localStorage.getItem('email');
    const storedUserId = localStorage.getItem('userId');
    const storedUserRole = localStorage.getItem('userRole');
    if (token && storedEmail && storedUserId && storedUserRole) {
      setIsAuthenticated(true);
      setUser({ id: storedUserId, email: storedEmail, role: storedUserRole });
      console.log('AuthContext: Initializing user state from localStorage with role:', storedUserRole);
    }
    setIsLoading(false); // Set to false after initialization
  }, []);

  const login = (email: string, token: string, userId: string, role: string) => {
    localStorage.setItem('jwt_token', token);
    localStorage.setItem('email', email);
    localStorage.setItem('userId', userId);
    localStorage.setItem('userRole', role);
    setIsAuthenticated(true);
    setUser({ id: userId, email: email, role: role });
    console.log('User logged in:', email);
  };

  const logout = () => {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('email');
    localStorage.removeItem('userId');
    localStorage.removeItem('userRole');
    setIsAuthenticated(false);
    setUser(null);
    console.log('User logged out');
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, isLoading }}>
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
