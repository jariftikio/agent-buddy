"""System Monitor Module - Track local system health and network connections."""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import psutil

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class CPUInfo:
    """CPU usage information."""

    percent_used: float
    core_count: int
    core_usage: List[float]
    load_average: tuple  # (1min, 5min, 15min)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "percent_used": self.percent_used,
            "core_count": self.core_count,
            "core_usage": self.core_usage,
            "load_average": {
                "one_minute": self.load_average[0],
                "five_minutes": self.load_average[1],
                "fifteen_minutes": self.load_average[2],
            },
        }


@dataclass
class MemoryInfo:
    """Memory usage information."""

    percent_used: float
    total_gb: float
    used_gb: float
    available_gb: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "percent_used": self.percent_used,
            "total_gb": round(self.total_gb, 2),
            "used_gb": round(self.used_gb, 2),
            "available_gb": round(self.available_gb, 2),
        }


@dataclass
class NetworkPort:
    """Information about a listening network port."""

    local_address: str
    local_port: int
    remote_address: str
    remote_port: Optional[int]
    status: str
    pid: Optional[int]
    process_name: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class SystemMonitor:
    """Monitor local system health, CPU, memory, and network connections."""

    def __init__(self, enable_logging: bool = True, log_level: str = "INFO"):
        """
        Initialize SystemMonitor.

        Args:
            enable_logging: Enable logging of monitoring events.
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        """
        self.enable_logging = enable_logging
        if enable_logging:
            logger.setLevel(log_level)
            logger.info("SystemMonitor initialized")

    def get_cpu_usage(self, interval: float = 1.0) -> CPUInfo:
        """
        Get current CPU usage information.

        Args:
            interval: Time interval (seconds) for measuring CPU usage.

        Returns:
            CPUInfo object with usage statistics.
        """
        try:
            percent = psutil.cpu_percent(interval=interval)
            core_count = psutil.cpu_count()
            core_usage = psutil.cpu_percent(interval=interval, percpu=True)
            load_avg = psutil.getloadavg()

            cpu_info = CPUInfo(
                percent_used=percent,
                core_count=core_count,
                core_usage=core_usage,
                load_average=load_avg,
            )

            if self.enable_logging:
                logger.info(f"CPU: {percent}% used, {core_count} cores")

            return cpu_info
        except Exception as e:
            logger.error(f"Failed to get CPU usage: {e}")
            raise

    def get_memory_usage(self) -> MemoryInfo:
        """
        Get current memory usage information.

        Returns:
            MemoryInfo object with memory statistics.
        """
        try:
            mem = psutil.virtual_memory()

            memory_info = MemoryInfo(
                percent_used=mem.percent,
                total_gb=mem.total / (1024**3),
                used_gb=mem.used / (1024**3),
                available_gb=mem.available / (1024**3),
            )

            if self.enable_logging:
                logger.info(
                    f"Memory: {memory_info.percent_used}% used "
                    f"({memory_info.used_gb:.2f}GB / {memory_info.total_gb:.2f}GB)"
                )

            return memory_info
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            raise

    def get_listening_ports(self, address_family: str = "all") -> List[NetworkPort]:
        """
        Get list of all listening network ports.

        Args:
            address_family: 'all', 'inet' (IPv4), or 'inet6' (IPv6).

        Returns:
            List of NetworkPort objects with active connections.
        """
        try:
            connections = psutil.net_connections()
            listening_ports = []

            for conn in connections:
                if conn.status != "LISTEN":
                    continue

                if address_family == "inet" and conn.family.name != "AF_INET":
                    continue
                elif address_family == "inet6" and conn.family.name != "AF_INET6":
                    continue

                try:
                    process_name = None
                    if conn.pid:
                        try:
                            process = psutil.Process(conn.pid)
                            process_name = process.name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            process_name = "N/A"

                    port = NetworkPort(
                        local_address=conn.laddr.ip if conn.laddr else "0.0.0.0",
                        local_port=conn.laddr.port if conn.laddr else 0,
                        remote_address=conn.raddr.ip if conn.raddr else "",
                        remote_port=conn.raddr.port if conn.raddr else None,
                        status=conn.status,
                        pid=conn.pid,
                        process_name=process_name,
                    )
                    listening_ports.append(port)
                except (AttributeError, psutil.AccessDenied) as e:
                    logger.warning(f"Could not retrieve process info: {e}")
                    continue

            if self.enable_logging:
                logger.info(f"Found {len(listening_ports)} listening ports")

            return sorted(listening_ports, key=lambda p: p.local_port)
        except psutil.AccessDenied:
            logger.error("Access denied when retrieving network connections. Run with sudo for full details.")
            raise
        except Exception as e:
            logger.error(f"Failed to get listening ports: {e}")
            raise

    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health report.

        Returns:
            Dictionary with CPU, memory, and port information.
        """
        try:
            cpu = self.get_cpu_usage()
            memory = self.get_memory_usage()
            ports = self.get_listening_ports()

            health = {
                "cpu": cpu.to_dict(),
                "memory": memory.to_dict(),
                "ports": [port.to_dict() for port in ports],
                "thresholds": {
                    "cpu_warning": Config.MONITOR_CPU_THRESHOLD,
                    "memory_warning": Config.MONITOR_MEMORY_THRESHOLD,
                },
                "alerts": self._generate_alerts(cpu, memory),
            }

            return health
        except Exception as e:
            logger.error(f"Failed to generate health report: {e}")
            raise

    def get_listening_ports_json(self, address_family: str = "all") -> List[Dict[str, Any]]:
        """
        Get listening ports as JSON-serializable list.

        Args:
            address_family: 'all', 'inet', or 'inet6'.

        Returns:
            List of port dictionaries.
        """
        ports = self.get_listening_ports(address_family)
        return [port.to_dict() for port in ports]

    @staticmethod
    def _generate_alerts(cpu: CPUInfo, memory: MemoryInfo) -> List[str]:
        """Generate alerts if thresholds are exceeded."""
        alerts = []

        if cpu.percent_used > Config.MONITOR_CPU_THRESHOLD:
            alerts.append(
                f"High CPU usage: {cpu.percent_used}% "
                f"(threshold: {Config.MONITOR_CPU_THRESHOLD}%)"
            )

        if memory.percent_used > Config.MONITOR_MEMORY_THRESHOLD:
            alerts.append(
                f"High memory usage: {memory.percent_used}% "
                f"(threshold: {Config.MONITOR_MEMORY_THRESHOLD}%)"
            )

        return alerts

    def is_port_listening(self, port: int, address: str = "0.0.0.0") -> bool:
        """
        Check if a specific port is currently listening.

        Args:
            port: Port number to check.
            address: IP address to check (default: all interfaces).

        Returns:
            True if port is listening, False otherwise.
        """
        try:
            ports = self.get_listening_ports()
            for p in ports:
                if p.local_port == port:
                    if address == "0.0.0.0" or p.local_address == address:
                        return True
            return False
        except Exception as e:
            logger.error(f"Failed to check port {port}: {e}")
            return False
