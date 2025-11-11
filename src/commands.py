"""
Commands module for the Memory Game.

This module provides a clean abstraction layer between the HTTP server and the Board ADT.
Each function in this module corresponds to a client command/request and delegates to
the appropriate Board method.

Module Structure (Required Design):
- Separates concerns: server handles HTTP, commands handle game logic coordination
- Provides simple async functions that can be called from request handlers
- Does not maintain any mutable state (stateless command layer)
- All game state is managed by the Board instance passed as a parameter

Safety from Rep Exposure:
- No mutable state in this module
- All functions take Board as parameter, never store references
- Returns only immutable strings from Board operations
- No direct access to Board's internal representation
"""

from board import Board
from typing import Callable, Awaitable, Optional


async def look(board: Board, player_id: str) -> str:
    """
    Return the board state from the perspective of a player.

    Preconditions:
    - board is a valid Board instance
    - player_id is a non-empty string

    Postconditions:
    - Returns string representation of board state
    - Board state is unchanged
    - No side effects

    Args:
        board: The game board
        player_id: ID of the player viewing the board

    Returns:
        Multi-line string with board dimensions and card states
    """
    return await board.look(player_id)


async def flip(board: Board, player_id: str, row: int, column: int) -> str:
    """
    Flip a card at (row, column) for a player.

    Preconditions:
    - board is a valid Board instance
    - player_id is a non-empty string
    - row and column are valid indices for the board

    Postconditions:
    - Card flip is processed according to game rules (1-A through 3-B)
    - Returns updated board state
    - Board state may be modified (cards flipped, removed, etc.)
    - All watchers are notified of the change

    Args:
        board: The game board
        player_id: ID of the player flipping the card
        row: Row index of the card to flip
        column: Column index of the card to flip

    Returns:
        String representation of updated board state

    Raises:
        ValueError: If flip operation fails (invalid position, no card, controlled card, etc.)
    """
    return await board.flip(player_id, row, column)


async def map_replace(board: Board, player_id: str,
                      f: Callable[[str], Awaitable[str]]) -> str:
    """
    Replace all card values using async function f.

    Preconditions:
    - board is a valid Board instance
    - player_id is a non-empty string
    - f is an async function that transforms card values (str -> str)

    Postconditions:
    - All card values on the board are transformed by function f
    - Returns updated board state
    - Board state is modified
    - All watchers are notified of the change

    Args:
        board: The game board
        player_id: ID of the player performing the replacement
        f: Async function to transform each card value

    Returns:
        String representation of updated board state
    """
    return await board.map_cards(player_id, f)


async def watch(board: Board, player_id: str) -> str:
    """
    Wait until any change occurs on the board, then return the updated board state.

    Preconditions:
    - board is a valid Board instance
    - player_id is a non-empty string

    Postconditions:
    - Blocks until another player modifies the board
    - Returns string representation of updated board state
    - Board state is unchanged by this operation
    - Multiple watchers can wait concurrently

    Args:
        board: The game board
        player_id: ID of the player watching for changes

    Returns:
        String representation of the board state after a change occurs
    """
    future: Optional[Awaitable[str]] = None

    # We need to wait until a board change happens and then return board state
    async def watcher():
        # Wait for a board change
        await board.watch(player_id)
        # After the change, return the latest board state
        return await board.look(player_id)

    return await watcher()
