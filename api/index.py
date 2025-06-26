from flask import Flask, jsonify
from flask import request
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import os

load_dotenv()

app = Flask(__name__)

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tls=True, server_api=ServerApi('1'))
db = client["Sensor_data"]  # Replace with your DB name
collection = db["readings"]  # Replace with your collection name

# Global cache
latest_data = None

@app.route("/health", methods=["GET"])
def health():
    global latest_data

    # Fetch latest from cache or DB
    if not latest_data:
        doc = collection.find_one(sort=[("timestamp", -1)])
        if doc:
            latest_data = {
                "device_id": doc.get("device_id"),
                "temp": doc.get("temp"),
                "humidity": doc.get("humidity"),
                "timestamp": doc.get("timestamp"),
            }

    if not latest_data:
        return jsonify({"status": "no_data"}), 404

    # Check freshness
    now = datetime.now(pytz.UTC)
    last_time = latest_data["timestamp"]
    elapsed = now - last_time
    minutes = elapsed.total_seconds() / 60

    if minutes <= 15:
        return jsonify({
            "status": "ok",
            "last_reading": latest_data,
            "minutes_ago": round(minutes, 2)
        }), 200
    else:
        return jsonify({
            "status": "stale",
            "last_reading": latest_data,
            "minutes_ago": round(minutes, 2)
        }), 503

# Required for Vercel

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
    recipient = os.getenv("EMAIL_TO")

    if not all([sender, password, recipient]):
        print("❌ Missing email credentials in environment variables")
        return False

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        print("✅ Alert email sent")
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
    







app = app