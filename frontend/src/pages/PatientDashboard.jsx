import React, { useContext, useEffect, useState, useCallback } from 'react';
import { AuthContext } from '../context/AuthContext';
import { getPatientStatus, getPatientHistory, addExternalHistory } from '../api';
import PrescriptionSection from '../components/PrescriptionSection';
import HistoryTimeline from '../components/HistoryTimeline';
import { toast } from 'react-toastify';

const PatientDashboard = () => {
  const { patient } = useContext(AuthContext);
  const [liveData, setLiveData] = useState({ position: null, wait_time: 0, status: 'Waiting', advice: null });
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // --- STATE FOR HISTORY ---
  const [patientHistory, setPatientHistory] = useState([]);
  const [showAddRecord, setShowAddRecord] = useState(false);
  const [newRecord, setNewRecord] = useState({ date: '', condition: '', advice: '' });
  const [isSubmittingRecord, setIsSubmittingRecord] = useState(false);

  const patientId = patient?.aiAssessment?.id;

  const fetchStatus = useCallback(async (isManualClick = false) => {
    if (!patientId) return;

    if (isManualClick) setIsRefreshing(true);
    
    try {
      const data = await getPatientStatus(patientId);
      
      if (data && data.status === 'Called' && liveData.status !== 'Called') {
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification("Doctor is ready!", { body: "Please proceed to the doctor's cabin immediately." });
        }
      }
      
      if (data) setLiveData(data);
      if (isManualClick) toast.success("Status updated securely.");
    } catch (error) {
      console.error("Error fetching live status", error);
      if (isManualClick) toast.error("Unable to reach the server.");
    } finally {
      if (isManualClick) setIsRefreshing(false);
    }
  }, [patientId, liveData.status]);

  useEffect(() => {
    if (!patientId) return;

    if ('Notification' in window && Notification.permission !== 'granted' && Notification.permission !== 'denied') {
      Notification.requestPermission();
    }

    // --- FETCH MEDICAL HISTORY ---
    const fetchHistory = async () => {
      try {
        const historyData = await getPatientHistory(patientId);
        setPatientHistory(historyData);
      } catch (error) {
        console.error("Failed to load history", error);
      }
    };
    fetchHistory();
    // ---------------------------

    fetchStatus();
    const interval = setInterval(() => fetchStatus(false), 10000);
    return () => clearInterval(interval);
  }, [fetchStatus, patientId]);

  // Handle adding an external record
  const handleAddExternalRecord = async (e) => {
    e.preventDefault();
    setIsSubmittingRecord(true);
    try {
      await addExternalHistory(patientId, newRecord);
      toast.success("External record added successfully!");
      setShowAddRecord(false);
      setNewRecord({ date: '', condition: '', advice: '' });
      
      // Refresh the history timeline
      const updatedHistory = await getPatientHistory(patientId);
      setPatientHistory(updatedHistory);
    } catch (error) {
      toast.error("Failed to add record.");
    } finally {
      setIsSubmittingRecord(false);
    }
  };


  if (!patient) return null;

  const aiData = patient.aiAssessment || {};
  const condition = aiData.condition || "Pending Assessment";
  const riskLevel = aiData.risk_level || aiData.risk || "Unknown";
  const isHighRisk = String(riskLevel).toLowerCase() === 'high';
  const firstName = patient.name ? String(patient.name).split(' ')[0] : 'Patient';
  const advice = aiData.advice || aiData.reason || "Please await doctor consultation.";

  // --- BMI CALCULATION ---
  const weight = parseFloat(patient.weight) || 0;
  const heightCm = parseFloat(patient.height) || 0;
  let bmi = 0;
  let bmiCategory = "Unknown";
  let bmiRisk = "Unknown";
  let bmiColorClass = "text-gray-500 bg-gray-100 dark:bg-gray-700";

  if (weight > 0 && heightCm > 0) {
    const heightM = heightCm / 100;
    bmi = (weight / (heightM * heightM)).toFixed(1);

    if (bmi < 18.5) {
      bmiCategory = "Underweight";
      bmiRisk = "Moderate Risk";
      bmiColorClass = "text-orange-600 bg-orange-100 dark:bg-orange-900/30 dark:text-orange-400";
    } else if (bmi >= 18.5 && bmi <= 24.9) {
      bmiCategory = "Normal Weight";
      bmiRisk = "Low Risk";
      bmiColorClass = "text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400";
    } else if (bmi >= 25 && bmi <= 29.9) {
      bmiCategory = "Overweight";
      bmiRisk = "Moderate Risk";
      bmiColorClass = "text-orange-600 bg-orange-100 dark:bg-orange-900/30 dark:text-orange-400";
    } else {
      bmiCategory = "Obese";
      bmiRisk = "High Risk";
      bmiColorClass = "text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400";
    }
  }

  return (
    <div className="container mx-auto p-6 md:p-10 max-w-4xl relative">
      
      <div className="absolute top-6 right-6 md:top-10 md:right-10 flex items-center gap-2">
         <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-clinical-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-clinical-500"></span>
         </span>
         <span className="text-sm font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">System Live</span>
      </div>

      <div className="mb-10 mt-4 animate-fade-in-down">
        <h1 className="text-3xl md:text-5xl font-extrabold text-gray-800 dark:text-white tracking-tight mb-3">
          Welcome back, <span className="text-clinical-500">{firstName}</span>!
        </h1>
      </div>

      {liveData.status === 'Called' && (
        <div className="mb-8 p-6 bg-green-500 rounded-3xl shadow-[0_10px_40px_rgba(34,197,94,0.4)] animate-pulse flex items-center justify-center gap-4">
           <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z" /></svg>
           <h2 className="text-2xl md:text-3xl font-black text-white tracking-wider uppercase">Doctor is ready. Please proceed to the cabin!</h2>
        </div>
      )}

      {/* Vitals & Health Index Card */}
      <div className="bg-white dark:bg-gray-800 p-8 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 mb-8 animate-fade-in-up">
        <h2 className="text-xl font-extrabold text-gray-800 dark:text-white mb-6 flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-clinical-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          Patient Vitals & Health Index
        </h2>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-50 dark:bg-gray-900/50 p-4 rounded-2xl">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Weight</p>
            <p className="text-xl font-black text-gray-700 dark:text-white">{weight} <span className="text-sm font-medium">kg</span></p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-900/50 p-4 rounded-2xl">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Height</p>
            <p className="text-xl font-black text-gray-700 dark:text-white">{heightCm} <span className="text-sm font-medium">cm</span></p>
          </div>
          <div className={`p-4 rounded-2xl col-span-2 flex items-center justify-between ${bmiColorClass}`}>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest mb-1 opacity-80">Calculated BMI</p>
              <p className="text-2xl font-black">{bmi > 0 ? bmi : '--'}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-bold uppercase tracking-wider">{bmiCategory}</p>
              <p className="text-xs font-medium opacity-80">{bmiRisk}</p>
            </div>
          </div>
        </div>
      </div>

      {liveData.status !== 'Treated' && liveData.status !== 'Called' && (
        <div className="grid grid-cols-2 gap-6 mb-8 animate-fade-in-up">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm text-center">
            <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Your Position in Queue</p>
            <p className="text-5xl font-black text-clinical-500">
              {liveData.position === null ? '...' : `#${liveData.position}`}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 p-6 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm text-center">
            <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Estimated Wait</p>
            <p className="text-5xl font-black text-orange-500">{liveData.wait_time} <span className="text-xl">min</span></p>
          </div>
        </div>
      )}

      <div className={`p-8 rounded-3xl shadow-sm border-l-4 mb-8 bg-white dark:bg-gray-800 ${isHighRisk ? 'border-l-red-500' : 'border-l-clinical-500'}`}>
        <div className="flex items-center justify-between mb-8">
           <h2 className="text-2xl font-extrabold text-gray-800 dark:text-white">AI Health Indicator</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-gray-50 dark:bg-gray-900/50 p-5 rounded-2xl">
            <p className="text-xs text-gray-500 font-bold mb-1 uppercase tracking-wider">Predicted Condition</p>
            <p className="font-bold text-xl dark:text-white">{condition}</p>
          </div>
          <div className="md:col-span-2 bg-gray-50 dark:bg-gray-900/50 p-5 rounded-2xl">
             <p className="text-xs text-gray-500 font-bold mb-2 uppercase tracking-wider">Preliminary Advice</p>
             <p className="font-medium text-gray-800 dark:text-gray-200">{advice}</p>
          </div>
        </div>
      </div>

      {liveData.status !== 'Called' && (
        <div className="flex justify-center mb-8 animate-fade-in-up">
          <button 
            onClick={() => fetchStatus(true)} 
            disabled={isRefreshing}
            className={`px-6 py-3 font-bold rounded-xl border transition-colors shadow-sm flex items-center gap-2
              ${isRefreshing 
                ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500 border-transparent cursor-not-allowed' 
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700'}`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {isRefreshing ? 'Checking secure connection...' : "Check for Doctor's Prescription"}
          </button>
        </div>
      )}

      {liveData.status === 'Treated' && (
        <PrescriptionSection result={{ ...aiData, status: liveData.status, advice: liveData.advice }} />
      )}

      {/* --- REAL MEDICAL HISTORY SECTION --- */}
      <div className="mt-12 mb-8 animate-fade-in-up">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
          <h2 className="text-2xl font-extrabold text-gray-800 dark:text-white flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-clinical-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Past Medical History
          </h2>
          <button 
            onClick={() => setShowAddRecord(!showAddRecord)}
            className="px-4 py-2 bg-clinical-50 dark:bg-clinical-900/20 text-clinical-600 dark:text-clinical-400 font-bold rounded-lg text-sm border border-clinical-100 dark:border-clinical-800 hover:bg-clinical-100 transition-colors uppercase tracking-wider"
          >
            {showAddRecord ? 'Cancel' : '+ Add External Record'}
          </button>
        </div>

        {/* Dropdown Form for External Records */}
        {showAddRecord && (
          <form onSubmit={handleAddExternalRecord} className="mb-8 p-6 bg-gray-50 dark:bg-gray-800/80 rounded-2xl border border-gray-200 dark:border-gray-700 animate-fade-in-down">
            <h3 className="font-bold text-gray-800 dark:text-white mb-4">Add Checkup from Another Doctor</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Date of Visit</label>
                <input type="date" required value={newRecord.date} onChange={(e) => setNewRecord({...newRecord, date: e.target.value})} className="w-full px-3 py-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white" />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Doctor / Clinic / Condition</label>
                <input type="text" required placeholder="e.g. Dr. Smith - General Checkup" value={newRecord.condition} onChange={(e) => setNewRecord({...newRecord, condition: e.target.value})} className="w-full px-3 py-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white" />
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Prescription / Advice Given</label>
              <textarea required rows="2" placeholder="e.g. Prescribed Amoxicillin for 5 days..." value={newRecord.advice} onChange={(e) => setNewRecord({...newRecord, advice: e.target.value})} className="w-full px-3 py-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white resize-none"></textarea>
            </div>
            <button type="submit" disabled={isSubmittingRecord} className="w-full py-3 bg-clinical-600 hover:bg-clinical-500 text-white font-bold rounded-lg uppercase tracking-wider text-sm transition-colors">
              {isSubmittingRecord ? 'Saving...' : 'Save Record'}
            </button>
          </form>
        )}

        {/* Real Timeline */}
        <HistoryTimeline history={patientHistory} />
      </div>
      
    </div>
  );
};

export default PatientDashboard;