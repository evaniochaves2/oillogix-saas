# =============================
# OilLogix SaaS - Auth + Multi-User
# =============================

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime, timedelta

# Auth libs
from passlib.context import CryptContext
from jose import jwt

# =============================
# CONFIG
# =============================

SECRET_KEY = "supersecretkey"  # change in production
ALGORITHM = "HS256"

DATABASE_URL = "sqlite:///./oillogix.db"

# =============================
# DB SETUP
# =============================

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

app = FastAPI()

# =============================
# SECURITY
# =============================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_token(data: dict):
    data["exp"] = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

# =============================
# MODELS
# =============================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)
    language = Column(String, default="en")

    shipments = relationship("Shipment", back_populates="owner")


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    origin = Column(String)
    destination = Column(String)
    status = Column(String, default="Pending")
    eta = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="shipments")


Base.metadata.create_all(bind=engine)

# =============================
# DB DEPENDENCY
# =============================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================
# AUTH HELPERS
# =============================

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = creds.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

# =============================
# AUTH ROUTES
# =============================

@app.post("/register")
def register(email: str, password: str, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(400, "User already exists")

    user = User(
        email=email,
        password=hash_password(password)
    )

    db.add(user)
    db.commit()

    return {"message": "User created"}

@app.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password):
        raise HTTPException(401, "Invalid credentials")

    token = create_token({"user_id": user.id})

    return {
        "access_token": token,
        "language": user.language
    }

# =============================
# SHIPMENTS (USER SCOPED)
# =============================

@app.post("/shipments/")
def create_shipment(
    name: str,
    origin: str,
    destination: str,
    eta: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    shipment = Shipment(
        name=name,
        origin=origin,
        destination=destination,
        eta=eta,
        owner=user
    )

    db.add(shipment)
    db.commit()
    return shipment


@app.get("/shipments/")
def get_shipments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return db.query(Shipment).filter(Shipment.user_id == user.id).all()


@app.put("/shipments/{id}")
def update_status(
    id: int,
    status: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    shipment = db.query(Shipment).filter(
        Shipment.id == id,
        Shipment.user_id == user.id
    ).first()

    if not shipment:
        raise HTTPException(404, "Not found")

    shipment.status = status
    shipment.last_updated = datetime.utcnow()

    db.commit()
    return shipment


@app.delete("/shipments/{id}")
def delete_shipment(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    shipment = db.query(Shipment).filter(
        Shipment.id == id,
        Shipment.user_id == user.id
    ).first()

    if not shipment:
        raise HTTPException(404, "Not found")

    db.delete(shipment)
    db.commit()
    return {"message": "Deleted"}

# =============================
# BASIC FRONTEND (LOGIN)
# =============================

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>OilLogix SaaS</title>

    <style>
        body { font-family: Arial; padding: 20px; }

        input, button {
            margin: 5px;
            padding: 8px;
        }

        .hidden { display: none; }

        .card {
            padding: 10px;
            margin: 10px 0;
            border-radius: 8px;
            border: 1px solid #ccc;
        }

        .Pending { background-color: #eee; }
        .In-Transit { background-color: #cce5ff; }
        .Delayed { background-color: #ffcccc; }
        .Delivered { background-color: #ccffcc; }
    </style>
</head>

<body>

<!-- ========================= -->
<!-- LOGIN SCREEN -->
<!-- ========================= -->

<div id="loginView">
    <h2>Login</h2>
    <input id="email" placeholder="Email">
    <input id="password" type="password" placeholder="Password">
    <br>
    <button onclick="login()">Login</button>
    <button onclick="register()">Register</button>
</div>

<!-- ========================= -->
<!-- DASHBOARD -->
<!-- ========================= -->

<div id="appView" class="hidden">

    <h1>🚚 OilLogix Dashboard</h1>
    <button onclick="logout()">Logout</button>

    <h2>Add Shipment</h2>
    <input id="name" placeholder="Name">
    <input id="origin" placeholder="Origin">
    <input id="destination" placeholder="Destination">
    <input id="eta" placeholder="ETA">
    <button onclick="addShipment()">Add</button>

    <h2>Shipments</h2>
    <div id="list"></div>

</div>

<script>

// =============================
// AUTH STATE
// =============================

let token = localStorage.getItem("token") || "";

// =============================
// VIEW SWITCHING
// =============================

function showApp() {
    document.getElementById("loginView").classList.add("hidden");
    document.getElementById("appView").classList.remove("hidden");
}

function showLogin() {
    document.getElementById("loginView").classList.remove("hidden");
    document.getElementById("appView").classList.add("hidden");
}

// =============================
// AUTH FUNCTIONS
// =============================

async function login() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const res = await fetch(`/login?email=${email}&password=${password}`, {
        method: "POST"
    });

    const data = await res.json();

    if (data.access_token) {
        token = data.access_token;

        // Save token
        localStorage.setItem("token", token);

        showApp();
        fetchShipments();
    } else {
        alert("Login failed");
    }
}

async function register() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    await fetch(`/register?email=${email}&password=${password}`, {
        method: "POST"
    });

    alert("User created! Now login.");
}

function logout() {
    token = "";
    localStorage.removeItem("token");
    showLogin();
}

// =============================
// AUTH HEADER
// =============================

function authHeaders() {
    return {
        "Authorization": "Bearer " + token
    };
}

// =============================
// SHIPMENTS
// =============================

function getStatusClass(status) {
    return status.replace(" ", "-");
}

async function fetchShipments() {
    const res = await fetch('/shipments/', {
        headers: authHeaders()
    });

    if (res.status === 401) {
        logout();
        return;
    }

    const data = await res.json();

    const list = document.getElementById('list');
    list.innerHTML = '';

    data.forEach(s => {
        const div = document.createElement('div');
        div.className = 'card ' + getStatusClass(s.status);

        div.innerHTML = `
            <strong>${s.name}</strong><br>
            ${s.origin} → ${s.destination}<br>
            ETA: ${s.eta}<br>
            Status: ${s.status}<br><br>

            <select onchange="updateStatus(${s.id}, this.value)">
                <option ${s.status=='Pending'?'selected':''}>Pending</option>
                <option ${s.status=='In Transit'?'selected':''}>In Transit</option>
                <option ${s.status=='Delayed'?'selected':''}>Delayed</option>
                <option ${s.status=='Delivered'?'selected':''}>Delivered</option>
            </select>

            <button onclick="deleteShipment(${s.id})">Delete</button>
        `;

        list.appendChild(div);
    });
}

async function addShipment() {
    const name = document.getElementById('name').value;
    const origin = document.getElementById('origin').value;
    const destination = document.getElementById('destination').value;
    const eta = document.getElementById('eta').value;

    await fetch(`/shipments/?name=${name}&origin=${origin}&destination=${destination}&eta=${eta}`, {
        method: 'POST',
        headers: authHeaders()
    });

    fetchShipments();
}

async function updateStatus(id, status) {
    await fetch(`/shipments/${id}?status=${status}`, {
        method: 'PUT',
        headers: authHeaders()
    });

    fetchShipments();
}

async function deleteShipment(id) {
    await fetch(`/shipments/${id}`, {
        method: 'DELETE',
        headers: authHeaders()
    });

    fetchShipments();
}

// =============================
// INITIAL LOAD
// =============================

if (token) {
    showApp();
    fetchShipments();
} else {
    showLogin();
}

</script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return html_content
