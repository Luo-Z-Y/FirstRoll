#!/usr/bin/env bash
# Prepare a fresh Ubuntu 24.04 server for the FirstRoll single-server stack.
#
# Run once as root from a copy of this directory, for example:
#   scp -r infra/vps root@SERVER:/root/firstroll-vps
#   ssh root@SERVER 'FIRSTROLL_DEPLOY_PUBLIC_KEY="ssh-ed25519 AAAA... github-actions" bash /root/firstroll-vps/bootstrap.sh'
#
# The script is idempotent: rerunning it refreshes packages and stack files but keeps an
# existing /opt/firstroll/.env and any published release.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "bootstrap.sh must run as root." >&2
  exit 1
fi

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
service_user=${FIRSTROLL_SERVICE_USER:-firstroll}
install_root=${FIRSTROLL_INSTALL_ROOT:-/opt/firstroll}
export DEBIAN_FRONTEND=noninteractive

for required in docker-compose.yml Caddyfile deploy.sh .env.example; do
  if [ ! -f "$script_dir/$required" ]; then
    echo "bootstrap.sh expects $required next to it." >&2
    exit 1
  fi
done

echo "==> Installing packages"
apt-get update -q
apt-get -y -q dist-upgrade
apt-get -y -q install --no-install-recommends \
  ca-certificates curl ufw unattended-upgrades docker.io docker-compose-v2

echo "==> Configuring Docker log rotation"
install -d -m 0755 /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
systemctl enable --now docker
systemctl restart docker

echo "==> Creating the service account"
if ! id "$service_user" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "FirstRoll service" "$service_user"
fi
# Membership of the docker group is equivalent to root on this host. The account exists so
# that GitHub Actions never logs in as root, not to contain a compromised deploy key.
usermod -aG docker "$service_user"
ssh_dir="/home/$service_user/.ssh"
auth_keys="$ssh_dir/authorized_keys"
install -d -m 0700 -o "$service_user" -g "$service_user" "$ssh_dir"
touch "$auth_keys"
if [ -f /root/.ssh/authorized_keys ]; then
  cat /root/.ssh/authorized_keys >> "$auth_keys"
fi
if [ -n "${FIRSTROLL_DEPLOY_PUBLIC_KEY:-}" ]; then
  printf '%s\n' "$FIRSTROLL_DEPLOY_PUBLIC_KEY" >> "$auth_keys"
fi
sort -u -o "$auth_keys" "$auth_keys"
chmod 0600 "$auth_keys"
chown "$service_user:$service_user" "$auth_keys"

echo "==> Installing stack files into $install_root"
install -d -m 0755 -o "$service_user" -g "$service_user" \
  "$install_root" "$install_root/releases" "$install_root/state" "$install_root/incoming"
install -m 0644 -o "$service_user" -g "$service_user" \
  "$script_dir/docker-compose.yml" "$script_dir/Caddyfile" "$install_root/"
install -m 0755 -o "$service_user" -g "$service_user" "$script_dir/deploy.sh" "$install_root/deploy.sh"
if [ ! -f "$install_root/.env" ]; then
  install -m 0600 -o "$service_user" -g "$service_user" "$script_dir/.env.example" "$install_root/.env"
  env_created=true
else
  env_created=false
fi
if [ ! -e "$install_root/releases/current" ]; then
  placeholder="$install_root/releases/site-bootstrap"
  install -d -m 0755 -o "$service_user" -g "$service_user" "$placeholder"
  cat > "$placeholder/index.html" <<'HTML'
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>FirstRoll</title></head>
<body><p>FirstRoll is being set up on this server. The first release has not been published yet.</p></body>
</html>
HTML
  chown "$service_user:$service_user" "$placeholder/index.html"
  ln -s site-bootstrap "$install_root/releases/current"
  chown -h "$service_user:$service_user" "$install_root/releases/current"
fi

echo "==> Adding swap on small servers"
total_kb=$(awk '/MemTotal/ { print $2 }' /proc/meminfo)
if [ "$total_kb" -lt 1900000 ] && ! swapon --show --noheadings | grep -q .; then
  fallocate -l 1G /swapfile
  chmod 0600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  printf 'vm.swappiness=10\n' > /etc/sysctl.d/60-firstroll-swap.conf
  sysctl -q -p /etc/sysctl.d/60-firstroll-swap.conf
fi

echo "==> Configuring the firewall"
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw allow 443/udp >/dev/null
ufw --force enable >/dev/null

echo "==> Enabling automatic security updates"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF

if [ -s "$auth_keys" ]; then
  echo "==> Restricting SSH to key authentication"
  cat > /etc/ssh/sshd_config.d/60-firstroll.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
CONF
  # Ubuntu may leave only ssh.socket running after an OpenSSH upgrade. Starting the
  # service recreates its systemd-managed /run/sshd before the standalone syntax check.
  # This is a no-op when already active and does not restart established sessions.
  systemctl start ssh
  sshd -t
  systemctl reload ssh
else
  echo "No SSH keys were found; password authentication was left enabled." >&2
fi

host_key=$(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)

cat <<SUMMARY

Bootstrap complete.

Service account:      $service_user (docker group)
Stack directory:      $install_root
Environment file:     $install_root/.env ($([ "$env_created" = true ] && echo "created from template; edit it now" || echo "kept"))

GitHub repository variable VPS_SSH_HOST_KEY (pinned server identity):
  $host_key

Next steps:
  1. Edit $install_root/.env: set CADDY_ACME_EMAIL and any provider keys. Keep mode 0600.
  2. Point the site and API DNS records at this server, then start Caddy so it can obtain
     certificates before the first release:
       sudo -u $service_user docker compose --project-directory $install_root up -d --no-deps caddy
  3. Configure the GitHub production environment and run the VPS Release workflow. It uploads
     and executes $install_root/deploy.sh for each approved release.
SUMMARY
