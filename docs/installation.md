# Installation Guide

This guide covers all installation methods and platform-specific setup instructions for Sleepless Agent.

## System Requirements

### Minimum Requirements

- **Python**: 3.11 or higher
- **Node.js**: 16.0 or higher (for Claude Code CLI)
- **Memory**: 2GB RAM minimum, 4GB recommended
- **Storage**: 1GB free space for workspace
- **OS**: Linux, macOS, or Windows (with WSL2)

### Required Software

- **Claude Code CLI**: The AI execution engine
- **Git**: For version control (optional but recommended)
- **SQLite3**: Usually pre-installed with Python
- **Slack Account**: With workspace admin access (**optional** — Slack adds a real-time interface but is not required to run `sle`)

## Installation Methods

### Method 1: Install from PyPI (Recommended)

```bash
# Install the latest stable version
pip install sleepless-agent

# Verify installation
sle --version
```

### Method 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/context-machine-lab/sleepless-agent
cd sleepless-agent

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Verify installation
sle --version
```

### Method 3: Docker Installation

```bash
# Pull the Docker image
docker pull sleeplessagent/sleepless-agent:latest

# Run with environment variables
docker run -d \
  --name sleepless-agent \
  -e SLACK_BOT_TOKEN=xoxb-... \
  -e SLACK_APP_TOKEN=xapp-... \
  -v $(pwd)/workspace:/workspace \
  sleeplessagent/sleepless-agent
```

## Platform-Specific Setup

### macOS

```bash
# Install Python 3.11+ via Homebrew
brew install python@3.11

# Install Node.js for Claude Code CLI
brew install node

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Install Sleepless Agent
pip install sleepless-agent
```

### Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install nodejs

# Install Claude Code CLI
sudo npm install -g @anthropic-ai/claude-code

# Install Sleepless Agent
pip install sleepless-agent
```

### Windows (WSL2)

```bash
# Inside WSL2 Ubuntu
# Follow Ubuntu instructions above

# Or use native Windows with Python
# Install Python from python.org
# Install Node.js from nodejs.org

# In PowerShell (as Administrator)
npm install -g @anthropic-ai/claude-code
pip install sleepless-agent
```

> ⚠️ **`sle` not found after install?** See [Troubleshooting: `sle` command not found](#sle-command-not-found-windows--wsl) below.

## Claude Code CLI Setup

### Install Claude Code CLI

```bash
# Install globally
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version
```

### Authenticate Claude Code

```bash
# Login to Claude Code (opens browser)
claude login

# Verify authentication
claude /usage
```

## Environment Configuration

### Create Environment File

```bash
# Copy example configuration
cp .env.example .env

# Edit with your tokens
nano .env  # or your preferred editor
```

### Required Environment Variables

```bash
# Slack Configuration (Required)
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# Agent Configuration (Optional)
AGENT_WORKSPACE=./workspace
AGENT_DB_PATH=./workspace/data/tasks.db
AGENT_RESULTS_PATH=./workspace/data/results

# Git Configuration (Optional)
GIT_USER_NAME=Sleepless Agent
GIT_USER_EMAIL=agent@sleepless.local

# Logging Configuration (Optional)
SLEEPLESS_LOG_LEVEL=INFO
SLEEPLESS_LOG_DIR=workspace/.logs
```

## Configuration File Setup

### Default Configuration

The agent uses `config.yaml` for runtime settings:

```yaml
# Create or modify config.yaml
cp src/sleepless_agent/config.yaml ./config.yaml
```

### Key Configuration Options

```yaml
claude_code:
  model: claude-sonnet-4-5-20250929
  night_start_hour: 20  # 8 PM
  night_end_hour: 8     # 8 AM
  threshold_day: 20.0   # Day usage limit
  threshold_night: 80.0 # Night usage limit

agent:
  workspace_root: ./workspace
  task_timeout_seconds: 1800

git:
  use_remote_repo: true
  remote_repo_url: git@github.com:yourusername/yourrepo.git
  auto_create_repo: true
```

## Post-Installation Setup

### 1. Initialize Workspace

```bash
# Create workspace structure
sle init

# This creates:
# workspace/
# ├── data/
# │   ├── tasks.db
# │   ├── results/
# │   └── reports/
# ├── tasks/
# └── projects/
```

### 2. Test Installation

```bash
# Check system status
sle check

# Run a test task
sle think "Test task - verify installation"

# Check daemon status
sle daemon --test
```

### 3. Set Up Git (Optional)

```bash
# Configure Git user
git config --global user.name "Sleepless Agent"
git config --global user.email "agent@sleepless.local"

# Authenticate GitHub CLI (for PR creation)
gh auth login
```

### 4. Configure Slack App

Follow the [Slack Setup Guide](guides/slack-setup.md) to:
- Create your Slack application
- Configure slash commands
- Set up permissions
- Install to workspace

## Upgrading

### Upgrade from PyPI

```bash
# Upgrade to latest version
pip install --upgrade sleepless-agent

# Check new version
sle --version
```

### Upgrade from Source

```bash
# Pull latest changes
cd sleepless-agent
git pull origin main

# Reinstall
pip install -e . --upgrade
```

## Troubleshooting Installation

### `sle` Command Not Found (Windows / WSL)

#### Symptom

After `pip install sleepless-agent` the terminal says `sle: command not found` (Linux/WSL) or `'sle' is not recognized` (Windows CMD/PowerShell).

#### Cause

`pip` installs the `sle` entry-point script into a `Scripts` (Windows) or `bin` (Linux/macOS) directory that may not be on your `PATH`.

#### Solutions

**1. Use a virtual environment (recommended for all platforms)**

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux / WSL:
source venv/bin/activate

pip install sleepless-agent
sle --version  # Always works inside the venv
```

**2. WSL / Linux — add `~/.local/bin` to PATH**

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
sle --version
```

**3. Windows — add the user Scripts directory to PATH**

```powershell
# Find the Scripts directory
python -m site --user-scripts
# Example output: C:\Users\YourName\AppData\Roaming\Python\Python311\Scripts

# Permanently add it (PowerShell, run as your user)
$scriptsDir = python -m site --user-scripts
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;$scriptsDir", "User")
# Restart your terminal, then:
sle --version
```

**4. Run without adding to PATH**

You can always invoke the CLI directly:

```bash
python -m sleepless_agent.interfaces.cli --help
```

### Python Version Issues

```bash
# Check Python version
python --version

# If version < 3.11, install pyenv
curl https://pyenv.run | bash
pyenv install 3.11.0
pyenv global 3.11.0
```

### Node.js/npm Issues

```bash
# Check Node version
node --version
npm --version

# If missing or old, use nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install --lts
nvm use --lts
```

### Permission Issues

```bash
# Fix workspace permissions
chmod -R 755 workspace/

# Fix global npm permissions
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Database Issues

```bash
# Reset database if corrupted
rm workspace/data/tasks.db
sle init  # Recreates database
```

## Verification Checklist

After installation, verify:

- [ ] `sle --version` shows correct version
- [ ] `claude --version` shows Claude Code CLI version
- [ ] `sle check` runs without errors
- [ ] Workspace directory exists and is writable
- [ ] `.env` file contains valid Slack tokens
- [ ] Slack app responds to test command

## Next Steps

- 📱 Complete [Slack Setup](guides/slack-setup.md)
- 🚀 Follow the [Quickstart Guide](quickstart.md)
- 🎓 Try your [First Task](tutorials/first-task.md)
- ⚙️ Configure [Environment Variables](reference/environment-variables.md)

## Getting Help

If you encounter issues:

1. Check [Troubleshooting Guide](troubleshooting.md)
2. Search [existing issues](https://github.com/context-machine-lab/sleepless-agent/issues)
3. Join our [Discord](https://discord.gg/74my3Wkn)
4. Open a [new issue](https://github.com/context-machine-lab/sleepless-agent/issues/new)