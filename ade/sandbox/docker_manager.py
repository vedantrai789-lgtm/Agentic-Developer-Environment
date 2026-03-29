"""Docker-based sandbox executor using docker-py."""

from __future__ import annotations

import asyncio
import sys
import time

from ade.agents.executor import ExecutorBackend
from ade.agents.state import ExecutionResultDict
from ade.core.config import get_settings
from ade.sandbox.security import SandboxSecurityPolicy


class DockerExecutor(ExecutorBackend):
    """Execute commands inside ephemeral Docker containers."""

    def __init__(self, policy: SandboxSecurityPolicy | None = None) -> None:
        settings = get_settings()
        self.image = settings.sandbox_docker_image
        self.policy = policy or SandboxSecurityPolicy(
            memory_limit=settings.sandbox_memory_limit,
            cpu_limit=settings.sandbox_cpu_limit,
            timeout_seconds=settings.sandbox_timeout_seconds,
            network_disabled=settings.sandbox_network_disabled,
        )
        self._client = None

    def _get_client(self):
        """Lazy-init docker client."""
        if self._client is None:
            import docker

            self._client = docker.from_env()
        return self._client

    async def run(
        self, command: str, workdir: str, timeout: int | None = None
    ) -> ExecutionResultDict:
        """Run a command in a Docker container with the workspace mounted."""
        effective_timeout = timeout or self.policy.timeout_seconds
        return await asyncio.to_thread(
            self._run_sync, command, workdir, effective_timeout
        )

    def _run_sync(
        self, command: str, workdir: str, timeout: int
    ) -> ExecutionResultDict:
        """Synchronous container execution (runs in thread pool)."""
        client = self._get_client()
        container = None
        start = time.monotonic()

        try:
            container_kwargs = self.policy.to_container_kwargs()

            container = client.containers.run(
                image=self.image,
                command=["bash", "-c", command],
                volumes={workdir: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                user="sandbox",
                detach=True,
                **container_kwargs,
            )

            # Wait for completion with timeout
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", 1)

            stdout = container.logs(stdout=True, stderr=False).decode(
                "utf-8", errors="replace"
            )
            stderr = container.logs(stdout=False, stderr=True).decode(
                "utf-8", errors="replace"
            )

            duration_ms = int((time.monotonic() - start) * 1000)

            return ExecutionResultDict(
                command=command,
                exit_code=exit_code,
                stdout=_truncate(stdout, max_bytes=50_000),
                stderr=_truncate(stderr, max_bytes=50_000),
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            error_msg = str(e)

            # Check for timeout
            if "timed out" in error_msg.lower() or "read timed out" in error_msg.lower():
                error_msg = f"Container timed out after {timeout}s"

            print(f"Docker executor error: {error_msg}", file=sys.stderr)

            return ExecutionResultDict(
                command=command,
                exit_code=1,
                stdout="",
                stderr=error_msg,
                duration_ms=duration_ms,
            )

        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def ensure_image(self) -> bool:
        """Check if sandbox image exists, build it if not.

        Returns True if image is available.
        """
        client = self._get_client()
        try:
            client.images.get(self.image)
            return True
        except Exception:
            return self._build_image(client)

    def _build_image(self, client) -> bool:
        """Build the sandbox Docker image from Dockerfile.sandbox."""
        from pathlib import Path

        dockerfile_path = Path(__file__).parent / "Dockerfile.sandbox"
        if not dockerfile_path.exists():
            print(
                f"Dockerfile not found at {dockerfile_path}", file=sys.stderr
            )
            return False

        try:
            print(f"Building sandbox image '{self.image}'...")
            client.images.build(
                path=str(dockerfile_path.parent),
                dockerfile="Dockerfile.sandbox",
                tag=self.image,
                rm=True,
            )
            print(f"Sandbox image '{self.image}' built successfully.")
            return True
        except Exception as e:
            print(f"Failed to build sandbox image: {e}", file=sys.stderr)
            return False


def _truncate(text: str, max_bytes: int = 50_000) -> str:
    """Truncate output to avoid storing huge logs."""
    if len(text) <= max_bytes:
        return text
    return text[:max_bytes] + f"\n... (truncated, {len(text)} bytes total)"
