# Quickstart Guide

Get Sleepless Agent running in 5 minutes! This guide covers the minimal setup needed to start processing tasks.

> 💡 **Slack is optional.** You can use the `sle` CLI to submit tasks, check status, and start the daemon without any Slack configuration. Skip to [Step 3](#step-3-configure-environment) if you want to try it without Slack first.

## Prerequisites

Before starting, ensure you have:

- ✅ Python 3.11+ installed
- ✅ Node.js 16+ installed
- ✅ Claude Code CLI installed
- ⬜ Slack workspace access (**optional**)

## Step 1: Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
```

Verify installation:
```bash
claude --version
```

## Step 2: Install Sleepless Agent

```bash
pip install sleepless-agent
```

Or from source:
```bash
git clone https://github.com/context-machine-lab/sleepless-agent
cd sleepless-agent
pip install -e .
```

> ⚠️ **Windows / WSL — `sle` not found?** After `pip install`, the `sle` script may not be on your `PATH`.  
> Quick fix (WSL/Linux): `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc`  
> Quick fix (Windows PowerShell): `$d = python -m site --user-scripts; [Environment]::SetEnvironmentVariable("PATH","$env:PATH;$d","User")` — then restart your terminal.  
> Or just use a virtual environment (`python -m venv venv && venv/bin/activate`) to avoid PATH issues entirely.

## Step 2b: (Optional) Set Up Slack

If you want to submit tasks via Slack slash commands, set up a Slack app first. If you just want to use the `sle` CLI, skip this step.

1. Visit [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name it "Sleepless Agent" and select your workspace

### Enable Socket Mode
- Go to Settings → Socket Mode → Enable
- Create an app-level token (name: "sleepless-token")
- Save the `xapp-...` token

### Add Slash Commands
Go to Features → Slash Commands and create:
- `/think` - Submit tasks
- `/check` - Check status
- `/chat` - Interactive chat mode with Claude
- `/usage` - Show Claude Code Pro plan usage

### Set Bot Permissions
Features → OAuth & Permissions → Bot Token Scopes:
- `chat:write`
- `commands`
- `channels:history` (for chat mode)
- `reactions:write` (for chat mode)

### Enable Events (for Chat Mode)
Features → Event Subscriptions → Enable Events → Subscribe to bot events:
- `message.channels`
- `message.groups`

### Install to Workspace
- Click "Install to Workspace"
- Save the `xoxb-...` bot token

See the [full Slack Setup Guide](guides/slack-setup.md) for a complete walkthrough.

## Step 3: Configure Environment

Create a `.env` file:

```bash
# Optional: only needed if you want Slack integration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# Optional: Custom workspace location
AGENT_WORKSPACE=./workspace
```

> If you don't have Slack tokens yet, you can leave them out and use the `sle` CLI directly. The daemon will start in CLI-only mode.

## Step 4: Start the Agent

```bash
sle daemon
```

Without Slack tokens the agent starts in CLI-only mode — you won't see Slack log lines but task processing works normally. With Slack tokens configured you should see:
```
2025-10-24 23:30:12 | INFO | Sleepless Agent starting...
2025-10-24 23:30:12 | INFO | Slack bot started and listening for events
```

## Step 5: Test Your Setup

**Without Slack** — use the CLI directly:

```bash
sle think "Research Python async patterns"
sle check
```

**With Slack** — try these commands in your workspace:

```
/think Research Python async patterns
/check
```

The agent should acknowledge your task and show the queue status.

### Try Chat Mode (Slack only)

Start an interactive session with Claude:

```
/chat my-project
```

This creates a **Slack thread** where you can have a real-time conversation with Claude.

> ⚠️ **Important**: All messages to Claude must be sent **inside the thread**, not in the main channel. Claude will only respond to messages within the chat thread.

In the thread, try:
```
Create a hello world Python script
```

To end the session, type `exit` in the thread or use `/chat end`.

## What's Next?

### Essential Configuration

1. **Set up Git integration** for automated commits:
   ```bash
   git config --global user.name "Sleepless Agent"
   git config --global user.email "agent@sleepless.local"
   ```

2. **Configure Pro plan thresholds** in `config.yaml`:
   ```yaml
   claude_code:
     threshold_day: 20.0    # Pause at 20% during day
     threshold_night: 80.0  # Pause at 80% at night
   ```

3. **Set working hours** for optimal usage:
   ```yaml
   claude_code:
     night_start_hour: 20  # 8 PM
     night_end_hour: 8     # 8 AM
   ```

### Recommended Next Steps

- 📖 Read the [Architecture Overview](concepts/architecture.md)
- 🔧 Complete [Slack Setup](guides/slack-setup.md) for all features
- 🎯 Try the [First Task Tutorial](tutorials/first-task.md)
- 📊 Learn about [Task Management](guides/project-management.md)

## Common Issues

### `sle` command not found (Windows / WSL)?
- **WSL/Linux**: `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc`
- **Windows**: Run `python -m site --user-scripts` to find the Scripts dir, then add it to your `PATH` in System Settings → Environment Variables
- Use a virtual environment to avoid this entirely: `python -m venv venv && source venv/bin/activate` (or `venv\Scripts\activate` on Windows)

### Agent not responding in Slack?
- Verify Socket Mode is enabled
- Check both tokens are correct in `.env`
- Ensure the bot is in your channel

### Tasks not executing?
- Run `claude --version` to verify CLI installation
- Check `sle check` for usage limits
- Review logs: `tail -f workspace/data/agent.log`

### Usage threshold reached?
- Agent pauses at configured thresholds
- Wait for 5-hour window reset
- Adjust thresholds in `config.yaml` if needed

## Getting Help

- 💬 [Discord Community](https://discord.gg/74my3Wkn)
- 📚 [Full Documentation](index.md)
- 🐛 [Report Issues](https://github.com/context-machine-lab/sleepless-agent/issues)

---

🎉 **Congratulations!** You now have a 24/7 AI agent working for you. Check out the [tutorials](tutorials/first-task.md) to learn more advanced features.