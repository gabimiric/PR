import asyncio
import random
from board import Board
from commands import flip, look


async def simulation_main():
    """
    Run a simulation of the Memory Scramble game with concurrent players.
    
    Raises:
        Exception: If an error occurs reading or parsing the board
    """
    filename = '../boards/ab.txt'
    board = await Board.parse_from_file(filename)
    
    size = 5
    num_players = 3
    tries = 10
    max_delay_milliseconds = 100
    
    # Start up one or more players as concurrent asynchronous tasks
    player_tasks = []
    for player_num in range(num_players):
        player_tasks.append(asyncio.create_task(player(board, player_num, size, tries, max_delay_milliseconds)))
    
    # Wait for all the players to finish (unless one throws an exception)
    await asyncio.gather(*player_tasks)
    
    # Display final board state
    print("\n=== Final Board State ===")
    final_state = await look(board, "observer")
    print(final_state)
    print("=== Simulation Complete ===")


async def player(board: Board, player_number: int, size: int, tries: int, max_delay: float):
    """
    Simulate a single player making random moves.
    
    Args:
        board: The game board
        player_number: Unique identifier for this player
        size: Size of the board (assumed square)
        tries: Number of flip attempts to make
        max_delay: Maximum delay in milliseconds between moves
    """
    player_id = f"player_{player_number}"
    print(f"Player {player_number} starting...")
    
    for attempt in range(tries):
        try:
            # Random delay before first flip
            await timeout(random.random() * max_delay)
            
            # Try to flip over a first card at random position
            row1 = random_int(size)
            col1 = random_int(size)
            
            print(f"Player {player_number} attempting flip at ({row1}, {col1})")
            board_state = await flip(board, player_id, row1, col1)
            print(f"Player {player_number} first flip succeeded")
            
            # Random delay before second flip
            await timeout(random.random() * max_delay)
            
            # Try to flip over a second card at random position
            row2 = random_int(size)
            col2 = random_int(size)
            
            print(f"Player {player_number} attempting second flip at ({row2}, {col2})")
            board_state = await flip(board, player_id, row2, col2)
            print(f"Player {player_number} second flip succeeded")
            
        except ValueError as err:
            print(f"Player {player_number} flip failed: {err}")
        except Exception as err:
            print(f"Player {player_number} unexpected error: {err}")
    
    print(f"Player {player_number} finished")


def random_int(max_val: int) -> int:
    """
    Generate a random positive integer.
    
    Args:
        max_val: A positive integer which is the upper bound of the generated number
        
    Returns:
        A random integer >= 0 and < max_val
    """
    return random.randint(0, max_val - 1)


async def timeout(milliseconds: float) -> None:
    """
    Wait for a specified duration.
    
    Args:
        milliseconds: Duration to wait in milliseconds
    """
    await asyncio.sleep(milliseconds / 1000.0)


if __name__ == '__main__':
    asyncio.run(simulation_main())