import json
import requests
from pathlib import Path
from typing import Dict, List, Optional
from rich import print as rprint
import time
from datetime import datetime
import subprocess
import sys

class ServerRegistry:
    def __init__(self, registry_url: str = "https://raw.githubusercontent.com/OJamals/mcp-registry/main/registry.json"):
        self.registry_url = registry_url
        self.local_registry_path = Path.home() / ".cursor" / "mcp_registry.json"
        self.cache_duration = 3600  # 1 hour in seconds

    def _load_local_registry(self) -> Optional[Dict]:
        """Load the local registry file if it exists and is not expired."""
        try:
            if not self.local_registry_path.exists():
                return None

            with open(self.local_registry_path, 'r') as f:
                data = json.load(f)
                
            # Check if cache is expired
            last_updated = datetime.fromisoformat(data.get('last_updated', '2000-01-01'))
            if (datetime.now() - last_updated).total_seconds() > self.cache_duration:
                return None
                
            return data
        except Exception as e:
            rprint(f"[yellow]Warning: Could not load local registry: {str(e)}[/yellow]")
            return None

    def _save_local_registry(self, data: Dict):
        """Save the registry data to local file."""
        try:
            self.local_registry_path.parent.mkdir(parents=True, exist_ok=True)
            data['last_updated'] = datetime.now().isoformat()
            with open(self.local_registry_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            rprint(f"[red]Error saving local registry: {str(e)}[/red]")

    def update_registry(self) -> Dict:
        """Fetch the latest registry from the remote URL."""
        try:
            # Add timestamp to bypass caching
            timestamp = int(time.time())
            url = f"{self.registry_url}?t={timestamp}"
            rprint(f"[yellow]Fetching registry from: {url}[/yellow]")
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            rprint(f"[green]Successfully fetched registry with {len(data.get('servers', {}))} servers[/green]")
            self._save_local_registry(data)
            return data
        except Exception as e:
            rprint(f"[red]Error updating registry: {str(e)}[/red]")
            return self._load_local_registry() or {'servers': {}}

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

    def install_server(self, server_name: str) -> bool:
        """Install a server from the registry."""
        server_info = self.get_server_info(server_name)
        if not server_info:
            rprint(f"[red]Error: Server '{server_name}' not found in registry[/red]")
            return False

        try:
            # Collect environment variables and placeholder values
            env_vars = {}
            
            # Check if server requires environment variables
            if "env" in server_info and server_info["env"]:
                rprint(f"[yellow]Server '{server_name}' requires the following environment variables:[/yellow]")
                for var_name, description in server_info["env"].items():
                    rprint(f"  [cyan]{var_name}[/cyan]: {description}")
                
                # Ask if user wants to provide values now
                if self._confirm_with_prompt("Would you like to provide values for these environment variables now?"):
                    for var_name, description in server_info["env"].items():
                        value = self._prompt_for_value(var_name, description)
                        if value:
                            env_vars[var_name] = value
                    
                    if not env_vars:
                        # If no values were provided, confirm if user wants to proceed
                        if not self._confirm_installation():
                            rprint(f"[yellow]Installation of '{server_name}' cancelled.[/yellow]")
                            return False
                else:
                    # If user doesn't want to provide values now, confirm if they want to proceed
                    if not self._confirm_installation():
                        rprint(f"[yellow]Installation of '{server_name}' cancelled.[/yellow]")
                        return False
            
            # Process args that contain placeholders in curly braces
            if "args" in server_info:
                modified_args = []
                placeholders_found = False
                
                for arg in server_info["args"]:
                    # Check if arg contains placeholders (text between curly braces)
                    if isinstance(arg, str) and "{" in arg and "}" in arg:
                        import re
                        # Find all placeholders in this arg
                        placeholders = re.findall(r'\{([^}]+)\}', arg)
                        modified_arg = arg
                        
                        for placeholder in placeholders:
                            # Skip the special {install_dir} placeholder
                            if placeholder == "install_dir":
                                # Will be replaced later
                                continue
                            
                            placeholders_found = True
                            # Prompt user for value
                            rprint(f"[yellow]Argument requires a value for [cyan]{{{placeholder}}}[/cyan][/yellow]")
                            value = self._prompt_for_value(placeholder)
                            
                            # Replace placeholder with value
                            modified_arg = modified_arg.replace(f"{{{placeholder}}}", value)
                        
                        modified_args.append(modified_arg)
                    else:
                        modified_args.append(arg)
                
                # If placeholders were found, update args
                if placeholders_found:
                    # Replace {install_dir} with the actual path
                    install_dir = self._get_install_dir(server_info['package_name'])
                    for i, arg in enumerate(modified_args):
                        if isinstance(arg, str):
                            modified_args[i] = arg.replace("{install_dir}", install_dir)
                    
                    server_info["args"] = modified_args
                    rprint("[green]Updated command arguments with your provided values.[/green]")

            # Install the package using npm
            package_name = server_info['package_name']
            rprint(f"[yellow]Installing {package_name}...[/yellow]")
            
            result = subprocess.run(
                f"npm install -g {package_name}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                rprint(f"[red]Error installing server: {result.stderr}[/red]")
                return False

            # Add to Cursor's config
            cursor_config_path = Path.home() / ".cursor" / "mcp.json"
            try:
                with open(cursor_config_path, 'r') as f:
                    config = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                config = {"mcpServers": {}}

            server_config = {
                'command': server_info['command'],
                'args': server_info['args'],
                'description': server_info.get('description', '')
            }
            
            # Add environment variables if provided
            if env_vars:
                server_config['env'] = env_vars
                
            config['mcpServers'][server_name] = server_config

            with open(cursor_config_path, 'w') as f:
                json.dump(config, f, indent=2)

            # Remind user about required environment variables that weren't provided
            if "env" in server_info and server_info["env"]:
                missing_vars = [var for var in server_info["env"] if var not in env_vars]
                if missing_vars:
                    rprint(f"[yellow]IMPORTANT: Before using '{server_name}', make sure to set these environment variables:[/yellow]")
                    for var_name in missing_vars:
                        rprint(f"  [cyan]{var_name}[/cyan]: {server_info['env'][var_name]}")

            rprint(f"[green]Successfully installed '{server_name}'[/green]")
            return True

        except Exception as e:
            rprint(f"[red]Error installing server: {str(e)}[/red]")
            return False

    def _confirm_installation(self) -> bool:
        """Ask user to confirm installation of server with environment variables."""
        try:
            from rich.prompt import Confirm
            return Confirm.ask("Do you want to proceed with installation? You'll need to set the required environment variables before using this server.")
        except ImportError:
            # Fallback if rich.prompt is not available
            response = input("Do you want to proceed with installation? You'll need to set the required environment variables before using this server. (y/n): ")
            return response.lower() in ['y', 'yes']

    def _confirm_with_prompt(self, message: str) -> bool:
        """Ask user to confirm with a custom message."""
        try:
            from rich.prompt import Confirm
            return Confirm.ask(message)
        except ImportError:
            # Fallback if rich.prompt is not available
            response = input(f"{message} (y/n): ")
            return response.lower() in ['y', 'yes']

    def _prompt_for_value(self, placeholder: str, description: str = None) -> str:
        """Prompt the user for a value to replace a placeholder."""
        prompt_text = f"Enter value for {{{placeholder}}}"
        if description:
            prompt_text = f"Enter value for {placeholder} ({description})"
            
        try:
            from rich.prompt import Prompt
            return Prompt.ask(prompt_text)
        except ImportError:
            # Fallback if rich.prompt is not available
            return input(f"{prompt_text}: ")
    
    def _get_install_dir(self, package_name: str) -> str:
        """Get the installation directory for an npm package."""
        try:
            # Try to find the global npm installation directory
            result = subprocess.run(
                "npm root -g",
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                npm_root = result.stdout.strip()
                # The package directory would be inside this root
                package_name_clean = package_name.split('/')[-1].replace('@', '')
                return str(Path(npm_root) / package_name_clean)
            
            # Fallback to a common location
            if sys.platform.startswith('win'):
                return str(Path.home() / "AppData" / "Roaming" / "npm" / "node_modules")
            else:
                return "/usr/local/lib/node_modules"
                
        except Exception as e:
            rprint(f"[yellow]Warning: Could not determine install directory: {str(e)}[/yellow]")
            return "/path/to/mcp/server" 