import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster, toast } from 'react-hot-toast';
import axios from 'axios';

const API_URL = import.meta.env.VITE_PATIENT_API_URL || '/patients';
const AUTH_API_URL = import.meta.env.VITE_AUTH_API_URL || '/api';

const Dashboard = () => {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingPatient, setEditingPatient] = useState(null);
  const [expandedPatient, setExpandedPatient] = useState(null);
  const [editForm, setEditForm] = useState({
    name: '',
    whatsapp_number: '',
    dob: '',
    medicines: []
  });
  const [editMedicines, setEditMedicines] = useState([]);
  const [users, setUsers] = useState([]);
  const [showUserManager, setShowUserManager] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const navigate = useNavigate();
  const token = localStorage.getItem('token');
  const currentUser = JSON.parse(localStorage.getItem('user') || 'null');

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }
    fetchPatients();
  }, [token, navigate]);

  const fetchPatients = async () => {
    try {
      const response = await axios.get(`${API_URL}/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPatients(response.data);
    } catch (error) {
      console.error('Error fetching patients:', error);
      if (error.response?.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this patient?')) return;
    
    try {
      await axios.delete(`${API_URL}/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPatients(patients.filter(p => p.id !== id));
      toast.success('Patient deleted successfully!');
    } catch (error) {
      toast.error('Failed to delete patient');
    }
  };

  const handleExportCSV = async () => {
    try {
      const response = await axios.get(`${API_URL}/export/csv`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `patients_export_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('Export successful!');
    } catch (error) {
      toast.error('Failed to export data');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const handleOpenUserManager = async () => {
    setShowUserManager(true);
    setLoadingUsers(true);
    try {
      const response = await axios.get(`${AUTH_API_URL}/users/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUsers(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to load users');
      setShowUserManager(false);
    } finally {
      setLoadingUsers(false);
    }
  };

  const handleDeleteUser = async (userId, username) => {
    if (!window.confirm(`Delete account "${username}"?`)) return;

    try {
      await axios.delete(`${AUTH_API_URL}/users/${userId}/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      toast.success('User account deleted');
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to delete user account');
    }
  };

  const handleEditClick = (patient) => {
    setEditingPatient(patient);
    setEditForm({
      name: patient.name,
      whatsapp_number: patient.whatsapp_number,
      dob: patient.dob || '',
      medicines: patient.medicines || []
    });
    setEditMedicines(patient.medicines?.map((med, idx) => ({
      id: med.id || idx,
      medicine_name: med.medicine_name,
      morning: med.morning,
      evening: med.evening,
      night: med.night,
      duration_days: med.duration_days,
      meal_time: med.meal_time || ''
    })) || []);
  };

  const handleEditMedicineChange = (id, field, value) => {
    setEditMedicines(editMedicines.map(med => 
      med.id === id ? { ...med, [field]: value } : med
    ));
  };

  const addEditMedicine = () => {
    setEditMedicines([
      ...editMedicines,
      {
        id: Date.now(),
        medicine_name: '',
        morning: false,
        evening: false,
        night: false,
        duration_days: 7
      }
    ]);
  };

  const removeEditMedicine = (id) => {
    if (editMedicines.length > 1) {
      setEditMedicines(editMedicines.filter(med => med.id !== id));
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    
    const validMedicines = editMedicines.filter(med => med.medicine_name.trim());
    
    try {
      const payload = {
        name: editForm.name,
        whatsapp_number: editForm.whatsapp_number,
        dob: editForm.dob,
        medicines: validMedicines.map(med => ({
          medicine_name: med.medicine_name,
          morning: med.morning,
          evening: med.evening,
          night: med.night,
          duration_days: parseInt(med.duration_days) || 7,
          meal_time: med.meal_time || ''
        }))
      };

      await axios.put(`${API_URL}/${editingPatient.id}`, payload, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success('Patient updated successfully!');
      setEditingPatient(null);
      fetchPatients();
    } catch (error) {
      toast.error('Failed to update patient');
    }
  };

  const filteredPatients = patients.filter(patient =>
    patient.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    patient.whatsapp_number.includes(searchTerm)
  );

  // Animation variants
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.05 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 },
    exit: { opacity: 0, x: -100 }
  };

  const getInitials = (name) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center"
        >
          <div className="w-16 h-16 border-4 border-rose-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 font-medium">Loading patients...</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <Toaster 
        position="top-center"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#fff',
            color: '#333',
            boxShadow: '0 10px 40px rgba(0,0,0,0.1)',
          },
        }}
      />

      {/* Header */}
      <motion.header 
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        className="bg-white/80 backdrop-blur-lg shadow-sm sticky top-0 z-50"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <motion.div 
              whileHover={{ scale: 1.05 }}
              className="flex items-center space-x-3"
            >
              <div className="w-10 h-10 bg-gradient-to-br from-rose-500 to-rose-600 rounded-xl flex items-center justify-center shadow-lg shadow-rose-500/30">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                </svg>
              </div>
              <span className="text-xl font-bold bg-gradient-to-r from-rose-600 to-rose-400 bg-clip-text text-transparent">
                PatientLink
              </span>
            </motion.div>

            {/* Actions */}
            <div className="flex items-center space-x-3">
              {currentUser?.is_superuser && (
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleOpenUserManager}
                  className="flex items-center space-x-2 bg-indigo-500 text-white px-4 py-2.5 rounded-xl font-medium shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-all"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2m0 2H7m0 0H2v-2a3 3 0 015.356-1.857M7 20v-2m10-8a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0zm8-3a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="hidden sm:inline">Manage Accounts</span>
                </motion.button>
              )}

              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleExportCSV}
                className="flex items-center space-x-2 bg-teal-500 text-white px-4 py-2.5 rounded-xl font-medium shadow-lg shadow-teal-500/30 hover:shadow-teal-500/50 transition-all"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span className="hidden sm:inline">Export</span>
              </motion.button>

              <Link to="/add-patient">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="flex items-center space-x-2 bg-gradient-to-r from-rose-500 to-rose-600 text-white px-5 py-2.5 rounded-xl font-medium shadow-lg shadow-rose-500/30 hover:shadow-rose-500/50 transition-all"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  <span>Add Patient</span>
                </motion.button>
              </Link>

              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleLogout}
                className="flex items-center space-x-2 bg-gray-100 text-gray-600 px-4 py-2.5 rounded-xl font-medium hover:bg-gray-200 transition-all"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span className="hidden sm:inline">Logout</span>
              </motion.button>
            </div>
          </div>
        </div>
      </motion.header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats & Search */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Stats Cards */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm">Total Patients</p>
                <p className="text-3xl font-bold text-gray-800 mt-1">{patients.length}</p>
              </div>
              <div className="w-14 h-14 bg-rose-100 rounded-2xl flex items-center justify-center">
                <svg className="w-7 h-7 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm">With Medicines</p>
                <p className="text-3xl font-bold text-gray-800 mt-1">
                  {patients.filter(p => p.medicines?.length > 0).length}
                </p>
              </div>
              <div className="w-14 h-14 bg-teal-100 rounded-2xl flex items-center justify-center">
                <svg className="w-7 h-7 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm">Today's Entries</p>
                <p className="text-3xl font-bold text-gray-800 mt-1">
                  {patients.filter(p => {
                    const today = new Date().toISOString().split('T')[0];
                    return p.created_at?.startsWith(today);
                  }).length}
                </p>
              </div>
              <div className="w-14 h-14 bg-amber-100 rounded-2xl flex items-center justify-center">
                <svg className="w-7 h-7 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Search Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mb-8"
        >
          <div className="relative max-w-xl">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              placeholder="Search patients by name or WhatsApp..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all shadow-sm"
            />
          </div>
        </motion.div>

        {/* Patients Grid */}
        <AnimatePresence mode="popLayout">
          {filteredPatients.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-center py-20"
            >
              <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-12 h-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">
                {searchTerm ? 'No patients found' : 'No patients yet'}
              </h3>
              <p className="text-gray-500 mb-6">
                {searchTerm ? 'Try adjusting your search' : 'Add your first patient to get started'}
              </p>
              {!searchTerm && (
                <Link to="/add-patient">
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    className="inline-flex items-center space-x-2 bg-gradient-to-r from-rose-500 to-rose-600 text-white px-6 py-3 rounded-xl font-medium shadow-lg shadow-rose-500/30"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                    <span>Add Patient</span>
                  </motion.button>
                </Link>
              )}
            </motion.div>
          ) : (
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="space-y-2"
            >
              {filteredPatients.map((patient) => (
                <motion.div
                  key={patient.id}
                  variants={itemVariants}
                  layout
                  className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden"
                >
                  {/* Main Row - Clickable */}
                  <div 
                    className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => setExpandedPatient(expandedPatient === patient.id ? null : patient.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3 flex-1 min-w-0">
                        <motion.div
                          animate={{ rotate: expandedPatient === patient.id ? 180 : 0 }}
                          className="text-gray-400"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </motion.div>
                        <div className="w-9 h-9 bg-gradient-to-br from-rose-100 to-rose-200 rounded-lg flex items-center justify-center flex-shrink-0">
                          <span className="text-sm font-bold text-rose-700">
                            {getInitials(patient.name)}
                          </span>
                        </div>
                        <div className="min-w-0 flex-1">
                          <h3 className="text-sm font-semibold text-gray-800 truncate">{patient.name}</h3>
                          <p className="text-xs text-gray-500">{patient.whatsapp_number}</p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 flex-shrink-0">
                        {patient.medicines?.length > 0 ? (
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-teal-100 text-teal-700">
                            {patient.medicines.length}
                          </span>
                        ) : null}
                        <span className="text-xs text-gray-400">{formatDate(patient.dob)}</span>
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={(e) => { e.stopPropagation(); handleEditClick(patient); }}
                          className="p-1.5 text-gray-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </motion.button>
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={(e) => { e.stopPropagation(); handleDelete(patient.id); }}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </motion.button>
                      </div>
                    </div>
                  </div>

                  {/* Dropdown Details */}
                  <AnimatePresence>
                    {expandedPatient === patient.id && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="border-t border-gray-100 bg-gray-50"
                      >
                        <div className="p-4 space-y-3">
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                              <span className="text-gray-500">Full Name:</span>
                              <p className="font-medium text-gray-800">{patient.name}</p>
                            </div>
                            <div>
                              <span className="text-gray-500">WhatsApp:</span>
                              <p className="font-medium text-gray-800">{patient.whatsapp_number}</p>
                            </div>
                            <div>
                              <span className="text-gray-500">Date of Birth:</span>
                              <p className="font-medium text-gray-800">{formatDate(patient.dob)}</p>
                            </div>
                            <div>
                              <span className="text-gray-500">Entered At:</span>
                              <p className="font-medium text-gray-800">{formatDateTime(patient.created_at)}</p>
                            </div>
                          </div>
                          
                          {patient.medicines?.length > 0 && (
                            <div>
                              <span className="text-gray-500 text-sm">Medicines:</span>
                              <div className="mt-2 space-y-2">
                                {patient.medicines.map((med, idx) => (
                                  <div key={idx} className="bg-white rounded-lg p-3 border border-gray-200">
                                    <div className="flex items-center justify-between">
                                      <span className="font-medium text-gray-800">{med.medicine_name}</span>
                                      <span className="text-xs text-gray-500">{med.duration_days} days</span>
                                    </div>
                                    <div className="flex flex-wrap gap-2 mt-1">
                                      {med.morning && <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">Morning</span>}
                                      {med.evening && <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">Evening</span>}
                                      {med.night && <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">Night</span>}
                                      {med.meal_time === 'before_meal' && (
                                        <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded">Before meal</span>
                                      )}
                                      {med.meal_time === 'after_meal' && (
                                        <span className="text-xs bg-cyan-100 text-cyan-700 px-2 py-0.5 rounded">After meal</span>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* User Manager Modal */}
      <AnimatePresence>
        {showUserManager && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowUserManager(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-2xl font-bold text-gray-800">User Accounts</h2>
                  <button
                    type="button"
                    onClick={() => setShowUserManager(false)}
                    className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-xl transition-all"
                  >
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {loadingUsers ? (
                  <p className="text-gray-500">Loading users...</p>
                ) : (
                  <div className="space-y-3">
                    {users.map((u) => (
                      <div key={u.id} className="flex items-center justify-between p-3 rounded-xl border border-gray-200 bg-gray-50">
                        <div>
                          <p className="font-semibold text-gray-800">{u.username}</p>
                          <p className="text-sm text-gray-500">{u.clinic_name || 'No clinic name'}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          {u.id === currentUser?.id && (
                            <span className="text-xs px-2 py-1 rounded-full bg-indigo-100 text-indigo-700">You</span>
                          )}
                          <button
                            type="button"
                            disabled={u.id === currentUser?.id}
                            onClick={() => handleDeleteUser(u.id, u.username)}
                            className="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    ))}
                    {users.length === 0 && <p className="text-gray-500">No users found.</p>}
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Edit Patient Modal */}
      <AnimatePresence>
        {editingPatient && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
            onClick={() => setEditingPatient(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <form onSubmit={handleEditSubmit} className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-2xl font-bold text-gray-800">Edit Patient</h2>
                  <button
                    type="button"
                    onClick={() => setEditingPatient(null)}
                    className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-xl transition-all"
                  >
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="space-y-4 mb-6">
                  {/* Name */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-1">Patient Name</label>
                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      className="input-field"
                      required
                    />
                  </div>

                  {/* WhatsApp */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-1">WhatsApp Number</label>
                    <input
                      type="tel"
                      value={editForm.whatsapp_number}
                      onChange={(e) => setEditForm({ ...editForm, whatsapp_number: e.target.value })}
                      className="input-field"
                      required
                    />
                  </div>

                  {/* DOB */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-1">Date of Birth</label>
                    <input
                      type="date"
                      value={editForm.dob}
                      onChange={(e) => setEditForm({ ...editForm, dob: e.target.value })}
                      className="input-field"
                    />
                  </div>

                  {/* Medicines */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <label className="block text-sm font-semibold text-gray-700">Medicines</label>
                      <button
                        type="button"
                        onClick={addEditMedicine}
                        className="text-sm text-teal-600 hover:text-teal-700 font-medium"
                      >
                        + Add Medicine
                      </button>
                    </div>
                    <div className="space-y-3">
                      {editMedicines.map((medicine, index) => (
                        <div key={medicine.id} className="bg-gray-50 rounded-2xl p-4">
                          <div className="flex items-start justify-between mb-2">
                            <span className="text-xs font-semibold text-gray-500 bg-gray-200 px-2 py-1 rounded-full">
                              Medicine #{index + 1}
                            </span>
                            {editMedicines.length > 1 && (
                              <button
                                type="button"
                                onClick={() => removeEditMedicine(medicine.id)}
                                className="text-red-500 hover:text-red-600"
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            )}
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <input
                              type="text"
                              placeholder="Medicine name"
                              value={medicine.medicine_name}
                              onChange={(e) => handleEditMedicineChange(medicine.id, 'medicine_name', e.target.value)}
                              className="input-field"
                            />
                            <input
                              type="number"
                              min="1"
                              placeholder="Duration (days)"
                              value={medicine.duration_days}
                              onChange={(e) => handleEditMedicineChange(medicine.id, 'duration_days', e.target.value)}
                              className="input-field"
                            />
                          </div>
                          <div className="flex flex-wrap gap-2 mt-2">
                            {['morning', 'evening', 'night'].map((time) => (
                              <label
                                key={time}
                                className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg cursor-pointer transition-all ${
                                  medicine[time]
                                    ? time === 'morning' ? 'bg-amber-100 text-amber-700 border-2 border-amber-300'
                                    : time === 'evening' ? 'bg-orange-100 text-orange-700 border-2 border-orange-300'
                                    : 'bg-indigo-100 text-indigo-700 border-2 border-indigo-300'
                                    : 'bg-gray-100 text-gray-600 border-2 border-transparent'
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={medicine[time]}
                                  onChange={(e) => handleEditMedicineChange(medicine.id, time, e.target.checked)}
                                  className="sr-only"
                                />
                                <span className="text-sm font-medium capitalize">{time}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex space-x-3">
                  <button
                    type="button"
                    onClick={() => setEditingPatient(null)}
                    className="flex-1 py-3 bg-gray-100 text-gray-700 rounded-xl font-semibold hover:bg-gray-200 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-3 bg-gradient-to-r from-rose-500 to-rose-600 text-white rounded-xl font-semibold shadow-lg shadow-rose-500/30 hover:shadow-rose-500/50 transition-all"
                  >
                    Save Changes
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Dashboard;
