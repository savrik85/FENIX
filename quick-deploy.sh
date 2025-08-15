#!/bin/bash

# Quick manual deployment script for FENIX
echo "Starting FENIX deployment..."

# Update code from git
echo "Pulling latest code..."
git pull origin main

# Stop current services
echo "Stopping services..."
docker compose down

# Remove old images to force rebuild
echo "Removing old images..."
docker compose build --no-cache

# Start services
echo "Starting services..."
docker compose up -d

# Wait for services to be healthy
echo "Waiting for services..."
sleep 30

# Check health
echo "Checking service health..."
curl -f http://localhost:8001/health || echo "Health check failed"

# Check if email endpoints are available
echo "Testing email endpoints..."
curl -f http://localhost:8001/emails || echo "Email endpoint not available"

echo "Deployment completed!"
