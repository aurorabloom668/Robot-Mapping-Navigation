"""Navigation script with RViz goal integration / 导航与RViz目标点联动脚本。

Function / 功能:
1) Initialize localization with a saved map / 基于已保存地图启动定位
2) Listen to RViz 2D Nav Goal on /goal_pose / 监听 RViz 的 2D Nav Goal
3) Send navigation goals via SDK API / 通过 SDK 下发导航目标
4) Publish actual trajectory on /actual_trajectory / 发布实际轨迹到 /actual_trajectory

Run location / 运行位置:
- Run on robot / 在机器人上运行
- Recommended command / 推荐命令:
  ./run_in_ros_env.sh navigation_rviz.py --server localhost:50051 --map-name my_map
"""
from __future__ import annotations

import math
import signal
import threading
import time
from typing import Annotated, Optional

import typer

from x2robot import Robot, connect
from x2robot.sdk import (
    ChassisControlMode,
    ChassisControlModeParam,
    ChassisPosition,
    CoordinateSystemMode,
    CoordinateSystemModeParam,
    NavigationMode,
    NavigationModeParam,
    RobotModeParam,
    RobotWorkMode,
    SaveMapParam,
)

try:
    import rclpy
    import rclpy.executors
    from geometry_msgs.msg import PoseStamped
    from nav_msgs.msg import Path

    _RCLPY_IMPORT_ERROR: Optional[Exception] = None
except ImportError as e:  # pragma: no cover - exercised only without ROS2 installed
    rclpy = None
    PoseStamped = None
    Path = None
    _RCLPY_IMPORT_ERROR = e


def require_rclpy():
    """Ensure rclpy is available / 确保rclpy可用。"""
    if rclpy is None:
        raise RuntimeError(
            "rclpy is required to listen for RViz's \"2D Nav Goal\". Run this "
            "script through run_in_ros_env.sh instead (see the module "
            "docstring), or use --goal-x/--goal-y to skip RViz entirely."
        ) from _RCLPY_IMPORT_ERROR


# SDK call timeout (seconds) / SDK 调用超时（秒）
SDK_CALL_TIMEOUT_S = 8.0


def call_and_check(action: str, fn, *args, timeout: float = SDK_CALL_TIMEOUT_S, **kwargs):
    """Call SDK and raise RuntimeError on failure / 调用SDK，失败时抛出异常。"""
    try:
        result = fn(*args, timeout=timeout, **kwargs)
    except Exception as e:
        raise RuntimeError(f"{action} failed: {e}") from e
    if not getattr(result, "is_success", True):
        error_message = getattr(result, "error_message", "unknown error")
        raise RuntimeError(f"{action} failed: {error_message}")
    return result


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    """Convert quaternion to yaw / 四元数转换为偏航角。"""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def setup_localization(robot: Robot, map_name: str):
    """Initialize localization and GLOBAL mode / 初始化定位并切到GLOBAL模式。"""
    robot.system.set_work_mode(RobotModeParam(mode=RobotWorkMode.SDK), timeout=SDK_CALL_TIMEOUT_S)

    call_and_check(
        "set navigation mode",
        robot.navigation.set_navigation_mode,
        NavigationModeParam(mode=NavigationMode.BUILT_IN_NAVIGATION),
    )

    call_and_check(
        "set trajectory coordinate system mode",
        robot.chassis.set_trajectory_coord_system_mode,
        CoordinateSystemModeParam(coordinate_system_mode=CoordinateSystemMode.MAP),
    )

    call_and_check(
        "start localization",
        robot.navigation.start_localization,
        SaveMapParam(map_name=map_name),
    )
    print(f"Localization started with map: {map_name!r}")

    call_and_check(
        "set chassis control mode to GLOBAL",
        robot.chassis.set_control_mode,
        ChassisControlModeParam(mode=ChassisControlMode.GLOBAL),
    )


def _navigation_ready(robot: Robot) -> bool:
    """Check nav readiness / 检查导航是否可用。"""
    try:
        mode = robot.chassis.get_control_mode(timeout=SDK_CALL_TIMEOUT_S)
        if mode.mode != ChassisControlMode.GLOBAL:
            return False
        robot.chassis.get_global_position(timeout=SDK_CALL_TIMEOUT_S)
        return True
    except Exception:
        return False


# Wait time after re-initialization (seconds) / 恢复初始化后的等待时间（秒）
WAIT_AFTER_RECOVERY_S = 15.0
# Published trajectory topic / 发布轨迹话题
ACTUAL_TRAJECTORY_TOPIC = "/actual_trajectory"


def _wait_until_ready(robot: Robot, timeout: float = WAIT_AFTER_RECOVERY_S) -> bool:
    """Wait until navigation is ready / 等待导航恢复可用。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _navigation_ready(robot):
            return True
        time.sleep(1.0)
    return False


def send_goal(robot: Robot, x: float, y: float, yaw: float, map_name: Optional[str] = None):
    """Send a navigation goal with recovery / 发送导航目标并在失败时恢复重试。"""
    print(f"Sending navigation goal: x={x:.3f}, y={y:.3f}, yaw={yaw:.3f}")

    if map_name and not _navigation_ready(robot):
        print(
            "Chassis is not in GLOBAL mode / localization not responding - re-running "
            "setup_localization() to recover (this restarts the robot's nav2 container, "
            f"can take up to {WAIT_AFTER_RECOVERY_S:.0f}s to come back up)..."
        )
        setup_localization(robot, map_name)
        if not _wait_until_ready(robot):
            print("Still not ready after waiting - sending the goal anyway, it will likely fail.")

    try:
        call_and_check(
            "move_to_global_position",
            robot.chassis.move_to_global_position,
            ChassisPosition(x=x, y=y, yaw=yaw),
        )
    except RuntimeError as e:
        if map_name is None:
            raise
        # Retry once after re-setup / 重新初始化后重试一次
        print(f"move_to_global_position failed/timed out ({e}); recovering and retrying once...")
        setup_localization(robot, map_name)
        if not _wait_until_ready(robot):
            print("Still not ready after waiting - retrying anyway, it will likely fail too.")
        call_and_check(
            "move_to_global_position",
            robot.chassis.move_to_global_position,
            ChassisPosition(x=x, y=y, yaw=yaw),
        )
    print("Goal accepted by the robot.")


def _spin_node(node, stop_event: threading.Event):
    """Spin ROS node in a loop / 循环执行ROS节点spin。"""
    while not stop_event.is_set() and rclpy.ok():
        try:
            rclpy.spin_once(node, timeout_sec=0.2)
        except rclpy.executors.ExternalShutdownException:
            break


class GoalListener:
    """Listen /goal_pose and forward goal / 监听 /goal_pose 并转发导航目标。"""

    _SAME_GOAL_TOLERANCE = 1e-3  # meters/radians / 米、弧度

    def __init__(self, robot: Robot, node, map_name: str, topic: str = "/goal_pose"):
        """Create goal listener subscriber / 创建目标点订阅器。"""
        self.robot = robot
        self.map_name = map_name
        self._last_goal: Optional[tuple] = None
        self._sub = node.create_subscription(PoseStamped, topic, self._on_goal, 10)
        print(f'Listening for RViz "2D Nav Goal" clicks on {topic}...')

    def _on_goal(self, msg: "PoseStamped"):
        """Handle incoming RViz goal / 处理RViz发送的目标点。"""
        try:
            yaw = quaternion_to_yaw(
                msg.pose.orientation.x,
                msg.pose.orientation.y,
                msg.pose.orientation.z,
                msg.pose.orientation.w,
            )
            x, y = msg.pose.position.x, msg.pose.position.y
            if self._last_goal is not None and all(
                abs(a - b) <= self._SAME_GOAL_TOLERANCE for a, b in zip((x, y, yaw), self._last_goal)
            ):
                print(
                    f"Ignoring duplicate goal (same as last one, x={x:.3f}, y={y:.3f}, "
                    f"yaw={yaw:.3f}) - not re-sending / not preempting the current task."
                )
                return
            self._last_goal = (x, y, yaw)
            send_goal(self.robot, x, y, yaw, map_name=self.map_name)
        except Exception as e:
            print(f"Failed to forward RViz goal: {e}")


class ActualTrajectoryPublisher:
    """Publish actual trajectory for RViz / 发布实际轨迹供RViz显示。"""

    def __init__(
        self,
        robot: Robot,
        node,
        topic: str = ACTUAL_TRAJECTORY_TOPIC,
        frame_id: str = "map",
        publish_rate_hz: float = 5.0,
        max_points: int = 4000,
        min_dist_m: float = 0.02,
        min_yaw_rad: float = 0.02,
    ):
        """Initialize trajectory publisher / 初始化轨迹发布器。"""
        self.robot = robot
        self.node = node
        self.frame_id = frame_id
        self.max_points = max_points
        self.min_dist_m = min_dist_m
        self.min_yaw_rad = min_yaw_rad
        self._last_pose: Optional[tuple] = None
        self._path_msg = Path()
        self._path_msg.header.frame_id = self.frame_id
        self._pub = node.create_publisher(Path, topic, 10)
        self._timer = node.create_timer(1.0 / max(publish_rate_hz, 0.1), self._tick)
        print(f'Publishing actual trajectory on {topic} (frame="{frame_id}")')

    def _tick(self):
        """Sample pose and publish path / 采样位姿并发布路径。"""
        try:
            pose = self.robot.chassis.get_global_position(timeout=SDK_CALL_TIMEOUT_S)
            x, y, yaw = float(pose.x), float(pose.y), float(pose.yaw)
        except Exception:
            return

        if self._last_pose is not None:
            lx, ly, lyaw = self._last_pose
            if math.hypot(x - lx, y - ly) < self.min_dist_m and abs(yaw - lyaw) < self.min_yaw_rad:
                return

        stamp = self.node.get_clock().now().to_msg()
        pose_msg = PoseStamped()
        pose_msg.header.stamp = stamp
        pose_msg.header.frame_id = self.frame_id
        pose_msg.pose.position.x = x
        pose_msg.pose.position.y = y
        pose_msg.pose.position.z = 0.0
        pose_msg.pose.orientation.z = math.sin(yaw * 0.5)
        pose_msg.pose.orientation.w = math.cos(yaw * 0.5)
        self._path_msg.poses.append(pose_msg)
        if len(self._path_msg.poses) > self.max_points:
            self._path_msg.poses = self._path_msg.poses[-self.max_points :]
        self._path_msg.header.stamp = stamp
        self._pub.publish(self._path_msg)
        self._last_pose = (x, y, yaw)


def main(
    server: Annotated[str, typer.Option(help="server address, e.g., 10.150.11.68:50051")] = "localhost:50051",
    map_name: Annotated[str, typer.Option(help="map name to localize against (see mapping.py --map-name)")] = "",
    goal_topic: Annotated[
        str, typer.Option(help='topic rviz2\'s "2D Nav Goal" tool publishes to')
    ] = "/goal_pose",
    goal_x: Annotated[
        Optional[float], typer.Option(help="send one goal via the API instead of using RViz (map frame, meters)")
    ] = None,
    goal_y: Annotated[Optional[float], typer.Option(help="target y (map frame, meters)")] = None,
    goal_yaw: Annotated[float, typer.Option(help="target yaw (map frame, radians)")] = 0.0,
):
    """CLI entry for navigation flow / 导航流程的命令行入口。"""
    if not map_name:
        print("Please provide --map-name (the map saved by mapping.py).")
        raise typer.Exit(code=1)

    robot = connect(f"x2://{server}")

    def signal_handler(signum, frame):
        """Handle Ctrl+C and exit / 处理Ctrl+C并退出。"""
        print("\nReceived interrupt signal, exiting...")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, signal_handler)

    setup_localization(robot, map_name)

    # One-shot API mode / 单次API目标模式
    if goal_x is not None and goal_y is not None:
        send_goal(robot, goal_x, goal_y, goal_yaw, map_name=map_name)
        return

    require_rclpy()
    if not rclpy.ok():
        rclpy.init(args=[])

    # Local ROS2 node for /goal_pose and /actual_trajectory
    # 本地ROS2节点：接收 /goal_pose、发布 /actual_trajectory
    node = rclpy.create_node("x2robot_navigation_rviz")
    stop_spin = threading.Event()
    spin_thread = threading.Thread(target=_spin_node, args=(node, stop_spin), daemon=True, name="nav-spin")
    spin_thread.start()

    goal_listener = GoalListener(robot, node, map_name=map_name, topic=goal_topic)
    _trajectory_publisher = ActualTrajectoryPublisher(robot, node)

    print("\nNavigation ready.")
    print('Click "2D Nav Goal" in RViz to send a target, or Ctrl+C to exit.')
    print("(Or re-run with --goal-x/--goal-y/--goal-yaw for a one-shot API goal, no RViz needed.)")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping navigation...")
    finally:
        stop_spin.set()
        spin_thread.join(timeout=2)
        node.destroy_node()
        try:
            result = robot.navigation.stop_localization(timeout=SDK_CALL_TIMEOUT_S)
            print(f"stop_localization result: {getattr(result, 'is_success', result)}")
        except Exception as e:
            print(f"stop_localization failed: {e}")
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    typer.run(main)
