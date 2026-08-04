#!/usr/bin/env bash
# Start RViz2 inside robot Docker and display via SSH X11 forwarding.
# 在机器人Docker容器内启动RViz2，并通过SSH X11转发到笔记本显示。
#
# Usage / 用法 (run on robot / 在机器人上执行):
#   ssh -X <robot_user>@<robot_ip>
#   cd ~/sdk_robot
#   ./examples/map_navigation/run_native_rviz.sh [path/to/config.rviz]

set -euo pipefail

IMAGE="zbl-registry.cn-shenzhen.cr.aliyuncs.com/xr/runtime/ex001:v00.02.06.02"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RVIZ_CONFIG="${1:-$SCRIPT_DIR/mapping.rviz}"

if [ -z "${DISPLAY:-}" ]; then
  echo "DISPLAY is not set. Run this from an 'ssh -X' (or -Y) session, not a plain SSH session." >&2
  exit 1
fi

if [ ! -f "$HOME/.Xauthority" ]; then
  echo "Warning: $HOME/.Xauthority not found; X11 auth may fail." >&2
fi

RVIZ_CONFIG_ARGS=()
if [ -f "$RVIZ_CONFIG" ]; then
  RVIZ_CONFIG_ARGS=(-v "$RVIZ_CONFIG:/tmp/rviz_config.rviz:ro")
  RVIZ_CMD="rviz2 -d /tmp/rviz_config.rviz"
else
  echo "rviz config not found at $RVIZ_CONFIG, launching rviz2 without a config." >&2
  RVIZ_CMD="rviz2"
fi

echo "Launching native rviz2 (image: $IMAGE, DISPLAY=$DISPLAY)..."
docker run --rm -it \
  --network host \
  -e DISPLAY="$DISPLAY" \
  -e XAUTHORITY="$HOME/.Xauthority" \
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  -e CYCLONEDDS_URI=file:///opt/xr/config/cyclone_uri/local.cyclonedds.xml \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "$HOME/.Xauthority:$HOME/.Xauthority:ro" \
  -v /opt/xr/config:/opt/xr/config:ro \
  "${RVIZ_CONFIG_ARGS[@]}" \
  "$IMAGE" \
  bash -ic "source /opt/xr/bot/setup.bash && exec $RVIZ_CMD"
