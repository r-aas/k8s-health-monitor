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

# Service URLs (using k3d loadbalancer on port 8443 for HTTPS)
echo "🔗 Service URLs:"
echo "  📊 Health Monitor:  https://monitor.127-0-0-1.sslip.io:8443/"
echo "  🚀 ArgoCD:          https://argocd.127-0-0-1.sslip.io:8443/"
echo "  📦 Gitea:           https://gitea.127-0-0-1.sslip.io:8443/"
echo "  🧪 Test App:        https://standalone.127-0-0-1.sslip.io:8443/"
echo ""

# API Endpoints
echo "🔌 Health Monitor API Examples:"
echo "  curl -k https://monitor.127-0-0-1.sslip.io:8443/health"
echo "  curl -k https://monitor.127-0-0-1.sslip.io:8443/cluster"
echo "  curl -k https://monitor.127-0-0-1.sslip.io:8443/processes/system"
echo "  curl -k 'https://monitor.127-0-0-1.sslip.io:8443/processes/top?limit=5'"
echo ""

# Quick health check
echo "🏥 Quick Health Check:"
HEALTH=$(curl -sk https://monitor.127-0-0-1.sslip.io:8443/health | jq -r .status 2>/dev/null || echo "error")
if [ "$HEALTH" = "healthy" ]; then
    echo "  ✅ Health Monitor: $HEALTH"
else
    echo "  ❌ Health Monitor: $HEALTH"
fi

CLUSTER=$(curl -sk https://monitor.127-0-0-1.sslip.io:8443/cluster | jq -r .healthy 2>/dev/null || echo "error")
if [ "$CLUSTER" = "true" ]; then
    echo "  ✅ Cluster Status: healthy"
else
    echo "  ❌ Cluster Status: unhealthy"
fi

echo ""
echo "💡 Tips:"
echo "  - Use 'open https://monitor.127-0-0-1.sslip.io:8443/' to open in browser"
echo "  - All services use self-signed certificates (use -k with curl)"
echo "  - Services are accessible without port forwarding via k3d loadbalancer"