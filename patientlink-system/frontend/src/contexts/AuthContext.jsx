import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => {
  return useContext(AuthContext);
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const storedUser = localStorage.getItem('user');
    return storedUser ? JSON.parse(storedUser) : null;
  });
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return !!localStorage.getItem('token');
  });
  const [refreshToken, setRefreshToken] = useState(localStorage.getItem('refresh_token'));

  // API base URL
  const API_BASE_URL = import.meta.env.VITE_AUTH_API_URL || '/api';

  // Check if user is authenticated on initial load
  // Trust localStorage - if token exists, user is logged in
  useEffect(() => {
    const token = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    
    if (token && storedUser) {
      // Token exists - restore session from localStorage
      setToken(token);
      setUser(JSON.parse(storedUser));
      setIsAuthenticated(true);
    }
  }, []);

  const verifyToken = async (token) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/verify-token/`,
        {}, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      if (response.data.valid) {
        setUser(response.data.user);
        setIsAuthenticated(true);
      } else {
        logout();
      }
    } catch (error) {
      console.error('Token verification failed:', error);
      logout();
    }
  };

  const login = async (username, password, otp = '') => {
    try {
      const response = await axios.post(`${API_BASE_URL}/login/`, {
        username,
        password,
        otp
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      const { tokens, user } = response.data;
      const accessToken = tokens.access;
      const newRefresh = tokens.refresh;
      
      localStorage.setItem('token', accessToken);
      if (newRefresh) localStorage.setItem('refresh_token', newRefresh);
      localStorage.setItem('user', JSON.stringify(user));
      setToken(accessToken);
      setRefreshToken(newRefresh || null);
      setUser(user);
      setIsAuthenticated(true);
      
      return { success: true };
    } catch (error) {
      console.error('Login failed:', error);
      return { 
        success: false, 
        error: error.response?.data || 'Login failed' 
      };
    }
  };

  const signup = async (username, password, clinicName) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/signup/`, {
        username,
        password,
        clinic_name: clinicName
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      const { tokens, user } = response.data;
      const accessToken = tokens.access;
      const newRefresh = tokens.refresh;
      
      localStorage.setItem('token', accessToken);
      if (newRefresh) localStorage.setItem('refresh_token', newRefresh);
      localStorage.setItem('user', JSON.stringify(user));
      setToken(accessToken);
      setRefreshToken(newRefresh || null);
      setUser(user);
      setIsAuthenticated(true);
      
      return { success: true };
    } catch (error) {
      console.error('Signup failed:', error);
      return { 
        success: false, 
        error: error.response?.data || 'Signup failed' 
      };
    }
  };

  const refreshAccessToken = async () => {
    try {
      const storedRefresh = localStorage.getItem('refresh_token');
      if (!storedRefresh) return null;
      const response = await axios.post(`${API_BASE_URL}/refresh/`, {
        refresh: storedRefresh
      });
      const newAccess = response.data.access;
      const newRefresh = response.data.refresh;
      if (newAccess) {
        localStorage.setItem('token', newAccess);
        setToken(newAccess);
        if (newRefresh) {
          localStorage.setItem('refresh_token', newRefresh);
          setRefreshToken(newRefresh);
        }
        return newAccess;
      }
      return null;
    } catch (error) {
      logout();
      return null;
    }
  };

  const logout = () => {
    const storedRefresh = localStorage.getItem('refresh_token');
    if (storedRefresh) {
      axios.post(`${API_BASE_URL}/logout/`, { refresh: storedRefresh }, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      }).catch(() => {});
    }
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    setIsAuthenticated(false);
  };

  const value = {
    user,
    token,
    isAuthenticated,
    refreshToken,
    login,
    signup,
    logout,
    refreshAccessToken
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
