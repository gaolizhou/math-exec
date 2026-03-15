#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME=${APP_NAME:-math-exec}
APP_DIR=${APP_DIR:-/opt/${APP_NAME}/app}
DATA_DIR=${DATA_DIR:-/opt/${APP_NAME}/data}
CONTAINER_NAME=${CONTAINER_NAME:-${APP_NAME}}
IMAGE_NAME=${IMAGE_NAME:-${APP_NAME}:latest}
APP_PORT=${APP_PORT:-6000}
PUBLIC_HOST=${PUBLIC_HOST:?PUBLIC_HOST is required}
LE_EMAIL=${LE_EMAIL:-}
CURRENT_SSH_PORT=${CURRENT_SSH_PORT:-22}
NEW_SSH_PORT=${NEW_SSH_PORT:-2222}
DEPLOY_PHASE=${DEPLOY_PHASE:-full}
HTTPS_MODE=${HTTPS_MODE:-letsencrypt}
ACME_WWWROOT=${ACME_WWWROOT:-/var/www/acme}
LEGO_BIN=${LEGO_BIN:-/usr/local/bin/lego}
LEGO_PATH=${LEGO_PATH:-/var/lib/lego}
LEGO_VERSION=${LEGO_VERSION:-v4.32.0}
LEGO_DOWNLOAD_URL=${LEGO_DOWNLOAD_URL:-https://github.com/go-acme/lego/releases/download/${LEGO_VERSION}/lego_${LEGO_VERSION}_linux_amd64.tar.gz}
NGINX_SSL_DIR=${NGINX_SSL_DIR:-/etc/nginx/ssl/${APP_NAME}}
NGINX_CONF=${NGINX_CONF:-/etc/nginx/conf.d/${APP_NAME}.conf}

log() {
  printf '==> %s\n' "$*"
}

ensure_root() {
  if [[ ${EUID} -ne 0 ]]; then
    echo "This script must run as root." >&2
    exit 1
  fi
}

service_cmd() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl "$@"
  else
    service "$1" "$2"
  fi
}

restart_service() {
  local name="$1"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl restart "$name"
  else
    service "$name" restart
  fi
}

reload_service() {
  local name="$1"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl reload "$name"
  else
    service "$name" reload
  fi
}

restart_ssh_listener() {
  local ssh_service
  ssh_service=$(ssh_service_name)

  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
    if systemctl list-unit-files | grep -q '^ssh\.socket'; then
      systemctl disable --now ssh.socket || true
      systemctl mask ssh.socket || true
    fi
    systemctl enable --now "$ssh_service"
    systemctl restart "$ssh_service"
  else
    service "$ssh_service" restart
  fi
}

ssh_service_name() {
  if command -v systemctl >/dev/null 2>&1; then
    if systemctl list-unit-files | grep -q '^sshd\.service'; then
      echo sshd
      return
    fi
    if systemctl list-unit-files | grep -q '^ssh\.service'; then
      echo ssh
      return
    fi
  fi
  if command -v service >/dev/null 2>&1 && service ssh status >/dev/null 2>&1; then
    echo ssh
    return
  fi
  echo sshd
}

cron_service_name() {
  if command -v systemctl >/dev/null 2>&1; then
    if systemctl list-unit-files | grep -q '^cron\.service'; then
      echo cron
      return
    fi
    if systemctl list-unit-files | grep -q '^crond\.service'; then
      echo crond
      return
    fi
  fi
  echo cron
}

install_base_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y nginx curl socat ca-certificates openssl tar cron python3
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y nginx curl socat ca-certificates openssl tar cronie python3
  elif command -v yum >/dev/null 2>&1; then
    yum install -y epel-release || true
    yum install -y nginx curl socat ca-certificates openssl tar cronie python3
  else
    echo "Unsupported package manager." >&2
    exit 1
  fi
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    return
  fi
  log "Installing Docker"
  curl -fsSL https://get.docker.com | sh
}

enable_services() {
  local cron_service
  cron_service=$(cron_service_name)

  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now docker
    systemctl enable --now nginx
    systemctl enable --now "$cron_service"
  else
    service docker start || true
    service nginx start || true
    service "$cron_service" start || true
  fi
}

configure_firewall() {
  if command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --permanent --add-service=http || true
    if [[ "$HTTPS_MODE" == "http-only" ]]; then
      firewall-cmd --permanent --remove-service=https || true
    else
      firewall-cmd --permanent --add-service=https || true
    fi
    firewall-cmd --permanent --add-port="${NEW_SSH_PORT}/tcp" || true
    if [[ "${DEPLOY_PHASE}" == "finalize-ssh" ]]; then
      firewall-cmd --permanent --remove-port="${CURRENT_SSH_PORT}/tcp" || true
    fi
    firewall-cmd --reload || true
  elif command -v ufw >/dev/null 2>&1; then
    ufw allow 80/tcp || true
    if [[ "$HTTPS_MODE" == "http-only" ]]; then
      ufw delete allow 443/tcp || true
    else
      ufw allow 443/tcp || true
    fi
    ufw allow "${NEW_SSH_PORT}/tcp" || true
    if [[ "${DEPLOY_PHASE}" == "finalize-ssh" ]]; then
      ufw delete allow "${CURRENT_SSH_PORT}/tcp" || true
    fi
  fi
}

prepare_directories() {
  mkdir -p "$DATA_DIR" "$ACME_WWWROOT" "$NGINX_SSL_DIR" "$LEGO_PATH"
}

ensure_selinux_proxying() {
  if command -v getenforce >/dev/null 2>&1 && [[ $(getenforce) != "Disabled" ]]; then
    setsebool -P httpd_can_network_connect 1 || true
  fi
}

deploy_container() {
  log "Building Docker image"
  docker build -t "$IMAGE_NAME" "$APP_DIR"

  log "Replacing application container"
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "127.0.0.1:${APP_PORT}:6000" \
    -e PORT=6000 \
    -e SAVED_PRESETS_FILE=/app/data/saved_presets.json \
    -e PDF_CJK_FONT_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
    -e PDF_CJK_SUBFONT_INDEX=2 \
    -v "$DATA_DIR:/app/data" \
    "$IMAGE_NAME"

  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${APP_PORT}/" >/dev/null; then
      return
    fi
    sleep 2
  done

  docker logs "$CONTAINER_NAME" || true
  echo "Container health check failed." >&2
  return 1
}

write_http_nginx_config() {
  cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name ${PUBLIC_HOST};

    location ^~ /.well-known/acme-challenge/ {
        root ${ACME_WWWROOT};
        default_type "text/plain";
    }

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

  nginx -t
  reload_service nginx
}

install_lego() {
  if [[ -x "$LEGO_BIN" ]] && "$LEGO_BIN" run --help 2>/dev/null | grep -q -- '--profile value'; then
    return
  fi

  log "Installing Lego ${LEGO_VERSION}"
  local workdir
  workdir=$(mktemp -d)
  curl -fsSL -o "$workdir/lego.tar.gz" "$LEGO_DOWNLOAD_URL"
  tar -xzf "$workdir/lego.tar.gz" -C "$workdir"
  install -m 0755 "$workdir/lego" "$LEGO_BIN"
  rm -rf "$workdir"
}

install_certificate_files() {
  local cert_dir="$LEGO_PATH/certificates"
  cat "$cert_dir/${PUBLIC_HOST}.crt" "$cert_dir/${PUBLIC_HOST}.issuer.crt" > "$NGINX_SSL_DIR/fullchain.pem"
  cp "$cert_dir/${PUBLIC_HOST}.key" "$NGINX_SSL_DIR/${APP_NAME}.key"
  chmod 600 "$NGINX_SSL_DIR/${APP_NAME}.key"
}

issue_ip_certificate() {
  log "Issuing short-lived IP certificate from Let's Encrypt"
  local lego_email="${LE_EMAIL:-noreply@${APP_NAME}.invalid}"
  "$LEGO_BIN" \
    --accept-tos \
    --email "$lego_email" \
    --path "$LEGO_PATH" \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --domains "$PUBLIC_HOST" \
    --http \
    --http.webroot "$ACME_WWWROOT" \
    --profile shortlived \
    run
  install_certificate_files
}

install_renew_job() {
  local renew_script="/usr/local/bin/${APP_NAME}-renew.sh"
  cat > "$renew_script" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
${LEGO_BIN} \
  --accept-tos \
  --email "${LE_EMAIL:-noreply@${APP_NAME}.invalid}" \
  --path "${LEGO_PATH}" \
  --server https://acme-v02.api.letsencrypt.org/directory \
  --domains "${PUBLIC_HOST}" \
  --http \
  --http.webroot "${ACME_WWWROOT}" \
  --profile shortlived \
  renew --dynamic
cat "${LEGO_PATH}/certificates/${PUBLIC_HOST}.crt" "${LEGO_PATH}/certificates/${PUBLIC_HOST}.issuer.crt" > "${NGINX_SSL_DIR}/fullchain.pem"
cp "${LEGO_PATH}/certificates/${PUBLIC_HOST}.key" "${NGINX_SSL_DIR}/${APP_NAME}.key"
chmod 600 "${NGINX_SSL_DIR}/${APP_NAME}.key"
$(command -v systemctl >/dev/null 2>&1 && echo 'systemctl reload nginx' || echo 'service nginx reload')
EOF
  chmod +x "$renew_script"

  cat > "/etc/cron.d/${APP_NAME}-renew" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 */6 * * * root ${renew_script} >> /var/log/${APP_NAME}-renew.log 2>&1
EOF
}

remove_renew_job() {
  rm -f "/etc/cron.d/${APP_NAME}-renew" "/usr/local/bin/${APP_NAME}-renew.sh"
}

issue_self_signed_certificate() {
  log "Generating self-signed certificate for ${PUBLIC_HOST}"
  openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$NGINX_SSL_DIR/${APP_NAME}.key" \
    -out "$NGINX_SSL_DIR/fullchain.pem" \
    -days 365 \
    -subj "/CN=${PUBLIC_HOST}" \
    -addext "subjectAltName = IP:${PUBLIC_HOST}"
  chmod 600 "$NGINX_SSL_DIR/${APP_NAME}.key"
}

write_https_nginx_config() {
  cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name ${PUBLIC_HOST};

    location ^~ /.well-known/acme-challenge/ {
        root ${ACME_WWWROOT};
        default_type "text/plain";
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${PUBLIC_HOST};

    ssl_certificate ${NGINX_SSL_DIR}/fullchain.pem;
    ssl_certificate_key ${NGINX_SSL_DIR}/${APP_NAME}.key;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    client_max_body_size 16m;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
EOF

  nginx -t
  reload_service nginx
}

backup_sshd_config() {
  if [[ ! -f /etc/ssh/sshd_config.math-exec.bak ]]; then
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.math-exec.bak
  fi
}

rewrite_sshd_ports() {
  local port_lines="$1"
  PORT_LINES="$port_lines" python3 - <<'PY'
from pathlib import Path
import os

port_lines = os.environ.get("PORT_LINES", "").splitlines()
path = Path("/etc/ssh/sshd_config")
text = path.read_text(encoding="utf-8")
lines = text.splitlines()
filtered = [
    line for line in lines
    if not line.lstrip().startswith("Port ")
    and line.strip() != "# Managed by math-exec deploy"
]
managed_block = ["", "# Managed by math-exec deploy"] + [line for line in port_lines if line.strip()]
path.write_text("\n".join(filtered).rstrip() + "\n" + "\n".join(managed_block) + "\n", encoding="utf-8")
PY
}

stage_ssh_dual_port() {
  backup_sshd_config
  if [[ "$CURRENT_SSH_PORT" == "$NEW_SSH_PORT" ]]; then
    rewrite_sshd_ports "$(printf 'Port %s\n' "$NEW_SSH_PORT")"
  else
    rewrite_sshd_ports "$(printf 'Port %s\nPort %s\n' "$CURRENT_SSH_PORT" "$NEW_SSH_PORT")"
  fi
  sshd -t
  restart_ssh_listener
}

finalize_ssh_port() {
  backup_sshd_config
  rewrite_sshd_ports "$(printf 'Port %s\n' "$NEW_SSH_PORT")"
  sshd -t
  restart_ssh_listener
}

configure_web_stack() {
  write_http_nginx_config

  case "$HTTPS_MODE" in
    letsencrypt)
      install_lego
      issue_ip_certificate
      install_renew_job
      write_https_nginx_config
      ;;
    self-signed)
      remove_renew_job
      issue_self_signed_certificate
      write_https_nginx_config
      ;;
    http-only)
      remove_renew_job
      ;;
    *)
      echo "Unsupported HTTPS_MODE: $HTTPS_MODE" >&2
      exit 1
      ;;
  esac
}

run_full_deploy() {
  install_base_packages
  install_docker
  enable_services
  configure_firewall
  prepare_directories
  ensure_selinux_proxying
  deploy_container
  configure_web_stack
  stage_ssh_dual_port
}

run_reconfigure_web() {
  configure_firewall
  prepare_directories
  ensure_selinux_proxying
  configure_web_stack
}

run_finalize_ssh() {
  configure_firewall
  finalize_ssh_port
}

main() {
  ensure_root

  case "$DEPLOY_PHASE" in
    full)
      run_full_deploy
      ;;
    reconfigure-web)
      run_reconfigure_web
      ;;
    finalize-ssh)
      run_finalize_ssh
      ;;
    *)
      echo "Unsupported DEPLOY_PHASE: $DEPLOY_PHASE" >&2
      exit 1
      ;;
  esac
}

main "$@"
