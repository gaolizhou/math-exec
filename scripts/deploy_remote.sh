#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
APP_NAME="math-exec"
REMOTE_BASE_DIR="/opt/${APP_NAME}"
HOST=""
SSH_USER="root"
PASSWORD="${DEPLOY_PASSWORD:-}"
SSH_PORT="22"
NEW_SSH_PORT="2222"
PUBLIC_HOST=""
LE_EMAIL=""
IMAGE_NAME="${APP_NAME}:latest"
CONTAINER_NAME="${APP_NAME}"
APP_PORT="6000"
HTTPS_MODE="letsencrypt"
TMP_BUNDLE=""

usage() {
  cat <<EOF
用法:
  bash scripts/deploy_remote.sh \
    --host 114.215.179.221 \
    --user root \
    --password 'lab123lab123' \
    --ssh-port 22 \
    --new-ssh-port 2222 \
    --public-host 114.215.179.221

可选参数:
  --email you@example.com   Let's Encrypt 账号邮箱，可留空
  --https-mode letsencrypt|self-signed|http-only
EOF
}

log() {
  printf '==> %s\n' "$*"
}

cleanup() {
  if [[ -n "$TMP_BUNDLE" && -f "$TMP_BUNDLE" ]]; then
    rm -f "$TMP_BUNDLE"
  fi
}
trap cleanup EXIT

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "缺少命令: $cmd" >&2
    exit 1
  fi
}

shell_quote() {
  python3 -c 'import shlex, sys; print(shlex.quote(sys.argv[1]))' "$1"
}

run_expect() {
  local raw_cmd="$1"
  CMD="$raw_cmd" SSHPASS="$PASSWORD" expect <<'EOF'
set timeout -1
set cmd $env(CMD)
set password $env(SSHPASS)
spawn bash -lc $cmd
expect {
  -re {yes/no} {
    send "yes\r"
    exp_continue
  }
  -re {[Pp]assword:} {
    send "$password\r"
    exp_continue
  }
  eof
}
catch wait result
set exit_code [lindex $result 3]
exit $exit_code
EOF
}

ssh_exec() {
  local port="$1"
  local remote_cmd="$2"
  local quoted_remote_cmd
  quoted_remote_cmd=$(shell_quote "$remote_cmd")
  run_expect "ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$HOME/.ssh/known_hosts -p ${port} ${SSH_USER}@${HOST} ${quoted_remote_cmd}"
}

scp_upload() {
  local port="$1"
  local local_path="$2"
  local remote_path="$3"
  local quoted_local_path quoted_remote_target
  quoted_local_path=$(shell_quote "$local_path")
  quoted_remote_target=$(shell_quote "${SSH_USER}@${HOST}:${remote_path}")
  run_expect "scp -P ${port} -o StrictHostKeyChecking=accept-new ${quoted_local_path} ${quoted_remote_target}"
}

build_bundle() {
  TMP_BUNDLE="/tmp/${APP_NAME}-$(date +%Y%m%d%H%M%S).tar.gz"
  tar \
    --exclude='.git' \
    --exclude='.codebuddy' \
    --exclude='agency-agents-src' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pdf' \
    --exclude='.DS_Store' \
    -czf "$TMP_BUNDLE" \
    -C "$ROOT_DIR" .
}

verify_ssh_port() {
  local port="$1"
  run_expect "ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$HOME/.ssh/known_hosts -p ${port} ${SSH_USER}@${HOST} 'echo ok'" >/dev/null 2>&1
}

access_scheme() {
  if [[ "$HTTPS_MODE" == "http-only" ]]; then
    echo http
  else
    echo https
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host)
        HOST="$2"
        shift 2
        ;;
      --user)
        SSH_USER="$2"
        shift 2
        ;;
      --password)
        PASSWORD="$2"
        shift 2
        ;;
      --ssh-port)
        SSH_PORT="$2"
        shift 2
        ;;
      --new-ssh-port)
        NEW_SSH_PORT="$2"
        shift 2
        ;;
      --public-host)
        PUBLIC_HOST="$2"
        shift 2
        ;;
      --email)
        LE_EMAIL="$2"
        shift 2
        ;;
      --https-mode)
        HTTPS_MODE="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "未知参数: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  if [[ -z "$HOST" || -z "$PASSWORD" ]]; then
    usage
    exit 1
  fi

  if [[ -z "$PUBLIC_HOST" ]]; then
    PUBLIC_HOST="$HOST"
  fi
}

main() {
  parse_args "$@"

  require_cmd expect
  require_cmd python3
  require_cmd tar
  require_cmd ssh
  require_cmd scp

  build_bundle

  local remote_bundle="/tmp/${APP_NAME}-bundle.tar.gz"

  log "上传部署包到远端"
  ssh_exec "$SSH_PORT" "mkdir -p ${REMOTE_BASE_DIR} ${REMOTE_BASE_DIR}/data"
  scp_upload "$SSH_PORT" "$TMP_BUNDLE" "$remote_bundle"

  log "解压代码到远端"
  ssh_exec "$SSH_PORT" "rm -rf ${REMOTE_BASE_DIR}/app && mkdir -p ${REMOTE_BASE_DIR}/app && tar xzf ${remote_bundle} -C ${REMOTE_BASE_DIR}/app && chmod +x ${REMOTE_BASE_DIR}/app/scripts/*.sh && rm -f ${remote_bundle}"

  log "执行远端部署"
  ssh_exec "$SSH_PORT" "APP_NAME=${APP_NAME} APP_DIR=${REMOTE_BASE_DIR}/app DATA_DIR=${REMOTE_BASE_DIR}/data CONTAINER_NAME=${CONTAINER_NAME} IMAGE_NAME=${IMAGE_NAME} APP_PORT=${APP_PORT} PUBLIC_HOST=${PUBLIC_HOST} LE_EMAIL=${LE_EMAIL} HTTPS_MODE=${HTTPS_MODE} CURRENT_SSH_PORT=${SSH_PORT} NEW_SSH_PORT=${NEW_SSH_PORT} DEPLOY_PHASE=full ${REMOTE_BASE_DIR}/app/scripts/remote_server_setup.sh"

  local active_ssh_port="$SSH_PORT"
  if [[ "$SSH_PORT" == "$NEW_SSH_PORT" ]]; then
    log "当前 SSH 端口与目标端口相同，跳过旧端口关闭步骤。"
    active_ssh_port="$NEW_SSH_PORT"
  elif verify_ssh_port "$NEW_SSH_PORT"; then
    log "已验证新的 SSH 端口 ${NEW_SSH_PORT} 可用，开始关闭旧端口 ${SSH_PORT}"
    ssh_exec "$NEW_SSH_PORT" "PUBLIC_HOST=${PUBLIC_HOST} HTTPS_MODE=${HTTPS_MODE} CURRENT_SSH_PORT=${SSH_PORT} NEW_SSH_PORT=${NEW_SSH_PORT} DEPLOY_PHASE=finalize-ssh ${REMOTE_BASE_DIR}/app/scripts/remote_server_setup.sh"
    active_ssh_port="$NEW_SSH_PORT"
  else
    log "未能从外部验证 SSH 新端口 ${NEW_SSH_PORT}，已保留旧端口 ${SSH_PORT} 作为回退。"
  fi

  printf '\n部署完成。\n'
  printf '访问地址: %s://%s\n' "$(access_scheme)" "$PUBLIC_HOST"
  printf 'SSH 端口: %s\n' "$active_ssh_port"
}

main "$@"
