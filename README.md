# MCP Server Manager

A command-line tool for managing Model Context Protocol (MCP) servers for Cursor IDE. Offers an intuitive interface to manage MCP servers, and a remote repository with over 50 MCP servers which can be installed with a single click! Pure python with debug code purposely left in, to give an idea of what's happening. So many of the issues and confusion with MCP is lack of contextual awareness. Using this tool to manage and test your MCP servers helps overcome that!

## Installation

```bash
git clone https://github.com/yourusername/mcp-server-manager.git
cd mcp-server-manager
pip install -r requirements.txt
```

## Basic Usage

```bash
# View all commands
python mcp_manager.py --help

# List all installed servers and their status
python mcp_manager.py list

# List available servers from the registry
python mcp_manager.py available

# Install a server from the registry
python mcp_manager.py install <server-name> // uninstall

# Start a server
python mcp_manager.py start <server-name> // start_all

# Stop a server
python mcp_manager.py stop <server-name> // stop_all
```

## Commands

### Managing Servers

| Command | Description |
|---------|-------------|
| `python mcp_manager.py list` | List all installed MCP servers and their status |
| `python mcp_manager.py start <name>` | Start a specific MCP server |
| `python mcp_manager.py stop <name>` | Stop a specific MCP server |
| `python mcp_manager.py restart <name>` | Restart a specific MCP server |
| `python mcp_manager.py start_all` | Start all configured MCP servers |
| `python mcp_manager.py stop_all` | Stop all running MCP servers |
| `python mcp_manager.py functions <name>` | Display available functions for a specific server |

### Installation & Registry

| Command | Description |
|---------|-------------|
| `python mcp_manager.py available` | List all available servers from the registry |
| `python mcp_manager.py install <name>` | Install an MCP server from the registry |
| `python mcp_manager.py uninstall <name>` | Uninstall a specific MCP server |
| `python mcp_manager.py update` | Update the local registry cache |

### Advanced Installation

```bash
# Install from a git repository
python mcp_manager.py install_git <git-url> [options]

# Options:
# --name, -n      Name for the server (defaults to repository name)
# --command, -c   Command to run the server (default: node)
# --main-file, -m Main file to run (default: index.js)
# --subdir, -s    Subdirectory within the repository
# --install-steps, -i Installation steps (can be specified multiple times)

# Example:
python mcp_manager.py install_git https://github.com/example/my-mcp-server.git --name custom-server --subdir src --install-steps "npm install" --install-steps "npm run build"
```

## Server Types

MCP servers extend Cursor's capabilities in various ways:

- **filesystem**: File and directory operations
- **memory**: Knowledge graph and memory management
- **sequential-thinking**: Advanced problem-solving through structured thinking
- **e2b**: Code execution in secure sandboxes
- **tavily**: Web search and content extraction
- **neo4j**: Database interaction and graph queries
- Over 50 ready-to-install servers available on the registry! Access the registry here: https://github.com/OJamals/mcp-registry

## Configuration

The tool manages configuration in `~/.cursor/mcp.json`, which stores information about installed servers.

## Troubleshooting

- If a server fails to start, check that all required environment variables are set
- For git installations, ensure you have proper permissions and git is installed
- Use `python mcp_manager.py functions <name>` to verify a server's available functionality
- Check that npm/node.js is properly installed on your system

## Advanced Usage

```bash
# Start a server and verify its functions
python mcp_manager.py start filesystem
python mcp_manager.py functions filesystem

# Update registry and install a new server
python mcp_manager.py update
python mcp_manager.py available
python mcp_manager.py install tavily
```
