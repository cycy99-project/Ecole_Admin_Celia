# Déploiement Hetzner — Ecole_Admin_Celia

App déployée derrière le **Caddy mutualisé de Cycymulator** sur le VPS Hetzner.

## URL de production

**https://rdv-celia.duckdns.org**

## Pré-requis

- VPS Hetzner accessible (`ssh root@46.62.244.195`)
- Cycymulator déjà installé dans `/srv/cycymulator/` (fournit le réseau Docker `hetzner_web` + le Caddy partagé qui termine le HTTPS Let's Encrypt)
- Sous-domaine **rdv-celia.duckdns.org** créé sur https://www.duckdns.org/ et pointant sur l'IP du VPS (`46.62.244.195`)
- Clé SSH Github présente sur le VPS (`~/.ssh/id_ed25519`) pour cloner le repo privé

## Premier déploiement

```bash
ssh root@46.62.244.195
git clone git@github.com:cycy99-project/Ecole_Admin_Celia.git /srv/ecole-celia
bash /srv/ecole-celia/deploy/hetzner/install.sh
```

Le script s'occupe de tout : build Docker, démarrage du container, ajout du vhost au Caddyfile, reload de Caddy.

## Mise à jour (après `git push` côté local)

```bash
ssh root@46.62.244.195
cd /srv/ecole-celia && git pull
cd deploy/hetzner && docker compose build && docker compose up -d
```

## Fichiers de ce dossier

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | Service unique `ecole-celia` (FastAPI + SQLite), expose 8000 sur le réseau `hetzner_web`, volume `data/` persistant |
| `Caddyfile.snippet` | Bloc vhost à ajouter au Caddyfile de Cycymulator (reverse proxy + headers HSTS) |
| `install.sh` | Bootstrap automatique (build, run, intégration Caddy) |
| `README.md` | Ce fichier |

## Architecture

```
Internet (HTTPS)
   ↓ port 443
[Caddy de Cycymulator] (sur réseau hetzner_web)
   ↓ rdv-celia.duckdns.org
   ↓ reverse_proxy ecole-celia:8000
[Container ecole-celia] (FastAPI + uvicorn)
   ↓ volume bind
[/srv/ecole-celia/data/]
   ├── rdv_ecole.db  (SQLite persistant)
   └── .secret        (clé de signature des cookies, auto-générée)
```

## Variables d'environnement

| Variable | Valeur | Rôle |
|---|---|---|
| `RDV_DATA_DIR` | `/app/data` | Chemin du dossier persistant pour SQLite + secret |
| `COOKIE_SECURE` | `1` | Cookies marqués `Secure` (HTTPS only) |
| `TZ` | `Europe/Paris` | Fuseau horaire pour les datetimes |

## Sécurité

- HTTPS Let's Encrypt automatique via Caddy
- HSTS 1 an
- Cookies `httpOnly` + `secure` + `SameSite=Lax`
- Mots de passe `bcrypt`
- `.secret` (clé de signature des cookies) auto-générée et persistée hors image Docker

## Compte super-admin par défaut au premier boot

- Login : **`prof`**
- Mdp : **`PROF2026`** (changement forcé à la 1ère connexion)

Mot de passe par défaut donné aux enseignants créés par le super-admin :
**`Bienvenue123`** (changement forcé à leur 1ère connexion).
