# Real-Robot Mapping & Navigation with X Square SDK

[![Ubuntu](https://img.shields.io/badge/OS-Ubuntu%2024.04-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com/download)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Language / 语言**: [English](README.md) • [中文](README_CN.md)

This repository demonstrates an end-to-end **mapping and navigation workflow on a real robot** using the **X Square open-source SDK**.

## What This Project Covers

- Mapping with keyboard teleoperation
- Saving and reusing maps
- Localization and goal-based navigation
- RViz visualization and 2D Nav Goal interaction

## System Requirement

- **OS**: **Ubuntu 24.04** (x86_64)
- **Python**: 3.12
- **Runtime**: Docker available on robot side

## Prerequisites

### 1) Network and Access

- Ensure your laptop can SSH into the robot
- Use X11 forwarding when opening RViz from robot side:

```bash
ssh -X <robot_user>@<robot_ip>
```

If OpenGL forwarding is unstable, try:

```bash
ssh -Y <robot_user>@<robot_ip>
```

### 2) Python Environment (Ubuntu 24.04)

```bash
sudo apt update
sudo apt install -y python3-pip python3.12-venv ffmpeg
```

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the SDK wheel (example):

```bash
pip install x2robot-*.whl
```

### 3) Recommended Project Files

This guide focuses on:

- `examples/map_navigation/mapping.py`
- `examples/map_navigation/navigation_rviz.py`
- `examples/map_navigation/run_native_rviz.sh`
- `examples/map_navigation/run_in_ros_env.sh`
- `examples/map_navigation/mapping.rviz`
- `examples/chassis_control.py` (shared keyboard control logic dependency)

## Quick Start

> Commands below are executed on the robot unless explicitly noted.

### Phase A: Mapping

1. Start mapping (keyboard control):

```bash
cd ~/sdk_robot
python3 examples/map_navigation/mapping.py --server localhost:50051 --map-name my_map --no-start-rviz
```

2. Optional visualization in another SSH terminal:

```bash
cd ~/sdk_robot
./examples/map_navigation/run_native_rviz.sh
```

### Phase B: Navigation

1. Start localization + goal listener:

```bash
cd ~/sdk_robot
./examples/map_navigation/run_in_ros_env.sh examples/map_navigation/navigation_rviz.py \
  --server localhost:50051 --map-name my_map
```

2. Open RViz in another SSH terminal and use **2D Nav Goal**:

```bash
cd ~/sdk_robot
./examples/map_navigation/run_native_rviz.sh
```

3. API-only one-shot goal (without RViz):

```bash
python3 examples/map_navigation/navigation_rviz.py \
  --server <robot_ip>:50051 --map-name my_map \
  --goal-x 1.2 --goal-y -0.3 --goal-yaw 0.0
```

## Notes

- To switch to a new map, only change `--map-name` in navigation command.
- RViz config in this project subscribes to map/costmap/trajectory topics used by this workflow.

## Attribution

This project is built with the **X Square open-source SDK** and references official API documentation for real-robot integration and validation.

**Trademark Notice**: X Square and related product names may be trademarks or registered trademarks of their respective owners.  
This repository is an independent community example and is not officially affiliated with or endorsed by X Square.
