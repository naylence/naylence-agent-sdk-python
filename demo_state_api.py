#!/usr/bin/env python3
"""Demonstration of the improved state API."""

import asyncio
from src.naylence.agent.base_agent import BaseAgent, BaseAgentState


class UserPreferences(BaseAgentState):
    """User preferences with automatic persistence."""

    theme: str = "light"
    notifications_enabled: bool = True
    last_login: str = ""


class PreferencesAgent(BaseAgent[UserPreferences]):
    """Agent that manages user preferences."""

    def __init__(self, user_id: str):
        super().__init__(
            name=f"prefs_{user_id}",
            state_factory=lambda: UserPreferences(
                theme="dark", notifications_enabled=True, last_login="never"
            ),
        )


async def demo():
    """Demonstrate the new state API."""
    print("=== State Management Demo ===\n")

    agent = PreferencesAgent("user123")

    print("1. Using state as context manager (recommended):")
    async with agent.state as prefs:
        print(f"   Current theme: {prefs.theme}")
        print(f"   Notifications: {prefs.notifications_enabled}")
        prefs.theme = "blue"
        prefs.last_login = "2024-01-15"
        print("   Updated preferences in context")
        # Auto-saves when exiting context

    print("\n2. Direct state access:")
    current_prefs = await agent.get_state()
    print(f"   Persisted theme: {current_prefs.theme}")
    print(f"   Last login: {current_prefs.last_login}")

    print("\n3. Error handling (no save on exception):")
    try:
        async with agent.state as prefs:
            prefs.theme = "purple"
            print(f"   Changed theme to: {prefs.theme}")
            raise ValueError("Simulated error")
    except ValueError:
        print("   Exception caught!")

    # Check that state wasn't saved due to exception
    final_prefs = await agent.get_state()
    print(f"   Theme after exception: {final_prefs.theme} (should still be 'blue')")

    print("\n✅ Demo complete!")


if __name__ == "__main__":
    asyncio.run(demo())
