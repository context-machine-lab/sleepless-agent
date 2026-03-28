# Troubleshooting Guide

This guide helps you diagnose and fix common issues with Sleepless Agent.

## Quick Diagnostics

Run these commands first to identify issues:

```bash
# Check system status
sle check

# Verify Claude Code CLI
claude --version
claude /usage

# Check daemon status
ps aux | grep "sle daemon"

# Review recent logs
tail -50 workspace/data/agent.log | grep ERROR
```

## Common Issues

### `sle` Command Not Found (Windows / WSL)

#### Symptom

```
bash: sle: command not found
```
or
```
'sle' is not recognized as an internal or external command
```

#### Cause

`pip install sleepless-agent` places the `sle` script in a directory that is not on your `PATH` by default (e.g. `~/.local/bin` on Linux/WSL, or `%APPDATA%\Python\PythonXX\Scripts` on Windows).

#### Solutions

**Virtual environment (recommended)**

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux / WSL:
source venv/bin/activate

pip install sleepless-agent
sle --version
```

**WSL / Linux — add `~/.local/bin` to PATH**

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
sle --version
```

**Windows — add user Scripts directory to PATH (PowerShell)**

```powershell
$scriptsDir = python -m site --user-scripts
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;$scriptsDir", "User")
# Restart your terminal, then:
sle --version
```

**Run without modifying PATH**

```bash
python -m sleepless_agent.interfaces.cli --help
```

### Is Slack Required?

**No.** Slack is an optional integration. The `sle` CLI works independently:

```bash
sle daemon      # Start the agent daemon
sle think "..."  # Queue a task
sle check        # Show system status
sle report       # View task reports
```

You only need Slack tokens (`SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN`) when you want to submit tasks via Slack slash commands. Without them the daemon starts in CLI-only mode and you can still run `sle daemon` to execute queued tasks.

### Agent Not Starting

#### Symptom
```
Error: Failed to start daemon
```

#### Solutions

1. **Check Python version**:
   ```bash
   python --version  # Must be 3.11+
   ```

2. **Verify dependencies**:
   ```bash
   pip install --upgrade sleepless-agent
   pip list | grep -E "anthropic|slack-sdk|sqlalchemy"
   ```

3. **Check workspace permissions**:
   ```bash
   ls -la workspace/
   chmod -R 755 workspace/
   ```

4. **Reset database**:
   ```bash
   rm workspace/data/tasks.db
   sle init
   ```

### Slack Bot Not Responding

#### Symptom
Slash commands don't trigger any response in Slack.

#### Solutions

1. **Verify Socket Mode**:
   - Go to Slack App settings
   - Settings → Socket Mode → Should be ON
   - Regenerate app token if needed

2. **Check tokens**:
   ```bash
   # Verify tokens in .env
   cat .env | grep SLACK
   # SLACK_BOT_TOKEN should start with xoxb-
   # SLACK_APP_TOKEN should start with xapp-
   ```

3. **Test bot connection**:
   ```bash
   # Check if bot is running
   sle daemon --test-slack
   ```

4. **Restart bot**:
   ```bash
   pkill -f "sle daemon"
   sle daemon
   ```

### Tasks Not Executing

#### Symptom
Tasks stay in "pending" status and never execute.

#### Solutions

1. **Check Claude Code authentication**:
   ```bash
   claude login
   claude /usage
   ```

2. **Verify usage limits**:
   ```bash
   sle check
   # Look for "Pro Usage" - if at threshold, wait for reset
   ```

3. **Check task status**:
   ```bash
   # View pending tasks
   sqlite3 workspace/data/tasks.db \
     "SELECT id, description, status FROM tasks WHERE status='pending';"
   ```

4. **Force task execution**:
   ```bash
   # Restart daemon with debug logging
   SLEEPLESS_LOG_LEVEL=DEBUG sle daemon
   ```

### Usage Threshold Reached

#### Symptom
```
WARNING: Pro usage at 85%, pausing task generation
```

#### Solutions

1. **Check current usage**:
   ```bash
   claude /usage
   sle check
   ```

2. **Wait for window reset**:
   - Pro plan resets every 5 hours
   - Check logs for exact reset time

3. **Adjust thresholds** (if needed):
   ```yaml
   # In config.yaml
   claude_code:
     threshold_day: 30.0   # Increase daytime limit
     threshold_night: 90.0  # Increase nighttime limit
   ```

4. **Clear completed tasks**:
   ```bash
   # Archive old tasks to reduce overhead
   sle archive --before 7d
   ```

### Database Locked

#### Symptom
```
sqlite3.OperationalError: database is locked
```

#### Solutions

1. **Stop all processes**:
   ```bash
   pkill -f sleepless
   pkill -f "sle daemon"
   ```

2. **Check for hung processes**:
   ```bash
   lsof workspace/data/tasks.db
   # Kill any processes still using the database
   ```

3. **Reset database** (last resort):
   ```bash
   cp workspace/data/tasks.db workspace/data/tasks.db.backup
   rm workspace/data/tasks.db
   sle init
   ```

### Git Integration Issues

#### Symptom
Commits or PRs are not being created.

#### Solutions

1. **Configure Git user**:
   ```bash
   git config --global user.name "Sleepless Agent"
   git config --global user.email "agent@sleepless.local"
   ```

2. **Authenticate GitHub CLI**:
   ```bash
   gh auth login
   gh auth status
   ```

3. **Check repository configuration**:
   ```yaml
   # In config.yaml
   git:
     use_remote_repo: true
     remote_repo_url: git@github.com:username/repo.git
   ```

4. **Test Git operations**:
   ```bash
   cd workspace/projects/test
   git remote -v
   git push --dry-run
   ```

### High Memory Usage

#### Symptom
Agent consuming excessive RAM.

#### Solutions

1. **Check running tasks**:
   ```bash
   ps aux | grep claude
   sle check
   ```

2. **Clean up workspaces**:
   ```bash
   # Remove old task workspaces
   find workspace/tasks -type d -mtime +7 -exec rm -rf {} +
   ```

3. **Limit concurrent tasks**:
   ```yaml
   # In config.yaml
   agent:
     max_concurrent_tasks: 2
   ```

4. **Restart daemon**:
   ```bash
   pkill -f "sle daemon"
   sle daemon
   ```

### Tasks Failing

#### Symptom
Tasks consistently marked as "failed".

#### Solutions

1. **Check error logs**:
   ```bash
   # View recent errors
   grep ERROR workspace/data/agent.log | tail -20

   # Check specific task
   sle report <task_id>
   ```

2. **Increase timeout**:
   ```yaml
   # In config.yaml
   agent:
     task_timeout_seconds: 3600  # Increase to 1 hour
   ```

3. **Test Claude Code directly**:
   ```bash
   # Try a simple command
   echo "print('test')" | claude
   ```

4. **Check workspace permissions**:
   ```bash
   ls -la workspace/tasks/
   chmod -R 755 workspace/
   ```

## Performance Issues

### Slow Task Execution

1. **Check system resources**:
   ```bash
   top -p $(pgrep -f "sle daemon")
   df -h workspace/
   ```

2. **Optimize database**:
   ```bash
   sqlite3 workspace/data/tasks.db "VACUUM;"
   sqlite3 workspace/data/tasks.db "ANALYZE;"
   ```

3. **Clear old logs**:
   ```bash
   # Archive old logs
   mv workspace/data/agent.log workspace/data/agent.log.old
   ```

### Queue Backlog

1. **View queue status**:
   ```bash
   sle check
   ```

2. **Cancel stuck tasks**:
   ```bash
   # Cancel old pending tasks
   sle cancel --status pending --older-than 24h
   ```

3. **Prioritize important tasks**:
   ```bash
   # Move task to front of queue
   sle prioritize <task_id>
   ```

## Log Analysis

### Enable Debug Logging

```bash
# Temporary debug mode
SLEEPLESS_LOG_LEVEL=DEBUG sle daemon

# Or in .env
SLEEPLESS_LOG_LEVEL=DEBUG
```

### Common Log Patterns

```bash
# Find authentication issues
grep -i "auth\|token\|login" workspace/data/agent.log

# Find task failures
grep "status.*failed" workspace/data/agent.log

# Find usage warnings
grep -i "usage\|threshold\|limit" workspace/data/agent.log

# Find Slack errors
grep -i "slack.*error" workspace/data/agent.log
```

### Log Rotation

```bash
# Set up log rotation
cat > /etc/logrotate.d/sleepless-agent << EOF
workspace/data/agent.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
}
EOF
```

## System Checks

### Health Check Script

Create `health_check.sh`:

```bash
#!/bin/bash

echo "=== Sleepless Agent Health Check ==="
echo

# Check daemon
if pgrep -f "sle daemon" > /dev/null; then
    echo "✅ Daemon is running"
else
    echo "❌ Daemon is NOT running"
fi

# Check Claude Code
if claude --version > /dev/null 2>&1; then
    echo "✅ Claude Code CLI installed"
else
    echo "❌ Claude Code CLI missing"
fi

# Check database
if [ -f "workspace/data/tasks.db" ]; then
    echo "✅ Database exists"
    TASK_COUNT=$(sqlite3 workspace/data/tasks.db "SELECT COUNT(*) FROM tasks;" 2>/dev/null)
    echo "   Total tasks: $TASK_COUNT"
else
    echo "❌ Database missing"
fi

# Check Slack tokens
if [ -f ".env" ]; then
    if grep -q "SLACK_BOT_TOKEN=xoxb" .env; then
        echo "✅ Slack bot token configured"
    else
        echo "❌ Slack bot token missing"
    fi
else
    echo "❌ .env file missing"
fi

# Check disk space
WORKSPACE_SIZE=$(du -sh workspace 2>/dev/null | cut -f1)
echo "📊 Workspace size: $WORKSPACE_SIZE"

echo
echo "Run 'sle check' for detailed status"
```

## Recovery Procedures

### Complete Reset

```bash
# Backup current data
tar -czf workspace_backup.tar.gz workspace/

# Stop everything
pkill -f sleepless
pkill -f claude

# Clean workspace
rm -rf workspace/
rm .env

# Reinstall
pip install --upgrade sleepless-agent

# Reconfigure
sle init
cp .env.example .env
# Edit .env with your tokens

# Restart
sle daemon
```

### Restore from Backup

```bash
# Stop daemon
pkill -f "sle daemon"

# Restore backup
tar -xzf workspace_backup.tar.gz

# Verify integrity
sqlite3 workspace/data/tasks.db "PRAGMA integrity_check;"

# Restart
sle daemon
```

## Getting Help

If these solutions don't resolve your issue:

1. **Collect diagnostic information**:
   ```bash
   sle diagnose > diagnostic_report.txt
   ```

2. **Check existing issues**:
   - [GitHub Issues](https://github.com/context-machine-lab/sleepless-agent/issues)

3. **Join the community**:
   - [Discord Server](https://discord.gg/74my3Wkn)

4. **Report new issue**:
   - Include diagnostic report
   - Describe steps to reproduce
   - Attach relevant log excerpts

## Prevention Tips

1. **Regular maintenance**:
   - Clean old task workspaces weekly
   - Archive completed tasks monthly
   - Rotate logs daily

2. **Monitor resources**:
   - Set up disk space alerts
   - Monitor memory usage
   - Track task success rates

3. **Keep updated**:
   - Update Sleepless Agent regularly
   - Update Claude Code CLI
   - Update dependencies

4. **Backup important data**:
   - Database backups
   - Configuration backups
   - Result archives