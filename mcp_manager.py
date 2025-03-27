#!/usr/bin/env python3

import click
import psutil
import yaml
import os
import sys
import json
from rich.console import Console
from rich.table import Table
from rich import print as rprint
import subprocess
from typing import List, Dict, Optional
from pathlib import Path
import signal
import requests
import time

# Fix import to work both as module and script
try:
    from mcp_server_manager.server_registry import ServerRegistry
except ModuleNotFoundError:
    from server_registry import ServerRegistry

console = Console()

class MCPServerManager:
    def __init__(self):
        self.cursor_config_path = os.path.expanduser("~/.cursor/mcp.json")
        self.config = self._load_cursor_config()
        
        # Use the local registry file
        local_registry_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry.json")
        self.registry = ServerRegistry(local_registry_path)
        
    def _load_cursor_config(self) -> Dict:
        """Load Cursor's MCP configuration."""
        try:
            with open(self.cursor_config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            rprint(f"[red]Error loading Cursor MCP config: {str(e)}[/red]")
            return {"mcpServers": {}}

    def _find_npm_path(self) -> str:
        """Find the npm executable path."""
        try:
            if os.name == 'nt':  # Windows
                npm_path = subprocess.check_output(['where', 'npm']).decode().strip()
            else:  # Unix-like
                npm_path = subprocess.check_output(['which', 'npm']).decode().strip()
            return npm_path
        except subprocess.CalledProcessError:
            rprint("[red]Error: npm not found. Please install Node.js and npm.[/red]")
            sys.exit(1)

    def detect_cursor_mcp_servers(self) -> List[Dict]:
        """Detect running Cursor MCP servers."""
        mcp_servers = []
        
        # Print config server names for debugging
        rprint(f"[dim]DEBUG: Looking for these configured servers: {', '.join(self.config['mcpServers'].keys())}[/dim]")
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'connections']):
            try:
                cmdline = proc.info['cmdline']
                if not cmdline:
                    continue

                cmd_str = ' '.join(cmdline)
                
                # Debug any node.js process that might be related to our servers
                if ('node' in cmd_str and 
                    ('mcp-server' in cmd_str or 
                     'modelcontextprotocol' in cmd_str or 
                     'server-' in cmd_str or 
                     'e2b' in cmd_str or
                     'smithery' in cmd_str)):
                    rprint(f"[dim]DEBUG: Found potential MCP server: PID {proc.pid}: {cmd_str[:100]}...[/dim]")
                
                # Match against known MCP servers from config
                for server_name, server_config in self.config['mcpServers'].items():
                    if self._is_mcp_server_process(cmdline, server_config):
                        connections = proc.connections()
                        ports = [conn.laddr.port for conn in connections if conn.status == 'LISTEN']
                        
                        server_info = {
                            'name': server_name,
                            'pid': proc.pid,
                            'ports': ports,
                            'command': ' '.join(cmdline),
                            'status': 'Running',
                            'config': server_config
                        }
                        
                        try:
                            server_info['working_dir'] = proc.cwd()
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            server_info['working_dir'] = 'N/A'
                        
                        rprint(f"[dim]DEBUG: Found MCP server: {server_name} (PID: {proc.pid})[/dim]")
                        mcp_servers.append(server_info)
                        break

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return mcp_servers

    def _is_mcp_server_process(self, cmdline: List[str], server_config: Dict) -> bool:
        """Check if a process matches an MCP server configuration."""
        if not cmdline or len(cmdline) < 2:
            return False
        
        # First check: exclude Cursor application
        cmd_str = ' '.join(cmdline)
        if 'Cursor.app/Contents/MacOS/Cursor' in cmd_str:
            return False
        
        # Extract the server name from server_config
        server_name = next((name for name, config in self.config['mcpServers'].items() 
                          if config == server_config), None)
                          
        # Print extended debug for e2b
        if server_name == 'e2b':
            rprint(f"[dim]DEBUG: Checking if process is e2b: {cmd_str[:150]}...[/dim]")
        
        # Special cases for known servers
        if server_name == 'filesystem':
            # Just check for the presence of server-filesystem in command
            if '@modelcontextprotocol/server-filesystem' in cmd_str or 'mcp-server-filesystem' in cmd_str:
                return True
                
        elif server_name == 'memory':
            # Just check for the presence of server-memory in command
            if (('mcp-server-memory' in cmd_str) or
                ('@modelcontextprotocol/server-memory' in cmd_str)):
                return True
                
        elif server_name == 'sequential-thinking':
            # Just check for the presence of server-sequential-thinking in command
            if (('mcp-server-sequential-thinking' in cmd_str) or
                ('@modelcontextprotocol/server-sequential-thinking' in cmd_str)):
                return True
                
        elif server_name == 'e2b':
            # Check for any indication of e2b in the command line
            if any(pattern in cmd_str for pattern in [
                '@smithery/cli run e2b', 
                'run e2b', 
                '@e2b/mcp-server',
                'e2b --config'
            ]):
                rprint(f"[dim]DEBUG: Found e2b server process: {cmd_str[:100]}...[/dim]")
                return True
        
        # For all other servers, do a more generic check
        # Case 1: npm exec or npx direct command match
        if (('npm exec @modelcontextprotocol/server-' + server_name in cmd_str or
            'npx @modelcontextprotocol/server-' + server_name in cmd_str or
            'npm exec mcp-server-' + server_name in cmd_str or
            'npx mcp-server-' + server_name in cmd_str)):
            return True
            
        # Case 2: node direct execution of server binary
        if f'mcp-server-{server_name}' in cmd_str:
            return True
            
        # Extract the exact package identifier from args
        package_identifier = None
        for arg in server_config.get('args', []):
            if (arg.startswith('@modelcontextprotocol/server-') or 
                arg.startswith('mcp-server-') or
                arg.startswith('@e2b/') or
                arg == 'e2b'):
                package_identifier = arg
                break
        
        # If we have a package identifier, look for it in the command line
        if package_identifier and package_identifier in cmd_str:
            return True
        
        return False
        
    def _check_process_is_listening(self, pid_or_cmd):
        """Check if a process is actually listening on a port."""
        try:
            if isinstance(pid_or_cmd, int):
                pid = pid_or_cmd
            else:
                # Try to extract PID from command
                pid = None
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    if proc.info['cmdline'] and pid_or_cmd in ' '.join(proc.info['cmdline']):
                        pid = proc.pid
                        break
                        
            if pid:
                try:
                    proc = psutil.Process(pid)
                    connections = proc.connections()
                    
                    # Print debug info
                    cmd_str = ' '.join(proc.cmdline())
                    rprint(f"[dim]DEBUG: Checking process {pid}: {cmd_str[:50]}...[/dim]")
                    if connections:
                        rprint(f"[dim]DEBUG: Process has {len(connections)} connections[/dim]")
                        for conn in connections:
                            if conn.status == 'LISTEN':
                                rprint(f"[dim]DEBUG: Found LISTEN connection on port {conn.laddr.port}[/dim]")
                                return True
                    
                    # Let's be more permissive for MCP servers that might not have active connections yet
                    # If it's a Node.js process with MCP server or e2b in command, assume it's a server
                    if ('node' in cmd_str.lower() and 
                        ('mcp-server' in cmd_str.lower() or 
                         'server-' in cmd_str.lower() or 
                         'e2b' in cmd_str or 
                         'smithery' in cmd_str)):
                        rprint(f"[dim]DEBUG: Process appears to be an MCP server based on command[/dim]")
                        return True
                        
                    return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return False
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def list_servers(self):
        """List all Cursor MCP servers (both running and configured)."""
        detected_servers = self.detect_cursor_mcp_servers()
        
        # Debug - print detected servers
        for server in detected_servers:
            rprint(f"[dim]DEBUG: list_servers detected: {server['name']} (PID: {server['pid']})[/dim]")
        
        table = Table(title="Cursor MCP Servers")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Description", style="yellow")
        
        # Add all configured servers
        for name, config in self.config['mcpServers'].items():
            running_server = next((s for s in detected_servers if s['name'] == name), None)
            
            status = "Running" if running_server else "Stopped"
            description = config.get('description', 'No description available')
            
            # Debug - show if server is found as running or not
            if running_server:
                rprint(f"[dim]DEBUG: Server '{name}' found as running (PID: {running_server['pid']})[/dim]")
            else:
                rprint(f"[dim]DEBUG: Server '{name}' not found as running[/dim]")
            
            table.add_row(name, status, description)
        
        console.print(table)

    def start_server(self, server_name: str):
        """Start a specific MCP server."""
        if server_name not in self.config['mcpServers']:
            rprint(f"[red]Error: Server '{server_name}' not found in configuration[/red]")
            return False

        # Check if already running
        running_servers = self.detect_cursor_mcp_servers()
        
        # Debug info
        rprint(f"[dim]DEBUG: Detected {len(running_servers)} running servers:[/dim]")
        for server in running_servers:
            rprint(f"[dim]DEBUG: - {server['name']} (PID: {server['pid']})[/dim]")
            
        if any(s['name'] == server_name for s in running_servers):
            rprint(f"[yellow]Server '{server_name}' is already running[/yellow]")
            return True

        server_config = self.config['mcpServers'][server_name]
        cmd = [server_config['command']] + server_config['args']
        
        # Debug info
        rprint(f"[dim]DEBUG: Starting server with command: {' '.join(cmd)}[/dim]")

        try:
            # Start the server in the background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # This makes it run in the background
            )
            rprint(f"[green]Started server '{server_name}' (PID: {process.pid})[/green]")
            return True
        except subprocess.CalledProcessError as e:
            rprint(f"[red]Error starting server '{server_name}': {e}[/red]")
            return False
        except Exception as e:
            rprint(f"[red]Unexpected error starting server '{server_name}': {str(e)}[/red]")
            return False

    def stop_server(self, server_name: str):
        """Stop a specific MCP server."""
        if server_name not in self.config['mcpServers']:
            rprint(f"[red]Error: Server '{server_name}' not found in configuration[/red]")
            return False

        running_servers = self.detect_cursor_mcp_servers()
        server = next((s for s in running_servers if s['name'] == server_name), None)
        
        if not server:
            rprint(f"[yellow]Server '{server_name}' is not running[/yellow]")
            return True

        try:
            # Get process
            process = psutil.Process(server['pid'])
            
            # ENHANCED SAFETY CHECKS: Don't kill anything that might be Cursor or system processes
            process_cmd = ' '.join(process.cmdline())
            
            # Cursor app protection
            cursor_patterns = [
                'Cursor.app', 
                'cursor.app',
                '/Applications/Cursor',
                'Cursor Helper',
                'cursor_',
                'CursorUpdate'
            ]
            
            if any(pattern in process_cmd for pattern in cursor_patterns):
                rprint(f"[red]Error: Refusing to stop process that appears to be Cursor[/red]")
                return False
                
            # Verify it's an MCP server based on server_name and cmdline
            mcp_patterns = [
                f'mcp-server-{server_name}',
                f'server-{server_name}',
                f'@modelcontextprotocol/server-{server_name}',
                f'@e2b/mcp-server'
            ]
            
            # Add specific case for e2b
            if server_name == 'e2b':
                mcp_patterns.extend(['@smithery/cli run e2b', 'e2b --config'])
                
            # Add specific pattern for memory server
            if server_name == 'memory':
                mcp_patterns.extend(['server-memory', 'mcp-server-memory'])
                
            # Add specific pattern for sequential thinking
            if server_name == 'sequential-thinking':
                mcp_patterns.extend(['server-sequential-thinking', 'mcp-server-sequential-thinking'])
                
            # Only kill if we match at least one expected MCP pattern
            if not any(pattern in process_cmd for pattern in mcp_patterns):
                rprint(f"[red]Error: Process does not match expected MCP server pattern for '{server_name}'[/red]")
                return False
                
            # Additional sanity check - don't kill processes that have been running much longer than expected
            # MCP servers should be recently started
            process_create_time = process.create_time()
            if (time.time() - process_create_time) > 86400:  # older than 1 day
                rprint(f"[red]Error: Process has been running too long to be an MCP server[/red]")
                return False
                
            # Kill process and its children
            for child in process.children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            process.kill()
            
            rprint(f"[green]Successfully stopped server '{server_name}'[/green]")
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            rprint(f"[yellow]Server '{server_name}' was already stopped[/yellow]")
            return True
        except Exception as e:
            rprint(f"[red]Error stopping server '{server_name}': {str(e)}[/red]")
            return False

    def get_server_functions(self, server_name: str):
        """Get detailed information about a server's available functions."""
        if server_name not in self.config['mcpServers']:
            rprint(f"[red]Error: Server '{server_name}' not found in configuration[/red]")
            return

        server_config = self.config['mcpServers'][server_name]
        
        # First check if the server is running
        running_servers = self.detect_cursor_mcp_servers()
        running_server = next((s for s in running_servers if s['name'] == server_name), None)
        
        if not running_server:
            rprint(f"[yellow]Note: Server '{server_name}' is not running. Starting it temporarily...[/yellow]")
            self.start_server(server_name)
            # Give it a moment to start
            time.sleep(2)
            running_servers = self.detect_cursor_mcp_servers()
            running_server = next((s for s in running_servers if s['name'] == server_name), None)
            if not running_server:
                rprint(f"[red]Error: Could not start server '{server_name}'[/red]")
                return

        # Try to get server information from package
        try:
            # Find the package name from args
            package_name = None
            for arg in server_config['args']:
                if '@' in arg:
                    package_name = arg
                    break
                elif 'mcp-' in arg or arg.endswith('-mcp'):
                    package_name = arg
                    break

            if not package_name:
                rprint(f"[red]Error: Could not determine package name for '{server_name}'[/red]")
                return

            rprint(f"[bold]Server: {server_name}[/bold]")
            rprint(f"[bold]Package: {package_name}[/bold]")
            rprint()

            # Display available functions
            table = Table(title=f"Available Functions")
            table.add_column("Function Name", style="cyan")
            table.add_column("Description", style="yellow")
            table.add_column("Parameters", style="green")

            # Get function information based on server type
            if 'filesystem' in package_name:
                functions = [
                    ("read_file", "Read the contents of a file", "path: string"),
                    ("write_file", "Write content to a file", "path: string, content: string"),
                    ("list_directory", "List contents of a directory", "path: string"),
                    ("create_directory", "Create a new directory", "path: string"),
                    ("delete_file", "Delete a file", "path: string"),
                    ("move_file", "Move or rename a file", "source: string, destination: string"),
                ]
            elif 'browser-tools' in package_name:
                functions = [
                    ("getConsoleLogs", "Get browser console logs", "None"),
                    ("getConsoleErrors", "Get browser console errors", "None"),
                    ("getNetworkLogs", "Get network request logs", "None"),
                    ("takeScreenshot", "Take a screenshot", "None"),
                    ("runSEOAudit", "Run SEO audit", "None"),
                    ("runDebuggerMode", "Start debugger mode", "None"),
                ]
            elif 'server-llm-txt' in package_name:
                functions = [
                    ("list_llm_txt", "List available LLM.txt files", "None"),
                    ("get_llm_txt", "Get contents of an LLM.txt file", "id: number, page: number"),
                    ("search_llm_txt", "Search within LLM.txt files", "id: number, queries: string[]"),
                ]
            elif 'mcp-shell' in package_name:
                functions = [
                    ("connect", "Connect to an MCP server", "url: string"),
                    ("disconnect", "Disconnect from current server", "None"),
                    ("list", "List available functions", "None"),
                    ("call", "Call a function", "function: string, params: object"),
                    ("help", "Show help for a function", "function: string"),
                ]
            else:
                # Generic MCP server functions
                functions = [
                    ("start", "Start the server", "None"),
                    ("stop", "Stop the server", "None"),
                    ("status", "Get server status", "None"),
                    ("version", "Get server version", "None"),
                ]

            for func_name, description, params in functions:
                table.add_row(func_name, description, params)

            console.print(table)

        except Exception as e:
            rprint(f"[red]Error getting server functions: {str(e)}[/red]")

    def uninstall_server(self, server_name: str):
        """Uninstall a specific MCP server."""
        if server_name not in self.config['mcpServers']:
            rprint(f"[red]Error: Server '{server_name}' not found in configuration[/red]")
            return False

        # First stop the server if it's running
        running_servers = self.detect_cursor_mcp_servers()
        if any(s['name'] == server_name for s in running_servers):
            rprint(f"[yellow]Stopping server '{server_name}' before uninstalling...[/yellow]")
            if not self.stop_server(server_name):
                rprint(f"[red]Failed to stop server '{server_name}'. Aborting uninstall.[/red]")
                return False
            time.sleep(2)  # Give it time to stop

        server_config = self.config['mcpServers'][server_name]
        
        # Try to find the package name from args
        package_name = None
        for arg in server_config['args']:
            if '@' in arg:
                package_name = arg
                break
            elif 'mcp-' in arg or arg.endswith('-mcp'):
                package_name = arg
                break

        if not package_name:
            rprint(f"[red]Error: Could not determine package name for '{server_name}'[/red]")
            return False

        try:
            # Uninstall the package using npm
            rprint(f"[yellow]Uninstalling {package_name}...[/yellow]")
            
            # Use shell=True to prevent process termination issues
            result = subprocess.run(
                f"npm uninstall -g {package_name}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30  # Add timeout to prevent hanging
            )
            
            if result.returncode != 0:
                rprint(f"[red]Error uninstalling server: {result.stderr}[/red]")
                return False

            # Remove from Cursor's config
            self.config['mcpServers'].pop(server_name)
            
            # Save the updated config
            with open(self.cursor_config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

            rprint(f"[green]Successfully uninstalled '{server_name}'[/green]")
            return True

        except subprocess.TimeoutExpired:
            rprint(f"[red]Timeout while uninstalling {package_name}[/red]")
            return False
        except Exception as e:
            rprint(f"[red]Error: {str(e)}[/red]")
            return False

    def start_all_servers(self):
        """Start all configured MCP servers."""
        success_count = 0
        total_count = len(self.config['mcpServers'])
        
        for server_name in self.config['mcpServers']:
            rprint(f"Starting {server_name}...")
            if self.start_server(server_name):
                success_count += 1
            time.sleep(1)  # Brief pause between starts
        
        rprint(f"[green]Started {success_count} out of {total_count} servers[/green]")

    def stop_all_servers(self):
        """Stop all running MCP servers."""
        running_servers = self.detect_cursor_mcp_servers()
        success_count = 0
        
        for server in running_servers:
            rprint(f"Stopping {server['name']}...")
            if self.stop_server(server['name']):
                success_count += 1
            time.sleep(1)  # Brief pause between stops
        
        rprint(f"[green]Stopped {success_count} out of {len(running_servers)} servers[/green]")

    def list_available_servers(self):
        """List all available servers from the registry."""
        try:
            servers = self.registry.get_available_servers()
            
            if not servers:
                rprint("[yellow]No servers found in registry. Try running 'mcp update' first.[/yellow]")
                return
            
            table = Table(title="Available MCP Servers")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="yellow")
            table.add_column("MCP Server", style="green")
            table.add_column("Author", style="magenta")
            
            for server in servers:
                try:
                    # Check if required keys exist
                    name = server.get('name', 'Unknown')
                    description = server.get('description', 'No description available')
                    author = server.get('author', 'Unknown')
                    
                    # Handle package_name with extra safety
                    if 'package_name' not in server:
                        mcp_name = 'Unknown'
                    else:
                        mcp_name = str(server['package_name'])
                        if '@modelcontextprotocol/' in mcp_name:
                            mcp_name = mcp_name.replace('@modelcontextprotocol/server-', '')
                            mcp_name = mcp_name.replace('@modelcontextprotocol/', '')
                        elif '@' in mcp_name and '/' in mcp_name:
                            # Only try to split if the package name contains both '@' and '/'
                            parts = mcp_name.split('/')
                            if len(parts) > 1:
                                mcp_name = parts[1]
                    
                    table.add_row(
                        name,
                        description,
                        mcp_name,
                        author
                    )
                except Exception as e:
                    rprint(f"[red]Error processing server entry: {str(e)}[/red]")
                    # Skip this server but continue with others
                    continue
            
            console.print(table)
        except Exception as e:
            rprint(f"[red]Error listing available servers: {str(e)}[/red]")
            rprint("[yellow]Try running 'mcp update' to refresh the registry.[/yellow]")

    def install_from_registry(self, server_name: str):
        """Install a server from the registry."""
        server_info = self.registry.get_server_info(server_name)
        if not server_info:
            rprint(f"[red]Error: Server '{server_name}' not found in registry[/red]")
            return False

        try:
            # Get server configuration
            package_name = server_info['package_name']
            command = server_info.get('command', 'npx')
            
            # Check installation type
            installation_type = server_info.get('installation_type', 'npm')
            
            if installation_type == 'git':
                return self._install_from_git(server_name, server_info)
            elif installation_type == 'smithery' or (server_info.get('args') and '@smithery/cli' in str(server_info.get('args'))):
                # If smithery installation type is specified or the args contain smithery command
                return self._install_via_smithery(server_name, server_info)
            
            # Continue with normal npm installation
            args = server_info.get('args')
            
            if not args:  # If args is None or empty, use default
                args = ['-y', package_name]
            
            # Process args that contain variables in curly braces
            import re
            var_pattern = re.compile(r'\{([^{}]+)\}')
            processed_args = []
            arg_values = {}  # Store values for arg variables
            
            # First, check if we need to prompt for any variables
            arg_vars = set()
            for arg in args:
                if isinstance(arg, str):  # Make sure arg is a string before searching
                    matches = var_pattern.findall(arg)
                    for match in matches:
                        arg_vars.add(match)
            
            # If we have variables to prompt for, do so
            if arg_vars:
                rprint("\n[yellow]This server requires the following arguments:[/yellow]")
                for var in arg_vars:
                    rprint(f"\n[cyan]{var}[/cyan]")
                    # Use input() to prompt for values
                    value = input(f"Please enter value for {var}: ").strip()
                    arg_values[var] = value
                    rprint(f"[green]Value set for {var}[/green]")
                rprint()
            
            # Replace variables in args
            for arg in args:
                if isinstance(arg, str):  # Ensure arg is a string before processing
                    # Replace variables
                    for var, value in arg_values.items():
                        arg = arg.replace(f'{{{var}}}', value)
                
                processed_args.append(arg)
            
            # Handle environment variables
            required_env = server_info.get('env', {})
            env = {}
            if required_env:
                rprint("\n[yellow]This server requires the following environment variables:[/yellow]")
                for key, description in required_env.items():
                    rprint(f"\n[cyan]{key}[/cyan]")
                    rprint(f"Description: {description}")
                    # Use input() to prompt for values
                    value = input(f"Please enter value for {key} (press Enter to skip): ").strip()
                    if value:
                        env[key] = value
                        rprint(f"[green]Value set for {key}[/green]")
                    else:
                        rprint(f"[yellow]Warning: Skipped setting {key}[/yellow]")
                rprint()
            
            # Update Cursor's config
            if 'mcpServers' not in self.config:
                self.config['mcpServers'] = {}
            
            self.config['mcpServers'][server_name] = {
                'command': command,
                'args': processed_args,  # Use processed args with replaced variables
                'env': env,
                'description': server_info.get('description', '')
            }
            
            # Save the updated config
            os.makedirs(os.path.dirname(self.cursor_config_path), exist_ok=True)
            with open(self.cursor_config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            rprint(f"[green]Successfully installed '{server_name}'[/green]")
            
            # Show summary of environment variables
            if required_env:
                rprint("\n[yellow]Environment Variable Summary:[/yellow]")
                for key in required_env.keys():
                    status = "[green]Set[/green]" if key in env else "[red]Not Set[/red]"
                    rprint(f"  - {key}: {status}")
                if len(env) < len(required_env):
                    rprint("\n[yellow]Note: Some environment variables were not set. You can update them later in:")
                    rprint(f"  {self.cursor_config_path}[/yellow]")
                rprint()
            
            # Show summary of arg variables if any were prompted
            if arg_vars:
                rprint("\n[yellow]Argument Variable Summary:[/yellow]")
                for var in arg_vars:
                    rprint(f"  - {var}: [green]Set[/green]")
                rprint()
            
            return True
            
        except Exception as e:
            rprint(f"[red]Error installing server: {str(e)}[/red]")
            return False

    def _install_from_git(self, server_name: str, server_info: Dict) -> bool:
        """Install an MCP server from a git repository."""
        try:
            # Extract git repository information
            git_url = server_info.get('git_url')
            if not git_url:
                rprint(f"[red]Error: No git URL provided for '{server_name}'[/red]")
                return False
                
            # Create installation directory in user's home directory
            install_dir = os.path.expanduser(f"~/.cursor/mcp_servers/{server_name}")
            os.makedirs(install_dir, exist_ok=True)
            
            rprint(f"[yellow]Cloning repository {git_url} to {install_dir}...[/yellow]")
            
            # Clone the repository
            result = subprocess.run(
                ['git', 'clone', git_url, install_dir],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # If directory already exists and has content, try pulling instead
                if os.path.exists(os.path.join(install_dir, '.git')):
                    rprint(f"[yellow]Repository already exists, updating...[/yellow]")
                    result = subprocess.run(
                        ['git', 'pull'],
                        cwd=install_dir,
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        rprint(f"[red]Error updating repository: {result.stderr}[/red]")
                        return False
                else:
                    rprint(f"[red]Error cloning repository: {result.stderr}[/red]")
                    return False
            
            # Check if subdir is specified
            subdir = server_info.get('subdir')
            working_dir = install_dir
            if subdir:
                working_dir = os.path.join(install_dir, subdir)
                if not os.path.exists(working_dir):
                    rprint(f"[yellow]Subdirectory '{subdir}' not found. Attempting to create it...[/yellow]")
                    try:
                        os.makedirs(working_dir, exist_ok=True)
                    except Exception as e:
                        rprint(f"[red]Error creating subdirectory: {str(e)}[/red]")
                        return False
            
            # Handle installation steps
            install_steps = server_info.get('install_steps', [])
            if not install_steps:
                # Fall back to install_command for backward compatibility
                install_command = server_info.get('install_command', 'npm install')
                install_steps = [install_command]
            
            # Execute each installation step
            for step_num, step_command in enumerate(install_steps, 1):
                rprint(f"[yellow]Running installation step {step_num}/{len(install_steps)}: {step_command}[/yellow]")
                
                result = subprocess.run(
                    step_command,
                    cwd=working_dir,  # Use working_dir that respects subdir
                    shell=True,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    rprint(f"[red]Error in installation step {step_num}: {result.stderr}[/red]")
                    return False
                else:
                    rprint(f"[green]Installation step {step_num} completed successfully[/green]")
            
            # Get command to run
            command = server_info.get('command', 'node')
            args = server_info.get('args', [])
            
            # Process args that contain variables in curly braces
            import re
            var_pattern = re.compile(r'\{([^{}]+)\}')
            processed_args = []
            arg_values = {}  # Store values for arg variables
            
            # First, check if we need to prompt for any variables
            arg_vars = set()
            for arg in args:
                matches = var_pattern.findall(arg)
                for match in matches:
                    if match != 'install_dir':  # Skip the pre-defined install_dir variable
                        arg_vars.add(match)
            
            # If we have variables to prompt for, do so
            if arg_vars:
                rprint("\n[yellow]This server requires the following arguments:[/yellow]")
                for var in arg_vars:
                    rprint(f"\n[cyan]{var}[/cyan]")
                    # Use input() to prompt for values
                    value = input(f"Please enter value for {var}: ").strip()
                    arg_values[var] = value
                    rprint(f"[green]Value set for {var}[/green]")
                rprint()
            
            # Replace variables in args
            for arg in args:
                if '{install_dir}' in arg:
                    # Handle the special case for install_dir
                    arg = arg.replace('{install_dir}', install_dir)
                
                # Handle other variables
                for var, value in arg_values.items():
                    arg = arg.replace(f'{{{var}}}', value)
                
                processed_args.append(arg)
            
            # If main_file is specified and not in args, append it
            main_file = server_info.get('main_file')
            if main_file:
                # First look in the working_dir (respecting subdir)
                main_file_path = os.path.join(working_dir, main_file)
                
                if not os.path.exists(main_file_path):
                    # If not found in the working_dir, try the install_dir
                    main_file_path = os.path.join(install_dir, main_file)
                    
                    if not os.path.exists(main_file_path):
                        # Try to find the file recursively
                        rprint(f"[yellow]Main file {main_file} not found, searching for it...[/yellow]")
                        found = False
                        for root, _, files in os.walk(install_dir):
                            if main_file in files:
                                main_file_path = os.path.join(root, main_file)
                                rprint(f"[green]Found main file at: {main_file_path}[/green]")
                                found = True
                                break
                        
                        if not found:
                            rprint(f"[red]Could not find main file {main_file}[/red]")
                            return False
                
                # Add main_file_path to args if not already present
                if main_file_path not in processed_args and main_file not in processed_args:
                    if not processed_args or not processed_args[-1].endswith(('.js', '.py')):
                        processed_args.append(main_file_path)
                
            # Handle environment variables
            required_env = server_info.get('env', {})
            env = {}
            if required_env:
                rprint("\n[yellow]This server requires the following environment variables:[/yellow]")
                for key, description in required_env.items():
                    rprint(f"\n[cyan]{key}[/cyan]")
                    rprint(f"Description: {description}")
                    value = input(f"Please enter value for {key} (press Enter to skip): ").strip()
                    if value:
                        env[key] = value
                        rprint(f"[green]Value set for {key}[/green]")
                    else:
                        rprint(f"[yellow]Warning: Skipped setting {key}[/yellow]")
                rprint()
            
            # Update Cursor's config
            if 'mcpServers' not in self.config:
                self.config['mcpServers'] = {}
            
            self.config['mcpServers'][server_name] = {
                'command': command,
                'args': processed_args,  # Use processed args with replaced variables
                'env': env,
                'description': server_info.get('description', ''),
                'installation_type': 'git',
                'install_dir': working_dir  # Use working_dir instead of install_dir to respect subdir
            }
            
            # Save the updated config
            os.makedirs(os.path.dirname(self.cursor_config_path), exist_ok=True)
            with open(self.cursor_config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            rprint(f"[green]Successfully installed '{server_name}' from git repository[/green]")
            
            # Show summary of environment variables
            if required_env:
                rprint("\n[yellow]Environment Variable Summary:[/yellow]")
                for key in required_env.keys():
                    status = "[green]Set[/green]" if key in env else "[red]Not Set[/red]"
                    rprint(f"  - {key}: {status}")
                if len(env) < len(required_env):
                    rprint("\n[yellow]Note: Some environment variables were not set. You can update them later in:")
                    rprint(f"  {self.cursor_config_path}[/yellow]")
                rprint()
            
            # Show summary of arg variables if any were prompted
            if arg_vars:
                rprint("\n[yellow]Argument Variable Summary:[/yellow]")
                for var in arg_vars:
                    rprint(f"  - {var}: [green]Set[/green]")
                rprint()
            
            return True
        
        except Exception as e:
            rprint(f"[red]Error installing from git: {str(e)}[/red]")
            return False

    def _install_via_smithery(self, server_name: str, server_info: Dict) -> bool:
        """Install an MCP server using Smithery."""
        try:
            # Get server configuration
            package_name = server_info['package_name']
            command = server_info.get('command', 'npx')
            args = server_info.get('args', [])
            
            if not args:
                rprint(f"[red]Error: No arguments provided for Smithery installation of '{server_name}'[/red]")
                return False
            
            # Create an MCP directory in user's home directory if it doesn't exist
            mcp_dir = os.path.expanduser("~/.cursor/mcp_servers")
            os.makedirs(mcp_dir, exist_ok=True)
            
            # Process args that contain variables in curly braces
            import re
            var_pattern = re.compile(r'\{([^{}]+)\}')
            processed_args = []
            arg_values = {}  # Store values for arg variables
            
            # First, check if we need to prompt for any variables
            arg_vars = set()
            for arg in args:
                if isinstance(arg, str):  # Make sure arg is a string before searching
                    matches = var_pattern.findall(arg)
                    for match in matches:
                        arg_vars.add(match)
            
            # If we have variables to prompt for, do so
            if arg_vars:
                rprint("\n[yellow]This server requires the following arguments:[/yellow]")
                for var in arg_vars:
                    rprint(f"\n[cyan]{var}[/cyan]")
                    # Use input() to prompt for values
                    value = input(f"Please enter value for {var}: ").strip()
                    arg_values[var] = value
                    rprint(f"[green]Value set for {var}[/green]")
                rprint()
            
            # Replace variables in args
            for arg in args:
                if isinstance(arg, str):  # Ensure arg is a string before processing
                    # Replace variables
                    for var, value in arg_values.items():
                        arg = arg.replace(f'{{{var}}}', value)
                
                processed_args.append(arg)
            
            # Handle environment variables
            required_env = server_info.get('env', {})
            env = {}
            if required_env:
                rprint("\n[yellow]This server requires the following environment variables:[/yellow]")
                for key, description in required_env.items():
                    rprint(f"\n[cyan]{key}[/cyan]")
                    rprint(f"Description: {description}")
                    # Use input() to prompt for values
                    value = input(f"Please enter value for {key} (press Enter to skip): ").strip()
                    if value:
                        env[key] = value
                        rprint(f"[green]Value set for {key}[/green]")
                    else:
                        rprint(f"[yellow]Warning: Skipped setting {key}[/yellow]")
                rprint()
            
            # Run the smithery installation command
            rprint(f"[yellow]Installing {server_name} using Smithery...[/yellow]")
            
            # Build the full command
            full_command = [command] + processed_args
            
            # Execute the command
            process = subprocess.Popen(
                full_command,
                cwd=mcp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream the output to the terminal
            for line in iter(process.stdout.readline, ''):
                print(line, end='')
            
            # Wait for the process to complete
            process.wait()
            
            if process.returncode != 0:
                error_output = process.stderr.read()
                rprint(f"[red]Error installing {server_name}: {error_output}[/red]")
                return False
            
            # Update Cursor's config
            if 'mcpServers' not in self.config:
                self.config['mcpServers'] = {}
            
            self.config['mcpServers'][server_name] = {
                'command': command,
                'args': processed_args,
                'env': env,
                'description': server_info.get('description', ''),
                'installation_type': 'smithery'
            }
            
            # Save the updated config
            os.makedirs(os.path.dirname(self.cursor_config_path), exist_ok=True)
            with open(self.cursor_config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            rprint(f"[green]Successfully installed '{server_name}' using Smithery[/green]")
            
            # Show summary of environment variables
            if required_env:
                rprint("\n[yellow]Environment Variable Summary:[/yellow]")
                for key in required_env.keys():
                    status = "[green]Set[/green]" if key in env else "[red]Not Set[/red]"
                    rprint(f"  - {key}: {status}")
                if len(env) < len(required_env):
                    rprint("\n[yellow]Note: Some environment variables were not set. You can update them later in:")
                    rprint(f"  {self.cursor_config_path}[/yellow]")
                rprint()
            
            # Show summary of arg variables if any were prompted
            if arg_vars:
                rprint("\n[yellow]Argument Variable Summary:[/yellow]")
                for var in arg_vars:
                    rprint(f"  - {var}: [green]Set[/green]")
                rprint()
            
            return True
        
        except Exception as e:
            rprint(f"[red]Error installing via Smithery: {str(e)}[/red]")
            return False

    def update_registry(self):
        """Update the local registry cache."""
        self.registry.update_registry()
        rprint("[green]Registry updated successfully[/green]")

@click.group()
def cli():
    """Cursor MCP Server Manager - Detect and manage Cursor MCP servers."""
    pass

@cli.command()
def list():
    """List all Cursor MCP servers and their status."""
    manager = MCPServerManager()
    manager.list_servers()

@cli.command()
@click.argument('name')
def start(name):
    """Start a specific MCP server."""
    manager = MCPServerManager()
    manager.start_server(name)

@cli.command()
@click.argument('name')
def stop(name):
    """Stop a specific MCP server."""
    manager = MCPServerManager()
    manager.stop_server(name)

@cli.command()
@click.argument('name')
def restart(name):
    """Restart a specific MCP server."""
    manager = MCPServerManager()
    manager.stop_server(name)
    click.echo("Waiting for server to stop...")
    time.sleep(2)  # Give it a moment to fully stop
    manager.start_server(name)

@cli.command()
@click.argument('name')
def functions(name):
    """Display available functions for a specific MCP server."""
    manager = MCPServerManager()
    manager.get_server_functions(name)

@cli.command()
@click.argument('name')
def uninstall(name):
    """Uninstall a specific MCP server."""
    if click.confirm(f"Are you sure you want to uninstall '{name}'?"):
        manager = MCPServerManager()
        manager.uninstall_server(name)

@cli.command()
def start_all():
    """Start all configured MCP servers."""
    manager = MCPServerManager()
    manager.start_all_servers()

@cli.command()
def stop_all():
    """Stop all running MCP servers."""
    manager = MCPServerManager()
    manager.stop_all_servers()

@cli.command()
def available():
    """List all available servers from the registry."""
    manager = MCPServerManager()
    manager.list_available_servers()

@cli.command()
@click.argument('name')
def install(name):
    """Install an MCP server from the registry."""
    manager = MCPServerManager()
    if manager.install_from_registry(name):
        rprint(f"[green]Server '{name}' installed successfully[/green]")
    else:
        sys.exit(1)

@cli.command()
@click.argument('git_url')
@click.option('--name', '-n', help='Name for the server (defaults to repository name)')
@click.option('--command', '-c', default='node', help='Command to run the server (default: node)')
@click.option('--main-file', '-m', default='index.js', help='Main file to run (default: index.js)')
@click.option('--subdir', '-s', help='Subdirectory within the repository containing the MCP server')
@click.option('--install-steps', '-i', multiple=True, help='Installation steps to run (can be specified multiple times)')
def install_git(git_url, name, command, main_file, subdir, install_steps):
    """Install an MCP server directly from a git repository."""
    manager = MCPServerManager()
    
    # If name is not provided, try to extract it from the git URL
    if not name:
        # Extract repository name from git URL
        name = git_url.split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]  # Remove .git suffix
    
    # Use default install step if none provided
    if not install_steps:
        install_steps = ['npm install']
    
    # Create server info for git installation
    server_info = {
        'name': name,
        'description': f'MCP server installed from {git_url}',
        'git_url': git_url,
        'command': command,
        'main_file': main_file,
        'install_steps': list(install_steps),  # Convert tuple to list
        'installation_type': 'git',
        'subdir': subdir,
    }
    
    # Install from git
    if manager._install_from_git(name, server_info):
        rprint(f"[green]Server '{name}' installed successfully from git repository[/green]")
    else:
        sys.exit(1)

@cli.command()
def update():
    """Update the local registry cache."""
    manager = MCPServerManager()
    manager.update_registry()

if __name__ == '__main__':
    cli()