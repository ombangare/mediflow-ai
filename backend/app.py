from flask import Flask, request, jsonify
from flask_cors import CORS
from utils import calculate_wait_time, get_peak_hours
from model import predict_disease
from firebase_config import db
import json
import os
import uuid  
import datetime

app = Flask(__name__)
CORS(app)

# -----------------------------
# Data & Config
# -----------------------------
# VERCEL FIX: Vercel is read-only. /tmp/ is the only place we can write.
DATA_FILE = "/tmp/sample_patients.json"
DOCTORS = ["Dr. Sharma", "Dr. Mehta", "Dr. Iyer"]

def assign_doctor(queue):
    if not queue:
        return DOCTORS[0]
    return DOCTORS[len(queue) % len(DOCTORS)]

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
    except:
        return []
    return []

def save_data(data):
    # VERCEL FIX: Wrap in try-except so the app never crashes if writing is blocked
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Local save skipped (Expected on Vercel): {e}")

queue = load_data()

# -----------------------------
# 🧠 AI Advice Engine & Priority Scanner
# -----------------------------
def analyze_priority(disease, symptoms):
    """
    Scans the disease and symptoms for critical keywords and assigns a strict priority score.
    100 = Critical (Red), 75 = Urgent, 50 = Moderate, 10 = Stable/General (Green)
    """
    disease_lower = disease.lower()
    symptoms_text = ", ".join(symptoms).lower() if symptoms else ""
    combined_text = disease_lower + " " + symptoms_text

    CRITICAL_KEYWORDS = [
        "heart attack", "chest pain", "cardiac", "stroke", "pain in heart", "heart",
        "breathing difficulty", "shortness of breath", "unconscious", "fainting", 
        "seizure", "severe bleeding", "poisoning", "head trauma", "paralysis", 
        "anaphylaxis", "vomiting blood", "choking", "gunshot", "stab"
    ]
    
    HIGH_KEYWORDS = [
        "fracture", "broken bone", "severe pain", "high fever", "asthma", 
        "severe burn", "infection", "headache severe", "blur vision"
    ]
    
    MEDIUM_KEYWORDS = [
        "flu", "fever", "migraine", "vomiting", "diarrhea", "stomach ache", 
        "dizziness", "nausea", "sprain", "rash"
    ]

    if any(keyword in combined_text for keyword in CRITICAL_KEYWORDS):
        return 100, "CRITICAL: Immediate life-threatening symptoms detected."
    elif any(keyword in combined_text for keyword in HIGH_KEYWORDS):
        return 75, "URGENT: Severe symptoms requiring rapid attention."
    elif any(keyword in combined_text for keyword in MEDIUM_KEYWORDS):
        return 50, "MODERATE: Standard illness or moderate discomfort."
    else:
        return 10, "STABLE: General checkup or minor symptoms."


def generate_advice(disease, priority_score):
    if priority_score >= 100:
        return f"⚠️ Serious condition suspected related to {disease}. Seek immediate medical attention. Do not exert yourself."
    elif priority_score >= 75:
        return f"Urgent care needed for {disease}. Please remain seated and notify a nurse if pain worsens."
    elif priority_score >= 50:
        return f"Moderate symptoms detected for {disease}. Rest, stay hydrated, and await doctor consultation."
    else:
        return "Condition appears stable. Routine checkup protocols apply."

# -----------------------------
# Routes (Updated with /api to match your frontend)
# -----------------------------

@app.route('/api/add_patient', methods=['POST'])
def add_patient():
    global queue 
    try:
        data = request.json
        raw_symptoms = data.get('symptoms', [])
        if isinstance(raw_symptoms, str):
            symptoms = [s.strip() for s in raw_symptoms.split(',') if s.strip()]
        else:
            symptoms = raw_symptoms

        name = data.get('name')
        age = int(data.get('age', 0)) if data.get('age') else 0
        weight = int(data.get('weight', 0)) if data.get('weight') else 0
        height = int(data.get('height', 0)) if data.get('height') else 0 

        if not name or age == 0:
            return jsonify({"error": "Name and age are required"}), 400

        disease = predict_disease(symptoms)
        priority, reason = analyze_priority(disease, symptoms)
        
        risk_level = "High" if priority >= 100 else "Medium" if priority >= 50 else "Low"
        patient_id = str(uuid.uuid4())

        patient = {
            "id": patient_id, 
            "name": name,
            "phone": data.get('phone', ''),
            "email": data.get('email', ''),
            "age": age,
            "weight": weight,
            "height": height, 
            "symptoms": symptoms,
            "priority": priority,
            "disease": disease,
            "reason": reason,
            "risk_level": risk_level,
            "assigned_doctor": assign_doctor(queue),
            "arrival_time": datetime.datetime.now().strftime("%H"),
            "advice": generate_advice(disease, priority),
            "status": "Waiting"
        }

        try:
            db.collection("patients").document(patient_id).set(patient)
        except Exception as e:
            print("Firebase error:", e)

        queue.append(patient)
        queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
        save_data(queue)

        patient_index = next((i for i, p in enumerate(queue) if p['id'] == patient_id), 0)
        wait_time = patient_index * 15

        return jsonify({
            "id": patient_id,
            "predicted_disease": disease,
            "condition": disease,      
            "risk_level": risk_level,  
            "wait_time": wait_time,
            "priority": priority,
            "reason": reason,
            "assigned_doctor": patient["assigned_doctor"],
            "advice": patient["advice"]
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/queue', methods=['GET'])
def get_queue():
    sorted_queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
    return jsonify(sorted_queue)


@app.route('/api/complete_patient/<string:patient_id>', methods=['POST'])
def complete_patient(patient_id):
    global queue
    data = request.json or {}
    doctor_advice = data.get('advice', 'Standard treatment applied. Rest and hydrate.')
    patient_to_remove = next((p for p in queue if p.get('id') == patient_id), None)

    if patient_to_remove:
        patient_to_remove['advice'] = doctor_advice
        patient_to_remove['status'] = 'Treated'
        queue.remove(patient_to_remove)
        save_data(queue)

        try:
            db.collection("completed_patients").document(patient_id).set(patient_to_remove)
            db.collection("patients").document(patient_id).delete() 
            history_record = {
                "patient_id": patient_id,
                "date": datetime.datetime.now().strftime("%b %d, %Y"),
                "condition": patient_to_remove.get("disease", "Clinic Checkup"),
                "advice": doctor_advice,
                "source": "Mediflow Clinic",
                "created_at": datetime.datetime.now().isoformat()
            }
            db.collection('patient_history').add(history_record)
        except Exception as e:
            print("Firebase error:", e)

        return jsonify({"message": "Patient marked as treated.", "removed": patient_to_remove})
    return jsonify({"error": "Patient not found"}), 404


@app.route('/api/patient_status/<string:patient_id>', methods=['GET'])
def get_patient_status(patient_id):
    sorted_queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
    for index, p in enumerate(sorted_queue):
        if p.get('id') == patient_id:
            return jsonify({"position": index + 1, "wait_time": index * 15, "status": p.get('status', 'Waiting')})
    return jsonify({"error": "Patient not found"}), 404


@app.route('/api/call_patient/<string:patient_id>', methods=['POST'])
def call_patient(patient_id):
    global queue
    patient = next((p for p in queue if p.get('id') == patient_id), None)
    if patient:
        patient['status'] = 'Called'
        save_data(queue)
        try:
            db.collection("patients").document(patient_id).update({"status": "Called"})
        except Exception:
            pass
        return jsonify({"message": "Patient called successfully"})
    return jsonify({"error": "Patient not found"}), 404


@app.route('/api/patient_history/<string:patient_id>', methods=['GET'])
def get_patient_history(patient_id):
    try:
        history_ref = db.collection('patient_history').where('patient_id', '==', patient_id).stream()
        history = [doc.to_dict() for doc in history_ref]
        history = sorted(history, key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/retrieve_patient', methods=['POST'])
def retrieve_patient():
    global queue
    data = request.json
    phone = data.get('phone', '').strip()
    if not phone:
        return jsonify({"error": "Phone number required"}), 400

    existing = next((p for p in queue if p.get('phone') == phone), None)
    if existing:
        return jsonify({"success": True, "patient": existing}), 200
    
    try:
        completed = db.collection("completed_patients").where("phone", "==", phone).stream()
        for doc in completed:
            return jsonify({"success": True, "patient": doc.to_dict()}), 200
    except:
        pass
    return jsonify({"error": "No active session found."}), 404

# REQUIRED FOR VERCEL: Do not use app.run() here.