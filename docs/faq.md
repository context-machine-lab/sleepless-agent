# Frequently Asked Questions

## General Questions

### What is Sleepless Agent?

Sleepless Agent is a 24/7 AI automation system that uses your Claude Code Pro subscription to process tasks autonomously. It runs as a daemon, accepts tasks via Slack, and manages isolated workspaces for parallel execution.

### Why was Sleepless Agent created?

Most Claude Code Pro subscriptions are underutilized, especially during night hours. Sleepless Agent maximizes your subscription value by processing tasks 24/7, turning idle compute time into productive work.

### How is this different from other AI agents?

- **24/7 Operation**: Runs continuously as a daemon
- **Slack-Native**: Direct integration with your team's workflow
- **Workspace Isolation**: Each task runs in its own environment
- **Usage Optimization**: Intelligent Pro plan management
- **Git Integration**: Automated commits and PRs

## Setup & Installation

### Is Slack required?

**No — Slack is completely optional.** The `sle` CLI provides full functionality without any Slack configuration:

```bash
sle daemon       # Start the agent
sle think "..."  # Queue a task
sle check        # Check status
sle report       # View reports
```

You only need Slack tokens (`SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN`) if you want to submit tasks via Slack slash commands (`/think`, `/check`, etc.) or use interactive chat mode. Without them, the daemon starts in CLI-only mode and everything still works.

### Why doesn't `sle` work after `pip install` on Windows or WSL?

After `pip install sleepless-agent`, the `sle` script is placed in a directory that may not be on your `PATH`.

**WSL / Linux** — add `~/.local/bin` to `PATH`:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
sle --version
```

**Windows (PowerShell)** — find and add the Scripts directory:
```powershell
$d = python -m site --user-scripts
[Environment]::SetEnvironmentVariable("PATH","$env:PATH;$d","User")
# Restart terminal, then:
sle --version
```

**Recommended alternative** — use a virtual environment (avoids the issue on all platforms):
```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS/WSL: source venv/bin/activate
pip install sleepless-agent
sle --version
```

You can also always invoke the CLI without modifying PATH:
```bash
python -m sleepless_agent.interfaces.cli --help
```

### What are the system requirements?

- Python 3.11 or higher
- Node.js 16+ (for Claude Code CLI)
- 2GB RAM minimum
- 1GB free disk space
- Linux, macOS, or Windows with WSL2

### Do I need a Claude API key?

No! Sleepless Agent uses Claude Code CLI, which handles authentication through your Claude Code Pro subscription. You just need to run `claude login` once.

### How do I update Sleepless Agent?

```bash
# From PyPI
pip install --upgrade sleepless-agent

# From source
cd sleepless-agent
git pull
pip install -e . --upgrade
```

## Usage & Features

### What's the difference between "random thoughts" and "serious tasks"?

- **Random Thoughts** (`/think`): Auto-committed to `thought-ideas` branch, no review needed
- **Serious Tasks** (`/think -p project`): Creates feature branches and PRs, requires review

### How does workspace isolation work?

Each task runs in its own directory (`workspace/tasks/task_<id>/`), preventing conflicts and allowing true parallel execution. Tasks can only access their workspace and shared resources.

### Can multiple tasks run simultaneously?

Yes! Tasks execute in parallel within isolated workspaces. The scheduler manages concurrency based on system resources and Claude usage limits.

### How are tasks prioritized?

Tasks are scheduled based on:
1. Priority level (serious > random)
2. Project association
3. Creation time (FIFO within priority)
4. Available Claude usage quota

## Claude Code & Usage

### How does Pro plan usage management work?

The agent monitors usage via `claude /usage` and automatically pauses at configurable thresholds:
- **Daytime (8 AM - 8 PM)**: Pauses at 20% to preserve manual usage
- **Nighttime (8 PM - 8 AM)**: Pauses at 80% for maximum automation

### What happens when usage limits are reached?

1. New task generation pauses
2. Running tasks complete normally
3. Pending tasks wait in queue
4. Agent resumes after 5-hour window reset

### Can I adjust usage thresholds?

Yes, in `config.yaml`:
```yaml
claude_code:
  threshold_day: 20.0   # Daytime limit
  threshold_night: 80.0 # Nighttime limit
```

### How do I check current usage?

- Via CLI: `sle check`
- Via Slack: `/check`
- In logs: Look for "Pro Usage" entries

## Slack Integration

### Which Slack permissions are required?

Minimum required scopes:
- `chat:write` - Send messages
- `commands` - Receive slash commands
- `app_mentions:read` - Respond to mentions

### Can I use custom slash commands?

Yes! You can add custom commands in your Slack app configuration and handle them in the bot code.

### Why isn't the bot responding?

Check:
1. Socket Mode is enabled in Slack app settings
2. Both tokens (`xoxb-` and `xapp-`) are correct in `.env`
3. Bot is invited to the channel
4. Agent daemon is running (`sle daemon`)

### How do I use the bot in private channels?

Invite the bot to the private channel using `/invite @sleepless-agent`

## Task Management

### How do I cancel a running task?

```bash
# CLI
sle cancel <task_id>

# Slack
/cancel <task_id>
```

### Can I restore cancelled tasks?

Yes, cancelled tasks go to trash and can be restored:
```bash
# CLI
sle trash restore <task_id>

# Slack
/trash restore <task_id>
```

### How long are task results kept?

Task results are stored indefinitely in `workspace/data/results/`. You can manually clean old results if needed.

### How do I see task history?

```bash
# Today's tasks
sle report

# Specific task
sle report <task_id>

# All reports
sle report --list
```

## Git Integration

### Is Git integration required?

No, Git integration is optional. Without it, tasks still execute but won't create commits or PRs.

### How do I set up GitHub authentication?

```bash
# Install GitHub CLI
brew install gh  # or appropriate for your OS

# Authenticate
gh auth login
```

### Can I use a different Git provider?

Yes, the system works with any Git provider. Configure the remote URL in `config.yaml`.

### How are commits structured?

- Random thoughts: Committed to `thought-ideas` branch
- Serious tasks: Create feature branches like `feature/task-description`
- Commit messages include task metadata

## Troubleshooting

### Tasks aren't executing

1. Check Claude Code CLI: `claude --version`
2. Verify login: `claude /usage`
3. Check usage limits: `sle check`
4. Review logs: `tail -f workspace/data/agent.log`

### Database is locked

```bash
# Stop the daemon
pkill -f "sle daemon"

# Reset database
rm workspace/data/tasks.db
sle init
```

### High memory usage

- Reduce concurrent tasks in config
- Clear old task workspaces
- Check for memory leaks in custom executors

### Agent crashes frequently

1. Check system resources
2. Review error logs
3. Increase task timeout
4. Disable problematic features

## Advanced Usage

### Can I create custom executors?

Yes! Extend the `BaseExecutor` class and register it in the configuration.

### How do I integrate with other tools?

- Use the Python API for programmatic access
- Create custom Slack commands
- Extend the task processor
- Add webhook notifications

### Can I run multiple agents?

Yes, with separate:
- Workspace directories
- Database files
- Slack apps
- Configuration files

### Is there an API?

Yes, the Python package exposes a full API. See [API Reference](reference/api/python-api.md).

## Security & Privacy

### Is my code secure?

- Tasks run in isolated workspaces
- No external data transmission (except Git if configured)
- All processing happens locally
- Slack tokens are never logged

### Can I use this with sensitive projects?

Yes, with precautions:
- Run on secure infrastructure
- Use private Git repositories
- Configure strict access controls
- Review generated code before deployment

### What data is collected?

None. Sleepless Agent:
- Runs entirely locally
- No telemetry or analytics
- No external API calls (except Claude Code and Slack)
- All data stays in your workspace

## Getting Help

### Where can I get support?

1. [Documentation](index.md)
2. [Discord Community](https://discord.gg/74my3Wkn)
3. [GitHub Issues](https://github.com/context-machine-lab/sleepless-agent/issues)
4. [Troubleshooting Guide](troubleshooting.md)

### How do I report bugs?

Open an issue on [GitHub](https://github.com/context-machine-lab/sleepless-agent/issues) with:
- System information
- Error messages
- Steps to reproduce
- Log excerpts

### Can I contribute?

Yes! We welcome contributions. See [Contributing Guide](https://github.com/context-machine-lab/sleepless-agent/blob/main/CONTRIBUTING.md).

### Is commercial use allowed?

Yes, Sleepless Agent is MIT licensed. See [LICENSE](https://github.com/context-machine-lab/sleepless-agent/blob/main/LICENSE) for details.