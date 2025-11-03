# Railway Deployment Guide

This guide explains how to deploy Sleepless Agent as a Docker container on [Railway](https://railway.app).

## Overview

Sleepless Agent is now fully containerized and ready for deployment on Railway. The Docker container includes:

- Python 3.11 runtime
- Node.js and Claude Code CLI
- Git and GitHub CLI (gh)
- All required Python dependencies
- Persistent workspace for task data

## Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **Slack App Configured**: Follow the [Slack Setup Guide](./slack-setup.md) to create your Slack app and obtain tokens
3. **Git Repository**: Your code should be in a Git repository (GitHub, GitLab, etc.)

## Deployment Steps

### 1. Connect Your Repository

1. Log in to Railway
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Authorize Railway to access your repositories
5. Select the `sleepless-agent` repository

### 2. Configure Environment Variables

In the Railway dashboard, add the following environment variables:

#### Required Variables

```bash
# Slack Configuration (REQUIRED)
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
```

#### Optional Variables

```bash
# Git Configuration (for PR automation)
GIT_USER_NAME=Sleepless Agent
GIT_USER_EMAIL=agent@sleepless.local

# Logging
LOG_LEVEL=INFO
DEBUG=false

# Claude Code Binary Path (pre-configured in Docker)
CLAUDE_CODE_BINARY_PATH=/usr/local/bin/claude
```

#### Agent Configuration (with defaults)

```bash
# Workspace paths (defaults work in container)
AGENT_WORKSPACE_ROOT=/app/workspace
AGENT_DB_PATH=/app/workspace/data/tasks.db
AGENT_RESULTS_PATH=/app/workspace/data/results
```

### 3. Add Volume for Persistence (Optional but Recommended)

Railway supports volumes for persistent data. To preserve your task database and results across deployments:

1. In the Railway dashboard, go to your service
2. Navigate to "Settings" → "Volumes"
3. Click "Add Volume"
4. Mount path: `/app/workspace`
5. Size: 1GB (or more based on your needs)

**Without a volume**: Your task database and results will be reset on each deployment.

### 4. Configure Build Settings (Optional)

Railway automatically detects the Dockerfile. If needed, you can customize:

1. Go to "Settings" → "Build"
2. Build command: `docker build -t sleepless-agent .`
3. Dockerfile path: `Dockerfile`

The repository includes `railway.toml` and `railway.json` configuration files that Railway will automatically detect.

### 5. Deploy

Railway will automatically deploy when you push to your repository. You can also trigger manual deploys:

1. Go to your project in Railway
2. Click "Deploy" or "Redeploy"
3. Monitor the build logs

### 6. Verify Deployment

Check the deployment logs:

```
2025-10-26 03:30:12 | INFO | Sleepless Agent starting...
2025-10-26 03:30:12 | INFO | Slack bot connected
2025-10-26 03:30:13 | INFO | Daemon running, ready for tasks
```

Test in Slack:

```
/status
```

You should receive a status update from the bot.

## GitHub Integration (Optional)

For PR automation and Git operations, you'll need to configure SSH or HTTPS authentication:

### Option 1: Using GitHub Personal Access Token (Recommended)

1. Create a GitHub Personal Access Token with `repo` scope
2. In Railway, add environment variable:
   ```bash
   GH_TOKEN=your_github_token_here
   ```

### Option 2: Using SSH Keys

1. Generate SSH key pair
2. Add public key to GitHub
3. In Railway, store private key as a secret
4. Mount it in the container (requires custom Dockerfile modification)

## Configuration Files

The repository includes several Docker-related files:

- **Dockerfile**: Multi-stage build with Python, Node.js, and Claude Code CLI
- **docker-compose.yml**: For local testing before Railway deployment
- **.dockerignore**: Optimizes build by excluding unnecessary files
- **railway.toml** / **railway.json**: Railway-specific configuration

## Local Testing with Docker

Before deploying to Railway, test locally:

### 1. Create `.env` file

```bash
cp .env.example .env
# Edit .env with your tokens
```

### 2. Build and run with Docker Compose

```bash
docker-compose up --build
```

### 3. Test the bot in Slack

```
/think Create a simple hello world script
```

### 4. Check logs

```bash
docker-compose logs -f sleepless-agent
```

### 5. Stop the container

```bash
docker-compose down
```

## Updating the Deployment

Railway automatically redeploys on git push:

```bash
git add .
git commit -m "Update agent configuration"
git push origin main
```

Or trigger manual redeploy in Railway dashboard.

## Monitoring and Debugging

### View Logs

In Railway dashboard:
1. Go to your service
2. Click "Logs" tab
3. View real-time logs

### Health Check

The container includes a health check that runs every 30 seconds:

```bash
sle check
```

If the health check fails, Railway will restart the container.

### Common Issues

#### Container Crashes Immediately

**Cause**: Missing required environment variables (SLACK_BOT_TOKEN, SLACK_APP_TOKEN)

**Solution**: Verify all required env vars are set in Railway dashboard

#### Slack Bot Not Responding

**Cause**:
- Incorrect tokens
- Slack app not installed in workspace
- Bot missing required permissions

**Solution**:
1. Verify tokens in Railway match your Slack app
2. Reinstall Slack app in workspace
3. Check bot has required scopes (see [Slack Setup Guide](./slack-setup.md))

#### Database Locked Errors

**Cause**: No persistent volume, database resets on redeploy

**Solution**: Add a Railway volume mounted to `/app/workspace`

#### Git Operations Failing

**Cause**: Git credentials not configured

**Solution**: Add GH_TOKEN environment variable or configure SSH keys

## Resource Requirements

Railway free tier should be sufficient for light usage:

- **Memory**: ~512MB (with usage spikes to ~1GB during task execution)
- **CPU**: 0.5 vCPU (bursts to 1 vCPU)
- **Storage**: 1GB volume for workspace data

For heavy usage, consider upgrading to Railway Pro.

## Cost Optimization

Railway charges based on usage. To optimize costs:

1. **Use day/night thresholds**: Configure `threshold_day` and `threshold_night` in config.yaml to control Claude Code usage
2. **Monitor usage**: Use `sle report` commands to track task execution
3. **Adjust auto-generation**: Tune auto-generation weights in config.yaml to control task frequency
4. **Set task timeouts**: Configure `task_timeout_seconds` to prevent runaway tasks

## Security Best Practices

1. **Never commit secrets**: Use Railway environment variables for all tokens and keys
2. **Rotate tokens regularly**: Update Slack tokens and GitHub tokens periodically
3. **Use read-only volumes**: If mounting SSH keys, mount as read-only (`:ro`)
4. **Enable GitHub security scanning**: Use Dependabot and security advisories
5. **Limit bot permissions**: Only grant necessary Slack scopes

## Next Steps

- [Configure Git Integration](./git-integration.md) for PR automation
- [Set up Auto-generation](../reference/auto-generation.md) to customize task generation
- [Customize the Agent](../reference/configuration.md) to tune behavior

## Troubleshooting

For Railway-specific issues, consult:
- [Railway Documentation](https://docs.railway.app)
- [Railway Discord Community](https://discord.gg/railway)

For Sleepless Agent issues, see:
- [Troubleshooting Guide](../troubleshooting.md)
- [FAQ](../faq.md)

## Support

- GitHub Issues: [Report a bug](https://github.com/context-machine-lab/sleepless-agent/issues)
- Discord: [Join our community](https://discord.gg/74my3Wkn)
