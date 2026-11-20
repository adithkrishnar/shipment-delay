import React, { createContext, useContext, useState, useEffect } from 'react';
import { login as apiLogin, register as apiRegister, getMe } from '../services/api';

const AuthContext = createContext(null);

const getStoredToken = () => {
  try {
    return sessionStorage.getItem('token') || localStorage.getItem('token') || null;
  } catch (e) {
    return null;
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    try {
      const stored = sessionStorage.getItem('user') || localStorage.getItem('user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [token, setToken] = useState(getStoredToken());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const activeToken = getStoredToken();
      if (activeToken) {
        try {
          const userData = await getMe();
          setUser(userData);
        } catch (error) {
          console.error("Failed to restore session", error);
          setToken(null);
          sessionStorage.removeItem('token');
          sessionStorage.removeItem('user');
          localStorage.removeItem('token');
          localStorage.removeItem('user');
        }
      }
      setLoading(false);
    };
    initAuth();
  }, [token]);

  const login = async (email, password) => {
    try {
      const data = await apiLogin(email, password);
      setToken(data.access_token);
      sessionStorage.setItem('token', data.access_token);
      localStorage.setItem('token', data.access_token);
      
      const userData = await getMe();
      setUser(userData);
      sessionStorage.setItem('user', JSON.stringify(userData));
      localStorage.setItem('user', JSON.stringify(userData));
      return { success: true, user: userData };
    } catch (error) {
      let errorMsg = "Login failed";
      if (!error.response) {
        errorMsg = "Unable to reach server. Please check network connection or API URL.";
      } else if (error.response.status === 401) {
        errorMsg = "Incorrect email or password.";
      } else if (error.response.status === 403) {
        errorMsg = "Access forbidden. CORS or authorization check failed.";
      } else if (error.response.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          errorMsg = error.response.data.detail.map(d => d.msg).join(', ');
        } else {
          errorMsg = error.response.data.detail;
        }
      }
      return { success: false, error: errorMsg };
    }
  };

  const register = async (email, password, companyName) => {
    try {
      const data = await apiRegister(email, password, companyName);
      setToken(data.access_token);
      sessionStorage.setItem('token', data.access_token);
      localStorage.setItem('token', data.access_token);
      
      const userData = await getMe();
      setUser(userData);
      sessionStorage.setItem('user', JSON.stringify(userData));
      localStorage.setItem('user', JSON.stringify(userData));
      return { success: true, user: userData };
    } catch (error) {
      let errorMsg = "Registration failed";
      if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          errorMsg = error.response.data.detail.map(d => d.msg).join(', ');
        } else {
          errorMsg = error.response.data.detail;
        }
      }
      return { success: false, error: errorMsg };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('user');
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  };

  const value = {
    user,
    token,
    isAuthenticated: !!user,
    loading,
    login,
    register,
    logout
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
