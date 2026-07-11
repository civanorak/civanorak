"""Issue-driven tic-tac-toe for the profile README.

Modes:
    python3 scripts/tictactoe.py render   # re-render board section only
    python3 scripts/tictactoe.py play     # apply move from ISSUE_TITLE/ISSUE_USER env

Issue title protocol:
    ttt|move|<0-8>   place X on a square (0 = top-left, row-major)
    ttt|new          reset the board
"""
import json
import os
import random
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "game" / "state.json"
README_PATH = ROOT / "README.md"
COMMENT_PATH = ROOT / "comment.txt"

REPO = "civanorak/civanorak"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/main/assets/ttt"
PROFILE_URL = "https://github.com/civanorak"
MARKER_START = "<!-- TTT-BOARD-START -->"
MARKER_END = "<!-- TTT-BOARD-END -->"

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]
CENTER = 4
CORNERS = [0, 2, 6, 8]
SIDES = [1, 3, 5, 7]

ISSUE_BODY = "Just press **Submit new issue** — the board on my profile updates automatically in ~30 seconds."


def load_state():
    with open(STATE_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def fresh_board(state):
    state["board"] = [None] * 9
    state["status"] = "playing"
    state["last_player"] = None


def winner(board):
    for a, b, c in WIN_LINES:
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
    if all(cell is not None for cell in board):
        return "draw"
    return None


def winning_square(board, mark):
    for i in range(9):
        if board[i] is None:
            board[i] = mark
            won = winner(board) == mark
            board[i] = None
            if won:
                return i
    return None


def bot_pick(board):
    move = winning_square(board, "O")
    if move is not None:
        return move
    move = winning_square(board, "X")
    if move is not None:
        return move
    if board[CENTER] is None:
        return CENTER
    open_corners = [i for i in CORNERS if board[i] is None]
    if open_corners:
        return random.choice(open_corners)
    open_sides = [i for i in SIDES if board[i] is None]
    if open_sides:
        return random.choice(open_sides)
    return None


def move_issue_url(square):
    title = urllib.parse.quote(f"ttt|move|{square}")
    body = urllib.parse.quote(ISSUE_BODY)
    return f"https://github.com/{REPO}/issues/new?title={title}&body={body}"


def new_game_url():
    title = urllib.parse.quote("ttt|new")
    body = urllib.parse.quote(ISSUE_BODY)
    return f"https://github.com/{REPO}/issues/new?title={title}&body={body}"


def render_cell(board, square, playing):
    mark = board[square]
    if mark == "X":
        return f'<img src="{RAW_BASE}/x.svg" width="70" height="70" alt="X" />'
    if mark == "O":
        return f'<img src="{RAW_BASE}/o.svg" width="70" height="70" alt="O" />'
    img = f'<img src="{RAW_BASE}/empty.svg" width="70" height="70" alt="empty square {square}" />'
    if playing:
        return f'<a href="{move_issue_url(square)}">{img}</a>'
    return img


def render_board(state):
    playing = state["status"] == "playing"
    rows = []
    for r in range(3):
        cells = "".join(
            f"<td>{render_cell(state['board'], r * 3 + c, playing)}</td>"
            for c in range(3)
        )
        rows.append(f"<tr>{cells}</tr>")
    table = "<table>\n" + "\n".join(rows) + "\n</table>"

    if state["status"] == "playing":
        status_line = "**Your move — you play ❌**"
    elif state["status"] == "x_won":
        who = f"@{state['last_player']}" if state.get("last_player") else "The community"
        status_line = f"**🏆 {who} beat the bot! Click any square to start a new game.**"
    elif state["status"] == "o_won":
        status_line = "**🤖 Bot wins this round. Click any square for a rematch.**"
    else:
        status_line = "**🤝 Draw. Click any square to play again.**"

    score = state["score"]
    score_line = (
        f"Community **{score['community']}** · Bot **{score['bot']}** · "
        f"Draws **{score['draws']}** &nbsp;|&nbsp; [🔄 New game]({new_game_url()})"
    )

    return (
        f"{MARKER_START}\n"
        f'<div align="center">\n\n'
        f"{table}\n\n"
        f"{status_line}\n\n"
        f"{score_line}\n\n"
        f"</div>\n"
        f"{MARKER_END}"
    )


def update_readme(state):
    content = README_PATH.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END), re.DOTALL)
    if not pattern.search(content):
        raise SystemExit("TTT markers not found in README.md")
    content = pattern.sub(lambda _: render_board(state), content)
    README_PATH.write_text(content, encoding="utf-8", newline="\n")


def write_comment(text):
    COMMENT_PATH.write_text(text + f"\n\n➡️ See the board: {PROFILE_URL}", encoding="utf-8")


def apply_move(state, square, user):
    if state["status"] != "playing":
        fresh_board(state)

    if state["board"][square] is not None:
        write_comment("⚠️ That square is already taken — pick an empty one.")
        return False

    state["board"][square] = "X"
    state["last_player"] = user

    result = winner(state["board"])
    if result == "X":
        state["status"] = "x_won"
        state["score"]["community"] += 1
        write_comment(f"🏆 **You beat the bot!** GG @{user} — the scoreboard remembers you.")
        return True
    if result == "draw":
        state["status"] = "draw"
        state["score"]["draws"] += 1
        write_comment("🤝 It's a draw! Well defended.")
        return True

    bot_square = bot_pick(state["board"])
    state["board"][bot_square] = "O"
    result = winner(state["board"])
    if result == "O":
        state["status"] = "o_won"
        state["score"]["bot"] += 1
        write_comment(
            f"✅ You played square {square}. 🤖 Bot answered with square {bot_square} "
            f"— and that's the game. Rematch?"
        )
        return True
    if result == "draw":
        state["status"] = "draw"
        state["score"]["draws"] += 1
        write_comment(f"✅ You played square {square}. 🤖 Bot answered with square {bot_square}. 🤝 Draw!")
        return True

    write_comment(f"✅ You played square {square}. 🤖 Bot answered with square {bot_square}. Your move!")
    return True


def play():
    title = os.environ.get("ISSUE_TITLE", "").strip()
    user = os.environ.get("ISSUE_USER", "someone").strip() or "someone"
    state = load_state()

    if title == "ttt|new":
        fresh_board(state)
        write_comment("🔄 Fresh board is up — you move first.")
    else:
        match = re.fullmatch(r"ttt\|move\|([0-8])", title)
        if not match:
            write_comment(
                "⚠️ I couldn't parse that move. Use the links on the board instead of "
                "editing the issue title."
            )
            return
        apply_move(state, int(match.group(1)), user)

    save_state(state)
    update_readme(state)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "render"
    if mode == "play":
        play()
    elif mode == "render":
        update_readme(load_state())
    else:
        raise SystemExit(f"unknown mode: {mode}")


if __name__ == "__main__":
    main()
