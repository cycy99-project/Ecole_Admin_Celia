# Ecole_Admin_Celia — Prise de rendez-vous parents / enseignants

Plateforme web multi-enseignants pour publier des créneaux de rendez-vous et permettre aux parents de réserver depuis n'importe quel appareil.

- **Production** : https://rdv-celia.duckdns.org (déployée sur Hetzner derrière Caddy mutualisé)
- **Local** : http://localhost:8770

## Stack

- **Backend** : FastAPI + SQLAlchemy 2 + SQLite
- **Frontend** : Jinja2 + vanilla JS + CSS responsive (mobile-first) + manifest PWA
- **Auth** : bcrypt + cookie httpOnly signé (itsdangerous)
- **Reverse proxy / TLS** : Caddy mutualisé Hetzner (Let's Encrypt auto)

## Rôles

| Rôle | Login | Pouvoirs |
|---|---|---|
| **super-admin** (`prof`) | seed au 1er boot, mdp `PROF2026` | Crée/supprime des enseignants, réinit. mdp, voit tous les plannings |
| **teacher** | créé par le super-admin, mdp `Bienvenue123` | Gère uniquement ses propres créneaux et réservations |

À chaque création/réinitialisation, l'utilisateur doit changer son mot de passe à la 1ère connexion.

## Démarrage rapide (Windows local)

```powershell
.\start.ps1
```

Le script crée un venv Python 3.12, installe les dépendances, et lance l'app sur **http://localhost:8770**.

### Premier login (super-admin)

- URL : http://localhost:8770/admin/login
- Identifiant : `prof`
- Mot de passe : `PROF2026` (changement forcé)

## Utilisation

### Côté parents

1. **Page d'accueil** `/` → liste les enseignants enregistrés
2. Clic sur un enseignant → page `/prof/{username}` avec son planning
3. Clic sur **Réserver** sur un créneau libre → modale → prénom + nom enfant → confirmer
4. Le créneau est verrouillé en BDD (contrainte `UNIQUE(slot_id)` sur bookings)

Aucun compte parent — accès direct par lien public.

### Côté super-admin (`prof`)

- `/admin` → tableau de bord (compteurs : enseignants, créneaux, réservations)
- `/admin/teachers` → CRUD enseignants (créer, supprimer, réinit. mdp)
- `/admin/all` → vue consolidée de tous les plannings

### Côté enseignant

- `/admin` → son propre planning + liens publics
- Ajout d'un créneau (date + heure + durée + libellé optionnel ex: "salle B")
- Ajout en lot (plage horaire fractionnée en N créneaux)
- Annulation d'une réservation, suppression d'un créneau
- Ne peut PAS toucher aux créneaux d'un autre enseignant (403)

## Structure du projet

```
c:\_Perso\Ecole_Admin_Celia\
├── backend/
│   ├── app/
│   │   ├── main.py            # routes FastAPI (parents + admin + super-admin)
│   │   ├── models.py          # User (rôle + classe), Slot, Booking + CLASS_LEVELS
│   │   ├── auth.py            # bcrypt + cookies signés (require_super_admin, etc.)
│   │   ├── database.py        # engine SQLite (RDV_DATA_DIR configurable)
│   │   ├── templates/         # Jinja2 (accueil, parents, admin_teacher, admin_super, admin_teachers, admin_all, login, …)
│   │   └── static/            # CSS, JS, manifest, icon SVG
│   └── requirements.txt
├── data/                       # SQLite + .secret (volume persistant en prod)
├── deploy/hetzner/             # Dockerfile, compose, Caddyfile snippet, install.sh
├── Dockerfile
├── start.ps1                   # démarrage local Windows
└── README.md
```

## Données

- DB SQLite à `c:\_Perso\Ecole_Admin_Celia\data\rdv_ecole.db` (auto-créée au 1er boot)
- Secret cookie à `c:\_Perso\Ecole_Admin_Celia\data\.secret` (auto-généré, **ne pas committer**)
- En production : ces fichiers sont dans `/srv/ecole-celia/data/` (bind mount Docker)

## Niveaux de classe disponibles

`TPS`, `PS`, `MS`, `GS`, `CP`, `CE1`, `CE2`, `CM1`, `CM2`

## Sécurité

- Passwords : `bcrypt`
- Sessions : cookie `httpOnly` + `SameSite=Lax` + `Secure` (en prod via env `COOKIE_SECURE=1`)
- Signature : `itsdangerous` URLSafeSerializer, secret persistant `.secret`
- HTTPS prod : Let's Encrypt automatique via Caddy
- HSTS 1 an en prod
- Verrouillage anti-double-réservation : contrainte SQL `UNIQUE(slot_id)` sur `bookings`
- Isolation par enseignant : les routes admin vérifient `slot.teacher_id == user.id` (sauf super-admin)

## Déploiement Hetzner

Voir [`deploy/hetzner/README.md`](deploy/hetzner/README.md) pour la procédure complète.

```bash
# Sur le VPS (root) :
git clone git@github.com:cycy99-project/Ecole_Admin_Celia.git /srv/ecole-celia
bash /srv/ecole-celia/deploy/hetzner/install.sh
```

Mise à jour : `git pull` + `docker compose build && docker compose up -d`.

## Roadmap envisagée

- v0.3 : notifications email parents (rappel 24h avant)
- v0.4 : export CSV des plannings
- v0.5 : invitations enseignants par email (token UUID)
