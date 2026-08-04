# 基于 X Square SDK 的真机建图导航项目

**Language / 语言**: [English](README.md) • [中文](README_CN.md)

本仓库聚焦一个完整的真机流程：使用 **X Square 开源 SDK** 实现 **建图 + 定位导航**。

## 项目内容

- 键盘遥控建图
- 地图保存与复用
- 基于已保存地图的定位导航
- RViz 可视化与 2D Nav Goal 点目标

## 系统要求

- **操作系统**：**Ubuntu 24.04**（x86_64）
- **Python**：3.12
- **运行环境**：机器人侧可用 Docker

## 前置配置

### 1）网络与登录

- 确保笔记本可以 SSH 登录机器人
- 如需在笔记本显示机器人侧 RViz，使用 X11 转发：

```bash
ssh -X <robot_user>@<robot_ip>
```

如果 OpenGL 转发不稳定，可改用：

```bash
ssh -Y <robot_user>@<robot_ip>
```

### 2）Python 环境（Ubuntu 24.04）

```bash
sudo apt update
sudo apt install -y python3-pip python3.12-venv ffmpeg
```

```bash
python3 -m venv .venv
source .venv/bin/activate
```

安装 SDK wheel（示例）：

```bash
pip install x2robot-*.whl
```

### 3）本项目用到的核心文件

- `examples/map_navigation/mapping.py`
- `examples/map_navigation/navigation_rviz.py`
- `examples/map_navigation/run_native_rviz.sh`
- `examples/map_navigation/run_in_ros_env.sh`
- `examples/map_navigation/mapping.rviz`
- `examples/chassis_control.py`（建图脚本依赖的通用键盘控制逻辑）

## 快速开始

> 除非特别说明，以下命令都在机器人上执行。

### 阶段A：建图

1. 启动建图（键盘控制）：

```bash
cd ~/sdk_robot
python3 examples/map_navigation/mapping.py --server localhost:50051 --map-name my_map --no-start-rviz
```

2. 可选：另一个 SSH 终端打开 RViz 可视化：

```bash
cd ~/sdk_robot
./examples/map_navigation/run_native_rviz.sh
```

### 阶段B：导航

1. 启动定位与目标监听：

```bash
cd ~/sdk_robot
./examples/map_navigation/run_in_ros_env.sh examples/map_navigation/navigation_rviz.py \
  --server localhost:50051 --map-name my_map
```

2. 在另一个 SSH 终端打开 RViz，用 **2D Nav Goal** 点目标：

```bash
cd ~/sdk_robot
./examples/map_navigation/run_native_rviz.sh
```

3. 仅 API 单次下发目标（不使用 RViz）：

```bash
python3 examples/map_navigation/navigation_rviz.py \
  --server <robot_ip>:50051 --map-name my_map \
  --goal-x 1.2 --goal-y -0.3 --goal-yaw 0.0
```

## 使用说明

- 重新建图后，导航阶段只需要替换 `--map-name`。
- 本项目的 `mapping.rviz` 已配置该流程所需地图/代价地图/轨迹显示话题。

## 引用与声明（X Square SDK）

本项目基于 **X Square 开源 SDK** 开发，并参考官方 API 文档进行真机集成与验证。

**商标声明**：X Square 及相关产品名称可能是其各自所有者的商标或注册商标。  
本仓库为独立社区示例，不代表 X Square 官方立场，也未获得官方背书。
