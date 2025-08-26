import asyncio

import pytest
from naylence.fame.core import FameFabric

from naylence.agent.a2a_types import (
    Message,
    Task,
    TaskQueryParams,
    TaskSendParams,
    TaskState,
)
from naylence.agent.agent import Agent
from naylence.agent.base_agent import BaseAgent
from naylence.agent.util import make_task


@pytest.mark.asyncio
async def test_background_task_lifecycle():
    class TestAgent(BaseAgent):
        def __init__(self):
            super().__init__("test_agent")
            self._tasks: dict[str, TaskState] = {}

        async def start_task(self, params: TaskSendParams) -> Task:
            self._tasks[params.id] = TaskState.WORKING
            asyncio.create_task(self._run_background_job(params.id))
            return make_task(id=params.id, state=TaskState.WORKING, payload={})

        async def _run_background_job(self, task_id: str):
            await asyncio.sleep(0.1)
            self._tasks[task_id] = TaskState.COMPLETED

        async def get_task_status(self, params: TaskQueryParams) -> Task:
            state = self._tasks.get(params.id, TaskState.UNKNOWN)
            return make_task(id=params.id, state=state, payload={})

    async with FameFabric.create() as fabric:
        address = await fabric.serve(TestAgent())
        agent = Agent.remote_by_address(address)

        # ——— START & VERIFY PENDING ———
        task1 = await agent.start_task(
            TaskSendParams(id="task1", message=Message(role="agent", parts=[]))
        )
        assert task1.status.state == TaskState.WORKING

        task2 = await agent.start_task(
            TaskSendParams(id="task2", message=Message(role="agent", parts=[]))
        )
        assert task2.status.state == TaskState.WORKING

        status_immediate1 = await agent.get_task_status(TaskQueryParams(id="task1"))
        assert status_immediate1.status.state == TaskState.WORKING

        status_immediate2 = await agent.get_task_status(TaskQueryParams(id="task2"))
        assert status_immediate2.status.state == TaskState.WORKING

        # ——— WAIT FOR BACKGROUND JOB TO COMPLETE ———
        await asyncio.sleep(0.2)

        status_later1 = await agent.get_task_status(TaskQueryParams(id="task1"))
        assert status_later1.status.state == TaskState.COMPLETED

        status_later2 = await agent.get_task_status(TaskQueryParams(id="task2"))
        assert status_later2.status.state == TaskState.COMPLETED
