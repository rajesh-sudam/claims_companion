import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface AuthContextType {
  isAuthenticated: boolean;
  user: { id: string; email: string; first_name?: string; last_name?: string; phone?: string; role: string } | null; // Updated user type
  login: (email: string, token: string, userId: string) => void; // Changed username to email
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<AuthContextType['user'] | null>(null); // Use the updated type

  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    const storedEmail = localStorage.getItem('email'); // Changed to email
    const storedUserId = localStorage.getItem('userId');
    if (token && storedEmail && storedUserId) {
      setIsAuthenticated(true);
      // Reconstruct user object from stored data, assuming we only stored email and id
      setUser({ id: storedUserId, email: storedEmail, role: 'user' }); // Default role to 'user' or fetch full user data
    }
  }, []);

  const login = (email: string, token: string, userId: string) => { // Changed username to email
    localStorage.setItem('jwt_token', token);
    localStorage.setItem('email', email); // Changed to email
    localStorage.setItem('userId', userId);
    setIsAuthenticated(true);
    setUser({ id: userId, email: email, role: 'user' }); // Store minimal user data, or fetch full user data
    console.log('User logged in:', email);
  };

  const logout = () => {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('email'); // Changed to email
    localStorage.removeItem('userId');
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