#!/usr/bin/env bash
# pending apt upgrades (local cache, does not install)
set -u
mapfile -t pkgs < <(apt list --upgradable 2>/dev/null | awk -F/ 'NR>1 && $1 != "Listing..."{print $1}')
echo "${#pkgs[@]} upgradable"
((${#pkgs[@]})) || exit 0
printf '%s\n' "${pkgs[@]:0:25}"
((${#pkgs[@]} > 25)) && echo "…"
