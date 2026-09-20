# 🏛️ Auction Empire (Dominator-v2)

A pass-the-device auction game for you and your friends — bid on companies and stocks, team up on deals, and try to end the game with the biggest empire.

This is the **GUI version** of a game originally designed and played by "Raakin khan" (and friends) in school and college. The auction engine (`main.py`) is entirely hand-written; the point-and-click Tkinter interface (`gui.py`) was built with AI assistance (Claude) to speed up the repetitive UI work. If you'd rather play the original, no-frills version, check out the CLI edition of this game.

## How it works

Each round, one asset comes up for auction. Players take turns raising the bid, teaming up with another player for a joint bid, or folding. A round ends once only one bidder is left standing — the last bid on the table wins.

| Asset | What it does |
|---|---|
| 🏢 **Company** | Pays its full value out as cash again at the start of every later round. Buy early, collect often. |
| 📈 **Stock** | After winning, call 0 or 1 on a coin toss. Guess right and you gain the stock's value in cash. Guess wrong and you just lose what you paid. |
| 💀 **Death Stock** | The same coin toss as a Stock, but guessing wrong wipes out **all** of your cash and company value. |
| 🎰 **Jackpot Company** | Five companies bundled together. You pick one of five mystery slots blind and keep whatever it's worth. |

**Deals:** on your turn you can invite another player to bid with you, splitting both the cost and the eventual winnings by whatever percentages you agree on.

**Scoring:** your final score is your cash plus your company value multiplied by the number of rounds, so holding companies pays off the longer the game runs.

## Requirements

- Python 3.10+ (uses modern type-hint syntax like `list[dict]`)
- Tkinter (bundled with most standard Python installs — on Linux you may need `sudo apt install python3-tk`)

No third-party packages or `requirements.txt` needed — everything runs on the standard library.

## Running the game

```bash
git clone https://github.com/raakinkhan/Dominator-v2.git
cd Dominator-v2
python3 gui.py
```

`gui.py` imports the `Auctioneer` engine from `main.py`, so keep both files in the same folder.

This is a **local, single-screen game** — everyone plays on one machine, passing the device to whoever's turn it is.

### Setup screen options

When you launch the game you can configure:

- **Number of players** (2–8)
- **Number of rounds** (3–30)
- **Starting cash** per player
- **Company vs. stock mix** — a slider controlling what fraction of assets are companies vs. stocks
- **Jackpot companies** and **Death stocks** — how many of each rare/high-risk asset appear

A live preview shows exactly how many of each asset type will be generated before you start.

## Project structure

```
Dominator-v2/
├── main.py    # Core game engine (Auctioneer class): accounts, asset generation, bidding, payouts
├── gui.py     # Tkinter GUI that drives the engine turn-by-turn
└── LICENSE
```

- **`main.py`** — the `Auctioneer` class manages player accounts, generates a balanced, randomised set of assets per game, validates and tracks bids (including joint bids split between two players), and resolves each round's payout (including the coin-toss mechanic for stocks and death stocks).
- **`gui.py`** — a Tkinter front end with setup, player-naming, live bidding (including deal-making and folding), and end-game screens, plus an in-app "How to Play" reference.

## License

All rights reserved © 2026 Raakin Khan. No permission is granted to modify, distribute, reproduce, or create derivative works from this software without prior permission. See [`LICENSE`](./LICENSE) for the full text.
