#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu VM (Oracle Cloud Always Free, Google Cloud e2-micro, any VPS).
#   git clone <your repo> jobkit && cd jobkit && bash deploy/setup-vm.sh [your.domain]
# Without a domain it uses <your-ip>.sslip.io, which works with HTTPS out of the box.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
fi

# Oracle's Ubuntu images reject ports 80/443 in iptables even after you open them in the cloud console
if sudo iptables -L INPUT -n 2>/dev/null | grep -q "REJECT"; then
  echo "Opening ports 80 and 443 in iptables..."
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
  sudo netfilter-persistent save 2>/dev/null || true
fi

# Small VMs (1 GB): add swap so the image build doesn't run out of memory
if [ "$(free -m | awk '/Mem:/{print $2}')" -lt 2000 ] && ! swapon --show | grep -q .; then
  echo "Adding 2 GB swap..."
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  IP="$(curl -fsS https://api.ipify.org)"
  DOMAIN="${IP//./-}.sslip.io"
fi
echo "DOMAIN=$DOMAIN" > .env

if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo
  echo "Created .env.local - add your ANTHROPIC_API_KEY (and anything else) then run this script again:"
  echo "  nano .env.local"
  exit 1
fi
sudo docker compose up -d --build
echo
echo "jobkit is starting at https://$DOMAIN (the first HTTPS certificate can take a minute)."
echo "Open it NOW and create your account - the first account becomes the admin."
echo "After that nobody can join without an invite link you create in Admin."
