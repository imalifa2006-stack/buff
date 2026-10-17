#!/usr/bin/env bash
# Prepares a fresh Ubuntu 22.04/24.04 server: Docker + firewall. Run as root.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Run as root (sudo bash deploy/setup_server.sh)"; exit 1; fi
apt-get update -y
apt-get install -y ca-certificates curl unzip ufw
curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
echo "Server is ready."
