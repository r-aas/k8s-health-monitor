# K8s Health Monitor

**FastAPI service for monitoring Kubernetes cluster health and status with comprehensive process management**

## Features

### 🎯 **Cluster Monitoring**
-  **Cluster Overview** - Node status, resource usage, pod health
-  **Service Health** - ArgoCD, Gitea, Traefik status checks
-  **GitOps Status** - ArgoCD application sync status
-  **Web Dashboard** - Real-time monitoring interface

### ⚡ **Process Management**
-  **System Resources** - CPU, memory, disk monitoring via psutil
-  **Process Monitoring** - Top processes by CPU/memory usage
-  **Container Processes** - Kubernetes and container process discovery
-  **Resource Alerts** - CPU/memory threshold monitoring
-  **Process-Compose Integration** - API for persistent process management

### 🔌 **APIs**
-  **REST Endpoints** - JSON APIs for programmatic access
-  **Real-time Data** - Live system metrics and cluster status
-  **Process Control** - Start/stop/restart process management

## Endpoints

### Core Monitoring
- `GET /` - Web dashboard with real-time updates
- `GET /health` - Service health check
- `GET /cluster` - Overall cluster status
- `GET /nodes` - Node status and resources
- `GET /pods` - Pod status across namespaces
- `GET /services` - Service health checks
- `GET /argocd` - ArgoCD applications status
- `GET /gitea` - Gitea health and repository stats

### Process Management
- `GET /processes/system` - System resource information
- `GET /processes/top?limit=N` - Top processes by CPU usage
- `GET /processes/kubernetes` - Kubernetes-related processes
- `GET /processes/containers` - Container processes
- `GET /processes/alerts` - Resource usage alerts
- `POST /processes/{pid}/restart` - Restart process by PID

### Process-Compose Integration
- `GET /compose/project` - Project information
- `GET /compose/processes` - All managed processes
- `GET /compose/processes/{name}` - Specific process info
- `POST /compose/processes/{name}/start` - Start process
- `POST /compose/processes/{name}/stop` - Stop process
- `POST /compose/processes/{name}/restart` - Restart process
- `GET /compose/processes/{name}/logs?tail=N` - Process logs
- `GET /compose/health` - Overall process health

## Quick Start

```bash
# Deploy complete GitOps platform with health monitoring
./standalone.sh

# Access services (no port forwarding needed!)
./access-services.sh
```

### 🔗 **Service URLs** (via k3d loadbalancer)
- **📊 Health Monitor**: https://monitor.127-0-0-1.sslip.io:8443/
- **🚀 ArgoCD**: https://argocd.127-0-0-1.sslip.io:8443/  
- **📦 Gitea**: https://gitea.127-0-0-1.sslip.io:8443/

### 🔌 **API Examples**
```bash
# Health check
curl -k https://monitor.127-0-0-1.sslip.io:8443/health

# Cluster status
curl -k https://monitor.127-0-0-1.sslip.io:8443/cluster

# System resources
curl -k https://monitor.127-0-0-1.sslip.io:8443/processes/system

# Top processes
curl -k 'https://monitor.127-0-0-1.sslip.io:8443/processes/top?limit=5'
```

## Development

```bash
# Install dependencies
uv sync

# Run locally (requires kubeconfig)
uv run src/k8s_health_monitor/main.py

# Build container
docker build -t k8s-health-monitor .

# Push to registry (for k3d)
docker build -t registry.localhost:5001/k8s-health-monitor:latest . && \
docker push registry.localhost:5001/k8s-health-monitor:latest
```

## Architecture

### k3d Integration
- **Loadbalancer**: Built-in k3d loadbalancer on ports 8086 (HTTP) and 8443 (HTTPS)
- **DNS**: /etc/hosts entries for *.127-0-0-1.sslip.io domains
- **Certificates**: mkcert-generated TLS certificates via cert-manager
- **No Port Forwarding**: Direct access via k3d's built-in networking

### GitOps Workflow
1. **Infrastructure**: Deploy via `./standalone.sh` (k3d, ArgoCD, Gitea)
2. **Applications**: Deploy via ArgoCD from Git repositories
3. **Monitoring**: Health monitor provides oversight of entire stack
4. **Process Management**: Integrated system and process monitoring

### Container Security
- **Non-root user**: Runs as `appuser` with restricted permissions
- **Read-only filesystem**: Security context prevents filesystem writes
- **Resource limits**: CPU and memory constraints defined
- **Health checks**: Liveness and readiness probes configured

## Troubleshooting

### Common Issues
- **Services not accessible**: Check `k3d cluster list` and ensure standalone-cluster is running
- **Certificate errors**: Use `-k` flag with curl for self-signed certificates  
- **DNS resolution**: Verify /etc/hosts entries or use host headers with curl
- **Pod not starting**: Check `kubectl logs -n monitoring deployment/k8s-health-monitor`

### Cleanup
```bash
# Stop cluster
k3d cluster stop standalone-cluster

# Delete cluster
k3d cluster delete standalone-cluster

# Remove DNS entries
sudo sed -i '' '/k3d standalone cluster entries/,+5d' /etc/hosts
```