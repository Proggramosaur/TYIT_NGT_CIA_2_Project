class Player:
    def __init__(self, player_id, player_name, player_level, score):
        self.player_id = player_id
        self.player_name = player_name
        self.player_level = player_level
        self.score = score

    def display(self):
        print("\n----- Player Details -----")
        print("Player ID:", self.player_id)
        print("Player Name:", self.player_name)
        print("Player Level:", self.player_level)
        print("Score:", self.score)