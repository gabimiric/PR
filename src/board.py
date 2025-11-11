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
    first_card: Optional[tuple[int, int]] = None  # (row, col) of first card
    second_card: Optional[tuple[int, int]] = None  # (row, col) of second card
    matched: bool = False  # Whether the last pair matched


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
        """
        Flip a card at the given position following game rules.
        
        Args:
            player_id: ID of the player making the flip
            row: Row index of card to flip
            col: Column index of card to flip
            
        Returns:
            Updated board state from player's perspective
            
        Raises:
            ValueError: If the flip operation fails
        """
        # Validate position
        if not (0 <= row < self._rows and 0 <= col < self._cols):
            raise ValueError(f"Invalid position ({row}, {col})")

        async with self._lock:
            # Initialize player state if needed
            if player_id not in self._players:
                self._players[player_id] = PlayerState()

            player_state = self._players[player_id]

            # Handle cleanup from previous move (rules 3-A and 3-B)
            await self._cleanup_previous_move(player_id)

            card = self._board[row][col]

            # Rule 1-A: No card at this position
            if card is None:
                raise ValueError("No card at this position")

            # First card flip
            if player_state.first_card is None:
                # Rule 1-D: Wait if card is controlled by another player
                while card.state == CardState.CONTROLLED and card.controller != player_id:
                    # Set up condition variable if not exists
                    pos = (row, col)
                    if pos not in self._card_available:
                        self._card_available[pos] = asyncio.Condition(self._lock)

                    condition = self._card_available[pos]
                    await condition.wait()

                    # Re-check card state after waiting
                    card = self._board[row][col]
                    if card is None:
                        raise ValueError("Card was removed while waiting")

                # Rule 1-B and 1-C: Take control of the card
                card.state = CardState.CONTROLLED
                card.controller = player_id
                player_state.first_card = (row, col)

                self._notify_watchers()
                self._check_rep()
                return self._format_board(player_id)

            # Second card flip
            else:
                # Rule 2-A: No card at this position
                if card is None:
                    # Relinquish control of first card
                    self._relinquish_card(player_state.first_card)
                    player_state.first_card = None
                    self._notify_watchers()
                    self._check_rep()
                    raise ValueError("No card at this position")

                # Rule 2-B: Card is controlled (deadlock avoidance)
                if card.state == CardState.CONTROLLED:
                    # Relinquish control of first card
                    self._relinquish_card(player_state.first_card)
                    player_state.first_card = None
                    self._notify_watchers()
                    self._check_rep()
                    raise ValueError("Card is already controlled")

                # Rule 2-C: Turn card face up if needed
                if card.state == CardState.DOWN:
                    card.state = CardState.UP

                # Get first card
                first_row, first_col = player_state.first_card
                first_card = self._board[first_row][first_col]

                # Rule 2-D and 2-E: Check for match
                if first_card.value == card.value:
                    # Matching pair! Take control of second card
                    card.state = CardState.CONTROLLED
                    card.controller = player_id
                    player_state.second_card = (row, col)
                    player_state.matched = True
                else:
                    # No match - relinquish control of both
                    self._relinquish_card(player_state.first_card)
                    player_state.first_card = None
                    player_state.matched = False

                self._notify_watchers()
                self._check_rep()
                return self._format_board(player_id)

    async def _cleanup_previous_move(self, player_id: str) -> None:
        """Clean up cards from player's previous move (rules 3-A and 3-B)."""
        player_state = self._players[player_id]

        # Rule 3-A: Remove matched pair
        if player_state.matched and player_state.first_card and player_state.second_card:
            self._remove_card(player_state.first_card)
            self._remove_card(player_state.second_card)
            player_state.first_card = None
            player_state.second_card = None
            player_state.matched = False

        # Rule 3-B: Turn down non-matching cards
        elif not player_state.matched:
            if player_state.first_card:
                self._turn_down_if_possible(player_state.first_card)
                player_state.first_card = None
            if player_state.second_card:
                self._turn_down_if_possible(player_state.second_card)
                player_state.second_card = None

    def _relinquish_card(self, position: tuple[int, int]) -> None:
        """Relinquish control of a card, leaving it face up."""
        row, col = position
        card = self._board[row][col]
        if card and card.state == CardState.CONTROLLED:
            card.state = CardState.UP
            card.controller = None

            # Notify waiting players
            if position in self._card_available:
                self._card_available[position].notify_all()

    def _remove_card(self, position: tuple[int, int]) -> None:
        """Remove a card from the board."""
        row, col = position
        self._board[row][col] = None

        # Notify waiting players
        if position in self._card_available:
            self._card_available[position].notify_all()

    def _turn_down_if_possible(self, position: tuple[int, int]) -> None:
        """Turn a card face down if it's not controlled by another player."""
        row, col = position
        card = self._board[row][col]
        if card and card.state == CardState.UP:
            card.state = CardState.DOWN

    async def map_cards(self, player_id: str, f) -> str:
        """
        Replace all cards on the board using function f, maintaining pairwise consistency.
        
        Args:
            player_id: ID of the player applying the map
            f: Async function that maps card values to new card values
            
        Returns:
            Updated board state from player's perspective
        """
        async with self._lock:
            # Build mapping of old values to new values
            card_mapping: dict[str, str] = {}

            for row in self._board:
                for card in row:
                    if card and card.value not in card_mapping:
                        card_mapping[card.value] = await f(card.value)

            # Apply mapping to all cards atomically
            for row in self._board:
                for card in row:
                    if card:
                        card.value = card_mapping[card.value]

            self._notify_watchers()
            self._check_rep()
            return self._format_board(player_id)

    async def watch(self, player_id: str) -> str:
        """
        Wait for a change to the board, then return the updated state.
        
        Args:
            player_id: ID of the player watching
            
        Returns:
            Updated board state after a change occurs
        """
        future: asyncio.Future[str] = asyncio.Future()

        async with self._lock:
            self._watchers.add(future)

        try:
            return await future
        finally:
            async with self._lock:
                self._watchers.discard(future)

    def _notify_watchers(self) -> None:
        """Notify all watchers that the board has changed."""
        for watcher in self._watchers:
            if not watcher.done():
                # Create board state for each watcher
                # Note: We can't determine player_id here, so we'll use empty string
                # The watch command will need to handle this
                watcher.set_result("")
        self._watchers.clear()

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
