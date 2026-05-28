"""
This is the main file for the chess game. It initializes the game window, handles the main game loop, and processes user input. 
The actual game logic and rendering will be handled in the GameEngine class, which is imported at the beginning of this file.
"""

import pygame
from GameEngine import GameEngine

pygame.init()

WIDTH, HEIGHT = 512, 512
DIMENSION = 8  # 8x8 chess board
SQ_SIZE = HEIGHT // DIMENSION
FPS = 15 # Frames per second for the game loop
WIN = pygame.display.set_mode((WIDTH, HEIGHT)) # Set up the game window with the specified width and height
pygame.display.set_caption('Chess Game') # Set the title of the game window to "Chess Game"

def load_images():
    # Load images for the chess pieces. This function will be called once at the beginning of the game.
    pieces = ['wp', 'wr', 'wn', 'wb', 'wq', 'wk', 'bp', 'br', 'bn', 'bb', 'bq', 'bk']
    images = {}
    for piece in pieces:
        images[piece] = pygame.transform.scale(pygame.image.load(f'images/{piece}.png'), (SQ_SIZE, SQ_SIZE))
    return images

def main():
    clock = pygame.time.Clock()
    game_engine = GameEngine()
    images = load_images()

    running = True
    selected_square = None  # Board coordinates (board_row, board_col) of selected piece

    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                screen_col = mouse_pos[0] // SQ_SIZE
                screen_row = mouse_pos[1] // SQ_SIZE
                board_row = 7 - screen_row
                board_col = screen_col
                clicked = (board_row, board_col)
                print(f"Clicked on board square: {clicked}")
                if event.button == 1:  # Left click: select
                    piece = game_engine.get_piece(clicked)
                    if piece != '.' and game_engine.is_own_piece(piece):
                        selected_square = clicked
                    else:
                        selected_square = None

                elif event.button == 3:  # Right click: execute move
                    if selected_square is not None:
                        game_engine.move_piece(selected_square, clicked)
                        selected_square = None

        # Draw the game state
        draw_game_state(WIN, game_engine, images, game_engine.in_check, selected_square)
        pygame.display.flip()

    pygame.quit()

def draw_game_state(win, game_engine, images, check, selected_square):
    draw_board(win)
    draw_highlight(win, game_engine, check, selected_square)
    draw_pieces(win, game_engine, images)

def draw_board(win):
    # Draw the chess board squares. Light and dark squares will alternate
    colors = [pygame.Color(235, 235, 208), pygame.Color(119, 148, 85)]
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            color = colors[(r + c) % 2]
            pygame.draw.rect(win, color, pygame.Rect(c*SQ_SIZE, r*SQ_SIZE, SQ_SIZE, SQ_SIZE))

def draw_pieces(win, game_engine, images):
    # Draw pieces on the board based on the bitboards in the game engine.
    # Pygame coordinates are (x, y) with (0, 0) at the top-left corner, while our board coordinates are (row, col) with (0, 0) at the bottom-left corner.
    # We need to convert between these coordinate systems when drawing the pieces.
    for piece, bitboard_name in game_engine.bitboards.items():
        bitboard = getattr(game_engine, bitboard_name)
        for i in range(64):
            if (bitboard >> i) & 1:
                row = 7 - (i // 8)  # Convert bit index to row
                col = i % 8          # Convert bit index to column
                win.blit(images[piece], pygame.Rect(col*SQ_SIZE, row*SQ_SIZE, SQ_SIZE, SQ_SIZE))

def draw_highlight(win, game_engine, check, selected_square):
    if selected_square is not None:
        board_row, board_col = selected_square
        screen_row = 7 - board_row
        pygame.draw.rect(win, (255, 255, 0), pygame.Rect(board_col * SQ_SIZE, screen_row * SQ_SIZE, SQ_SIZE, SQ_SIZE), 3)

    if check:
        king_key = 'wk' if game_engine.current_player == 'white' else 'bk'
        bitboard = getattr(game_engine, game_engine.bitboards[king_key])
        for i in range(64):
            if (bitboard >> i) & 1:
                screen_row = 7 - (i // 8)
                col = i % 8
                pygame.draw.rect(win, (255, 0, 0), pygame.Rect(col * SQ_SIZE, screen_row * SQ_SIZE, SQ_SIZE, SQ_SIZE), 3)

if __name__ == "__main__":
    main()