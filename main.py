# ===============================
# OilLogix MVP - Enhanced Version
# ===============================

# -------- IMPORTS --------
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

# -------- DATABASE SETUP --------

DATABASE_URL = "sqlite:///./oillogix.db"

# Create DB engine (SQLite file)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# -------- FASTAPI APP --------
app = FastAPI()

# -------- DATABASE MODEL --------

class Shipment(Base):
    """
    Represents a shipment in the database
    """
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    origin = Column(String)
    destination = Column(String)
    status = Column(String, default="Pending")  # Default status
    eta = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

# Create table automatically
Base.metadata.create_all(bind=engine)

# -------- DB DEPENDENCY --------

def get_db():
    """
    Creates and closes DB session per request
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------- API ROUTES --------

# CREATE shipment
@app.post("/shipments/")
def create_shipment(name: str, origin: str, destination: str, eta: str, db: Session = Depends(get_db)):
    shipment = Shipment(
        name=name,
        origin=origin,
        destination=destination,
        eta=eta
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment

# READ all shipments
@app.get("/shipments/")
def get_shipments(status: str = None, db: Session = Depends(get_db)):
    """
    Optional filtering by status
    """
    query = db.query(Shipment)

    if status:
        query = query.filter(Shipment.status == status)

    return query.all()

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
# FRONTEND (HTML + CSS + JS)
# =============================

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>OilLogix Dashboard</title>

    <style>
        body { font-family: Arial; padding: 20px; }

        input, select, button {
            margin: 5px;
            padding: 8px;
        }

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

        .badge {
            padding: 5px 10px;
            border-radius: 12px;
            font-weight: bold;
        }

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
    </style>
</head>

<body>

<div class="topbar">
    <h1 id="title">Shipment Tracker</h1>

    <!-- LANGUAGE SELECTOR -->
    <select id="language" onchange="changeLanguage()">
        <option value="en">EN</option>
        <option value="pt">PT</option>
    </select>
</div>

<h2 id="addTitle">Add Shipment</h2>
<input id="name" placeholder="Name">
<input id="origin" placeholder="Origin">
<input id="destination" placeholder="Destination">
<input id="eta" placeholder="ETA">
<button onclick="addShipment()" id="addBtn">Add</button>

<h2 id="filterTitle">Filter</h2>
<select id="filter" onchange="fetchShipments()">
    <option value="">All</option>
    <option value="Pending">Pending</option>
    <option value="In Transit">In Transit</option>
    <option value="Delayed">Delayed</option>
    <option value="Delivered">Delivered</option>
</select>

<h2 id="shipmentsTitle">Shipments</h2>
<div id="list"></div>

<script>

// =============================
// LANGUAGE SYSTEM (SCALABLE)
// =============================

// Load saved language OR default to English
let currentLang = localStorage.getItem("lang") || "en";

// Translation dictionary
const translations = {
    en: {
        title: "Shipment Tracker",
        add: "Add Shipment",
        filter: "Filter",
        shipments: "Shipments",
        addBtn: "Add",
        all: "All",
        name: "Name",
        origin: "Origin",
        destination: "Destination",
        eta: "ETA",
        Pending: "Pending",
        "In Transit": "In Transit",
        Delayed: "Delayed",
        Delivered: "Delivered"
    },
    pt: {
        title: "Rastreamento de Cargas",
        add: "Adicionar Carga",
        filter: "Filtrar",
        shipments: "Cargas",
        addBtn: "Adicionar",
        all: "Todos",
        name: "Nome",
        origin: "Origem",
        destination: "Destino",
        eta: "ETA",
        Pending: "Pendente",
        "In Transit": "Em Transporte",
        Delayed: "Atrasado",
        Delivered: "Entregue"
    }
};

// Translation helper
function t(key) {
    return translations[currentLang][key] || key;
}

// Apply translations to UI
function applyTranslations() {
    document.getElementById("title").innerText = t("title");
    document.getElementById("addTitle").innerText = t("add");
    document.getElementById("filterTitle").innerText = t("filter");
    document.getElementById("shipmentsTitle").innerText = t("shipments");
    document.getElementById("addBtn").innerText = t("addBtn");

    document.getElementById("name").placeholder = t("name");
    document.getElementById("origin").placeholder = t("origin");
    document.getElementById("destination").placeholder = t("destination");
    document.getElementById("eta").placeholder = t("eta");
}

// Change language + persist
function changeLanguage() {
    currentLang = document.getElementById("language").value;

    // Save preference (important for SaaS UX)
    localStorage.setItem("lang", currentLang);

    applyTranslations();
    fetchShipments();
}

// =============================
// STATUS STYLE HELPER
// =============================

function getStatusClass(status) {
    return status.replace(" ", "-");
}

// =============================
// FETCH DATA (READY FOR BACKEND I18N)
// =============================

async function fetchShipments() {
    const filter = document.getElementById('filter').value;
    let url = '/shipments/';

    if (filter) {
        url += '?status=' + filter;
    }

    const res = await fetch(url);
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

            <span class="badge">${t(s.status)}</span><br><br>

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

// =============================
// CRUD FUNCTIONS
// =============================

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

async function updateStatus(id, status) {
    await fetch(`/shipments/${id}?status=${status}`, {
        method: 'PUT'
    });

    fetchShipments();
}

async function deleteShipment(id) {
    await fetch(`/shipments/${id}`, {
        method: 'DELETE'
    });

    fetchShipments();
}

// =============================
// INITIAL LOAD
// =============================

// Set dropdown to saved language
document.getElementById("language").value = currentLang;

// Apply UI language
applyTranslations();

// Load data
fetchShipments();

</script>

</body>
</html>
"""

# Serve frontend
@app.get("/", response_class=HTMLResponse)
def home():
    return html_content


# ====================================
# RUN COMMAND
# python3 -m uvicorn main:app --reload
# ====================================
