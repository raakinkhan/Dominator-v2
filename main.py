#  This is the game which i designed and i used to play in school and college days with my friends group
#
#  NOTE FOR THE GUI VERSION (gui.py):
#  This file is your original engine, unchanged except for two small, clearly
#  marked spots (search "GUI FIX") so the point-and-click version can drive it
#  correctly:
#    1) finalise_bid() checked for a stray "dc" instead of "ds" when splitting
#       a death-stock payout between two teamed-up players - fixed to "ds" so
#       team death-stock winners actually get their share calculated.
#    2) finalise_bid() now stores the coin-toss outcome on self.last_toss_outcome
#       so a caller (the GUI) can truthfully report "it landed on 0/1" instead
#       of guessing from before/after balances.
#  Nothing about how the game plays was changed.

import math
import random


class Auctioneer:
    """
    Manages a multi-round auction game where players bid on companies and stocks.

    The game generates a normalised list of assets (companies and stocks) based
    on the number of rounds and initial cash. Players compete by bidding individually
    or in pairs. The highest bid at the end of each round wins the asset.

    Attributes:
        rounds (int): Total number of auction rounds.
        init_cash (float): Starting cash balance for every player.
        players (int): Maximum number of players allowed.
        player_id (int): Auto-incrementing ID counter for new accounts.
        highest_bid (float): The current highest bid in the active round.
        highest_players_who_bid (list[int]): Player IDs who placed the current highest bid.
        accounts (dict): Maps player_id -> account dict with keys id, name, cash, company.
    """

    # ------------------------------------------------------------------ #
    #  Construction                                                        #
    # ------------------------------------------------------------------ #

    def __init__(self, rounds: int, init_cash: float, players: int):
        """
        Initialise the Auctioneer.

        Args:
            rounds (int): Total number of auction rounds to run.
            init_cash (float): Cash given to every player at the start.
            players (int): Maximum number of players allowed in the game.
        """
        self.rounds = rounds
        self.init_cash = init_cash
        self.players = players

        self.player_id = 0
        self.highest_bid = 0
        self.highest_players_who_bid = [0]
        self.accounts = {}

        # Populated by player_bid(); consumed and cleared by finalise_bid()
        self.asset_split_list = []
        self.money_left_list = []

        # GUI FIX (2): last coin-toss result, so callers can report it accurately.
        self.last_toss_outcome = None

    # ------------------------------------------------------------------ #
    #  Account management                                                  #
    # ------------------------------------------------------------------ #

    def make_account(self, name: str) -> None:
        """
        Register a new player and create their account.

        Each account records the player's unique ID, display name, remaining
        cash, and cumulative company value owned.  Account creation is blocked
        once the player cap (self.rounds) is reached.

        Args:
            name (str): Display name for the new player.
        """
        if self.player_id <= self.players-1:
            account_info = {
                "id": self.player_id,
                "name": name,
                "cash": self.init_cash,
                "company": 0,   # total company value owned, starts at zero
            }
            self.accounts[self.player_id] = account_info
            self.player_id += 1
        else:
            print(f"max player limit reached: {self.players}")

    # ------------------------------------------------------------------ #
    #  Asset generation                                                    #
    # ------------------------------------------------------------------ #

    def generate_normalised(self, company_ratio: float = 0.7, death_stocks: int = 1, jackpot_companies: int = 1) -> list[dict]:
        """
        Generate a randomised, normalised list of assets for the auction.

        Asset mix is split into companies (default 70 %) and stocks (30 %).
        Values are normalised using multipliers derived from real auctioneer
        experience so that the game stays balanced regardless of round count.

        Args:
            company_ratio (float): Fraction of rounds that produce company
                assets. Must be in (0, 1). Defaults to 0.7.

            death_stocks (int): how much amount of death stocks to produce,
                it must be less than number of normal stocks present

            jackpot_companies (int): how much amount of jackpot companies to produce,
                it must be less than number of normal companies present

        Returns:
            list[dict]: Shuffled list of length ``self.rounds``, each element
                being ``{"type": "company"|"stock"|"death_stock"|"jackpot_companies", "earn": float}``.
        """
        self.equiliser = self.init_cash / 20  #  20 billion was the iniitial cash we used to start with in college

        def generate_normal_company() -> float:
            """
            Return a normalised company earn value.

            Base value = (1/10) * rounds — calibrated through years of running
            the auction in college.  A random multiplier then adds variety
            without breaking balance.
            """
            MULTIPLIER = [0.7, 0.5, 1, 1, 2, 1.5]
            base_value = (1 / 10) * self.rounds
            return round(random.Random().choice(MULTIPLIER) * base_value * self.equiliser, 3)

        def generate_jackpot_company() -> list:
            """
            Return a normalised jack pot company earn value.

            explanation - this is basically numerous companies packed into a list, the player (with no info about the company earnings)
                          will try to choose a random company...

            Base value = (1/10) * rounds — calibrated through years of running
            the auction in college.  A random multiplier then adds variety
            without breaking balance.
            """
            MULTIPLIER = [0.5, 0.5, 0.5, 1, 1, 1, 1, 1, 1, 1.5, 1.5, 2]
            base_value = (1 / 10) * self.rounds
            jack_asset_companies = []
            for _ in range(5):
                jack_asset_companies.append(round(random.Random().choice(MULTIPLIER) * base_value * self.equiliser, 3))

            return jack_asset_companies


        def generate_normal_stock() -> float:
            """
            Return a normalised stock earn value.

            Base value = (1/3) * rounds — derived from the original game
            convention of awarding 5 billion in stock across 15 rounds.
            """
            MULTIPLIER = [1, 1, 1.3, 1.5]
            base_value = (1 / 3) * self.rounds
            return round(random.Random().choice(MULTIPLIER) * base_value * self.equiliser, 3)

        def generate_death_stock() -> float:
            """
            Return a Death stock earn value.

            Base value = (4/5) * rounds — derived from the original game
            convention of awarding 12 billion in death stock across 15 rounds.
            """
            MULTIPLIER = [1, 1, 1, 0.8, 1.5]
            base_value = (4 / 5) * self.rounds
            return round(random.Random().choice(MULTIPLIER) * base_value * self.equiliser, 3)


        # Determine how many of each asset type to generate
        company_freq = math.floor(company_ratio * self.rounds)
        # print(company_freq)
        stock_freq = self.rounds - company_freq
        # print(stock_freq)
        if company_freq >= 1:
            company_freq -= jackpot_companies

        if stock_freq >= 1:
            stock_freq -= death_stocks



        print(f"number of companies: {company_freq}")
        print(f"number of jackpot companies:    {jackpot_companies}")
        print(f"number of stocks:    {stock_freq}")
        print(f"number of death stocks:    {death_stocks}")

        # Build the base asset pool
        asset_pool = []
        for _ in range(company_freq):
            asset_pool.append({"type": "company", "earn": generate_normal_company()})


        for _ in range(jackpot_companies):
            asset_pool.append({"type": "jc", "earn": generate_jackpot_company()})  # jackpot company is a list

        for _ in range(stock_freq):
            asset_pool.append({"type": "stock", "earn": generate_normal_stock()})

        random.shuffle(asset_pool)  #  added this, has solved crucial problem in game mechanics
        for _ in range(death_stocks):
            asset_pool.append({"type": "ds", "earn": generate_death_stock()})

        # Randomly sample from the pool to produce the final round list
        # (allows repeats, giving natural variation per round)
        return asset_pool

    # ------------------------------------------------------------------ #
    #  Bidding                                                             #
    # ------------------------------------------------------------------ #

    def player_bid(
        self,
        player_id_list: list[int],
        player_bid: float,
        cash_players_split: float,
    ) -> None:
        """
        Submit a bid for the current auction round.

        One or two players may bid together and split both the cost and the
        earned asset proportionally via ``players_split``.

        If the bid exceeds any player's available cash the bid is rejected.

        Note:
            ``players_split`` is the main player's share (index 0).  If the
            side player lacks sufficient funds the split is not adjusted here —
            dynamic re-splitting is a planned future feature.

        Args:
            player_id_list (list[int]): IDs of players placing this bid.
                First entry is the *main* player; second (optional) is the
                *side* player.
            player_bid (float): Total bid amount (combined across both players).
            cash_players_split (float): Fraction of cost assigned to the main
                player (0–1).  Side player receives the remainder.
            asset (dict): The asset currently on auction
                (``{"type": str, "earn": float}``).
        """
        # Track the highest bid so far; only the leading bid goes to finalise
        if player_bid > self.highest_bid:

            # Calculate combined cash ceiling to validate the bid
            net_cash = sum(self.accounts[pid]["cash"] for pid in player_id_list)

            # Safely unpack cash for one or two players
            try:
                main_player_cash = self.accounts[player_id_list[0]]["cash"]
                side_player_cash = self.accounts[player_id_list[1]]["cash"]
            except IndexError:
                # Single-player bid — side player contributes nothing
                main_player_cash = self.accounts[player_id_list[0]]["cash"]
                side_player_cash = 0

            if player_bid > net_cash:
                print("players don't have that much money...")
                return

            # print(asset)



            # Split the bid cost between players
            main_cost = round(player_bid * cash_players_split, 3)
            side_cost = player_bid - main_cost

            if side_cost > side_player_cash or main_cost > main_player_cash:
                print("The split causes bankruptcy, so no split possible")
                return


            self.money_left_list = [
                main_player_cash - main_cost,
                side_player_cash - side_cost,
            ]

            # print(f"asset split between players:  {self.asset_split_list}")
            # print(f"cash remaining after bid:     {self.money_left_list}")

            self.highest_bid = player_bid
            self.highest_players_who_bid = player_id_list

    # ------------------------------------------------------------------ #
    #  Finalising a round                                                  #
    # ------------------------------------------------------------------ #

    def finalise_bid(self, asset: dict, integer_choice: int = 0, asset_split: float = 1) -> None:
        """
        Award the asset to the winning bidders and reset round state.

        For **company** assets the earn value is added directly to each
        winner's ``company`` balance and cash is deducted.

        For **stock** assets a coin-toss mechanic is used:
        - The winning player calls either 0 or 1 via ``choose_if_stock``.
        - A random outcome is drawn.
        - On a match the player *gains* their share of the stock earn value.
        - On a miss the player *loses* their bid cost instead.

        After awarding, the round's highest-bid state is cleared so the next
        round starts fresh.

        Args:
            asset (dict): The asset that was auctioned
                (``{"type": str, "earn": float}``).
            integer_choice (int): The player's guess for the stock toss —
                either ``0`` or ``1``. Ignored for company assets.
                additional for jackpot company the choice is between 0-4 or ~ in future 0-n ~
            asset_split (float): the players split the asset based on their whim, but if 1, every thing goes to main 1st player
        """
        winners = self.highest_players_who_bid
        # print(f"asset type: {asset['type']}")


        # Split the asset earn value between players
        if asset["type"] in ["company", "stock", "ds"]:  # GUI FIX (1): was "dc" (typo) -> "ds"
            main_asset_share = round(asset["earn"] * asset_split, 3)
            side_asset_share = asset["earn"] - main_asset_share
            self.asset_split_list = [main_asset_share, side_asset_share]
        elif asset["type"] == "jc":
            main_asset_share = round(asset["earn"][integer_choice] * asset_split, 3)  #  as jc is a list, there must be choice given b/w 0-4
            side_asset_share = asset["earn"][integer_choice] - main_asset_share
            self.asset_split_list = [main_asset_share, side_asset_share]

        outcome = random.choice([0, 1])
        self.last_toss_outcome = outcome  # GUI FIX (2): expose it for callers to report truthfully
        for idx, player_id in enumerate(winners):
            if asset["type"] in ["company","jc"]:
                # Deduct bid cost and credit company value
                self.accounts[player_id]["cash"] = self.money_left_list[idx]
                self.accounts[player_id]["company"] += self.asset_split_list[idx]

            elif asset["type"] in ["stock", "ds"]:
                # Stock: outcome decided by a fair coin toss

                if integer_choice == outcome:
                    # Correct guess — player gains the stock earn value
                    self.accounts[player_id]["cash"] += self.asset_split_list[idx]
                    print("you won the stock!")
                else:
                    # Wrong guess — player loses their bid cost
                    if asset["type"] == "stock":
                        self.accounts[player_id]["cash"] = self.money_left_list[idx]
                        print("you lost the stock.")
                    elif asset["type"] == "ds":
                        self.accounts[player_id]["cash"] = 0
                        self.accounts[player_id]["company"] = 0
                        print("you lost the death stock. and got bankrupt")

        # Reset round state for the next auction
        self.highest_players_who_bid = [0]
        self.highest_bid = 0

    def update_cash(self):
        for player in self.accounts:
            self.accounts[player]["cash"] += self.accounts[player]["company"]



# ------------------------------------------------------------------ #
#  Demo / smoke-test                                                   #
# ------------------------------------------------------------------ #

# a = Auctioneer(rounds=3, init_cash=10, players=5)
# a.generate_normalised(company_ratio=0.5)
#
# a.make_account(name="raakin")
# a.make_account(name="khan")
# a.make_account(name="cha")
# a.make_account(name="chi")
# a.make_account(name="gota")
#
# assets = a.generate_normalised(company_ratio=0, jackpot_companies=0, death_stocks=3)
# print(a.accounts)
#
# # Round 1 — three bids on the same asset; highest (7) wins
# a.player_bid(player_id_list=[0,1], player_bid=15, cash_players_split=0.5)
# print(a.money_left_list)
# print(a.highest_bid)
# print(a.highest_players_who_bid)
# print()
# print()
# print()
# print(assets)
# a.finalise_bid(asset=assets[0], integer_choice=0, asset_split=0.1)
# print(a.accounts)
# print(a.asset_split_list)



# print(a.highest_players_who_bid)
# a.player_bid(player_id_list=[2, 3], players_split=0.7, asset=assets[0], player_bid=5)
# a.player_bid(player_id_list=[0],    players_split=1,   asset=assets[0], player_bid=7)
# a.finalise_bid(asset=assets[0], choose_if_stock=1)
# print(a.highest_players_who_bid)
# print(a.accounts)
#
# print("===================")
# print("bid over , 2nd bid")
# print("===================")
# a.player_bid(player_id_list=[0],    players_split=1,   asset=assets[1], player_bid=4)
# print(a.highest_players_who_bid)
# a.player_bid(player_id_list=[2, 3], players_split=0.7, asset=assets[1], player_bid=5)
# a.player_bid(player_id_list=[1],    players_split=1,   asset=assets[1], player_bid=7)
# a.finalise_bid(asset=assets[1], choose_if_stock=1)
# print(a.highest_players_who_bid)
# print(a.accounts)
