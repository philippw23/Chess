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
PROMOTION_ORDER = ['q', 'r', 'b', 'n']
CPU_COLOR = 'black'
CPU_SEARCH_DEPTH = 2
HUMAN_COLOR = 'white'
RESET_BUTTON_RECT = pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2 + 54, 160, 44)

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
    pending_promotion = None

    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                if game_engine.game_over:
                    if RESET_BUTTON_RECT.collidepoint(mouse_pos):
                        game_engine = GameEngine()
                        selected_square = None
                        pending_promotion = None
                    continue

                if pending_promotion is not None:
                    promotion_piece = get_promotion_choice(mouse_pos, pending_promotion)
                    if promotion_piece is not None:
                        move_successful = game_engine.move_piece(
                            pending_promotion['from_square'],
                            pending_promotion['to_square'],
                            promotion_piece
                        )
                        pending_promotion = None
                        selected_square = None
                        if move_successful:
                            make_cpu_move(game_engine)
                    continue

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
                        piece = game_engine.get_piece(selected_square)
                        if is_promotion_attempt(piece, clicked) and game_engine.is_valid_move(piece, selected_square, clicked):
                            pending_promotion = {
                                'from_square': selected_square,
                                'to_square': clicked,
                                'color_prefix': piece[0],
                            }
                        else:
                            move_successful = game_engine.move_piece(selected_square, clicked)
                            selected_square = None
                            if move_successful:
                                make_cpu_move(game_engine)

        # Draw the game state
        draw_game_state(WIN, game_engine, images, game_engine.in_check, selected_square, pending_promotion)
        pygame.display.flip()

    pygame.quit()

def is_promotion_attempt(piece, to_square):
    return (piece == 'wp' and to_square[0] == 7) or (piece == 'bp' and to_square[0] == 0)

def make_cpu_move(game_engine):
    if game_engine.game_over or game_engine.current_player != CPU_COLOR:
        return

    best_move = game_engine.get_best_move(CPU_COLOR, CPU_SEARCH_DEPTH)
    if best_move is not None:
        game_engine.move_piece(*best_move)

def get_promotion_choice(mouse_pos, pending_promotion):
    for rect, piece in get_promotion_options(pending_promotion):
        if rect.collidepoint(mouse_pos):
            return piece
    return None

def get_promotion_options(pending_promotion):
    box_size = SQ_SIZE
    gap = 10
    total_width = len(PROMOTION_ORDER) * box_size + (len(PROMOTION_ORDER) - 1) * gap
    start_x = (WIDTH - total_width) // 2
    y = (HEIGHT - box_size) // 2
    color_prefix = pending_promotion['color_prefix']

    options = []
    for index, piece_type in enumerate(PROMOTION_ORDER):
        x = start_x + index * (box_size + gap)
        rect = pygame.Rect(x, y, box_size, box_size)
        options.append((rect, f'{color_prefix}{piece_type}'))
    return options

def draw_game_state(win, game_engine, images, check, selected_square, pending_promotion):
    draw_board(win)
    draw_highlight(win, game_engine, check, selected_square)
    draw_pieces(win, game_engine, images)
    if pending_promotion is not None:
        draw_promotion_overlay(win, images, pending_promotion)
    if game_engine.game_over:
        draw_game_over_overlay(win, game_engine)

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

def draw_promotion_overlay(win, images, pending_promotion):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    win.blit(overlay, (0, 0))

    mouse_pos = pygame.mouse.get_pos()
    for rect, piece in get_promotion_options(pending_promotion):
        is_hovered = rect.collidepoint(mouse_pos)
        draw_rect = rect.inflate(10, 10) if is_hovered else rect
        image_rect = images[piece].get_rect(center=draw_rect.center)
        if is_hovered:
            hovered_image = pygame.transform.smoothscale(images[piece], (draw_rect.width, draw_rect.height))
            image_rect = hovered_image.get_rect(center=draw_rect.center)
            image = hovered_image
        else:
            image = images[piece]

        pygame.draw.rect(win, pygame.Color(245, 245, 235), draw_rect, border_radius=6)
        pygame.draw.rect(win, pygame.Color(30, 30, 30), draw_rect, width=2, border_radius=6)
        win.blit(image, image_rect)

def draw_game_over_overlay(win, game_engine):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    win.blit(overlay, (0, 0))

    title_font = pygame.font.SysFont(None, 56)
    body_font = pygame.font.SysFont(None, 28)
    button_font = pygame.font.SysFont(None, 30)

    title, subtitle = get_game_over_text(game_engine)
    title_surface = title_font.render(title, True, pygame.Color(255, 255, 255))
    subtitle_surface = body_font.render(subtitle, True, pygame.Color(230, 230, 230))
    title_rect = title_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 56))
    subtitle_rect = subtitle_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10))

    mouse_pos = pygame.mouse.get_pos()
    button_color = pygame.Color(250, 250, 240) if RESET_BUTTON_RECT.collidepoint(mouse_pos) else pygame.Color(225, 225, 210)
    pygame.draw.rect(win, button_color, RESET_BUTTON_RECT, border_radius=6)
    pygame.draw.rect(win, pygame.Color(35, 35, 35), RESET_BUTTON_RECT, width=2, border_radius=6)

    button_surface = button_font.render("New Game", True, pygame.Color(20, 20, 20))
    button_text_rect = button_surface.get_rect(center=RESET_BUTTON_RECT.center)

    win.blit(title_surface, title_rect)
    win.blit(subtitle_surface, subtitle_rect)
    win.blit(button_surface, button_text_rect)

def get_game_over_text(game_engine):
    if game_engine.game_result == 'stalemate':
        return "Stalemate", "No legal moves remain."

    if game_engine.game_result == 'checkmate':
        if game_engine.winner == HUMAN_COLOR:
            return "You Win", "Checkmate."
        return "You Lose", "Checkmate."

    return "Game Over", "The game has ended."

if __name__ == "__main__":
    main()
