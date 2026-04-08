from flask import Flask, request, jsonify
from flask_cors import CORS
from utils import calculate_wait_time, get_peak_hours
from model import predict_disease
from firebase_config import db
import json
import os
import uuid  
import datetime
import threading

app = Flask(__name__)
CORS(app)

# -----------------------------
# Background Thread Helper
# -----------------------------
def fire_and_forget(task, *args, **kwargs):
    """Runs Firebase tasks in the background so the frontend never waits."""
    thread = threading.Thread(target=task, args=args, kwargs=kwargs)
    thread.start()

def async_firebase_set(collection, doc_id, data):
    try:
        db.collection(collection).document(doc_id).set(data)
    except Exception as e:
        print(f"Background Firebase Error: {e}")

def async_firebase_delete(collection, doc_id):
    try:
        db.collection(collection).document(doc_id).delete()
    except:
        pass

def async_firebase_update(collection, doc_id, data):
    try:
        db.collection(collection).document(doc_id).update(data)
    except:
        pass

def async_firebase_add(collection, data):
    try:
        db.collection(collection).add(data)
    except:
        pass

# -----------------------------
import tempfile

TEMP_DIR = tempfile.gettempdir()
DATA_FILE = os.path.join(TEMP_DIR, "sample_patients.json")
HISTORY_FILE = os.path.join(TEMP_DIR, "patient_history.json")
COMPLETED_FILE = os.path.join(TEMP_DIR, "completed_patients.json")
DOCTORS = ["Dr. Sharma", "Dr. Mehta", "Dr. Iyer"]

def assign_doctor(queue):
    if not queue:
        return DOCTORS[0]
    return DOCTORS[len(queue) % len(DOCTORS)]

def load_data(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
    except:
        return []
    return []

def save_data(filepath, data):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
    except:
        pass

# Load all our instant caches!
queue = load_data(DATA_FILE)
history_db = load_data(HISTORY_FILE)
completed_db = load_data(COMPLETED_FILE)
local_history_db = []

# -----------------------------
# 🧠 AI Advice Engine & Priority Scanner
# -----------------------------
def analyze_priority(disease, symptoms):
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
# Routes
# -----------------------------
@app.route('/add_patient', methods=['POST'])
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
        
        # --- 🚨 QUICK FIX FOR PRESENTATION 🚨 ---
        if priority >= 100 and "General Checkup" in disease:
            disease = "Critical Emergency (Pending Doctor Review)"
        elif priority >= 75 and "General Checkup" in disease:
            disease = "Urgent Care Required"
        # ----------------------------------------

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
            "arrival_time": datetime.datetime.now().strftime("%H:%M"),
            "advice": generate_advice(disease, priority),
            "status": "Waiting"
        }

        # 1. Update Local Queue Immediately
        queue.append(patient)
        queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
        save_data(DATA_FILE, queue) # <--- FIXED

        # 2. Sync to Firebase in the background (Instantly moves on!)
        fire_and_forget(async_firebase_set, "patients", patient_id, patient)

        patient_index = next((i for i, p in enumerate(queue) if p['id'] == patient_id), 0)
        wait_time = patient_index * 15

        # 3. Respond to frontend instantly
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


@app.route('/queue', methods=['GET'])
def get_queue():
    sorted_queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
    return jsonify(sorted_queue)


@app.route('/complete_patient/<string:patient_id>', methods=['POST'])
def complete_patient(patient_id):
    global queue, history_db, completed_db # Added completed_db
    data = request.json or {}
    doctor_advice = data.get('advice', 'Standard treatment applied. Rest and hydrate.')

    patient_to_remove = next((p for p in queue if p.get('id') == patient_id), None)

    if patient_to_remove:
        patient_to_remove['advice'] = doctor_advice
        patient_to_remove['status'] = 'Treated'
        queue.remove(patient_to_remove)
        save_data(DATA_FILE, queue)

        history_record = {
            "patient_id": patient_id,
            "date": datetime.datetime.now().strftime("%b %d, %Y"),
            "condition": patient_to_remove.get("disease", "Clinic Checkup"),
            "advice": doctor_advice,
            "source": "Mediflow Clinic",
            "created_at": datetime.datetime.now().isoformat()
        }
        
        history_db.append(history_record)
        save_data(HISTORY_FILE, history_db)

        # --- THE INSTANT CACHE FIX ---
        completed_db.append(patient_to_remove)
        save_data(COMPLETED_FILE, completed_db)
        # -----------------------------

        fire_and_forget(async_firebase_set, "completed_patients", patient_id, patient_to_remove)
        fire_and_forget(async_firebase_delete, "patients", patient_id)
        fire_and_forget(async_firebase_add, "patient_history", history_record)

        return jsonify({"message": "Patient marked as treated.", "removed": patient_to_remove})

    return jsonify({"error": "Patient not found"}), 404


@app.route('/analytics', methods=['GET'])
def get_analytics():
    return jsonify({"peak_hours": get_peak_hours(queue)})


@app.route('/priority', methods=['GET'])
def get_priority_patients():
    return jsonify([p for p in queue if p.get('priority', 0) >= 100])


@app.route('/doctor_stats', methods=['GET'])
def doctor_stats():
    return jsonify({
        "total_patients": len(queue),
        "critical_cases": len([p for p in queue if p.get('priority', 0) >= 100])
    })


@app.route('/patient_status/<string:patient_id>', methods=['GET'])
def get_patient_status(patient_id):
    global queue, completed_db # Added completed_db here!
    
    sorted_queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
    
    for index, p in enumerate(sorted_queue):
        if p.get('id') == patient_id:
            return jsonify({
                "position": index + 1, 
                "wait_time": index * 15,
                "status": p.get('status', 'Waiting')
            })
            
    # --- INSTANT CACHE CHECK (Fixes the infinite loading spinner!) ---
    completed_patient = next((p for p in completed_db if p.get('id') == patient_id), None)
    if completed_patient:
        return jsonify({
            "position": 0, 
            "wait_time": 0, 
            "status": "Treated", 
            "advice": completed_patient.get('advice')
        })
    # -----------------------------------------------------------------

    try:
        treated_doc = db.collection("completed_patients").document(patient_id).get()
        if treated_doc.exists:
            data = treated_doc.to_dict()
            return jsonify({
                "position": 0, "wait_time": 0, "status": "Treated", "advice": data.get('advice')
            })
    except Exception as e:
        print("Firebase Error:", e)

    return jsonify({"error": "Patient not found"}), 404

@app.route('/call_patient/<string:patient_id>', methods=['POST'])
def call_patient(patient_id):
    global queue
    patient = next((p for p in queue if p.get('id') == patient_id), None)
    
    if patient:
        patient['status'] = 'Called'
        save_data(DATA_FILE, queue) # <--- FIXED
        
        # Background update
        fire_and_forget(async_firebase_update, "patients", patient_id, {"status": "Called"})
            
        return jsonify({"message": "Patient called successfully"})
        
    return jsonify({"error": "Patient not found"}), 404

@app.route('/patient_history/<string:patient_id>', methods=['GET'])
def get_patient_history(patient_id):
    global local_history_db
    try:
        # Read instantly from local memory instead of broken Firebase
        history = [h for h in local_history_db if h.get('patient_id') == patient_id]
        history = sorted(history, key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_external_history/<string:patient_id>', methods=['POST'])
def add_external_history(patient_id):
    global local_history_db
    try:
        data = request.json
        
        # Bulletproof Date Handling
        date_str = data.get("date", "")
        final_date = datetime.datetime.now().strftime("%b %d, %Y")
        if date_str:
            try:
                date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                final_date = date_obj.strftime("%b %d, %Y")
            except:
                final_date = date_str

        record = {
            "id": str(uuid.uuid4()), # Give it an ID for React
            "patient_id": patient_id,
            "date": final_date,
            "condition": data.get("condition") or data.get("doctor") or "General Checkup",
            "advice": data.get("advice") or data.get("prescription") or "Rest",
            "source": "External Doctor",
            "created_at": datetime.datetime.now().isoformat()
        }
        
        # 1. Save to local memory instantly!
        local_history_db.append(record)
        
        # 2. Background Firebase Sync
        fire_and_forget(async_firebase_add, "patient_history", record)
        
        return jsonify({"message": "External record added successfully"}), 201
    except Exception as e:
        print(f"History Route Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/retrieve_patient', methods=['POST'])
def retrieve_patient():
    global queue, completed_db # Added completed_db here
    data = request.json
    phone_to_find = data.get('phone', '').strip()
    
    if not phone_to_find:
        return jsonify({"error": "Phone number is required"}), 400

    # 1. Search the ACTIVE queue
    existing_patient = next((p for p in queue if p.get('phone') == phone_to_find), None)

    if existing_patient:
        return jsonify({
            "success": True,
            "patient": {
                **existing_patient,
                "aiAssessment": {
                    "id": existing_patient['id'],
                    "condition": existing_patient.get('disease', ''),
                    "risk_level": existing_patient.get('risk_level', ''),
                    "advice": existing_patient.get('advice', ''),
                    "priority": existing_patient.get('priority', 0)
                }
            }
        }), 200

    # 2. THE FIX: Search the INSTANT Local Cache first (Beats the Firebase delay)
    completed_patient = next((p for p in completed_db if p.get('phone') == phone_to_find), None)
    
    if completed_patient:
        return jsonify({
            "success": True,
            "patient": {
                **completed_patient,
                "aiAssessment": {
                    "id": completed_patient['id'],
                    "condition": completed_patient.get('disease', ''),
                    "risk_level": completed_patient.get('risk_level', ''),
                    "advice": completed_patient.get('advice', ''),
                    "priority": completed_patient.get('priority', 0)
                }
            }
        }), 200

    # 3. Fallback: Search Firebase (With the fixed warning syntax)
    try:
        completed_ref = db.collection("completed_patients").where(field_path="phone", op_string="==", value=phone_to_find).stream()
        for doc in completed_ref:
            cp = doc.to_dict()
            return jsonify({
                "success": True,
                "patient": {
                    **cp,
                    "aiAssessment": {
                        "id": cp['id'],
                        "condition": cp.get('disease', ''),
                        "risk_level": cp.get('risk_level', ''),
                        "advice": cp.get('advice', ''),
                        "priority": cp.get('priority', 0)
                    }
                }
            }), 200
    except Exception as e:
        print("Firebase search error:", e)

    return jsonify({"error": "No session found for this number."}), 404


if __name__ == '__main__':
      app.run(debug=True)