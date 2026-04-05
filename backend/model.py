def predict_disease(symptoms):
    symptoms = [s.lower() for s in symptoms]
    
    if "fever" in symptoms and "cough" in symptoms:
        return "Flu"
    elif "headache" in symptoms and "nausea" in symptoms:
        return "Migraine"
    elif "chest pain" in symptoms:
        return "High Risk - Cardiac Issue"
    else:
        return "General Checkup"