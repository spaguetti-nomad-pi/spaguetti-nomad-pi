#!/usr/bin/env bash
# Apps catalog. Enabled names live in /etc/apps/enabled (not git).
set -euo pipefail

ETC=/etc/apps
if [[ -f $ETC/dir ]]; then
  ROOT=$(cat "$ETC/dir")
else
  ROOT=$(cd "$(dirname "$0")" && pwd)
fi
ENABLED=$ETC/enabled

usage() {
  echo "usage: apps status|up|down|logs|enable|disable [name]" >&2
  exit 1
}

enabled_list() {
  [[ -f $ENABLED ]] || return 0
  awk '/^[^#[:space:]]/ {print $1}' "$ENABLED"
}

is_enabled() {
  enabled_list | grep -qx "$1"
}

app_dir() {
  printf '%s/%s\n' "$ROOT" "$1"
}

require_app() {
  local name=$1
  [[ -n $name ]] || usage
  [[ -d $(app_dir "$name") ]] || {
    echo "unknown app: $name" >&2
    exit 1
  }
}

load_conf() {
  NEEDS_VAULT=0
  UNIT=
  # shellcheck disable=SC1091
  [[ -f $1/app.conf ]] && source "$1/app.conf"
}

vault_ok() {
  mountpoint -q /vault 2>/dev/null
}

unit_state() {
  local s
  s=$(systemctl is-active "$1" 2>/dev/null || true)
  echo "${s:-unknown}"
}

compose() {
  local name=$1
  shift
  docker compose --project-name "$name" -f "$(app_dir "$name")/compose.yml" "$@"
}

cmd_status() {
  local name dir n
  if vault_ok; then
    echo "vault mounted"
  else
    echo "vault locked"
  fi
  echo "apps:"
  if [[ -z $(enabled_list) ]]; then
    echo "  (none enabled)"
    return
  fi
  while read -r name; do
    [[ -n $name ]] || continue
    dir=$(app_dir "$name")
    if [[ ! -d $dir ]]; then
      echo "  $name missing"
      continue
    fi
    load_conf "$dir"
    if [[ -n ${UNIT:-} ]]; then
      echo "  $name $(unit_state "$UNIT")"
    elif [[ -f $dir/compose.yml ]] && command -v docker >/dev/null; then
      n=$(compose "$name" ps -q 2>/dev/null | wc -l | tr -d ' ')
      echo "  $name containers:$n"
    else
      echo "  $name enabled"
    fi
  done < <(enabled_list)
}

cmd_enable() {
  local name=${1:-}
  require_app "$name"
  mkdir -p "$ETC"
  touch "$ENABLED"
  if is_enabled "$name"; then
    echo "$name already enabled"
    return
  fi
  echo "$name" >> "$ENABLED"
  echo "enabled $name"
}

cmd_disable() {
  local name=${1:-} tmp
  require_app "$name"
  [[ -f $ENABLED ]] || return 0
  tmp=$(mktemp)
  awk -v n="$name" '$1!=n {print}' "$ENABLED" > "$tmp"
  cat "$tmp" > "$ENABLED"
  rm -f "$tmp"
  echo "disabled $name"
}

bring_up() {
  local name=$1 dir
  dir=$(app_dir "$name")
  load_conf "$dir"
  if [[ ${NEEDS_VAULT:-0} == 1 ]] && ! vault_ok; then
    echo "$name: vault locked" >&2
    return 1
  fi
  if [[ -x $dir/install.sh ]]; then
    "$dir/install.sh"
  fi
  if [[ -f $dir/compose.yml ]]; then
    compose "$name" up -d
  fi
}

bring_down() {
  local name=$1 dir
  dir=$(app_dir "$name")
  load_conf "$dir"
  if [[ -n ${UNIT:-} ]]; then
    systemctl stop "$UNIT" 2>/dev/null || true
  fi
  if [[ -f $dir/compose.yml ]] && command -v docker >/dev/null; then
    compose "$name" down
  fi
}

each_enabled() {
  local only=${1:-} name
  if [[ -n $only ]]; then
    require_app "$only"
    is_enabled "$only" || {
      echo "$only is not enabled" >&2
      exit 1
    }
    printf '%s\n' "$only"
    return
  fi
  enabled_list
}

cmd_up() {
  local name
  while read -r name; do
    [[ -n $name ]] || continue
    bring_up "$name"
  done < <(each_enabled "${1:-}")
}

cmd_down() {
  local name
  while read -r name; do
    [[ -n $name ]] || continue
    bring_down "$name"
  done < <(each_enabled "${1:-}")
}

cmd_logs() {
  local name=${1:-} dir
  require_app "$name"
  dir=$(app_dir "$name")
  load_conf "$dir"
  if [[ -n ${UNIT:-} ]]; then
    journalctl -u "$UNIT" -n 80 --no-pager
    return
  fi
  compose "$name" logs --tail 80
}

case ${1:-status} in
  status) cmd_status ;;
  enable) cmd_enable "${2:-}" ;;
  disable) cmd_disable "${2:-}" ;;
  up) cmd_up "${2:-}" ;;
  down) cmd_down "${2:-}" ;;
  logs) cmd_logs "${2:-}" ;;
  *) usage ;;
esac
