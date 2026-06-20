"""
Game Engine for Chess Game. Handles game logic, move validation, and game state management.
"""
import copy


class GameEngine:
    PIECE_VALUES = {
        'p': 100,
        'n': 320,
        'b': 330,
        'r': 500,
        'q': 900,
        'k': 0,
    }

    def __init__(self):
        self.initialize_board()
        self.current_player = 'white'
        self.game_over = False
        self.in_check = False

    def initialize_board(self):
        # Initialize bitboards for the chess starting position.
        # Bit 0 is a1, bit 7 is h1, bit 56 is a8, bit 63 is h8.
        self.white_pawns = sum(1 << i for i in range(8, 16))
        self.black_pawns = sum(1 << i for i in range(48, 56))
        self.white_rooks = (1 << 0) | (1 << 7)
        self.black_rooks = (1 << 56) | (1 << 63)
        self.white_knights = (1 << 1) | (1 << 6)
        self.black_knights = (1 << 57) | (1 << 62)
        self.white_bishops = (1 << 2) | (1 << 5)
        self.black_bishops = (1 << 58) | (1 << 61)
        self.white_queen = 1 << 3
        self.black_queen = 1 << 59
        self.white_king = 1 << 4
        self.black_king = 1 << 60

        self.bitboards = {
            'wp': 'white_pawns',
            'wr': 'white_rooks',
            'wn': 'white_knights',
            'wb': 'white_bishops',
            'wq': 'white_queen',
            'wk': 'white_king',
            'bp': 'black_pawns',
            'br': 'black_rooks',
            'bn': 'black_knights',
            'bb': 'black_bishops',
            'bq': 'black_queen',
            'bk': 'black_king',
        }
        self.update_occupancy()
        self.en_passant_target = None
        self.en_passant_capture_square = None
        self.castling_rights = {
            'white_kingside': True,
            'white_queenside': True,
            'black_kingside': True,
            'black_queenside': True,
        }

    def update_occupancy(self):
        self.white_pieces = (
            self.white_pawns
            | self.white_rooks
            | self.white_knights
            | self.white_bishops
            | self.white_queen
            | self.white_king
        )
        self.black_pieces = (
            self.black_pawns
            | self.black_rooks
            | self.black_knights
            | self.black_bishops
            | self.black_queen
            | self.black_king
        )
        self.occupied = self.white_pieces | self.black_pieces

    def square_to_bit(self, square):
        """Convert a (row, col) square to a bitboard bit."""
        row, col = square
        if not (0 <= row < 8 and 0 <= col < 8):
            raise ValueError("Square must be a (row, col) tuple with values from 0 to 7.")
        return 1 << (row * 8 + col)

    def move_piece(self, from_square, to_square, promotion_piece=None):
        # Validate and move a piece from one square to another
        if self.game_over:
            print("Game over. No more moves allowed.")
            return False
        
        piece = self.get_piece(from_square)
        if piece == '.':
            return False

        if not self.is_own_piece(piece):
            return False

        if not self.is_valid_move(piece, from_square, to_square):
            print("Invalid move.")
            return False

        previous_en_passant_target = self.en_passant_target
        previous_en_passant_capture_square = self.en_passant_capture_square
        previous_castling_rights = self.castling_rights.copy()
        moving_player = self.current_player
        from_row, from_col = from_square
        to_row, to_col = to_square
        is_castling = piece[1] == 'k' and abs(to_col - from_col) == 2
        is_en_passant = self.is_en_passant_move(piece, from_square, to_square)
        captured_square = self.en_passant_capture_square if is_en_passant else to_square
        captured_piece = self.get_piece(captured_square)
        placed_piece = self.get_promotion_piece(piece, to_square, promotion_piece)

        self.set_piece(from_square, '.')
        if is_en_passant:
            self.set_piece(captured_square, '.')
        self.set_piece(to_square, placed_piece)

        if is_castling:
            rook_from, rook_to = self.get_castling_rook_squares(from_square, to_square)
            rook_piece = self.get_piece(rook_from)
            self.set_piece(rook_from, '.')
            self.set_piece(rook_to, rook_piece)

        if self.is_check(moving_player):
            if is_castling:
                rook_from, rook_to = self.get_castling_rook_squares(from_square, to_square)
                rook_piece = self.get_piece(rook_to)
                self.set_piece(rook_to, '.')
                self.set_piece(rook_from, rook_piece)
            self.set_piece(to_square, '.')
            self.set_piece(captured_square, captured_piece)
            self.set_piece(from_square, piece)
            self.en_passant_target = previous_en_passant_target
            self.en_passant_capture_square = previous_en_passant_capture_square
            self.castling_rights = previous_castling_rights
            print("Invalid move. King would be in check.")
            return False

        self.update_castling_rights(piece, from_square, captured_piece, captured_square)
        self.en_passant_target = None
        self.en_passant_capture_square = None
        if piece[1] == 'p' and abs(to_row - from_row) == 2:
            self.en_passant_target = ((from_row + to_row) // 2, from_col)
            self.en_passant_capture_square = to_square

        self.toggle_player()
        self.in_check = self.is_check(self.current_player)

        if self.is_checkmate(self.current_player):
            print(f"Checkmate! {moving_player} wins!")
            self.game_over = True
        elif self.is_stalemate(self.current_player):
            print("Stalemate!")
            self.game_over = True
        
        return True

    def get_piece(self, square):
        # Get the piece at a given square directly from the bitboards.
        bit = self.square_to_bit(square)
        for piece, bitboard_name in self.bitboards.items():
            if getattr(self, bitboard_name) & bit:
                return piece
        return '.'

    def set_piece(self, square, piece):
        # Clear the square from every bitboard, then optionally place a piece.
        bit = self.square_to_bit(square)
        clear_mask = ~bit
        for bitboard_name in self.bitboards.values():
            setattr(self, bitboard_name, getattr(self, bitboard_name) & clear_mask)

        if piece != '.':
            if piece not in self.bitboards:
                raise ValueError(f"Unknown piece: {piece}")
            bitboard_name = self.bitboards[piece]
            setattr(self, bitboard_name, getattr(self, bitboard_name) | bit)

        self.update_occupancy()

    def is_own_piece(self, piece):
        if self.current_player == 'white':
            return piece.startswith('w')
        return piece.startswith('b')

    def is_valid_move(self, piece, from_square, to_square):
        # Implement move validation logic based on the type of piece and game rules
        # This is a placeholder for actual move validation logic
        valid_moves_func_dict = {
            'wp': self.is_valid_wpawn_move,
            'bp': self.is_valid_bpawn_move,
            'wr': self.is_valid_rook_move,
            'br': self.is_valid_rook_move,
            'wn': self.is_valid_knight_move,
            'bn': self.is_valid_knight_move,
            'wb': self.is_valid_bishop_move,
            'bb': self.is_valid_bishop_move,
            'wq': self.is_valid_queen_move,
            'bq': self.is_valid_queen_move,
            'wk': self.is_valid_king_move,
            'bk': self.is_valid_king_move,
        }
        if piece not in valid_moves_func_dict:
            raise ValueError(f"Unknown piece type: {piece}")
        return valid_moves_func_dict[piece](from_square, to_square)

    def bit_to_square(self, bit):
        """Convert a single bitboard bit to a (row, col) square."""
        index = bit.bit_length() - 1
        return (index // 8, index % 8)

    def iter_bitboard_squares(self, bitboard):
        while bitboard:
            piece_bit = bitboard & -bitboard
            yield self.bit_to_square(piece_bit)
            bitboard &= bitboard - 1

    def evaluate_board(self, perspective='white'):
        """Evaluate the position in centipawns. Positive is good for perspective."""
        score = 0

        for piece, bitboard_name in self.bitboards.items():
            color = 'white' if piece[0] == 'w' else 'black'
            piece_type = piece[1]
            color_sign = 1 if color == 'white' else -1
            bitboard = getattr(self, bitboard_name)

            for square in self.iter_bitboard_squares(bitboard):
                score += color_sign * self.evaluate_piece(piece_type, color, square)

        score += self.evaluate_bishop_pair()
        score += self.evaluate_castling_rights()

        if self.is_check('white'):
            score -= 50
        if self.is_check('black'):
            score += 50

        if perspective == 'black':
            return -score
        return score

    def evaluate_piece(self, piece_type, color, square):
        row, col = square
        value = self.PIECE_VALUES[piece_type]

        if piece_type == 'p':
            advancement = row if color == 'white' else 7 - row
            file_center_bonus = 6 - abs(col * 2 - 7)
            return value + advancement * 8 + file_center_bonus

        center_bonus = 14 - (abs(row * 2 - 7) + abs(col * 2 - 7))
        if piece_type in ('n', 'b'):
            return value + center_bonus * 4
        if piece_type == 'q':
            return value + center_bonus
        if piece_type == 'r':
            advancement = row if color == 'white' else 7 - row
            return value + advancement * 2
        if piece_type == 'k':
            back_rank = row == 0 if color == 'white' else row == 7
            return 20 if back_rank and col in (1, 2, 6) else 0

        return value

    def evaluate_bishop_pair(self):
        score = 0
        if self.white_bishops.bit_count() >= 2:
            score += 30
        if self.black_bishops.bit_count() >= 2:
            score -= 30
        return score

    def evaluate_castling_rights(self):
        score = 0
        if self.castling_rights['white_kingside']:
            score += 10
        if self.castling_rights['white_queenside']:
            score += 10
        if self.castling_rights['black_kingside']:
            score -= 10
        if self.castling_rights['black_queenside']:
            score -= 10
        return score

    def get_all_legal_moves(self, player=None):
        player = player or self.current_player
        previous_player = self.current_player
        self.current_player = player
        legal_moves = []

        try:
            for piece, bitboard_name in self.bitboards.items():
                if not piece.startswith(player[0]):
                    continue

                for from_square in self.iter_bitboard_squares(getattr(self, bitboard_name)):
                    for row in range(8):
                        for col in range(8):
                            to_square = (row, col)
                            if not self.is_valid_move(piece, from_square, to_square):
                                continue

                            promotion_pieces = self.get_promotion_options_for_move(piece, to_square)
                            for promotion_piece in promotion_pieces:
                                if self.move_keeps_king_safe(piece, from_square, to_square, promotion_piece):
                                    legal_moves.append((from_square, to_square, promotion_piece))
        finally:
            self.current_player = previous_player

        return legal_moves

    def get_promotion_options_for_move(self, piece, to_square):
        if piece == 'wp' and to_square[0] == 7:
            return ['wq', 'wr', 'wb', 'wn']
        if piece == 'bp' and to_square[0] == 0:
            return ['bq', 'br', 'bb', 'bn']
        return [None]

    def move_keeps_king_safe(self, piece, from_square, to_square, promotion_piece=None):
        moving_player = 'white' if piece[0] == 'w' else 'black'
        from_row, from_col = from_square
        _, to_col = to_square
        is_castling = piece[1] == 'k' and abs(to_col - from_col) == 2
        is_en_passant = self.is_en_passant_move(piece, from_square, to_square)
        captured_square = self.en_passant_capture_square if is_en_passant else to_square
        captured_piece = self.get_piece(captured_square)
        placed_piece = self.get_promotion_piece(piece, to_square, promotion_piece)

        self.set_piece(from_square, '.')
        if is_en_passant:
            self.set_piece(captured_square, '.')
        self.set_piece(to_square, placed_piece)

        if is_castling:
            rook_from, rook_to = self.get_castling_rook_squares(from_square, to_square)
            rook_piece = self.get_piece(rook_from)
            self.set_piece(rook_from, '.')
            self.set_piece(rook_to, rook_piece)

        is_safe = not self.is_check(moving_player)

        if is_castling:
            rook_from, rook_to = self.get_castling_rook_squares(from_square, to_square)
            rook_piece = self.get_piece(rook_to)
            self.set_piece(rook_to, '.')
            self.set_piece(rook_from, rook_piece)
        self.set_piece(to_square, '.')
        self.set_piece(captured_square, captured_piece)
        self.set_piece(from_square, piece)

        return is_safe

    def get_best_move(self, player='black', depth=2):
        previous_player = self.current_player
        self.current_player = player
        legal_moves = self.order_moves(self.get_all_legal_moves(player))
        self.current_player = previous_player

        if not legal_moves:
            return None

        best_move = None
        best_score = -float('inf') if player == 'black' else float('inf')
        alpha = -float('inf')
        beta = float('inf')

        for move in legal_moves:
            next_position = copy.deepcopy(self)
            next_position.current_player = player
            next_position.move_piece(*move)
            score = next_position.alpha_beta(depth - 1, alpha, beta)

            if player == 'black':
                if score > best_score:
                    best_score = score
                    best_move = move
                alpha = max(alpha, best_score)
            else:
                if score < best_score:
                    best_score = score
                    best_move = move
                beta = min(beta, best_score)

        return best_move

    def alpha_beta(self, depth, alpha, beta):
        if depth == 0 or self.game_over:
            return self.evaluate_board('black')

        player = self.current_player
        legal_moves = self.order_moves(self.get_all_legal_moves(player))
        if not legal_moves:
            if self.is_check(player):
                return -100000 - depth if player == 'black' else 100000 + depth
            return 0

        if player == 'black':
            value = -float('inf')
            for move in legal_moves:
                next_position = copy.deepcopy(self)
                next_position.move_piece(*move)
                value = max(value, next_position.alpha_beta(depth - 1, alpha, beta))
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = float('inf')
        for move in legal_moves:
            next_position = copy.deepcopy(self)
            next_position.move_piece(*move)
            value = min(value, next_position.alpha_beta(depth - 1, alpha, beta))
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    def order_moves(self, moves):
        return sorted(moves, key=self.score_move_for_ordering, reverse=True)

    def score_move_for_ordering(self, move):
        from_square, to_square, promotion_piece = move
        moving_piece = self.get_piece(from_square)
        captured_piece = self.get_piece(to_square)
        if self.is_en_passant_move(moving_piece, from_square, to_square):
            captured_piece = self.get_piece(self.en_passant_capture_square)

        score = 0
        if captured_piece != '.':
            score += self.PIECE_VALUES[captured_piece[1]] - self.PIECE_VALUES[moving_piece[1]] // 10
        if promotion_piece is not None:
            score += self.PIECE_VALUES[promotion_piece[1]]
        return score

    def get_promotion_piece(self, piece, to_square, promotion_piece):
        if piece == 'wp' and to_square[0] == 7:
            return promotion_piece if promotion_piece in ('wq', 'wr', 'wb', 'wn') else 'wq'
        if piece == 'bp' and to_square[0] == 0:
            return promotion_piece if promotion_piece in ('bq', 'br', 'bb', 'bn') else 'bq'
        return piece

    def get_castling_rook_squares(self, from_square, to_square):
        row = from_square[0]
        if to_square[1] > from_square[1]:
            return (row, 7), (row, 5)
        return (row, 0), (row, 3)

    def is_en_passant_move(self, piece, from_square, to_square):
        if piece[1] != 'p' or to_square != self.en_passant_target:
            return False
        if self.en_passant_capture_square is None or self.get_piece(to_square) != '.':
            return False

        from_row, from_col = from_square
        to_row, to_col = to_square
        captured_piece = self.get_piece(self.en_passant_capture_square)

        if piece == 'wp':
            return (
                to_row == from_row + 1
                and abs(to_col - from_col) == 1
                and self.en_passant_capture_square == (from_row, to_col)
                and captured_piece == 'bp'
            )

        if piece == 'bp':
            return (
                to_row == from_row - 1
                and abs(to_col - from_col) == 1
                and self.en_passant_capture_square == (from_row, to_col)
                and captured_piece == 'wp'
            )

        return False

    def update_castling_rights(self, piece, from_square, captured_piece='.', captured_square=None):
        if piece == 'wk':
            self.castling_rights['white_kingside'] = False
            self.castling_rights['white_queenside'] = False
        elif piece == 'bk':
            self.castling_rights['black_kingside'] = False
            self.castling_rights['black_queenside'] = False
        elif piece == 'wr':
            if from_square == (0, 0):
                self.castling_rights['white_queenside'] = False
            elif from_square == (0, 7):
                self.castling_rights['white_kingside'] = False
        elif piece == 'br':
            if from_square == (7, 0):
                self.castling_rights['black_queenside'] = False
            elif from_square == (7, 7):
                self.castling_rights['black_kingside'] = False

        if captured_piece == 'wr':
            if captured_square == (0, 0):
                self.castling_rights['white_queenside'] = False
            elif captured_square == (0, 7):
                self.castling_rights['white_kingside'] = False
        elif captured_piece == 'br':
            if captured_square == (7, 0):
                self.castling_rights['black_queenside'] = False
            elif captured_square == (7, 7):
                self.castling_rights['black_kingside'] = False

    def is_check(self, player=None):
        player = player or self.current_player
        king_bit = self.white_king if player == 'white' else self.black_king
        if not king_bit:
            return False

        king_square = self.bit_to_square(king_bit)
        opponent = 'black' if player == 'white' else 'white'
        return self.is_square_attacked(king_square, opponent)

    def is_square_attacked(self, square, attacker):
        attacker_prefix = attacker[0]
        for piece, bitboard_name in self.bitboards.items():
            if not piece.startswith(attacker_prefix):
                continue

            pieces = getattr(self, bitboard_name)
            while pieces:
                piece_bit = pieces & -pieces
                from_square = self.bit_to_square(piece_bit)
                if self.piece_attacks_square(piece, from_square, square):
                    return True
                pieces &= pieces - 1

        return False

    def piece_attacks_square(self, piece, from_square, target_square):
        from_row, from_col = from_square
        target_row, target_col = target_square
        row_diff = target_row - from_row
        col_diff = target_col - from_col
        row_diff_abs = abs(row_diff)
        col_diff_abs = abs(col_diff)

        if piece == 'wp':
            return row_diff == 1 and col_diff_abs == 1
        if piece == 'bp':
            return row_diff == -1 and col_diff_abs == 1
        if piece[1] == 'n':
            return (row_diff_abs, col_diff_abs) in ((2, 1), (1, 2))
        if piece[1] == 'k':
            return max(row_diff_abs, col_diff_abs) == 1
        if piece[1] == 'b':
            return self.is_clear_diagonal(from_square, target_square)
        if piece[1] == 'r':
            return self.is_clear_straight(from_square, target_square)
        if piece[1] == 'q':
            return self.is_clear_diagonal(from_square, target_square) or self.is_clear_straight(from_square, target_square)
        return False

    def is_clear_diagonal(self, from_square, to_square):
        from_row, from_col = from_square
        to_row, to_col = to_square
        row_diff = to_row - from_row
        col_diff = to_col - from_col
        row_diff_abs = abs(row_diff)

        if row_diff_abs == 0 or row_diff_abs != abs(col_diff):
            return False

        row_step = 1 if row_diff > 0 else -1
        col_step = 1 if col_diff > 0 else -1
        for i in range(1, row_diff_abs):
            if self.occupied & self.square_to_bit((from_row + row_step * i, from_col + col_step * i)):
                return False
        return True

    def is_clear_straight(self, from_square, to_square):
        from_row, from_col = from_square
        to_row, to_col = to_square
        row_diff = to_row - from_row
        col_diff = to_col - from_col

        if (row_diff == 0 and col_diff == 0) or (row_diff != 0 and col_diff != 0):
            return False

        row_step = 0 if row_diff == 0 else (1 if row_diff > 0 else -1)
        col_step = 0 if col_diff == 0 else (1 if col_diff > 0 else -1)
        distance = max(abs(row_diff), abs(col_diff))
        for i in range(1, distance):
            if self.occupied & self.square_to_bit((from_row + row_step * i, from_col + col_step * i)):
                return False
        return True

    def is_checkmate(self, player=None):
        player = player or self.current_player
        return self.is_check(player) and len(self.get_all_legal_moves(player)) == 0

    def is_stalemate(self, player=None):
        player = player or self.current_player
        return not self.is_check(player) and len(self.get_all_legal_moves(player)) == 0

    def toggle_player(self):
        self.current_player = 'black' if self.current_player == 'white' else 'white'

    def is_valid_wpawn_move(self, from_square, to_square):
        # Implement white pawn move validation logic
        from_row, from_col = from_square
        to_row, to_col = to_square

        # Vertical move
        # Normal move: 1 square forward
        if to_col == from_col and to_row == from_row + 1:
            one_ahead = self.square_to_bit(to_square)
            return not (self.occupied & one_ahead)

        # 2 squares forward from starting position
        if from_row == 1 and to_col == from_col and to_row == from_row + 2:
            one_ahead = self.square_to_bit((from_row + 1, from_col))
            two_ahead = self.square_to_bit(to_square)
            return not (self.occupied & one_ahead) and not (self.occupied & two_ahead)

        # Capture move: 1 square diagonally forward
        if to_row == from_row + 1 and abs(to_col - from_col) == 1:
            target_bit = self.square_to_bit(to_square)
            if self.black_pieces & target_bit:
                return True
            if self.is_en_passant_move('wp', from_square, to_square):
                return True
            
        return False
    
    def is_valid_bpawn_move(self, from_square, to_square):
        # Implement black pawn move validation logic
        from_row, from_col = from_square
        to_row, to_col = to_square

        # Vertical move
        # Normal move: 1 square forward
        if to_col == from_col and to_row == from_row - 1:
            one_down = self.square_to_bit(to_square)
            return not (self.occupied & one_down)

        # 2 squares forward from starting position
        if from_row == 6 and to_col == from_col and to_row == from_row - 2:
            one_down = self.square_to_bit((from_row - 1, from_col))
            two_down = self.square_to_bit(to_square)
            return not (self.occupied & one_down) and not (self.occupied & two_down)

        # Capture move: 1 square diagonally forward
        if to_row == from_row - 1 and abs(to_col - from_col) == 1:
            target_bit = self.square_to_bit(to_square)
            if self.white_pieces & target_bit:
                return True
            if self.is_en_passant_move('bp', from_square, to_square):
                return True
            
        return False
    
    def is_valid_rook_move(self, from_square, to_square):
        # Implement rook move validation logic
        from_row, from_col = from_square
        to_row, to_col = to_square
        
        row_diff = from_row-to_row
        row_diff_abs = abs(row_diff)
        col_diff = from_col-to_col
        col_diff_abs = abs(col_diff)

        # On same position or digonal moves are not allowed
        if (row_diff_abs==0 and col_diff_abs==0) or (row_diff_abs != 0 and col_diff_abs != 0):
            return False
        
        for i in range(1, row_diff_abs):
            if row_diff < 0:
                one_row_move = self.square_to_bit((from_row+i, from_col))
            else:
                one_row_move = self.square_to_bit((from_row-i, from_col))
            if self.occupied & one_row_move:
                return False

        for i in range(1, col_diff_abs):
            if col_diff < 0:
                one_col_move = self.square_to_bit((from_row, from_col+i))
            else:
                one_col_move = self.square_to_bit((from_row, from_col-i))
            if self.occupied & one_col_move:
                return False

        # Target square must not be occupied by own piece
        target_bit = self.square_to_bit(to_square)
        own_pieces = self.white_pieces if self.current_player == 'white' else self.black_pieces
        if own_pieces & target_bit:
            return False
                
        return True
    
    def is_valid_knight_move(self, from_square, to_square):
        # Implement knight move validation logic
        from_row, from_col = from_square
        to_row, to_col = to_square

        row_diff_abs = abs(from_row - to_row)
        col_diff_abs = abs(from_col - to_col)
        if (row_diff_abs, col_diff_abs) not in ((2, 1), (1, 2)):
            return False

        target_bit = self.square_to_bit(to_square)
        own_pieces = self.white_pieces if self.current_player == 'white' else self.black_pieces
        if own_pieces & target_bit:
            return False
        
        return True
    
    def is_valid_bishop_move(self, from_square, to_square):
        # Implement bishop move validation logic
        from_row, from_col = from_square
        to_row, to_col = to_square

        row_diff = to_row - from_row
        col_diff = to_col - from_col
        row_diff_abs = abs(row_diff)
        col_diff_abs = abs(col_diff)

        if row_diff_abs == 0 or row_diff_abs != col_diff_abs:
            return False

        row_step = 1 if row_diff > 0 else -1
        col_step = 1 if col_diff > 0 else -1
        for i in range(1, row_diff_abs):
            square_bit = self.square_to_bit((from_row + row_step * i, from_col + col_step * i))
            if self.occupied & square_bit:
                return False

        target_bit = self.square_to_bit(to_square)
        own_pieces = self.white_pieces if self.current_player == 'white' else self.black_pieces
        if own_pieces & target_bit:
            return False

        return True
    
    def is_valid_queen_move(self, from_square, to_square):
        # Implement queen move validation logic
        from_row, from_col = from_square
        to_row, to_col = to_square

        row_diff_abs = abs(from_row - to_row)
        col_diff_abs = abs(from_col - to_col)

        if row_diff_abs == col_diff_abs:
            return self.is_valid_bishop_move(from_square, to_square)
        if row_diff_abs == 0 or col_diff_abs == 0:
            return self.is_valid_rook_move(from_square, to_square)

        return False
    
    def is_valid_king_move(self, from_square, to_square):
        # Implement king move validation logic
        from_row, from_col = from_square
        to_row, to_col = to_square

        row_diff_abs = abs(from_row - to_row)
        col_diff_abs = abs(from_col - to_col)
        if row_diff_abs == 0 and col_diff_abs == 2:
            return self.is_valid_castling_move(from_square, to_square)

        if row_diff_abs > 1 or col_diff_abs > 1 or (row_diff_abs == 0 and col_diff_abs == 0):
            return False

        target_bit = self.square_to_bit(to_square)
        own_pieces = self.white_pieces if self.current_player == 'white' else self.black_pieces
        if own_pieces & target_bit:
            return False

        return True

    def is_valid_castling_move(self, from_square, to_square):
        player = self.current_player
        row = 0 if player == 'white' else 7
        king_piece = 'wk' if player == 'white' else 'bk'
        rook_piece = 'wr' if player == 'white' else 'br'
        opponent = 'black' if player == 'white' else 'white'

        if from_square != (row, 4) or self.get_piece(from_square) != king_piece:
            return False
        if to_square not in ((row, 6), (row, 2)):
            return False
        if self.is_check(player):
            return False

        if to_square[1] == 6:
            right_key = f'{player}_kingside'
            rook_square = (row, 7)
            empty_squares = [(row, 5), (row, 6)]
            checked_squares = [(row, 5), (row, 6)]
        else:
            right_key = f'{player}_queenside'
            rook_square = (row, 0)
            empty_squares = [(row, 1), (row, 2), (row, 3)]
            checked_squares = [(row, 3), (row, 2)]

        if not self.castling_rights[right_key]:
            return False
        if self.get_piece(rook_square) != rook_piece:
            return False
        for square in empty_squares:
            if self.occupied & self.square_to_bit(square):
                return False
        for square in checked_squares:
            if self.is_square_attacked(square, opponent):
                return False

        return True
    
