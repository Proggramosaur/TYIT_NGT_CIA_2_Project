from player import Player

players = []

while True:
    print("\n===== PLAYER LEADERBOARD =====")
    print("1. Add Player")
    print("2. Read Player")
    print("3. Update Player")
    print("4. Delete Player")
    print("5. View Leaderboard")
    print("6. Exit")

    choice = input("Enter your choice: ")

    # Add Player
    if choice == "1":
        player_id = int(input("Enter Player ID: "))
        player_name = input("Enter Player Name: ")
        player_level = int(input("Enter Player Level: "))
        score = int(input("Enter Score: "))

        player = Player(player_id, player_name, player_level, score)
        players.append(player)

        print("\nPlayer added successfully!")

    # Read Player
    elif choice == "2":
        player_id = int(input("Enter Player ID: "))

        found = False

        for player in players:
            if player.player_id == player_id:
                player.display()
                found = True
                break

        if not found:
            print("\nPlayer not found.")

    # Update Player
    elif choice == "3":
        player_id = int(input("Enter Player ID to update: "))

        found = False

        for player in players:
            if player.player_id == player_id:
                player.player_name = input("Enter new Player Name: ")
                player.player_level = int(input("Enter new Player Level: "))
                player.score = int(input("Enter new Score: "))

                print("\nPlayer updated successfully!")
                found = True
                break

        if not found:
            print("\nPlayer not found.")

    # Delete Player
    elif choice == "4":
        player_id = int(input("Enter Player ID to delete: "))

        found = False

        for player in players:
            if player.player_id == player_id:
                players.remove(player)
                print("\nPlayer deleted successfully!")
                found = True
                break

        if not found:
            print("\nPlayer not found.")

    # View Leaderboard
    elif choice == "5":
        print("\n===== PLAYER LEADERBOARD =====")

        if len(players) == 0:
            print("No players available.")

        else:
            # Sort by score - highest first
            sorted_players = sorted(
                players,
                key=lambda player: player.score,
                reverse=True
            )

            for rank, player in enumerate(sorted_players, start=1):
                print(
                    f"{rank}. "
                    f"ID: {player.player_id} | "
                    f"Name: {player.player_name} | "
                    f"Level: {player.player_level} | "
                    f"Score: {player.score}"
                )

    # Exit
    elif choice == "6":
        print("\nExiting...")
        break

    # Invalid Choice
    else:
        print("\nInvalid choice. Please try again.")