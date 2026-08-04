"""Mapping script / 建图脚本。

Function / 功能:
1) Start mapping via SDK / 通过SDK启动建图
2) Drive robot by keyboard / 键盘控制机器人移动
3) Stop mapping and save map / 停止建图并保存地图

Usage / 用法:
  python3 examples/map_navigation/mapping.py --server localhost:50051 --map-name my_map --no-start-rviz
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated
import shutil
import signal
import subprocess
import time

import typer

from x2robot import Robot, connect
from x2robot.sdk import (
    ChassisControlMode,
    ChassisControlModeParam,
    CoordinateSystemMode,
    CoordinateSystemModeParam,
    NavigationMode,
    NavigationModeParam,
    RobotModeParam,
    RobotWorkMode,
    SaveMapParam,
)

# Import shared keyboard helpers from examples/ / 从 examples/ 导入通用键盘控制逻辑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chassis_control import (
    KEY_TIMEOUT,
    VELOCITY_PUBLISH_RATE,
    VelocitySendThread,
    get_key,
    restore_terminal_settings,
    save_terminal_settings,
    stop_chassis,
)


DEFAULT_RVIZ_CONFIG = Path(__file__).with_name("mapping.rviz")  # default RViz config / 默认RViz配置


def ensure_success(result, action: str):
    """Check SDK call result / 检查SDK调用结果。"""
    if not getattr(result, "is_success", False):
        error_message = getattr(result, "error_message", "unknown error")
        raise RuntimeError(f"{action} failed: {error_message}")


def get_chassis_odometry(robot: Robot):
    """Print current chassis odometry / 打印当前底盘里程计信息。"""
    current_odometry = robot.chassis.get_odometry()
    current_orientation = current_odometry.pose.pose.orientation
    print(current_orientation)
    current_velocity = current_odometry.twist.twist.linear
    print(current_velocity)
    current_angular_velocity = current_odometry.twist.twist.angular
    print(current_angular_velocity)
    current_position = current_odometry.pose.pose.position
    print(current_position)


def launch_rviz2(rviz_config: Path | None) -> subprocess.Popen | None:
    """Launch local rviz2 process / 启动本地rviz2进程。"""
    rviz_executable = shutil.which("rviz2")
    if rviz_executable is None:
        ros2_executable = shutil.which("ros2")
        if ros2_executable is None:
            print("rviz2/ros2 not found, skip launching RViz2.")
            return None
        rviz_command = [ros2_executable, "run", "rviz2", "rviz2"]
    else:
        rviz_command = [rviz_executable]

    if rviz_config is not None and rviz_config.exists():
        rviz_command.extend(["-d", str(rviz_config)])
    elif rviz_config is not None:
        print(f"rviz config not found: {rviz_config}, launching RViz2 without config.")

    print(f"Launching RViz2: {' '.join(rviz_command)}")
    return subprocess.Popen(rviz_command)


def manual_mapping(robot: Robot, map_name: str, rviz_config: Path | None, start_rviz: bool):
    """Run mapping flow with keyboard teleop / 执行建图与键盘控制流程。"""
    rviz_process = None
    try:
        if start_rviz:
            rviz_process = launch_rviz2(rviz_config)

        result = robot.navigation.set_navigation_mode(
            NavigationModeParam(mode=NavigationMode.BUILT_IN_NAVIGATION)
        )
        ensure_success(result, "set navigation mode")

        coord_system_mode = CoordinateSystemModeParam(
            coordinate_system_mode=CoordinateSystemMode.MAP
        )
        result = robot.chassis.set_trajectory_coord_system_mode(coord_system_mode)
        ensure_success(result, "set trajectory coordinate system mode")

        result = robot.navigation.start_mapping()
        ensure_success(result, "start mapping")
        print("Mapping started.")

        robot.chassis.set_control_mode(
            ChassisControlModeParam(mode=ChassisControlMode.VELOCITY)
        )
        stop_chassis(robot)

        print(
            """
Manual mapping keys:
  w/s - forward/backward
  a/d - turn left/right
    i/k - increase/decrease linear speed
    j/l - increase/decrease angular speed
  space - stop
  q or Ctrl+C - finish and save map
            """.strip()
        )

        settings = save_terminal_settings()
        send_thread = VelocitySendThread(robot, VELOCITY_PUBLISH_RATE)
        send_thread.update(0.0, 0.0, 0.0, 0.0, 0.0)

        x = 0.0
        y = 0.0
        th = 0.0
        speed = 0.35
        turn = 0.40
        speed_limit = 1.0
        turn_limit = 2.0
        speed_step = 0.02
        turn_step = 0.02
        move_bindings = {
            "w": (1.0, 0.0, 0.0),
            "s": (-1.0, 0.0, 0.0),
            "a": (0.0, 0.0, 1.0),
            "d": (0.0, 0.0, -1.0),
        }

        try:
            while True:
                key = get_key(settings, KEY_TIMEOUT)
                if key in move_bindings:
                    x, y, th = move_bindings[key]
                elif key == "i":
                    speed = round(min(speed_limit, speed + speed_step), 2)
                    print(f"speed={speed:.2f} m/s, turn={turn:.2f} rad/s")
                    x, y, th = 0.0, 0.0, 0.0
                elif key == "k":
                    speed = round(max(0.0, speed - speed_step), 2)
                    print(f"speed={speed:.2f} m/s, turn={turn:.2f} rad/s")
                    x, y, th = 0.0, 0.0, 0.0
                elif key == "j":
                    turn = round(min(turn_limit, turn + turn_step), 2)
                    print(f"speed={speed:.2f} m/s, turn={turn:.2f} rad/s")
                    x, y, th = 0.0, 0.0, 0.0
                elif key == "l":
                    turn = round(max(0.0, turn - turn_step), 2)
                    print(f"speed={speed:.2f} m/s, turn={turn:.2f} rad/s")
                    x, y, th = 0.0, 0.0, 0.0
                elif key == " ":
                    x, y, th = 0.0, 0.0, 0.0
                elif key == "q":
                    break
                else:
                    x, y, th = 0.0, 0.0, 0.0

                send_thread.update(x, y, th, speed, turn)
        except KeyboardInterrupt:
            print("\nReceived interrupt signal, stopping mapping...")
        finally:
            send_thread.stop()
            restore_terminal_settings(settings)

        stop_chassis(robot)
        time.sleep(0.5)

        result = robot.navigation.stop_mapping(SaveMapParam(map_name=map_name))
        ensure_success(result, "stop mapping")
        print(f"Map saved successfully: {map_name}")

        time.sleep(1.0)
        get_chassis_odometry(robot)
    finally:
        if rviz_process is not None:
            rviz_process.terminate()
            try:
                rviz_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rviz_process.kill()


def main(
    server: Annotated[str, typer.Option(help="server address, e.g., localhost:50051")] = "localhost:50051",
    map_name: Annotated[str, typer.Option(help="name used to save the map")] = "",
    rviz_config: Annotated[
        Path,
        typer.Option(help="path to rviz2 config file"),
    ] = DEFAULT_RVIZ_CONFIG,
    start_rviz: Annotated[
        bool,
        typer.Option("--start-rviz/--no-start-rviz", help="launch rviz2 automatically"),
    ] = True,
):
    """CLI entry for mapping flow / 建图流程的命令行入口。"""
    robot = connect(f"x2://{server}")
    robot.system.set_work_mode(RobotModeParam(mode=RobotWorkMode.SDK))

    def signal_handler(signum, frame):
        """Handle Ctrl+C and exit / 处理Ctrl+C并退出。"""
        print("\nReceived interrupt signal, exiting...")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, signal_handler)

    if not map_name:
        map_name = datetime.now().strftime("mapping_%Y%m%d_%H%M%S")

    print("This example will start mapping and let you drive the robot with the keyboard.")
    print("Please make sure there is enough space around the robot.")
    if not input("continue? (y/n): ").lower() == "y":
        return

    manual_mapping(robot, map_name=map_name, rviz_config=rviz_config, start_rviz=start_rviz)


if __name__ == "__main__":
    typer.run(main)