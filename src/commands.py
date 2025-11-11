"""
String-based commands provided by the Memory Scramble game.
Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.

These functions provide the game interface as specified in the PS4 handout.
"""

from board import Board
from typing import Callable, Awaitable


async def look(board: Board, player_id: str) -> str:
    """
    Looks at the current state of the board.

    Args:
        board: A Memory Scramble board
        player_id: ID of player looking at the board;
                   must be a nonempty string of alphanumeric or underscore characters

    Returns:
        The state of the board from the perspective of player_id, in the format
        described in the ps4 handout
    """
    return await board.look(player_id)


async def flip(board: Board, player_id: str, row: int, column: int) -> str:
    """
    Tries to flip over a card on the board, following the rules in the ps4 handout.
    If another player controls the card, then this operation waits until the flip
    either becomes possible or fails.

    Args:
        board: A Memory Scramble board
        player_id: ID of player making the flip;
                   must be a nonempty string of alphanumeric or underscore characters
        row: Row number of card to flip;
             must be an integer in [0, height of board), indexed from the top of the board
        column: Column number of card to flip;
                must be an integer in [0, width of board), indexed from the left of the board

    Returns:
        The state of the board after the flip from the perspective of player_id, in the
        format described in the ps4 handout

    Raises:
        ValueError: If the flip operation fails as described in the ps4 handout
    """
    return await board.flip(player_id, row, column)


async def map_replace(board: Board, player_id: str,
                      f: Callable[[str], Awaitable[str]]) -> str:
    """
    Modifies board by replacing every card with f(card), without affecting other state of the game.

    This operation must be able to interleave with other operations, so while a map() is in progress,
    other operations like look() and flip() should not throw an unexpected error or wait for the map() 
    to finish. But the board must remain observably pairwise consistent for players: if two cards on 
    the board match each other at the start of a call to map(), then while that map() is in progress, 
    it must not cause any player to observe a board state in which that pair of cards do not match.

    Two interleaving map() operations should not throw an unexpected error, or force each other to wait,
    or violate pairwise consistency, but the exact way they must interleave is not specified.

    f must be a mathematical function from cards to cards:
    given some legal card `c`, f(c) should be a legal replacement card which is consistently
    the same every time f(c) is called for that same `c`.

    Args:
        board: Game board
        player_id: ID of player applying the map;
                   must be a nonempty string of alphanumeric or underscore characters
        f: Mathematical function from cards to cards (async callable)

    Returns:
        The state of the board after the replacement from the perspective of player_id,
        in the format described in the ps4 handout
    """
    return await board.map_cards(player_id, f)


async def watch(board: Board, player_id: str) -> str:
    """
    Watches the board for a change, waiting until any cards turn face up or face down,
    are removed from the board, or change from one string to a different string.

    Args:
        board: A Memory Scramble board
        player_id: ID of player watching the board;
                   must be a nonempty string of alphanumeric or underscore characters

    Returns:
        The updated state of the board from the perspective of player_id, in the
        format described in the ps4 handout
    """
    # Watch returns empty string as placeholder, need to get actual board state after
    await board.watch(player_id)
    return await board.look(player_id)