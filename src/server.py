"""
HTTP Server for the Memory Game.

This module provides a web server that exposes the game board through a REST API.
It serves the web frontend and handles all HTTP requests by delegating to the commands module.

Module Structure (Required Design):
- WebServer class manages HTTP server lifecycle and routing
- Routes map HTTP endpoints to command functions
- Serves static frontend files (public/index.html)
- Handles CORS for cross-origin requests
- Converts HTTP request parameters to command function arguments
- Returns command results as HTTP responses

Representation Invariant:
- self.board is always a valid Board instance
- self.port is a valid port number (0-65535)
- self.app is a configured aiohttp Application
- When running: self.runner and self.site are not None

Safety from Rep Exposure:
- self.board is private but shared with request handlers (necessary for serving requests)
- No mutable board state is exposed in responses (only string representations)
- HTTP handlers use the commands module as intermediary, never directly manipulate board
- All responses are immutable strings
"""

import sys
import asyncio
from pathlib import Path
from aiohttp import web
from board import Board
from commands import look, flip, map_replace, watch


class WebServer:
    """
    HTTP web game server.

    Manages the web server lifecycle and routes HTTP requests to game commands.
    """

    def __init__(self, board: Board, port: int):
        """
        Create a new web game server.

        Preconditions:
        - board is a valid Board instance
        - 0 <= port <= 65535

        Postconditions:
        - Creates aiohttp Application with routes configured
        - Server is not yet running (call start() to run)
        - Static file serving is configured if public/ directory exists
        - CORS middleware is added

        Args:
            board: Shared game board
            port: Server port number
        """
        self.board = board
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.site = None

        # Set up routes
        self.app.router.add_get('/look/{player_id}', self.handle_look)
        self.app.router.add_get('/flip/{player_id}/{location}', self.handle_flip)
        self.app.router.add_get('/replace/{player_id}/{from_card}/{to_card}', self.handle_replace)
        self.app.router.add_get('/watch/{player_id}', self.handle_watch)

        # Serve static files from public directory
        public_dir = Path(__file__).parent.parent / 'public'
        if public_dir.exists():
            # Serve all static files under /static
            self.app.router.add_static('/static', public_dir)

            # Serve index.html at root /
            async def index(request):
                return web.FileResponse(public_dir / 'index.html')

            self.app.router.add_get('/', index)

        # Add CORS middleware
        @web.middleware
        async def cors_middleware(request, handler):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

        self.app.middlewares.append(cors_middleware)

    async def handle_look(self, request: web.Request) -> web.Response:
        """
        Handle GET /look/<player_id>

        Preconditions:
        - player_id must be a nonempty string of alphanumeric or underscore characters

        Postconditions:
        - Returns 200 OK with board state as plain text
        - Board state is unchanged

        Returns:
            HTTP Response with board state from player_id's perspective
        """
        player_id = request.match_info['player_id']

        board_state = await look(self.board, player_id)
        return web.Response(text=board_state, content_type='text/plain')

    async def handle_flip(self, request: web.Request) -> web.Response:
        """
        Handle GET /flip/<player_id>/<row>,<column>

        Preconditions:
        - player_id must be a nonempty string of alphanumeric or underscore characters
        - row and column must be integers, 0 <= row,column < height,width of board

        Postconditions:
        - If flip succeeds: returns 200 OK with updated board state
        - If location format invalid: returns 400 Bad Request
        - If flip fails (invalid card, controlled, etc.): returns 409 Conflict
        - Board state may be modified if flip succeeds

        Returns:
            HTTP Response with updated board state or error message
        """
        player_id = request.match_info['player_id']
        location = request.match_info['location']

        try:
            row_str, col_str = location.split(',')
            row = int(row_str)
            column = int(col_str)
        except (ValueError, AttributeError):
            return web.Response(
                text=f"Invalid location format: {location}",
                status=400,
                content_type='text/plain'
            )

        try:
            board_state = await flip(self.board, player_id, row, column)
            return web.Response(text=board_state, content_type='text/plain')
        except ValueError as e:
            return web.Response(
                text=f"cannot flip this card: {e}",
                status=409,
                content_type='text/plain'
            )

    async def handle_replace(self, request: web.Request) -> web.Response:
        """
        Handle GET /replace/<player_id>/<oldcard>/<newcard>

        Preconditions:
        - player_id must be a nonempty string of alphanumeric or underscore characters
        - oldcard and newcard must be nonempty strings

        Postconditions:
        - All occurrences of oldcard are replaced with newcard on the board
        - Returns 200 OK with updated board state
        - Board state is modified
        - All watchers are notified

        Returns:
            HTTP Response with updated board state after replacement
        """
        player_id = request.match_info['player_id']
        from_card = request.match_info['from_card']
        to_card = request.match_info['to_card']

        async def replace_function(card: str) -> str:
            return to_card if card == from_card else card

        board_state = await map_replace(self.board, player_id, replace_function)
        return web.Response(text=board_state, content_type='text/plain')

    async def handle_watch(self, request: web.Request) -> web.Response:
        """
        Handle GET /watch/<player_id>

        Preconditions:
        - player_id must be a nonempty string of alphanumeric or underscore characters

        Postconditions:
        - Blocks until the board changes (cards flip, remove, or value changes)
        - Returns 200 OK with updated board state after change occurs
        - Board state unchanged by this operation (only observes changes)
        - Multiple clients can watch concurrently

        Returns:
            HTTP Response with board state after next change
        """
        player_id = request.match_info['player_id']

        board_state = await watch(self.board, player_id)
        return web.Response(text=board_state, content_type='text/plain')

    async def start(self) -> None:
        """
        Start this server.

        Preconditions:
        - Server is not already running
        - self.board and self.port are properly initialized

        Postconditions:
        - Server is running and listening for HTTP connections
        - If port was 0, self.port is updated with actual assigned port
        - Prints confirmation message with server URL
        """
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, 'localhost', self.port)
        await self.site.start()

        # Get the actual port if 0 was specified
        if self.port == 0:
            self.port = self.site._server.sockets[0].getsockname()[1]

        print(f"server now listening at http://localhost:{self.port}")

    async def stop(self) -> None:
        """
        Stop this server.

        Preconditions:
        - None (safe to call even if server not running)

        Postconditions:
        - Server stops accepting new connections
        - Existing connections are cleaned up
        - Prints confirmation message
        """
        if self.runner:
            await self.runner.cleanup()
        print("server stopped")


async def main():
    """
    Main entry point for the server.

    Preconditions:
    - Command line arguments: PORT FILENAME
    - PORT is an integer 0-65535
    - FILENAME is a valid path to a board file

    Postconditions:
    - Parses board from file
    - Creates and starts web server
    - Runs until interrupted (Ctrl+C)
    - Cleans up server on exit
    """
    if len(sys.argv) < 3:
        print("Usage: python server.py PORT FILENAME")
        print("  PORT: integer port number (0 for random)")
        print("  FILENAME: path to game board file")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1])
        if port < 0:
            raise ValueError("Port must be non-negative")
    except ValueError as e:
        print(f"Invalid PORT: {e}")
        sys.exit(1)
    
    filename = sys.argv[2]
    
    try:
        board = await Board.parse_from_file(filename)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading board file: {e}")
        sys.exit(1)
    
    server = WebServer(board, port)
    await server.start()
    
    # Keep server running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\nShutting down...")
        await server.stop()


if __name__ == '__main__':
    asyncio.run(main())