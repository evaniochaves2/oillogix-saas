# =============================
# OilLogix MVP - FastAPI Backend
# =============================

from fastapi import FastAPI, Depends, HTTPException # pyright: ignore[reportMissingImports]
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

DATABASE_URL = "sqlite:///./oillogix.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

# =============================
# Database Model
# =============================

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    origin = Column(String)
    destination = Column(String)
    status = Column(String, default="Pending")
    eta = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# =============================
# Dependency
# =============================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================
# API Routes
# =============================

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

@app.get("/shipments/")
def get_shipments(db: Session = Depends(get_db)):
    return db.query(Shipment).all()

@app.put("/shipments/{shipment_id}")
def update_status(shipment_id: int, status: str, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    shipment.status = status
    shipment.last_updated = datetime.utcnow()
    db.commit()
    return shipment

@app.delete("/shipments/{shipment_id}")
def delete_shipment(shipment_id: int, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    db.delete(shipment)
    db.commit()
    return {"message": "Deleted"}


# =============================
# Simple Frontend (HTML)
# =============================

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>OilLogix Dashboard</title>
</head>
<body>
    <h1>Shipment Tracker</h1>

    <h2>Add Shipment</h2>
    <input id="name" placeholder="Name"><br>
    <input id="origin" placeholder="Origin"><br>
    <input id="destination" placeholder="Destination"><br>
    <input id="eta" placeholder="ETA"><br>
    <button onclick="addShipment()">Add</button>

    <h2>All Shipments</h2>
    <ul id="list"></ul>

<script>
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

async function updateStatus(id) {
    const status = prompt("Enter new status:");

    await fetch(`/shipments/${id}?status=${status}`, {
        method: 'PUT'
    });

    fetchShipments();
}

fetchShipments();
</script>
</body>
</html>
"""

from fastapi.responses import HTMLResponse # type: ignore

@app.get("/", response_class=HTMLResponse)
def home():
    return html_content

# =============================
# Run with:
# uvicorn main:app --reload
# =============================
print("APP LOADED")