import sys
import asyncio
from pathlib import Path
from aiohttp import web
from board import Board
from commands import look, flip, map_replace, watch


class WebServer:
    """HTTP web game server."""

    def __init__(self, board: Board, port: int):
        """
        Create a new web game server.

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
        GET /look/<player_id>
        player_id must be a nonempty string of alphanumeric or underscore characters
        
        Response is the board state from player_id's perspective.
        """
        player_id = request.match_info['player_id']
        
        board_state = await look(self.board, player_id)
        return web.Response(text=board_state, content_type='text/plain')
    
    async def handle_flip(self, request: web.Request) -> web.Response:
        """
        GET /flip/<player_id>/<row>,<column>
        player_id must be a nonempty string of alphanumeric or underscore characters;
        row and column must be integers, 0 <= row,column < height,width of board (respectively)
        
        Response is the state of the board after the flip from the perspective of player_id.
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
        GET /replace/<player_id>/<oldcard>/<newcard>
        player_id must be a nonempty string of alphanumeric or underscore characters;
        oldcard and newcard must be nonempty strings.
        
        Replaces all occurrences of oldcard with newcard (as card labels) on the board.
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
        GET /watch/<player_id>
        player_id must be a nonempty string of alphanumeric or underscore characters
        
        Waits until the next time the board changes (defined as any cards turning face up or face down,
        being removed from the board, or changing from one string to a different string).
        """
        player_id = request.match_info['player_id']
        
        board_state = await watch(self.board, player_id)
        return web.Response(text=board_state, content_type='text/plain')
    
    async def start(self) -> None:
        """Start this server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, 'localhost', self.port)
        await self.site.start()
        
        # Get the actual port if 0 was specified
        if self.port == 0:
            self.port = self.site._server.sockets[0].getsockname()[1]
        
        print(f"server now listening at http://localhost:{self.port}")
    
    async def stop(self) -> None:
        """Stop this server."""
        if self.runner:
            await self.runner.cleanup()
        print("server stopped")


async def main():
    """Main entry point for the server."""
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