# =============================
# OilLogix MVP - FastAPI Backend
# =============================

# FastAPI for building the API
from fastapi import FastAPI, Depends, HTTPException  # pyright: ignore[reportMissingImports]

# SQLAlchemy for database interaction (ORM)
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Used for timestamps
from datetime import datetime


# =============================
# Database Configuration
# =============================

# SQLite database file (stored locally in project folder)
DATABASE_URL = "sqlite:///./oillogix.db"

# Create database engine (connection to DB)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create session factory (each request gets its own DB session)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all database models
Base = declarative_base()


# =============================
# FastAPI App Initialization
# =============================

app = FastAPI()


# =============================
# Database Model
# =============================

# This class represents the "shipments" table in the database
class Shipment(Base):
    __tablename__ = "shipments"  # table name

    id = Column(Integer, primary_key=True, index=True)  # unique ID
    name = Column(String, index=True)                   # shipment name
    origin = Column(String)                             # where it starts
    destination = Column(String)                        # where it's going
    status = Column(String, default="Pending")          # current status
    eta = Column(String)                                # estimated arrival
    last_updated = Column(DateTime, default=datetime.utcnow)  # timestamp


# Create the table in the database if it doesn't exist
Base.metadata.create_all(bind=engine)


# =============================
# Dependency (Database Session)
# =============================

# This function provides a DB session to each API request
def get_db():
    db = SessionLocal()  # create session
    try:
        yield db         # give session to route
    finally:
        db.close()       # always close after request


# =============================
# API Routes
# =============================

# CREATE a new shipment
@app.post("/shipments/")
def create_shipment(
    name: str,
    origin: str,
    destination: str,
    eta: str,
    db: Session = Depends(get_db)
):
    # Create new shipment object
    shipment = Shipment(
        name=name,
        origin=origin,
        destination=destination,
        eta=eta
    )

    # Save to database
    db.add(shipment)
    db.commit()
    db.refresh(shipment)  # get updated data (like ID)

    return shipment


# READ all shipments
@app.get("/shipments/")
def get_shipments(db: Session = Depends(get_db)):
    # Return all rows from shipments table
    return db.query(Shipment).all()


# UPDATE shipment status
@app.put("/shipments/{shipment_id}")
def update_status(shipment_id: int, status: str, db: Session = Depends(get_db)):
    # Find shipment by ID
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()

    # If not found → return error
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Update fields
    shipment.status = status
    shipment.last_updated = datetime.utcnow()

    # Save changes
    db.commit()

    return shipment


# DELETE a shipment
@app.delete("/shipments/{shipment_id}")
def delete_shipment(shipment_id: int, db: Session = Depends(get_db)):
    # Find shipment
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()

    # If not found → error
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Delete from DB
    db.delete(shipment)
    db.commit()

    return {"message": "Deleted"}


# =============================
# Simple Frontend (HTML + JS)
# =============================

# Basic frontend UI served directly from FastAPI
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>OilLogix Dashboard</title>
</head>
<body>
    <h1>Shipment Tracker</h1>

    <!-- Form to add shipment -->
    <h2>Add Shipment</h2>
    <input id="name" placeholder="Name"><br>
    <input id="origin" placeholder="Origin"><br>
    <input id="destination" placeholder="Destination"><br>
    <input id="eta" placeholder="ETA"><br>
    <button onclick="addShipment()">Add</button>

    <!-- List of shipments -->
    <h2>All Shipments</h2>
    <ul id="list"></ul>

<script>

// Fetch all shipments from backend
async function fetchShipments() {
    const res = await fetch('/shipments/');
    const data = await res.json();

    const list = document.getElementById('list');
    list.innerHTML = '';

    // Display each shipment
    data.forEach(s => {
        const li = document.createElement('li');
        li.innerHTML = `${s.name} - ${s.status} 
        <button onclick="updateStatus(${s.id})">Update</button>`;
        list.appendChild(li);
    });
}

// Add a new shipment
async function addShipment() {
    const name = document.getElementById('name').value;
    const origin = document.getElementById('origin').value;
    const destination = document.getElementById('destination').value;
    const eta = document.getElementById('eta').value;

    await fetch(`/shipments/?name=${name}&origin=${origin}&destination=${destination}&eta=${eta}`, {
        method: 'POST'
    });

    fetchShipments(); // refresh list
}

// Update shipment status
async function updateStatus(id) {
    const status = prompt("Enter new status:");

    await fetch(`/shipments/${id}?status=${status}`, {
        method: 'PUT'
    });

    fetchShipments(); // refresh list
}

// Load shipments on page load
fetchShipments();

</script>
</body>
</html>
"""

# Used to return HTML instead of JSON
from fastapi.responses import HTMLResponse  # type: ignore


# Root route → serves the frontend UI
@app.get("/", response_class=HTMLResponse)
def home():
    return html_content


# ====================================
# Run with:
# python3 -m uvicorn main:app --reload
# ====================================
