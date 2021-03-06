import discord
from discord.ext import commands

import core.poker as poker
import core.cardgame as cardgame
import core.hand_parser as hand_parser_module


async def play_game(
        ctx:commands.context, client:commands.Bot,
        list_of_users:dict, is_first_table:bool = True):
    async def flow():
        create_game() if is_first_table else game.start_game(deck)
        await bet_round(3)
        await bet_round(1)
        await bet_round(1)
        await bet_round(0)
        await hand_parser()
        await chip_redistribution_from_pot()
        await play_game(ctx, client, list_of_users, False)

    async def wait_for_response(message, name, func = False):
        await ctx.send(message)
        while True:
            response = await client.wait_for("message")
            author = response.author.name
            content = response.content
            if author == name:
                if not func:
                    return content
                else:
                    if func(content):
                        return content

    def create_game():
        def create_game_main_flow():
            get_list_of_players()
            get_game()
            get_options()

        def get_list_of_players():
            global list_of_players
            list_of_players = [poker.Poker_Player(user, 2000, channel) 
                               for user, channel in list_of_users.items()]

        def get_game():
            global game
            game = poker.Poker_Game(list_of_players)

            global deck
            deck = cardgame.Deck()

            global separator
            separator = 30 * "-"

        def get_options():
            async def call(need_to_bet):
                game.bet(need_to_bet)
                return False

            async def raise_bet(need_to_bet):
                __ = game.turn
                player = game.players[game.players_in_game[__]]

                message = "How much do you want to raise?"
                name = player.name
                is_int = lambda s: s.isdigit()
                raise_value = int(await wait_for_response(message, name, is_int))

                game.bet(need_to_bet + raise_value)
                game.last_to_raise = game.players_in_game[__]
                
                return False

            async def pass_turn(need_to_bet):
                if game.players_in_game[game.turn] == game.last_to_raise:
                    game.pass_without_betting()
                    return True
                game.pass_without_betting()
                return False

            async def fold(need_to_bet):
                game.fold(deck)
                return True

            global options
            options = {
                "c": call,
                "r": raise_bet,
                "p": pass_turn,
                "f": fold
            }

        create_game_main_flow()

    async def bet_round(cards_to_table:int):        
        async def bet_round_main_flow():
            await settings()
            await bets()
            await show_table()

        async def settings():
            if cards_to_table == 3:
                await ctx.send(separator)
                await ctx.send(f"Big blind: {game.players[game.big_blind].name}\n"
                               f"Small blind: {game.players[game.small_blind].name}\n"
                               f"{separator}")
                game.bet(game.actual_blind/2, game.small_blind)
                game.bet(game.actual_blind, game.big_blind)
                deck.shuffle()

                for player in game.players.values():
                    player.withdraw_card(deck)
                    player.withdraw_card(deck)

                    await player.channel.send(separator)
                    await player.channel.send(f"You have the amount of {player.money} chips")

                    for card in player.hand:
                        reactions = {
                            "spades":"♠️",
                            "clubs":"♣️",
                            "hearts":"♥️",
                            "diamonds":"♦️"
                        }

                        msg = await player.channel.send(f"==={card.return_rank_simbol()}===")
                        await msg.add_reaction(reactions[card.suit.lower()])
                       
            game.last_to_raise = game.big_blind


        async def bets():
            game.flag = True if len(game.players_in_game) == 1 else False
            while not game.flag:
                __ = game.turn
                player = game.players[__]
                need_to_bet = game.actual_bet - player.actual_bet
                if not player.all_in:
                    if need_to_bet != 0:
                        message = (f"{player.name} needs to bet {need_to_bet}\n"
                                   "Do you want to call, raise or fold?\n"
                                   "[c] call\n[r] raise\n[f] fold")
                        name = player.name                        
                        is_valid = lambda s: s.lower() in ["c", "r", "f"]
                        response = await wait_for_response(message, name, is_valid)

                        await options[response.lower()](need_to_bet)
                    else:
                        message = (f"{player.name} don't need to bet\n"
                                   "Do you want to pass, raise or fold?\n"
                                   "[p] pass\n[r] raise\n[f] fold")
                        name = player.name
                        is_valid = lambda s: s.lower() in ["p", "r", "f"]
                        response = await wait_for_response(message, name, is_valid)

                        value = await options[response.lower()](need_to_bet)
                        game.flag = value
            await ctx.send(separator)

        async def show_table():
            flag = True if (len(game.players_in_game) > 1) or (cards_to_table == 0) else False
            
            for __ in range(cards_to_table):
                game.withdraw_to_table(deck)

            if flag:
                for card in game.table:
                    reactions = {
                        "spades":"♠️",
                        "clubs":"♣️",
                        "hearts":"♥️",
                        "diamonds":"♦️"
                    }

                    msg = await ctx.send(f"==={card.return_rank_simbol()}===")
                    await msg.add_reaction(reactions[card.suit.lower()])

                await ctx.send(separator)

        await bet_round_main_flow()

    async def hand_parser():
        table = game.table
        hands = [] 
        for p in game.players_in_game:
            hands.append(game.players[p].hand)

        points = hand_parser_module.greater_hand(table, hands)
        points_sorted = sorted(points, reverse=True)

        global list_of_winners
        list_of_winners = [points.index(score) for score in points_sorted]

        winner_points = max(points)
        winner_index = points.index(winner_points)
        await ctx.send(f"{game.players[game.players_in_game[winner_index]].name} won the round!")

    async def chip_redistribution_from_pot():
        for player_index in list_of_winners:
            player = game.players[game.players_in_game[player_index]]
            if not player.all_in:
                for i, pot in enumerate(game.pot):
                    player.money += pot[0]
                    game.pot[i][0] = 0
                break
            else:
                for i, pot in enumerate(game.pot):
                    if player.id in pot[1]:
                        player.money += pot[0]
                        game.pot[i][0] = 0

    await flow()