#!/bin/bash
set -e

mkdir -p /home/vulcan/.ssh
chmod 700 /home/vulcan/.ssh

# If authorized_keys was mounted or provided
if [ -f /keys/id_ed25519.pub ]; then
    cp /keys/id_ed25519.pub /home/vulcan/.ssh/authorized_keys
    chmod 600 /home/vulcan/.ssh/authorized_keys
elif [ -f /home/vulcan/.ssh/authorized_keys ]; then
    chmod 600 /home/vulcan/.ssh/authorized_keys
else
    # Ephemeral key generation at container startup (R2/R3 invariant)
    echo "[*] Generating ephemeral SSH keypair in sandbox container..."
    ssh-keygen -t ed25519 -N "" -f /home/vulcan/.ssh/id_ed25519 -C "vulcan-sandbox@ephemeral"
    cat /home/vulcan/.ssh/id_ed25519.pub >> /home/vulcan/.ssh/authorized_keys
    chmod 600 /home/vulcan/.ssh/authorized_keys
    chmod 600 /home/vulcan/.ssh/id_ed25519
fi

chown -R vulcan:vulcan /home/vulcan/.ssh

echo "[✓] SSH sandbox ready. Starting OpenSSH daemon..."
exec /usr/sbin/sshd -D
