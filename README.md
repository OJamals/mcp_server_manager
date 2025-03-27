# MCP Server Manager

A command-line tool for managing Model Context Protocol (MCP) servers specifically for Cursor IDE.

## Overview

MCP Server Manager simplifies the installation, configuration, and management of servers that extend Cursor IDE's capabilities. These servers implement the Model Context Protocol (MCP), which allows Claude and other AI assistants to access additional functionality such as:

- File system operations
- Knowledge graph and memory management
- Structured thinking processes
- Secure code execution
- Web search and content extraction
- Web browser automation
- Database integration
- And many more specialized tools

## Table of Contents

- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Commands](#commands)
  - [Managing Servers](#managing-servers)
  - [Installation & Registry](#installation--registry)
  - [Advanced Installation](#advanced-installation)
- [Server Types](#server-types)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)
- [Development](#development)
- [License](#license)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/mcp-server-manager.git
cd mcp-server-manager

# Install required dependencies
pip install -r requirements.txt
```

### Requirements

- Python 3.8+
- Node.js and npm (for most MCP servers)
- Git (for installing servers from repositories)

## Basic Usage

```bash
# View all commands
python mcp_manager.py --help

# List all installed servers and their status
python mcp_manager.py list

# List available servers from the registry
python mcp_manager.py available

# Install a server from the registry
python mcp_manager.py install <server-name>

# Start a server
python mcp_manager.py start <server-name>

# Stop a server
python mcp_manager.py stop <server-name>

# View server's available functions
python mcp_manager.py functions <server-name>
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

MCP servers extend Cursor's capabilities in various domains:

| Type | Description | Examples |
|------|-------------|----------|
| **filesystem** | File and directory operations | Reading, writing files, directory management |
| **memory** | Knowledge graph management | Entity creation, relationships, observations |
| **sequential-thinking** | Structured problem-solving | Breaking down complex problems, iterative analysis |
| **e2b** | Secure code execution | Running Python code in sandbox environments |
| **tavily** | Web search capabilities | Real-time search, content extraction |
| **database** | Database interactions | PostgreSQL, SQLite, Redis, Neo4j |
| **cloud services** | Cloud provider integrations | AWS, Google Drive, GitHub, GitLab |
| **AI tools** | AI-powered utilities | Image generation, UI creation |

## Configuration

The tool manages configuration in `~/.cursor/mcp.json`, which stores information about installed servers including:

- Server name and description
- Command and arguments to start the server
- Required environment variables
- Installation details

Example configuration entry:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem"],
      "description": "Provides an API for filesystem operations"
    }
  }
}
```

## Troubleshooting

Common issues and solutions:

- **Server fails to start**
  - Check that all required environment variables are set
  - Verify Node.js and npm are properly installed
  - Look for error messages in the terminal output

- **Registry commands fail**
  - Run `python mcp_manager.py update` to refresh the registry cache
  - Check your internet connection
  - If `python mcp_manager.py available` fails with an `IndexError`, try updating the registry or check package naming in the registry

- **Git installation issues**
  - Ensure git is installed and accessible in your PATH
  - Verify you have proper permissions for the repository
  - Check that the repository structure matches your configuration options

- **Server detection problems**
  - Use `python mcp_manager.py list` to verify the server's status
  - Try stopping and restarting the server
  - Check that the server process hasn't been terminated unexpectedly

- **EVERYTHING else**
  - Restart Cursor

## Advanced Usage

### Using Multiple Servers Together

```bash
# Start the core servers used by Claude
python mcp_manager.py start filesystem
python mcp_manager.py start memory
python mcp_manager.py start sequential-thinking

# Start a web search capability
python mcp_manager.py install tavily
python mcp_manager.py start tavily-mcp
```

### Environment Variables for Servers

Many servers require API keys or other environment variables: The install command will prompt for the required variables, but you can always update the variables as follows:

```bash
# Example for setting up Tavily search server
export TAVILY_API_KEY="your-api-key-here"
python mcp_manager.py start tavily-mcp

# Example for setting up E2B code execution
export E2B_API_KEY="your-e2b-api-key"
python mcp_manager.py start e2b
```

## Development

### Project Structure

- `mcp_manager.py` - Main implementation of the MCP Server Manager
- `server_registry.py` - Handles fetching and managing the server registry
- `registry.json` - Local cache of available MCP servers
- `requirements.txt` - Python dependencies

### Creating a Command Alias (Optional)

If you want to use a shorter command, you can create an alias in your shell:

```bash
# For bash/zsh, add to your .bashrc or .zshrc:
alias mcp='python /path/to/mcp-server-manager/mcp_manager.py'

# Then you can use simpler commands like:
mcp list
mcp start filesystem
```

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)
