import re
from datetime import datetime, timedelta, time
from pathlib import Path
from collections import defaultdict
from typing import Optional, List

from fastapi import FastAPI, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db, SessionLocal
from .models import (
    User, Slot, Booking,
    CLASS_LEVELS, CLASS_LEVEL_KEYS, CLASS_LEVEL_LABELS,
    ROLE_SUPER_ADMIN, ROLE_TEACHER,
)
from .auth import (
    COOKIE_NAME, COOKIE_MAX_AGE, COOKIE_SECURE,
    DEFAULT_TEACHER_PASSWORD,
    get_current_user, require_user, require_super_admin,
    hash_password, verify_password, make_session_token,
    seed_default_super_admin,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="RDV École", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Service Worker servi depuis la racine (scope = '/')
@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


# Manifest aussi exposé à la racine pour les implémentations qui scrutent /manifest.webmanifest
@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
    )

USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def fmt_jour(dt: datetime) -> str:
    return f"{JOURS_FR[dt.weekday()]} {dt.day} {MOIS_FR[dt.month - 1]} {dt.year}"


def fmt_heure(dt: datetime) -> str:
    return dt.strftime("%H:%M")


templates.env.filters["jour"] = fmt_jour
templates.env.filters["heure"] = fmt_heure
templates.env.globals["CLASS_LEVELS"] = CLASS_LEVELS
templates.env.globals["CLASS_LEVEL_LABELS"] = CLASS_LEVEL_LABELS


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_default_super_admin(db)
    finally:
        db.close()


def _set_session_cookie(response, user_id: int) -> None:
    token = make_session_token(user_id)
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=COOKIE_MAX_AGE,
        httponly=True, samesite="lax",
        secure=COOKIE_SECURE,
    )


def _group_slots_by_day(slots: List[Slot]) -> list:
    groups = defaultdict(list)
    for s in slots:
        groups[s.start_at.date()].append(s)
    days = []
    for day in sorted(groups.keys()):
        items = sorted(groups[day], key=lambda s: s.start_at)
        days.append({"date": day, "label": fmt_jour(datetime.combine(day, time())), "slots": items})
    return days


def _list_active_teachers(db: Session) -> List[User]:
    teachers = (
        db.query(User)
        .filter(User.is_active == True, User.role == ROLE_TEACHER)
        .all()
    )
    # Tri en Python : full_name si défini, sinon username (insensible à la casse)
    teachers.sort(key=lambda t: (t.full_name or t.username).lower())
    return teachers


# =========================================================
# Vue parents (publique)
# =========================================================

@app.get("/", response_class=HTMLResponse)
def page_accueil(request: Request, db: Session = Depends(get_db)):
    teachers = _list_active_teachers(db)
    return templates.TemplateResponse(
        "accueil.html",
        {
            "request": request,
            "teachers": teachers,
            "user": get_current_user(request),
        },
    )


@app.get("/prof/{username}", response_class=HTMLResponse)
def page_prof(username: str, request: Request, db: Session = Depends(get_db)):
    teacher = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Enseignant introuvable")
    now = datetime.now().replace(second=0, microsecond=0)
    slots = (
        db.query(Slot)
        .filter(Slot.teacher_id == teacher.id, Slot.start_at >= now)
        .order_by(Slot.start_at.asc())
        .all()
    )
    days = _group_slots_by_day(slots)
    return templates.TemplateResponse(
        "parents.html",
        {
            "request": request,
            "teacher": teacher,
            "days": days,
            "user": get_current_user(request),
        },
    )


@app.post("/prof/{username}/reserver/{slot_id}")
def reserver(
    username: str,
    slot_id: int,
    request: Request,
    child_first_name: str = Form(...),
    child_last_name: str = Form(...),
    db: Session = Depends(get_db),
):
    teacher = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Enseignant introuvable")
    slot = db.get(Slot, slot_id)
    if not slot or slot.teacher_id != teacher.id:
        raise HTTPException(status_code=404, detail="Créneau introuvable")
    if slot.start_at < datetime.now():
        raise HTTPException(status_code=400, detail="Ce créneau est passé")

    first = child_first_name.strip()
    last = child_last_name.strip()
    if not first or not last:
        raise HTTPException(status_code=400, detail="Prénom et nom requis")

    booking = Booking(slot_id=slot.id, child_first_name=first, child_last_name=last)
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            "deja_reserve.html",
            {"request": request, "slot": slot, "teacher": teacher},
            status_code=409,
        )
    db.refresh(booking)
    return templates.TemplateResponse(
        "confirmation.html",
        {"request": request, "slot": slot, "booking": booking, "teacher": teacher},
    )


# =========================================================
# Auth
# =========================================================

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/admin/login")
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username.strip().lower()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Identifiants invalides"},
            status_code=401,
        )
    target = "/admin/password" if user.must_change_password else "/admin"
    response = RedirectResponse(url=target, status_code=303)
    _set_session_cookie(response, user.id)
    return response


@app.post("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/admin/password", response_class=HTMLResponse)
def admin_password_form(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(
        "change_password.html",
        {"request": request, "user": user, "error": None},
    )


@app.post("/admin/password")
def admin_password_change(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": user, "error": "Mot de passe actuel incorrect"},
            status_code=400,
        )
    if len(new_password) < 8:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": user, "error": "Le nouveau mot de passe doit faire au moins 8 caractères"},
            status_code=400,
        )
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": user, "error": "La confirmation ne correspond pas"},
            status_code=400,
        )
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


# =========================================================
# Dashboard (teacher = son propre planning)
# =========================================================

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if user.must_change_password:
        return RedirectResponse(url="/admin/password", status_code=303)

    if user.is_super_admin:
        # Le super-admin voit le résumé global + accès admin/teachers
        teachers = db.query(User).filter(User.role == ROLE_TEACHER).order_by(User.username.asc()).all()
        nb_active = sum(1 for t in teachers if t.is_active)
        nb_slots = db.query(Slot).count()
        nb_bookings = db.query(Booking).count()
        return templates.TemplateResponse(
            "admin_super.html",
            {
                "request": request, "user": user,
                "teachers": teachers,
                "nb_active": nb_active,
                "nb_slots": nb_slots,
                "nb_bookings": nb_bookings,
            },
        )

    # Vue enseignant : son propre planning
    slots = (
        db.query(Slot)
        .filter(Slot.teacher_id == user.id)
        .order_by(Slot.start_at.asc())
        .all()
    )
    days = _group_slots_by_day(slots)
    nb_total = len(slots)
    nb_reserved = sum(1 for s in slots if s.is_booked)
    nb_libres = nb_total - nb_reserved
    return templates.TemplateResponse(
        "admin_teacher.html",
        {
            "request": request, "user": user,
            "days": days,
            "nb_total": nb_total, "nb_reserved": nb_reserved, "nb_libres": nb_libres,
        },
    )


# =========================================================
# Routes teacher (gestion propres créneaux)
# =========================================================

def _ensure_owner_or_super(slot: Slot, user: User) -> None:
    if not user.is_super_admin and slot.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Action non autorisée sur ce créneau")


@app.post("/admin/slots")
def admin_add_slot(
    request: Request,
    date: str = Form(...),
    heure: str = Form(...),
    duration_minutes: int = Form(15),
    label: Optional[str] = Form(None),
    teacher_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if user.is_super_admin:
        if not teacher_id:
            raise HTTPException(status_code=400, detail="teacher_id requis pour un super-admin")
        target = db.get(User, teacher_id)
        if not target or target.role != ROLE_TEACHER:
            raise HTTPException(status_code=404, detail="Enseignant introuvable")
        owner_id = target.id
    else:
        owner_id = user.id

    try:
        start = datetime.strptime(f"{date} {heure}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date ou heure invalide")
    duration = max(5, min(180, int(duration_minutes)))
    slot = Slot(
        teacher_id=owner_id,
        start_at=start,
        duration_minutes=duration,
        label=(label.strip() if label else None) or None,
    )
    db.add(slot)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/slots/bulk")
def admin_add_bulk(
    request: Request,
    date: str = Form(...),
    heure_debut: str = Form(...),
    heure_fin: str = Form(...),
    duration_minutes: int = Form(15),
    label: Optional[str] = Form(None),
    teacher_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if user.is_super_admin:
        if not teacher_id:
            raise HTTPException(status_code=400, detail="teacher_id requis pour un super-admin")
        target = db.get(User, teacher_id)
        if not target or target.role != ROLE_TEACHER:
            raise HTTPException(status_code=404, detail="Enseignant introuvable")
        owner_id = target.id
    else:
        owner_id = user.id

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
        existing = db.query(Slot).filter(Slot.teacher_id == owner_id, Slot.start_at == cur).first()
        if not existing:
            db.add(Slot(teacher_id=owner_id, start_at=cur, duration_minutes=duration, label=label_clean))
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
    user: User = Depends(require_user),
):
    slot = db.get(Slot, slot_id)
    if slot:
        _ensure_owner_or_super(slot, user)
        db.delete(slot)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/bookings/{booking_id}/cancel")
def admin_cancel_booking(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    booking = db.get(Booking, booking_id)
    if booking:
        _ensure_owner_or_super(booking.slot, user)
        db.delete(booking)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


# =========================================================
# Super-admin : gestion des enseignants
# =========================================================

@app.get("/admin/teachers", response_class=HTMLResponse)
def admin_teachers_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    teachers = db.query(User).filter(User.role == ROLE_TEACHER).order_by(User.username.asc()).all()
    return templates.TemplateResponse(
        "admin_teachers.html",
        {
            "request": request, "user": user,
            "teachers": teachers,
            "default_password": DEFAULT_TEACHER_PASSWORD,
            "error": None,
        },
    )


@app.post("/admin/teachers")
def admin_teachers_create(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    class_level: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    username = username.strip().lower()
    full_name = full_name.strip()

    if not USERNAME_RE.match(username):
        teachers = db.query(User).filter(User.role == ROLE_TEACHER).order_by(User.username.asc()).all()
        return templates.TemplateResponse(
            "admin_teachers.html",
            {"request": request, "user": user, "teachers": teachers,
             "default_password": DEFAULT_TEACHER_PASSWORD,
             "error": "Identifiant invalide (3-32 car., minuscules/chiffres/_.-)"},
            status_code=400,
        )
    if class_level not in CLASS_LEVEL_KEYS:
        raise HTTPException(status_code=400, detail="Classe invalide")
    if db.query(User).filter(User.username == username).first():
        teachers = db.query(User).filter(User.role == ROLE_TEACHER).order_by(User.username.asc()).all()
        return templates.TemplateResponse(
            "admin_teachers.html",
            {"request": request, "user": user, "teachers": teachers,
             "default_password": DEFAULT_TEACHER_PASSWORD,
             "error": f"L'identifiant « {username} » est déjà pris"},
            status_code=400,
        )

    teacher = User(
        username=username,
        full_name=full_name or None,
        password_hash=hash_password(DEFAULT_TEACHER_PASSWORD),
        must_change_password=True,
        role=ROLE_TEACHER,
        class_level=class_level,
        is_active=True,
    )
    db.add(teacher)
    db.commit()
    return RedirectResponse(url="/admin/teachers", status_code=303)


@app.post("/admin/teachers/{teacher_id}/delete")
def admin_teachers_delete(
    teacher_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    teacher = db.get(User, teacher_id)
    if teacher and teacher.role == ROLE_TEACHER:
        db.delete(teacher)
        db.commit()
    return RedirectResponse(url="/admin/teachers", status_code=303)


@app.post("/admin/teachers/{teacher_id}/reset-password")
def admin_teachers_reset_password(
    teacher_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    teacher = db.get(User, teacher_id)
    if teacher and teacher.role == ROLE_TEACHER:
        teacher.password_hash = hash_password(DEFAULT_TEACHER_PASSWORD)
        teacher.must_change_password = True
        db.add(teacher)
        db.commit()
    return RedirectResponse(url="/admin/teachers", status_code=303)


# =========================================================
# Super-admin : vue de tous les plannings
# =========================================================

@app.get("/admin/all", response_class=HTMLResponse)
def admin_all_plannings(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    teachers = (
        db.query(User)
        .filter(User.role == ROLE_TEACHER, User.is_active == True)
        .order_by(User.username.asc())
        .all()
    )
    plannings = []
    for t in teachers:
        slots = (
            db.query(Slot)
            .filter(Slot.teacher_id == t.id)
            .order_by(Slot.start_at.asc())
            .all()
        )
        days = _group_slots_by_day(slots)
        nb_reserved = sum(1 for s in slots if s.is_booked)
        plannings.append({
            "teacher": t,
            "days": days,
            "nb_total": len(slots),
            "nb_reserved": nb_reserved,
        })
    return templates.TemplateResponse(
        "admin_all.html",
        {"request": request, "user": user, "plannings": plannings},
    )
