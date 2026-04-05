import axios from 'axios';

// Replace with your actual Flask backend URL
const API_BASE_URL = 'http://127.0.0.1:5000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const addPatientSymptoms = async (patientData) => {
  try {
    const response = await apiClient.post('/add_patient', patientData);
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};

export const getQueueData = async () => {
  try {
    const response = await apiClient.get('/queue');
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};

export const completePatient = async (patientId, adviceText) => {
  try {
    // Send the advice (prescription) as JSON in the body of the POST request
    const response = await apiClient.post(`/complete_patient/${patientId}`, { 
      advice: adviceText 
    });
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};

// Check live queue status
export const getPatientStatus = async (patientId) => {
  try {
    const response = await apiClient.get(`/patient_status/${patientId}`);
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};

// Doctor calls the patient
export const callPatient = async (patientId) => {
  try {
    const response = await apiClient.post(`/call_patient/${patientId}`);
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};

// Fetch Patient's Real Medical History
export const getPatientHistory = async (patientId) => {
  try {
    const response = await apiClient.get(`/patient_history/${patientId}`);
    return response.data;
  } catch (error) {
    console.error("Error fetching history", error);
    return []; // Returns empty array if patient has no history yet
  }
};

// Add External Doctor Record
export const addExternalHistory = async (patientId, historyData) => {
  try {
    const response = await apiClient.post(`/add_external_history/${patientId}`, historyData);
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};

export const retrieveExistingPatient = async (phone) => {
  try {
    const response = await apiClient.post('/retrieve_patient', { phone });
    return response.data; // Returns { success: true, patient: {...} }
  } catch (error) {
    throw error.response?.data || { error: "Server connection failed" };
  }
};