#!/usr/bin/env python3
"""Debug script to check state persistence."""

import asyncio
from src.naylence.agent.base_agent import BaseAgent, BaseAgentState


class Counter(BaseAgentState):
    count: int = 0
    message: str = "initial"


class TestAgent(BaseAgent[Counter]):
    def __init__(self, name: str = "test"):
        super().__init__(
            name, state_factory=lambda: Counter(count=0, message="initial")
        )


async def debug_state():
    """Debug state persistence."""
    agent = TestAgent("debug_agent")

    print("=== Step 1: First context use ===")
    async with agent.state as s:
        print(f"Loaded state: count={s.count}, message='{s.message}'")
        s.count = 42
        s.message = "modified"
        print(f"Modified state: count={s.count}, message='{s.message}'")
        print(f"State instance id: {id(s)}")
        # Should save when exiting

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
        # Should save when exiting

    print("\n=== Step 4: Final check ===")
    agent._state_cache = None
    final_state = await agent.get_state()
    print(f"Final state: count={final_state.count}, message='{final_state.message}'")


if __name__ == "__main__":
    asyncio.run(debug_state())
