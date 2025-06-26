
# 📘 ESP32 Server Room Monitoring – API Documentation

> Powered by Flask + MongoDB + Email Alerts

---

## 🌐 Base URL (Vercel)

```
https://<your-vercel-project-name>.vercel.app/
```

---

## 📡 Endpoints

### 1. `POST /logdata`

#### ✅ Purpose:

Log temperature and humidity data from ESP32

#### 📥 Body (JSON):

```json
{
  "device_id": "esp32-1",
  "temp": 28.5,
  "humidity": 60.2,
  "timestamp": "2025-06-25T14:30:00Z"
}
```

#### 📤 Response:

```json
{ "status": "success" }
```

---

### 2. `GET /latest`

#### ✅ Purpose:

Fetch the latest sensor reading.

#### 🔧 Optional Query:

* `device_id=esp32-1`

#### 📤 Response:

```json
{
  "status": "success",
  "reading": {
    "device_id": "esp32-1",
    "temp": 28.5,
    "humidity": 60.2,
    "timestamp": "2025-06-25T14:30:00Z"
  }
}
```

---

### 3. `GET /summary`

#### ✅ Purpose:

Get average of the **last 4 readings**.

#### 🔧 Optional Query:

* `device_id=esp32-1`

#### 📤 Response:

```json
{
  "status": "success",
  "device_id": "esp32-1",
  "data_points_used": 4,
  "last_hour_info": {
    "average_temp": 27.8,
    "average_humidity": 61.2
  }
}
```

---

### 4. `GET /history`

#### ✅ Purpose:

Get readings between 2 date/times.

#### 🔧 Query Parameters:

* `start` (ISO format)
* `end` (ISO format)
* Optional: `device_id`

#### 📥 Example:

```
/history?start=2025-06-25T00:00:00Z&end=2025-06-25T23:59:00Z
```

#### 📤 Response:

```json
{
  "status": "success",
  "count": 6,
  "readings": [
    {
      "device_id": "esp32-1",
      "temp": 28.2,
      "humidity": 60,
      "timestamp": "2025-06-25T10:00:00Z"
    },
    ...
  ]
}
```

---

### 5. `GET /health`

#### ✅ Purpose:

Checks if last data was logged within 15 minutes.

#### 📤 Response:

```json
{
  "status": "ok"
}
```

or

```json
{
  "status": "stale",
  "last_entry": "2025-06-25T13:20:00Z",
  "minutes_ago": 22.3
}
```

---

### 6. `POST /alert`

#### ✅ Purpose:

ESP sends alert (e.g. high temp) — email is sent.

#### 📥 Body (JSON):

```json
{
  "device_id": "esp32-1",
  "temp": 38.5,
  "humidity": 67,
  "timestamp": "2025-06-25T14:35:00Z"
}
```

#### 📤 Response:

```json
{
  "status": "alert_sent",
  "device_id": "esp32-1",
  "timestamp": "2025-06-25T14:35:00Z"
}
```

---

## 📧 Email Notification

* Triggered via `/alert`
* Sends to all emails defined in your `.env` as `EMAIL_TO` (comma-separated)
* Configurable subject and body

---

## 📁 Environment Variables

```env
EMAIL_USER=your@gmail.com
EMAIL_PASS=your_app_password
EMAIL_TO=person1@example.com,person2@example.com
MONGO_URI=your_mongodb_connection_string
```

---

## 📦 Required Python Packages

```txt
Flask==3.0.3
flask-pymongo==2.3.0
python-dotenv==1.0.1
pytz==2024.1
dnspython==2.6.1
email-validator==2.1.1
```

---

## 🧪 Testing

Use tools like:

* [Postman](https://www.postman.com/)
* [curl](https://curl.se/)
* React Dashboard (for frontend)

