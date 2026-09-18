"""
Auction Empire - Tkinter GUI
-----------------------------
A point-and-click version of the auction game that used to be played
through CLI.py from the terminal. It reuses the same Auctioneer engine
from main.py, but drives it through a turn-based, click-through
interface instead of typed commands.

This is a local, pass-the-device game: everyone plays on one screen,
handing it to whoever's turn it is.

Run with:  python3 gui.py
(main.py must be in the same folder.)
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

from main import Auctioneer

# ------------------------------------------------------------------ #
#  Look & feel
# ------------------------------------------------------------------ #
BG = "#f4f3ef"
CARD_BG = "#ffffff"
MUTED = "#6b6f76"
ACCENT = "#2f6fed"
ACCENT_DARK = "#1d4ed8"
GOOD = "#1d7a3c"
BAD = "#b4232c"

FONT_TITLE = ("Georgia", 24, "bold")
FONT_H2 = ("Helvetica", 14, "bold")
FONT_BODY = ("Helvetica", 11)
FONT_BODY_BOLD = ("Helvetica", 11, "bold")
FONT_SMALL = ("Helvetica", 9)
FONT_BIG_EMOJI = ("Helvetica", 34)
FONT_MONEY = ("Helvetica", 13, "bold")

ASSET_META = {
    "company": {"label": "Company", "emoji": "\U0001F3E2", "color": "#1d6f42",
                "blurb": "Pays its full value out as cash again at the start of every later round."},
    "stock": {"label": "Stock", "emoji": "\U0001F4C8", "color": "#4a3f8f",
              "blurb": "Call the coin toss right and cash in - call it wrong and you just lose the bid."},
    "ds": {"label": "Death Stock", "emoji": "\U0001F480", "color": "#a3122c",
           "blurb": "The same toss as a Stock, but losing wipes out ALL of the winner's cash and company value."},
    "jc": {"label": "Jackpot Company", "emoji": "\U0001F3B0", "color": "#a97a1a",
           "blurb": "Five companies bundled together. Pick one of five mystery slots - blind."},
}


def money(x):
    try:
        return f"${x:,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def asset_preview(rounds, ratio_pct, jackpot, death):
    """Mirror generate_normalised()'s counting logic so the setup screen can
    show an honest preview before any assets actually get generated."""
    ratio = ratio_pct / 100
    company_freq = math.floor(ratio * rounds)
    stock_freq = rounds - company_freq
    normal_companies = max(company_freq - jackpot, 0)
    normal_stocks = max(stock_freq - death, 0)
    total = max(company_freq, jackpot) + max(stock_freq, death)
    return {
        "normal_companies": normal_companies,
        "jackpot": jackpot,
        "normal_stocks": normal_stocks,
        "death": death,
        "total": total,
        "rounds": rounds,
    }


class AuctionApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auction Empire")
        self.geometry("1100x740")
        self.minsize(960, 640)
        self.configure(bg=BG)

        self._init_style()

        # ----- setup-screen settings -----
        self.var_players = tk.IntVar(value=4)
        self.var_rounds = tk.IntVar(value=10)
        self.var_cash = tk.IntVar(value=100)
        self.var_ratio = tk.DoubleVar(value=50)
        self.var_jackpot = tk.IntVar(value=1)
        self.var_death = tk.IntVar(value=1)
        self.name_vars = []

        # ----- game state -----
        self.auctioneer = None
        self.assets = []
        self.current_round = 0
        self.out_bidders = set()
        self.sweep_pos = 0
        self.pending_split = {"cost": 1.0, "asset": 1.0}
        self.log_lines = []

        # widget refs populated by _build_game_screen / _build_setup_screen
        self.round_label = None
        self.asset_frame = None
        self.turn_frame = None
        self.scoreboard = None
        self.log_text = None
        self.preview_lbl = None
        self.ratio_value_lbl = None

        self.container = ttk.Frame(self, style="App.TFrame")
        self.container.pack(fill="both", expand=True)

        # Registered once here (not inside _build_setup_screen, which can run
        # again via Back/Play Again) so re-visiting the setup screen never
        # piles up duplicate callbacks pointing at already-destroyed labels.
        for var in (self.var_rounds, self.var_ratio, self.var_jackpot, self.var_death):
            var.trace_add("write", lambda *a: self._on_setting_change())

        self._build_setup_screen()

    # ================================================================ #
    #  Styling & small helpers
    # ================================================================ #
    def _init_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("TLabel", background=BG, font=FONT_BODY)
        style.configure("Card.TLabel", background=CARD_BG, font=FONT_BODY)
        style.configure("H2.TLabel", background=BG, font=FONT_H2)
        style.configure("CardH2.TLabel", background=CARD_BG, font=FONT_H2)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
        style.configure("CardMuted.TLabel", background=CARD_BG, foreground=MUTED, font=FONT_SMALL)
        style.configure("TButton", font=FONT_BODY_BOLD, padding=6)
        style.configure("Accent.TButton", font=FONT_BODY_BOLD, foreground="#ffffff",
                         background=ACCENT)
        style.map("Accent.TButton", background=[("active", ACCENT_DARK)],
                  foreground=[("active", "#ffffff")])
        style.configure("Treeview", font=FONT_BODY, rowheight=26)
        style.configure("Treeview.Heading", font=FONT_BODY_BOLD)

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _log(self, msg):
        self.log_lines.append(msg)
        if self.log_text is not None and self.log_text.winfo_exists():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

    def _active_ids(self):
        return [p for p in range(self.auctioneer.players) if p not in self.out_bidders]

    def _name(self, pid):
        return self.auctioneer.accounts[pid]["name"]

    # ================================================================ #
    #  SCREEN 1 - setup
    # ================================================================ #
    def _build_setup_screen(self):
        self._clear()
        wrap = ttk.Frame(self.container, style="App.TFrame", padding=30)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="\U0001F3DB\uFE0F Auction Empire", font=FONT_TITLE,
                  background=BG).pack(anchor="w")
        ttk.Label(wrap, text="A pass-the-device bidding game for you and your friends.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 22))

        form = ttk.Frame(wrap, style="App.TFrame")
        form.pack(fill="x")

        def row(r, label_text, widget):
            ttk.Label(form, text=label_text).grid(row=r, column=0, sticky="w", pady=7, padx=(0, 16))
            widget.grid(row=r, column=1, sticky="w", pady=7)

        row(0, "Number of players", ttk.Spinbox(form, from_=2, to=8, width=6,
                                                  textvariable=self.var_players))
        row(1, "Number of rounds", ttk.Spinbox(form, from_=3, to=30, width=6,
                                                textvariable=self.var_rounds))
        row(2, "Starting cash", ttk.Spinbox(form, from_=10, to=100000, increment=10,
                                             width=8, textvariable=self.var_cash))

        ttk.Label(form, text="Company vs. stock mix").grid(row=3, column=0, sticky="w", pady=7)
        ratio_row = ttk.Frame(form, style="App.TFrame")
        ratio_row.grid(row=3, column=1, sticky="w", pady=7)
        self.ratio_scale = ttk.Scale(ratio_row, from_=0, to=100, orient="horizontal",
                                      variable=self.var_ratio, length=200)
        self.ratio_scale.pack(side="left")
        self.ratio_value_lbl = ttk.Label(ratio_row, text="50% companies")
        self.ratio_value_lbl.pack(side="left", padx=10)

        row(4, "Jackpot companies", ttk.Spinbox(form, from_=0, to=3, width=6,
                                                 textvariable=self.var_jackpot))
        row(5, "Death stocks", ttk.Spinbox(form, from_=0, to=3, width=6,
                                            textvariable=self.var_death))

        self.preview_lbl = ttk.Label(wrap, text="", style="Muted.TLabel", wraplength=580,
                                      justify="left")
        self.preview_lbl.pack(anchor="w", pady=(16, 4))
        self._on_setting_change()

        btn_row = ttk.Frame(wrap, style="App.TFrame")
        btn_row.pack(fill="x", pady=(22, 0))
        ttk.Button(btn_row, text="How to Play", command=self._show_rules).pack(side="left")
        ttk.Button(btn_row, text="Next: Add Players \u2192", style="Accent.TButton",
                   command=self._build_names_screen).pack(side="right")

    def _on_setting_change(self, *args):
        # This callback is registered once for the app's lifetime, but the
        # labels it updates only exist while the setup screen is on screen -
        # bail out quietly if we've navigated away (or they're not built yet).
        if self.preview_lbl is None or not self.preview_lbl.winfo_exists():
            return
        if self.ratio_value_lbl is None or not self.ratio_value_lbl.winfo_exists():
            return
        try:
            rounds = self.var_rounds.get()
            ratio_pct = self.var_ratio.get()
            jackpot = self.var_jackpot.get()
            death = self.var_death.get()
        except (tk.TclError, ValueError):
            return
        self.ratio_value_lbl.config(text=f"{int(round(ratio_pct))}% companies")
        info = asset_preview(rounds, int(round(ratio_pct)), jackpot, death)
        text = (f"\u2192 {info['normal_companies']} companies + {info['jackpot']} jackpot company(ies)"
                f"   |   {info['normal_stocks']} stocks + {info['death']} death stock(s)")
        if info["total"] > info["rounds"]:
            text += (f"\n   ({info['total']} assets generated for {info['rounds']} rounds - "
                     f"some of the rarer ones may not come up)")
        self.preview_lbl.config(text=text)

    # ================================================================ #
    #  SCREEN 2 - player names
    # ================================================================ #
    def _build_names_screen(self):
        self._clear()
        n = self.var_players.get()
        wrap = ttk.Frame(self.container, style="App.TFrame", padding=30)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="Who's playing?", font=FONT_TITLE, background=BG).pack(anchor="w")
        ttk.Label(wrap, text="Everyone plays on this device - pass it around when it's their turn.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 20))

        grid = ttk.Frame(wrap, style="App.TFrame")
        grid.pack(fill="x")

        self.name_vars = []
        for i in range(n):
            v = tk.StringVar(value=f"Player {i + 1}")
            self.name_vars.append(v)
            ttk.Label(grid, text=f"Player {i + 1}:").grid(row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            ttk.Entry(grid, textvariable=v, width=24).grid(row=i, column=1, sticky="w", pady=5)

        btn_row = ttk.Frame(wrap, style="App.TFrame")
        btn_row.pack(fill="x", pady=(26, 0))
        ttk.Button(btn_row, text="\u2190 Back", command=self._build_setup_screen).pack(side="left")
        ttk.Button(btn_row, text="Start Game \u2192", style="Accent.TButton",
                   command=self._start_game).pack(side="right")

    def _start_game(self):
        names = [v.get().strip() or f"Player {i + 1}" for i, v in enumerate(self.name_vars)]
        if len(set(n.lower() for n in names)) != len(names):
            messagebox.showerror("Duplicate names", "Please give each player a different name.")
            return

        n = self.var_players.get()
        rounds = self.var_rounds.get()
        cash = self.var_cash.get()

        self.auctioneer = Auctioneer(rounds=rounds, init_cash=cash, players=n)
        for nm in names:
            self.auctioneer.make_account(name=nm)

        ratio = self.var_ratio.get() / 100
        self.assets = self.auctioneer.generate_normalised(
            company_ratio=ratio,
            jackpot_companies=self.var_jackpot.get(),
            death_stocks=self.var_death.get(),
        )

        self.current_round = 0
        self.log_lines = []
        self._build_game_screen()
        self._start_round()

    # ================================================================ #
    #  SCREEN 3 - main game (static layout, built once per game)
    # ================================================================ #
    def _build_game_screen(self):
        self._clear()

        header = ttk.Frame(self.container, style="App.TFrame", padding=(20, 14, 20, 4))
        header.pack(fill="x")
        self.round_label = ttk.Label(header, text="", style="H2.TLabel")
        self.round_label.pack(side="left")
        ttk.Button(header, text="How to Play", command=self._show_rules).pack(side="right")

        body = ttk.Frame(self.container, style="App.TFrame", padding=(20, 8, 20, 0))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="App.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        self.asset_frame = tk.Frame(left, bg=CARD_BG, highlightthickness=2)
        self.asset_frame.pack(fill="x", pady=(0, 12))

        self.turn_frame = ttk.Frame(left, style="Card.TFrame", padding=18)
        self.turn_frame.pack(fill="both", expand=True)

        right = ttk.Frame(body, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(right, text="Standings", style="H2.TLabel").pack(anchor="w", pady=(0, 6))

        cols = ("name", "cash", "company", "status")
        self.scoreboard = ttk.Treeview(right, columns=cols, show="headings", height=8)
        headers = {"name": "Player", "cash": "Cash", "company": "Company", "status": "This round"}
        for c in cols:
            self.scoreboard.heading(c, text=headers[c])
            self.scoreboard.column(c, width=95 if c != "name" else 110,
                                    anchor="w" if c == "name" else "center")
        self.scoreboard.pack(fill="both", expand=True)

        log_wrap = ttk.Frame(self.container, style="App.TFrame", padding=(20, 10, 20, 16))
        log_wrap.pack(fill="x")
        ttk.Label(log_wrap, text="Game Log", style="H2.TLabel").pack(anchor="w")
        log_inner = tk.Frame(log_wrap, bg=BG)
        log_inner.pack(fill="x", pady=(4, 0))
        self.log_text = tk.Text(log_inner, height=7, wrap="word", state="disabled",
                                 font=FONT_SMALL, bg=CARD_BG, relief="flat")
        sb = ttk.Scrollbar(log_inner, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.log_text.configure(state="normal")
        for line in self.log_lines:
            self.log_text.insert("end", line + "\n")
        self.log_text.configure(state="disabled")

    def _refresh_round_header(self):
        self.round_label.config(text=f"Round {self.current_round + 1} of {self.auctioneer.rounds}")

    def _refresh_status(self):
        """Keep the asset card's bid line and the standings table in sync.
        Call this any time the highest bid, winners, or fold state changes -
        the two panels must never show different bid states."""
        self._refresh_asset_card()
        self._refresh_scoreboard()

    def _refresh_scoreboard(self):
        for row in self.scoreboard.get_children():
            self.scoreboard.delete(row)
        leader_ids = set(self.auctioneer.highest_players_who_bid) if self.auctioneer.highest_bid > 0 else set()
        for pid, acc in self.auctioneer.accounts.items():
            if pid in leader_ids:
                status = "Leading"
            elif pid in self.out_bidders:
                status = "Folded"
            else:
                status = "Deciding"
            self.scoreboard.insert("", "end", values=(acc["name"], money(acc["cash"]),
                                                        money(acc["company"]), status))

    def _refresh_asset_card(self):
        for w in self.asset_frame.winfo_children():
            w.destroy()
        asset = self.assets[self.current_round]
        meta = ASSET_META[asset["type"]]
        self.asset_frame.configure(highlightbackground=meta["color"], highlightcolor=meta["color"])

        top = tk.Frame(self.asset_frame, bg=CARD_BG)
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text=meta["emoji"], font=FONT_BIG_EMOJI, bg=CARD_BG).pack(side="left")
        info = tk.Frame(top, bg=CARD_BG)
        info.pack(side="left", padx=12)
        tk.Label(info, text=meta["label"], font=FONT_H2, bg=CARD_BG, fg=meta["color"]).pack(anchor="w")
        if asset["type"] == "jc":
            earn_text = "Value hidden until someone wins and picks a slot"
        else:
            earn_text = f"Base value: {money(asset['earn'])}"
        tk.Label(info, text=earn_text, font=FONT_BODY, bg=CARD_BG, fg=MUTED).pack(anchor="w")

        tk.Label(self.asset_frame, text=meta["blurb"], font=FONT_SMALL, bg=CARD_BG, fg=MUTED,
                 wraplength=420, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        bid_line = tk.Frame(self.asset_frame, bg=CARD_BG)
        bid_line.pack(fill="x", padx=16, pady=(0, 14))
        if self.auctioneer.highest_bid > 0:
            names = " & ".join(self._name(p) for p in self.auctioneer.highest_players_who_bid)
            txt = f"Highest bid: {money(self.auctioneer.highest_bid)} - {names}"
        else:
            txt = "No bids yet"
        tk.Label(bid_line, text=txt, font=FONT_MONEY, bg=CARD_BG, fg="#111111").pack(anchor="w")

    # ================================================================ #
    #  Round lifecycle
    # ================================================================ #
    def _start_round(self):
        self.out_bidders = set()
        self.sweep_pos = 0
        self.pending_split = {"cost": 1.0, "asset": 1.0}
        self.auctioneer.highest_bid = 0
        self.auctioneer.highest_players_who_bid = []
        self.auctioneer.update_cash()

        self._refresh_round_header()
        self._refresh_status()

        asset = self.assets[self.current_round]
        meta = ASSET_META[asset["type"]]
        self._log(f"\n=== Round {self.current_round + 1}: {meta['emoji']} {meta['label']} up for auction ===")

        self._advance_turn()

    def _end_turn(self):
        self.sweep_pos += 1
        self._refresh_status()
        self._advance_turn()

    def _advance_turn(self):
        n = self.auctioneer.players
        while True:
            if self.sweep_pos >= n:
                if len(self.out_bidders) >= n - 1:
                    self._resolve_round()
                    return
                self.sweep_pos = 0
                continue
            pid = self.sweep_pos
            if pid in self.out_bidders:
                self.sweep_pos += 1
                continue
            break
        self._show_turn_choice(pid)

    def _clear_turn(self):
        for w in self.turn_frame.winfo_children():
            w.destroy()

    # ---------------------------------------------------------------- #
    #  A player's turn: bid / deal / fold
    # ---------------------------------------------------------------- #
    def _show_turn_choice(self, pid):
        self._clear_turn()
        cash = self.auctioneer.accounts[pid]["cash"]

        ttk.Label(self.turn_frame, text=f"{self._name(pid)}'s turn", style="CardH2.TLabel").pack(anchor="w")
        ttk.Label(self.turn_frame, text=f"Cash on hand: {money(cash)}",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(0, 16))

        btns = ttk.Frame(self.turn_frame, style="Card.TFrame")
        btns.pack(anchor="w")
        ttk.Button(btns, text="\U0001F4B0 Place Bid", style="Accent.TButton",
                   command=lambda: self._show_bid_entry([pid], 1.0, 1.0)).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="\U0001F91D Propose Deal",
                   command=lambda: self._show_deal_setup(pid)).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="\U0001F6AB Fold",
                   command=lambda: self._fold(pid)).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="\U0001F4B0 Send money",
                   command=lambda: self._send_money(pid)).pack(side="left", padx=(0, 8))

    def _fold(self, pid):
        self.out_bidders.add(pid)
        self._log(f"{self._name(pid)} folds.")
        self._end_turn()

    def _send_money(self, pid):
        self._clear_turn()  #  basically removes the action buttons currently
        ttk.Label(self.turn_frame, text=f"{self._name(pid)} is transferring money - ", style="CardH2.TLabel").pack(anchor="w")
        others = [p for p in self._active_ids() if p != pid]

        row1 = ttk.Frame(self.turn_frame, style="Card.TFrame")
        row1.pack(anchor="w", pady=4)
        row2 = ttk.Frame(self.turn_frame, style="Card.TFrame")
        row2.pack(anchor="w", pady=4)
        ttk.Label(row1, text="Send money to:", style="Card.TLabel").pack(side="left")
        combo = ttk.Combobox(row1, state="readonly", width=18,
                              values=[self._name(p) for p in others])  #  which player to send money
        combo.current(0)
        combo.pack(side="left", padx=8)


        ttk.Label(row2, text="Amount :", style="Card.TLabel").pack(side="left")
        amount_var = tk.StringVar()
        entry = ttk.Entry(row2, textvariable=amount_var, width=12)
        entry.pack(side="left", padx=8)

        btns = ttk.Frame(self.turn_frame, style="Card.TFrame")
        btns.pack(anchor="w", pady=(14, 0))

        error_lbl = ttk.Label(self.turn_frame, text="", style="Card.TLabel", foreground=BAD)
        error_lbl.pack(anchor="w", pady=(8, 0))

        ttk.Button(btns, text="Send", style="Accent.TButton", command=lambda: validate_and_send()).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Cancel",
                   command=lambda: self._show_turn_choice(pid)).pack(side="left")
        
        def validate_and_send():
            partner_name = combo.get()
            partner_id = next(p for p in others if self._name(p) == partner_name)  #  player who ur sending money

            raw = amount_var.get().strip() 
            accounts = self.auctioneer.accounts  #  accounts and it details
            current_person_money = accounts[pid]["cash"]
            try:
                amount = float(raw)  #  the amount of money to be sent
            except ValueError:
                error_lbl.config(text="Enter a number.")
                return
            if amount <= current_person_money and amount > 0:
                error_lbl.config(text="")
                #  sending money code here
                accounts[pid]["cash"] -= amount
                accounts[partner_id]["cash"] += amount
                self._refresh_scoreboard()
                self._show_turn_choice(pid)
                self._log(f"{accounts[pid]["name"]} sent $ {amount} to {accounts[partner_id]["name"]}")
            else:
                if amount <= current_person_money:
                    error_lbl.config(text="You don't have enough money to send")
                else:
                    error_lbl.config(text="Some error has occured while sending money")
                return
            
                


    def _show_bid_entry(self, player_ids, cost_split, asset_split, deal_note=None):
        self._clear_turn()
        names = " & ".join(self._name(p) for p in player_ids)
        ttk.Label(self.turn_frame, text=f"Bid - {names}", style="CardH2.TLabel").pack(anchor="w")
        if deal_note:
            ttk.Label(self.turn_frame, text=deal_note, style="CardMuted.TLabel",
                      wraplength=400, justify="left").pack(anchor="w", pady=(2, 8))

        ttk.Label(self.turn_frame, text=f"Current highest bid: {money(self.auctioneer.highest_bid)}",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(self.turn_frame, style="Card.TFrame")
        row.pack(anchor="w")
        ttk.Label(row, text="Your bid:", style="Card.TLabel").pack(side="left")
        amount_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=amount_var, width=12)
        entry.pack(side="left", padx=8)
        entry.focus_set()

        error_lbl = ttk.Label(self.turn_frame, text="", style="Card.TLabel", foreground=BAD)
        error_lbl.pack(anchor="w", pady=(8, 0))

        def confirm(event=None):
            raw = amount_var.get().strip()
            try:
                amount = float(raw)
            except ValueError:
                error_lbl.config(text="Enter a number.")
                return
            ok, err = self._validate_bid(player_ids, amount, cost_split)
            if not ok:
                error_lbl.config(text=err)
                return
            self.auctioneer.player_bid(player_ids, amount, cost_split)
            self.pending_split = {"cost": cost_split, "asset": asset_split}
            tag = names if len(player_ids) == 1 else f"{names} (team)"
            self._log(f"{tag} bid {money(amount)}.")
            self._end_turn()

        entry.bind("<Return>", confirm)

        btns = ttk.Frame(self.turn_frame, style="Card.TFrame")
        btns.pack(anchor="w", pady=(14, 0))
        ttk.Button(btns, text="Confirm Bid", style="Accent.TButton", command=confirm).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Cancel",
                   command=lambda: self._show_turn_choice(player_ids[0])).pack(side="left")

    def _validate_bid(self, player_ids, amount, cost_split):
        if amount <= 0:
            return False, "Bid must be greater than zero."
        if amount <= self.auctioneer.highest_bid:
            return False, f"Bid must be higher than the current highest bid of {money(self.auctioneer.highest_bid)}."
        accounts = self.auctioneer.accounts
        main_cash = accounts[player_ids[0]]["cash"]
        side_cash = accounts[player_ids[1]]["cash"] if len(player_ids) > 1 else 0
        if amount > main_cash + side_cash:
            return False, "That's more than your combined cash."
        main_cost = round(amount * cost_split, 3)
        side_cost = amount - main_cost
        if main_cost > main_cash or side_cost > side_cash:
            return False, "That split would leave one of you short - adjust the split or the bid."
        return True, ""

    # ---------------------------------------------------------------- #
    #  Deal proposal / response
    # ---------------------------------------------------------------- #
    def _show_deal_setup(self, pid):
        others = [p for p in self._active_ids() if p != pid]
        if not others:
            messagebox.showinfo("No one to deal with", "Everyone else has already folded this round.")
            return
        self._clear_turn()
        ttk.Label(self.turn_frame, text=f"{self._name(pid)} proposes a deal",
                  style="CardH2.TLabel").pack(anchor="w", pady=(0, 12))

        row1 = ttk.Frame(self.turn_frame, style="Card.TFrame")
        row1.pack(anchor="w", pady=4)
        ttk.Label(row1, text="Team up with:", style="Card.TLabel").pack(side="left")
        combo = ttk.Combobox(row1, state="readonly", width=18,
                              values=[self._name(p) for p in others])
        combo.current(0)
        combo.pack(side="left", padx=8)

        cost_var = tk.IntVar(value=50)
        asset_var = tk.IntVar(value=50)

        row2 = ttk.Frame(self.turn_frame, style="Card.TFrame")
        row2.pack(anchor="w", pady=8)
        ttk.Label(row2, text=f"{self._name(pid)}'s share of the cost:", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(row2, from_=0, to=100, textvariable=cost_var, width=5).pack(side="left", padx=8)
        ttk.Label(row2, text="%", style="Card.TLabel").pack(side="left")

        row3 = ttk.Frame(self.turn_frame, style="Card.TFrame")
        row3.pack(anchor="w", pady=8)
        ttk.Label(row3, text=f"{self._name(pid)}'s share of the winnings:", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(row3, from_=0, to=100, textvariable=asset_var, width=5).pack(side="left", padx=8)
        ttk.Label(row3, text="%", style="Card.TLabel").pack(side="left")

        def send():
            partner_name = combo.get()
            partner_id = next(p for p in others if self._name(p) == partner_name)
            self._show_deal_response(pid, partner_id, cost_var.get() / 100, asset_var.get() / 100)

        btns = ttk.Frame(self.turn_frame, style="Card.TFrame")
        btns.pack(anchor="w", pady=(16, 0))
        ttk.Button(btns, text="Send Deal", style="Accent.TButton", command=send).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=lambda: self._show_turn_choice(pid)).pack(side="left")

    def _show_deal_response(self, pid, partner_id, cost_split, asset_split):
        self._clear_turn()
        proposer = self._name(pid)
        partner = self._name(partner_id)
        ttk.Label(self.turn_frame, text=f"Pass the device to {partner}",
                  style="CardH2.TLabel").pack(anchor="w", pady=(0, 12))
        msg = (f"{proposer} wants to team up with you on this bid.\n\n"
               f"Cost split: {proposer} pays {int(cost_split * 100)}%, you pay {int((1 - cost_split) * 100)}%.\n"
               f"If you win: {proposer} gets {int(asset_split * 100)}%, you get "
               f"{int((1 - asset_split) * 100)}% of the asset.")
        ttk.Label(self.turn_frame, text=msg, style="Card.TLabel", wraplength=420,
                  justify="left").pack(anchor="w", pady=(0, 16))

        btns = ttk.Frame(self.turn_frame, style="Card.TFrame")
        btns.pack(anchor="w")
        ttk.Button(btns, text=f"\u2705 {partner} Accepts", style="Accent.TButton",
                   command=lambda: self._deal_accepted(pid, partner_id, cost_split, asset_split)
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text=f"\u274C {partner} Declines",
                   command=lambda: self._deal_declined(pid, partner)).pack(side="left")

    def _deal_accepted(self, pid, partner_id, cost_split, asset_split):
        self._log(f"{self._name(partner_id)} accepted a deal from {self._name(pid)} "
                  f"(cost {int(cost_split * 100)}/{int((1 - cost_split) * 100)}, "
                  f"winnings {int(asset_split * 100)}/{int((1 - asset_split) * 100)}).")
        note = f"Teamed up with {self._name(partner_id)}."
        self._show_bid_entry([pid, partner_id], cost_split, asset_split, deal_note=note)

    def _deal_declined(self, pid, partner_name):
        self._log(f"{partner_name} declined the deal.")
        self._show_turn_choice(pid)

    # ================================================================ #
    #  Round resolution
    # ================================================================ #
    def _resolve_round(self):
        self._clear_turn()
        self._refresh_status()
        asset = self.assets[self.current_round]

        if self.auctioneer.highest_bid <= 0:
            self._log("No one bid on this asset - it goes unclaimed.")
            ttk.Label(self.turn_frame, text="No bids were placed this round.",
                      style="CardH2.TLabel").pack(anchor="w", pady=(0, 10))
            ttk.Label(self.turn_frame, text="The asset goes unclaimed - nothing changes hands.",
                      style="Card.TLabel").pack(anchor="w", pady=(0, 16))
            ttk.Button(self.turn_frame, text="Continue \u2192", style="Accent.TButton",
                       command=self._next_round).pack(anchor="w")
            return

        winners = list(self.auctioneer.highest_players_who_bid)
        names = " & ".join(self._name(p) for p in winners)
        self._log(f"{names} won the bid at {money(self.auctioneer.highest_bid)}.")

        if asset["type"] == "company":
            self._finalize(asset, 0)
        elif asset["type"] in ("stock", "ds"):
            self._show_toss_ui(asset, winners, names)
        elif asset["type"] == "jc":
            self._show_jackpot_ui(asset, winners, names)

    def _show_toss_ui(self, asset, winners, names):
        self._clear_turn()
        if asset["type"] == "ds":
            ttk.Label(self.turn_frame, text=f"{names}, call the toss. \u26A0\uFE0F Losing wipes out everything!",
                      style="CardH2.TLabel", foreground=BAD, wraplength=420,
                      justify="left").pack(anchor="w", pady=(0, 16))
        else:
            ttk.Label(self.turn_frame, text=f"{names}, call the toss.",
                      style="CardH2.TLabel").pack(anchor="w", pady=(0, 16))
        btns = ttk.Frame(self.turn_frame, style="Card.TFrame")
        btns.pack(anchor="w")
        ttk.Button(btns, text="\U0001FA99 Call 0", style="Accent.TButton",
                   command=lambda: self._finalize(asset, 0)).pack(side="left", padx=(0, 10))
        ttk.Button(btns, text="\U0001FA99 Call 1", style="Accent.TButton",
                   command=lambda: self._finalize(asset, 1)).pack(side="left")

    def _show_jackpot_ui(self, asset, winners, names):
        self._clear_turn()
        ttk.Label(self.turn_frame, text=f"{names}, pick a mystery slot",
                  style="CardH2.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(self.turn_frame,
                  text="Five companies are bundled here - you won't know the value until you choose.",
                  style="CardMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(0, 16))
        btns = ttk.Frame(self.turn_frame, style="Card.TFrame")
        btns.pack(anchor="w")
        for i in range(5):
            ttk.Button(btns, text=f"\u2753 Slot {i + 1}",
                       command=lambda i=i: self._finalize(asset, i)).pack(side="left", padx=4)

    def _finalize(self, asset, choice):
        winners = list(self.auctioneer.highest_players_who_bid)
        asset_split = self.pending_split["asset"] if len(winners) > 1 else 1.0

        cash_before = {p: self.auctioneer.accounts[p]["cash"] for p in winners}
        company_before = {p: self.auctioneer.accounts[p]["company"] for p in winners}

        self.auctioneer.finalise_bid(asset=asset, integer_choice=choice, asset_split=asset_split)

        self._show_outcome(asset, choice, winners, cash_before, company_before)

    def _show_outcome(self, asset, choice, winners, cash_before, company_before):
        self._clear_turn()
        names = " & ".join(self._name(p) for p in winners)
        atype = asset["type"]
        team = len(winners) > 1

        if atype == "company":
            gained = sum(self.auctioneer.accounts[p]["company"] - company_before[p] for p in winners)
            ttk.Label(self.turn_frame,
                      text=f"\U0001F3E2 {names} added {money(gained)} in company value"
                           f"{' between them' if team else ''}!",
                      style="CardH2.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(0, 10))
            ttk.Label(self.turn_frame,
                      text="That value pays out again in full at the start of every round from here on.",
                      style="Card.TLabel", wraplength=400, justify="left").pack(anchor="w")
            self._log(f"{names} added {money(gained)} in company value.")

        elif atype in ("stock", "ds"):
            outcome = getattr(self.auctioneer, "last_toss_outcome", None)
            won = outcome == choice
            if won:
                gained = sum(self.auctioneer.accounts[p]["cash"] - cash_before[p] for p in winners)
                ttk.Label(self.turn_frame, text=f"\U0001F389 It landed on {outcome} - {names} called it right!",
                          style="CardH2.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(0, 10))
                ttk.Label(self.turn_frame,
                          text=f"{names} gained {money(gained)}{' between them' if team else ''} in cash.",
                          style="Card.TLabel", wraplength=400, justify="left").pack(anchor="w")
                self._log(f"{names} called {choice}, it landed on {outcome} - gained {money(gained)}.")
            else:
                ttk.Label(self.turn_frame, text=f"\U0001F4A5 It landed on {outcome} - {names} called {choice}.",
                          style="CardH2.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(0, 10))
                if atype == "ds":
                    ttk.Label(self.turn_frame,
                              text=f"Death stock! {names} lost everything - all cash and company value.",
                              style="Card.TLabel", foreground=BAD, wraplength=400,
                              justify="left").pack(anchor="w")
                    self._log(f"{names} called {choice}, it landed on {outcome} - wiped out.")
                else:
                    ttk.Label(self.turn_frame, text=f"{names} lose the bid amount.",
                              style="Card.TLabel").pack(anchor="w")
                    self._log(f"{names} called {choice}, it landed on {outcome} - lost the stock.")

        elif atype == "jc":
            values = asset["earn"]
            got = values[choice]
            reveal = ", ".join(
                (f"[{money(v)}]" if i == choice else money(v)) for i, v in enumerate(values)
            )
            gained = sum(self.auctioneer.accounts[p]["company"] - company_before[p] for p in winners)
            ttk.Label(self.turn_frame, text=f"\U0001F3B0 Slot {choice + 1} revealed: {money(got)}!",
                      style="CardH2.TLabel").pack(anchor="w", pady=(0, 8))
            ttk.Label(self.turn_frame, text=f"All five slots were: {reveal}",
                      style="CardMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(0, 8))
            ttk.Label(self.turn_frame,
                      text=f"{names} add {money(gained)} in company value{' between them' if team else ''}.",
                      style="Card.TLabel", wraplength=400, justify="left").pack(anchor="w")
            self._log(f"{names} opened slot {choice + 1} for {money(got)}.")

        self._refresh_scoreboard()
        ttk.Button(self.turn_frame, text="Continue \u2192", style="Accent.TButton",
                   command=self._next_round).pack(anchor="w", pady=(18, 0))

    def _next_round(self):
        self.current_round += 1
        if self.current_round >= self.auctioneer.rounds:
            self._build_end_screen()
        else:
            self._start_round()

    # ================================================================ #
    #  SCREEN 4 - end of game
    # ================================================================ #
    def _build_end_screen(self):
        self._clear()
        wrap = ttk.Frame(self.container, style="App.TFrame", padding=30)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="\U0001F3C1 Game Over", font=FONT_TITLE, background=BG).pack(anchor="w", pady=(0, 4))
        ttk.Label(wrap, text="Final score = cash + (company value \u00D7 number of rounds).",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 18))

        results = []
        for pid, acc in self.auctioneer.accounts.items():
            net = acc["cash"] + acc["company"] * self.auctioneer.rounds
            results.append((acc["name"], acc["cash"], acc["company"], net))
        results.sort(key=lambda r: r[3], reverse=True)

        cols = ("rank", "name", "cash", "company", "net")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", height=len(results))
        headers = {"rank": "#", "name": "Player", "cash": "Cash", "company": "Company", "net": "Final Score"}
        for c in cols:
            tree.heading(c, text=headers[c])
            tree.column(c, width=150 if c == "name" else 120,
                        anchor="w" if c == "name" else "center")
        medals = ["\U0001F947", "\U0001F948", "\U0001F949"]
        for i, (name, cash, company, net) in enumerate(results):
            rank = medals[i] if i < 3 else str(i + 1)
            tree.insert("", "end", values=(rank, name, money(cash), money(company), money(net)))
        tree.pack(fill="x", pady=(0, 20))

        ttk.Label(wrap, text=f"\U0001F451 {results[0][0]} wins the game!", font=FONT_H2,
                  background=BG, foreground=GOOD).pack(anchor="w")

        ttk.Button(wrap, text="Play Again", style="Accent.TButton",
                   command=self._restart).pack(anchor="w", pady=(24, 0))

    def _restart(self):
        self.auctioneer = None
        self.assets = []
        self.current_round = 0
        self.out_bidders = set()
        self.log_lines = []
        self._build_setup_screen()

    # ================================================================ #
    #  Rules dialog
    # ================================================================ #
    def _show_rules(self):
        win = tk.Toplevel(self)
        win.title("How to Play")
        win.configure(bg=CARD_BG)
        w, h = 480, 540
        x = self.winfo_rootx() + max(0, (self.winfo_width() - w) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.transient(self)
        txt = tk.Text(win, wrap="word", bg=CARD_BG, relief="flat", padx=18, pady=18, font=FONT_BODY)
        txt.pack(fill="both", expand=True)
        rules = (
            "Each round, one asset comes up for auction. Players take turns "
            "raising the bid, teaming up with someone else for a joint bid, "
            "or folding. A round ends once only one bidder is left standing "
            "- the last bid on the table wins.\n\n"
            "\U0001F3E2 Company - pays its full value out as cash again at the "
            "start of every later round. Buy early, collect often.\n\n"
            "\U0001F4C8 Stock - after winning, call 0 or 1 on a coin toss. Guess "
            "right and you gain the stock's value in cash. Guess wrong and "
            "you simply lose what you paid.\n\n"
            "\U0001F480 Death Stock - the same coin toss as a Stock, but "
            "guessing wrong wipes out every bit of your cash and company "
            "value.\n\n"
            "\U0001F3B0 Jackpot Company - five companies bundled together. "
            "You pick one of five mystery slots blind and keep whatever "
            "it's worth.\n\n"
            "\U0001F91D Deals - on your turn you can invite another player to "
            "bid with you, splitting both the cost and the eventual "
            "winnings by whatever percentages you agree on.\n\n"
            "\U0001F3C6 Scoring - your final score is your cash plus your "
            "company value multiplied by the number of rounds, so holding "
            "companies pays off the longer the game runs."
        )
        txt.insert("1.0", rules)
        txt.configure(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)


if __name__ == "__main__":
    app = AuctionApp()
    app.mainloop()
