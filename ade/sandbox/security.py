"""Security policy for Docker sandbox containers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SandboxSecurityPolicy:
    """Defines resource limits and security constraints for sandbox containers."""

    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    timeout_seconds: int = 60
    network_disabled: bool = True
    read_only_rootfs: bool = False  # pytest needs to write .pytest_cache
    pids_limit: int = 256
    nofile_soft: int = 1024
    nofile_hard: int = 4096

    # Dropped Linux capabilities for tighter security
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])
    cap_add: list[str] = field(default_factory=list)

    # Security opt
    security_opt: list[str] = field(default_factory=lambda: ["no-new-privileges"])

    def to_container_kwargs(self) -> dict:
        """Convert policy to docker-py container.run() keyword arguments."""
        ulimits = []
        try:
            import docker.types

            ulimits.append(
                docker.types.Ulimit(
                    name="nofile",
                    soft=self.nofile_soft,
                    hard=self.nofile_hard,
                )
            )
        except ImportError:
            pass

        return {
            "mem_limit": self.memory_limit,
            "nano_cpus": int(self.cpu_limit * 1e9),
            "network_disabled": self.network_disabled,
            "read_only": self.read_only_rootfs,
            "pids_limit": self.pids_limit,
            "cap_drop": self.cap_drop,
            "cap_add": self.cap_add if self.cap_add else None,
            "security_opt": self.security_opt,
            "ulimits": ulimits if ulimits else None,
        }
