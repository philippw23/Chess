# Chess

A small Pygame chess game with a custom chess engine and a basic CPU opponent.

## Requirements

- Python 3
- Pygame

Install Pygame if it is not already installed:

```bash
pip install pygame
```

## Start the Game

Run the main file from the project folder:

```bash
python GameMain.py
```

## Controls

- Left-click one of your pieces to select it.
- Right-click a target square to move the selected piece.
- White is controlled by the player.
- Black is controlled by the CPU and moves automatically after a valid white move.

The board coordinates printed in the terminal are internal board coordinates. Row `0` is White's back rank and row `7` is Black's back rank.

## Special Moves

The engine supports:

- Castling
- En passant
- Pawn promotion
- Check validation
- Checkmate
- Stalemate

For pawn promotion, the board is dimmed and an overlay appears with promotion choices. Click the piece you want: queen, rook, bishop, or knight.

## AI

The CPU plays Black. It uses:

- legal move generation
- board evaluation in centipawns
- alpha-beta pruning search
- basic move ordering for captures and promotions

The evaluation function considers material, piece positioning, pawn advancement, bishop pair, castling rights, and check status.

The default search depth is configured in `GameMain.py`:

```python
CPU_SEARCH_DEPTH = 2
```

Increasing the depth makes the CPU stronger, but also slower.
