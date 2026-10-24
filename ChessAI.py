"""
Fast search for the chess AI. Copies the GameEngine position into a 64-square board
and searches it with make/unmake, alpha-beta, a transposition table, iterative deepening
and a capture-only quiescence search.
Square index is row * 8 + col, the same layout as the GameEngine bitboards.
"""
import random

PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 1, 2, 3, 4, 5, 6
WHITE, BLACK = 0, 8  # A piece is color | type, so black pieces are 9..14.

PIECE_CODES = {
    'wp': WHITE | PAWN, 'wn': WHITE | KNIGHT, 'wb': WHITE | BISHOP,
    'wr': WHITE | ROOK, 'wq': WHITE | QUEEN, 'wk': WHITE | KING,
    'bp': BLACK | PAWN, 'bn': BLACK | KNIGHT, 'bb': BLACK | BISHOP,
    'br': BLACK | ROOK, 'bq': BLACK | QUEEN, 'bk': BLACK | KING,
}
CODE_TO_PIECE = {code: piece for piece, code in PIECE_CODES.items()}
TYPE_LETTERS = {PAWN: 'p', KNIGHT: 'n', BISHOP: 'b', ROOK: 'r', QUEEN: 'q', KING: 'k'}
ORDER_VALUES = [0, 100, 320, 330, 500, 900, 2000]

MATE = 100000
INF = 10 ** 9
MAX_PLY = 64
TT_EXACT, TT_LOWER, TT_UPPER = 0, 1, 2

# Castling rights as bits: white kingside, white queenside, black kingside, black queenside.
CASTLE_WK, CASTLE_WQ, CASTLE_BK, CASTLE_BQ = 1, 2, 4, 8
CASTLE_KEYS = (
    ('white_kingside', CASTLE_WK),
    ('white_queenside', CASTLE_WQ),
    ('black_kingside', CASTLE_BK),
    ('black_queenside', CASTLE_BQ),
)
CASTLE_MASK = [15] * 64
CASTLE_MASK[0] &= ~CASTLE_WQ
CASTLE_MASK[7] &= ~CASTLE_WK
CASTLE_MASK[4] &= ~(CASTLE_WK | CASTLE_WQ)
CASTLE_MASK[56] &= ~CASTLE_BQ
CASTLE_MASK[63] &= ~CASTLE_BK
CASTLE_MASK[60] &= ~(CASTLE_BK | CASTLE_BQ)
# Same bonus as GameEngine.evaluate_castling_rights, from white's view.
CASTLE_SCORE = [
    10 * (bool(c & CASTLE_WK) + bool(c & CASTLE_WQ) - bool(c & CASTLE_BK) - bool(c & CASTLE_BQ))
    for c in range(16)
]


def build_targets(offsets):
    targets = []
    for sq in range(64):
        row, col = divmod(sq, 8)
        targets.append([
            (row + dr) * 8 + col + dc
            for dr, dc in offsets
            if 0 <= row + dr < 8 and 0 <= col + dc < 8
        ])
    return targets


def build_rays(directions):
    rays = []
    for sq in range(64):
        row, col = divmod(sq, 8)
        square_rays = []
        for dr, dc in directions:
            ray = []
            r, c = row + dr, col + dc
            while 0 <= r < 8 and 0 <= c < 8:
                ray.append(r * 8 + c)
                r += dr
                c += dc
            square_rays.append(ray)
        rays.append(square_rays)
    return rays


KNIGHT_TARGETS = build_targets([(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)])
KING_TARGETS = build_targets([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)])
DIAGONAL_RAYS = build_rays([(1, 1), (1, -1), (-1, 1), (-1, -1)])
STRAIGHT_RAYS = build_rays([(1, 0), (-1, 0), (0, 1), (0, -1)])
SLIDER_RAYS = {
    BISHOP: DIAGONAL_RAYS,
    ROOK: STRAIGHT_RAYS,
    QUEEN: [DIAGONAL_RAYS[sq] + STRAIGHT_RAYS[sq] for sq in range(64)],
}
# Squares a pawn of that color on sq attacks.
PAWN_ATTACKS = {
    WHITE: build_targets([(1, 1), (1, -1)]),
    BLACK: build_targets([(-1, 1), (-1, -1)]),
}

_rng = random.Random(20240601)
ZOBRIST_PIECE = [[_rng.getrandbits(64) for _ in range(64)] for _ in range(15)]
ZOBRIST_SIDE = _rng.getrandbits(64)
ZOBRIST_CASTLE = [_rng.getrandbits(64) for _ in range(16)]
ZOBRIST_EP = [_rng.getrandbits(64) for _ in range(8)]


def build_piece_square_table(engine):
    """Signed piece values per square (white positive), taken from GameEngine.evaluate_piece."""
    table = [[0] * 64 for _ in range(15)]
    for code, piece in CODE_TO_PIECE.items():
        color = 'white' if piece[0] == 'w' else 'black'
        sign = 1 if color == 'white' else -1
        for sq in range(64):
            table[code][sq] = sign * engine.evaluate_piece(piece[1], color, divmod(sq, 8))
    return table


class Searcher:
    def __init__(self, engine):
        self.board = [0] * 64
        for piece, bitboard_name in engine.bitboards.items():
            bitboard = getattr(engine, bitboard_name)
            while bitboard:
                bit = bitboard & -bitboard
                self.board[bit.bit_length() - 1] = PIECE_CODES[piece]
                bitboard &= bitboard - 1

        self.side = WHITE if engine.current_player == 'white' else BLACK
        self.castling = sum(bit for key, bit in CASTLE_KEYS if engine.castling_rights[key])
        target = engine.en_passant_target
        self.ep = target[0] * 8 + target[1] if target is not None else -1
        self.kings = [self.board.index(WHITE | KING), self.board.index(BLACK | KING)]

        self.pst = build_piece_square_table(engine)
        self.score = sum(self.pst[p][sq] for sq, p in enumerate(self.board) if p)
        self.hash = self.compute_hash()

        # Positions from the real game. Reaching one of them again counts as a draw.
        self.game_history = {self.hash_from_position_key(key) for key in engine.position_counts}
        self.path = []
        self.undo_stack = []
        self.tt = {}
        self.killers = [[0, 0] for _ in range(MAX_PLY + 1)]
        self.history = {}

    def compute_hash(self):
        h = ZOBRIST_CASTLE[self.castling]
        for sq, p in enumerate(self.board):
            if p:
                h ^= ZOBRIST_PIECE[p][sq]
        if self.side == BLACK:
            h ^= ZOBRIST_SIDE
        return h

    def hash_from_position_key(self, key):
        """Hash a GameEngine.get_position_key() tuple the same way as position_key()."""
        pieces_key, player, castling_key, en_passant_target = key
        h = 0
        for piece, bitboard in zip(('wp', 'wr', 'wn', 'wb', 'wq', 'wk', 'bp', 'br', 'bn', 'bb', 'bq', 'bk'), pieces_key):
            code = PIECE_CODES[piece]
            while bitboard:
                bit = bitboard & -bitboard
                h ^= ZOBRIST_PIECE[code][bit.bit_length() - 1]
                bitboard &= bitboard - 1
        if player == 'black':
            h ^= ZOBRIST_SIDE
        castling = sum(bit for has_right, (_, bit) in zip(castling_key, CASTLE_KEYS) if has_right)
        h ^= ZOBRIST_CASTLE[castling]
        if en_passant_target is not None:
            h ^= ZOBRIST_EP[en_passant_target[1]]
        return h

    def position_key(self):
        # Like GameEngine, the en passant square only counts if it can actually be captured.
        ep = self.ep
        if ep < 0:
            return self.hash
        pawn = PAWN | self.side
        for sq in PAWN_ATTACKS[self.side ^ BLACK][ep]:
            if self.board[sq] == pawn:
                return self.hash ^ ZOBRIST_EP[ep & 7]
        return self.hash

    def is_attacked(self, sq, by):
        board = self.board
        pawn = PAWN | by
        for s in PAWN_ATTACKS[by ^ BLACK][sq]:
            if board[s] == pawn:
                return True
        knight = KNIGHT | by
        for s in KNIGHT_TARGETS[sq]:
            if board[s] == knight:
                return True
        king = KING | by
        for s in KING_TARGETS[sq]:
            if board[s] == king:
                return True
        bishop, rook, queen = BISHOP | by, ROOK | by, QUEEN | by
        for ray in DIAGONAL_RAYS[sq]:
            for s in ray:
                p = board[s]
                if p:
                    if p == bishop or p == queen:
                        return True
                    break
        for ray in STRAIGHT_RAYS[sq]:
            for s in ray:
                p = board[s]
                if p:
                    if p == rook or p == queen:
                        return True
                    break
        return False

    def in_check(self, color):
        return self.is_attacked(self.kings[color >> 3], color ^ BLACK)

    def generate_moves(self, captures_only=False):
        """Pseudo-legal moves encoded as from | to << 6 | promotion << 12."""
        board = self.board
        side = self.side
        enemy = side ^ BLACK
        moves = []
        append = moves.append

        for fr in range(64):
            p = board[fr]
            if not p or (p & BLACK) != side:
                continue
            kind = p & 7

            if kind == PAWN:
                if side == WHITE:
                    step, start_row, promotion_row = 8, 1, 7
                else:
                    step, start_row, promotion_row = -8, 6, 0
                to = fr + step
                promotes = to >> 3 == promotion_row
                if not board[to]:
                    if promotes:
                        for kind_to in (QUEEN, ROOK, BISHOP, KNIGHT):
                            if not captures_only or kind_to == QUEEN:
                                append(fr | to << 6 | (side | kind_to) << 12)
                    elif not captures_only:
                        append(fr | to << 6)
                        if fr >> 3 == start_row and not board[to + step]:
                            append(fr | (to + step) << 6)
                for to in PAWN_ATTACKS[side][fr]:
                    target = board[to]
                    if target and (target & BLACK) == enemy:
                        if promotes:
                            for kind_to in (QUEEN, ROOK, BISHOP, KNIGHT):
                                append(fr | to << 6 | (side | kind_to) << 12)
                        else:
                            append(fr | to << 6)
                    elif to == self.ep and not target:
                        append(fr | to << 6)

            elif kind == KNIGHT or kind == KING:
                for to in (KNIGHT_TARGETS if kind == KNIGHT else KING_TARGETS)[fr]:
                    target = board[to]
                    if not target:
                        if not captures_only:
                            append(fr | to << 6)
                    elif (target & BLACK) == enemy:
                        append(fr | to << 6)
                if kind == KING and not captures_only:
                    self.add_castling_moves(fr, moves)

            else:
                for ray in SLIDER_RAYS[kind][fr]:
                    for to in ray:
                        target = board[to]
                        if not target:
                            if not captures_only:
                                append(fr | to << 6)
                            continue
                        if (target & BLACK) == enemy:
                            append(fr | to << 6)
                        break

        return moves

    def add_castling_moves(self, fr, moves):
        side = self.side
        if side == WHITE:
            home, kingside, queenside = 4, CASTLE_WK, CASTLE_WQ
        else:
            home, kingside, queenside = 60, CASTLE_BK, CASTLE_BQ
        if fr != home or not self.castling & (kingside | queenside):
            return
        board = self.board
        enemy = side ^ BLACK
        rook = ROOK | side
        if self.is_attacked(fr, enemy):
            return
        if (self.castling & kingside and board[fr + 3] == rook
                and not board[fr + 1] and not board[fr + 2]
                and not self.is_attacked(fr + 1, enemy) and not self.is_attacked(fr + 2, enemy)):
            moves.append(fr | (fr + 2) << 6)
        if (self.castling & queenside and board[fr - 4] == rook
                and not board[fr - 1] and not board[fr - 2] and not board[fr - 3]
                and not self.is_attacked(fr - 1, enemy) and not self.is_attacked(fr - 2, enemy)):
            moves.append(fr | (fr - 2) << 6)

    def make(self, move):
        board = self.board
        pst = self.pst
        fr = move & 63
        to = (move >> 6) & 63
        promotion = move >> 12
        p = board[fr]
        kind = p & 7
        captured = board[to]
        captured_sq = to
        h = self.hash
        score = self.score

        if kind == PAWN and to == self.ep and not captured and (to - fr) % 8:
            captured_sq = to - 8 if self.side == WHITE else to + 8
            captured = board[captured_sq]
            board[captured_sq] = 0

        self.undo_stack.append((move, captured, captured_sq, self.castling, self.ep, h, score))

        if captured:
            h ^= ZOBRIST_PIECE[captured][captured_sq]
            score -= pst[captured][captured_sq]

        placed = promotion or p
        board[fr] = 0
        board[to] = placed
        h ^= ZOBRIST_PIECE[p][fr] ^ ZOBRIST_PIECE[placed][to]
        score += pst[placed][to] - pst[p][fr]

        if kind == KING:
            self.kings[self.side >> 3] = to
            if to - fr == 2 or fr - to == 2:
                rook_from, rook_to = (fr + 3, fr + 1) if to > fr else (fr - 4, fr - 1)
                rook = board[rook_from]
                board[rook_from] = 0
                board[rook_to] = rook
                h ^= ZOBRIST_PIECE[rook][rook_from] ^ ZOBRIST_PIECE[rook][rook_to]
                score += pst[rook][rook_to] - pst[rook][rook_from]

        castling = self.castling & CASTLE_MASK[fr] & CASTLE_MASK[to]
        h ^= ZOBRIST_CASTLE[self.castling] ^ ZOBRIST_CASTLE[castling]
        self.castling = castling

        self.ep = (fr + to) >> 1 if kind == PAWN and (to - fr == 16 or fr - to == 16) else -1
        self.side ^= BLACK
        self.hash = h ^ ZOBRIST_SIDE
        self.score = score

    def unmake(self):
        move, captured, captured_sq, castling, ep, h, score = self.undo_stack.pop()
        board = self.board
        self.side ^= BLACK
        fr = move & 63
        to = (move >> 6) & 63
        p = board[to]
        if move >> 12:
            p = PAWN | self.side

        board[fr] = p
        board[to] = 0
        if captured:
            board[captured_sq] = captured

        if p & 7 == KING:
            self.kings[self.side >> 3] = fr
            if to - fr == 2 or fr - to == 2:
                rook_from, rook_to = (fr + 3, fr + 1) if to > fr else (fr - 4, fr - 1)
                board[rook_from] = board[rook_to]
                board[rook_to] = 0

        self.castling = castling
        self.ep = ep
        self.hash = h
        self.score = score

    def evaluate(self):
        """Same score as GameEngine.evaluate_board, from the side to move's view."""
        board = self.board
        score = self.score + CASTLE_SCORE[self.castling]
        if board.count(WHITE | BISHOP) >= 2:
            score += 30
        if board.count(BLACK | BISHOP) >= 2:
            score -= 30
        if self.in_check(WHITE):
            score -= 50
        if self.in_check(BLACK):
            score += 50
        return score if self.side == WHITE else -score

    def order_moves(self, moves, tt_move=0, ply=0):
        board = self.board
        killers = self.killers[ply]
        history = self.history
        scored = []
        for move in moves:
            if move == tt_move:
                priority = 10_000_000
            else:
                captured = board[(move >> 6) & 63]
                if captured:
                    priority = 1_000_000 + ORDER_VALUES[captured & 7] * 10 - ORDER_VALUES[board[move & 63] & 7] // 10
                elif move >> 12:
                    priority = 900_000 + ORDER_VALUES[(move >> 12) & 7]
                elif move == killers[0] or move == killers[1]:
                    priority = 800_000
                else:
                    priority = history.get(move, 0)
            scored.append((priority, move))
        scored.sort(reverse=True)
        return [move for _, move in scored]

    def search(self, depth, alpha, beta, ply):
        if depth <= 0 or ply >= MAX_PLY:
            return self.quiesce(alpha, beta, ply)

        key = self.position_key()
        if ply and (key in self.game_history or key in self.path):
            return 0

        alpha_start = alpha
        tt_move = 0
        entry = self.tt.get(key)
        if entry is not None:
            entry_depth, entry_score, entry_flag, tt_move = entry
            if ply and entry_depth >= depth:
                if entry_score > MATE - MAX_PLY:
                    entry_score -= ply
                elif entry_score < -MATE + MAX_PLY:
                    entry_score += ply
                if entry_flag == TT_EXACT:
                    return entry_score
                if entry_flag == TT_LOWER and entry_score >= beta:
                    return entry_score
                if entry_flag == TT_UPPER and entry_score <= alpha:
                    return entry_score

        side = self.side
        enemy = side ^ BLACK
        king_index = side >> 3
        best_score = -INF
        best_move = 0
        legal_moves = 0

        self.path.append(key)
        for move in self.order_moves(self.generate_moves(), tt_move, ply):
            self.make(move)
            if self.is_attacked(self.kings[king_index], enemy):
                self.unmake()
                continue
            legal_moves += 1
            score = -self.search(depth - 1, -beta, -alpha, ply + 1)
            self.unmake()

            if score > best_score:
                best_score = score
                best_move = move
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        if not self.board[(move >> 6) & 63] and not move >> 12:
                            killers = self.killers[ply]
                            if killers[0] != move:
                                killers[1] = killers[0]
                                killers[0] = move
                            self.history[move] = self.history.get(move, 0) + depth * depth
                        break
        self.path.pop()

        if not legal_moves:
            return -MATE + ply if self.in_check(side) else 0

        if best_score <= alpha_start:
            flag = TT_UPPER
        elif best_score >= beta:
            flag = TT_LOWER
        else:
            flag = TT_EXACT
        stored_score = best_score
        if stored_score > MATE - MAX_PLY:
            stored_score += ply
        elif stored_score < -MATE + MAX_PLY:
            stored_score -= ply
        self.tt[key] = (depth, stored_score, flag, best_move)
        return best_score

    def quiesce(self, alpha, beta, ply):
        """Only follow captures (or all moves when in check) so the search stops in quiet positions."""
        side = self.side
        enemy = side ^ BLACK
        king_index = side >> 3
        in_check = self.in_check(side)

        if in_check and ply < MAX_PLY:
            best_score = -INF
            moves = self.generate_moves()
        else:
            best_score = self.evaluate()
            if best_score >= beta or ply >= MAX_PLY:
                return best_score
            if best_score > alpha:
                alpha = best_score
            moves = self.generate_moves(captures_only=True)

        legal_moves = 0
        for move in self.order_moves(moves, ply=ply):
            self.make(move)
            if self.is_attacked(self.kings[king_index], enemy):
                self.unmake()
                continue
            legal_moves += 1
            score = -self.quiesce(-beta, -alpha, ply + 1)
            self.unmake()

            if score > best_score:
                best_score = score
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break

        if in_check and not legal_moves:
            return -MATE + ply
        return best_score

    def find_best_move(self, depth):
        best_move = 0
        for current_depth in range(1, depth + 1):
            score = self.search(current_depth, -INF, INF, 0)
            entry = self.tt.get(self.position_key())
            if entry is None:
                return 0  # No legal moves.
            best_move = entry[3]
            if abs(score) > MATE - MAX_PLY:
                break  # Forced mate found, deeper search won't change it.
        return best_move

    def move_to_engine_format(self, move):
        fr = move & 63
        to = (move >> 6) & 63
        promotion = move >> 12
        promotion_piece = CODE_TO_PIECE[promotion] if promotion else None
        return divmod(fr, 8), divmod(to, 8), promotion_piece


def find_best_move(engine, player, depth):
    """Return the best move for player as (from_square, to_square, promotion_piece), or None."""
    previous_player = engine.current_player
    engine.current_player = player
    try:
        searcher = Searcher(engine)
    finally:
        engine.current_player = previous_player

    best_move = searcher.find_best_move(max(1, depth))
    if not best_move:
        return None
    return searcher.move_to_engine_format(best_move)
