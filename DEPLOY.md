# Quick Deploy Guide

## Deploy to Railway (Recommended for 24/7 Operation)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

### Quick Steps

1. **Click "Deploy on Railway"** button above (or follow manual steps below)
2. **Set environment variables**:
   - `SLACK_BOT_TOKEN` - Your Slack bot token (xoxb-...)
   - `SLACK_APP_TOKEN` - Your Slack app token (xapp-...)
3. **Add a volume** (optional but recommended):
   - Mount path: `/app/workspace`
   - Size: 1GB+
4. **Deploy** and wait for build to complete

See [Full Railway Deployment Guide](./docs/guides/railway-deployment.md) for detailed instructions.

## Deploy with Docker

### Using Docker Compose (Recommended for Local Testing)

```bash
# 1. Clone the repository
git clone <repo-url>
cd sleepless-agent

# 2. Create and configure .env file
cp .env.example .env
# Edit .env with your Slack tokens

# 3. Start the container
docker-compose up -d

# 4. View logs
docker-compose logs -f

# 5. Stop the container
docker-compose down
```

### Using Docker Directly

```bash
# Build the image
docker build -t sleepless-agent .

# Run the container
docker run -d \
  --name sleepless-agent \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_APP_TOKEN=xapp-your-token \
  -v sleepless-data:/app/workspace \
  sleepless-agent

# View logs
docker logs -f sleepless-agent

# Stop and remove
docker stop sleepless-agent
docker rm sleepless-agent
```

## Environment Variables

### Required

- `SLACK_BOT_TOKEN` - Slack bot token (starts with xoxb-)
- `SLACK_APP_TOKEN` - Slack app token (starts with xapp-)

### Optional

- `GIT_USER_NAME` - Git commit author name (default: "Sleepless Agent")
- `GIT_USER_EMAIL` - Git commit author email (default: "agent@sleepless.local")
- `LOG_LEVEL` - Logging level (default: "INFO")
- `DEBUG` - Enable debug mode (default: "false")

See `.env.example` for full list.

## Prerequisites

Before deploying, you need:

1. **Slack App**: Create and configure a Slack app with required permissions
   - See [Slack Setup Guide](./docs/guides/slack-setup.md)
2. **Tokens**: Obtain `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`
3. **Claude Code Pro**: Ensure you have an active Claude Code Pro subscription

## Deployment Platforms

| Platform | Status | Guide |
|----------|--------|-------|
| Railway | ✅ Recommended | [Railway Guide](./docs/guides/railway-deployment.md) |
| Docker | ✅ Ready | See above |
| Render | ⚠️ Compatible | Use Dockerfile |
| Fly.io | ⚠️ Compatible | Use Dockerfile |
| AWS ECS | ⚠️ Compatible | Use Dockerfile |
| Kubernetes | ⚠️ Compatible | Use Dockerfile |

## Verifying Deployment

After deployment, test in Slack:

```
/status
```

You should receive a status message from the bot.

Submit a test task:

```
/think Create a hello world Python script
```

Monitor the logs to see the agent process the task.

## Monitoring

### Health Check

The container includes a health check endpoint:

```bash
docker exec sleepless-agent sle check
```

Or in Railway, monitor the "Health" tab in the dashboard.

### View Task Queue

```bash
docker exec sleepless-agent sle queue
```

### Generate Report

```bash
docker exec sleepless-agent sle report <task_id>
```

## Troubleshooting

### Container Won't Start

- **Check logs**: `docker logs sleepless-agent` or Railway logs
- **Verify env vars**: Ensure SLACK_BOT_TOKEN and SLACK_APP_TOKEN are set
- **Check Slack app**: Verify app is installed in workspace with correct permissions

### Bot Not Responding

- **Check Slack connection**: Look for "Slack bot connected" in logs
- **Verify tokens**: Ensure tokens match your Slack app
- **Test Claude Code CLI**: Exec into container and run `claude --version`

### Database Issues

- **Use persistent volume**: Mount `/app/workspace` to persist data across restarts
- **Check permissions**: Ensure workspace directory is writable

For more help, see:
- [Troubleshooting Guide](./docs/troubleshooting.md)
- [FAQ](./docs/faq.md)

## Next Steps

After successful deployment:

1. [Configure Git Integration](./docs/guides/git-integration.md) for PR automation
2. [Customize Configuration](./docs/reference/configuration.md) to tune agent behavior
3. [Set up Auto-generation](./docs/reference/auto-generation.md) to customize task generation

## Support

- **Documentation**: [Full Docs](https://context-machine-lab.github.io/sleepless-agent/)
- **Issues**: [GitHub Issues](https://github.com/context-machine-lab/sleepless-agent/issues)
- **Community**: [Discord](https://discord.gg/74my3Wkn)
