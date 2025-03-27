# MCP Server Manager

A command-line utility for managing Model Context Protocol (MCP) servers for Cursor IDE.

## Overview

MCP Server Manager allows you to easily manage Model Context Protocol servers that extend Cursor's functionality. This tool helps you:

- List installed MCP servers and their status
- Start, stop, and restart specific servers
- Manage multiple servers simultaneously
- Install new servers from the registry
- View available functions for each server
- Remote registry containing more than 50 MCP servers which can be installed with one click

## Installation

```bash
# Clone the repository
git clone https://github.com/OJamals/mcp_server_manager.git

# Navigate to the directory
cd mcp_server_manager

# Ensure dependencies are installed
pip install -r requirements.txt

# Make the script executable
chmod +x mcp_manager.py
```

## Usage

```bash
./mcp_manager.py [COMMAND] [OPTIONS]
```

## Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `list` | Display all configured MCP servers and their status | `./mcp_manager.py list` |
| `start` | Start a specific MCP server by name | `./mcp_manager.py start [SERVER_NAME]` |
| `stop` | Stop a running MCP server | `./mcp_manager.py stop [SERVER_NAME]` |
| `restart` | Restart a specific MCP server | `./mcp_manager.py restart [SERVER_NAME]` |
| `functions` | Display available functions for a specific server | `./mcp_manager.py functions [SERVER_NAME]` |
| `start_all` | Start all configured MCP servers | `./mcp_manager.py start_all` |
| `stop_all` | Stop all running MCP servers | `./mcp_manager.py stop_all` |
| `available` | Display all servers available in the registry | `./mcp_manager.py available` |
| `install` | Install a server from the registry | `./mcp_manager.py install [SERVER_NAME]` |
| `install_git` | Install an MCP server from a Git repository | `./mcp_manager.py install_git [REPOSITORY_URL] [OPTIONS]` |
| `uninstall` | Uninstall a specific MCP server | `./mcp_manager.py uninstall [SERVER_NAME]` |
| `update` | Update the local registry cache | `./mcp_manager.py update` |

### Git Installation Options

| Option | Description | Default |
|--------|-------------|---------|
| `--name` | Custom name for the server | Repository name |
| `--branch` | Branch to clone | main/master |
| `--subdir` | Subdirectory for repositories with multiple MCP configs | Root directory |

Example:
```bash
./mcp_manager.py install_git https://github.com/example/mcp-server.git --name custom-name --branch develop --subdir packages/mcp
```

## Server Types

The manager supports various MCP server types including:

- Filesystem servers - For file operations in the editor
- Browser tools - For web development and debugging
- Server LLM TXT servers - For managing LLM.txt files
- MCP Shell servers - For interacting with MCP servers

## How It Works

The manager reads from Cursor's MCP configuration located at `~/.cursor/mcp.json`. It can:

1. Detect running MCP server processes
2. Start servers using their configured commands
3. Safely terminate running servers
4. Install servers via npm/uv from the registry
5. Display detailed information about server capabilities

### Git Installation Process

When installing from Git repositories:

1. The repository is cloned to a temporary directory
2. The tool looks for a valid `package.json` with MCP server configuration
3. Dependencies are installed using npm/yarn based on available lock files
4. The server is registered in Cursor's MCP configuration
5. The server can then be managed like any other MCP server

This allows you to:
- Install servers not yet published to npm
- Install specific branches or development versions
- Install private repositories you have access to
- Contribute to MCP server development by testing your local changes

## Requirements

- Python 3.6+
- npm & uv (for installing/uninstalling servers)

## Troubleshooting - Always RESTART CURSOR before anything!

- **Server won't start**: Ensure npm is installed and in your PATH
- **Permission errors**: Try running with sudo or checking file permissions
- **Server won't stop**: Use the force option or restart your system
- **Package not found**: Ensure your registry is up to date with `update` command
- **Git repository issues**: 
  - Ensure you have git installed and configured
  - For private repositories, make sure your SSH keys are set up
  - If you see "Invalid package.json" errors, verify the repository is an MCP server
  - Try specifying a specific branch with `--branch` if the default branch fails