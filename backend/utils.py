def get_case_weight(symptoms):
    symptoms = [s.lower() for s in symptoms]
    
    if "chest pain" in symptoms:
        return 1.5
    elif "fever" in symptoms and "cough" in symptoms:
        return 1.2
    else:
        return 1.0


def calculate_wait_time(queue):
    total_time = 0

    for patient in queue:
        weight = get_case_weight(patient["symptoms"])

        # 🔥 PRIORITY IMPACT
        if patient.get("priority", 0) >= 100:
            total_time += 5  # fast-track
        else:
            total_time += 10 * weight

    return round(total_time)

def calculate_priority(data, predicted_disease):
    score = 0
    reasons = []

    symptoms = [s.lower() for s in data.get("symptoms", [])]

    # 🔥 HARD RULE: CARDIAC SYMPTOMS
    if "chest pain" in symptoms or "heart pain" in symptoms:
        score += 120
        reasons.append("Possible Cardiac Emergency")

    # 🔥 BREATHING ISSUE
    if "shortness of breath" in symptoms:
        score += 80
        reasons.append("Breathing Issue")

    # 🔥 EMERGENCY FLAG
    if data.get("emergency"):
        score += 100
        reasons.append("Marked Emergency")

    # 🔥 AGE FACTOR
    if data.get("age", 0) > 60:
        score += 30
        reasons.append("Senior Risk")

    # 🔥 AI CONDITION BOOST
    if predicted_disease == "High Risk - Cardiac Issue":
        score += 80
        reasons.append("AI Detected Cardiac Risk")

    elif predicted_disease == "Flu":
        score += 20
        reasons.append("Moderate Condition")

    # 🔥 FINAL CLASSIFICATION FIX
    if score >= 150:
        priority_label = "CRITICAL"
    elif score >= 80:
        priority_label = "HIGH"
    else:
        priority_label = "NORMAL"

    return score, f"{priority_label} - " + (" + ".join(reasons) if reasons else "General Case")

def predict_disease(symptoms):
    symptoms = set([s.lower().strip() for s in symptoms])

    # 🔥 CARDIAC HIGH RISK
    if "chest pain" in symptoms or "heart pain" in symptoms:
        return "High Risk - Cardiac Issue"

    if {"shortness of breath", "chest pain"}.issubset(symptoms):
        return "High Risk - Cardiac Issue"

    # 🔥 FLU
    if {"fever", "cough", "fatigue"}.issubset(symptoms):
        return "Flu"

    # 🔥 MIGRAINE
    if {"headache", "nausea"}.issubset(symptoms):
        return "Migraine"

    return "General Checkup"

def get_peak_hours(queue):
    hour_count = {}

    for patient in queue:
        hour = patient.get("arrival_time")

        if hour:
            hour_count[hour] = hour_count.get(hour, 0) + 1

    # sort by highest traffic
    sorted_hours = sorted(hour_count.items(), key=lambda x: x[1], reverse=True)

    formatted = [
    {"hour": format_hour(h), "count": c}
    for h, c in sorted_hours[:3]
]

    return formatted  # top 3 busiest hours

def format_hour(hour_str):
    hour = int(hour_str)

    if hour == 0:
        return "12 AM"
    elif hour < 12:
        return f"{hour} AM"
    elif hour == 12:
        return "12 PM"
    else:
        return f"{hour - 12} PM"