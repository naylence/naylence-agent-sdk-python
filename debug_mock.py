#!/usr/bin/env python3
"""Debug script with mocked storage."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from src.naylence.agent.base_agent import BaseAgent, BaseAgentState


class Counter(BaseAgentState):
    count: int = 0
    message: str = "initial"


class TestAgent(BaseAgent[Counter]):
    def __init__(self, name: str = "test"):
        super().__init__(
            name, state_factory=lambda: Counter(count=0, message="initial")
        )
        # Mock storage
        self._storage_provider = MagicMock()
        self._mock_storage = {}

        # Mock kv store
        mock_kv_store = AsyncMock()
        mock_kv_store.get = AsyncMock(side_effect=self._mock_get)
        mock_kv_store.set = AsyncMock(side_effect=self._mock_set)
        self._storage_provider.get_kv_store = AsyncMock(return_value=mock_kv_store)

    async def _mock_get(self, key: str):
        print(f"MOCK: Getting key '{key}' -> {self._mock_storage.get(key)}")
        return self._mock_storage.get(key)

    async def _mock_set(self, key: str, value: Any):
        print(f"MOCK: Setting key '{key}' -> {value}")
        self._mock_storage[key] = value


async def debug_state():
    """Debug state persistence with mocked storage."""
    agent = TestAgent("debug_agent")

    print("=== Step 1: First context use ===")
    async with agent.state as s:
        print(f"Loaded state: count={s.count}, message='{s.message}'")
        print(f"State type: {type(s)}")
        print(f"State instance id: {id(s)}")
        s.count = 42
        s.message = "modified"
        print(f"Modified state: count={s.count}, message='{s.message}'")
        # Should save when exiting

    print(f"\nMock storage after first context: {agent._mock_storage}")

    print("\n=== Step 2: Check persistence ===")
    # Clear cache to force reload from storage
    agent._state_cache = None

    state_direct = await agent.get_state()
    print(f"Direct load: count={state_direct.count}, message='{state_direct.message}'")
    print(f"State instance id: {id(state_direct)}")

    print("\n=== Step 3: Second context use ===")
    async with agent.state as s:
        print(f"Second load: count={s.count}, message='{s.message}'")
        print(f"State instance id: {id(s)}")
        s.count += 10
        print(f"Modified to: count={s.count}")
        # Should save when exiting

    print(f"\nMock storage after second context: {agent._mock_storage}")

    print("\n=== Step 4: Final check ===")
    agent._state_cache = None
    final_state = await agent.get_state()
    print(f"Final state: count={final_state.count}, message='{final_state.message}'")


if __name__ == "__main__":
    asyncio.run(debug_state())
