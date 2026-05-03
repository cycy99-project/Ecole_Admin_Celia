# Ecole_Admin_Celia — Prise de rendez-vous parents / enseignant

Application web simple permettant à une enseignante de publier ses créneaux de rendez-vous, et aux parents de réserver en quelques clics depuis n'importe quel appareil.

## Stack

- **Backend** : FastAPI + SQLAlchemy 2 + SQLite
- **Frontend** : Jinja2 + vanilla JS + CSS responsive (mobile-first)
- **Auth** : bcrypt + cookie signé (itsdangerous)

## Démarrage rapide (Windows)

```powershell
.\start.ps1
```

Le script crée automatiquement un venv, installe les dépendances et lance l'app sur :

> http://localhost:8770

### Premier login enseignant

- URL : http://localhost:8770/admin/login
- Identifiant : `prof`
- Mot de passe par défaut : `PROF2026`

À la première connexion, l'app force le changement de mot de passe.

### Démarrage manuel (sans le script)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8770 --reload
```

## Utilisation

### Côté parents (`/`)

- Accès direct via le lien public, **aucun compte requis**.
- Liste des créneaux groupés par jour, distinction visuelle libre / réservé.
- Cliquer sur **Réserver** → modale → saisir prénom + nom de l'enfant → confirmer.
- Une fois confirmé : le créneau est verrouillé en base (contrainte `UNIQUE(slot_id)`), plus modifiable ni supprimable côté parents.

### Côté enseignant (`/admin`)

- Connexion via `/admin/login`.
- Dashboard avec compteurs : total / libres / réservés.
- **Ajout d'un créneau** : date + heure + durée + libellé optionnel.
- **Ajout en lot** : générer automatiquement tous les créneaux entre deux heures (ex: 17h-19h par tranches de 15 min).
- Pour chaque créneau : annulation d'une réservation, suppression complète du créneau (avec confirmation).
- Changement de mot de passe à tout moment.

## Structure du projet

```
c:\_Perso\Ecole_Admin_Celia\
├── backend/
│   ├── app/
│   │   ├── main.py            # routes FastAPI
│   │   ├── models.py          # Admin, Slot, Booking
│   │   ├── auth.py            # hash + cookies signés
│   │   ├── database.py        # engine SQLite
│   │   ├── templates/         # Jinja2
│   │   └── static/            # CSS + JS
│   └── requirements.txt
├── data/
│   ├── rdv_ecole.db           # SQLite (auto-créé)
│   └── .secret                # clé de signature cookies (auto-générée)
├── start.ps1
└── README.md
```

## Données

- DB SQLite à `c:\_Perso\Ecole_Admin_Celia\data\rdv_ecole.db` (auto-créée au 1er boot)
- Secret cookie à `c:\_Perso\Ecole_Admin_Celia\data\.secret` (auto-généré, à NE PAS commit)

## Sécurité

- Mots de passe : bcrypt
- Sessions : cookie httpOnly + samesite=lax + signature itsdangerous
- Verrouillage créneaux : contrainte SQL `UNIQUE` sur `bookings.slot_id` → impossible de réserver deux fois le même créneau, même en cas de course.

## Roadmap envisagée

- v0.2 : multi-enseignants, vue par enfant, export CSV
- v0.3 : notifications email parents (rappel 24h avant)
- v0.4 : déploiement Docker NAS (alignement écosystème Cycy)
