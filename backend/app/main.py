from datetime import datetime, timedelta, time
from pathlib import Path
from collections import defaultdict
from typing import Optional

from fastapi import FastAPI, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db, SessionLocal
from .models import Admin, Slot, Booking
from .auth import (
    COOKIE_NAME,
    COOKIE_MAX_AGE,
    get_current_admin,
    require_admin,
    hash_password,
    verify_password,
    make_session_token,
    seed_default_admin,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="RDV École", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def fmt_jour(dt: datetime) -> str:
    return f"{JOURS_FR[dt.weekday()]} {dt.day} {MOIS_FR[dt.month - 1]} {dt.year}"


def fmt_heure(dt: datetime) -> str:
    return dt.strftime("%H:%M")


templates.env.filters["jour"] = fmt_jour
templates.env.filters["heure"] = fmt_heure


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_default_admin(db)
    finally:
        db.close()


def _group_slots_by_day(slots: list[Slot]) -> list[dict]:
    groups: dict = defaultdict(list)
    for s in slots:
        groups[s.start_at.date()].append(s)
    days = []
    for day in sorted(groups.keys()):
        items = sorted(groups[day], key=lambda s: s.start_at)
        days.append({"date": day, "label": fmt_jour(datetime.combine(day, time())), "slots": items})
    return days


# -----------------------------
# Vue parents (public)
# -----------------------------

@app.get("/", response_class=HTMLResponse)
def page_parents(request: Request, db: Session = Depends(get_db)):
    now = datetime.now().replace(second=0, microsecond=0)
    slots = (
        db.query(Slot)
        .filter(Slot.start_at >= now)
        .order_by(Slot.start_at.asc())
        .all()
    )
    days = _group_slots_by_day(slots)
    return templates.TemplateResponse(
        "parents.html",
        {"request": request, "days": days, "admin": get_current_admin(request)},
    )


@app.post("/reserver/{slot_id}")
def reserver(
    slot_id: int,
    request: Request,
    child_first_name: str = Form(...),
    child_last_name: str = Form(...),
    db: Session = Depends(get_db),
):
    slot = db.get(Slot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Créneau introuvable")
    if slot.start_at < datetime.now():
        raise HTTPException(status_code=400, detail="Ce créneau est passé")

    first = child_first_name.strip()
    last = child_last_name.strip()
    if not first or not last:
        raise HTTPException(status_code=400, detail="Prénom et nom requis")

    booking = Booking(
        slot_id=slot.id,
        child_first_name=first,
        child_last_name=last,
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            "deja_reserve.html",
            {"request": request, "slot": slot},
            status_code=409,
        )
    db.refresh(booking)
    return templates.TemplateResponse(
        "confirmation.html",
        {"request": request, "slot": slot, "booking": booking},
    )


# -----------------------------
# Auth admin
# -----------------------------

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    if get_current_admin(request):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/admin/login")
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = db.query(Admin).filter(Admin.username == username.strip()).first()
    if not admin or not verify_password(password, admin.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Identifiants invalides"},
            status_code=401,
        )
    token = make_session_token(admin.id)
    target = "/admin/password" if admin.must_change_password else "/admin"
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/admin/password", response_class=HTMLResponse)
def admin_password_form(request: Request, admin: Admin = Depends(require_admin)):
    return templates.TemplateResponse(
        "change_password.html",
        {"request": request, "admin": admin, "error": None, "success": False},
    )


@app.post("/admin/password")
def admin_password_change(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin),
):
    if not verify_password(current_password, admin.password_hash):
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "admin": admin, "error": "Mot de passe actuel incorrect", "success": False},
            status_code=400,
        )
    if len(new_password) < 8:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "admin": admin, "error": "Le nouveau mot de passe doit faire au moins 8 caractères", "success": False},
            status_code=400,
        )
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "admin": admin, "error": "La confirmation ne correspond pas", "success": False},
            status_code=400,
        )
    admin.password_hash = hash_password(new_password)
    admin.must_change_password = False
    db.add(admin)
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


# -----------------------------
# Dashboard admin
# -----------------------------

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin),
):
    if admin.must_change_password:
        return RedirectResponse(url="/admin/password", status_code=303)
    slots = db.query(Slot).order_by(Slot.start_at.asc()).all()
    days = _group_slots_by_day(slots)
    nb_total = len(slots)
    nb_reserved = sum(1 for s in slots if s.is_booked)
    nb_libres = nb_total - nb_reserved
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "admin": admin,
            "days": days,
            "nb_total": nb_total,
            "nb_reserved": nb_reserved,
            "nb_libres": nb_libres,
        },
    )


@app.post("/admin/slots")
def admin_add_slot(
    request: Request,
    date: str = Form(...),
    heure: str = Form(...),
    duration_minutes: int = Form(15),
    label: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin),
):
    try:
        start = datetime.strptime(f"{date} {heure}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date ou heure invalide")
    duration = max(5, min(180, int(duration_minutes)))
    slot = Slot(
        start_at=start,
        duration_minutes=duration,
        label=(label.strip() if label else None) or None,
    )
    db.add(slot)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # créneau déjà existant à ce datetime
        pass
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/slots/bulk")
def admin_add_bulk(
    request: Request,
    date: str = Form(...),
    heure_debut: str = Form(...),
    heure_fin: str = Form(...),
    duration_minutes: int = Form(15),
    label: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin),
):
    try:
        start = datetime.strptime(f"{date} {heure_debut}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{date} {heure_fin}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format date/heure invalide")
    if end <= start:
        raise HTTPException(status_code=400, detail="Heure de fin après l'heure de début")
    duration = max(5, min(180, int(duration_minutes)))
    label_clean = (label.strip() if label else None) or None
    cur = start
    added = 0
    while cur + timedelta(minutes=duration) <= end:
        existing = db.query(Slot).filter(Slot.start_at == cur).first()
        if not existing:
            db.add(Slot(start_at=cur, duration_minutes=duration, label=label_clean))
            added += 1
        cur = cur + timedelta(minutes=duration)
    if added:
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/slots/{slot_id}/delete")
def admin_delete_slot(
    slot_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin),
):
    slot = db.get(Slot, slot_id)
    if slot:
        db.delete(slot)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/bookings/{booking_id}/cancel")
def admin_cancel_booking(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin),
):
    booking = db.get(Booking, booking_id)
    if booking:
        db.delete(booking)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)
