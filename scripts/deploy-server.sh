#!/usr/bin/env bash
set -e

# ==============================================================================
# PROJECT VULCAN: Automated Production Server Deployer
# Target Environment: Ubuntu 22.04 / 24.04 LTS
# ==============================================================================

APP_DIR="${APP_DIR:-$HOME/vulcan}"
REPO_URL="https://github.com/lavkushry/vulcan.git"

echo "================================================================"
echo "          PROJECT VULCAN: Automated Server Deployment"
echo "================================================================"
echo "Deployment Target Directory: $APP_DIR"

# 1. Ensure Docker & Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "[!] Docker not detected. Installing Docker & Docker Compose..."
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg lsb-release
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo usermod -aG docker "$USER" || true
    echo "[✓] Docker installed successfully."
fi

# 2. Clone or pull repository
if [ ! -d "$APP_DIR/.git" ]; then
    echo "[1/4] Cloning repository to $APP_DIR..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
else
    echo "[1/4] Fetching latest commit from origin/main..."
    cd "$APP_DIR"
    git fetch origin main
    git reset --hard origin/main
fi

# 3. Pull & Rebuild Docker Stack
echo "[2/4] Deploying stack via Docker Compose..."
cd "$APP_DIR/deploy"

# Determine docker compose command (plugin or standalone)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Graceful rebuild
$DOCKER_COMPOSE down --remove-orphans
$DOCKER_COMPOSE build --pull
$DOCKER_COMPOSE up -d

# 4. Wait for Health Probes
echo "[3/4] Validating service health..."
sleep 5

MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s -f http://localhost:8000/healthz > /dev/null 2>&1 && curl -s -f http://localhost:3000 > /dev/null 2>&1; then
        echo "[✓] Both Backend and Frontend are responding with 200 OK!"
        break
    fi
    echo "Waiting for services to become healthy ($WAITED/${MAX_WAIT}s)..."
    sleep 3
    WAITED=$((WAITED + 3))
done

# 5. Summary
echo "[4/4] Active Deployment Status:"
$DOCKER_COMPOSE ps

SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo ""
echo "================================================================"
echo " Vulcan Deployment Complete!"
echo "   - Console Web UI:   http://$SERVER_IP:3000"
echo "   - API Endpoint:     http://$SERVER_IP:8000"
echo "   - API Swagger Docs: http://$SERVER_IP:8000/docs"
echo "   - Health Check:     http://$SERVER_IP:8000/healthz"
echo "================================================================"
