import React, { createContext, useContext, useState, useEffect } from 'react';
import { login as apiLogin, register as apiRegister, getMe } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token') || null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        try {
          const userData = await getMe();
          setUser(userData);
        } catch (error) {
          console.error("Failed to restore session", error);
          setToken(null);
          localStorage.removeItem('token');
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
      localStorage.setItem('token', data.access_token);
      
      const userData = await getMe();
      setUser(userData);
      return { success: true };
    } catch (error) {
      let errorMsg = "Login failed";
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

  const register = async (email, password, companyName) => {
    try {
      const data = await apiRegister(email, password, companyName);
      setToken(data.access_token);
      localStorage.setItem('token', data.access_token);
      
      const userData = await getMe();
      setUser(userData);
      return { success: true };
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
    localStorage.removeItem('token');
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
