# =============================
# OilLogix SaaS - FULL I18N VERSION
# =============================

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import datetime

# =============================
# DATABASE SETUP
# =============================

DATABASE_URL = "sqlite:///./oillogix.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

app = FastAPI()

# =============================
# TRANSLATIONS (BACKEND)
# =============================

translations = {
    "en": {
        "shipment_not_found": "Shipment not found",
        "deleted": "Deleted successfully"
    },
    "pt": {
        "shipment_not_found": "Carga não encontrada",
        "deleted": "Excluído com sucesso"
    }
}

def t(lang: str, key: str):
    return translations.get(lang, translations["en"]).get(key, key)

# =============================
# MODEL
# =============================

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    origin = Column(String)
    destination = Column(String)
    status = Column(String, default="Pending")
    eta = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

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
# API ROUTES (WITH LANGUAGE)
# =============================

@app.get("/shipments/")
def get_shipments(
    status: str = None,
    lang: str = Query("en"),
    db: Session = Depends(get_db)
):
    query = db.query(Shipment)
    if status:
        query = query.filter(Shipment.status == status)
    return query.all()

@app.post("/shipments/")
def create_shipment(
    name: str,
    origin: str,
    destination: str,
    eta: str,
    db: Session = Depends(get_db)
):
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

@app.put("/shipments/{shipment_id}")
def update_status(
    shipment_id: int,
    status: str,
    lang: str = Query("en"),
    db: Session = Depends(get_db)
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(404, t(lang, "shipment_not_found"))

    shipment.status = status
    shipment.last_updated = datetime.utcnow()
    db.commit()
    return shipment

@app.delete("/shipments/{shipment_id}")
def delete_shipment(
    shipment_id: int,
    lang: str = Query("en"),
    db: Session = Depends(get_db)
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(404, t(lang, "shipment_not_found"))

    db.delete(shipment)
    db.commit()
    return {"message": t(lang, "deleted")}

# =============================
# FRONTEND (FULL I18N)
# =============================

html_content = """
<!DOCTYPE html>
<html>
<head>
<title>OilLogix SaaS</title>

<style>
body { font-family: Arial; padding: 20px; }
.card { padding: 10px; margin: 10px 0; border-radius: 8px; }
.Pending { background:#eee; }
.In-Transit { background:#cce5ff; }
.Delayed { background:#ffcccc; }
.Delivered { background:#ccffcc; }
.hidden { display:none; }
</style>
</head>

<body>

<div id="loginView">
<h2 id="loginTitle"></h2>
<input id="email" placeholder="Email">
<input id="password" type="password" placeholder="Password">
<br>
<button onclick="login()" id="loginBtn"></button>
<button onclick="register()" id="registerBtn"></button>
</div>

<div id="appView" class="hidden">

<h1 id="title"></h1>

<select id="language" onchange="changeLanguage()">
<option value="en">EN</option>
<option value="pt">PT</option>
</select>

<button onclick="logout()" id="logoutBtn"></button>

<h2 id="addTitle"></h2>
<input id="name">
<input id="origin">
<input id="destination">
<input id="eta">
<button onclick="addShipment()" id="addBtn"></button>

<h2 id="filterTitle"></h2>
<select id="filter" onchange="fetchShipments()"></select>

<div id="list"></div>

</div>

<script>

// =============================
// LANGUAGE SYSTEM (FRONTEND)
// =============================

let currentLang = localStorage.getItem("lang") || "en";

const translations = {
en: {
title:"Shipment Tracker",
add:"Add Shipment",
filter:"Filter",
login:"Login",
register:"Register",
logout:"Logout",
delete:"Delete",
name:"Name",
origin:"Origin",
destination:"Destination",
eta:"ETA",
all:"All",
Pending:"Pending",
"In Transit":"In Transit",
Delayed:"Delayed",
Delivered:"Delivered"
},
pt: {
title:"Rastreamento de Cargas",
add:"Adicionar Carga",
filter:"Filtrar",
login:"Entrar",
register:"Registrar",
logout:"Sair",
delete:"Excluir",
name:"Nome",
origin:"Origem",
destination:"Destino",
eta:"ETA",
all:"Todos",
Pending:"Pendente",
"In Transit":"Em Transporte",
Delayed:"Atrasado",
Delivered:"Entregue"
}
};

function t(key){
return translations[currentLang][key] || key;
}

// =============================
// APPLY TRANSLATIONS
// =============================

function applyTranslations(){
document.getElementById("title").innerText = t("title");
document.getElementById("addTitle").innerText = t("add");
document.getElementById("filterTitle").innerText = t("filter");

document.getElementById("loginBtn").innerText = t("login");
document.getElementById("registerBtn").innerText = t("register");
document.getElementById("logoutBtn").innerText = t("logout");
document.getElementById("addBtn").innerText = t("add");

document.getElementById("name").placeholder = t("name");
document.getElementById("origin").placeholder = t("origin");
document.getElementById("destination").placeholder = t("destination");
document.getElementById("eta").placeholder = t("eta");
}

// =============================
// FILTER TRANSLATION
// =============================

function updateFilter(){
document.getElementById("filter").innerHTML = `
<option value="">${t("all")}</option>
<option value="Pending">${t("Pending")}</option>
<option value="In Transit">${t("In Transit")}</option>
<option value="Delayed">${t("Delayed")}</option>
<option value="Delivered">${t("Delivered")}</option>
`;
}

// =============================
// LANGUAGE SWITCH
// =============================

function changeLanguage(){
currentLang = document.getElementById("language").value;
localStorage.setItem("lang", currentLang);
applyTranslations();
updateFilter();
fetchShipments();
}

// =============================
// DATE FORMAT (LOCALE)
// =============================

function formatDate(dateStr){
return new Date(dateStr).toLocaleString(currentLang);
}

// =============================
// FETCH SHIPMENTS
// =============================

async function fetchShipments(){
const filter = document.getElementById("filter").value;

let url = `/shipments/?lang=${currentLang}`;
if(filter) url += `&status=${filter}`;

const res = await fetch(url);
const data = await res.json();

const list = document.getElementById("list");
list.innerHTML = "";

data.forEach(s=>{
const div = document.createElement("div");
div.className = "card " + s.status.replace(" ","-");

div.innerHTML = `
<strong>${s.name}</strong><br>
${s.origin} → ${s.destination}<br>
ETA: ${s.eta}<br>
Updated: ${formatDate(s.last_updated)}<br>
<b>${t(s.status)}</b><br><br>

<select onchange="updateStatus(${s.id}, this.value)">
<option ${s.status=="Pending"?"selected":""}>Pending</option>
<option ${s.status=="In Transit"?"selected":""}>In Transit</option>
<option ${s.status=="Delayed"?"selected":""}>Delayed</option>
<option ${s.status=="Delivered"?"selected":""}>Delivered</option>
</select>

<button onclick="deleteShipment(${s.id})">${t("delete")}</button>
`;

list.appendChild(div);
});
}

// =============================
// CRUD ACTIONS
// =============================

async function addShipment(){
await fetch(`/shipments/?name=${name.value}&origin=${origin.value}&destination=${destination.value}&eta=${eta.value}`);
fetchShipments();
}

async function updateStatus(id,status){
await fetch(`/shipments/${id}?status=${status}&lang=${currentLang}`,{method:"PUT"});
fetchShipments();
}

async function deleteShipment(id){
await fetch(`/shipments/${id}?lang=${currentLang}`,{method:"DELETE"});
fetchShipments();
}

// =============================
// INIT
// =============================

document.getElementById("language").value = currentLang;
applyTranslations();
updateFilter();
fetchShipments();

</script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return html_content
