import asyncio
import re
from typing import Optional, Set
from dataclasses import dataclass
from enum import Enum


class CardState(Enum):
    """State of a card on the board."""
    DOWN = "down"  # Face down
    UP = "up"  # Face up, not controlled
    CONTROLLED = "controlled"  # Face up and controlled by a player


@dataclass
class Card:
    """Represents a card with its value and state."""
    value: str
    state: CardState
    controller: Optional[str] = None  # Player ID who controls this card

@dataclass
class PlayerState:
    """Tracks a player's current game state."""
    first_card: Optional[tuple[int, int]] = None  # (row, col) of first card (currently controlled)
    second_card: Optional[tuple[int, int]] = None  # (row, col) of second card (currently controlled)
    matched: bool = False  # Whether the last pair matched
    # Positions of cards that were relinquished after a mismatch and left face-up.
    pending_first_card: Optional[tuple[int, int]] = None
    pending_second_card: Optional[tuple[int, int]] = None


class Board:
    """
    Mutable and concurrency-safe Memory Scramble game board.

    A Board represents a grid of cards that players can flip over to find matches.
    Multiple players can interact with the board concurrently.
    """

    def __init__(self, rows: int, cols: int, cards: list[str]):
        """
        Create a new board with the given dimensions and cards.

        Args:
            rows: Number of rows in the board (positive integer)
            cols: Number of columns in the board (positive integer)
            cards: List of card values, must have exactly rows*cols elements
        """
        self._rows = rows
        self._cols = cols

        # Initialize board with face-down cards
        self._board: list[list[Optional[Card]]] = []
        card_idx = 0
        for r in range(rows):
            row = []
            for c in range(cols):
                if card_idx < len(cards):
                    row.append(Card(cards[card_idx], CardState.DOWN))
                    card_idx += 1
                else:
                    row.append(None)
            self._board.append(row)

        # Track player states
        self._players: dict[str, PlayerState] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Condition variable for waiting players
        self._card_available: dict[tuple[int, int], asyncio.Condition] = {}

        # Watchers waiting for board changes
        self._watchers: Set[asyncio.Future] = set()

        self._check_rep()

    def _check_rep(self) -> None:
        """Check that the representation invariant is maintained."""
        assert self._rows > 0, "Board must have positive rows"
        assert self._cols > 0, "Board must have positive columns"
        assert len(self._board) == self._rows, "Board row count mismatch"

        for row in self._board:
            assert len(row) == self._cols, "Board column count mismatch"
            for card in row:
                if card is not None:
                    assert isinstance(card, Card), "Invalid card type"
                    assert card.value and not re.search(r'[\s\n\r]', card.value), \
                        "Card value must be non-empty and contain no whitespace"
                    if card.state == CardState.CONTROLLED:
                        assert card.controller is not None, "Controlled card must have controller"
                    if card.state != CardState.CONTROLLED:
                        assert card.controller is None, "Uncontrolled card should not have controller"

        # Check that controlled cards match player states
        for player_id, state in self._players.items():
            if state.first_card:
                r, c = state.first_card
                card = self._board[r][c]
                assert card is not None, "Player's first card is None"
                assert card.state == CardState.CONTROLLED, "Player's first card not controlled"
                assert card.controller == player_id, "Player's first card controller mismatch"

            if state.second_card:
                r, c = state.second_card
                card = self._board[r][c]
                assert card is not None, "Player's second card is None"
                assert card.state == CardState.CONTROLLED, "Player's second card not controlled"
                assert card.controller == player_id, "Player's second card controller mismatch"

    async def look(self, player_id: str) -> str:
        """
        Get the current state of the board from a player's perspective.

        Args:
            player_id: ID of the player looking at the board

        Returns:
            String representation of the board state
        """
        async with self._lock:
            self._check_rep()
            return self._format_board(player_id)

    def _format_board(self, player_id: str) -> str:
        """Format the board state as a string for the given player."""
        lines = [f"{self._rows}x{self._cols}"]

        for row in self._board:
            for card in row:
                if card is None:
                    lines.append("none")
                elif card.state == CardState.DOWN:
                    lines.append("down")
                elif card.state == CardState.CONTROLLED and card.controller == player_id:
                    lines.append(f"my {card.value}")
                else:  # UP or CONTROLLED by someone else
                    lines.append(f"up {card.value}")

        return "\n".join(lines)

    async def flip(self, player_id: str, row: int, col: int) -> str:
        """Flip a card for a player, following rules 1-A to 2-E, 3-A/B."""
        if not (0 <= row < self._rows and 0 <= col < self._cols):
            raise ValueError(f"Invalid position ({row}, {col})")

        async with self._lock:
            if player_id not in self._players:
                self._players[player_id] = PlayerState()
            player_state = self._players[player_id]

            # If the player has a previous completed pair stored, finish its cleanup
            if player_state.first_card is not None and player_state.second_card is not None:
                await self._cleanup_previous_move(player_id)

            # If the player has pending relinquished cards (from a previous mismatch),
            # and they are starting a new move (no current controlled first_card),
            # turn those pending face-up cards back down now.
            if player_state.first_card is None and (
                    player_state.pending_first_card or player_state.pending_second_card):
                for pos in [player_state.pending_first_card, player_state.pending_second_card]:
                    if pos:
                        r, c = pos
                        # card may have been removed meanwhile
                        if 0 <= r < self._rows and 0 <= c < self._cols:
                            card = self._board[r][c]
                            if card and card.state == CardState.UP:
                                card.state = CardState.DOWN
                                card.controller = None
                                if pos in self._card_available:
                                    self._card_available[pos].notify_all()
                player_state.pending_first_card = None
                player_state.pending_second_card = None

            card = self._board[row][col]

            # Rule 1-A / 2-A: Check card exists
            if card is None:
                if player_state.first_card:
                    self._relinquish_card(player_state.first_card)
                    player_state.first_card = None
                raise ValueError("No card at this position")

            # First card flip
            if player_state.first_card is None:
                pos = (row, col)

                # Wait if controlled by another player, and re-check if the card was removed
                while True:
                    card = self._board[row][col]
                    if card is None:
                        # Card disappeared while waiting -> fail as per Rule 2-A
                        if player_state.first_card:
                            self._relinquish_card(player_state.first_card)
                            player_state.first_card = None
                        raise ValueError("No card at this position")

                    if not (card.state == CardState.CONTROLLED and card.controller != player_id):
                        break

                    if pos not in self._card_available:
                        self._card_available[pos] = asyncio.Condition(self._lock)
                    await self._card_available[pos].wait()

                # Take control (Rule 1-B / 1-C)
                card.state = CardState.CONTROLLED
                card.controller = player_id
                player_state.first_card = pos

                self._notify_watchers()
                self._check_rep()
                return self._format_board(player_id)

            # Second card flip
            first_pos = player_state.first_card
            first_card = self._board[first_pos[0]][first_pos[1]]

            # Cannot flip same card twice
            if (row, col) == first_pos:
                raise ValueError("Cannot flip the same card twice")

            card = self._board[row][col]
            if card is None:
                self._relinquish_card(first_pos)
                player_state.first_card = None
                raise ValueError("No card at this position")

            # Rule 2-B: If card is controlled by a player, fail (no waiting)
            if card.state == CardState.CONTROLLED:
                self._relinquish_card(first_pos)
                # Store the relinquished card so it gets turned down on next first flip
                player_state.first_card = None
                player_state.pending_first_card = first_pos
                raise ValueError("Card is controlled by another player")

            # Turn face up if needed (Rule 2-C)
            if card.state == CardState.DOWN:
                card.state = CardState.UP

            # Now control the second card
            card.state = CardState.CONTROLLED
            card.controller = player_id
            player_state.second_card = (row, col)

            # Match check (Rule 2-D / 2-E)
            if first_card.value == card.value:
                player_state.matched = True
            else:
                # 2-E: Mismatch - relinquish both cards, remember their positions as pending
                self._relinquish_card(first_pos)
                self._relinquish_card((row, col))
                # Clear controlled references (cards are no longer controlled)
                player_state.first_card = None
                player_state.second_card = None
                # Save pending positions so they'll be turned down on next first flip
                player_state.pending_first_card = first_pos
                player_state.pending_second_card = (row, col)
                player_state.matched = False

            self._notify_watchers()
            self._check_rep()
            return self._format_board(player_id)

    def _remove_card(self, pos: tuple):
        """Remove a card from the board."""
        r, c = pos
        if 0 <= r < len(self._board) and 0 <= c < len(self._board[0]):
            self._board[r][c] = None

    async def _cleanup_previous_move(self, player_id: str):
        """Cleanup after previous move (must be called within lock)."""
        state = self._players[player_id]

        if state.matched and state.first_card and state.second_card:
            # 3-A: Remove matched cards
            r1, c1 = state.first_card
            r2, c2 = state.second_card

            # Notify waiting players before removing cards
            for pos in [state.first_card, state.second_card]:
                if pos in self._card_available:
                    self._card_available[pos].notify_all()

            self._board[r1][c1] = None
            self._board[r2][c2] = None
            state.first_card = None
            state.second_card = None
            state.matched = False
        elif state.first_card or state.second_card:
            # 3-B: Turn down unmatched cards
            for pos in [state.first_card, state.second_card]:
                if pos:
                    r, c = pos
                    card = self._board[r][c]
                    if card:
                        card.state = CardState.DOWN
                        card.controller = None
                        # Notify waiting players that this card is now available
                        if pos in self._card_available:
                            self._card_available[pos].notify_all()
            state.first_card = None
            state.second_card = None

    def _relinquish_card(self, pos: tuple[int, int]):
        """Relinquish control of a card (must be called within lock)."""
        row, col = pos
        card = self._board[row][col]
        if card and card.state == CardState.CONTROLLED:
            card.state = CardState.UP
            card.controller = None
            # Notify waiting players
            if pos in self._card_available:
                self._card_available[pos].notify_all()

    def _notify_watchers(self):
        """Notify watchers with actual board state."""
        for watcher in self._watchers:
            if not watcher.done():
                watcher.set_result("")  # can update with actual board if needed
        self._watchers.clear()

    async def watch(self, player_id: str) -> str:
        future = asyncio.Future()
        async with self._lock:
            self._watchers.add(future)
        try:
            await future
            async with self._lock:
                return self._format_board(player_id)
        finally:
            async with self._lock:
                self._watchers.discard(future)

    @staticmethod
    async def parse_from_file(filename: str) -> 'Board':
        """
        Create a new board by parsing a file.

        Args:
            filename: Path to game board file

        Returns:
            A new board with the size and cards from the file

        Raises:
            ValueError: If the file format is invalid
            FileNotFoundError: If the file cannot be read
        """
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.strip().split('\n')

        if len(lines) < 1:
            raise ValueError("Empty board file")

        # Parse dimensions
        dimensions = lines[0].strip()
        match = re.match(r'^(\d+)x(\d+)$', dimensions)
        if not match:
            raise ValueError(f"Invalid dimensions format: {dimensions}")

        rows = int(match.group(1))
        cols = int(match.group(2))

        # Parse cards
        cards = []
        for line in lines[1:]:
            card = line.strip()
            if card and not re.search(r'[\s\n\r]', card):
                cards.append(card)

        expected_cards = rows * cols
        if len(cards) != expected_cards:
            raise ValueError(f"Expected {expected_cards} cards, got {len(cards)}")

        return Board(rows, cols, cards)