from board import Board
from typing import Callable, Awaitable, Optional


async def look(board: Board, player_id: str) -> str:
    """Return the board state from the perspective of a player."""
    return await board.look(player_id)


async def flip(board: Board, player_id: str, row: int, column: int) -> str:
    """Flip a card at (row, column) for a player."""
    return await board.flip(player_id, row, column)


async def map_replace(board: Board, player_id: str,
                      f: Callable[[str], Awaitable[str]]) -> str:
    """Replace all card values using async function f."""
    return await board.map_cards(player_id, f)


async def watch(board: Board, player_id: str) -> str:
    """
    Wait until any change occurs on the board, then return the updated board state.
    """
    future: Optional[Awaitable[str]] = None

    # We need to wait until a board change happens and then return board state
    async def watcher():
        # Wait for a board change
        await board.watch(player_id)
        # After the change, return the latest board state
        return await board.look(player_id)

    return await watcher()
