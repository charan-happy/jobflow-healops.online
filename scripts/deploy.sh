#!/bin/bash
set -e

# ============================================================
# JobFlow — Oracle Cloud Ubuntu Deployment
# ============================================================
#
# Prerequisites:
#   - Ubuntu 22.04+ on Oracle Cloud (free tier works)
#   - A domain pointed to your server's public IP
#   - SSH access to the server
#
# Usage:
#   1. SSH into your Oracle server
#   2. Clone the repo
#   3. Copy .env.production.example to .env.production and fill values
#   4. Run: bash scripts/deploy.sh
#
# ============================================================

DOMAIN=""
EMAIL=""

# ---- Parse arguments ----
usage() {
    echo "Usage: $0 --domain <your-domain> --email <your-email>"
    echo ""
    echo "  --domain    Your domain name (e.g., jobs.example.com)"
    echo "  --email     Email for Let's Encrypt notifications"
    echo ""
    echo "Example:"
    echo "  bash scripts/deploy.sh --domain jobs.example.com --email you@gmail.com"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain) DOMAIN="$2"; shift 2 ;;
        --email) EMAIL="$2"; shift 2 ;;
        *) usage ;;
    esac
done

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    usage
fi

echo "========================================"
echo "  Deploying JobFlow"
echo "  Domain: $DOMAIN"
echo "  Email:  $EMAIL"
echo "========================================"

# ---- Step 1: Install Docker if not present ----
if ! command -v docker &> /dev/null; then
    echo "[1/7] Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to log out and back in for group changes."
else
    echo "[1/7] Docker already installed."
fi

# ---- Step 2: Open firewall ports ----
echo "[2/7] Configuring firewall (iptables)..."
# Oracle Cloud uses iptables, not ufw
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || true
# Also try ufw in case it's enabled
if command -v ufw &> /dev/null; then
    sudo ufw allow 80/tcp 2>/dev/null || true
    sudo ufw allow 443/tcp 2>/dev/null || true
fi
echo "  Ports 80, 443 opened."
echo ""
echo "  IMPORTANT: Also open ports 80 and 443 in Oracle Cloud Console:"
echo "  Networking > Virtual Cloud Networks > your VCN > Security Lists > Ingress Rules"
echo "  Add rules for TCP ports 80 and 443 from 0.0.0.0/0"
echo ""

# ---- Step 3: Check .env.production ----
echo "[3/7] Checking environment file..."
if [ ! -f .env.production ]; then
    echo "  ERROR: .env.production not found!"
    echo "  Copy .env.production.example to .env.production and fill in your values."
    echo "  Run: cp .env.production.example .env.production && nano .env.production"
    exit 1
fi

# Inject DOMAIN into .env.production if not set
if ! grep -q "^DOMAIN=" .env.production; then
    echo "DOMAIN=$DOMAIN" >> .env.production
fi

# ---- Step 4: Generate nginx config with actual domain ----
echo "[4/7] Generating nginx config for $DOMAIN..."
sed "s/\${DOMAIN}/$DOMAIN/g" nginx/nginx.conf > nginx/nginx.prod.conf

# ---- Step 5: Get SSL certificate (initial setup) ----
echo "[5/7] Obtaining SSL certificate from Let's Encrypt..."

# First, start nginx with HTTP-only config for the ACME challenge
cat > nginx/nginx.initial.conf <<EOF
server {
    listen 80;
    server_name $DOMAIN grafana.$DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'Setting up...';
        add_header Content-Type text/plain;
    }
}
EOF

# Start just nginx for certificate issuance
docker compose -f docker-compose.prod.yml run -d --rm \
    -v "$(pwd)/nginx/nginx.initial.conf:/etc/nginx/conf.d/default.conf:ro" \
    --name jobflow-nginx-init \
    -p 80:80 \
    nginx nginx -g "daemon off;" 2>/dev/null || true

sleep 2

# Request certificate
docker run --rm \
    -v jobflow_certbot-etc:/etc/letsencrypt \
    -v jobflow_certbot-var:/var/lib/letsencrypt \
    -v jobflow_certbot-webroot:/var/www/certbot \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    -d "grafana.$DOMAIN" \
    --force-renewal

# Stop temporary nginx
docker stop jobflow-nginx-init 2>/dev/null || true

echo "  SSL certificate obtained for $DOMAIN + grafana.$DOMAIN"

# ---- Step 6: Build and deploy ----
echo "[6/7] Building and starting all services..."

# Use the production nginx config
cp nginx/nginx.prod.conf nginx/nginx.conf.bak
cp nginx/nginx.prod.conf nginx/nginx.conf

# Export DOMAIN for docker-compose interpolation
export DOMAIN=$DOMAIN

# Build and start everything
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

echo "  Waiting for services to start..."
sleep 10

# ---- Step 7: Verify ----
echo "[7/7] Verifying deployment..."

# Check if backend is healthy
if curl -sf "http://localhost:8000/api/health" > /dev/null 2>&1 || \
   docker exec jobflow-backend curl -sf "http://localhost:8000/api/health" > /dev/null 2>&1; then
    echo "  Backend: OK"
else
    echo "  Backend: checking via docker..."
    docker logs jobflow-backend --tail 5 2>&1 | tail -3
fi

echo ""
echo "========================================"
echo "  Deployment complete!"
echo "========================================"
echo ""
echo "  Your app is live at: https://$DOMAIN"
echo "  Grafana dashboard:  https://grafana.$DOMAIN"
echo ""
echo "  Useful commands:"
echo "    docker compose -f docker-compose.prod.yml logs -f          # View all logs"
echo "    docker compose -f docker-compose.prod.yml logs -f backend  # Backend logs"
echo "    docker compose -f docker-compose.prod.yml restart backend  # Restart backend"
echo "    docker compose -f docker-compose.prod.yml down             # Stop everything"
echo "    docker compose -f docker-compose.prod.yml up -d --build    # Rebuild & restart"
echo ""
echo "  SSL auto-renews via certbot container."
echo "  To manually renew: docker exec jobflow-certbot certbot renew"
echo ""
