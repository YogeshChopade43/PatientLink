import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster, toast } from 'react-hot-toast';
import axios from 'axios';

const API_URL = import.meta.env.VITE_PATIENT_API_URL || '/patients';

const AddPatient = () => {
  const [formData, setFormData] = useState({
    name: '',
    whatsapp_number: '',
    dob: ''
  });
  const [medicines, setMedicines] = useState([
    {
      id: 1,
      medicine_name: '',
      morning: false,
      evening: false,
      night: false,
      duration_days: 7,
      meal_time: ''
    }
  ]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  const handleChange = (e) => {
    if (e.target.name === 'whatsapp_number') {
      const digitsOnly = e.target.value.replace(/[^\d+]/g, '');
      setFormData({ ...formData, whatsapp_number: digitsOnly });
      return;
    }
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleMedicineChange = (id, field, value) => {
    setMedicines(medicines.map(med => 
      med.id === id ? { ...med, [field]: value } : med
    ));
  };

  const addMedicine = () => {
    setMedicines([
      ...medicines,
      {
        id: Date.now(),
        medicine_name: '',
        morning: false,
        evening: false,
        night: false,
        duration_days: 7,
        meal_time: ''
      }
    ]);
  };

  const removeMedicine = (id) => {
    if (medicines.length > 1) {
      setMedicines(medicines.filter(med => med.id !== id));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      toast.error('Please enter patient name');
      return;
    }

    if (!formData.whatsapp_number.trim()) {
      toast.error('Please enter WhatsApp number');
      return;
    }
    if (formData.dob && new Date(formData.dob) > new Date()) {
      toast.error('Date of birth cannot be in the future');
      return;
    }

    const validMedicines = medicines.filter(med => med.medicine_name.trim());
    
    if (validMedicines.length === 0) {
      toast.error('Please add at least one medicine');
      return;
    }

    const hasMedicineWithNoTime = validMedicines.some(
      (med) => !med.morning && !med.evening && !med.night
    );
    if (hasMedicineWithNoTime) {
      toast.error('Please select at least one time for each medicine');
      return;
    }

    setLoading(true);

    try {
      const payload = {
        name: formData.name,
        whatsapp_number: formData.whatsapp_number,
        dob: formData.dob,
        medicines: validMedicines.map(med => ({
          medicine_name: med.medicine_name,
          morning: med.morning,
          evening: med.evening,
          night: med.night,
          duration_days: parseInt(med.duration_days) || 7,
          meal_time: med.meal_time || ''
        }))
      };

      await axios.post(`${API_URL}/`, payload, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success('Patient added successfully! 🎉', {
        duration: 3000,
        icon: '✅'
      });

      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (error) {
      console.error('Error creating patient:', error);
      toast.error(error.response?.data?.detail || 'Failed to add patient');
    } finally {
      setLoading(false);
    }
  };

  // Animation variants
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.08 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  };

  const floatVariants = {
    initial: { y: 0 },
    animate: {
      y: [0, -15, 0],
      transition: {
        duration: 4,
        repeat: Infinity,
        ease: 'easeInOut'
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50 py-8 px-4">
      {/* Background decorations */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <motion.div
          variants={floatVariants}
          initial="initial"
          animate="animate"
          className="absolute -top-10 -left-10 w-72 h-72 bg-rose-200/20 rounded-full blur-3xl"
        />
        <motion.div
          variants={floatVariants}
          initial="initial"
          animate="animate"
          style={{ animationDelay: '1s' }}
          className="absolute top-1/2 -right-10 w-60 h-60 bg-teal-200/20 rounded-full blur-3xl"
        />
        <motion.div
          variants={floatVariants}
          initial="initial"
          animate="animate"
          style={{ animationDelay: '2s' }}
          className="absolute -bottom-10 left-1/3 w-80 h-80 bg-amber-200/20 rounded-full blur-3xl"
        />
      </div>

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

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="max-w-3xl mx-auto relative"
      >
        {/* Header */}
        <motion.div variants={itemVariants} className="mb-8">
          <Link
            to="/dashboard"
            className="inline-flex items-center space-x-2 text-gray-600 hover:text-rose-600 transition-colors mb-4"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            <span>Back to Dashboard</span>
          </Link>

          <div className="flex items-center space-x-4">
            <div className="w-14 h-14 bg-gradient-to-br from-rose-500 to-rose-600 rounded-2xl flex items-center justify-center shadow-lg shadow-rose-500/30">
              <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-800">Add New Patient</h1>
              <p className="text-gray-500">Enter patient details and medicines</p>
            </div>
          </div>
        </motion.div>

        {/* Form */}
        <motion.form
          variants={itemVariants}
          onSubmit={handleSubmit}
          className="bg-white rounded-3xl shadow-xl border border-gray-100 overflow-hidden"
        >
          {/* Patient Details Section */}
          <div className="p-8 border-b border-gray-100">
            <h2 className="text-xl font-semibold text-gray-800 mb-6 flex items-center space-x-2">
              <svg className="w-5 h-5 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              <span>Patient Information</span>
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Name */}
              <div className="space-y-2">
                <label htmlFor="name" className="text-sm font-semibold text-gray-700">
                  Patient Name <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <input
                    id="name"
                    name="name"
                    type="text"
                    value={formData.name}
                    onChange={handleChange}
                    className="input-field pl-12"
                    placeholder="Enter patient full name"
                    required
                  />
                </div>
              </div>

              {/* WhatsApp Number */}
              <div className="space-y-2">
                <label htmlFor="whatsapp_number" className="text-sm font-semibold text-gray-700">
                  WhatsApp Number <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                    </svg>
                  </div>
                  <input
                    id="whatsapp_number"
                    name="whatsapp_number"
                    type="tel"
                    value={formData.whatsapp_number}
                    onChange={handleChange}
                    className="input-field pl-12"
                    placeholder="+91 9876543210"
                    pattern="^\+?[0-9]{10,15}$"
                    required
                  />
                </div>
              </div>

              {/* Date of Birth */}
              <div className="space-y-2 md:col-span-2">
                <label htmlFor="dob" className="text-sm font-semibold text-gray-700">
                  Date of Birth
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <input
                    id="dob"
                    name="dob"
                    type="date"
                    value={formData.dob}
                    onChange={handleChange}
                    className="input-field pl-12"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Medicines Section */}
          <div className="p-8 bg-gray-50/50">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-800 flex items-center space-x-2">
                <svg className="w-5 h-5 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
                <span>Medicines</span>
              </h2>

              <motion.button
                type="button"
                onClick={addMedicine}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center space-x-2 text-teal-600 hover:text-teal-700 font-medium"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                <span>Add Medicine</span>
              </motion.button>
            </div>

            <AnimatePresence mode="popLayout">
              {medicines.map((medicine, index) => (
                <motion.div
                  key={medicine.id}
                  layout
                  initial={{ opacity: 0, y: 20, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -20, scale: 0.95 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 20 }}
                  className="bg-white rounded-2xl p-6 mb-4 shadow-sm border border-gray-100"
                >
                  <div className="flex items-start justify-between mb-4">
                    <span className="text-sm font-semibold text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
                      Medicine #{index + 1}
                    </span>
                    {medicines.length > 1 && (
                      <motion.button
                        type="button"
                        onClick={() => removeMedicine(medicine.id)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </motion.button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Medicine Name */}
                    <div className="lg:col-span-2 space-y-2">
                      <label className="text-sm font-semibold text-gray-700">
                        Medicine Name <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={medicine.medicine_name}
                        onChange={(e) => handleMedicineChange(medicine.id, 'medicine_name', e.target.value)}
                        className="input-field"
                        placeholder="e.g., Paracetamol 500mg"
                      />
                    </div>

                    {/* Duration */}
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-gray-700">
                        Duration (days)
                      </label>
                      <input
                        type="number"
                        min="1"
                        value={medicine.duration_days}
                        onChange={(e) => handleMedicineChange(medicine.id, 'duration_days', e.target.value)}
                        className="input-field"
                      />
                    </div>

                    {/* Meal Time */}
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-gray-700">
                        When to take
                      </label>
                      <select
                        value={medicine.meal_time}
                        onChange={(e) => handleMedicineChange(medicine.id, 'meal_time', e.target.value)}
                        className="input-field"
                      >
                        <option value="">Any time</option>
                        <option value="before_meal">🍽️ Before meal</option>
                        <option value="after_meal">🍽️ After meal</option>
                      </select>
                    </div>

                    {/* Time Selection */}
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-gray-700">
                        Time <span className="text-rose-500">*</span>
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <motion.label
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          className={`flex items-center space-x-2 px-3 py-2 rounded-xl cursor-pointer transition-all ${
                            medicine.morning
                              ? 'bg-amber-100 text-amber-700 border-2 border-amber-300'
                              : 'bg-gray-100 text-gray-600 border-2 border-transparent hover:bg-gray-200'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={medicine.morning}
                            onChange={(e) => handleMedicineChange(medicine.id, 'morning', e.target.checked)}
                            className="sr-only"
                          />
                          <span className="text-sm font-medium">🌅 Morning</span>
                        </motion.label>

                        <motion.label
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          className={`flex items-center space-x-2 px-3 py-2 rounded-xl cursor-pointer transition-all ${
                            medicine.evening
                              ? 'bg-orange-100 text-orange-700 border-2 border-orange-300'
                              : 'bg-gray-100 text-gray-600 border-2 border-transparent hover:bg-gray-200'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={medicine.evening}
                            onChange={(e) => handleMedicineChange(medicine.id, 'evening', e.target.checked)}
                            className="sr-only"
                          />
                          <span className="text-sm font-medium">☀️ Evening</span>
                        </motion.label>

                        <motion.label
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          className={`flex items-center space-x-2 px-3 py-2 rounded-xl cursor-pointer transition-all ${
                            medicine.night
                              ? 'bg-indigo-100 text-indigo-700 border-2 border-indigo-300'
                              : 'bg-gray-100 text-gray-600 border-2 border-transparent hover:bg-gray-200'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={medicine.night}
                            onChange={(e) => handleMedicineChange(medicine.id, 'night', e.target.checked)}
                            className="sr-only"
                          />
                          <span className="text-sm font-medium">🌙 Night</span>
                        </motion.label>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          {/* Submit Button */}
          <div className="p-8 border-t border-gray-100">
            <div className="flex space-x-4">
              <Link to="/dashboard" className="flex-1">
                <motion.button
                  type="button"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full py-4 bg-gray-100 text-gray-700 rounded-2xl font-semibold hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </motion.button>
              </Link>

              <motion.button
                type="submit"
                disabled={loading}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex-1 flex items-center justify-center space-x-2 bg-gradient-to-r from-rose-500 to-rose-600 text-white py-4 rounded-2xl font-semibold shadow-lg shadow-rose-500/30 hover:shadow-rose-500/50 transition-all disabled:opacity-70"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Save Patient</span>
                  </>
                )}
              </motion.button>
            </div>
          </div>
        </motion.form>
      </motion.div>
    </div>
  );
};

export default AddPatient;
