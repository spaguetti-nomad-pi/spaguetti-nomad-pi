#!/usr/bin/env bash
# hostname, load, memory, disk, SoC temp
set -u
host=$(hostname -s 2>/dev/null || hostname)
load=$(awk '{print $1, $2, $3}' /proc/loadavg)
mins=$(awk '{printf "%d", $1/60}' /proc/uptime)
mem=$(free -m | awk '/^Mem:/{printf "%s/%s MB", $3, $2}')
disk=$(df -h / | awk 'NR==2{printf "%s used of %s (%s)", $3, $2, $5}')
echo "$host"
echo "up ${mins} min  load $load"
echo "mem $mem"
echo "disk $disk"
if [[ -r /sys/class/thermal/thermal_zone0/temp ]]; then
  awk '{printf "temp %.1f C\n", $1/1000}' /sys/class/thermal/thermal_zone0/temp
fi
