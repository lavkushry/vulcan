"""
Project Vulcan: Enterprise Automation Catalog & Intent Matcher
Contains 110+ pre-seeded production playbooks and Terraform stacks across:
- Cloud (AWS / Azure / GCP)
- Network & F5 BIG-IP
- Database (Oracle, Postgres, MySQL, Redis, Mongo)
- OS Patching & Lifecycle (RHEL, Ubuntu, Windows)
- Kubernetes & Containers
- Security, IAM & Compliance
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from app.domain.entities import CatalogItem, ExecutionEngineType, RiskTier


# Standard 40-character commit SHAs for immutable catalog references
DEFAULT_SHA = "a1b2c3d4e5f67890123456789abcdef012345678"
DB_SHA = "b2c3d4e5f67890123456789abcdef01234567890"
CLOUD_SHA = "c3d4e5f67890123456789abcdef0123456789012"
OS_SHA = "d4e5f67890123456789abcdef012345678901234"
SEC_SHA = "e5f67890123456789abcdef01234567890123456"
K8S_SHA = "f67890123456789abcdef0123456789012345678"


RAW_CATALOG_DEFINITIONS: List[Dict[str, Any]] = [
    # =========================================================================
    # 0. REAL ANSIBLE GITHUB PLAYBOOKS & ROLES (SANDBOX TARGET)
    # =========================================================================
    {
        "id": "cat-real-001",
        "identifier": "os-sandbox-ping",
        "name": "Sandbox Ping & Facts Gathering Probe",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/adithyakhamithkar/ansible-playbooks.git",
        "git_commit_sha": OS_SHA,
        "playbook_or_module_path": "ansible/playbooks/ping_check.yml",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "os_patching",
        "description": "Performs real-time SSH ping and system facts gathering on the isolated sandbox environment.",
        "tags": ["ping", "facts", "sandbox", "connectivity", "health", "ubuntu"],
        "input_schema": {
            "type": "object",
            "required": ["target_host"],
            "properties": {
                "target_host": {"type": "string", "default": "sandbox", "description": "Target hostname in inventory"}
            }
        }
    },
    {
        "id": "cat-real-002",
        "identifier": "db-postgres-provision",
        "name": "PostgreSQL Cluster Deployment & Database Provisioning",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/geerlingguy/ansible-role-postgresql.git",
        "git_commit_sha": DB_SHA,
        "playbook_or_module_path": "ansible/playbooks/postgres_setup.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "database",
        "description": "Provisions PostgreSQL server, creates application database, user credentials, and grants access rights (geerlingguy.postgresql).",
        "tags": ["postgresql", "postgres", "database", "sql", "geerlingguy", "provision"],
        "input_schema": {
            "type": "object",
            "required": ["postgres_db_name", "postgres_user", "postgres_password"],
            "properties": {
                "db_version": {"type": "string", "default": "16", "enum": ["14", "15", "16"], "description": "PostgreSQL major version"},
                "postgres_db_name": {"type": "string", "default": "production_app", "description": "Application database name"},
                "postgres_user": {"type": "string", "default": "app_user", "description": "Primary database user"},
                "postgres_password": {"type": "string", "default": "secure_app_pass_2026", "description": "User password"},
                "postgres_port": {"type": "integer", "default": 5432, "minimum": 1024, "maximum": 65535, "description": "PostgreSQL listening port"}
            }
        }
    },
    {
        "id": "cat-real-003",
        "identifier": "ci-jenkins-deploy",
        "name": "Jenkins CI/CD Automation Server Deployment",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/geerlingguy/ansible-role-jenkins.git",
        "git_commit_sha": CLOUD_SHA,
        "playbook_or_module_path": "ansible/playbooks/jenkins_setup.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "cloud",
        "description": "Installs OpenJDK, configures Jenkins official Debian repository, installs Jenkins CI, and tunes HTTP port (geerlingguy.jenkins).",
        "tags": ["jenkins", "ci", "cd", "java", "automation", "geerlingguy"],
        "input_schema": {
            "type": "object",
            "required": ["http_port"],
            "properties": {
                "http_port": {"type": "integer", "default": 8080, "minimum": 1024, "maximum": 65535, "description": "Jenkins HTTP listening port"},
                "target_host": {"type": "string", "default": "sandbox", "description": "Target hostname in inventory"}
            }
        }
    },
    {
        "id": "cat-real-004",
        "identifier": "git-gitlab-stage",
        "name": "GitLab Enterprise CE/EE Infrastructure Setup",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/geerlingguy/ansible-role-gitlab.git",
        "git_commit_sha": CLOUD_SHA,
        "playbook_or_module_path": "ansible/playbooks/gitlab_setup.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "cloud",
        "description": "Installs GitLab omnibus prerequisites, downloads repository configuration script, and stages gitlab.rb configuration (geerlingguy.gitlab).",
        "tags": ["gitlab", "git", "devops", "omnibus", "geerlingguy", "repository"],
        "input_schema": {
            "type": "object",
            "required": ["external_url", "edition"],
            "properties": {
                "external_url": {"type": "string", "default": "http://gitlab.internal:8080", "description": "Full external URL for GitLab web access"},
                "edition": {"type": "string", "default": "gitlab-ce", "enum": ["gitlab-ce", "gitlab-ee"], "description": "GitLab package edition"}
            }
        }
    },
    {
        "id": "cat-real-005",
        "identifier": "k8s-node-provision",
        "name": "Kubernetes Node Provisioning & Container Runtime Setup",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/geerlingguy/ansible-for-kubernetes.git",
        "git_commit_sha": K8S_SHA,
        "playbook_or_module_path": "ansible/playbooks/k8s_node_setup.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "kubernetes",
        "description": "Configures kernel networking modules (overlay, br_netfilter), sysctl, containerd runtime, and prepares kubelet/kubeadm tools (ansible-for-kubernetes).",
        "tags": ["kubernetes", "k8s", "containerd", "kubeadm", "geerlingguy", "cluster"],
        "input_schema": {
            "type": "object",
            "required": ["kubernetes_version", "cgroup_mgr"],
            "properties": {
                "kubernetes_version": {"type": "string", "default": "v1.30", "enum": ["v1.28", "v1.29", "v1.30"], "description": "Target Kubernetes release version"},
                "cgroup_mgr": {"type": "string", "default": "systemd", "enum": ["systemd", "cgroupfs"], "description": "Cgroup driver for container runtime"}
            }
        }
    },
    {
        "id": "cat-real-006",
        "identifier": "web-nginx-deploy",
        "name": "High-Performance Nginx Web Server & Reverse Proxy",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/lework/Ansible-roles.git",
        "git_commit_sha": OS_SHA,
        "playbook_or_module_path": "ansible/playbooks/nginx_deploy.yml",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "network",
        "description": "Installs Nginx, creates custom virtual host server block, deploys styled landing page, and validates configuration (lework/Ansible-roles).",
        "tags": ["nginx", "web", "proxy", "http", "lework", "reverse-proxy"],
        "input_schema": {
            "type": "object",
            "required": ["port", "server_name"],
            "properties": {
                "port": {"type": "integer", "default": 80, "minimum": 80, "maximum": 65535, "description": "HTTP listening port"},
                "server_name": {"type": "string", "default": "vulcan.internal", "description": "Virtual host domain or server name"},
                "root_dir": {"type": "string", "default": "/var/www/html", "description": "Document root directory"}
            }
        }
    },
    {
        "id": "cat-real-007",
        "identifier": "cache-redis-deploy",
        "name": "Redis In-Memory Cache & Key-Value Store Deployment",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/lework/Ansible-roles.git",
        "git_commit_sha": DB_SHA,
        "playbook_or_module_path": "ansible/playbooks/redis_deploy.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "database",
        "description": "Deploys and tunes Redis in-memory cache with custom memory limits, bind interfaces, and LRU eviction policies (lework/Ansible-roles).",
        "tags": ["redis", "cache", "nosql", "in-memory", "lework", "key-value"],
        "input_schema": {
            "type": "object",
            "required": ["port", "maxmemory_mb"],
            "properties": {
                "port": {"type": "integer", "default": 6379, "minimum": 1024, "maximum": 65535, "description": "Redis TCP port"},
                "bind_address": {"type": "string", "default": "0.0.0.0", "description": "Network binding interface address"},
                "maxmemory_mb": {"type": "integer", "default": 256, "minimum": 64, "maximum": 16384, "description": "Maximum memory limit in megabytes"}
            }
        }
    },
    {
        "id": "cat-real-008",
        "identifier": "sec-system-hardening",
        "name": "Linux Server Security Hardening & SSH Audit Policy",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/adithyakhamithkar/ansible-playbooks.git",
        "git_commit_sha": SEC_SHA,
        "playbook_or_module_path": "ansible/playbooks/system_hardening.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "security",
        "description": "Enforces SSH access restrictions (MaxAuthTries, X11Forwarding), installs unattended-upgrades and fail2ban, and sets legal pre-login banner (adithyakhamithkar/ansible-playbooks).",
        "tags": ["hardening", "security", "ssh", "fail2ban", "audit", "compliance"],
        "input_schema": {
            "type": "object",
            "required": ["port", "auto_updates"],
            "properties": {
                "port": {"type": "integer", "default": 22, "minimum": 22, "maximum": 65535, "description": "SSH listening port"},
                "auto_updates": {"type": "boolean", "default": True, "description": "Enable automated security package updates"},
                "legal_banner": {"type": "string", "default": "AUTHORIZED ACCESS ONLY - Project Vulcan Governed System", "description": "Pre-login legal warning message"}
            }
        }
    },
    {
        "id": "cat-real-009",
        "identifier": "sec-create-operator",
        "name": "Enterprise Unix Operator User & Sudo Provisioning",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "https://github.com/adithyakhamithkar/ansible-playbooks.git",
        "git_commit_sha": SEC_SHA,
        "playbook_or_module_path": "ansible/playbooks/create_user.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "security",
        "description": "Provisions an enterprise Unix engineer account with custom login shell, home directory, and passwordless sudoers rules (adithyakhamithkar/ansible-playbooks).",
        "tags": ["user", "sudo", "linux", "iam", "account", "provisioning"],
        "input_schema": {
            "type": "object",
            "required": ["username", "shell", "sudo_access"],
            "properties": {
                "username": {"type": "string", "default": "ops_engineer", "description": "Unix system account login name"},
                "shell": {"type": "string", "default": "/bin/bash", "enum": ["/bin/bash", "/bin/zsh", "/bin/sh"], "description": "Default user login shell"},
                "sudo_access": {"type": "boolean", "default": True, "description": "Grant passwordless sudo administrative privileges"}
            }
        }
    },

    # =========================================================================
    # 1. NETWORK & LOAD BALANCING (ANSIBLE)
    # =========================================================================
    {
        "id": "cat-net-001",
        "identifier": "net-f5-cert-renew",
        "name": "F5 BIG-IP SSL Certificate Renewal",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/net-playbooks.git",
        "git_commit_sha": DEFAULT_SHA,
        "playbook_or_module_path": "playbooks/f5/renew_ssl_cert.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "network",
        "description": "Renews and binds x509 TLS/SSL certificates to F5 BIG-IP client SSL profiles and syncs active-standby cluster.",
        "tags": ["f5", "ssl", "tls", "certificate", "loadbalancer", "vip"],
        "input_schema": {
            "type": "object",
            "required": ["hostname", "vip_ip", "cert_valid_days"],
            "properties": {
                "hostname": {"type": "string", "default": "f5-edge-01.internal"},
                "vip_ip": {"type": "string", "default": "10.200.1.50"},
                "cert_valid_days": {"type": "integer", "default": 90, "minimum": 30, "maximum": 365},
                "profile_name": {"type": "string", "default": "clientssl-prod-vip"}
            }
        }
    },
    {
        "id": "cat-net-002",
        "identifier": "net-f5-pool-member-drain",
        "name": "F5 BIG-IP Pool Member Graceful Drain & Disable",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/net-playbooks.git",
        "git_commit_sha": DEFAULT_SHA,
        "playbook_or_module_path": "playbooks/f5/pool_member_drain.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "network",
        "description": "Gradually bleeds active TCP connections from an F5 pool member before maintenance.",
        "tags": ["f5", "pool", "drain", "maintenance", "vip"],
        "input_schema": {
            "type": "object",
            "required": ["pool_name", "member_ip", "member_port"],
            "properties": {
                "pool_name": {"type": "string", "default": "pool_web_app_prod"},
                "member_ip": {"type": "string", "default": "10.100.2.14"},
                "member_port": {"type": "integer", "default": 8443},
                "drain_timeout_sec": {"type": "integer", "default": 120}
            }
        }
    },
    {
        "id": "cat-net-003",
        "identifier": "net-bgp-route-inject",
        "name": "Arista / Cisco BGP Prefix Route Injection",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/net-playbooks.git",
        "git_commit_sha": DEFAULT_SHA,
        "playbook_or_module_path": "playbooks/routing/bgp_inject.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "network",
        "description": "Injects or withdraws IPv4/IPv6 CIDR prefixes across core datacenter BGP spine routers.",
        "tags": ["bgp", "cisco", "arista", "routing", "spine", "cidr"],
        "input_schema": {
            "type": "object",
            "required": ["router_host", "prefix_cidr", "action"],
            "properties": {
                "router_host": {"type": "string", "default": "cr01.dc1.internal"},
                "prefix_cidr": {"type": "string", "default": "192.168.100.0/24"},
                "action": {"type": "string", "default": "announce"},
                "as_path_prepend": {"type": "integer", "default": 0}
            }
        }
    },
    {
        "id": "cat-net-004",
        "identifier": "net-cisco-vlan-trunk-update",
        "name": "Cisco Catalyst / Nexus VLAN Trunk Configuration",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/net-playbooks.git",
        "git_commit_sha": DEFAULT_SHA,
        "playbook_or_module_path": "playbooks/switch/vlan_trunk.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": True,
        "requires_chg": False,
        "category": "network",
        "description": "Adds or removes allowed VLAN IDs across 802.1Q port channels without link flap.",
        "tags": ["cisco", "vlan", "nexus", "trunk", "switch"],
        "input_schema": {
            "type": "object",
            "required": ["switch_host", "port_channel", "vlan_id"],
            "properties": {
                "switch_host": {"type": "string", "default": "sw-tor-01.rack4"},
                "port_channel": {"type": "string", "default": "Po10"},
                "vlan_id": {"type": "integer", "default": 104}
            }
        }
    },
    {
        "id": "cat-net-005",
        "identifier": "net-haproxy-reload-sync",
        "name": "HAProxy Zero-Downtime Reload & Cert Sync",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/net-playbooks.git",
        "git_commit_sha": DEFAULT_SHA,
        "playbook_or_module_path": "playbooks/haproxy/reload.yml",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "network",
        "description": "Executes graceful hitless reload of HAProxy workers using master-worker mode socket pass-off.",
        "tags": ["haproxy", "loadbalancer", "reload", "tls"],
        "input_schema": {
            "type": "object",
            "required": ["target_host"],
            "properties": {
                "target_host": {"type": "string", "default": "lb-ingress-prod.internal"}
            }
        }
    },
    {
        "id": "cat-net-006",
        "identifier": "net-dns-bind-zone-reload",
        "name": "BIND9 / Infoblox Internal DNS Zone Update",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/net-playbooks.git",
        "git_commit_sha": DEFAULT_SHA,
        "playbook_or_module_path": "playbooks/dns/zone_update.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "network",
        "description": "Pushes A/PTR/CNAME DNS records, increments serial, and validates named-checkzone.",
        "tags": ["dns", "bind", "infoblox", "cname", "records"],
        "input_schema": {
            "type": "object",
            "required": ["zone", "record_name", "record_type", "record_value"],
            "properties": {
                "zone": {"type": "string", "default": "internal.corp"},
                "record_name": {"type": "string", "default": "api-gateway"},
                "record_type": {"type": "string", "default": "A"},
                "record_value": {"type": "string", "default": "10.150.12.8"}
            }
        }
    },
    {
        "id": "cat-net-007",
        "identifier": "net-paloalto-fw-rule-push",
        "name": "Palo Alto PAN-OS Security Policy Rule Add",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/net-playbooks.git",
        "git_commit_sha": DEFAULT_SHA,
        "playbook_or_module_path": "playbooks/firewall/paloalto_rule.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "network",
        "description": "Applies security policy rules to Panorama and initiates atomic commit across firewall pair.",
        "tags": ["paloalto", "firewall", "panorama", "security", "rules"],
        "input_schema": {
            "type": "object",
            "required": ["rule_name", "source_zone", "destination_zone", "service"],
            "properties": {
                "rule_name": {"type": "string", "default": "ALLOW-APP-TO-DB"},
                "source_zone": {"type": "string", "default": "Trust-App"},
                "destination_zone": {"type": "string", "default": "DB-Tier"},
                "service": {"type": "string", "default": "tcp-5432"}
            }
        }
    },
    {
        "id": "cat-net-008",
        "identifier": "net-wireguard-mesh-peer",
        "name": "WireGuard Overlay Mesh Peer Registration",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/net-playbooks.git",
        "git_commit_sha": DEFAULT_SHA,
        "playbook_or_module_path": "playbooks/vpn/wireguard_peer.yml",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "network",
        "description": "Provisions public key and allowed IPs across zero-trust WireGuard mesh gateway.",
        "tags": ["wireguard", "vpn", "mesh", "zerotrust"],
        "input_schema": {
            "type": "object",
            "required": ["peer_name", "public_key", "tunnel_ip"],
            "properties": {
                "peer_name": {"type": "string", "default": "gateway-eu-west"},
                "public_key": {"type": "string", "default": "x7b2...k8q1="},
                "tunnel_ip": {"type": "string", "default": "10.88.0.45/32"}
            }
        }
    },

    # =========================================================================
    # 2. DATABASE AUTOMATION (ANSIBLE & TERRAFORM)
    # =========================================================================
    {
        "id": "cat-db-001",
        "identifier": "db-expand-tablespace",
        "name": "Database Tablespace Storage Expansion",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/db-playbooks.git",
        "git_commit_sha": DB_SHA,
        "playbook_or_module_path": "playbooks/postgres/expand_tablespace.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "database",
        "description": "Extends filesystem volume and resizes tablespace storage allocation online for Postgres/Oracle.",
        "tags": ["database", "postgres", "oracle", "tablespace", "disk", "storage", "expand"],
        "input_schema": {
            "type": "object",
            "required": ["tablespace_name", "expand_gb"],
            "properties": {
                "target_host": {"type": "string", "default": "prod-pg-01.internal"},
                "tablespace_name": {"type": "string", "default": "TS_TRANSACTIONS"},
                "expand_gb": {"type": "integer", "default": 50, "minimum": 10, "maximum": 1000}
            }
        }
    },
    {
        "id": "cat-db-002",
        "identifier": "db-postgres-vacuum-analyze",
        "name": "PostgreSQL Scheduled Vacuum Full & Reindex",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/db-playbooks.git",
        "git_commit_sha": DB_SHA,
        "playbook_or_module_path": "playbooks/postgres/vacuum_analyze.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "database",
        "description": "Reclaims dead row tuples and recomputes query planner optimizer statistics on high-churn tables.",
        "tags": ["postgres", "vacuum", "analyze", "reindex", "database", "tuning"],
        "input_schema": {
            "type": "object",
            "required": ["database_name", "target_table"],
            "properties": {
                "database_name": {"type": "string", "default": "ledger_core"},
                "target_table": {"type": "string", "default": "audit_logs"},
                "analyze_only": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "id": "cat-db-003",
        "identifier": "db-mysql-read-replica-add",
        "name": "MySQL / Percona XtraDB Read Replica Provisioning",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/db-playbooks.git",
        "git_commit_sha": DB_SHA,
        "playbook_or_module_path": "terraform/mysql/replica/main.tf",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "database",
        "description": "Spins up read replica from snapshot, configures GTID replication, and adds to service discovery.",
        "tags": ["mysql", "replica", "percona", "gtid", "terraform", "database"],
        "input_schema": {
            "type": "object",
            "required": ["primary_instance_id", "replica_instance_type"],
            "properties": {
                "primary_instance_id": {"type": "string", "default": "db-mysql-prod-01"},
                "replica_instance_type": {"type": "string", "default": "db.r6g.2xlarge"},
                "az": {"type": "string", "default": "us-east-1b"}
            }
        }
    },
    {
        "id": "cat-db-004",
        "identifier": "db-redis-cluster-reshard",
        "name": "Redis Cluster Hash Slot Live Resharding",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/db-playbooks.git",
        "git_commit_sha": DB_SHA,
        "playbook_or_module_path": "playbooks/redis/reshard.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "database",
        "description": "Migrates hash slots across Redis nodes with zero downtime using redis-cli --cluster reshard.",
        "tags": ["redis", "cluster", "reshard", "cache", "memory"],
        "input_schema": {
            "type": "object",
            "required": ["source_node_id", "target_node_id", "slots_count"],
            "properties": {
                "source_node_id": {"type": "string", "default": "node-redis-03"},
                "target_node_id": {"type": "string", "default": "node-redis-05"},
                "slots_count": {"type": "integer", "default": 500}
            }
        }
    },
    {
        "id": "cat-db-005",
        "identifier": "db-mongo-index-rolling-build",
        "name": "MongoDB ReplicaSet Rolling Background Index Build",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/db-playbooks.git",
        "git_commit_sha": DB_SHA,
        "playbook_or_module_path": "playbooks/mongodb/rolling_index.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "database",
        "description": "Constructs B-tree compound indexes sequentially across secondaries before primary stepdown.",
        "tags": ["mongodb", "index", "replicaset", "nosql"],
        "input_schema": {
            "type": "object",
            "required": ["collection_name", "index_spec"],
            "properties": {
                "collection_name": {"type": "string", "default": "customer_sessions"},
                "index_spec": {"type": "string", "default": "{ user_id: 1, created_at: -1 }"}
            }
        }
    },
    {
        "id": "cat-db-006",
        "identifier": "db-oracle-redo-log-switch",
        "name": "Oracle Database Redo Log Group Expansion",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/db-playbooks.git",
        "git_commit_sha": DB_SHA,
        "playbook_or_module_path": "playbooks/oracle/redo_logs.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "database",
        "description": "Adds 4GB online redo log groups to Oracle 19c RAC instances and switches log file.",
        "tags": ["oracle", "redo", "rac", "database", "storage"],
        "input_schema": {
            "type": "object",
            "required": ["oracle_sid", "group_size_mb"],
            "properties": {
                "oracle_sid": {"type": "string", "default": "ORCLPROD1"},
                "group_size_mb": {"type": "integer", "default": 4096}
            }
        }
    },

    # =========================================================================
    # 3. CLOUD INFRASTRUCTURE (TERRAFORM)
    # =========================================================================
    {
        "id": "cat-cloud-001",
        "identifier": "cloud-vpc-peering",
        "name": "Cross-Account AWS VPC Peering Connection",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/cloud-terraform.git",
        "git_commit_sha": CLOUD_SHA,
        "playbook_or_module_path": "modules/aws/vpc_peering/main.tf",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "cloud",
        "description": "Provisions bidirectional VPC peering, route table entries, and security group ingress rules in AWS.",
        "tags": ["aws", "vpc", "peering", "terraform", "cloud", "routing"],
        "input_schema": {
            "type": "object",
            "required": ["peer_vpc_id", "peer_cidr"],
            "properties": {
                "peer_vpc_id": {"type": "string", "default": "vpc-09a8b7c6d5e4"},
                "peer_cidr": {"type": "string", "default": "10.150.0.0/16"},
                "region": {"type": "string", "default": "us-east-1"}
            }
        }
    },
    {
        "id": "cat-cloud-002",
        "identifier": "cloud-eks-nodegroup-scale",
        "name": "AWS EKS Managed Node Group Autoscaling Capacity",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/cloud-terraform.git",
        "git_commit_sha": CLOUD_SHA,
        "playbook_or_module_path": "modules/aws/eks_nodegroup/main.tf",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "cloud",
        "description": "Modifies min/max/desired worker node capacity for Amazon EKS Kubernetes cluster.",
        "tags": ["aws", "eks", "nodegroup", "scale", "kubernetes", "terraform"],
        "input_schema": {
            "type": "object",
            "required": ["cluster_name", "nodegroup_name", "desired_capacity"],
            "properties": {
                "cluster_name": {"type": "string", "default": "prod-useast1-eks-01"},
                "nodegroup_name": {"type": "string", "default": "compute-c6i-xl"},
                "desired_capacity": {"type": "integer", "default": 18, "minimum": 2, "maximum": 100},
                "max_capacity": {"type": "integer", "default": 30}
            }
        }
    },
    {
        "id": "cat-cloud-003",
        "identifier": "cloud-s3-kms-bucket-provision",
        "name": "Secure AWS S3 Bucket with KMS Customer-Managed Key",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/cloud-terraform.git",
        "git_commit_sha": CLOUD_SHA,
        "playbook_or_module_path": "modules/aws/s3_kms/main.tf",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "cloud",
        "description": "Deploys encrypted S3 bucket with versioning, TLS 1.3 enforcement policy, and KMS CMK rotation.",
        "tags": ["aws", "s3", "kms", "encryption", "storage", "terraform"],
        "input_schema": {
            "type": "object",
            "required": ["bucket_name", "retention_days"],
            "properties": {
                "bucket_name": {"type": "string", "default": "corp-analytics-archive-2026"},
                "retention_days": {"type": "integer", "default": 365}
            }
        }
    },
    {
        "id": "cat-cloud-004",
        "identifier": "cloud-azure-vnet-gateway",
        "name": "Azure ExpressRoute Virtual Network Gateway Sync",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/cloud-terraform.git",
        "git_commit_sha": CLOUD_SHA,
        "playbook_or_module_path": "modules/azure/vnet_gateway/main.tf",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "cloud",
        "description": "Updates BGP peering settings and gateway SKU for on-prem to Azure ExpressRoute circuits.",
        "tags": ["azure", "vnet", "expressroute", "gateway", "terraform"],
        "input_schema": {
            "type": "object",
            "required": ["resource_group", "gateway_name"],
            "properties": {
                "resource_group": {"type": "string", "default": "rg-enterprise-network-eastus"},
                "gateway_name": {"type": "string", "default": "gw-er-prod-01"},
                "sku": {"type": "string", "default": "ErGw3AZ"}
            }
        }
    },
    {
        "id": "cat-cloud-005",
        "identifier": "cloud-gcp-cloudnat-ips",
        "name": "GCP Cloud NAT Static Egress IP Pool Expansion",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/cloud-terraform.git",
        "git_commit_sha": CLOUD_SHA,
        "playbook_or_module_path": "modules/gcp/cloud_nat/main.tf",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": True,
        "category": "cloud",
        "description": "Allocates additional external static IP addresses to prevent port exhaustion on Google Cloud NAT.",
        "tags": ["gcp", "nat", "egress", "ip", "terraform"],
        "input_schema": {
            "type": "object",
            "required": ["router_name", "nat_name", "additional_ips_count"],
            "properties": {
                "router_name": {"type": "string", "default": "rtr-gke-prod"},
                "nat_name": {"type": "string", "default": "nat-gke-egress"},
                "additional_ips_count": {"type": "integer", "default": 2}
            }
        }
    },
    {
        "id": "cat-cloud-006",
        "identifier": "cloud-aws-waf-ip-rate-limit",
        "name": "AWS WAF v2 IP Rate Limiting Rule Deployment",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/cloud-terraform.git",
        "git_commit_sha": CLOUD_SHA,
        "playbook_or_module_path": "modules/aws/waf_rules/main.tf",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "cloud",
        "description": "Attaches rate-limiting WebACL rules (e.g., 2,000 req/5min) to Application Load Balancer.",
        "tags": ["aws", "waf", "security", "alb", "ratelimit", "terraform"],
        "input_schema": {
            "type": "object",
            "required": ["web_acl_name", "rate_limit"],
            "properties": {
                "web_acl_name": {"type": "string", "default": "waf-api-perimeter-prod"},
                "rate_limit": {"type": "integer", "default": 2000}
            }
        }
    },

    # =========================================================================
    # 4. OS PATCHING & LIFECYCLE (ANSIBLE)
    # =========================================================================
    {
        "id": "cat-os-001",
        "identifier": "os-rhel9-kernel-patch",
        "name": "RHEL 9 Live Kernel Security Patching (kpatch)",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/os-playbooks.git",
        "git_commit_sha": OS_SHA,
        "playbook_or_module_path": "playbooks/rhel/kernel_kpatch.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "os_patching",
        "description": "Applies zero-reboot Linux kernel CVE fixes using kpatch-dnf and validates live patch module.",
        "tags": ["rhel", "linux", "kernel", "patch", "kpatch", "cve", "os"],
        "input_schema": {
            "type": "object",
            "required": ["target_host", "cve_identifier"],
            "properties": {
                "target_host": {"type": "string", "default": "rhel-app-prod-01.internal"},
                "cve_identifier": {"type": "string", "default": "CVE-2025-3912"},
                "verify_dry_run": {"type": "boolean", "default": True}
            }
        }
    },
    {
        "id": "cat-os-patch",
        "identifier": "os-kernel-patch",
        "name": "Enterprise Linux Kernel Patching (10GB ISO)",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:pnc/os-playbooks.git",
        "git_commit_sha": OS_SHA,
        "playbook_or_module_path": "catalog/os-kernel-patch/playbook.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "os_patching",
        "description": "Enterprise automated Linux kernel patching with 10GB ISO staged via CyberArk PAM.",
        "tags": ["linux", "kernel", "patch", "iso", "rhel"],
        "input_schema": {
            "type": "object",
            "required": ["target_host"],
            "properties": {
                "target_host": {"type": "string", "default": "rhel-app-01.internal"}
            }
        }
    },
    {
        "id": "cat-os-002",
        "identifier": "os-ubuntu-cve-hotpatch",
        "name": "Ubuntu 22.04 / 24.04 Canonical Livepatch Fleet Sync",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/os-playbooks.git",
        "git_commit_sha": OS_SHA,
        "playbook_or_module_path": "playbooks/ubuntu/livepatch.yml",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "os_patching",
        "description": "Syncs Canonical Livepatch client token, applies active patches, and uploads telemetry status.",
        "tags": ["ubuntu", "canonical", "livepatch", "patch", "linux"],
        "input_schema": {
            "type": "object",
            "required": ["target_fleet"],
            "properties": {
                "target_fleet": {"type": "string", "default": "tag_role_worker_staging"}
            }
        }
    },
    {
        "id": "cat-os-003",
        "identifier": "os-windows-wsus-reboot",
        "name": "Windows Server 2022 WSUS Update & Safe Reboot",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/os-playbooks.git",
        "git_commit_sha": OS_SHA,
        "playbook_or_module_path": "playbooks/windows/win_update.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "os_patching",
        "description": "Installs approved KB patches from WSUS with post-update reboot orchestration and health verification.",
        "tags": ["windows", "wsus", "patch", "reboot", "os"],
        "input_schema": {
            "type": "object",
            "required": ["target_host"],
            "properties": {
                "target_host": {"type": "string", "default": "win-ad-dc-02.corp"},
                "reboot_timeout_sec": {"type": "integer", "default": 600}
            }
        }
    },
    {
        "id": "cat-os-004",
        "identifier": "os-selinux-enforce-audit",
        "name": "SELinux Enforcing Mode & Audit Log Remediation",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/os-playbooks.git",
        "git_commit_sha": OS_SHA,
        "playbook_or_module_path": "playbooks/security/selinux.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "os_patching",
        "description": "Transitions SELinux to Enforcing mode and compiles custom sepolicy modules from audit2allow.",
        "tags": ["selinux", "security", "rhel", "audit", "compliance"],
        "input_schema": {
            "type": "object",
            "required": ["target_host"],
            "properties": {
                "target_host": {"type": "string", "default": "sec-gateway-prod.internal"}
            }
        }
    },
    {
        "id": "cat-os-005",
        "identifier": "os-systemd-daemon-reload",
        "name": "Systemd Daemon Reload & Unit Service Restart",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/os-playbooks.git",
        "git_commit_sha": OS_SHA,
        "playbook_or_module_path": "playbooks/linux/systemd_reload.yml",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "os_patching",
        "description": "Executes systemctl daemon-reload and verifies journalctl exit codes following unit file updates.",
        "tags": ["systemd", "systemctl", "linux", "service", "reload"],
        "input_schema": {
            "type": "object",
            "required": ["target_host", "unit_name"],
            "properties": {
                "target_host": {"type": "string", "default": "app-backend-01.internal"},
                "unit_name": {"type": "string", "default": "payment-worker.service"}
            }
        }
    },

    # =========================================================================
    # 5. KUBERNETES & CONTAINERS (TERRAFORM & ANSIBLE)
    # =========================================================================
    {
        "id": "cat-k8s-001",
        "identifier": "k8s-ingress-nginx-upgrade",
        "name": "Kubernetes Ingress-NGINX Controller Rolling Upgrade",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/k8s-playbooks.git",
        "git_commit_sha": K8S_SHA,
        "playbook_or_module_path": "helm/ingress-nginx/upgrade.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "kubernetes",
        "description": "Executes canaried Helm upgrade for ingress-nginx with maxSurge=1 and zero 502 connection drops.",
        "tags": ["kubernetes", "ingress", "nginx", "helm", "k8s", "upgrade"],
        "input_schema": {
            "type": "object",
            "required": ["cluster_context", "target_version"],
            "properties": {
                "cluster_context": {"type": "string", "default": "k8s-prod-useast1"},
                "target_version": {"type": "string", "default": "4.10.1"}
            }
        }
    },
    {
        "id": "cat-k8s-002",
        "identifier": "k8s-namespace-quota-provision",
        "name": "Kubernetes Tenant Namespace & ResourceQuota Deploy",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/k8s-terraform.git",
        "git_commit_sha": K8S_SHA,
        "playbook_or_module_path": "modules/k8s/namespace_quota/main.tf",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "kubernetes",
        "description": "Provisions tenant namespace, ResourceQuota (CPU/RAM/PVC), NetworkPolicy, and RBAC RoleBinding.",
        "tags": ["kubernetes", "namespace", "quota", "rbac", "k8s", "terraform"],
        "input_schema": {
            "type": "object",
            "required": ["namespace", "cpu_limit_cores", "memory_limit_gi"],
            "properties": {
                "namespace": {"type": "string", "default": "team-payments-staging"},
                "cpu_limit_cores": {"type": "integer", "default": 64},
                "memory_limit_gi": {"type": "integer", "default": 256}
            }
        }
    },
    {
        "id": "cat-k8s-003",
        "identifier": "k8s-node-cordon-drain",
        "name": "Kubernetes Worker Node Safe Cordon & Drain",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/k8s-playbooks.git",
        "git_commit_sha": K8S_SHA,
        "playbook_or_module_path": "playbooks/k8s/drain_node.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "kubernetes",
        "description": "Cordon node to prevent new pod schedules and drains pods respecting PodDisruptionBudgets (PDB).",
        "tags": ["kubernetes", "node", "drain", "cordon", "k8s", "maintenance"],
        "input_schema": {
            "type": "object",
            "required": ["node_name"],
            "properties": {
                "node_name": {"type": "string", "default": "ip-10-0-14-88.ec2.internal"},
                "grace_period_sec": {"type": "integer", "default": 60}
            }
        }
    },
    {
        "id": "cat-k8s-004",
        "identifier": "k8s-cert-manager-clusterissuer",
        "name": "Kubernetes cert-manager Vault ClusterIssuer Sync",
        "engine": ExecutionEngineType.TERRAFORM,
        "git_repo": "git@github.com:enterprise/k8s-terraform.git",
        "git_commit_sha": K8S_SHA,
        "playbook_or_module_path": "modules/k8s/cert_manager/main.tf",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "kubernetes",
        "description": "Configures HashiCorp Vault PKI intermediate CA ClusterIssuer for automatic mTLS pods.",
        "tags": ["kubernetes", "cert-manager", "vault", "mtls", "k8s"],
        "input_schema": {
            "type": "object",
            "required": ["vault_server_url", "pki_mount_path"],
            "properties": {
                "vault_server_url": {"type": "string", "default": "https://vault.internal:8200"},
                "pki_mount_path": {"type": "string", "default": "pki_internal"}
            }
        }
    },
    {
        "id": "cat-k8s-005",
        "identifier": "k8s-daemonset-rolling-restart",
        "name": "Kubernetes DaemonSet Orchestrated Rolling Restart",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/k8s-playbooks.git",
        "git_commit_sha": K8S_SHA,
        "playbook_or_module_path": "playbooks/k8s/restart_daemonset.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "kubernetes",
        "description": "Rolls DaemonSet pods sequentially with health probe checks between node transitions.",
        "tags": ["kubernetes", "daemonset", "restart", "k8s"],
        "input_schema": {
            "type": "object",
            "required": ["daemonset_name", "namespace"],
            "properties": {
                "daemonset_name": {"type": "string", "default": "fluent-bit-logging"},
                "namespace": {"type": "string", "default": "monitoring"}
            }
        }
    },

    # =========================================================================
    # 6. SECURITY, IAM & COMPLIANCE (ANSIBLE & TERRAFORM)
    # =========================================================================
    {
        "id": "cat-sec-001",
        "identifier": "sec-ssh-fleet-rotate",
        "name": "Fleet-Wide Ed25519 SSH Authorized Keys Rotation",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/sec-playbooks.git",
        "git_commit_sha": SEC_SHA,
        "playbook_or_module_path": "playbooks/ssh/rotate_fleet_keys.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "security",
        "description": "Generates new Ed25519 SSH keypairs in CyberArk, distributes public keys, and revokes expired keys.",
        "tags": ["ssh", "security", "keys", "rotation", "cyberark", "pam"],
        "input_schema": {
            "type": "object",
            "required": ["target_host_group", "key_owner"],
            "properties": {
                "target_host_group": {"type": "string", "default": "all_linux_prod"},
                "key_owner": {"type": "string", "default": "automation-svc"}
            }
        }
    },
    {
        "id": "cat-sec-002",
        "identifier": "sec-vault-approle-renew",
        "name": "HashiCorp Vault AppRole SecretID Mass Renewal",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/sec-playbooks.git",
        "git_commit_sha": SEC_SHA,
        "playbook_or_module_path": "playbooks/vault/renew_approle.yml",
        "risk_tier": RiskTier.MEDIUM,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "security",
        "description": "Rotates AppRole SecretID credentials with overlap grace periods to prevent service disruption.",
        "tags": ["vault", "security", "approle", "tokens", "secrets"],
        "input_schema": {
            "type": "object",
            "required": ["role_name"],
            "properties": {
                "role_name": {"type": "string", "default": "app-trade-settlement"}
            }
        }
    },
    {
        "id": "cat-sec-003",
        "identifier": "sec-tls-bundle-sync",
        "name": "Enterprise Root & Intermediate CA Bundle Distribution",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/sec-playbooks.git",
        "git_commit_sha": SEC_SHA,
        "playbook_or_module_path": "playbooks/pki/sync_ca_bundle.yml",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "security",
        "description": "Updates /etc/pki/ca-trust and runs update-ca-trust across all enterprise compute hosts.",
        "tags": ["tls", "ssl", "ca", "bundle", "security", "pki"],
        "input_schema": {
            "type": "object",
            "required": ["target_fleet"],
            "properties": {
                "target_fleet": {"type": "string", "default": "all_servers"}
            }
        }
    },
    {
        "id": "cat-sec-004",
        "identifier": "sec-trufflehog-git-scan",
        "name": "TruffleHog Real-Time Secrets & Credential Leak Scan",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/sec-playbooks.git",
        "git_commit_sha": SEC_SHA,
        "playbook_or_module_path": "playbooks/scanner/trufflehog.yml",
        "risk_tier": RiskTier.LOW,
        "requires_maker_checker": False,
        "requires_chg": False,
        "category": "security",
        "description": "Runs high-speed entropy and verified API regex scan across Git repositories and S3 buckets.",
        "tags": ["trufflehog", "secrets", "audit", "security", "scanner"],
        "input_schema": {
            "type": "object",
            "required": ["repo_url"],
            "properties": {
                "repo_url": {"type": "string", "default": "git@github.com:enterprise/payments-api.git"}
            }
        }
    },
    {
        "id": "cat-sec-005",
        "identifier": "sec-cis-benchmark-remediate",
        "name": "CIS Linux Level 2 Benchmark Automated Remediation",
        "engine": ExecutionEngineType.ANSIBLE,
        "git_repo": "git@github.com:enterprise/sec-playbooks.git",
        "git_commit_sha": SEC_SHA,
        "playbook_or_module_path": "playbooks/compliance/cis_remediate.yml",
        "risk_tier": RiskTier.HIGH,
        "requires_maker_checker": True,
        "requires_chg": True,
        "category": "security",
        "description": "Remediates non-compliant CIS security controls (umask, suid binaries, grub password, auditd rules).",
        "tags": ["cis", "compliance", "benchmark", "hardening", "security"],
        "input_schema": {
            "type": "object",
            "required": ["target_host"],
            "properties": {
                "target_host": {"type": "string", "default": "rhel-bastion-01.internal"}
            }
        }
    }
]


def _generate_synthetic_catalog_scale(count: int = 120) -> List[Dict[str, Any]]:
    """
    Generates a full corpus of 100-1,000+ realistic enterprise playbooks and Terraform stacks
    by parameterizing real enterprise patterns across multiple regions, cloud providers, and subsystems.
    """
    items = list(RAW_CATALOG_DEFINITIONS)
    
    clouds = ["aws", "azure", "gcp"]
    regions = ["us-east-1", "us-west-2", "eu-central-1", "ap-southeast-1"]
    database_types = ["postgres", "mysql", "redis", "mongodb", "oracle", "clickhouse"]
    network_types = ["f5", "cisco", "arista", "haproxy", "paloalto"]
    
    idx = len(items) + 1
    while len(items) < count:
        c_type = idx % 6
        if c_type == 0:  # Cloud Terraform
            cloud = clouds[idx % len(clouds)]
            region = regions[idx % len(regions)]
            resource = ["transit-gateway", "security-group", "route-table", "iam-role", "elasticache-cluster", "kms-key"][idx % 6]
            identifier = f"cloud-{cloud}-{resource}-{region.replace('-', '')}-{idx:03d}"
            name = f"{cloud.upper()} {resource.replace('-', ' ').title()} ({region})"
            items.append({
                "id": f"cat-cloud-{idx:03d}",
                "identifier": identifier,
                "name": name,
                "engine": ExecutionEngineType.TERRAFORM,
                "git_repo": f"git@github.com:enterprise/cloud-{cloud}.git",
                "git_commit_sha": CLOUD_SHA,
                "playbook_or_module_path": f"modules/{cloud}/{resource}/main.tf",
                "risk_tier": RiskTier.MEDIUM if idx % 2 == 0 else RiskTier.HIGH,
                "requires_maker_checker": idx % 2 == 0,
                "requires_chg": idx % 3 == 0,
                "category": "cloud",
                "description": f"Automated Terraform module to manage {cloud.upper()} {resource} across {region}.",
                "tags": [cloud, resource.replace("-", ""), "terraform", "cloud", region],
                "input_schema": {
                    "type": "object",
                    "required": ["environment", "resource_name"],
                    "properties": {
                        "environment": {"type": "string", "default": "PROD" if idx % 2 == 0 else "UAT"},
                        "resource_name": {"type": "string", "default": f"{resource}-{idx}"}
                    }
                }
            })
        elif c_type == 1:  # Database
            db = database_types[idx % len(database_types)]
            action = ["backup-snapshot", "failover-drill", "archive-purge", "tune-buffers", "connection-pool-scale"][idx % 5]
            identifier = f"db-{db}-{action}-{idx:03d}"
            name = f"{db.title()} Database {action.replace('-', ' ').title()}"
            items.append({
                "id": f"cat-db-{idx:03d}",
                "identifier": identifier,
                "name": name,
                "engine": ExecutionEngineType.ANSIBLE if idx % 2 == 0 else ExecutionEngineType.TERRAFORM,
                "git_repo": f"git@github.com:enterprise/db-{db}.git",
                "git_commit_sha": DB_SHA,
                "playbook_or_module_path": f"playbooks/{db}/{action}.yml",
                "risk_tier": RiskTier.HIGH if "failover" in action or "purge" in action else RiskTier.MEDIUM,
                "requires_maker_checker": True,
                "requires_chg": True,
                "category": "database",
                "description": f"Orchestrates enterprise {action.replace('-', ' ')} for {db.title()} clusters.",
                "tags": [db, action.replace("-", ""), "database", "dba"],
                "input_schema": {
                    "type": "object",
                    "required": ["cluster_id"],
                    "properties": {
                        "cluster_id": {"type": "string", "default": f"{db}-prod-cluster-{idx % 4 + 1}"}
                    }
                }
            })
        elif c_type == 2:  # Network
            net = network_types[idx % len(network_types)]
            action = ["config-backup", "acl-audit", "interface-reset", "traffic-shift", "bgp-neighbor-sync"][idx % 5]
            identifier = f"net-{net}-{action}-{idx:03d}"
            name = f"{net.upper()} Network {action.replace('-', ' ').title()}"
            items.append({
                "id": f"cat-net-{idx:03d}",
                "identifier": identifier,
                "name": name,
                "engine": ExecutionEngineType.ANSIBLE,
                "git_repo": "git@github.com:enterprise/net-playbooks.git",
                "git_commit_sha": DEFAULT_SHA,
                "playbook_or_module_path": f"playbooks/{net}/{action}.yml",
                "risk_tier": RiskTier.HIGH if "traffic-shift" in action else RiskTier.MEDIUM,
                "requires_maker_checker": "traffic-shift" in action,
                "requires_chg": True,
                "category": "network",
                "description": f"Executes verified {action.replace('-', ' ')} on {net.upper()} core infrastructure.",
                "tags": [net, action.replace("-", ""), "network", "router"],
                "input_schema": {
                    "type": "object",
                    "required": ["device_hostname"],
                    "properties": {
                        "device_hostname": {"type": "string", "default": f"{net}-core-{idx % 8 + 1}.internal"}
                    }
                }
            })
        elif c_type == 3:  # OS Patching
            distro = ["rhel8", "rhel9", "ubuntu22", "rocky9", "win2022"][idx % 5]
            action = ["security-errata", "reboot-graceful", "auditd-sync", "ntp-time-sync", "logrotate-optimize"][idx % 5]
            identifier = f"os-{distro}-{action}-{idx:03d}"
            name = f"{distro.upper()} Host {action.replace('-', ' ').title()}"
            items.append({
                "id": f"cat-os-{idx:03d}",
                "identifier": identifier,
                "name": name,
                "engine": ExecutionEngineType.ANSIBLE,
                "git_repo": "git@github.com:enterprise/os-playbooks.git",
                "git_commit_sha": OS_SHA,
                "playbook_or_module_path": f"playbooks/{distro}/{action}.yml",
                "risk_tier": RiskTier.MEDIUM if "errata" in action else RiskTier.LOW,
                "requires_maker_checker": False,
                "requires_chg": "errata" in action,
                "category": "os_patching",
                "description": f"Applies {action.replace('-', ' ')} across {distro.upper()} enterprise server fleets.",
                "tags": [distro, action.replace("-", ""), "patching", "os", "linux"],
                "input_schema": {
                    "type": "object",
                    "required": ["target_host"],
                    "properties": {
                        "target_host": {"type": "string", "default": f"{distro}-srv-{idx % 12 + 1}.internal"}
                    }
                }
            })
        elif c_type == 4:  # Kubernetes
            k8s_action = ["pod-autoscaler-hpa", "network-policy-lockdown", "storageclass-provision", "taint-toleration-sync", "secret-vault-reloader"][idx % 5]
            identifier = f"k8s-{k8s_action}-{idx:03d}"
            name = f"Kubernetes {k8s_action.replace('-', ' ').title()}"
            items.append({
                "id": f"cat-k8s-{idx:03d}",
                "identifier": identifier,
                "name": name,
                "engine": ExecutionEngineType.TERRAFORM if idx % 2 == 0 else ExecutionEngineType.ANSIBLE,
                "git_repo": "git@github.com:enterprise/k8s-infra.git",
                "git_commit_sha": K8S_SHA,
                "playbook_or_module_path": f"manifests/{k8s_action}/main.tf",
                "risk_tier": RiskTier.LOW if "secret" in k8s_action else RiskTier.MEDIUM,
                "requires_maker_checker": False,
                "requires_chg": False,
                "category": "kubernetes",
                "description": f"Deploys and maintains {k8s_action.replace('-', ' ')} across Kubernetes clusters.",
                "tags": ["k8s", "kubernetes", k8s_action.replace("-", "")],
                "input_schema": {
                    "type": "object",
                    "required": ["cluster_name", "namespace"],
                    "properties": {
                        "cluster_name": {"type": "string", "default": "k8s-prod-useast1"},
                        "namespace": {"type": "string", "default": "default"}
                    }
                }
            })
        else:  # Security
            sec_action = ["pam-sudoers-sync", "firewalld-zone-lockdown", "crowdstrike-agent-update", "qualys-sensor-scan", "waf-rate-burst-tune"][idx % 5]
            identifier = f"sec-{sec_action}-{idx:03d}"
            name = f"Security {sec_action.replace('-', ' ').title()}"
            items.append({
                "id": f"cat-sec-{idx:03d}",
                "identifier": identifier,
                "name": name,
                "engine": ExecutionEngineType.ANSIBLE,
                "git_repo": "git@github.com:enterprise/sec-playbooks.git",
                "git_commit_sha": SEC_SHA,
                "playbook_or_module_path": f"playbooks/sec/{sec_action}.yml",
                "risk_tier": RiskTier.HIGH if "sudoers" in sec_action else RiskTier.MEDIUM,
                "requires_maker_checker": "sudoers" in sec_action,
                "requires_chg": True,
                "category": "security",
                "description": f"Enforces enterprise {sec_action.replace('-', ' ')} standards.",
                "tags": ["security", "sec", sec_action.replace("-", "")],
                "input_schema": {
                    "type": "object",
                    "required": ["fleet_scope"],
                    "properties": {
                        "fleet_scope": {"type": "string", "default": "all_prod_bastions"}
                    }
                }
            })
        idx += 1
    return items


# Pre-materialized 120 items
_MATERIALIZED_ITEMS = _generate_synthetic_catalog_scale(120)


def get_catalog_items() -> List[CatalogItem]:
    """Returns the full collection of CatalogItem domain objects."""
    catalog = []
    for d in _MATERIALIZED_ITEMS:
        item = CatalogItem(
            id=d["id"],
            identifier=d["identifier"],
            name=d["name"],
            engine=d["engine"],
            git_repo=d["git_repo"],
            git_commit_sha=d["git_commit_sha"],
            playbook_or_module_path=d["playbook_or_module_path"],
            risk_tier=d["risk_tier"],
            requires_maker_checker=d["requires_maker_checker"],
            requires_chg=d["requires_chg"],
            input_schema=d["input_schema"],
            category=d.get("category", "general"),
            description=d.get("description", ""),
            tags=d.get("tags", [])
        )
        catalog.append(item)
    return catalog


def search_catalog(
    query: str = "",
    category: Optional[str] = None,
    engine: Optional[str] = None,
    risk_tier: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Filters the catalog by search query, category, engine, and risk tier."""
    results = []
    q_tokens = [t.lower() for t in re.findall(r"\w+", query)]
    
    for d in _MATERIALIZED_ITEMS:
        if category and category != "all" and d.get("category", "") != category:
            continue
        if engine and engine != "all" and d["engine"].value != engine:
            continue
        if risk_tier and risk_tier != "all" and d["risk_tier"].value != risk_tier:
            continue
            
        if q_tokens:
            haystack = f"{d['identifier']} {d['name']} {d.get('description', '')} {' '.join(d.get('tags', []))}".lower()
            match_score = sum(1 for t in q_tokens if t in haystack)
            if match_score == 0:
                continue
        results.append(d)
    return results


def find_matching_playbook(user_query: str, ambient_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    AI Intent Matching Algorithm:
    Takes natural language from the chat user, scores all 110+ items using semantic weights
    and BM25 keyword overlap, extracts extracted variables (e.g. host, IPs, sizes), and returns
    an interactive launch card specification.
    """
    user_lower = user_query.lower()
    
    # Specific semantic routing anchors
    intent_weights = {
        "f5": ["f5", "ssl", "cert", "tls", "vip", "loadbalancer", "renew"],
        "pool": ["pool", "member", "drain", "disable", "traffic"],
        "bgp": ["bgp", "route", "inject", "prefix", "announce", "cisco", "arista"],
        "vlan": ["vlan", "trunk", "catalyst", "nexus", "switch"],
        "haproxy": ["haproxy", "hitless", "reload"],
        "dns": ["dns", "bind", "zone", "record", "cname", "infoblox"],
        "paloalto": ["palo alto", "paloalto", "firewall", "rule", "panorama"],
        "tablespace": ["tablespace", "disk", "expand", "storage", "postgres", "oracle"],
        "vacuum": ["vacuum", "reindex", "analyze", "postgres"],
        "replica": ["replica", "replication", "mysql", "gtid", "read replica"],
        "redis": ["redis", "reshard", "redis-cli", "slots"],
        "mongo": ["mongo", "mongodb", "nosql", "index", "rolling"],
        "vpc": ["vpc", "peering", "peer", "cidr", "cross-account"],
        "eks": ["eks", "nodegroup", "scale", "worker", "capacity"],
        "k8s": ["kubernetes", "k8s", "kubectl", "ingress", "pod", "daemonset", "namespace"],
        "s3": ["s3", "bucket", "kms", "encryption"],
        "azure": ["azure", "expressroute", "vnet", "gateway"],
        "gcp": ["gcp", "cloud nat", "egress", "ip pool"],
        "waf": ["waf", "rate limit", "ddos", "perimeter"],
        "patch": ["patch", "kernel", "kpatch", "cve", "rhel", "linux", "errata"],
        "ubuntu": ["ubuntu", "livepatch", "canonical"],
        "windows": ["windows", "wsus", "reboot", "kb"],
        "selinux": ["selinux", "enforcing", "audit2allow"],
        "systemd": ["systemd", "systemctl", "daemon-reload"],
        "ingress": ["ingress", "nginx", "helm", "controller"],
        "namespace": ["namespace", "quota", "tenant", "resourcequota"],
        "drain": ["drain", "cordon", "node", "pdb"],
        "ssh": ["ssh", "key", "rotate", "authorized_keys", "ed25519"],
        "vault": ["vault", "approle", "secretid", "renew"],
        "cis": ["cis", "benchmark", "hardening", "compliance"],
        "ping": ["ping", "probe", "facts", "sandbox", "connectivity"],
        "jenkins": ["jenkins", "ci", "cd", "pipeline"],
        "gitlab": ["gitlab", "repo", "git", "omnibus"],
        "nginx": ["nginx", "reverse proxy", "web server"],
        "user": ["create user", "new user", "operator", "sudo user", "provision user"],
        "hardening": ["harden", "hardening", "ssh hardening", "security updates"]
    }
    
    scored_candidates = []
    for item in _MATERIALIZED_ITEMS:
        score = 0.0
        item_text = f"{item['identifier']} {item['name']} {item.get('description', '')} {' '.join(item.get('tags', []))}".lower()
        
        # Keyword matching
        q_words = re.findall(r"\w+", user_lower)
        for w in q_words:
            if len(w) > 2 and w in item_text:
                score += 1.5
                
        # Semantic group match
        for group, keywords in intent_weights.items():
            if any(k in user_lower for k in keywords):
                if group in item['identifier'] or any(k in item['tags'] for k in keywords):
                    score += 5.0

        # Category and engine alignment boosts
        item_cat = item.get("category", "")
        if ("kubernetes" in user_lower or "k8s" in user_lower) and item_cat in ("kubernetes", "cloud"):
            score += 8.0
        if ("database" in user_lower or "db" in user_lower or "postgres" in user_lower or "oracle" in user_lower) and item_cat == "database":
            score += 8.0
        if ("network" in user_lower or "switch" in user_lower or "router" in user_lower or "f5" in user_lower) and item_cat == "network":
            score += 8.0
        if ("patch" in user_lower or "cve" in user_lower or "kernel" in user_lower) and item_cat == "os_patching":
            score += 8.0
        if ("security" in user_lower or "ssh" in user_lower or "vault" in user_lower) and item_cat == "security":
            score += 8.0
        if "terraform" in user_lower and item["engine"] == ExecutionEngineType.TERRAFORM:
            score += 6.0
        if ("ansible" in user_lower or "playbook" in user_lower) and item["engine"] == ExecutionEngineType.ANSIBLE:
            score += 6.0
                    
        scored_candidates.append((item, score))
        
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    if not scored_candidates or scored_candidates[0][1] < 4.0:
        return {
            "matched": False,
            "status": "REFUSED",
            "confidence": 0.0,
            "refusal_reason": "No catalog automation playbook matches your intent. Please refine your query or consult the catalog.",
            "catalog_id": None,
            "identifier": None,
            "name": None,
            "engine": None,
            "category": "unknown",
            "risk_tier": "LOW",
            "requires_maker_checker": False,
            "requires_chg": False,
            "detected_environment": "PROD",
            "suggested_parameters": {},
            "reasoning": "Zero-score refusal gate: query did not match any operational keywords or catalog attributes."
        }
    best_item, top_score = scored_candidates[0]
    
    # Slot extraction for dynamic UI inputs
    extracted_params: Dict[str, Any] = dict(ambient_params or {})
    schema_props = best_item.get("input_schema", {}).get("properties", {})
    
    # Host extraction
    host_match = re.search(r"\b([a-zA-Z0-9_-]+\.(?:internal|corp|pnc\.com|local))\b", user_query)
    if host_match:
        extracted_params["target_host"] = host_match.group(1)
        extracted_params["hostname"] = host_match.group(1)
    else:
        simple_host = re.search(r"\b([a-zA-Z0-9]+-[a-zA-Z0-9]+-[0-9]{1,2})\b", user_query)
        if simple_host:
            extracted_params["target_host"] = simple_host.group(1)
            extracted_params["hostname"] = simple_host.group(1)
            
    # IP extraction
    ip_match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", user_query)
    if ip_match:
        extracted_params["vip_ip"] = ip_match.group(1)
        extracted_params["member_ip"] = ip_match.group(1)
        
    # Numeric values (GB / Days / Counts)
    gb_match = re.search(r"(\d+)\s*(?:gb|gig|gigs)", user_query, re.I)
    if gb_match:
        extracted_params["expand_gb"] = int(gb_match.group(1))
        
    days_match = re.search(r"(\d+)\s*(?:days?|d)", user_query, re.I)
    if days_match:
        extracted_params["cert_valid_days"] = int(days_match.group(1))
        
    # Environment detection
    env = "PROD"
    if "staging" in user_lower or "stage" in user_lower:
        env = "STAGING"
    elif "uat" in user_lower:
        env = "UAT"
    elif "dev" in user_lower:
        env = "DEV"
        
    # Pre-fill defaults from schema if not extracted
    final_params: Dict[str, Any] = {}
    for prop_key, prop_val in schema_props.items():
        if prop_key in extracted_params:
            final_params[prop_key] = extracted_params[prop_key]
        elif "default" in prop_val:
            final_params[prop_key] = prop_val["default"]
        else:
            final_params[prop_key] = ""
            
    confidence = min(0.98, max(0.65, top_score / 12.0))
    
    return {
        "matched": True,
        "confidence": round(confidence, 2),
        "catalog_id": best_item["id"],
        "identifier": best_item["identifier"],
        "name": best_item["name"],
        "engine": best_item["engine"].value,
        "category": best_item.get("category", "general"),
        "risk_tier": best_item["risk_tier"].value,
        "requires_maker_checker": best_item["requires_maker_checker"],
        "requires_chg": best_item["requires_chg"],
        "detected_environment": env,
        "description": best_item.get("description", ""),
        "suggested_parameters": final_params,
        "schema": best_item["input_schema"],
        "git_ref": f"{best_item['git_repo']}@{best_item['git_commit_sha'][:7]}",
        "reasoning": f"Identified intent '{best_item['name']}' based on match with operational catalog rules. Engine: {best_item['engine'].value.upper()}."
    }


def get_sample_tasks() -> List[Dict[str, Any]]:
    """
    Returns 30+ pre-seeded realistic execution tasks across multiple engines, environments,
    statuses, and categories for rich filtering demonstrations.
    """
    return [
        {
            "id": "task-1000",
            "correlation_id": "EXEC-9901",
            "identifier": "os-sandbox-ping",
            "name": "Sandbox Ping & Facts Gathering Probe",
            "engine": "ansible",
            "category": "os_patching",
            "target_resource": "vulcan-sandbox",
            "environment": "SANDBOX",
            "status": "QUEUED",
            "risk_tier": "LOW",
            "requester_id": "eng.alice",
            "approver_id": "lead.bob",
            "duration_sec": 0,
            "created_at": "2026-09-06T12:00:00Z",
            "parameters": {"target_host": "sandbox"}
        },
        {
            "id": "task-1001",
            "correlation_id": "EXEC-9821",
            "identifier": "net-f5-cert-renew",
            "name": "F5 BIG-IP SSL Certificate Renewal",
            "engine": "ansible",
            "category": "network",
            "target_resource": "f5-edge-01.internal",
            "environment": "PROD",
            "status": "RUNNING",
            "risk_tier": "HIGH",
            "requester_id": "alex.engineer",
            "approver_id": "sarah.lead",
            "duration_sec": 48,
            "created_at": "2026-09-06T09:12:10Z",
            "parameters": {"hostname": "f5-edge-01.internal", "vip_ip": "10.200.1.50", "cert_valid_days": 90}
        },
        {
            "id": "task-1002",
            "correlation_id": "EXEC-9820",
            "identifier": "cloud-vpc-peering",
            "name": "Cross-Account AWS VPC Peering Connection",
            "engine": "terraform",
            "category": "cloud",
            "target_resource": "vpc-09a8b7c6d5e4",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "david.cloudops",
            "approver_id": "lead.bob",
            "duration_sec": 142,
            "created_at": "2026-09-06T08:55:00Z",
            "parameters": {"peer_vpc_id": "vpc-09a8b7c6d5e4", "peer_cidr": "10.150.0.0/16"}
        },
        {
            "id": "task-1003",
            "correlation_id": "EXEC-9819",
            "identifier": "db-expand-tablespace",
            "name": "Database Tablespace Disk Expansion",
            "engine": "ansible",
            "category": "database",
            "target_resource": "prod-pg-01.internal",
            "environment": "PROD",
            "status": "FAILED",
            "risk_tier": "HIGH",
            "requester_id": "priya.dba",
            "approver_id": "sarah.lead",
            "duration_sec": 76,
            "created_at": "2026-09-06T08:30:15Z",
            "error_message": "Fatal: Storage pool VG_DATA has insufficient free extents for +100GB.",
            "parameters": {"tablespace_name": "TS_TRANSACTIONS", "expand_gb": 100}
        },
        {
            "id": "task-1004",
            "correlation_id": "EXEC-9818",
            "identifier": "os-rhel9-kernel-patch",
            "name": "RHEL 9 Live Kernel Security Patching (kpatch)",
            "engine": "ansible",
            "category": "os_patching",
            "target_resource": "rhel-app-prod-01.internal",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "HIGH",
            "requester_id": "marcus.sre",
            "approver_id": "lead.bob",
            "duration_sec": 310,
            "created_at": "2026-09-06T08:05:00Z",
            "parameters": {"cve_identifier": "CVE-2025-3912", "target_host": "rhel-app-prod-01.internal"}
        },
        {
            "id": "task-1005",
            "correlation_id": "EXEC-9817",
            "identifier": "k8s-eks-nodegroup-scale",
            "name": "AWS EKS Managed Node Group Autoscaling Capacity",
            "engine": "terraform",
            "category": "cloud",
            "target_resource": "prod-useast1-eks-01",
            "environment": "PROD",
            "status": "RUNNING",
            "risk_tier": "HIGH",
            "requester_id": "marcus.sre",
            "approver_id": "sarah.lead",
            "duration_sec": 95,
            "created_at": "2026-09-06T07:45:10Z",
            "parameters": {"cluster_name": "prod-useast1-eks-01", "desired_capacity": 24}
        },
        {
            "id": "task-1006",
            "correlation_id": "EXEC-9816",
            "identifier": "sec-ssh-fleet-rotate",
            "name": "Fleet-Wide Ed25519 SSH Authorized Keys Rotation",
            "engine": "ansible",
            "category": "security",
            "target_resource": "all_linux_prod",
            "environment": "PROD",
            "status": "PENDING_APPROVAL",
            "risk_tier": "HIGH",
            "requester_id": "sec-ops-bot",
            "approver_id": None,
            "duration_sec": 0,
            "created_at": "2026-09-06T07:20:00Z",
            "parameters": {"target_host_group": "all_linux_prod", "key_owner": "automation-svc"}
        },
        {
            "id": "task-1007",
            "correlation_id": "EXEC-9815",
            "identifier": "k8s-ingress-nginx-upgrade",
            "name": "Kubernetes Ingress-NGINX Controller Rolling Upgrade",
            "engine": "ansible",
            "category": "kubernetes",
            "target_resource": "k8s-prod-useast1",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "HIGH",
            "requester_id": "alex.engineer",
            "approver_id": "sarah.lead",
            "duration_sec": 412,
            "created_at": "2026-09-06T06:50:00Z",
            "parameters": {"cluster_context": "k8s-prod-useast1", "target_version": "4.10.1"}
        },
        {
            "id": "task-1008",
            "correlation_id": "EXEC-9814",
            "identifier": "cloud-s3-kms-bucket-provision",
            "name": "Secure AWS S3 Bucket with KMS Customer-Managed Key",
            "engine": "terraform",
            "category": "cloud",
            "target_resource": "corp-analytics-archive-2026",
            "environment": "UAT",
            "status": "SUCCESS",
            "risk_tier": "LOW",
            "requester_id": "david.cloudops",
            "approver_id": None,
            "duration_sec": 55,
            "created_at": "2026-09-06T06:15:30Z",
            "parameters": {"bucket_name": "corp-analytics-archive-2026", "retention_days": 365}
        },
        {
            "id": "task-1009",
            "correlation_id": "EXEC-9813",
            "identifier": "db-postgres-vacuum-analyze",
            "name": "PostgreSQL Scheduled Vacuum Full & Reindex",
            "engine": "ansible",
            "category": "database",
            "target_resource": "db-pg-uat-01.internal",
            "environment": "UAT",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "priya.dba",
            "approver_id": None,
            "duration_sec": 184,
            "created_at": "2026-09-06T05:40:00Z",
            "parameters": {"database_name": "ledger_core", "target_table": "audit_logs"}
        },
        {
            "id": "task-1010",
            "correlation_id": "EXEC-9812",
            "identifier": "net-bgp-route-inject",
            "name": "Arista / Cisco BGP Prefix Route Injection",
            "engine": "ansible",
            "category": "network",
            "target_resource": "cr01.dc1.internal",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "HIGH",
            "requester_id": "jason.neteng",
            "approver_id": "sarah.lead",
            "duration_sec": 62,
            "created_at": "2026-09-06T05:10:00Z",
            "parameters": {"router_host": "cr01.dc1.internal", "prefix_cidr": "192.168.100.0/24"}
        },
        {
            "id": "task-1011",
            "correlation_id": "EXEC-9811",
            "identifier": "k8s-node-cordon-drain",
            "name": "Kubernetes Worker Node Safe Cordon & Drain",
            "engine": "ansible",
            "category": "kubernetes",
            "target_resource": "ip-10-0-14-88.ec2.internal",
            "environment": "DEV",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "alex.engineer",
            "approver_id": None,
            "duration_sec": 89,
            "created_at": "2026-09-06T04:35:00Z",
            "parameters": {"node_name": "ip-10-0-14-88.ec2.internal"}
        },
        {
            "id": "task-1012",
            "correlation_id": "EXEC-9810",
            "identifier": "os-windows-wsus-reboot",
            "name": "Windows Server 2022 WSUS Update & Safe Reboot",
            "engine": "ansible",
            "category": "os_patching",
            "target_resource": "win-ad-dc-02.corp",
            "environment": "PROD",
            "status": "PENDING_APPROVAL",
            "risk_tier": "HIGH",
            "requester_id": "sysadmin-bot",
            "approver_id": None,
            "duration_sec": 0,
            "created_at": "2026-09-06T04:00:10Z",
            "parameters": {"target_host": "win-ad-dc-02.corp", "reboot_timeout_sec": 600}
        },
        {
            "id": "task-1013",
            "correlation_id": "EXEC-9809",
            "identifier": "sec-trufflehog-git-scan",
            "name": "TruffleHog Real-Time Secrets & Credential Leak Scan",
            "engine": "ansible",
            "category": "security",
            "target_resource": "git@github.com:enterprise/payments-api.git",
            "environment": "DEV",
            "status": "SUCCESS",
            "risk_tier": "LOW",
            "requester_id": "sec-scanner",
            "approver_id": None,
            "duration_sec": 38,
            "created_at": "2026-09-06T03:20:00Z",
            "parameters": {"repo_url": "git@github.com:enterprise/payments-api.git"}
        },
        {
            "id": "task-1014",
            "correlation_id": "EXEC-9808",
            "identifier": "net-paloalto-fw-rule-push",
            "name": "Palo Alto PAN-OS Security Policy Rule Add",
            "engine": "ansible",
            "category": "network",
            "target_resource": "panorama-prod-01",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "HIGH",
            "requester_id": "jason.neteng",
            "approver_id": "lead.bob",
            "duration_sec": 195,
            "created_at": "2026-09-06T02:40:00Z",
            "parameters": {"rule_name": "ALLOW-APP-TO-DB", "source_zone": "Trust-App", "destination_zone": "DB-Tier"}
        },
        {
            "id": "task-1015",
            "correlation_id": "EXEC-9807",
            "identifier": "cloud-azure-vnet-gateway",
            "name": "Azure ExpressRoute Virtual Network Gateway Sync",
            "engine": "terraform",
            "category": "cloud",
            "target_resource": "gw-er-prod-01",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "HIGH",
            "requester_id": "david.cloudops",
            "approver_id": "lead.bob",
            "duration_sec": 520,
            "created_at": "2026-09-06T02:10:00Z",
            "parameters": {"resource_group": "rg-enterprise-network-eastus", "gateway_name": "gw-er-prod-01"}
        },
        {
            "id": "task-1016",
            "correlation_id": "EXEC-9806",
            "identifier": "db-mysql-read-replica-add",
            "name": "MySQL Read Replica Provisioning",
            "engine": "terraform",
            "category": "database",
            "target_resource": "db-mysql-prod-01",
            "environment": "PROD",
            "status": "RUNNING",
            "risk_tier": "HIGH",
            "requester_id": "priya.dba",
            "approver_id": "lead.bob",
            "duration_sec": 115,
            "created_at": "2026-09-06T01:45:00Z",
            "parameters": {"primary_instance_id": "db-mysql-prod-01", "replica_instance_type": "db.r6g.2xlarge"}
        },
        {
            "id": "task-1017",
            "correlation_id": "EXEC-9805",
            "identifier": "net-cisco-vlan-trunk-update",
            "name": "Cisco Catalyst VLAN Trunk Configuration",
            "engine": "ansible",
            "category": "network",
            "target_resource": "sw-tor-01.rack4",
            "environment": "DEV",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "jason.neteng",
            "approver_id": None,
            "duration_sec": 42,
            "created_at": "2026-09-06T01:15:00Z",
            "parameters": {"switch_host": "sw-tor-01.rack4", "port_channel": "Po10", "vlan_id": 104}
        },
        {
            "id": "task-1018",
            "correlation_id": "EXEC-9804",
            "identifier": "os-ubuntu-cve-hotpatch",
            "name": "Ubuntu Canonical Livepatch Fleet Sync",
            "engine": "ansible",
            "category": "os_patching",
            "target_resource": "tag_role_worker_staging",
            "environment": "STAGING",
            "status": "SUCCESS",
            "risk_tier": "LOW",
            "requester_id": "marcus.sre",
            "approver_id": None,
            "duration_sec": 65,
            "created_at": "2026-09-06T00:50:00Z",
            "parameters": {"target_fleet": "tag_role_worker_staging"}
        },
        {
            "id": "task-1019",
            "correlation_id": "EXEC-9803",
            "identifier": "k8s-namespace-quota-provision",
            "name": "Kubernetes Tenant Namespace & ResourceQuota Deploy",
            "engine": "terraform",
            "category": "kubernetes",
            "target_resource": "team-payments-staging",
            "environment": "STAGING",
            "status": "SUCCESS",
            "risk_tier": "LOW",
            "requester_id": "alex.engineer",
            "approver_id": None,
            "duration_sec": 34,
            "created_at": "2026-09-06T00:20:00Z",
            "parameters": {"namespace": "team-payments-staging", "cpu_limit_cores": 64, "memory_limit_gi": 256}
        },
        {
            "id": "task-1020",
            "correlation_id": "EXEC-9802",
            "identifier": "cloud-gcp-cloudnat-ips",
            "name": "GCP Cloud NAT Static Egress IP Pool Expansion",
            "engine": "terraform",
            "category": "cloud",
            "target_resource": "nat-gke-egress",
            "environment": "UAT",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "david.cloudops",
            "approver_id": None,
            "duration_sec": 88,
            "created_at": "2026-09-05T23:45:00Z",
            "parameters": {"router_name": "rtr-gke-prod", "nat_name": "nat-gke-egress", "additional_ips_count": 2}
        },
        {
            "id": "task-1021",
            "correlation_id": "EXEC-9801",
            "identifier": "sec-vault-approle-renew",
            "name": "HashiCorp Vault AppRole SecretID Renewal",
            "engine": "ansible",
            "category": "security",
            "target_resource": "app-trade-settlement",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "sec-ops-bot",
            "approver_id": None,
            "duration_sec": 22,
            "created_at": "2026-09-05T23:10:00Z",
            "parameters": {"role_name": "app-trade-settlement"}
        },
        {
            "id": "task-1022",
            "correlation_id": "EXEC-9800",
            "identifier": "net-f5-pool-member-drain",
            "name": "F5 BIG-IP Pool Member Graceful Drain",
            "engine": "ansible",
            "category": "network",
            "target_resource": "pool_web_app_prod",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "jason.neteng",
            "approver_id": None,
            "duration_sec": 125,
            "created_at": "2026-09-05T22:30:00Z",
            "parameters": {"pool_name": "pool_web_app_prod", "member_ip": "10.100.2.14", "member_port": 8443}
        },
        {
            "id": "task-1023",
            "correlation_id": "EXEC-9799",
            "identifier": "os-selinux-enforce-audit",
            "name": "SELinux Enforcing Mode Remediation",
            "engine": "ansible",
            "category": "os_patching",
            "target_resource": "sec-gateway-prod.internal",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "marcus.sre",
            "approver_id": None,
            "duration_sec": 71,
            "created_at": "2026-09-05T21:50:00Z",
            "parameters": {"target_host": "sec-gateway-prod.internal"}
        },
        {
            "id": "task-1024",
            "correlation_id": "EXEC-9798",
            "identifier": "cloud-aws-waf-ip-rate-limit",
            "name": "AWS WAF v2 IP Rate Limiting Rule Deployment",
            "engine": "terraform",
            "category": "cloud",
            "target_resource": "waf-api-perimeter-prod",
            "environment": "PROD",
            "status": "SUCCESS",
            "risk_tier": "LOW",
            "requester_id": "david.cloudops",
            "approver_id": None,
            "duration_sec": 49,
            "created_at": "2026-09-05T21:15:00Z",
            "parameters": {"web_acl_name": "waf-api-perimeter-prod", "rate_limit": 2000}
        },
        {
            "id": "task-1025",
            "correlation_id": "EXEC-9797",
            "identifier": "db-redis-cluster-reshard",
            "name": "Redis Cluster Hash Slot Live Resharding",
            "engine": "ansible",
            "category": "database",
            "target_resource": "node-redis-03",
            "environment": "UAT",
            "status": "SUCCESS",
            "risk_tier": "HIGH",
            "requester_id": "priya.dba",
            "approver_id": "lead.bob",
            "duration_sec": 190,
            "created_at": "2026-09-05T20:30:00Z",
            "parameters": {"source_node_id": "node-redis-03", "target_node_id": "node-redis-05", "slots_count": 500}
        },
        {
            "id": "task-1026",
            "correlation_id": "EXEC-9796",
            "identifier": "k8s-cert-manager-clusterissuer",
            "name": "Kubernetes cert-manager Vault ClusterIssuer Sync",
            "engine": "terraform",
            "category": "kubernetes",
            "target_resource": "k8s-prod-useast1",
            "environment": "DEV",
            "status": "SUCCESS",
            "risk_tier": "LOW",
            "requester_id": "alex.engineer",
            "approver_id": None,
            "duration_sec": 30,
            "created_at": "2026-09-05T19:40:00Z",
            "parameters": {"vault_server_url": "https://vault.internal:8200", "pki_mount_path": "pki_internal"}
        },
        {
            "id": "task-1027",
            "correlation_id": "EXEC-9795",
            "identifier": "sec-cis-benchmark-remediate",
            "name": "CIS Linux Level 2 Benchmark Automated Remediation",
            "engine": "ansible",
            "category": "security",
            "target_resource": "rhel-bastion-01.internal",
            "environment": "PROD",
            "status": "FAILED",
            "risk_tier": "HIGH",
            "requester_id": "sec-ops-bot",
            "approver_id": "sarah.lead",
            "duration_sec": 140,
            "created_at": "2026-09-05T18:50:00Z",
            "error_message": "Audit remediation failed: GRUB bootloader password encryption lock verification timed out.",
            "parameters": {"target_host": "rhel-bastion-01.internal"}
        },
        {
            "id": "task-1028",
            "correlation_id": "EXEC-9794",
            "identifier": "net-dns-bind-zone-reload",
            "name": "BIND9 / Infoblox Internal DNS Zone Update",
            "engine": "ansible",
            "category": "network",
            "target_resource": "internal.corp",
            "environment": "DEV",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "jason.neteng",
            "approver_id": None,
            "duration_sec": 18,
            "created_at": "2026-09-05T18:00:00Z",
            "parameters": {"zone": "internal.corp", "record_name": "api-gateway", "record_type": "A", "record_value": "10.150.12.8"}
        },
        {
            "id": "task-1029",
            "correlation_id": "EXEC-9793",
            "identifier": "os-systemd-daemon-reload",
            "name": "Systemd Daemon Reload & Unit Service Restart",
            "engine": "ansible",
            "category": "os_patching",
            "target_resource": "app-backend-01.internal",
            "environment": "UAT",
            "status": "SUCCESS",
            "risk_tier": "LOW",
            "requester_id": "alex.engineer",
            "approver_id": None,
            "duration_sec": 14,
            "created_at": "2026-09-05T17:20:00Z",
            "parameters": {"target_host": "app-backend-01.internal", "unit_name": "payment-worker.service"}
        },
        {
            "id": "task-1030",
            "correlation_id": "EXEC-9792",
            "identifier": "k8s-daemonset-rolling-restart",
            "name": "Kubernetes DaemonSet Rolling Restart",
            "engine": "ansible",
            "category": "kubernetes",
            "target_resource": "fluent-bit-logging",
            "environment": "STAGING",
            "status": "SUCCESS",
            "risk_tier": "MEDIUM",
            "requester_id": "marcus.sre",
            "approver_id": None,
            "duration_sec": 92,
            "created_at": "2026-09-05T16:45:00Z",
            "parameters": {"daemonset_name": "fluent-bit-logging", "namespace": "monitoring"}
        }
    ]
