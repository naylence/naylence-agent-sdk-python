"""Math Agent - A simple agent demonstrating RPC operations."""

from typing import Any, AsyncIterator, Optional

from naylence.fame.core import FameMessageResponse
from naylence.fame.service import operation

from naylence.agent import BaseAgent


class MathAgent(BaseAgent):
    """A simple math agent that provides add, multiply, and Fibonacci operations."""

    async def on_message(self, message: Any) -> Optional[FameMessageResponse]:
        """Handle incoming messages."""
        print(f"MathAgent received message: {message}")
        return None

    @operation()
    async def add(self, x: int = 0, y: int = 0) -> int:
        """Add two numbers."""
        return x + y

    @operation(name="multiply")
    async def multi(self, x: int = 0, y: int = 0) -> int:
        """Multiply two numbers."""
        return x * y

    @operation(name="fib_stream", streaming=True)
    async def fib(self, n: int = 10) -> AsyncIterator[int]:
        """Generate Fibonacci sequence."""
        a, b = 0, 1
        for _ in range(n):
            yield a
            a, b = b, a + b
