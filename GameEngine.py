"""
Game Engine for Chess Game. Handles game logic, move validation, and game state management.
"""
class GameEngine:
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
        row, col = square
        if not (0 <= row < 8 and 0 <= col < 8):
            raise ValueError("Square must be a (row, col) tuple with values from 0 to 7.")
        return 1 << (row * 8 + col)

    def move_piece(self, from_square, to_square):
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
        
        self.set_piece(to_square, piece)
        self.set_piece(from_square, '.')
        
        if self.is_checkmate():
            print(f"Checkmate! {self.current_player} wins!")
            self.game_over = True
        else:
            self.toggle_player()
        
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

    def is_checkmate(self):
        # Implement checkmate detection logic
        # This is a placeholder for actual checkmate detection
        return False

    def toggle_player(self):
        self.current_player = 'black' if self.current_player == 'white' else 'white'

    def is_valid_wpawn_move(self, from_square, to_square):
        # Implement white pawn move validation logic
        if starting_square := self.square_to_bit(from_square) & self.white_pawns:
            pass   
        return True
    
    def is_valid_bpawn_move(self, from_square, to_square):
        # Implement black pawn move validation logic
        return True
    
    def is_valid_rook_move(self, from_square, to_square):
        # Implement rook move validation logic
        return True
    
    def is_valid_knight_move(self, from_square, to_square):
        # Implement knight move validation logic
        return True
    
    def is_valid_bishop_move(self, from_square, to_square):
        # Implement bishop move validation logic
        return True
    
    def is_valid_queen_move(self, from_square, to_square):
        # Implement queen move validation logic
        return True
    
    def is_valid_king_move(self, from_square, to_square):
        # Implement king move validation logic
        return True
    