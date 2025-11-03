#!/usr/bin/env python3

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProcessStatus(BaseModel):
    name: str
    status: str
    pid: Optional[int]
    restart_count: int
    memory_kb: Optional[int]
    cpu_percent: Optional[float]
    uptime_seconds: Optional[float]
    last_exit_code: Optional[int]
    is_ready: bool
    health_check_status: str


class ProcessComposeInfo(BaseModel):
    project_name: str
    config_file: str
    processes_count: int
    running_processes: int
    processes: List[ProcessStatus]
    uptime_seconds: float
    status: str


class ProcessComposeManager:
    """Manages processes through process-compose API"""
    
    def __init__(self, api_url: str = "http://localhost:8080"):
        self.api_url = api_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=10.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def get_project_info(self) -> Optional[ProcessComposeInfo]:
        """Get overall project information"""
        try:
            response = await self.client.get(f"{self.api_url}/project")
            if response.status_code == 200:
                data = response.json()
                
                processes = []
                for proc_name, proc_data in data.get("processes", {}).items():
                    processes.append(ProcessStatus(
                        name=proc_name,
                        status=proc_data.get("status", "unknown"),
                        pid=proc_data.get("pid"),
                        restart_count=proc_data.get("restart_count", 0),
                        memory_kb=proc_data.get("mem_rss_kb"),
                        cpu_percent=proc_data.get("cpu_percent"),
                        uptime_seconds=proc_data.get("uptime_seconds"),
                        last_exit_code=proc_data.get("exit_code"),
                        is_ready=proc_data.get("is_ready", False),
                        health_check_status=proc_data.get("health", "unknown")
                    ))
                
                return ProcessComposeInfo(
                    project_name=data.get("name", "unknown"),
                    config_file=data.get("config_file", "unknown"),
                    processes_count=len(processes),
                    running_processes=sum(1 for p in processes if p.status == "Running"),
                    processes=processes,
                    uptime_seconds=data.get("uptime_seconds", 0),
                    status=data.get("status", "unknown")
                )
                
        except Exception as e:
            logger.error(f"Failed to get project info: {e}")
            return None
    
    async def get_process_info(self, process_name: str) -> Optional[ProcessStatus]:
        """Get information about a specific process"""
        try:
            response = await self.client.get(f"{self.api_url}/processes/{process_name}")
            if response.status_code == 200:
                data = response.json()
                return ProcessStatus(
                    name=process_name,
                    status=data.get("status", "unknown"),
                    pid=data.get("pid"),
                    restart_count=data.get("restart_count", 0),
                    memory_kb=data.get("mem_rss_kb"),
                    cpu_percent=data.get("cpu_percent"),
                    uptime_seconds=data.get("uptime_seconds"),
                    last_exit_code=data.get("exit_code"),
                    is_ready=data.get("is_ready", False),
                    health_check_status=data.get("health", "unknown")
                )
                
        except Exception as e:
            logger.error(f"Failed to get process info for {process_name}: {e}")
            return None
    
    async def restart_process(self, process_name: str) -> Dict[str, str]:
        """Restart a specific process"""
        try:
            response = await self.client.post(f"{self.api_url}/processes/{process_name}/restart")
            if response.status_code == 200:
                return {"status": "success", "message": f"Process {process_name} restart initiated"}
            else:
                return {"status": "error", "message": f"Failed to restart {process_name}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Failed to restart process {process_name}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def start_process(self, process_name: str) -> Dict[str, str]:
        """Start a specific process"""
        try:
            response = await self.client.post(f"{self.api_url}/processes/{process_name}/start")
            if response.status_code == 200:
                return {"status": "success", "message": f"Process {process_name} start initiated"}
            else:
                return {"status": "error", "message": f"Failed to start {process_name}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Failed to start process {process_name}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def stop_process(self, process_name: str) -> Dict[str, str]:
        """Stop a specific process"""
        try:
            response = await self.client.post(f"{self.api_url}/processes/{process_name}/stop")
            if response.status_code == 200:
                return {"status": "success", "message": f"Process {process_name} stop initiated"}
            else:
                return {"status": "error", "message": f"Failed to stop {process_name}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Failed to stop process {process_name}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_process_logs(self, process_name: str, follow: bool = False, tail: int = 100) -> List[str]:
        """Get logs for a specific process"""
        try:
            params = {"tail": tail}
            if follow:
                params["follow"] = "true"
                
            response = await self.client.get(f"{self.api_url}/processes/{process_name}/logs", params=params)
            if response.status_code == 200:
                # Process-compose returns logs as text, split by lines
                logs = response.text.strip().split('\n') if response.text.strip() else []
                return logs
            else:
                return [f"Failed to get logs: {response.text}"]
                
        except Exception as e:
            logger.error(f"Failed to get logs for {process_name}: {e}")
            return [f"Error getting logs: {e}"]
    
    async def scale_process(self, process_name: str, replicas: int) -> Dict[str, str]:
        """Scale a process to specified number of replicas"""
        try:
            payload = {"replicas": replicas}
            response = await self.client.post(f"{self.api_url}/processes/{process_name}/scale", json=payload)
            if response.status_code == 200:
                return {"status": "success", "message": f"Process {process_name} scaled to {replicas} replicas"}
            else:
                return {"status": "error", "message": f"Failed to scale {process_name}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Failed to scale process {process_name}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_process_health(self) -> Dict[str, str]:
        """Get overall process health status"""
        try:
            project_info = await self.get_project_info()
            if not project_info:
                return {"status": "error", "message": "Process-compose not available"}
            
            total_processes = project_info.processes_count
            running_processes = project_info.running_processes
            failed_processes = [p for p in project_info.processes if p.status in ["Failed", "Crashed"]]
            
            if len(failed_processes) > 0:
                return {
                    "status": "unhealthy",
                    "message": f"{len(failed_processes)} processes failed: {', '.join(p.name for p in failed_processes)}"
                }
            elif running_processes == total_processes:
                return {"status": "healthy", "message": f"All {total_processes} processes running"}
            else:
                return {
                    "status": "degraded", 
                    "message": f"{running_processes}/{total_processes} processes running"
                }
                
        except Exception as e:
            logger.error(f"Failed to get process health: {e}")
            return {"status": "error", "message": str(e)}
    
    async def is_available(self) -> bool:
        """Check if process-compose API is available"""
        try:
            response = await self.client.get(f"{self.api_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False