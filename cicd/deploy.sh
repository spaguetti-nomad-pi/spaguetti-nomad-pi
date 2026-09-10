#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/load-env.sh"

SRC=$REPO_ROOT
DEST=$DEPLOY_DIR

mkdir -p "$DEST"
SRC_REAL=$(realpath "$SRC")
DEST_REAL=$(realpath "$DEST")

if [[ $SRC_REAL != "$DEST_REAL" ]]; then
  rsync -a --delete \
    --exclude "cicd/deploy.env" \
    --exclude "apps/wifi-fallback/wifi-fallback.env" \
    --exclude "apps/telegram/telegram.env" \
    "$SRC_REAL/" "$DEST_REAL/"
fi

echo "Deployed $SRC_REAL → $DEST_REAL"
sudo "$DEST_REAL/apps/install.sh"
sudo apps up
