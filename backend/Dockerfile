FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including OpenSSH client, sshpass, rsync, and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    openssh-client \
    sshpass \
    rsync \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set strict permissions on Ansible private keys
RUN if [ -f /app/ansible/keys/id_ed25519 ]; then chmod 600 /app/ansible/keys/id_ed25519; fi

# Install Ansible collections from requirements.yml (roles are vendored locally)
RUN if [ -f /app/ansible/requirements.yml ]; then \
    ansible-galaxy collection install -r /app/ansible/requirements.yml --ignore-errors || true; \
    fi

RUN mkdir -p /app/data /tmp/vulcan-ansible

EXPOSE 8000

CMD ["python", "main.py"]
