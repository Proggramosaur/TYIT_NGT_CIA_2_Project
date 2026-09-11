import time

from player import Player
import MySQL_Handler
import Redis_Handler
import Benchmark


print("Initialising MySQL Database...")
MySQL_Handler.initialiseDB()

print("Initialising Redis Cache...")
Redis_Handler.initialiseCache()

print()

players = []       # in-memory list stays in sync with DB


while True:
    print("\n===== PLAYER LEADERBOARD =====")
    print("1. Add Player")
    print("2. Read Player")
    print("3. Update Player")
    print("4. Delete Player")
    print("5. View Leaderboard")
    print("6. Get Player Rank")
    print("7. Get Top 10 Players")
    print("8. Run Benchmark")
    print("9. Exit")
    print("10. Clear Redis Cache")

    choice = input("Enter your choice: ")

    # Write-through: MySQL first, then Redis.
    # If MySQL fails, addPlayer raises and we skip the cache write entirely.
    
    if choice == "1":
        player_name  = input("Enter Player Name: ")
        player_level = int(input("Enter Player Level: "))
        score        = int(input("Enter Score: "))

        player = Player(None, player_name, player_level, score)

        try:
            t0 = time.perf_counter()
            MySQL_Handler.addPlayer(player)
            Benchmark.log_operation('ADD', 'MySQL', (time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            Redis_Handler.cachePlayer(player)
            Benchmark.log_operation('ADD', 'Redis', (time.perf_counter() - t0) * 1000)

            players.append(player)
            print(f"\n  Player added successfully! (Assigned ID: {player.player_id})")
        except Exception:
            print("\n  Failed to add player. MySQL error — player not saved.")

    # Cache-aside: Redis first, MySQL on miss, repopulate cache after miss.
    elif choice == "2":
        player_name = input("Enter Player Name: ")

        t0  = time.perf_counter()
        row = Redis_Handler.getCachedPlayer(player_name)
        lat = (time.perf_counter() - t0) * 1000

        if row is None:
            Benchmark.log_operation('READ', 'Redis', lat)   
            print("Cache MISS, Querying the DB")
            t0  = time.perf_counter()
            row = MySQL_Handler.getPlayer(player_name)
            lat = (time.perf_counter() - t0) * 1000
            if row:
                temp = Player(*row)
                Redis_Handler.repopulatePlayer(temp)
            Benchmark.log_operation('READ', 'MySQL', lat)
        else:
            Benchmark.log_operation('READ', 'Redis', lat)

        if row:
            pid, name, level, score = row
            print(f"\n  ID: {pid} | Name: {name} | Level: {level} | Score: {score}")
        else:
            print("\n  Player not found.")
    # Write-through: MySQL first, then refresh Redis.
    # We keep old_name before mutation so the stale name key can be evicted.
    elif choice == "3":
        player_id = int(input("Enter Player ID to update: "))

        found = False
        for player in players:
            if player.player_id == player_id:
                old_name            = player.player_name   # snapshot before mutation
                player.player_name  = input("Enter new Player Name: ")
                player.player_level = int(input("Enter new Player Level: "))
                player.score        = int(input("Enter new Score: "))

                try:
                    t0 = time.perf_counter()
                    updated = MySQL_Handler.updatePlayer(player)
                    Benchmark.log_operation('UPDATE', 'MySQL', (time.perf_counter() - t0) * 1000)

                    if updated:
                        t0 = time.perf_counter()
                        Redis_Handler.refreshCachedPlayer(player, old_name)
                        Benchmark.log_operation('UPDATE', 'Redis', (time.perf_counter() - t0) * 1000)
                        print("\n  Player updated successfully!")
                    else:
                        print("\n  Player not found in database.")
                except Exception:
                    print("\n  Failed to update player.")

                found = True
                break

        if not found:
            print("\nPlayer not found in current session.")

    # Write-through: MySQL first, then evict from Redis.
    elif choice == "4":
        player_id = int(input("Enter Player ID to delete: "))

        found = False
        for player in players:
            if player.player_id == player_id:
                try:
                    t0 = time.perf_counter()
                    deleted = MySQL_Handler.deletePlayer(player_id)
                    Benchmark.log_operation('DELETE', 'MySQL', (time.perf_counter() - t0) * 1000)

                    if deleted:
                        t0 = time.perf_counter()
                        Redis_Handler.evictPlayer(player_id, player.player_name)
                        Benchmark.log_operation('DELETE', 'Redis', (time.perf_counter() - t0) * 1000)
                        players.remove(player)
                        print("\n  Player deleted successfully!")
                    else:
                        print("\n  Player not found in database.")
                except Exception:
                    print("\n  Failed to delete player.")

                found = True
                break

        if not found:
            print("\n  Player not found in current session.")
    
    # Cache-aside: Redis sorted set first, MySQL on miss, repopulate after miss.
    elif choice == "5":
        print("\n===== PLAYER LEADERBOARD =====")

        t0   = time.perf_counter()
        rows = Redis_Handler.getCachedLeaderboard()
        lat  = (time.perf_counter() - t0) * 1000

        if rows is None:
            Benchmark.log_operation('LEADERBOARD', 'Redis', lat)
            print("Cache MISS, Querying the DB")
            t0   = time.perf_counter()
            rows = MySQL_Handler.getLeaderboard()
            lat  = (time.perf_counter() - t0) * 1000
            if rows:
                Redis_Handler.repopulateLeaderboard(rows, Player)
            Benchmark.log_operation('LEADERBOARD', 'MySQL', lat)
        else:
            Benchmark.log_operation('LEADERBOARD', 'Redis', lat)

        if not rows:
            print("  No players available.")
        else:
            for rank, (pid, name, level, score) in enumerate(rows, start=1):
                print(f"  {rank}. ID: {pid} | Name: {name} | Level: {level} | Score: {score}")
        
    # Cache-aside: ZREVRANK from Redis sorted set, COUNT subquery on miss.
    elif choice == "6":
        player_name = input("Enter Player Name: ")

        t0   = time.perf_counter()
        rank = Redis_Handler.getCachedPlayerRank(player_name)
        lat  = (time.perf_counter() - t0) * 1000

        if rank is None:
            Benchmark.log_operation('GET RANK', 'Redis', lat)
            print("Cache MISS, Querying the DB")
            t0   = time.perf_counter()
            rank = MySQL_Handler.getPlayerRank(player_name)
            lat  = (time.perf_counter() - t0) * 1000
            Benchmark.log_operation('GET RANK', 'MySQL', lat)

        else:
            Benchmark.log_operation('GET RANK', 'Redis', lat)

        if rank is not None:
            print(f"\n  '{player_name}' is ranked #{rank}")
        else:
            print("\n  Player not found.")
    # Cache-aside: ZREVRANGE from Redis, LIMIT query on miss.
    elif choice == "7":

        n = int(input("Enter N: "))

        t0   = time.perf_counter()
        rows = Redis_Handler.getCachedTopN(n)
        lat  = (time.perf_counter() - t0) * 1000

        if rows is None:
            Benchmark.log_operation(f'TOP {n}', 'Redis', lat)
            t0   = time.perf_counter()
            rows = MySQL_Handler.getTopN(n)
            lat  = (time.perf_counter() - t0) * 1000
            if rows:
                Redis_Handler.repopulateLeaderboard(rows, Player)
            Benchmark.log_operation(f'TOP {n}', 'MySQL', lat)
            
        else:
            Benchmark.log_operation(f'TOP {n}', 'Redis', lat)

        if not rows:
            print("\n  No players available.")
        else:
            print(f"\n===== TOP {n} PLAYERS =====")
            for rank, (pid, name, level, score) in enumerate(rows, start=1):
                print(f"  {rank}. ID: {pid} | Name: {name} | Level: {level} | Score: {score}")

    elif choice == "8":
        print("\n--- Benchmark Mode ---")
        print("1. Full Benchmark (all operations)")
        print("2. Read only")
        print("3. Rank only")
        print("4. Top 10 only")
        print("5. Leaderboard only")

        b_choice = input("Select Benchmark: ")
        runs = int(input("Number of runs per operation: "))

        if b_choice in ("1", "2", "3"):
            bname = input("Enter a player name to use for read/rank tests: ")

        if b_choice == "1":
            Benchmark.run_full_benchmark(bname, runs=runs)
        elif b_choice == "2":
            Benchmark.bench_read(bname, runs)
        elif b_choice == "3":
            Benchmark.bench_rank(bname, runs)
        elif b_choice == "4":
            Benchmark.bench_top_ten( runs)
        elif b_choice == "5":
            Benchmark.bench_leaderboard(runs)
        else:
            print("\nInvalid Benchmark choice.")

    elif choice == "9":
        print("\nExiting...")
        print("\nBye")
        break

    elif choice == "10":
        confirm = input("This will clear all Redis cache. Confirm? (yes/no): ")
        if confirm.strip().lower() == "yes":
            cleared = Redis_Handler.clearCache()
            print(f"\n  Redis cache cleared. {cleared} key(s) removed.")
            print("  Next read operations will fall back to MySQL and repopulate the cache.")
            
        else:
            print("\n  Cancelled.")

    else:
        print("\nInvalid choice. Please try again.")

    input("Press Enter key to continue")