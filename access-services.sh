#!/bin/bash

# K8s Health Monitor - Service Access Helper
# This script provides easy access to all services via k3d's built-in loadbalancer

set -e

echo "🎯 K8s Health Monitor Services"
echo "================================"
echo ""

# Check if cluster is running
if ! k3d cluster list | grep -q "standalone-cluster.*1/1.*0/0.*true"; then
    echo "❌ Error: standalone-cluster is not running"
    echo "Run: ./standalone.sh to start the cluster"
    exit 1
fi

echo "✅ Cluster Status: standalone-cluster is running"
echo ""

# Detect k3d loadbalancer port
HTTPS_PORT=$(docker ps --filter "name=k3d-standalone-cluster-serverlb" --format "{{.Ports}}" | grep -o "0.0.0.0:[0-9]*->443" | cut -d: -f2 | cut -d- -f1 2>/dev/null || echo "8443")

# Service URLs (using k3d loadbalancer)
echo "🔗 Service URLs:"
if [[ "$HTTPS_PORT" == "443" ]]; then
    echo "  📊 Health Monitor:  https://monitor.127-0-0-1.sslip.io/"
    echo "  🚀 ArgoCD:          https://argocd.127-0-0-1.sslip.io/"
    echo "  📦 Gitea:           https://gitea.127-0-0-1.sslip.io/"
    echo "  🧪 Test App:        https://standalone.127-0-0-1.sslip.io/"
else
    echo "  📊 Health Monitor:  https://monitor.127-0-0-1.sslip.io:$HTTPS_PORT/"
    echo "  🚀 ArgoCD:          https://argocd.127-0-0-1.sslip.io:$HTTPS_PORT/"
    echo "  📦 Gitea:           https://gitea.127-0-0-1.sslip.io:$HTTPS_PORT/"
    echo "  🧪 Test App:        https://standalone.127-0-0-1.sslip.io:$HTTPS_PORT/"
fi
echo ""

# API Endpoints
echo "🔌 Health Monitor API Examples:"
if [[ "$HTTPS_PORT" == "443" ]]; then
    BASE_URL="https://monitor.127-0-0-1.sslip.io"
else
    BASE_URL="https://monitor.127-0-0-1.sslip.io:$HTTPS_PORT"
fi
echo "  curl -k $BASE_URL/health"
echo "  curl -k $BASE_URL/cluster"
echo "  curl -k $BASE_URL/processes/system"
echo "  curl -k '$BASE_URL/processes/top?limit=5'"
echo ""

# Quick health check
echo "🏥 Quick Health Check:"
HEALTH=$(curl -sk $BASE_URL/health | jq -r .status 2>/dev/null || echo "error")
if [ "$HEALTH" = "healthy" ]; then
    echo "  ✅ Health Monitor: $HEALTH"
else
    echo "  ❌ Health Monitor: $HEALTH"
fi

CLUSTER=$(curl -sk $BASE_URL/cluster | jq -r .healthy 2>/dev/null || echo "error")
if [ "$CLUSTER" = "true" ]; then
    echo "  ✅ Cluster Status: healthy"
else
    echo "  ❌ Cluster Status: unhealthy"
fi

echo ""
echo "💡 Tips:"
if [[ "$HTTPS_PORT" == "443" ]]; then
    echo "  - Use 'open https://monitor.127-0-0-1.sslip.io/' to open in browser"
else
    echo "  - Use 'open https://monitor.127-0-0-1.sslip.io:$HTTPS_PORT/' to open in browser"
fi
echo "  - All services use self-signed certificates (use -k with curl)"
echo "  - Services are accessible without port forwarding via k3d loadbalancer"