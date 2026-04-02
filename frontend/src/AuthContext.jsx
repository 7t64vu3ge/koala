import React, { createContext, useState, useEffect, useContext } from 'react';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('koala_token') || null);
  const [theme, setTheme] = useState(localStorage.getItem('koala_theme') || 'dark');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('koala_theme', theme);
  }, [theme]);

  const fetchUser = async (authToken) => {
    try {
      const res = await fetch('http://localhost:8000/auth/me', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
        if (data.theme) {
          setTheme(data.theme);
        }
      } else {
        logout();
      }
    } catch (err) {
      console.error(err);
      logout();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchUser(token);
    } else {
      setLoading(false);
    }
  }, [token]);

  const login = (newToken) => {
    localStorage.setItem('koala_token', newToken);
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem('koala_token');
    setToken(null);
    setUser(null);
  };

  const updateUserSettings = (updates) => {
    if (updates.theme) setTheme(updates.theme);
    setUser(prev => ({ ...prev, ...updates }));
  };

  return (
    <AuthContext.Provider value={{ user, token, theme, login, logout, updateUserSettings, setTheme, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
