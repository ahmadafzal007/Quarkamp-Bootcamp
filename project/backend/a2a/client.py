"""
A2A Client — call external A2A agents from our pipeline.

Usage:
    from backend.a2a.client import A2AClient

    client = A2AClient("http://other-student-agent:8000")
    card   = client.get_agent_card()
    result = client.submit_and_wait("research", "Explain quantum entanglement")
"""

import time
import httpx
from typing import Optional


class A2AClient:
    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

    def get_agent_card(self) -> dict:
        """Discover what skills the remote agent has."""
        resp = httpx.get(f"{self.base_url}/a2a/.well-known/agent.json", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def submit_task(self, skill: str, question: str) -> str:
        """Submit a task and return the task_id."""
        resp = httpx.post(
            f"{self.base_url}/a2a/tasks",
            json={"skill": skill, "question": question},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["task_id"]

    def get_task(self, task_id: str) -> dict:
        """Poll for task status and result."""
        resp = httpx.get(f"{self.base_url}/a2a/tasks/{task_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def submit_and_wait(
        self,
        skill: str,
        question: str,
        poll_interval: float = 2.0,
        max_wait: int = 120,
    ) -> Optional[str]:
        """Submit a task and block until it completes or times out."""
        task_id  = self.submit_task(skill, question)
        deadline = time.time() + max_wait

        while time.time() < deadline:
            task = self.get_task(task_id)
            if task["status"] == "completed":
                return task.get("result", "")
            if task["status"] == "failed":
                raise RuntimeError(f"Remote task failed: {task.get('error')}")
            time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} did not complete within {max_wait}s")
