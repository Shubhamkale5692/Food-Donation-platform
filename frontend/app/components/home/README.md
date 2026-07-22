# 🍱 FoodBridge – Smart Food Donation Platform

FoodBridge is an industry-level smart food donation and distribution platform designed to reduce food waste and improve food accessibility for NGOs, shelters, and beneficiaries.

The platform connects **Donors**, **NGOs**, **Delivery Partners**, and **Beneficiaries** through a real-time logistics and food safety workflow powered by AI-assisted assignment, live tracking, OTP verification, and food quality testing.

---

# 🚀 Features

## 👤 Multi-Role System

* Donor Dashboard
* NGO Dashboard
* Delivery Partner Dashboard
* Beneficiary / Recipient Management
* Admin Panel

---

# 🧠 Core Modules

## 1. Smart Donation Management

* Donors can post surplus food
* NGOs receive incoming donations
* AI & Manual assignment of delivery partners
* Real-time donation lifecycle tracking

---

## 2. Real-Time Delivery Tracking

* Live map navigation using Leaflet + OSRM + Mapbox
* WebSocket-based live tracking
* Dynamic route switching
* ETA tracking
* Delivery timer system

---

## 3. OTP Verification System

### Pickup Stage

Donor verifies food pickup using OTP.

### Distribution Stage

Beneficiary verifies food delivery using OTP.

---

## 4. Food Testing & Safety Decision System

After food reaches NGO:

| Food Quality | Decision            |
| ------------ | ------------------- |
| Fresh ✅      | Distribution        |
| Moderate ⚠️  | Urgent Distribution |
| Spoiled ❌    | Waste Management    |

---

## 5. Distribution Management System

* NGO selects beneficiary/shelter
* AI/manual delivery partner assignment
* Distribution tracking
* Beneficiary delivery confirmation
* Distribution analytics

---

## 6. Waste Management

* Rejected/spoiled food tracking
* Waste reports
* NGO analytics

---

## 7. AI Smart Assignment

AI evaluates:

* Delivery partner distance
* Availability
* Live location
* Trust score
* Performance history

Then automatically assigns the best delivery partner.

---

## 8. Certificate & Achievement System

Automatic certificates generated for:

### Donors

* Bronze
* Silver
* Gold
* Platinum

### Delivery Partners

* Bronze
* Silver
* Gold
* Platinum

Includes:

* PDF certificates
* Achievement tracking
* Auto email delivery

---

# 🏗️ System Workflow

## Stage 1 – Collection

Donor → Delivery Partner → NGO

1. Donor posts food donation
2. NGO accepts donation
3. Delivery Partner assigned
4. OTP verified with donor
5. Food delivered to NGO

---

## Stage 2 – Food Testing

NGO manually tests food quality.

* Fresh → Distribution
* Moderate → Urgent Distribution
* Spoiled → Waste Management

---

## Stage 3 – Distribution

NGO → Delivery Partner → Beneficiary

1. NGO selects beneficiary
2. Delivery Partner assigned
3. Live navigation to beneficiary
4. Beneficiary OTP verification
5. Distribution completed

---

# 🛠️ Tech Stack

## Frontend

* HTML5
* CSS3
* Bootstrap
* AngularJS
* Leaflet Maps

---

## Backend

* FastAPI
* Python
* JWT Authentication
* RBAC Authorization
* WebSockets

---

## Database

* PostgreSQL

---

## Maps & Navigation

* Leaflet
* OSRM
* Mapbox

---

## Infrastructure

* Docker Ready
* REST APIs
* Environment Configuration
* Real-time Tracking
* Centralized Logging

---

# 📂 Project Structure

```bash
FoodBridge/
│
├── backend/
│   ├── app/
│   ├── routers/
│   ├── services/
│   ├── models/
│   └── main.py
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── services/
│   └── assets/
│
├── screenshots/
├── README.md
└── requirements.txt
```

---

# ⚙️ Installation & Setup

## 1. Clone Repository

```bash
git clone https://github.com/yourusername/FoodBridge.git
cd FoodBridge
```

---

## 2. Backend Setup

```bash
cd backend
python -m venv venv
```

### Activate Environment

#### Windows

```bash
venv\Scripts\activate
```

#### Linux/Mac

```bash
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. PostgreSQL Setup

Create database:

```sql
CREATE DATABASE foodbridge_db;
```

---

## 5. Configure Environment Variables

Create `.env`

```env
DATABASE_URL=postgresql://username:password@localhost/foodbridge_db

SECRET_KEY=your_secret_key

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=1440

MAPBOX_TOKEN=your_mapbox_token
```

---

## 6. Run Backend

```bash
uvicorn app.main:app --reload
```

Backend URL:

```text
http://localhost:8000
```

Swagger API Docs:

```text
http://localhost:8000/docs
```

---

## 7. Frontend Setup

```bash
cd frontend
npm install
npm start
```

Frontend URL:

```text
http://localhost:3000
```

---

# 🔐 Security Features

* JWT Authentication
* Role-Based Access Control (RBAC)
* OTP Verification
* Secure Password Hashing
* Protected APIs
* Rate Limiting

---

# 📊 Major Dashboards

## Donor Dashboard

* Post Donations
* Track Donations
* Donation History
* Impact Analytics
* Certificates

---

## NGO Dashboard

* Incoming Donations
* Food Testing
* Distribution Management
* Waste Management
* Delivery Tracking
* Analytics

---

## Delivery Partner Dashboard

* Active Tasks
* Live Navigation
* OTP Verification
* Route Tracking
* Achievements

---

# 📈 Future Enhancements

* AI Food Quality Detection
* Temperature Sensor Integration
* QR Verification
* Mobile App
* Push Notifications
* Predictive Demand Analysis
* Blockchain-based Food Traceability

---

# 🧪 Testing Scenarios

✅ Donor posts donation
✅ NGO accepts donation
✅ Delivery Partner assigned
✅ OTP verification works
✅ Live tracking works
✅ Food testing works
✅ Distribution works
✅ Beneficiary verification works
✅ Certificates generated automatically

---

# 📸 Screenshots

Screenshots here:

* Donor Dashboard
![alt text](<Screenshot 2026-04-13 170048.png>)

* NGO Dashboard
![alt text](<Screenshot 2026-04-13 170142.png>)

* Food Testing Module
![alt text](<Screenshot 2026-04-22 174331.png>)

* Distribution Management
![alt text](<Screenshot 2026-04-26 092154.png>)

---

# 👨‍💻 Team

FoodBridge Development Team

---

# 📜 License

This project is licensed under the MIT License.

---

# 🌍 Vision

FoodBridge aims to create a sustainable ecosystem where surplus food is safely redistributed to people in need through intelligent logistics, food safety validation, and real-time coordination.

---

# ⭐ Support

If you like this project, please give it a ⭐ on GitHub.
