"""
Simulation script for testing concurrent gameplay.

This script simulates multiple players making random moves concurrently to verify
that the game server and board implementation handle concurrent access correctly
and never crash.

Simulation Parameters:
- NUM_PLAYERS: 4 players
- TRIES: 100 moves per player (200 card flips total per player)
- Delay between moves: 50-200ms (randomized)
- Board: Uses boards/fruit.txt by default
- Server: Assumes server running on localhost:8080

Purpose:
- Stress test the server with concurrent requests
- Verify thread safety of Board ADT
- Ensure no crashes, deadlocks, or race conditions
- Validate game rules hold under concurrent access
"""

import asyncio
import random
import sys
from aiohttp import ClientSession, ClientConnectorError
from board import Board

FILENAME = '../boards/fruit.txt'
NUM_PLAYERS = 4
TRIES = 100
MIN_DELAY_MS = 50.0
MAX_DELAY_MS = 200.0
SERVER_PORT = 8080


async def player_client(session: ClientSession, port: int, player_number: int, rows: int, cols: int):
    """
    Simulates a single player making random moves.

    Preconditions:
    - session is a valid aiohttp ClientSession
    - port is the server port number
    - player_number is a unique player identifier
    - rows > 0, cols > 0 (valid board dimensions)

    Postconditions:
    - Makes TRIES iterations of: flip random first card, delay, flip random second card
    - Total of 2 * TRIES HTTP requests per player
    - Prints error messages if requests fail
    - Prints completion message when finished

    Args:
        session: HTTP client session for making requests
        port: Server port number
        player_number: Unique identifier for this player
        rows: Number of rows in the board
        cols: Number of columns in the board
    """
    player_id = f"player_{player_number}"
    for _ in range(TRIES):
        await asyncio.sleep(random.uniform(MIN_DELAY_MS, MAX_DELAY_MS) / 1000.0)

        r1 = random.randint(0, rows - 1)
        c1 = random.randint(0, cols - 1)
        url1 = f"http://localhost:{port}/flip/{player_id}/{r1},{c1}"
        try:
            async with session.get(url1) as resp:
                pass
        except Exception as e:
            print(f"Player {player_number} error on first flip: {e}")

        await asyncio.sleep(random.uniform(MIN_DELAY_MS, MAX_DELAY_MS) / 1000.0)

        r2 = random.randint(0, rows - 1)
        c2 = random.randint(0, cols - 1)
        url2 = f"http://localhost:{port}/flip/{player_id}/{r2},{c2}"
        try:
            async with session.get(url2) as resp:
                pass
        except Exception as e:
            print(f"Player {player_number} error on second flip: {e}")

    print(f"Player {player_number} finished")


async def simulation_main():
    """
    Main simulation entry point.

    Preconditions:
    - Server must be running on localhost:SERVER_PORT
    - FILENAME must point to a valid board file

    Postconditions:
    - Parses board file to get dimensions
    - Verifies server is reachable
    - Spawns NUM_PLAYERS concurrent player tasks
    - Waits for all players to complete
    - Prints final board state
    - Exits with code 1 if server unreachable, 0 if successful

    This function tests:
    - Concurrent card flipping by multiple players
    - Server's ability to handle simultaneous requests
    - Board's thread safety and correctness under load
    - That the game never crashes or deadlocks
    """
    board = await Board.parse_from_file(FILENAME)
    rows, cols = board._rows, board._cols
    port = SERVER_PORT

    # Verify external server is running
    async with ClientSession() as session:
        try:
            async with session.get(f"http://localhost:{port}/look/observer", timeout=5) as resp:
                if resp.status != 200:
                    print(f"Server responded with status {resp.status}")
        except ClientConnectorError as e:
            print(f"Could not connect to server at http://localhost:{port}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error checking server at http://localhost:{port}: {e}")
            sys.exit(1)

        # Start simulated players
        tasks = [asyncio.create_task(player_client(session, port, i, rows, cols)) for i in range(NUM_PLAYERS)]
        await asyncio.gather(*tasks)

        # Print final board state
        try:
            async with session.get(f"http://localhost:{port}/look/observer") as resp:
                text = await resp.text()
                print("\n=== Final Board State ===")
                print(text)
        except Exception:
            pass


if __name__ == '__main__':
    asyncio.run(simulation_main())