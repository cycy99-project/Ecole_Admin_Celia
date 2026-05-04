#!/bin/bash
# ============================================================================
# Ecole_Admin_Celia — Bootstrap script pour Hetzner VPS Ubuntu 22.04 / 24.04
# ============================================================================
# Prérequis : Cycymulator déjà installé sur le VPS (Docker + Caddy en place).
#
# Usage (sur le VPS, en root) :
#   git clone git@github.com:cycy99-project/Ecole_Admin_Celia.git /srv/ecole-celia
#   bash /srv/ecole-celia/deploy/hetzner/install.sh
# ============================================================================

set -euo pipefail

REPO_URL="${REPO_URL:-git@github.com:cycy99-project/Ecole_Admin_Celia.git}"
INSTALL_DIR="/srv/ecole-celia"
CYCY_DIR="/srv/cycymulator"
LOG_FILE="/tmp/ecole-celia-install.log"
DOMAIN="rdv-celia.duckdns.org"

log()  { echo -e "\033[1;34m[$(date +%H:%M:%S)]\033[0m $*" | tee -a "$LOG_FILE"; }
fail() { echo -e "\033[1;31m[ERREUR]\033[0m $*" | tee -a "$LOG_FILE"; exit 1; }

# ----- Préchecks ------------------------------------------------------------
log "Vérification des prérequis…"
command -v docker &>/dev/null || fail "Docker manquant. Installe Cycymulator d'abord."
docker compose version &>/dev/null || fail "docker compose plugin manquant."
[[ -d "$CYCY_DIR/deploy/hetzner" ]] || fail "Cycymulator pas trouvé dans $CYCY_DIR — il fournit le réseau Caddy partagé."

if [[ $EUID -ne 0 ]]; then
    SUDO="sudo"
else
    SUDO=""
fi

# ----- Vérif réseau Caddy partagé -------------------------------------------
NET_NAME=$($SUDO docker network ls --filter "name=hetzner_web" --format '{{.Name}}' | head -1)
if [[ -z "$NET_NAME" ]]; then
    log "Réseau hetzner_web introuvable — démarrage Cycymulator pour le créer…"
    cd "$CYCY_DIR/deploy/hetzner" && $SUDO docker compose up -d
    NET_NAME=$($SUDO docker network ls --filter "name=hetzner_web" --format '{{.Name}}' | head -1)
    [[ -n "$NET_NAME" ]] || fail "Impossible de créer/trouver le réseau hetzner_web."
fi
log "Réseau Caddy partagé OK : $NET_NAME"

# ----- Clone / pull du repo -------------------------------------------------
log "Récupération du code Ecole_Admin_Celia dans $INSTALL_DIR…"
$SUDO mkdir -p /srv
if [[ ! -d "$INSTALL_DIR/.git" ]]; then
    $SUDO git clone "$REPO_URL" "$INSTALL_DIR"
else
    log "Repo déjà cloné, mise à jour (git pull)…"
    cd "$INSTALL_DIR" && $SUDO git pull --ff-only
fi

cd "$INSTALL_DIR/deploy/hetzner"

# ----- Volumes persistants --------------------------------------------------
log "Création du dossier data persistant (SQLite + secret cookie)…"
$SUDO mkdir -p "$INSTALL_DIR/data"

# ----- Build & démarrage ----------------------------------------------------
log "Build de l'image Docker (peut prendre 1-2 min la 1ère fois)…"
$SUDO docker compose build

log "Démarrage du container…"
$SUDO docker compose up -d

# ----- Caddy : ajout du vhost si absent -------------------------------------
CADDYFILE="$CYCY_DIR/deploy/hetzner/Caddyfile"
if ! $SUDO grep -q "$DOMAIN" "$CADDYFILE"; then
    log "Ajout du bloc vhost Ecole_Admin_Celia au Caddyfile de Cycymulator…"
    $SUDO tee -a "$CADDYFILE" >/dev/null < "$INSTALL_DIR/deploy/hetzner/Caddyfile.snippet"
    log "Reload de Caddy…"
    cd "$CYCY_DIR/deploy/hetzner"
    $SUDO docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile || \
        { log "⚠ reload échoué, restart full…"; $SUDO docker compose restart caddy; }
else
    log "Bloc vhost Ecole_Admin_Celia déjà présent dans Caddyfile."
fi

# ----- État final -----------------------------------------------------------
sleep 5
log "État du container Ecole_Admin_Celia :"
cd "$INSTALL_DIR/deploy/hetzner"
$SUDO docker compose ps

VPS_IP=$(curl -s -4 ifconfig.me 2>/dev/null || echo "<inconnue>")

log "✅ Installation terminée."
echo
echo "📋 Étapes restantes :"
echo "  1. Vérifie que le sous-domaine $DOMAIN pointe sur l'IP du VPS :"
echo "     IP du VPS : $VPS_IP"
echo "     Va sur https://www.duckdns.org/ → créer/modifier 'rdv-celia' avec cette IP."
echo "  2. Attends 1-2 min la propagation DNS + Let's Encrypt :"
echo "     curl -I https://$DOMAIN"
echo "  3. Ouvre https://$DOMAIN — la page d'accueil parents doit s'afficher."
echo
echo "🔐 Compte super-admin par défaut au premier boot :"
echo "  Login : prof"
echo "  Mdp   : PROF2026  (changement forcé à la 1ère connexion)"
echo
echo "🔧 Mise à jour future (après git push) :"
echo "  cd $INSTALL_DIR && $SUDO git pull"
echo "  cd deploy/hetzner && $SUDO docker compose build && $SUDO docker compose up -d"
echo
echo "📁 Logs install : $LOG_FILE"
