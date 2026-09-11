import mysql.connector
import os
from dotenv import load_dotenv


load_dotenv()

sql_host     = os.getenv('MYSQL_Host')
sql_user     = os.getenv('MYSQL_User')
sql_password = os.getenv('MYSQL_Password')
sql_database = os.getenv('MYSQL_DB')

MySQL_connector = None
MySQL_cursor    = None


def initialiseDB():
    """Connect to MySQL and create the cursor. Must be called before any other method."""
    global MySQL_connector, MySQL_cursor
    try:
        MySQL_connector = mysql.connector.connect(
            host     = sql_host,
            user     = sql_user,
            password = sql_password,
            database = sql_database,
        )
        print(
            f"Connected to MySQL Database '{MySQL_connector.database}' "
            f"successfully at '{MySQL_connector.server_host}' "
            f"for user '{MySQL_connector.user}'"
        )
        MySQL_cursor = MySQL_connector.cursor(buffered=True)
        print("Successfully created cursor")
    except Exception as e:
        print(f"[initialiseDB] Error: {e}")


def addPlayer(player):
    try:
        query = """
            INSERT INTO player_info (PlayerName, PlayerLevel, Score) 
            VALUES (%s, %s, %s)
        """
        MySQL_cursor.execute(query, (player.player_name, player.player_level, player.score))
        MySQL_connector.commit()
        player.player_id = MySQL_cursor.lastrowid   # sync DB-assigned PK back to object
        print(f"[addPlayer] Player '{player.player_name}' saved to database with ID {player.player_id}.")
    except Exception as e:
        print(f"[addPlayer] Error: {e}")




def getPlayer(player_name):
    
    try:
        query = "SELECT PlayerID, PlayerName, PlayerLevel, Score FROM player_info WHERE PlayerName = %s"
        MySQL_cursor.execute(query, (player_name,))
        row = MySQL_cursor.fetchone()
        return row
    
    except Exception as e:
        print(f"[getPlayer] Error: {e}")
        return None




def updatePlayer(player):
    
    try:
        query = """
            UPDATE player_info
               SET PlayerName  = %s,
                   PlayerLevel = %s,
                   Score       = %s
             WHERE player_id    = %s
        """
        MySQL_cursor.execute(query, (player.player_name, player.player_level, player.score, player.player_id))
        MySQL_connector.commit()
        if MySQL_cursor.rowcount:
            print(f"[updatePlayer] Player ID {player.player_id} updated in database.")
        else:
            print(f"[updatePlayer] No row found for Player ID {player.player_id}.")
    except Exception as e:
        print(f"[updatePlayer] Error: {e}")


def deletePlayer(player_id):
    try:
        query = "DELETE FROM player_info WHERE PlayerID = %s"
        MySQL_cursor.execute(query, (player_id,))
        MySQL_connector.commit()
        if MySQL_cursor.rowcount:
            print(f"[deletePlayer] Player ID {player_id} removed from database.")
        else:
            print(f"[deletePlayer] No row found for Player ID {player_id}.")
    except Exception as e:
        print(f"[deletePlayer] Error: {e}")


def getLeaderboard():
    
    try:
        query = """
            SELECT PlayerID, PlayerName, PlayerLevel, Score
              FROM player_info
             ORDER BY score DESC
        """
        MySQL_cursor.execute(query)
        rows = MySQL_cursor.fetchall()
        return rows         
    except Exception as e:
        print(f"[getLeaderboard] Error: {e}")
        return []

def getPlayerRank(player_name: str) -> int | None:
    # 1-based rank of player by score descending (rank 1 = highest score).
    # Uses a COUNT subquery — no temp table, single pass.
    # Returns None if player not found.
    
    try:
        MySQL_cursor.execute(
            """SELECT COUNT(*) + 1
                 FROM player_info
                WHERE score > (
                      SELECT Score FROM player_info WHERE PlayerName = %s
                )""",
            (player_name,)
        )
        row = MySQL_cursor.fetchone()
        # If the subquery finds no player, COUNT returns 1 but the outer check
        # will still be wrong — verify the player actually exists first.
        MySQL_cursor.execute(
            "SELECT COUNT(*) FROM player_info WHERE PlayerName = %s",
            (player_name,)
        )

        exists = MySQL_cursor.fetchone()[0]
        return row[0] if exists else None
    
    except Exception as e:
        print(f"[getPlayerRank] MySQL Error: {e}")
        return None


def getTopTen() -> list:
    # Return the top-N players by score descending.
    # Returns [(player_id, player_name, player_level, score), ...].
    
    try:
        MySQL_cursor.execute(
            """SELECT PlayerID, PlayerName, PlayerLevel, Score
                 FROM player_info
                ORDER BY score DESC
                LIMIT 10""",
            
        )
        return MySQL_cursor.fetchall()
    
    except Exception as e:
        print(f"[getTopN] MySQL Error: {e}")
        return []