"""
This is the main file for the chess game. It initializes the game window, handles the main game loop, and processes user input.
The actual game logic and rendering will be handled in the GameEngine class, which is imported at the beginning of this file.

Controls (like chess.com):
- Left click a piece, then left click a target square, or drag the piece to the target square.
- Right drag from one square to another to draw an arrow, right click a square to mark it.
- Any left click clears all arrows and marks.
- After a game, "Review" steps through the moves: arrow keys, Home/End, or click a move in the list.
  Every finished game is also saved as a PGN file in game_logs/.
"""

import os
import threading
import time
from datetime import datetime
import pygame
from GameEngine import GameEngine

pygame.init()

BOARD_SIZE = 512
PANEL_WIDTH = 200  # Move list to the right of the board
WIDTH, HEIGHT = BOARD_SIZE + PANEL_WIDTH, BOARD_SIZE
DIMENSION = 8  # 8x8 chess board
SQ_SIZE = BOARD_SIZE // DIMENSION
FPS = 60 # Frames per second for the game loop, high enough for smooth animations
WIN = pygame.display.set_mode((WIDTH, HEIGHT)) # Set up the game window with the specified width and height
pygame.display.set_caption('Chess Game') # Set the title of the game window to "Chess Game"
PROMOTION_ORDER = ['q', 'r', 'b', 'n']
CPU_COLOR = 'black'
CPU_SEARCH_DEPTH = 5
HUMAN_COLOR = 'white'
REVIEW_BUTTON_RECT = pygame.Rect(BOARD_SIZE // 2 - 170, HEIGHT // 2 + 54, 160, 44)
RESET_BUTTON_RECT = pygame.Rect(BOARD_SIZE // 2 + 10, HEIGHT // 2 + 54, 160, 44)
GAME_LOG_DIR = 'game_logs'

MOVE_LIST_TOP = 44
MOVE_ROW_HEIGHT = 24
VISIBLE_MOVE_ROWS = (HEIGHT - 60 - MOVE_LIST_TOP) // MOVE_ROW_HEIGHT
PREVIOUS_BUTTON_RECT = pygame.Rect(BOARD_SIZE + 10, HEIGHT - 48, 34, 36)
NEXT_BUTTON_RECT = pygame.Rect(BOARD_SIZE + 50, HEIGHT - 48, 34, 36)
PANEL_RESET_BUTTON_RECT = pygame.Rect(BOARD_SIZE + 90, HEIGHT - 48, 100, 36)

ANIMATION_DURATION = 0.5  # Seconds for lift, travel and landing of a moved piece
LIFT_HEIGHT = 14  # Pixels a piece rises while it moves
LIFT_SCALE = 1.15  # Size of a lifted piece compared to a resting one
DRAG_THRESHOLD = 4  # Pixels the mouse must move before a click becomes a drag

LAST_MOVE_COLOR = (255, 235, 59, 110)
SELECTED_COLOR = (255, 235, 59, 160)
MARK_COLOR = (235, 97, 80, 190)
ARROW_COLOR = (255, 170, 0, 170)
MOVE_HINT_COLOR = (0, 0, 0, 45)
PANEL_COLOR = (38, 37, 34)
PANEL_TEXT_COLOR = (225, 225, 215)
PANEL_MUTED_COLOR = (140, 140, 130)
CURRENT_MOVE_COLOR = (80, 78, 72)

class UiState:
    """Everything the board UI tracks besides the game itself."""

    def __init__(self):
        self.selected_square = None  # Board coordinates (board_row, board_col) of selected piece
        self.legal_targets = set()  # Squares the selected piece can move to
        self.pending_promotion = None
        self.cpu_job = None  # Running CPU search, see start_cpu_move
        self.animation = None  # Running move animation, see create_move_animation
        self.drag_square = None  # Square of the piece held with the left mouse button
        self.drag_start_pos = None
        self.drag_active = False
        self.arrow_start = None  # Square where the current right drag started
        self.arrows = []  # Planned moves as (from_square, to_square)
        self.marked_squares = set()
        self.review_ply = None  # Number of moves shown while reviewing, None during play
        self.move_list_scroll = 0  # First visible row of the move list
        self.log_saved = False

    def is_busy(self):
        return self.cpu_job is not None or self.animation is not None

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
    ui = UiState()

    running = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if event.pos[0] >= BOARD_SIZE:
                    if handle_panel_click(game_engine, ui, event.pos):
                        game_engine = GameEngine()
                        ui = UiState()
                    continue
                if game_engine.game_over and ui.review_ply is None:
                    if REVIEW_BUTTON_RECT.collidepoint(event.pos):
                        set_review_ply(game_engine, ui, len(game_engine.move_log))
                    elif RESET_BUTTON_RECT.collidepoint(event.pos):
                        game_engine = GameEngine()
                        ui = UiState()
                    continue
                handle_left_press(game_engine, ui, event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                handle_left_release(game_engine, ui, event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                can_plan = not game_engine.game_over or ui.review_ply is not None
                if can_plan and event.pos[0] < BOARD_SIZE and ui.pending_promotion is None:
                    ui.drag_square = None  # Right click cancels a drag
                    ui.arrow_start = screen_to_square(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                handle_right_release(ui, event.pos)
            elif event.type == pygame.MOUSEWHEEL:
                scroll_move_list(game_engine, ui, ui.move_list_scroll - event.y)
            elif event.type == pygame.KEYDOWN and ui.review_ply is not None:
                handle_review_key(game_engine, ui, event.key)
            elif event.type == pygame.MOUSEMOTION and ui.drag_square is not None and not ui.drag_active:
                start_x, start_y = ui.drag_start_pos
                if abs(event.pos[0] - start_x) + abs(event.pos[1] - start_y) > DRAG_THRESHOLD:
                    ui.drag_active = True

        if ui.animation is not None and get_animation_progress(ui.animation) >= 1:
            ui.animation = None

        # Play the CPU move once the search is done and the previous animation has finished.
        if ui.cpu_job is not None and ui.cpu_job['done'] and ui.animation is None:
            cpu_move = ui.cpu_job['move']
            ui.cpu_job = None
            if cpu_move is not None:
                play_move(game_engine, ui, *cpu_move)

        if game_engine.game_over and not ui.log_saved:
            save_game_log(game_engine)
            ui.log_saved = True

        # Draw the game state
        draw_game_state(WIN, game_engine, images, ui)
        pygame.display.flip()

    pygame.quit()

def handle_left_press(game_engine, ui, mouse_pos):
    ui.arrows.clear()
    ui.marked_squares.clear()

    if ui.review_ply is not None:
        return  # Only arrows and marks while reviewing

    if ui.pending_promotion is not None:
        promotion_piece = get_promotion_choice(mouse_pos, ui.pending_promotion)
        if promotion_piece is not None:
            pending_promotion = ui.pending_promotion
            ui.pending_promotion = None
            play_move(
                game_engine,
                ui,
                pending_promotion['from_square'],
                pending_promotion['to_square'],
                promotion_piece,
                animate=pending_promotion['animate']
            )
        return

    if ui.is_busy():
        return

    clicked = screen_to_square(mouse_pos)
    if ui.selected_square is not None and clicked in ui.legal_targets:
        try_human_move(game_engine, ui, ui.selected_square, clicked, animate=True)
        return

    piece = game_engine.get_piece(clicked)
    if piece != '.' and game_engine.current_player == HUMAN_COLOR and game_engine.is_own_piece(piece):
        select_square(game_engine, ui, clicked)
        ui.drag_square = clicked
        ui.drag_start_pos = mouse_pos
        ui.drag_active = False
    else:
        clear_selection(ui)

def handle_left_release(game_engine, ui, mouse_pos):
    if ui.drag_square is None:
        return

    from_square = ui.drag_square
    was_dragged = ui.drag_active
    ui.drag_square = None
    ui.drag_active = False

    # A plain click keeps the piece selected, a drag tries to drop it on the target square.
    to_square = screen_to_square(mouse_pos)
    if was_dragged and to_square != from_square:
        try_human_move(game_engine, ui, from_square, to_square, animate=False)

def handle_right_release(ui, mouse_pos):
    if ui.arrow_start is None:
        return

    from_square = ui.arrow_start
    to_square = screen_to_square(mouse_pos)
    ui.arrow_start = None
    if mouse_pos[0] >= BOARD_SIZE:
        return

    # Drawing the same arrow or mark a second time removes it again.
    if from_square == to_square:
        ui.marked_squares ^= {from_square}
    elif (from_square, to_square) in ui.arrows:
        ui.arrows.remove((from_square, to_square))
    else:
        ui.arrows.append((from_square, to_square))

def handle_panel_click(game_engine, ui, mouse_pos):
    """Handle a click on the move list panel. Returns True if a new game should start."""
    if ui.review_ply is None:
        return False
    if PANEL_RESET_BUTTON_RECT.collidepoint(mouse_pos):
        return True
    if PREVIOUS_BUTTON_RECT.collidepoint(mouse_pos):
        set_review_ply(game_engine, ui, ui.review_ply - 1)
    elif NEXT_BUTTON_RECT.collidepoint(mouse_pos):
        set_review_ply(game_engine, ui, ui.review_ply + 1)
    else:
        for rect, ply in get_move_list_cells(game_engine, ui):
            if rect.collidepoint(mouse_pos):
                set_review_ply(game_engine, ui, ply)
    return False

def handle_review_key(game_engine, ui, key):
    target_plies = {
        pygame.K_LEFT: ui.review_ply - 1,
        pygame.K_RIGHT: ui.review_ply + 1,
        pygame.K_HOME: 0,
        pygame.K_END: len(game_engine.move_log),
    }
    if key in target_plies:
        set_review_ply(game_engine, ui, target_plies[key])

def set_review_ply(game_engine, ui, ply):
    ui.review_ply = min(max(ply, 0), len(game_engine.move_log))
    ui.arrows.clear()
    ui.marked_squares.clear()
    scroll_to_ply(game_engine, ui, ui.review_ply)

def scroll_to_ply(game_engine, ui, ply):
    # Keep the row of that move inside the visible part of the move list.
    row = max(ply - 1, 0) // 2
    if row < ui.move_list_scroll:
        scroll_move_list(game_engine, ui, row)
    elif row >= ui.move_list_scroll + VISIBLE_MOVE_ROWS:
        scroll_move_list(game_engine, ui, row - VISIBLE_MOVE_ROWS + 1)

def scroll_move_list(game_engine, ui, first_row):
    row_count = (len(game_engine.move_log) + 1) // 2
    ui.move_list_scroll = min(max(first_row, 0), max(row_count - VISIBLE_MOVE_ROWS, 0))

def get_game_result(game_engine):
    if game_engine.game_result == 'checkmate':
        return '1-0' if game_engine.winner == 'white' else '0-1'
    if game_engine.game_over:
        return '1/2-1/2'
    return '*'

def save_game_log(game_engine):
    # Write the game in PGN format, which chess sites and programs can import.
    players = {HUMAN_COLOR: 'Player', CPU_COLOR: f'CPU (depth {CPU_SEARCH_DEPTH})'}
    result = get_game_result(game_engine)
    finished = datetime.now()

    tokens = []
    for index, entry in enumerate(game_engine.move_log):
        if index % 2 == 0:
            tokens.append(f'{index // 2 + 1}.')
        tokens.append(entry['notation'])
    tokens.append(result)

    lines = []
    line = ''
    for token in tokens:
        if line and len(line) + len(token) + 1 > 80:
            lines.append(line)
            line = token
        else:
            line = f'{line} {token}' if line else token
    lines.append(line)

    pgn = '\n'.join([
        '[Event "Casual Game"]',
        f'[Date "{finished:%Y.%m.%d}"]',
        f'[White "{players["white"]}"]',
        f'[Black "{players["black"]}"]',
        f'[Result "{result}"]',
        f'[Termination "{game_engine.game_result}"]',
        '',
        *lines,
        '',
    ])

    path = os.path.join(GAME_LOG_DIR, f'{finished:%Y-%m-%d_%H-%M-%S}.pgn')
    try:
        os.makedirs(GAME_LOG_DIR, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as log_file:
            log_file.write(pgn)
        print(f"Game saved to {path}")
    except OSError as error:
        print(f"Could not save game log: {error}")

def select_square(game_engine, ui, square):
    ui.selected_square = square
    ui.legal_targets = {
        to_square
        for from_square, to_square, _ in game_engine.get_all_legal_moves(HUMAN_COLOR)
        if from_square == square
    }

def clear_selection(ui):
    ui.selected_square = None
    ui.legal_targets = set()

def try_human_move(game_engine, ui, from_square, to_square, animate):
    if to_square not in ui.legal_targets:
        clear_selection(ui)
        return

    piece = game_engine.get_piece(from_square)
    if is_promotion_attempt(piece, to_square):
        ui.pending_promotion = {
            'from_square': from_square,
            'to_square': to_square,
            'color_prefix': piece[0],
            'animate': animate,
        }
        return

    play_move(game_engine, ui, from_square, to_square, animate=animate)

def play_move(game_engine, ui, from_square, to_square, promotion_piece=None, animate=True):
    board_before = game_engine.get_board()
    if not game_engine.move_piece(from_square, to_square, promotion_piece):
        clear_selection(ui)
        return False

    scroll_to_ply(game_engine, ui, len(game_engine.move_log))
    ui.animation = create_move_animation(game_engine, board_before, from_square, to_square) if animate else None
    clear_selection(ui)
    ui.cpu_job = start_cpu_move(game_engine)
    return True

def is_promotion_attempt(piece, to_square):
    return (piece == 'wp' and to_square[0] == 7) or (piece == 'bp' and to_square[0] == 0)

def start_cpu_move(game_engine):
    # Search in a background thread so the window keeps responding. The main loop plays the move once done.
    if game_engine.game_over or game_engine.current_player != CPU_COLOR:
        return None

    cpu_job = {'move': None, 'done': False}

    def search():
        cpu_job['move'] = game_engine.get_best_move(CPU_COLOR, CPU_SEARCH_DEPTH)
        cpu_job['done'] = True

    threading.Thread(target=search, daemon=True).start()
    return cpu_job

def create_move_animation(game_engine, board_before, from_square, to_square):
    piece = board_before[from_square]
    moving_pieces = [(piece, from_square, to_square)]
    if piece[1] == 'k' and abs(to_square[1] - from_square[1]) == 2:
        rook_from, rook_to = game_engine.get_castling_rook_squares(from_square, to_square)
        moving_pieces.append((board_before[rook_from], rook_from, rook_to))

    # En passant captures a pawn that is not on the target square.
    captured_square = to_square
    if piece[1] == 'p' and from_square[1] != to_square[1] and to_square not in board_before:
        captured_square = (from_square[0], to_square[1])
    captured_piece = board_before.get(captured_square)

    return {
        'moving_pieces': moving_pieces,
        'captured': (captured_piece, captured_square) if captured_piece else None,
        'start_time': time.perf_counter(),
    }

def get_animation_progress(animation):
    return min(1.0, (time.perf_counter() - animation['start_time']) / ANIMATION_DURATION)

def ease_in_out(t):
    return t * t * (3 - 2 * t)

def screen_to_square(mouse_pos):
    col = min(max(mouse_pos[0] // SQ_SIZE, 0), DIMENSION - 1)
    screen_row = min(max(mouse_pos[1] // SQ_SIZE, 0), DIMENSION - 1)
    return (7 - screen_row, col)

def square_to_screen(square):
    # Top-left pixel of a board square. Board row 0 is at the bottom of the window.
    board_row, board_col = square
    return board_col * SQ_SIZE, (7 - board_row) * SQ_SIZE

def square_center(square):
    x, y = square_to_screen(square)
    return pygame.Vector2(x + SQ_SIZE / 2, y + SQ_SIZE / 2)

def get_promotion_choice(mouse_pos, pending_promotion):
    for rect, piece in get_promotion_options(pending_promotion):
        if rect.collidepoint(mouse_pos):
            return piece
    return None

def get_promotion_options(pending_promotion):
    box_size = SQ_SIZE
    gap = 10
    total_width = len(PROMOTION_ORDER) * box_size + (len(PROMOTION_ORDER) - 1) * gap
    start_x = (BOARD_SIZE - total_width) // 2
    y = (HEIGHT - box_size) // 2
    color_prefix = pending_promotion['color_prefix']

    options = []
    for index, piece_type in enumerate(PROMOTION_ORDER):
        x = start_x + index * (box_size + gap)
        rect = pygame.Rect(x, y, box_size, box_size)
        options.append((rect, f'{color_prefix}{piece_type}'))
    return options

def get_displayed_position(game_engine, ui):
    """Board, last move and king in check (or None) of the live game, or of the reviewed move."""
    ply = len(game_engine.move_log) if ui.review_ply is None else ui.review_ply
    if ply == 0:
        return game_engine.start_board, None, None
    entry = game_engine.move_log[ply - 1]
    checked_king = ('wk' if ply % 2 == 0 else 'bk') if entry['in_check'] else None
    return entry['board'], (entry['from_square'], entry['to_square']), checked_king

def draw_game_state(win, game_engine, images, ui):
    board, last_move, checked_king = get_displayed_position(game_engine, ui)

    draw_board(win)
    draw_square_colors(win, ui, last_move)
    if checked_king is not None:
        draw_check_highlight(win, board, checked_king)
    draw_move_hints(win, game_engine, ui)
    draw_pieces(win, board, images, ui)
    draw_arrows(win, ui)
    draw_move_panel(win, game_engine, ui)
    if ui.drag_square is not None and ui.drag_active:
        piece = game_engine.get_piece(ui.drag_square)
        win.blit(images[piece], images[piece].get_rect(center=pygame.mouse.get_pos()))
    if ui.pending_promotion is not None:
        draw_promotion_overlay(win, images, ui.pending_promotion)
    if game_engine.game_over and ui.animation is None and ui.review_ply is None:
        draw_game_over_overlay(win, game_engine)

def draw_board(win):
    # Draw the chess board squares. Light and dark squares will alternate
    colors = [pygame.Color(235, 235, 208), pygame.Color(119, 148, 85)]
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            color = colors[(r + c) % 2]
            pygame.draw.rect(win, color, pygame.Rect(c*SQ_SIZE, r*SQ_SIZE, SQ_SIZE, SQ_SIZE))

def fill_square(win, square, color):
    overlay = pygame.Surface((SQ_SIZE, SQ_SIZE), pygame.SRCALPHA)
    overlay.fill(color)
    win.blit(overlay, square_to_screen(square))

def draw_square_colors(win, ui, last_move):
    if last_move is not None:
        for square in last_move:
            fill_square(win, square, LAST_MOVE_COLOR)
    if ui.selected_square is not None:
        fill_square(win, ui.selected_square, SELECTED_COLOR)
    for square in ui.marked_squares:
        fill_square(win, square, MARK_COLOR)

def draw_move_hints(win, game_engine, ui):
    # Dots on empty target squares, rings on squares with a piece to capture.
    if not ui.legal_targets:
        return

    overlay = pygame.Surface((BOARD_SIZE, HEIGHT), pygame.SRCALPHA)
    for square in ui.legal_targets:
        center = square_center(square)
        if game_engine.get_piece(square) == '.':
            pygame.draw.circle(overlay, MOVE_HINT_COLOR, center, SQ_SIZE * 0.16)
        else:
            pygame.draw.circle(overlay, MOVE_HINT_COLOR, center, SQ_SIZE * 0.47, width=int(SQ_SIZE * 0.08))
    win.blit(overlay, (0, 0))

def draw_pieces(win, board, images, ui):
    # Draw the pieces of a board dict as returned by GameEngine.get_board().
    # Pygame coordinates are (x, y) with (0, 0) at the top-left corner, while our board coordinates are (row, col) with (0, 0) at the bottom-left corner.
    # Pieces that are animated or dragged are drawn separately on top.
    hidden_squares = set()
    if ui.animation is not None:
        hidden_squares.update(to_square for _, _, to_square in ui.animation['moving_pieces'])
    if ui.drag_square is not None and ui.drag_active:
        hidden_squares.add(ui.drag_square)

    for square, piece in board.items():
        if square not in hidden_squares:
            win.blit(images[piece], square_to_screen(square))

    if ui.animation is not None:
        draw_animation(win, images, ui.animation)

def draw_animation(win, images, animation):
    progress = get_animation_progress(animation)

    # The captured piece stays visible until the moving piece starts to land on it.
    if animation['captured'] is not None and progress < 0.8:
        captured_piece, captured_square = animation['captured']
        win.blit(images[captured_piece], square_to_screen(captured_square))

    for piece, from_square, to_square in animation['moving_pieces']:
        draw_flying_piece(win, images[piece], from_square, to_square, progress)

def draw_flying_piece(win, image, from_square, to_square, progress):
    # Lift the piece during the first 20%, move it until 80%, then set it down.
    if progress < 0.2:
        lift, travel = progress / 0.2, 0.0
    elif progress < 0.8:
        lift, travel = 1.0, (progress - 0.2) / 0.6
    else:
        lift, travel = 1.0 - (progress - 0.8) / 0.2, 1.0
    lift = ease_in_out(lift)
    travel = ease_in_out(travel)

    center = square_center(from_square).lerp(square_center(to_square), travel)

    shadow_size = (SQ_SIZE * 0.6, SQ_SIZE * 0.18)
    shadow = pygame.Surface(shadow_size, pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, int(70 * lift)), shadow.get_rect())
    win.blit(shadow, shadow.get_rect(center=(center.x, center.y + SQ_SIZE * 0.36)))

    size = int(SQ_SIZE * (1 + (LIFT_SCALE - 1) * lift))
    lifted_image = pygame.transform.smoothscale(image, (size, size))
    win.blit(lifted_image, lifted_image.get_rect(center=(center.x, center.y - LIFT_HEIGHT * lift)))

def draw_arrows(win, ui):
    arrows = list(ui.arrows)
    hovered = screen_to_square(pygame.mouse.get_pos())
    if ui.arrow_start is not None and hovered != ui.arrow_start:
        arrows.append((ui.arrow_start, hovered))  # Preview of the arrow being drawn
    if not arrows:
        return

    # Draw all arrows on one surface so overlapping parts don't get darker.
    overlay = pygame.Surface((BOARD_SIZE, HEIGHT), pygame.SRCALPHA)
    for from_square, to_square in arrows:
        draw_arrow(overlay, from_square, to_square)
    win.blit(overlay, (0, 0))

def draw_arrow(surface, from_square, to_square):
    shaft_width = SQ_SIZE * 0.2
    head_length = SQ_SIZE * 0.45
    head_width = SQ_SIZE * 0.55

    # Knight moves get an L-shaped arrow that first follows the longer side.
    points = [square_center(from_square)]
    row_diff = abs(to_square[0] - from_square[0])
    col_diff = abs(to_square[1] - from_square[1])
    if (row_diff, col_diff) == (2, 1):
        points.append(square_center((to_square[0], from_square[1])))
    elif (row_diff, col_diff) == (1, 2):
        points.append(square_center((from_square[0], to_square[1])))
    points.append(square_center(to_square))

    # Start a bit away from the piece's center, end where the arrow head begins.
    points[0] += (points[1] - points[0]).normalize() * SQ_SIZE * 0.25
    tip = points[-1]
    direction = (tip - points[-2]).normalize()
    points[-1] = tip - direction * head_length

    for index in range(len(points) - 1):
        start, end = points[index], points[index + 1]
        segment_direction = (end - start).normalize()
        if index < len(points) - 2:
            end = end + segment_direction * shaft_width / 2  # Fill the corner of the L
        normal = pygame.Vector2(-segment_direction.y, segment_direction.x) * shaft_width / 2
        pygame.draw.polygon(surface, ARROW_COLOR, [start + normal, end + normal, end - normal, start - normal])

    normal = pygame.Vector2(-direction.y, direction.x) * head_width / 2
    base = points[-1]
    pygame.draw.polygon(surface, ARROW_COLOR, [base + normal, tip, base - normal])

def draw_check_highlight(win, board, checked_king):
    for square, piece in board.items():
        if piece == checked_king:
            pygame.draw.rect(win, (255, 0, 0), pygame.Rect(*square_to_screen(square), SQ_SIZE, SQ_SIZE), 3)

def draw_button(win, rect, text, font):
    mouse_pos = pygame.mouse.get_pos()
    button_color = pygame.Color(250, 250, 240) if rect.collidepoint(mouse_pos) else pygame.Color(225, 225, 210)
    pygame.draw.rect(win, button_color, rect, border_radius=6)
    pygame.draw.rect(win, pygame.Color(35, 35, 35), rect, width=2, border_radius=6)
    text_surface = font.render(text, True, pygame.Color(20, 20, 20))
    win.blit(text_surface, text_surface.get_rect(center=rect.center))

def get_move_list_cells(game_engine, ui):
    # Clickable rectangles of the visible moves in the panel, with the number of moves up to and including each.
    cells = []
    for row in range(ui.move_list_scroll, ui.move_list_scroll + VISIBLE_MOVE_ROWS):
        y = MOVE_LIST_TOP + (row - ui.move_list_scroll) * MOVE_ROW_HEIGHT
        for column in range(2):
            ply = row * 2 + column + 1
            if ply <= len(game_engine.move_log):
                cells.append((pygame.Rect(BOARD_SIZE + 44 + column * 76, y, 72, MOVE_ROW_HEIGHT), ply))
    return cells

def draw_move_panel(win, game_engine, ui):
    pygame.draw.rect(win, PANEL_COLOR, pygame.Rect(BOARD_SIZE, 0, PANEL_WIDTH, HEIGHT))
    title_font = pygame.font.SysFont(None, 30)
    move_font = pygame.font.SysFont(None, 24)

    win.blit(title_font.render("Moves", True, PANEL_TEXT_COLOR), (BOARD_SIZE + 12, 14))
    if game_engine.game_over:
        result_surface = title_font.render(get_game_result(game_engine), True, PANEL_TEXT_COLOR)
        win.blit(result_surface, result_surface.get_rect(topright=(WIDTH - 12, 14)))

    current_ply = len(game_engine.move_log) if ui.review_ply is None else ui.review_ply
    for rect, ply in get_move_list_cells(game_engine, ui):
        if ply % 2 == 1:
            number_surface = move_font.render(f"{ply // 2 + 1}.", True, PANEL_MUTED_COLOR)
            win.blit(number_surface, number_surface.get_rect(midleft=(BOARD_SIZE + 12, rect.centery)))
        if ply == current_ply:
            pygame.draw.rect(win, CURRENT_MOVE_COLOR, rect, border_radius=4)
        notation_surface = move_font.render(game_engine.move_log[ply - 1]['notation'], True, PANEL_TEXT_COLOR)
        win.blit(notation_surface, notation_surface.get_rect(midleft=(rect.x + 6, rect.centery)))

    if ui.review_ply is not None:
        button_font = pygame.font.SysFont(None, 26)
        draw_button(win, PREVIOUS_BUTTON_RECT, "<", button_font)
        draw_button(win, NEXT_BUTTON_RECT, ">", button_font)
        draw_button(win, PANEL_RESET_BUTTON_RECT, "New Game", button_font)
    elif ui.cpu_job is not None:
        thinking_surface = move_font.render("CPU is thinking...", True, PANEL_MUTED_COLOR)
        win.blit(thinking_surface, (BOARD_SIZE + 12, HEIGHT - 36))

def draw_promotion_overlay(win, images, pending_promotion):
    overlay = pygame.Surface((BOARD_SIZE, HEIGHT), pygame.SRCALPHA)
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
    overlay = pygame.Surface((BOARD_SIZE, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    win.blit(overlay, (0, 0))

    title_font = pygame.font.SysFont(None, 56)
    body_font = pygame.font.SysFont(None, 28)
    button_font = pygame.font.SysFont(None, 30)

    title, subtitle = get_game_over_text(game_engine)
    title_surface = title_font.render(title, True, pygame.Color(255, 255, 255))
    subtitle_surface = body_font.render(subtitle, True, pygame.Color(230, 230, 230))
    title_rect = title_surface.get_rect(center=(BOARD_SIZE // 2, HEIGHT // 2 - 56))
    subtitle_rect = subtitle_surface.get_rect(center=(BOARD_SIZE // 2, HEIGHT // 2 - 10))

    draw_button(win, REVIEW_BUTTON_RECT, "Review", button_font)
    draw_button(win, RESET_BUTTON_RECT, "New Game", button_font)

    win.blit(title_surface, title_rect)
    win.blit(subtitle_surface, subtitle_rect)

def get_game_over_text(game_engine):
    if game_engine.game_result == 'stalemate':
        return "Stalemate", "No legal moves remain."

    if game_engine.game_result == 'threefold_repetition':
        return "Draw", "Threefold repetition."

    if game_engine.game_result == 'checkmate':
        if game_engine.winner == HUMAN_COLOR:
            return "You Win", "Checkmate."
        return "You Lose", "Checkmate."

    return "Game Over", "The game has ended."

if __name__ == "__main__":
    main()
