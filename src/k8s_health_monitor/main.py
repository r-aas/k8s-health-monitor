#!/usr/bin/env python3

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from kubernetes import client, config
from pydantic import BaseModel

from .process_manager import ProcessManager, ProcessInfo, SystemResources
from .process_compose_manager import ProcessComposeManager, ProcessStatus, ProcessComposeInfo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Kubernetes config
try:
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config")
    else:
        config.load_kube_config()
        logger.info("Loaded local Kubernetes config")
except Exception as e:
    logger.error(f"Failed to load Kubernetes config: {e}")
    raise

# Initialize Kubernetes clients
v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
custom_api = client.CustomObjectsApi()

# Initialize Process Manager
process_manager = ProcessManager()
pc_manager = ProcessComposeManager()

app = FastAPI(
    title="K8s Health Monitor",
    description="Kubernetes cluster health and status monitoring API",
    version="1.0.0"
)


class HealthStatus(BaseModel):
    service: str
    status: str
    message: str
    timestamp: datetime


class ClusterStatus(BaseModel):
    healthy: bool
    nodes_ready: int
    nodes_total: int
    pods_running: int
    pods_total: int
    services_healthy: int
    services_total: int
    timestamp: datetime


class NodeStatus(BaseModel):
    name: str
    status: str
    ready: bool
    cpu_capacity: str
    memory_capacity: str
    pod_capacity: str
    architecture: str
    os_image: str


class PodStatus(BaseModel):
    name: str
    namespace: str
    status: str
    ready: bool
    restarts: int
    age: str
    node: str


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Web dashboard for cluster overview"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>K8s Health Monitor</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .status-ok { color: #22c55e; }
            .status-warning { color: #f59e0b; }
            .status-error { color: #ef4444; }
            .metric { font-size: 2em; font-weight: bold; margin: 10px 0; }
            .refresh-btn { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
            .refresh-btn:hover { background: #2563eb; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }
            th { background-color: #f8f9fa; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 K8s Health Monitor</h1>
                <p>Real-time Kubernetes cluster health and status monitoring</p>
                <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h2>📊 Cluster Overview</h2>
                    <div id="cluster-status">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>🏠 Nodes</h2>
                    <div id="nodes-status">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>🚀 Services</h2>
                    <div id="services-status">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>🔄 GitOps</h2>
                    <div id="argocd-status">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>⚡ System Resources</h2>
                    <div id="system-resources">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>🚨 Alerts</h2>
                    <div id="alerts-status">Loading...</div>
                </div>
            </div>
            
            <div class="grid" style="margin-top: 20px;">
                <div class="card">
                    <h2>📦 Recent Pods</h2>
                    <div id="pods-status">Loading...</div>
                </div>
                
                <div class="card">
                    <h2>⚙️ Top Processes</h2>
                    <div id="processes-status">Loading...</div>
                </div>
            </div>
        </div>

        <script>
            async function loadData() {
                try {
                    // Load cluster status
                    const cluster = await fetch('/cluster').then(r => r.json());
                    document.getElementById('cluster-status').innerHTML = `
                        <div class="metric ${cluster.healthy ? 'status-ok' : 'status-error'}">${cluster.healthy ? '✅' : '❌'}</div>
                        <p><strong>Nodes:</strong> ${cluster.nodes_ready}/${cluster.nodes_total} ready</p>
                        <p><strong>Pods:</strong> ${cluster.pods_running}/${cluster.pods_total} running</p>
                        <p><strong>Services:</strong> ${cluster.services_healthy}/${cluster.services_total} healthy</p>
                    `;

                    // Load nodes
                    const nodes = await fetch('/nodes').then(r => r.json());
                    document.getElementById('nodes-status').innerHTML = 
                        nodes.map(node => `
                            <p><span class="${node.ready ? 'status-ok' : 'status-error'}">●</span> ${node.name} (${node.status})</p>
                        `).join('');

                    // Load services
                    const services = await fetch('/services').then(r => r.json());
                    document.getElementById('services-status').innerHTML = 
                        services.map(svc => `
                            <p><span class="${svc.status === 'healthy' ? 'status-ok' : 'status-error'}">●</span> ${svc.service}</p>
                        `).join('');

                    // Load ArgoCD
                    try {
                        const argocd = await fetch('/argocd').then(r => r.json());
                        document.getElementById('argocd-status').innerHTML = 
                            argocd.applications.map(app => `
                                <p><span class="${app.health === 'Healthy' && app.sync === 'Synced' ? 'status-ok' : 'status-warning'}">●</span> ${app.name}</p>
                            `).join('');
                    } catch {
                        document.getElementById('argocd-status').innerHTML = '<p class="status-warning">ArgoCD not available</p>';
                    }

                    // Load system resources
                    try {
                        const resources = await fetch('/processes/system').then(r => r.json());
                        document.getElementById('system-resources').innerHTML = `
                            <p><strong>CPU:</strong> ${resources.cpu_percent}% (${resources.cpu_count} cores)</p>
                            <p><strong>Memory:</strong> ${resources.memory_used_gb}GB/${resources.memory_total_gb}GB (${resources.memory_percent}%)</p>
                            <p><strong>Disk:</strong> ${resources.disk_usage_percent}% used, ${resources.disk_free_gb}GB free</p>
                            <p><strong>Load:</strong> ${resources.load_average.slice(0,3).join(', ')}</p>
                        `;
                    } catch {
                        document.getElementById('system-resources').innerHTML = '<p class="status-warning">System resources unavailable</p>';
                    }

                    // Load alerts
                    try {
                        const alerts = await fetch('/processes/alerts').then(r => r.json());
                        if (alerts.count === 0) {
                            document.getElementById('alerts-status').innerHTML = '<p class="status-ok">✅ No alerts</p>';
                        } else {
                            const alertsList = alerts.alerts.map(alert => `
                                <p class="status-${alert.severity === 'critical' ? 'error' : 'warning'}">
                                    ${alert.severity === 'critical' ? '🚨' : '⚠️'} ${alert.message}
                                </p>
                            `).join('');
                            document.getElementById('alerts-status').innerHTML = alertsList;
                        }
                    } catch {
                        document.getElementById('alerts-status').innerHTML = '<p class="status-warning">Alerts unavailable</p>';
                    }

                    // Load pods
                    const pods = await fetch('/pods').then(r => r.json());
                    const podTable = `
                        <table>
                            <tr><th>Name</th><th>Namespace</th><th>Status</th><th>Ready</th><th>Restarts</th></tr>
                            ${pods.slice(0, 10).map(pod => `
                                <tr>
                                    <td>${pod.name}</td>
                                    <td>${pod.namespace}</td>
                                    <td><span class="${pod.ready ? 'status-ok' : 'status-error'}">${pod.status}</span></td>
                                    <td>${pod.ready ? '✅' : '❌'}</td>
                                    <td>${pod.restarts}</td>
                                </tr>
                            `).join('')}
                        </table>
                    `;
                    document.getElementById('pods-status').innerHTML = podTable;

                    // Load top processes
                    try {
                        const processes = await fetch('/processes/top?limit=5').then(r => r.json());
                        const processTable = `
                            <table>
                                <tr><th>Process</th><th>CPU%</th><th>Memory%</th><th>MB</th></tr>
                                ${processes.map(proc => `
                                    <tr>
                                        <td>${proc.name}</td>
                                        <td>${proc.cpu_percent}%</td>
                                        <td>${proc.memory_percent}%</td>
                                        <td>${proc.memory_mb}</td>
                                    </tr>
                                `).join('')}
                            </table>
                        `;
                        document.getElementById('processes-status').innerHTML = processTable;
                    } catch {
                        document.getElementById('processes-status').innerHTML = '<p class="status-warning">Process data unavailable</p>';
                    }
                    
                } catch (error) {
                    console.error('Failed to load data:', error);
                }
            }

            // Load data on page load
            loadData();
            
            // Auto-refresh every 30 seconds
            setInterval(loadData, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/health")
async def health_check():
    """Service health check endpoint"""
    return HealthStatus(
        service="k8s-health-monitor",
        status="healthy",
        message="Service is running",
        timestamp=datetime.now()
    )


@app.get("/cluster")
async def cluster_status():
    """Get overall cluster health status"""
    try:
        # Get nodes
        nodes = v1.list_node()
        nodes_ready = sum(1 for node in nodes.items 
                         if any(condition.type == "Ready" and condition.status == "True"
                               for condition in node.status.conditions))
        
        # Get pods across all namespaces
        pods = v1.list_pod_for_all_namespaces()
        pods_running = sum(1 for pod in pods.items if pod.status.phase == "Running")
        
        # Get services status
        services = await get_services_health()
        services_healthy = sum(1 for svc in services if svc.status == "healthy")
        
        healthy = (nodes_ready == len(nodes.items) and 
                  pods_running > 0 and 
                  services_healthy > 0)
        
        return ClusterStatus(
            healthy=healthy,
            nodes_ready=nodes_ready,
            nodes_total=len(nodes.items),
            pods_running=pods_running,
            pods_total=len(pods.items),
            services_healthy=services_healthy,
            services_total=len(services),
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to get cluster status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nodes")
async def nodes_status():
    """Get detailed node status"""
    try:
        nodes = v1.list_node()
        node_list = []
        
        for node in nodes.items:
            ready = any(condition.type == "Ready" and condition.status == "True"
                       for condition in node.status.conditions)
            
            node_list.append(NodeStatus(
                name=node.metadata.name,
                status=node.status.phase or "Unknown",
                ready=ready,
                cpu_capacity=node.status.capacity.get('cpu', 'Unknown'),
                memory_capacity=node.status.capacity.get('memory', 'Unknown'),
                pod_capacity=node.status.capacity.get('pods', 'Unknown'),
                architecture=node.status.node_info.architecture,
                os_image=node.status.node_info.os_image
            ))
        
        return node_list
        
    except Exception as e:
        logger.error(f"Failed to get nodes status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pods")
async def pods_status(namespace: Optional[str] = None, limit: int = 50):
    """Get pod status across namespaces"""
    try:
        if namespace:
            pods = v1.list_namespaced_pod(namespace)
        else:
            pods = v1.list_pod_for_all_namespaces()
        
        pod_list = []
        for pod in pods.items[:limit]:
            ready = (pod.status.container_statuses and 
                    all(cs.ready for cs in pod.status.container_statuses))
            
            restarts = (sum(cs.restart_count for cs in pod.status.container_statuses)
                       if pod.status.container_statuses else 0)
            
            age = str(datetime.now() - pod.metadata.creation_timestamp.replace(tzinfo=None))[:10]
            
            pod_list.append(PodStatus(
                name=pod.metadata.name,
                namespace=pod.metadata.namespace,
                status=pod.status.phase or "Unknown",
                ready=ready,
                restarts=restarts,
                age=age,
                node=pod.spec.node_name or "Unknown"
            ))
        
        return sorted(pod_list, key=lambda x: x.name)
        
    except Exception as e:
        logger.error(f"Failed to get pods status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/services")
async def services_health():
    """Get service health checks"""
    return await get_services_health()


async def get_services_health():
    """Internal function to check service health"""
    services = []
    
    # Check ArgoCD
    try:
        argocd_pods = v1.list_namespaced_pod("argocd", label_selector="app.kubernetes.io/name=argocd-server")
        if argocd_pods.items and all(pod.status.phase == "Running" for pod in argocd_pods.items):
            services.append(HealthStatus(
                service="ArgoCD",
                status="healthy",
                message="Server pods running",
                timestamp=datetime.now()
            ))
        else:
            services.append(HealthStatus(
                service="ArgoCD",
                status="unhealthy",
                message="Server pods not ready",
                timestamp=datetime.now()
            ))
    except Exception as e:
        services.append(HealthStatus(
            service="ArgoCD",
            status="error",
            message=f"Failed to check: {e}",
            timestamp=datetime.now()
        ))
    
    # Check Gitea
    try:
        gitea_pods = v1.list_namespaced_pod("git", label_selector="app.kubernetes.io/name=gitea")
        if gitea_pods.items and all(pod.status.phase == "Running" for pod in gitea_pods.items):
            services.append(HealthStatus(
                service="Gitea",
                status="healthy",
                message="Git server running",
                timestamp=datetime.now()
            ))
        else:
            services.append(HealthStatus(
                service="Gitea",
                status="unhealthy",
                message="Git server not ready",
                timestamp=datetime.now()
            ))
    except Exception as e:
        services.append(HealthStatus(
            service="Gitea",
            status="error",
            message=f"Failed to check: {e}",
            timestamp=datetime.now()
        ))
    
    # Check Traefik
    try:
        traefik_pods = v1.list_namespaced_pod("kube-system", label_selector="app.kubernetes.io/name=traefik")
        if traefik_pods.items and all(pod.status.phase == "Running" for pod in traefik_pods.items):
            services.append(HealthStatus(
                service="Traefik",
                status="healthy",
                message="Ingress controller running",
                timestamp=datetime.now()
            ))
        else:
            services.append(HealthStatus(
                service="Traefik",
                status="unhealthy",
                message="Ingress controller not ready",
                timestamp=datetime.now()
            ))
    except Exception as e:
        services.append(HealthStatus(
            service="Traefik",
            status="error",
            message=f"Failed to check: {e}",
            timestamp=datetime.now()
        ))
    
    return services


@app.get("/argocd")
async def argocd_status():
    """Get ArgoCD applications status"""
    try:
        apps = custom_api.list_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argocd",
            plural="applications"
        )
        
        applications = []
        for app in apps.get('items', []):
            status = app.get('status', {})
            applications.append({
                'name': app['metadata']['name'],
                'sync': status.get('sync', {}).get('status', 'Unknown'),
                'health': status.get('health', {}).get('status', 'Unknown'),
                'revision': status.get('sync', {}).get('revision', '')[:8] if status.get('sync', {}).get('revision') else 'Unknown'
            })
        
        return {
            'applications': applications,
            'total': len(applications),
            'synced': len([app for app in applications if app['sync'] == 'Synced']),
            'healthy': len([app for app in applications if app['health'] == 'Healthy'])
        }
        
    except Exception as e:
        logger.error(f"Failed to get ArgoCD status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gitea")
async def gitea_status():
    """Get Gitea health and basic stats"""
    try:
        # Check if Gitea is running
        gitea_pods = v1.list_namespaced_pod("git", label_selector="app.kubernetes.io/name=gitea")
        
        if not gitea_pods.items:
            return {"status": "not_found", "message": "No Gitea pods found"}
        
        running_pods = [pod for pod in gitea_pods.items if pod.status.phase == "Running"]
        
        return {
            "status": "healthy" if running_pods else "unhealthy",
            "pods_running": len(running_pods),
            "pods_total": len(gitea_pods.items),
            "message": f"{len(running_pods)}/{len(gitea_pods.items)} pods running"
        }
        
    except Exception as e:
        logger.error(f"Failed to get Gitea status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/processes/system")
async def system_resources():
    """Get system resource information"""
    try:
        resources = await process_manager.get_system_resources()
        return resources
    except Exception as e:
        logger.error(f"Failed to get system resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/processes/top")
async def top_processes(limit: int = 10):
    """Get top processes by CPU usage"""
    try:
        processes = await process_manager.get_top_processes(limit)
        return processes
    except Exception as e:
        logger.error(f"Failed to get top processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/processes/kubernetes")
async def kubernetes_processes():
    """Get Kubernetes-related processes"""
    try:
        processes = await process_manager.get_kubernetes_processes()
        return processes
    except Exception as e:
        logger.error(f"Failed to get Kubernetes processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/processes/containers")
async def container_processes():
    """Get container processes"""
    try:
        processes = await process_manager.get_container_processes()
        return processes
    except Exception as e:
        logger.error(f"Failed to get container processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/processes/alerts")
async def resource_alerts():
    """Get resource usage alerts"""
    try:
        alerts = await process_manager.check_resource_alerts()
        return {
            "alerts": alerts,
            "count": len(alerts),
            "has_critical": any(alert.get("severity") == "critical" for alert in alerts)
        }
    except Exception as e:
        logger.error(f"Failed to get resource alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/processes/{pid}/restart")
async def restart_process(pid: int):
    """Restart a process by PID"""
    try:
        result = await process_manager.restart_process(pid)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"Failed to restart process {pid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compose/project")
async def process_compose_project():
    """Get process-compose project information"""
    try:
        async with ProcessComposeManager() as pc:
            project_info = await pc.get_project_info()
            if not project_info:
                raise HTTPException(status_code=503, detail="Process-compose not available")
            return project_info
    except Exception as e:
        logger.error(f"Failed to get process-compose project info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compose/processes")
async def process_compose_processes():
    """Get all process-compose processes"""
    try:
        async with ProcessComposeManager() as pc:
            project_info = await pc.get_project_info()
            if not project_info:
                raise HTTPException(status_code=503, detail="Process-compose not available")
            return {"processes": project_info.processes}
    except Exception as e:
        logger.error(f"Failed to get process-compose processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compose/processes/{process_name}")
async def process_compose_process(process_name: str):
    """Get specific process information"""
    try:
        async with ProcessComposeManager() as pc:
            process_info = await pc.get_process_info(process_name)
            if not process_info:
                raise HTTPException(status_code=404, detail=f"Process {process_name} not found")
            return process_info
    except Exception as e:
        logger.error(f"Failed to get process info for {process_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compose/processes/{process_name}/restart")
async def restart_compose_process(process_name: str):
    """Restart a process-compose process"""
    try:
        async with ProcessComposeManager() as pc:
            result = await pc.restart_process(process_name)
            if result["status"] == "error":
                raise HTTPException(status_code=400, detail=result["message"])
            return result
    except Exception as e:
        logger.error(f"Failed to restart process {process_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compose/processes/{process_name}/start")
async def start_compose_process(process_name: str):
    """Start a process-compose process"""
    try:
        async with ProcessComposeManager() as pc:
            result = await pc.start_process(process_name)
            if result["status"] == "error":
                raise HTTPException(status_code=400, detail=result["message"])
            return result
    except Exception as e:
        logger.error(f"Failed to start process {process_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compose/processes/{process_name}/stop")
async def stop_compose_process(process_name: str):
    """Stop a process-compose process"""
    try:
        async with ProcessComposeManager() as pc:
            result = await pc.stop_process(process_name)
            if result["status"] == "error":
                raise HTTPException(status_code=400, detail=result["message"])
            return result
    except Exception as e:
        logger.error(f"Failed to stop process {process_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compose/processes/{process_name}/logs")
async def get_compose_process_logs(process_name: str, tail: int = 100):
    """Get logs for a process-compose process"""
    try:
        async with ProcessComposeManager() as pc:
            logs = await pc.get_process_logs(process_name, tail=tail)
            return {"logs": logs, "count": len(logs)}
    except Exception as e:
        logger.error(f"Failed to get logs for {process_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compose/health")
async def process_compose_health():
    """Get process-compose health status"""
    try:
        async with ProcessComposeManager() as pc:
            health = await pc.get_process_health()
            return health
    except Exception as e:
        logger.error(f"Failed to get process-compose health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )