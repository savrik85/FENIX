#!/bin/bash

# FENIX Deployment Script
# This script should be placed on your Linux server

set -e

DEPLOY_DIR="/root/fenix"
LOG_FILE="/var/log/fenix-deploy.log"

echo "$(date): Starting deployment..." >> $LOG_FILE

cd $DEPLOY_DIR

echo "$(date): Pulling latest changes from main branch..." >> $LOG_FILE
git pull origin main

echo "$(date): Stopping current containers..." >> $LOG_FILE
docker compose down

echo "$(date): Building new images..." >> $LOG_FILE
docker compose build

echo "$(date): Starting containers..." >> $LOG_FILE
docker compose up -d

echo "$(date): Waiting for services to be healthy..." >> $LOG_FILE
sleep 10

echo "$(date): Checking container status..." >> $LOG_FILE
docker compose ps >> $LOG_FILE

echo "$(date): Running health checks..." >> $LOG_FILE
if command -v make &> /dev/null; then
    make health >> $LOG_FILE 2>&1 || echo "$(date): Health check failed" >> $LOG_FILE
fi

echo "$(date): Deployment completed!" >> $LOG_FILE

# Clean up old images
docker image prune -f >> $LOG_FILE 2>&1

exit 0