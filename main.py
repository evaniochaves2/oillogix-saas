# =============================
# OilLogix SaaS - Full Backend
# =============================

import os
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship

from jose import jwt, JWTError
from passlib.context import CryptContext

import stripe
from dotenv import load_dotenv

# =============================
# ENV CONFIG
# =============================
load_dotenv()

DATABASE_URL = "sqlite:///./oillogix.db"
SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

DOMAIN = os.getenv("DOMAIN", "http://localhost:8001")

# Stripe price IDs for tiers
STRIPE_PRICE_FREE = "price_free"
STRIPE_PRICE_PRO = "price_pro"
STRIPE_PRICE_ENT = "price_enterprise"

stripe.api_key = STRIPE_SECRET_KEY

# =============================
# DATABASE SETUP
# =============================
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =============================
# PASSWORD HASHING
# =============================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# =============================
# MODELS
# =============================

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    hashed_password = Column(String)

    organization_id = Column(Integer, ForeignKey("organizations.id"))
    organization = relationship("Organization")

    stripe_customer_id = Column(String, nullable=True)
    subscription_status = Column(String, default="inactive")
    plan = Column(String, default="free")  # free, pro, enterprise


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    origin = Column(String)
    destination = Column(String)
    status = Column(String, default="Pending")
    eta = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

    organization_id = Column(Integer, ForeignKey("organizations.id"))


Base.metadata.create_all(bind=engine)

# =============================
# APP INIT
# =============================
app = FastAPI()

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
def create_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = None, db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(401, "Missing token")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    return user

# =============================
# FEATURE GATING
# =============================
def get_plan_limits(plan: str):
    if plan == "free":
        return {"shipments_limit": 5}
    elif plan == "pro":
        return {"shipments_limit": 100}
    elif plan == "enterprise":
        return {"shipments_limit": float("inf")}
    return {"shipments_limit": 0}

def enforce_shipment_limit(user: User, db: Session):
    limits = get_plan_limits(user.plan)

    count = db.query(Shipment).filter(
        Shipment.organization_id == user.organization_id
    ).count()

    if count >= limits["shipments_limit"]:
        raise HTTPException(
            status_code=403,
            detail="Shipment limit reached. Upgrade your plan."
        )

# =============================
# AUTH ROUTES
# =============================
@app.post("/register")
def register(email: str, password: str, db: Session = Depends(get_db)):
    org = Organization(name=f"{email}'s Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    hashed = pwd_context.hash(password)

    user = User(
        email=email,
        hashed_password=hashed,
        organization_id=org.id,
        plan="free"
    )

    db.add(user)
    db.commit()

    return {"message": "User created"}

@app.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()

    if not user or not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    token = create_token({"user_id": user.id})

    return {"access_token": token}

# =============================
# STRIPE: CREATE CHECKOUT
# =============================
@app.post("/billing/create-checkout")
def create_checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email)
        user.stripe_customer_id = customer["id"]
        db.commit()

    price_map = {
        "free": STRIPE_PRICE_FREE,
        "pro": STRIPE_PRICE_PRO,
        "enterprise": STRIPE_PRICE_ENT
    }

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_map[user.plan], "quantity": 1}],
        success_url=f"{DOMAIN}/success",
        cancel_url=f"{DOMAIN}/cancel"
    )

    return {"url": session.url}

# =============================
# STRIPE WEBHOOK
# =============================
@app.post("/billing/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(400, "Invalid webhook")

    data = event["data"]["object"]

    # When subscription is created
    if event["type"] == "checkout.session.completed":
        customer_id = data["customer"]

        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()

        if user:
            user.subscription_status = "active"
            user.plan = "pro"  # upgrade default (can map dynamically)
            db.commit()

    # Subscription updates
    if event["type"] == "customer.subscription.updated":
        customer_id = data["customer"]
        status = data["status"]

        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()

        if user:
            user.subscription_status = status
            db.commit()

    return {"status": "ok"}

# =============================
# SHIPMENT ROUTES
# =============================
@app.post("/shipments/")
def create_shipment(
    name: str,
    origin: str,
    destination: str,
    eta: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 🔒 Feature gating
    enforce_shipment_limit(user, db)

    shipment = Shipment(
        name=name,
        origin=origin,
        destination=destination,
        eta=eta,
        organization_id=user.organization_id
    )

    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    return shipment

@app.get("/shipments/")
def get_shipments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Shipment).filter(
        Shipment.organization_id == user.organization_id
    ).all()

# =============================
# SIMPLE FRONTEND
# =============================
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>OilLogix SaaS</title>
</head>
<body>
    <h1>Dashboard</h1>

    <button onclick="upgrade()">Upgrade Plan</button>

    <h2>Create Shipment</h2>
    <input id="name" placeholder="Name">
    <input id="origin" placeholder="Origin">
    <input id="destination" placeholder="Destination">
    <input id="eta" placeholder="ETA">
    <button onclick="addShipment()">Add</button>

    <h2>Shipments</h2>
    <ul id="list"></ul>

<script>
let token = localStorage.getItem("token");

async function fetchShipments() {
    const res = await fetch('/shipments/', {
        headers: { "Authorization": token }
    });
    const data = await res.json();

    const list = document.getElementById('list');
    list.innerHTML = '';

    data.forEach(s => {
        const li = document.createElement('li');
        li.innerText = `${s.name} - ${s.status}`;
        list.appendChild(li);
    });
}

async function addShipment() {
    const name = document.getElementById('name').value;
    const origin = document.getElementById('origin').value;
    const destination = document.getElementById('destination').value;
    const eta = document.getElementById('eta').value;

    await fetch(`/shipments/?name=${name}&origin=${origin}&destination=${destination}&eta=${eta}`, {
        method: 'POST',
        headers: { "Authorization": token }
    });

    fetchShipments();
}

async function upgrade() {
    const res = await fetch('/billing/create-checkout', {
        method: 'POST',
        headers: { "Authorization": token }
    });

    const data = await res.json();
    window.location.href = data.url;
}

fetchShipments();
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return html_content

# =============================
# RUN:
# uvicorn main:app --reload
# =============================
