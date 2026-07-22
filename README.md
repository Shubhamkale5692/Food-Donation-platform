# FoodBridge - Smart Food Donation Platform

FoodBridge is a modern platform that connects surplus food from businesses to NGOs and volunteers for fast, tracked delivery.

This guide provides the exact steps to install and run the platform natively on Windows without using Docker.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your Windows machine:
1. **Python 3.11+**
2. **Node.js** (Only needed if you plan to do future frontend development)
3. **PostgreSQL (v14+)** for the database.
4. **Redis** (for background tasks like email and AI).

### Installing PostgreSQL & Redis natively on Windows
* **PostgreSQL:** Download from [EnterpriseDB](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads). Remember your password (e.g., `123456789`). Once installed, open pgAdmin and create a database named `foodbridge`.
* **Redis:** Download the `.msi` from [tporadowski/redis releases](https://github.com/tporadowski/redis/releases). Install it, and it will run automatically in the background on port 6379.

---

## ⚙️ Step-by-Step Setup

### 1. Configure Environment Variables
Navigate to the `backend/` folder and make sure your `.env` file is properly configured.
```env
# backend/.env
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_actual_postgres_password
POSTGRES_DB=foodbridge

CELERY_BROKER_URL=redis://localhost:6379/0
```

### 2. Backend Setup
Open a terminal in the root project folder, then run:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Initialize the Database
While your virtual environment is still active in the `backend` folder, run the setup scripts:

```powershell
python seed_data.py
```
*(This creates all database tables and populates the system with dummy users, NGOs, donors, and volunteers).*

---

## 🚀 How to Run the Platform

To run the platform locally, you will need **three separate terminals** running simultaneously.

### Terminal 1: Start the Backend API
```powershell
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```
*Your backend will be live at: http://localhost:8000*

### Terminal 2: Start the Background Worker (Celery)
Because you are on Windows, you must use the `--pool=solo` flag.
```powershell
cd backend
.\venv\Scripts\activate
celery -A app.workers.tasks worker --loglevel=info --pool=solo
```

### Terminal 3: Start the Frontend
The frontend is a static AngularJS application.
```powershell
cd frontend
python -m http.server 8080
```
*Your frontend will be live at: http://localhost:8080*

---

## 🔑 Test Accounts

You can log in to the platform at `http://localhost:8080` using any of the following pre-generated accounts (Password for all is the username + `123`):

* **Admin:** admin@foodbridge.org / admin123
* **NGO:** ngo1@foodbridge.org / ngo123
* **Donor:** donor1@foodbridge.org / donor123
* **Volunteer:** vol1@foodbridge.org / vol123
