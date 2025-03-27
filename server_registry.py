import json
import requests
from pathlib import Path
from typing import Dict, List, Optional
from rich import print as rprint
import time
from datetime import datetime
import subprocess
import os

class ServerRegistry:
    def __init__(self, local_registry_path: str = None):
        # Default to the GitHub registry if no local path is provided
        self.use_local = local_registry_path is not None
        self.github_registry_url = "https://raw.githubusercontent.com/OJamals/mcp-registry/main/registry.json"
        self.local_registry_path = local_registry_path or (Path.home() / ".cursor" / "mcp_registry.json")
        self.cache_duration = 3600  # 1 hour in seconds

    def _load_local_registry(self) -> Optional[Dict]:
        """Load the registry file."""
        try:
            # If using a local registry file specified at init, use that directly
            if self.use_local:
                if not os.path.exists(self.local_registry_path):
                    rprint(f"[red]Error: Local registry file not found at {self.local_registry_path}[/red]")
                    return None
                
                with open(self.local_registry_path, 'r') as f:
                    data = json.load(f)
                return data
            
            # Otherwise use the cache in ~/.cursor
            if not Path(self.local_registry_path).exists():
                return None

            with open(self.local_registry_path, 'r') as f:
                data = json.load(f)
                
            # Check if cache is expired (only for non-local registry)
            last_updated = datetime.fromisoformat(data.get('last_updated', '2000-01-01'))
            if (datetime.now() - last_updated).total_seconds() > self.cache_duration:
                return None
                
            return data
        except Exception as e:
            rprint(f"[yellow]Warning: Could not load registry: {str(e)}[/yellow]")
            return None

    def _save_local_registry(self, data: Dict):
        """Save the registry data to local file."""
        try:
            Path(self.local_registry_path).parent.mkdir(parents=True, exist_ok=True)
            if not self.use_local:  # Only update timestamp for cache
                data['last_updated'] = datetime.now().isoformat()
            with open(self.local_registry_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            rprint(f"[red]Error saving registry: {str(e)}[/red]")

    def update_registry(self) -> Dict:
        """Update the registry by either loading from local file or fetching from GitHub."""
        try:
            # If using a local registry file, just load it
            if self.use_local:
                data = self._load_local_registry()
                if data:
                    # Ensure data has the expected structure
                    if 'servers' not in data:
                        rprint("[yellow]Warning: Local registry is missing 'servers' field[/yellow]")
                        data = {'servers': {}}
                    rprint(f"[green]Successfully loaded local registry with {len(data.get('servers', {}))} servers[/green]")
                    return data
                return {'servers': {}}
            
            # Otherwise fetch from GitHub
            timestamp = int(time.time())
            url = f"{self.github_registry_url}?nocache={timestamp}"
            rprint(f"[yellow]Fetching registry from: {url}[/yellow]")
            
            headers = {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Validate the data structure
                if not isinstance(data, dict) or 'servers' not in data:
                    rprint("[yellow]Warning: Retrieved registry has invalid format[/yellow]")
                    data = {'servers': {}}
                
                # Validate each server entry
                valid_servers = {}
                for name, server in data.get('servers', {}).items():
                    if not isinstance(server, dict):
                        rprint(f"[yellow]Warning: Server '{name}' has invalid format - skipping[/yellow]")
                        continue
                    
                    # Ensure required fields exist
                    if 'name' not in server:
                        server['name'] = name
                    if 'description' not in server:
                        server['description'] = 'No description available'
                    if 'package_name' not in server:
                        server['package_name'] = f"unknown-{name}"
                    if 'author' not in server:
                        server['author'] = 'Unknown'
                    
                    valid_servers[name] = server
                
                # Replace with validated servers
                data['servers'] = valid_servers
                
                rprint(f"[green]Successfully fetched registry with {len(data.get('servers', {}))} servers[/green]")
                self._save_local_registry(data)
                return data
            except requests.RequestException as e:
                rprint(f"[red]Error fetching registry: {str(e)}[/red]")
                raise
        except Exception as e:
            rprint(f"[red]Error updating registry: {str(e)}[/red]")
            existing_data = self._load_local_registry()
            if existing_data:
                rprint("[yellow]Using cached registry data[/yellow]")
                return existing_data
            
            # Return empty registry as a fallback
            rprint("[yellow]Creating empty registry as fallback[/yellow]")
            return {'servers': {}}

    def get_available_servers(self) -> List[Dict]:
        """Get list of available servers from the registry."""
        data = self._load_local_registry()
        if not data:
            data = self.update_registry()
        return list(data.get('servers', {}).values())

    def get_server_info(self, server_name: str) -> Optional[Dict]:
        """Get information about a specific server."""
        data = self._load_local_registry()
        if not data:
            data = self.update_registry()
        return data.get('servers', {}).get(server_name) 