import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API methods
export const uploadPDF = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/api/extract-pdf', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const visualizeCode = async (code) => {
  const response = await api.post('/api/visualize', { code });
  return response.data;
};

export const checkHealth = async () => {
  const response = await api.get('/api/health');
  return response.data;
};

export default api;
