#!/bin/bash

# Server preparation script for CentOS Stream 9
echo "=== Preparing CentOS server for FENIX deployment ==="

# Install required packages
echo "Installing git and make..."
yum install -y git make

# Create deployment directory
echo "Creating deployment directory..."
mkdir -p /root/fenix

# Clone repository
echo "Cloning FENIX repository..."
cd /root
if [ ! -d fenix/.git ]; then
    git clone https://github.com/savrik85/FENIX.git fenix
fi

cd /root/fenix

# Create .env file
echo "Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Please edit /root/fenix/.env with your API keys"
fi

# Create log directory
mkdir -p /var/log
touch /var/log/fenix-deploy.log

echo "Server preparation complete!"
echo "Next steps:"
echo "1. Edit /root/fenix/.env with your API keys"
echo "2. Push to main branch to trigger deployment"