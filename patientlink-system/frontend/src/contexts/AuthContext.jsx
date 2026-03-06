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

  const login = async (username, password) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/login/`, {
        username,
        password
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      const { tokens, user } = response.data;
      const accessToken = tokens.access;
      
      localStorage.setItem('token', accessToken);
      localStorage.setItem('user', JSON.stringify(user));
      setToken(accessToken);
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
      
      localStorage.setItem('token', accessToken);
      localStorage.setItem('user', JSON.stringify(user));
      setToken(accessToken);
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

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
  };

  const value = {
    user,
    token,
    isAuthenticated,
    login,
    signup,
    logout
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
