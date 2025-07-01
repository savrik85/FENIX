#!/bin/bash

# Setup script for GitHub Actions auto-deployment
# Run this on your LOCAL machine

echo "=== FENIX Auto-Deploy Setup ==="
echo

# Generate SSH key for GitHub Actions
echo "1. Generating SSH key for GitHub Actions..."
ssh-keygen -t ed25519 -f ~/.ssh/github-actions-deploy -N "" -C "github-actions@fenix"

echo
echo "2. SSH Key generated. Here's your PUBLIC key to add to server:"
echo "================================================"
cat ~/.ssh/github-actions-deploy.pub
echo "================================================"
echo

echo "3. Add the above public key to your server's ~/.ssh/authorized_keys"
echo "   On your server, run:"
echo "   echo 'PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys"
echo

echo "4. Here's your PRIVATE key for GitHub Secrets:"
echo "================================================"
cat ~/.ssh/github-actions-deploy
echo "================================================"
echo

echo "5. Go to your GitHub repository settings:"
echo "   - Navigate to Settings > Secrets and variables > Actions"
echo "   - Add the following secrets:"
echo "     * SERVER_HOST: Your server IP or domain"
echo "     * SERVER_USER: Your server username"
echo "     * SERVER_PORT: SSH port (usually 22)"
echo "     * SERVER_SSH_KEY: The private key shown above"
echo

echo "6. Update the deployment path in:"
echo "   - .github/workflows/deploy.yml (line 25): cd /path/to/fenix"
echo "   - scripts/deploy.sh (line 7): DEPLOY_DIR=\"/path/to/fenix\""
echo

echo "7. Copy deploy.sh to your server:"
echo "   scp scripts/deploy.sh user@server:/path/to/fenix/scripts/"
echo

echo "Setup complete! Push to main branch to trigger deployment."