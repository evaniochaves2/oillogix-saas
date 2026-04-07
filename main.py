# =============================
# OilLogix MVP - FULL COMMENTED VERSION
# =============================

# FastAPI is the web framework used to build the API
from fastapi import FastAPI, Depends, HTTPException

# SQLAlchemy is used to interact with the database
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Used for timestamps
from datetime import datetime

# =============================
# DATABASE SETUP
# =============================

# SQLite database (simple file-based DB for MVP)
DATABASE_URL = "sqlite:///./oillogix.db"

# Create database engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # needed for SQLite
)

# Create session factory (used to talk to DB)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# =============================
# FASTAPI APP
# =============================

app = FastAPI()

# =============================
# DATABASE MODEL (TABLE)
# =============================

class Shipment(Base):
    __tablename__ = "shipments"  # table name

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # shipment name
    origin = Column(String)  # where it starts
    destination = Column(String)  # where it goes
    status = Column(String, default="Pending")  # current status
    eta = Column(String)  # estimated arrival
    last_updated = Column(DateTime, default=datetime.utcnow)

# Create tables in DB
Base.metadata.create_all(bind=engine)

# =============================
# DATABASE DEPENDENCY
# =============================

# This function creates a DB session for each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================
# API ROUTES (BACKEND LOGIC)
# =============================

# CREATE a new shipment
@app.post("/shipments/")
def create_shipment(name: str, origin: str, destination: str, eta: str, db: Session = Depends(get_db)):
    shipment = Shipment(
        name=name,
        origin=origin,
        destination=destination,
        eta=eta
    )
    db.add(shipment)  # add to DB
    db.commit()       # save changes
    db.refresh(shipment)  # reload object
    return shipment

# READ all shipments
@app.get("/shipments/")
def get_shipments(db: Session = Depends(get_db)):
    return db.query(Shipment).all()

# UPDATE shipment status
@app.put("/shipments/{shipment_id}")
def update_status(shipment_id: int, status: str, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    shipment.status = status
    shipment.last_updated = datetime.utcnow()

    db.commit()
    return shipment

# DELETE shipment
@app.delete("/shipments/{shipment_id}")
def delete_shipment(shipment_id: int, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    db.delete(shipment)
    db.commit()

    return {"message": "Deleted"}

# =============================
# FRONTEND (HTML + JAVASCRIPT)
# =============================

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>OilLogix Dashboard</title>
</head>
<body>

    <!-- Language Selector -->
    <select id="lang" onchange="setLanguage()">
      <option value="en">English</option>
      <option value="pt">Português</option>
    </select>

    <!-- Title -->
    <h1 id="title">Shipment Tracker</h1>

    <!-- Add Shipment Form -->
    <h2 id="add_title">Add Shipment</h2>
    <input id="name" placeholder="Name"><br>
    <input id="origin" placeholder="Origin"><br>
    <input id="destination" placeholder="Destination"><br>
    <input id="eta" placeholder="ETA"><br>
    <button onclick="addShipment()">Add</button>

    <!-- Shipment List -->
    <h2 id="list_title">All Shipments</h2>
    <ul id="list"></ul>

<script>

// =============================
// TRANSLATIONS (EN + PT)
// =============================

let currentLang = 'en';

const translations = {
  en: {
    title: "Shipment Tracker",
    add: "Add Shipment",
    list: "All Shipments"
  },
  pt: {
    title: "Rastreamento de Encomendas",
    add: "Adicionar Envio",
    list: "Todos os Envios"
  }
};

// Change language
function setLanguage() {
  currentLang = document.getElementById("lang").value;
  renderText();
}

// Apply translations to UI
function renderText() {
  document.getElementById("title").innerText = translations[currentLang].title;
  document.getElementById("add_title").innerText = translations[currentLang].add;
  document.getElementById("list_title").innerText = translations[currentLang].list;
}

// =============================
// API CALLS
// =============================

// Fetch shipments from backend
async function fetchShipments() {
    const res = await fetch('/shipments/');
    const data = await res.json();

    const list = document.getElementById('list');
    list.innerHTML = '';

    data.forEach(s => {
        const li = document.createElement('li');
        li.innerHTML = `${s.name} - ${s.status} 
        <button onclick="updateStatus(${s.id})">Update</button>`;
        list.appendChild(li);
    });
}

// Add new shipment
async function addShipment() {
    const name = document.getElementById('name').value;
    const origin = document.getElementById('origin').value;
    const destination = document.getElementById('destination').value;
    const eta = document.getElementById('eta').value;

    await fetch(`/shipments/?name=${name}&origin=${origin}&destination=${destination}&eta=${eta}`, {
        method: 'POST'
    });

    fetchShipments();
}

// Update shipment status
async function updateStatus(id) {
    const status = prompt("Enter new status:");

    await fetch(`/shipments/${id}?status=${status}`, {
        method: 'PUT'
    });

    fetchShipments();
}

// Initial load
fetchShipments();

</script>
</body>
</html>
"""

# =============================
# SERVE HTML PAGE
# =============================

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def home():
    return html_content

# ====================================
# Run with:
# python3 -m uvicorn main:app --reload
# ====================================
