# Docker Deployment Guide

## Prerequisites

- Docker Engine 20.10+ 
- Docker Compose 2.0+

## Quick Start

### 1. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```bash
OPENAI_API_KEY=sk-your-actual-openai-api-key
```

### 2. Build and Run

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### 4. Configure Azure Credentials

Azure credentials are configured through the UI:

1. Open http://localhost:3000
2. Click on the "Configuration" tab
3. Enter your Azure credentials:
   - Tenant ID
   - Client ID
   - Client Secret
4. Add your subscription IDs with custom names
5. Click "Save Configuration"

## Docker Commands

### Start Services

```bash
# Start in detached mode
docker-compose up -d

# Start with rebuild
docker-compose up -d --build

# Start and view logs
docker-compose up
```

### Stop Services

```bash
# Stop services
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers, volumes, and images
docker-compose down -v --rmi all
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100
```

### Rebuild Services

```bash
# Rebuild all services
docker-compose build

# Rebuild specific service
docker-compose build backend

# Force rebuild (no cache)
docker-compose build --no-cache
```

### Access Container Shell

```bash
# Backend container
docker-compose exec backend sh

# Frontend container
docker-compose exec frontend sh
```

## Service Health Checks

Both services include health checks:

```bash
# Check service status
docker-compose ps

# Check backend health
curl http://localhost:8000/api/health

# Check frontend health
curl http://localhost:3000/health
```

## Volumes and Persistence

### Output Files

Generated reports are stored in `./outputs` directory and persist across container restarts.

```bash
# View outputs
ls -l outputs/

# Clean outputs
rm -rf outputs/*
```

### Configuration

User configurations (Azure credentials and subscriptions) are stored in-memory and need to be re-entered after container restart. Future versions may add persistent storage for these.

## Port Configuration

Default ports can be changed in `docker-compose.yml`:

```yaml
services:
  backend:
    ports:
      - "8080:8000"  # Change 8080 to your preferred port
  
  frontend:
    ports:
      - "80:80"      # Change first 80 to your preferred port
```

## Production Deployment

### Security Considerations

1. **Use secrets for sensitive data**:
   ```yaml
   services:
     backend:
       secrets:
         - openai_api_key
   secrets:
     openai_api_key:
       file: ./secrets/openai_api_key.txt
   ```

2. **Configure CORS properly**:
   ```bash
   CORS_ORIGINS=https://yourdomain.com
   ```

3. **Use HTTPS**:
   - Add reverse proxy (nginx/traefik) with SSL certificates
   - Update frontend to use HTTPS backend URL

4. **Resource limits**:
   ```yaml
   services:
     backend:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 2G
   ```

### Environment-Specific Configs

```bash
# Development
docker-compose up

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs backend

# Check if port is already in use
netstat -an | grep 8000  # Linux/Mac
netstat -an | findstr 8000  # Windows
```

### Backend can't connect to Azure

1. Verify Azure credentials in the UI configuration
2. Check Azure AD app permissions
3. Verify network connectivity from container

### Frontend can't reach backend

1. Check if backend is healthy: `docker-compose ps`
2. Verify backend URL in frontend config
3. Check CORS settings

### Permission issues with outputs

```bash
# Linux/Mac: Fix permissions
sudo chown -R $USER:$USER outputs/

# Or run with specific user
docker-compose run --user $(id -u):$(id -g) backend
```

## Development with Docker

### Hot Reload

Mount source code for development:

```yaml
services:
  backend:
    volumes:
      - ./backend/app:/app/app
      - ./outputs:/app/outputs
```

Then restart:
```bash
docker-compose restart backend
```

### Debug Mode

```yaml
services:
  backend:
    environment:
      - DEBUG=true
    command: python -m debugpy --listen 0.0.0.0:5678 -m app.main
    ports:
      - "8000:8000"
      - "5678:5678"  # Debug port
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

## Monitoring

### Resource Usage

```bash
# Container stats
docker stats

# Specific containers
docker stats azure-cost-analyzer-backend azure-cost-analyzer-frontend
```

### Disk Usage

```bash
# Docker disk usage
docker system df

# Clean up unused resources
docker system prune -a
```

## Backup and Restore

### Backup Outputs

```bash
# Create backup
tar -czf outputs-backup-$(date +%Y%m%d).tar.gz outputs/

# Restore backup
tar -xzf outputs-backup-20260128.tar.gz
```

## Uninstall

```bash
# Stop and remove everything
docker-compose down -v --rmi all

# Remove outputs
rm -rf outputs/

# Remove environment file
rm .env
```
