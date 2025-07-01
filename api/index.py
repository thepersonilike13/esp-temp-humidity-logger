from flask import Flask, jsonify
from flask import request
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import os
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tls=True, server_api=ServerApi('1'))
db = client["Sensor_data"]  # Replace with your DB name
collection = db["readings"]  # Replace with your collection name

# Global cache
# Global state
is_device_alive = True 
last_heartbeat_time = datetime.now(pytz.UTC)

# @app.route('/heartbeat', methods=['POST'])
# def heartbeat():
#     global is_device_alive, last_heartbeat_time
#     is_device_alive = True
#     last_heartbeat_time = datetime.now(pytz.UTC)
#     return jsonify({"status": "heartbeat_received"}), 200

# === 2. HEALTH API ===
@app.route('/health', methods=['GET'])
def health():
    global is_device_alive, last_heartbeat_time

    now = datetime.now(pytz.UTC)

    if not last_heartbeat_time:
        return jsonify({"status": "no_heartbeat"}), 404

    # Check freshness of last heartbeat
    if now - last_heartbeat_time <= timedelta(hours=1):
        return jsonify({
            "status": "ok",
            "last_heartbeat": last_heartbeat_time.isoformat(),
            "minutes_ago": round((now - last_heartbeat_time).total_seconds() / 60, 2)
        }), 200
    else:
        return jsonify({
            "status": "stale",
            "last_heartbeat": last_heartbeat_time.isoformat(),
            "minutes_ago": round((now - last_heartbeat_time).total_seconds() / 60, 2)
        }), 503

@app.route("/logdata", methods=["POST"])
def logdata():
    global latest_data
    data = request.get_json()

    # Basic validation
    required = {"device_id", "temp", "humidity", "timestamp"}
    if not data or not required.issubset(data):
        return jsonify({"error": "Invalid payload"}), 400

    # Convert timestamp to datetime (if needed)
    try:
        data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    except Exception as e:
        return jsonify({"error": "Invalid timestamp format"}), 400

    # Insert into MongoDB
    try:
        collection.insert_one(data)
        latest_data = data  # Update cache
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/latest", methods=["GET"])
def latest():
    try:
        device_id = request.args.get("device_id")
        query = {"device_id": device_id} if device_id else {}

        doc = collection.find_one(query, sort=[("timestamp", -1)])

        if not doc:
            return jsonify({"status": "no_data"}), 404
        # Convert timestamp to ISO format
        
        return jsonify({
            "status": "success",
            "latest": {
                "device_id": doc.get("device_id"),
                "temp": doc.get("temp"),
                "humidity": doc.get("humidity"),
                "timestamp": doc.get("timestamp")
            }
        }), 200

    except Exception as e:
        print("❌ Error in /latest:", str(e))  # Visible in Vercel logs
        return jsonify({"status": "error", "message": str(e)}), 500




@app.route("/summary", methods=["GET"])
def summary():
    try:
        device_id = request.args.get("device_id")
        query = {"device_id": device_id} if device_id else {}

        # Fetch the last 4 readings
        cursor = collection.find(query).sort("timestamp", -1).limit(4)
        data_points = list(cursor)

        if not data_points:
            return jsonify({"status": "no_data"}), 404

        # Compute averages
        avg_temp = sum(d["temp"] for d in data_points) / len(data_points)
        avg_humidity = sum(d["humidity"] for d in data_points) / len(data_points)

        return jsonify({
            "status": "success",
            "device_id": device_id or "all",
            "data_points_used": len(data_points),
            "last_hour_info": {
                "average_temp": round(avg_temp, 2),
                "average_humidity": round(avg_humidity, 2)
            }
        }), 200

    except Exception as e:
        print("❌ /summary error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500




@app.route("/history", methods=["GET"])
def history():
    try:
        # Parse query parameters
        start_str = request.args.get("start")
        end_str = request.args.get("end")
        device_id = request.args.get("device_id")

        if not start_str or not end_str:
            return jsonify({"error": "Missing start or end date"}), 400

        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "Invalid datetime format"}), 400

        # Build query
        query = {
            "timestamp": {"$gte": start_dt, "$lte": end_dt}
        }
        if device_id:
            query["device_id"] = device_id

        cursor = collection.find(query).sort("timestamp", 1)
        results = []
        for doc in cursor:
            results.append({
                "timestamp": doc.get("timestamp").isoformat(),
                "temp": doc.get("temp"),
                "humidity": doc.get("humidity"),
                "device_id": doc.get("device_id")
            })

        return jsonify({
            "status": "success",
            "count": len(results),
            "readings": results
        }), 200

    except Exception as e:
        print("❌ /history error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500





@app.route('/test', methods=['GET'])
def test_connection():
    try:
        # Ping the MongoDB deployment
        client.admin.command("ping")
        return jsonify({
            "status": "success",
            "message": "✅ Connected to MongoDB successfully!"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_alert_email(subject, body):
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    recipients_raw = os.getenv("EMAIL_TO")

    if not all([sender, password, recipients_raw]):
        print("❌ Missing email credentials in environment variables")
        return False

    # Convert comma-separated recipients to list
    recipients = [email.strip() for email in recipients_raw.split(",") if email.strip()]

    if not recipients:
        print("❌ No valid recipient email addresses found")
        return False

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)  # For email headers
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())  # Actual recipients
        server.quit()
        print(f"✅ Alert email sent to: {', '.join(recipients)}")
        return True
    except Exception as e:
        print("❌ Failed to send email:", e)
        return False
    



@app.route("/alert", methods=["POST"])
def receive_alert():
    try:
        data = request.get_json()
        device_id = data.get("device_id", "unknown-device")
        temp = data.get("temp")
        humidity = data.get("humidity")
        timestamp = data.get("timestamp")

        if temp is None or timestamp is None:
            return jsonify({"status": "error", "message": "Missing data"}), 400

        # Compose alert message
        subject = f"[ALERT] {device_id} reports high temperature!"
        body = f"""
📡 ESP32 Alert Triggered

Device ID: {device_id}
Temperature: {temp} °C
Humidity: {humidity} %
Timestamp: {timestamp}

Take necessary action immediately.
        """

        # Send email
        send_alert_email(subject, body)

        return jsonify({
            "status": "alert_sent",
            "device_id": device_id,
            "timestamp": timestamp
        }), 200

    except Exception as e:
        print("❌ /alert POST error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500
    








@app.route('/send-summary-email', methods=['POST'])
def send_summary_email():
    try:
        data = request.get_json()

        required_fields = ['device_id', 'average_temp', 'average_humidity', 'data_points', 'readings']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing one or more required fields"}), 400

        device_id = data['device_id']
        avg_temp = data['average_temp']
        avg_humidity = data['average_humidity']
        data_points = data['data_points']
        readings = data['readings']  # List of readings

        # Create email body
        body = (
            f"📊 Summary for device **{device_id}** (Last Hour)\n\n"
            f"🌡️ Average Temperature: {avg_temp:.1f} °C\n"
            f"💧 Average Humidity: {avg_humidity:.1f} %\n"
            f"📈 Data Points: {data_points}\n\n"
            f"--- Raw Readings ---\n"
        )

        for r in readings:
            ts = r.get("timestamp", "N/A")
            temp = r.get("temp", "N/A")
            hum = r.get("humidity", "N/A")
            body += f"• {ts} → Temp: {temp}°C, Humidity: {hum}%\n"

        subject = f"📡 Hourly Summary for {device_id}"
        success = send_alert_email(subject, body)

        if success:
            return jsonify({"status": "Email sent with full data"}), 200
        else:
            return jsonify({"error": "Failed to send email"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500
