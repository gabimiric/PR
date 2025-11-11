import pytest
from src.board import Board

@pytest.mark.asyncio
async def test_board_initialization():
    """Test that a board is initialized correctly with all cards face down."""
    board = await Board.parse_from_file("boards/perfect.txt")

    assert board._rows == 3
    assert board._cols == 3

    # All cards should be face down initially
    result = await board.look("player1")
    lines = result.split("\n")
    assert lines[0] == "3x3"
    assert all(line == "down" for line in lines[1:])

@pytest.mark.asyncio
async def test_parse_from_file():
    """Test parsing a board from a file."""
    board = await Board.parse_from_file("boards/perfect.txt")

    result = await board.look("observer")
    lines = result.split("\n")

    # Check dimensions
    assert "x" in lines[0]
    rows, cols = map(int, lines[0].split("x"))
    assert rows == 3
    assert cols == 3

    # Check all cards are face down initially
    assert all(line == "down" for line in lines[1:])


@pytest.mark.asyncio
async def test_flip_first_card_face_down():
    """Rule 1-B: Face-down card turns face up and player controls it."""
    board = await Board.parse_from_file("boards/perfect.txt")

    result = await board.flip("player1", 0, 0)
    lines = result.split("\n")

    # Card should be face up and controlled by player1 (first card is 🦄)
    assert lines[1] == "my 🦄"
    assert lines[2] == "down"  # Other cards still down

@pytest.mark.asyncio
async def test_flip_face_up_uncontrolled_card_as_first():
    """Rule 1-C: Player can take control of a face-up uncontrolled card as first flip."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 flips two non-matching cards and relinquishes them
    await board.flip("player1", 0, 0)  # 🦄
    await board.flip("player1", 0, 2)  # 🌈 (mismatch, cards stay face up)

    # Player2 can now take control of the face-up uncontrolled card
    result = await board.flip("player2", 0, 0)
    lines = result.split("\n")

    # Player2 should control the card
    assert "my 🦄" in lines[1]

@pytest.mark.asyncio
async def test_wait_for_controlled_card_as_first_flip():
    """Rule 1-D: Player waits for controlled card, can take it after relinquish."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 controls a card
    await board.flip("player1", 0, 0)  # 🦄

    # Player2 will wait for the same card - we'll test this by checking they can take it after relinquish
    # First, player1 relinquishes by flipping a non-matching second card
    await board.flip("player1", 0, 2)  # 🌈 (mismatch)

    # Now player2 can take control (it's face up and uncontrolled)
    result = await board.flip("player2", 0, 0)
    lines = result.split("\n")
    assert "my 🦄" in lines[1]


@pytest.mark.asyncio
async def test_first_card_relinquished_on_empty_second_flip():
    """Rule 2-A: First card relinquished when second flip hits empty space."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 matches and removes a pair (🦄 at positions 0,0 and 0,1)
    await board.flip("player1", 0, 0)  # 🦄
    await board.flip("player1", 0, 1)  # 🦄 (match)
    await board.flip("player1", 1, 0)  # Trigger removal

    # Player2 flips a card, then tries to flip the empty space
    await board.flip("player2", 2, 2)  # 🌈
    with pytest.raises(ValueError, match="No card at this position"):
        await board.flip("player2", 0, 0)

    # First card should be relinquished but face up
    result = await board.look("player2")
    lines = result.split("\n")
    assert "up 🌈" in lines[9]

@pytest.mark.asyncio
async def test_player_continues_after_second_flip_failure():
    """Rule 2-A/2-B: Player can continue playing after second flip failure."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 controls a card
    await board.flip("player1", 0, 0)  # 🦄

    # Player2 flips first card
    await board.flip("player2", 0, 2)  # 🌈

    # Player2 tries to flip player1's controlled card - should fail
    with pytest.raises(ValueError, match="Card is controlled"):
        await board.flip("player2", 0, 0)

    # Player2 should be able to continue playing with a new first flip
    result = await board.flip("player2", 1, 1)  # 🌈
    lines = result.split("\n")
    assert "my 🌈" in lines[5]

@pytest.mark.asyncio
async def test_flip_matching_pair():
    """Rule 2-D: Matching pair - player keeps control of both cards."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Flip first card (🦄 at 0,0)
    await board.flip("player1", 0, 0)

    # Flip matching second card (🦄 at 0,1)
    result = await board.flip("player1", 0, 1)
    lines = result.split("\n")

    # Both cards should be controlled by player1
    assert "my 🦄" in lines[1]
    assert "my 🦄" in lines[2]

@pytest.mark.asyncio
async def test_flip_non_matching_pair():
    """Rule 2-E: Non-matching pair - player relinquishes control, cards stay face up."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Flip first card (🦄)
    await board.flip("player1", 0, 0)

    # Flip non-matching second card (🌈)
    result = await board.flip("player1", 0, 2)
    lines = result.split("\n")

    # Cards should be face up but not controlled (relinquished)
    assert "up 🦄" in lines[1]
    assert "up 🌈" in lines[3]


@pytest.mark.asyncio
async def test_matched_cards_stay_until_next_move():
    """Rule 3-A: Matched cards stay on board until next first flip, then removed."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 matches a pair (🦄 at 0,0 and 0,1)
    await board.flip("player1", 0, 0)  # 🦄
    result = await board.flip("player1", 0, 1)  # 🦄 (match)
    lines = result.split("\n")

    # Cards should still be on board and controlled
    assert "my 🦄" in lines[1]
    assert "my 🦄" in lines[2]

    # Only when player1 flips a new first card are they removed
    result = await board.flip("player1", 0, 2)  # 🌈
    lines = result.split("\n")
    assert lines[1] == "none"
    assert lines[2] == "none"

@pytest.mark.asyncio
async def test_mismatched_cards_stay_up_until_next_move():
    """Rule 3-B: Mismatched cards stay face up until next first flip, then turned down."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 flips non-matching pair
    await board.flip("player1", 0, 0)  # 🦄
    result = await board.flip("player1", 0, 2)  # 🌈 (mismatch)
    lines = result.split("\n")

    # Cards should be face up but not controlled
    assert "up 🦄" in lines[1]
    assert "up 🌈" in lines[3]

    # Only when player1 flips a new first card are they turned down
    await board.flip("player1", 1, 0)  # 🌈
    result = await board.look("player1")
    lines = result.split("\n")
    assert lines[1] == "down"
    assert lines[3] == "down"

@pytest.mark.asyncio
async def test_relinquished_card_stays_up_if_controlled():
    """Rule 3-B: Relinquished cards stay face-up if controlled by another player."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 flips non-matching pair and relinquishes
    await board.flip("player1", 0, 0)  # 🦄
    await board.flip("player1", 0, 2)  # 🌈 (mismatch, relinquished, face up)

    # Player2 takes control of one of player1's relinquished cards
    await board.flip("player2", 0, 0)  # 🦄

    # Player1 starts new move - their relinquished card at (0, 0) should stay face up (controlled by player2)
    result = await board.flip("player1", 1, 0)  # 🌈
    lines = result.split("\n")

    # Position (0, 0) should still be face up (controlled by player2)
    # Position (0, 2) should be face down (uncontrolled and was relinquished)
    assert "up 🦄" in lines[1]  # player1 sees player2's card
    assert lines[3] == "down"


@pytest.mark.asyncio
async def test_flip_empty_space_fails():
    """Rule 1-A: Flipping an empty space fails."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Match and remove a pair (🦄 at 0,0 and 0,1)
    await board.flip("player1", 0, 0)
    await board.flip("player1", 0, 1)
    await board.flip("player1", 0, 2)  # Trigger removal

    # Try to flip the removed card position
    with pytest.raises(ValueError, match="No card at this position"):
        await board.flip("player2", 0, 0)

@pytest.mark.asyncio
async def test_flip_controlled_card_second_flip_fails():
    """Rule 2-B: Flipping a controlled card as second flip fails."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 flips first card
    await board.flip("player1", 0, 0)  # 🦄

    # Player2 flips first card
    await board.flip("player2", 0, 2)  # 🌈

    # Player2 tries to flip player1's controlled card as second - should fail
    with pytest.raises(ValueError, match="Card is controlled"):
        await board.flip("player2", 0, 0)

@pytest.mark.asyncio
async def test_multiple_players_concurrent():
    """Test multiple players playing concurrently with separate first cards."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 makes a move
    await board.flip("player1", 0, 0)  # 🦄

    # Player2 makes a move
    await board.flip("player2", 0, 2)  # 🌈

    # Both should see their own cards as "my" and others as "up"
    result1 = await board.look("player1")
    result2 = await board.look("player2")

    assert "my 🦄" in result1
    assert "up 🌈" in result1

    assert "my 🌈" in result2
    assert "up 🦄" in result2

@pytest.mark.asyncio
async def test_concurrent_matches_and_removals():
    """Test multiple players making concurrent matches and removals."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Player1 matches first pair (🦄 at 0,0 and 0,1)
    await board.flip("player1", 0, 0)  # 🦄
    await board.flip("player1", 0, 1)  # 🦄 (match)

    # Player2 matches second pair (🌈 at 0,2 and 1,0)
    await board.flip("player2", 0, 2)  # 🌈
    await board.flip("player2", 1, 0)  # 🌈 (match)

    # Player1 starts new move - their match should be removed
    await board.flip("player1", 1, 1)  # 🌈
    result1 = await board.look("player1")
    lines1 = result1.split("\n")
    assert lines1[1] == "none"
    assert lines1[2] == "none"

    # Player2 starts new move - their match should be removed
    await board.flip("player2", 1, 2)  # 🦄
    result2 = await board.look("player2")
    lines2 = result2.split("\n")
    assert lines2[3] == "none"
    assert lines2[4] == "none"

@pytest.mark.asyncio
async def test_flip_same_card_twice_fails():
    """Test that flipping the same card twice in one turn fails."""
    board = await Board.parse_from_file("boards/perfect.txt")

    # Flip first card
    await board.flip("player1", 0, 0)  # 🦄

    # Try to flip same card as second
    with pytest.raises(ValueError, match="Cannot flip the same card twice"):
        await board.flip("player1", 0, 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

