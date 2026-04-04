"""HTTP client for communicating with the ADE API."""

from __future__ import annotations

import os

import httpx


def get_base_url() -> str:
    return os.environ.get("ADE_API_URL", "http://127.0.0.1:8000")


class ADEClient:
    """Thin async httpx wrapper for the ADE API."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or get_base_url()

    async def health(self) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.get("/health")
            resp.raise_for_status()
            return resp.json()

    async def create_project(self, name: str, path: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.post("/projects/", json={"name": name, "path": path})
            resp.raise_for_status()
            return resp.json()

    async def list_projects(self) -> list[dict]:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.get("/projects/")
            resp.raise_for_status()
            return resp.json()

    async def get_project(self, project_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.get(f"/projects/{project_id}")
            resp.raise_for_status()
            return resp.json()

    async def create_task(self, project_id: str, description: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.post(
                f"/projects/{project_id}/tasks",
                json={"description": description},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_task(self, task_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.get(f"/tasks/{task_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_task_logs(self, task_id: str, agent_name: str | None = None) -> list[dict]:
        params = {}
        if agent_name:
            params["agent_name"] = agent_name
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.get(f"/tasks/{task_id}/logs", params=params)
            resp.raise_for_status()
            return resp.json()

    async def list_tasks(self, project_id: str) -> list[dict]:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.get(f"/projects/{project_id}/tasks")
            resp.raise_for_status()
            return resp.json()
