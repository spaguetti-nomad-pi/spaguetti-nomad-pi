#!/usr/bin/env bash
# One-time: register THIS Pi as a runner on YOUR GitHub repo.
# Usage: ./cicd/install-runner.sh <registration-token>
set -euo pipefail

if [[ ${EUID} -eq 0 ]]; then
  echo "Run as the deploy user, not root." >&2
  exit 1
fi

TOKEN=${1:-${RUNNER_TOKEN:-}}
if [[ -z $TOKEN ]]; then
  echo "GitHub → your repo → Settings → Actions → Runners → New self-hosted runner" >&2
  echo "Usage: $0 <registration-token>" >&2
  exit 1
fi

CICD_DIR=$(cd "$(dirname "$0")" && pwd)
if [[ ! -f $CICD_DIR/deploy.env ]]; then
  cp "$CICD_DIR/deploy.env.example" "$CICD_DIR/deploy.env"
  echo "Created cicd/deploy.env from the example. Edit it anytime (DEPLOY_DIR, REPO_URL)."
fi

# shellcheck disable=SC1091
source "$CICD_DIR/load-env.sh"

if [[ -z $REPO_URL ]]; then
  echo "Set REPO_URL in cicd/deploy.env (your fork) or add a git remote named origin." >&2
  exit 1
fi

if [[ $(_cicd_norm_repo_url "$REPO_URL") == $(_cicd_norm_repo_url "$UPSTREAM_REPO_URL") ]]; then
  echo "Do not register a runner on upstream ($UPSTREAM_REPO_URL)." >&2
  echo "Fork it, clone YOUR fork, then re-run this script." >&2
  exit 1
fi

mkdir -p "$HOME/.config/raspi"
install -m 0600 "$CICD_DIR/deploy.env" "$HOME/.config/raspi/deploy.env"

case $(uname -m) in
  aarch64 | arm64) ARCH=arm64 ;;
  x86_64) ARCH=x64 ;;
  *)
    echo "Unsupported arch: $(uname -m)" >&2
    exit 1
    ;;
esac

sudo apt-get update -qq
sudo apt-get install -y -qq git rsync curl python3
sudo apt-get install -y -qq libicu72 2>/dev/null || sudo apt-get install -y -qq libicu76 2>/dev/null || true

VER=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
TARBALL="actions-runner-linux-${ARCH}-${VER}.tar.gz"

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"
if [[ ! -x ./config.sh ]]; then
  curl -fsSL -o "$TARBALL" "https://github.com/actions/runner/releases/download/v${VER}/${TARBALL}"
  tar xzf "$TARBALL"
  rm -f "$TARBALL"
fi

./config.sh --unattended --replace \
  --url "$REPO_URL" \
  --token "$TOKEN" \
  --name "$RUNNER_NAME" \
  --labels "$RUNNER_LABEL"

sudo tee /etc/sudoers.d/raspi-ci >/dev/null <<EOF
$USER ALL=(ALL) NOPASSWD: ALL
EOF
sudo chmod 440 /etc/sudoers.d/raspi-ci

sudo ./svc.sh install "$USER"
sudo ./svc.sh start

echo
echo "Runner '$RUNNER_NAME' online for $REPO_URL (label: $RUNNER_LABEL)."
echo "Deploys land in $DEPLOY_DIR."
