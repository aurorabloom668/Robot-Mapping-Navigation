#!/usr/bin/env bash
# Run a Python script in robot ROS2 Docker with x2robot venv packages.
# 在机器人ROS2容器中运行Python脚本，并挂载x2robot虚拟环境依赖。
#
# Usage / 用法 (run on robot / 在机器人上执行):
#   ./examples/map_navigation/run_in_ros_env.sh \
#       examples/map_navigation/navigation_rviz.py \
#       --server localhost:50051 --map-name my_map

set -euo pipefail

IMAGE="zbl-registry.cn-shenzhen.cr.aliyuncs.com/xr/runtime/ex001:v00.02.06.02"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_SITE_PACKAGES="$REPO_DIR/.venv/lib/python3.12/site-packages"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <script.py> [args...]" >&2
  exit 1
fi

if [ ! -d "$VENV_SITE_PACKAGES" ]; then
  echo "Could not find $VENV_SITE_PACKAGES - is the venv at $REPO_DIR/.venv (python 3.12)?" >&2
  exit 1
fi

docker run --rm -it \
  --network host \
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  -e CYCLONEDDS_URI=file:///opt/xr/config/cyclone_uri/local.cyclonedds.xml \
  -e PYTHONPATH="$VENV_SITE_PACKAGES" \
  -v /opt/xr/config:/opt/xr/config:ro \
  -v "$REPO_DIR:$REPO_DIR" \
  -w "$REPO_DIR" \
  "$IMAGE" \
  bash -c 'source /opt/xr/bot/setup.bash && exec python3 "$@"' bash "$@"
