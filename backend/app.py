from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet
from pymongo import MongoClient
from datetime import datetime
import base64
import os
from bson import ObjectId
import requests
from io import BytesIO

from cred import url
from encryption import encrypt_data, decrypt_data
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
import jwt_config 

# pip install cryptography
# pip install pymongo
# pip install flask
# pip install flask_cors
# pip install flask-jwt-extended

app = Flask(__name__)
# CORS(app)
CORS(app, resources={r"/*": {"origins": "*"}})


# Configure JWT
app.config.from_object(jwt_config)
jwt = JWTManager(app)

# Get the ML service URL from environment variable
ml_service_url = os.getenv("ML_SERVICE_URL")

# MongoDB Config
client = MongoClient(url)

try:
    client.admin.command('ping')
    print("Connected to MongoDB")
except Exception as e:
    print("MongoDB connection failed:", e)
    raise

# {
#   "_id": "user_pid",
#   "seq": 1000
# }

db = client["Patient"]
counter_collection = db["counters"]
user_collection = db["Login"]
patient_collection = db["Patient_info"]
diagnosis_result_collection = db["Diagnosis_Result"]
request_collection = db["Request"]


# Initialize counters if not present
if counter_collection.count_documents({"_id": "user_pid"}) == 0:
    counter_collection.insert_one({"_id": "user_pid", "seq": 1000})
if counter_collection.count_documents({"_id": "patient_id"}) == 0:
    counter_collection.insert_one({"_id": "patient_id", "seq": 1000})

# Auto-increment functions
def get_next_user_pid():
    counter = counter_collection.find_one_and_update(
        {"_id": "user_pid"},
        {"$inc": {"seq": 1}},
        return_document=True
    )
    return str(counter["seq"])

# User registration
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    name = data.get('name')

    if not all([username, password, email, name]):
        return jsonify({"error": "All fields (username, password, email, name) are required"}), 400

    # Check if user already exists in MongoDB
    existing_user = user_collection.find_one({"username": username})
    if existing_user:
        return jsonify({"error": "User already exists"}), 409

    # Encrypt the password
    # encrypted_password = fernet.encrypt(password.encode())
    encrypted_password = encrypt_data(password)

    # Get auto-incremented PID
    pid = get_next_user_pid()

    # Prepare document
    document = {
        "username": username,
        "password": encrypted_password,
        "email": email,
        "name": name,
        "pid": pid  # Store PID as int or string as you prefer
    }

    # Insert into MongoDB
    user_collection.insert_one(document)

    return jsonify({"message": f"User {username} registered successfully", "pid": pid}), 201

# User verification     
@app.route('/verify', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Doctor login
    if username == "doctor" and password == "doctor123":
        access_token = create_access_token(identity="doctor",additional_claims={"role": "doctor"})
        return jsonify({
            "message": "Doctor authenticated",
            "role": "doctor",
            "token": access_token
        }), 200

    # Patient login
    user = user_collection.find_one({"username": username})
    if not user:
        return jsonify({"error": "Username not found"}), 404

    try:
        decrypted_password = decrypt_data(user["password"])
    except Exception as e:
        return jsonify({"error": "Password decryption failed"}), 500

    if password == decrypted_password:
        access_token = create_access_token(identity=str(user["pid"]), additional_claims={"username": username, "role": "patient"})
        return jsonify({
            "message": "Verification successful",
            "pid": user["pid"],
            "role": "patient",
            "token": access_token
        }), 200
    else:
        return jsonify({"error": "Wrong password"}), 401


# Upload data
@app.route('/upload_data/<pid>', methods=['POST'])
def upload_data(pid):
    try:
        # Get data from form (request.form)
        date = request.form.get('date')
        prediction = request.form.get('mlDiagnosis')
        # doctor_diagnosis = request.form.get('doctorDiagnosis')
        status = request.form.get('status')
        p_comment = request.form.get('patientComments')
        # d_comment = request.form.get('doctorComments')
        image = request.files.get('image')

        # if not all([date, prediction, doctor_diagnosis, status, p_comment, d_comment, image]):
        #     return jsonify({"error": "All fields are required"}), 400

        # Convert image to base64
        image_data = base64.b64encode(image.read()).decode("utf-8")

        # Build your data document
        document = {
            "patient_id": pid,
            "date": date,
            "mlDiagnosis": prediction,
            "doctorDiagnosis": None,
            "status": status,
            "patientComments" :p_comment,
            "doctorComments": None,
            "imagePath": image_data
        }

        # Save to database
        diagnosis_result_collection.insert_one(document)

        # Return only the success message
        return jsonify({"message": "data uploaded successfully"}), 201

    except Exception as e:
        return jsonify({"error": f"Failed to upload data: {str(e)}"}), 500

# Data of given patient
@app.route('/get_data/<pid>', methods=['GET'])
@jwt_required()
def get_data(pid):
    # Ensure the token belongs to a patient with matching PID  
    token_pid = get_jwt_identity()  # This will be a string pid
    claims = get_jwt()              # This will be a dict with "role"

    if claims.get("role") != "patient" or token_pid != pid:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Query diagnosis records from the 'Request' collection
        results = request_collection.find({"patient_id": pid})

        records = []
        for result in results:
            result.pop('_id', None)
            records.append({
                "patient_id": result.get("patient_id"),
                "date": result.get("date"),
                "status": result.get("status"),
                "mlDiagnosis": result.get("mlDiagnosis"),
                "doctorDiagnosis": result.get("doctorDiagnosis"),
                "doctorComments": result.get("doctorComments"),
                "patientComments": result.get("patientComments"),
                "imagePath": result.get("imagePath")
            })

        if records:
            return jsonify({"data": records}), 200
        else:
            return jsonify({"error": "No records found for this patient"}), 404

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve data: {str(e)}"}), 500

    
# Data of all patient
@app.route('/get_patient_data', methods=['GET'])
def get_patient_data():
    try:
        # Query the database for all diagnosis records
        results = request_collection.find({})  # No patient_id filter

        # Convert the cursor to a list and remove '_id' from each result
        records = []
        for result in results:
            result.pop('_id', None)  # Remove '_id' field
            records.append({
                "patient_id": result.get("patient_id"),
                "date": result.get("date"),
                "status": result.get("status"),
                "mlDiagnosis": result.get("ml_diagnosis"),
                "imagePath": result.get("image")
            })

        if records:
            response = {
                "data": records
            }
            return jsonify(response), 200
        else:
            return jsonify({"error": "No records found"}), 404

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve data: {str(e)}"}), 500      
 
@app.route("/create-request", methods=["POST"])
def create_request():
    try:
        patient_id = request.form.get("patientId")
        comments = request.form.get("comments")
        image_file = request.files.get("image") 

        print("patientId:", patient_id)
        print("comments:", comments)
        if not image_file:
            print("Image not found")
            return jsonify({"error": "Image file is required"}), 400

        image_content = image_file.read()
        if not image_content:
            print("Image content is empty")
            return jsonify({"error": "Image file is empty"}), 400

        image_data = base64.b64encode(image_content).decode("utf-8")
        image_file_io = BytesIO(image_content)
        image_file_io.seek(0)

        files = {"image": (image_file.filename, image_file_io, image_file.content_type)}
        print("Sending image to ML service...")

        # ml_response = requests.post("http://127.0.0.1:5001/predict", files=files)
        # ml_response = requests.post("http://ml-service:5001/predict", files=files)
        ml_response = requests.post(ml_service_url, files=files)
        
        
        print("ML service response status:", ml_response.status_code)

        try:
            ml_data = ml_response.json()
        except ValueError:
            print("Invalid JSON from ML service:", ml_response.text)
            return jsonify({"error": "Invalid response from ML service"}), 500

        ml_diagnosis = ml_data.get("predicted_class", "Unknown")
        print("Diagnosis from ML:", ml_diagnosis)

        date = datetime.now().strftime("%Y-%m-%d")
        new_entry = {
            "patient_id": patient_id,
            "date": date,
            "imagePath": image_data,
            "patientComments": comments,
            "mlDiagnosis": ml_diagnosis,
            "doctorComments": None,
            "doctorDiagnosis": None,
            "status": "Pending"
        }

        print("Inserting into MongoDB:", new_entry)
        request_collection.insert_one(new_entry)

        return jsonify({"message": "Request created successfully"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

    
# ========== DOCTOR ENDPOINTS ==========
# @app.route('/doctor-verify', methods=['POST'])
# def doctor_verify():
#     data = request.get_json()
#     if data.get('username') == "doctor" and data.get('password') == "doctor123":
#         print("doctor login succeess")
#         return jsonify({"message": "Doctor authenticated", "role": "doctor"}), 200
#     return jsonify({"error": "Invalid credentials"}), 401

@app.route('/get-pending-requests', methods=['GET'])
@jwt_required()
def get_pending_requests():
    identity = get_jwt_identity()  # will be "doctor"
    claims = get_jwt()             # dict with "role"

    if claims.get("role") != "doctor":
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Fetch requests with status "Pending" from the MongoDB collection
        pending_requests = request_collection.find({"status": "Pending"})

        results = []
        for request in pending_requests:
            results.append({
                "appointment_id": str(request.get("_id")),
                "patientId": request.get("patient_id"),
                "date": request.get("date"),
                "mlDiagnosis": request.get("mlDiagnosis"),
                "patientComments": request.get("patientComments"),
                "status": request.get("status"),
                "imagePath": request.get("imagePath")
            })

        return jsonify({"data": results}), 200

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve pending requests: {str(e)}"}), 500


@app.route('/update-diagnosis', methods=['POST'])
@jwt_required()
def update_diagnosis():
    identity = get_jwt_identity()  # should be "doctor"
    claims = get_jwt()             # dict with "role"

    if claims.get("role") != "doctor":
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.json
        print(data)

        _id = ObjectId(data['appointment_id'])

        request_collection.update_one(
            {"_id": _id},
            {
                "$set": {
                    "status": "Reviewed",
                    "doctorDiagnosis": data['doctorDiagnosis'],
                    "doctorComments": data.get('doctorComments', "No comments")
                }
            }
        )

        return jsonify({"message": "Diagnosis updated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Run the app
# if __name__ == '__main__':
#     app.run(debug=True)

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True) 

