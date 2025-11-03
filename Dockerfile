# Multi-stage build for sleepless-agent
FROM node:20-slim AS node-base

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Main application image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy Node.js and npm from node-base stage
COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Copy Claude Code CLI from node-base
COPY --from=node-base /usr/local/lib/node_modules/@anthropic-ai/claude-code /usr/local/lib/node_modules/@anthropic-ai/claude-code
RUN ln -s /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/run.js /usr/local/bin/claude && \
    chmod +x /usr/local/bin/claude

# Optional: Install GitHub CLI for PR automation
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install gh -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY README.md LICENSE Makefile ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create necessary directories with proper permissions
RUN mkdir -p /app/workspace/data/results && \
    mkdir -p /app/workspace/shared && \
    mkdir -p /app/workspace/tasks && \
    chmod -R 755 /app/workspace

# Configure git (will be overridden by env vars if provided)
RUN git config --global user.name "Sleepless Agent" && \
    git config --global user.email "agent@sleepless.local" && \
    git config --global init.defaultBranch main

# Set environment variables with defaults
ENV AGENT_WORKSPACE_ROOT=/app/workspace \
    AGENT_DB_PATH=/app/workspace/data/tasks.db \
    AGENT_RESULTS_PATH=/app/workspace/data/results \
    CLAUDE_CODE_BINARY_PATH=/usr/local/bin/claude \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sle check || exit 1

# Expose port if needed for webhooks (Railway assigns port dynamically)
EXPOSE 8080

# Run the daemon
CMD ["sle", "daemon"]
