#!/usr/bin/env python3

import asyncio
import logging
import os
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional

import psutil
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProcessInfo(BaseModel):
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    create_time: datetime
    uptime_seconds: float
    cmdline: List[str]


class SystemResources(BaseModel):
    cpu_percent: float
    cpu_count: int
    memory_total_gb: float
    memory_used_gb: float
    memory_percent: float
    disk_usage_percent: float
    disk_free_gb: float
    load_average: List[float]
    boot_time: datetime


class ProcessManager:
    """Manages and monitors system processes for the K8s Health Monitor"""
    
    def __init__(self):
        self.monitored_processes = {}
        self.start_time = time.time()
        
    async def get_system_resources(self) -> SystemResources:
        """Get comprehensive system resource information"""
        try:
            # CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory info
            memory = psutil.virtual_memory()
            memory_total_gb = memory.total / (1024**3)
            memory_used_gb = memory.used / (1024**3)
            
            # Disk info
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)
            
            # Load average (Unix-like systems)
            try:
                load_avg = list(os.getloadavg())
            except (OSError, AttributeError):
                load_avg = [0.0, 0.0, 0.0]
            
            # Boot time
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            
            return SystemResources(
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                memory_total_gb=round(memory_total_gb, 2),
                memory_used_gb=round(memory_used_gb, 2),
                memory_percent=memory.percent,
                disk_usage_percent=round(disk_usage_percent, 2),
                disk_free_gb=round(disk_free_gb, 2),
                load_average=load_avg,
                boot_time=boot_time
            )
            
        except Exception as e:
            logger.error(f"Failed to get system resources: {e}")
            raise
    
    async def get_kubernetes_processes(self) -> List[ProcessInfo]:
        """Get processes related to Kubernetes components"""
        k8s_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 
                                           'memory_percent', 'memory_info', 'create_time', 'cmdline']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name']
                    cmdline = proc_info['cmdline'] or []
                    
                    # Check if it's a Kubernetes-related process
                    k8s_keywords = ['k3s', 'containerd', 'runc', 'kubelet', 'kubectl', 
                                   'traefik', 'coredns', 'argocd', 'gitea', 'uvicorn', 
                                   'python', 'gunicorn']
                    
                    if any(keyword in proc_name.lower() for keyword in k8s_keywords) or \
                       any(any(keyword in arg.lower() for keyword in k8s_keywords) for arg in cmdline):
                        
                        # Get detailed process info
                        try:
                            cpu_percent = proc.cpu_percent()
                            memory_info = proc.memory_info()
                            memory_mb = memory_info.rss / (1024 * 1024)
                            
                            create_time = datetime.fromtimestamp(proc_info['create_time'])
                            uptime = time.time() - proc_info['create_time']
                            
                            k8s_processes.append(ProcessInfo(
                                pid=proc_info['pid'],
                                name=proc_name,
                                status=proc_info['status'],
                                cpu_percent=round(cpu_percent, 2),
                                memory_percent=round(proc_info['memory_percent'], 2),
                                memory_mb=round(memory_mb, 2),
                                create_time=create_time,
                                uptime_seconds=round(uptime, 1),
                                cmdline=cmdline[:3]  # Truncate for readability
                            ))
                            
                        except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                            continue
                            
                except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to get Kubernetes processes: {e}")
            raise
            
        # Sort by CPU usage
        return sorted(k8s_processes, key=lambda x: x.cpu_percent, reverse=True)
    
    async def get_container_processes(self) -> List[ProcessInfo]:
        """Get processes running inside containers"""
        container_processes = []
        
        try:
            # Look for processes with container-related patterns
            for proc in psutil.process_iter(['pid', 'name', 'ppid', 'cmdline']):
                try:
                    # Check if process is likely in a container
                    cmdline = proc.info['cmdline'] or []
                    if any('/pause' in arg or 'containerd-shim' in arg for arg in cmdline):
                        continue
                        
                    # Get children of containerd-shim processes (actual container processes)
                    if proc.info['name'] in ['python', 'uvicorn', 'gunicorn', 'node', 'nginx']:
                        try:
                            proc_obj = psutil.Process(proc.info['pid'])
                            cpu_percent = proc_obj.cpu_percent()
                            memory_info = proc_obj.memory_info()
                            memory_percent = proc_obj.memory_percent()
                            
                            container_processes.append(ProcessInfo(
                                pid=proc.info['pid'],
                                name=proc.info['name'],
                                status=proc_obj.status(),
                                cpu_percent=round(cpu_percent, 2),
                                memory_percent=round(memory_percent, 2),
                                memory_mb=round(memory_info.rss / (1024 * 1024), 2),
                                create_time=datetime.fromtimestamp(proc_obj.create_time()),
                                uptime_seconds=round(time.time() - proc_obj.create_time(), 1),
                                cmdline=cmdline[:3]
                            ))
                            
                        except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                            continue
                            
                except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to get container processes: {e}")
            
        return sorted(container_processes, key=lambda x: x.cpu_percent, reverse=True)
    
    async def get_top_processes(self, limit: int = 10) -> List[ProcessInfo]:
        """Get top processes by CPU usage"""
        top_processes = []
        
        try:
            for proc in psutil.process_iter():
                try:
                    proc_info = proc.as_dict(['pid', 'name', 'status', 'cpu_percent', 
                                            'memory_percent', 'memory_info', 'create_time', 'cmdline'])
                    
                    # Skip kernel threads and processes with no name
                    if not proc_info['name'] or proc_info['name'].startswith('['):
                        continue
                        
                    memory_mb = proc_info['memory_info'].rss / (1024 * 1024)
                    create_time = datetime.fromtimestamp(proc_info['create_time'])
                    uptime = time.time() - proc_info['create_time']
                    
                    top_processes.append(ProcessInfo(
                        pid=proc_info['pid'],
                        name=proc_info['name'],
                        status=proc_info['status'],
                        cpu_percent=round(proc_info['cpu_percent'], 2),
                        memory_percent=round(proc_info['memory_percent'], 2),
                        memory_mb=round(memory_mb, 2),
                        create_time=create_time,
                        uptime_seconds=round(uptime, 1),
                        cmdline=(proc_info['cmdline'] or [])[:3]
                    ))
                    
                except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to get top processes: {e}")
            
        # Sort by CPU usage and limit results
        return sorted(top_processes, key=lambda x: x.cpu_percent, reverse=True)[:limit]
    
    async def restart_process(self, pid: int) -> Dict[str, str]:
        """Restart a process by PID (if allowed)"""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            
            # Only allow restarting certain processes for safety
            allowed_processes = ['uvicorn', 'gunicorn', 'python', 'node']
            
            if proc_name not in allowed_processes:
                return {"status": "error", "message": f"Restarting {proc_name} not allowed"}
            
            # Send SIGTERM first, then SIGKILL if needed
            proc.terminate()
            
            # Wait for graceful shutdown
            try:
                proc.wait(timeout=10)
                return {"status": "success", "message": f"Process {pid} ({proc_name}) terminated successfully"}
            except psutil.TimeoutExpired:
                proc.kill()
                return {"status": "success", "message": f"Process {pid} ({proc_name}) killed after timeout"}
                
        except psutil.NoSuchProcess:
            return {"status": "error", "message": f"Process {pid} not found"}
        except psutil.AccessDenied:
            return {"status": "error", "message": f"Access denied to process {pid}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to restart process {pid}: {e}"}
    
    async def check_resource_alerts(self) -> List[Dict[str, str]]:
        """Check for resource usage alerts"""
        alerts = []
        
        try:
            resources = await self.get_system_resources()
            
            # CPU alert
            if resources.cpu_percent > 80:
                alerts.append({
                    "type": "cpu",
                    "severity": "warning" if resources.cpu_percent < 90 else "critical",
                    "message": f"High CPU usage: {resources.cpu_percent}%"
                })
            
            # Memory alert
            if resources.memory_percent > 80:
                alerts.append({
                    "type": "memory", 
                    "severity": "warning" if resources.memory_percent < 90 else "critical",
                    "message": f"High memory usage: {resources.memory_percent}%"
                })
            
            # Disk alert
            if resources.disk_usage_percent > 85:
                alerts.append({
                    "type": "disk",
                    "severity": "warning" if resources.disk_usage_percent < 95 else "critical", 
                    "message": f"High disk usage: {resources.disk_usage_percent}%"
                })
            
            # Load average alert (for systems that support it)
            if len(resources.load_average) > 0 and resources.load_average[0] > resources.cpu_count * 2:
                alerts.append({
                    "type": "load",
                    "severity": "warning",
                    "message": f"High load average: {resources.load_average[0]}"
                })
                
        except Exception as e:
            alerts.append({
                "type": "system",
                "severity": "error", 
                "message": f"Failed to check resource alerts: {e}"
            })
            
        return alerts