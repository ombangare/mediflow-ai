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
DATA_FILE = "../data/sample_patients.json"
DOCTORS = ["Dr. Sharma", "Dr. Mehta", "Dr. Iyer"]

def assign_doctor(queue):
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
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

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

    # List of keywords mapped to priority levels
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
    global queue # Ensure we are modifying the global queue
    try:
        data = request.json

        # ✅ SAFE INPUT HANDLING
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

        # ✅ AI Processing & Priority Calculation
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

        # ✅ Firebase save 
        try:
            db.collection("patients").document(patient_id).set(patient)
        except Exception as e:
            print("Firebase error:", e)

        # ✅ Local queue appending AND immediate sorting!
        queue.append(patient)
        queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
        #save_data(queue)

        # Get exact index to calculate wait time accurately
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


@app.route('/queue', methods=['GET'])
def get_queue():
    sorted_queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
    return jsonify(sorted_queue)


@app.route('/complete_patient/<string:patient_id>', methods=['POST'])
def complete_patient(patient_id):
    global queue
    
    data = request.json or {}
    doctor_advice = data.get('advice', 'Standard treatment applied. Rest and hydrate.')

    patient_to_remove = next((p for p in queue if p.get('id') == patient_id), None)

    if patient_to_remove:
        patient_to_remove['advice'] = doctor_advice
        patient_to_remove['status'] = 'Treated'

        queue.remove(patient_to_remove)
        #save_data(queue)

        try:
            db.collection("completed_patients").document(patient_id).set(patient_to_remove)
            db.collection("patients").document(patient_id).delete() 
            
            # AUTOMATICALLY ADD TO PATIENT HISTORY
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

        return jsonify({
            "message": "Patient marked as treated and prescription saved.",
            "removed": patient_to_remove
        })

    return jsonify({"error": "Patient not found"}), 404


@app.route('/analytics', methods=['GET'])
def get_analytics():
    return jsonify({
        "peak_hours": get_peak_hours(queue)
    })


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
    sorted_queue = sorted(queue, key=lambda x: int(x.get('priority', 0)), reverse=True)
    
    for index, p in enumerate(sorted_queue):
        if p.get('id') == patient_id:
            wait_time = index * 15 
            return jsonify({
                "position": index + 1, 
                "wait_time": wait_time,
                "status": p.get('status', 'Waiting')
            })
            
    try:
        treated_doc = db.collection("completed_patients").document(patient_id).get()
        if treated_doc.exists:
            data = treated_doc.to_dict()
            return jsonify({
                "position": 0,
                "wait_time": 0,
                "status": "Treated",
                "advice": data.get('advice')
            })
    except Exception as e:
        pass

    return jsonify({"error": "Patient not found"}), 404

@app.route('/call_patient/<string:patient_id>', methods=['POST'])
def call_patient(patient_id):
    global queue
    patient = next((p for p in queue if p.get('id') == patient_id), None)
    
    if patient:
        patient['status'] = 'Called'
        #save_data(queue)
        
        try:
            db.collection("patients").document(patient_id).update({"status": "Called"})
        except Exception:
            pass
            
        return jsonify({"message": "Patient called successfully"})
        
    return jsonify({"error": "Patient not found"}), 404

@app.route('/patient_history/<string:patient_id>', methods=['GET'])
def get_patient_history(patient_id):
    try:
        history_ref = db.collection('patient_history').where('patient_id', '==', patient_id).stream()
        history = []
        for doc in history_ref:
            data = doc.to_dict()
            data['id'] = doc.id
            history.append(data)
        
        history = sorted(history, key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_external_history/<string:patient_id>', methods=['POST'])
def add_external_history(patient_id):
    try:
        data = request.json
        date_str = data.get("date")
        if not date_str:
            date_str = datetime.datetime.now().strftime("%b %d, %Y")
        else:
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            date_str = date_obj.strftime("%b %d, %Y")

        record = {
            "patient_id": patient_id,
            "date": date_str,
            "condition": data.get("condition", "External Consultation"),
            "advice": data.get("advice", ""),
            "source": "External Doctor",
            "created_at": datetime.datetime.now().isoformat()
        }
        db.collection('patient_history').add(record)
        return jsonify({"message": "External record added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/retrieve_patient', methods=['POST'])
def retrieve_patient():
    global queue
    data = request.json
    phone_to_find = data.get('phone', '').strip()
    
    if not phone_to_find:
        return jsonify({"error": "Phone number is required"}), 400

    # 1. Search for the patient in the ACTIVE queue first
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
    
    # 2. THE FIX: Search for the patient in the COMPLETED queue (Firebase)
    try:
        completed_ref = db.collection("completed_patients").where("phone", "==", phone_to_find).stream()
        for doc in completed_ref:
            completed_patient = doc.to_dict()
            # If found in completed, return them so they can see their prescription!
            return jsonify({
                "success": True,
                "patient": {
                    **completed_patient,
                    "aiAssessment": {
                        "id": completed_patient['id'],
                        "condition": completed_patient.get('disease', ''),
                        "risk_level": completed_patient.get('risk_level', ''),
                        "advice": completed_patient.get('advice', ''), # This now holds the DOCTOR'S prescription!
                        "priority": completed_patient.get('priority', 0)
                    }
                }
            }), 200
    except Exception as e:
        print("Firebase search error:", e)

    # 3. If not in active queue AND not in completed queue
    return jsonify({"error": "No active or recently treated session found for this number."}), 404


#if __name__ == '__main__':
 #app.run(debug=True)