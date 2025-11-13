# Network Programming

### Lab 3 - Multiplayer Memory Game
### Miricinschi Gabriel

## Overview

This is a multiplayer implementation of the Memory card game where multiple players can concurrently flip cards to find matching pairs. The game follows specific concurrency rules allowing players to wait for cards controlled by others and handles complex scenarios like deadlock prevention.

## Running the Server

### Prerequisites
- Python 3.13+
- Required packages listed in `requirements.txt`

Install dependencies:
```bash
pip install -r requirements.txt
```

### Start the Server

```bash
python src/server.py <PORT> <BOARD_FILE>
```
**Arguments:**
- `PORT`: Integer port number (use `0` for random port assignment)
- `BOARD_FILE`: Path to game board file (e.g., `boards/perfect.txt`)

**Example:**
```bash
python src/server.py 8080 boards/perfect.txt
```

The server will start and display:
```
server now listening at http://localhost:8080
```

### Access the Game

Open your browser and navigate to:
```
http://localhost:8080
```

The web interface (`public/index.html`) will be served automatically.

## Running Tests

Run all unit tests for the Board ADT:
```bash
python -m pytest test/board_test.py -v
```

Run specific test:
```bash
python -m pytest test/board_test.py::test_flip_matching_pair -v
```

## Running the Simulation

The simulation script spawns multiple concurrent players making random moves to verify the game doesn't crash under concurrent access.

**Simulation Parameters:**
- **Players:** 4
- **Moves per player:** 100
- **Delay between moves:** 0.1-2ms (randomized)
- **Board:** Uses `boards/fruit.txt` by default

**Run the simulation:**
```bash
python src/simulation.py
```

**Note:** Make sure the server is running on port 8080 before starting the simulation.

The simulation will output player progress and the final board state.

## Project Structure

```
PR/
├── src/
│   ├── board.py          # Board ADT with game logic
│   ├── commands.py       # Command layer for board operations
│   ├── server.py         # HTTP server with REST API
│   └── simulation.py     # Multi-player simulation script
├── test/
│   └── board_test.py     # Unit tests for Board ADT (17 tests)
├── boards/
│   ├── perfect.txt       # 3x3 board for testing
│   ├── ab.txt            # Small test board
│   ├── fruit.txt         # Larger game board
│   └── zoom.txt          # Another test board
├── public/
│   └── index.html        # Web frontend
├── requirements.txt      # Python dependencies
└── README.md
```
### Tests (`test/board_test.py`)

**17 comprehensive unit tests (all passing):**

1. `test_board_initialization` - Test that a board is initialized correctly with all cards face down.
2. `test_parse_from_file` - Test parsing a board from a file.
3. `test_flip_first_card_face_down` - Rule 1-B: Face-down card turns face up and player controls it.
4. `test_flip_face_up_uncontrolled_card_as_first` - Rule 1-C: Player can take control of a face-up uncontrolled card as first flip.
5. `test_wait_for_controlled_card_as_first_flip` - Rule 1-D: Player waits for controlled card, can take it after relinquish.
6. `test_flip_empty_space_fails` - Rule 1-A: Flipping an empty space fails.
7. `test_first_card_relinquished_on_empty_second_flip` - Rule 2-A: First card relinquished when second flip hits empty space.
8. `test_player_continues_after_second_flip_failure` - Rule 2-A/2-B: Player can continue playing after second flip failure.
9. `test_flip_controlled_card_second_flip_fails` - Rule 2-B: Flipping a controlled card as second flip fails.
10. `test_flip_matching_pair` - Rule 2-D: Matching pair - player keeps control of both cards.
11. `test_flip_non_matching_pair` - Rule 2-E: Non-matching pair - player relinquishes control, cards stay face up.
12. `test_matched_cards_stay_until_next_move` - Rule 3-A: Matched cards stay on board until next first flip, then removed.
13. `test_mismatched_cards_stay_up_until_next_move` - Rule 3-B: Mismatched cards stay face up until next first flip, then turned down.
14. `test_relinquished_card_stays_up_if_controlled` - Rule 3-B: Relinquished cards stay face-up if controlled by another player.
15. `test_multiple_players_concurrent` - Test multiple players playing concurrently with separate first cards.
16. `test_concurrent_matches_and_removals` - Test multiple players making concurrent matches and removals.
17. `test_flip_same_card_twice_fails` - Test that flipping the same card twice in one turn fails.

**PASSED TESTS:**
<img width="769" height="542" alt="Image" src="https://github.com/user-attachments/assets/54bc9981-af3b-4510-8ed4-26b06b73f4f3" />

## Game Rules

### Informal Summary
1. When a player turns over a first card, they control that card; if someone else already controls it, the player waits until they can take control.
2. When the player turns over a second card, if the cards match, the player keeps control of them; otherwise, the player gives up control. The cards stay face up for now.
3. When the player makes their next move, if their previous cards matched, those cards are removed from the board; otherwise, if no one controls them, they turn face down.

### Complete Rules

**First card (Rules 1-A through 1-D):**
- **1-A:** If there is no card there, the operation fails.
- **1-B:** If the card is face down, it turns face up and the player controls it.
- **1-C:** If the card is already face up but not controlled, the player controls it.
- **1-D:** If the card is face up and controlled by another player, the operation waits.

**Second card (Rules 2-A through 2-E):**
- **2-A:** If there is no card there, the operation fails. The player relinquishes control of their first card.
- **2-B:** If the card is controlled by a player, the operation fails (no waiting to avoid deadlocks). The player relinquishes control of their first card.
- **2-C:** If it is face down, it turns face up.
- **2-D:** If the two cards match, the player keeps control of both cards.
- **2-E:** If they don't match, the player relinquishes control of both cards (they remain face up).

**Cleanup (Rules 3-A and 3-B):**
- **3-A:** If the player had a matching pair, those cards are removed from the board when they flip a new first card.
- **3-B:** Otherwise, for each non-matching card that is still on the board, face up, and not controlled by another player, the card is turned face down.