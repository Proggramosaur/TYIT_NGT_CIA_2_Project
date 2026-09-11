import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST      = os.getenv('REDIS_Host')
REDIS_PORT      = int(os.getenv('REDIS_Port'))
REDIS_DB        = int(os.getenv('REDIS_DB'))

CACHE_TTL       = 900          
LEADERBOARD_KEY = 'leaderboard'

redis_client = None



def initialiseCache():
    global redis_client
    try:
        redis_client = redis.Redis(
            host             = REDIS_HOST,
            port             = REDIS_PORT,
            db               = REDIS_DB,
            decode_responses = True,
        )

        redis_client.ping()
        print(f"Connected to Redis at '{REDIS_HOST}:{REDIS_PORT}' db={REDIS_DB}")
    except Exception as e:
        print(f"[initialiseCache] Redis Error: {e}")


# ── Key helpers ───────────────────────────────────────────────────────────────
#
#  Key                          Type          Contains
#  ───────────────────────────  ────────────  ──────────────────────────────
#  player:id:{player_id}        String (JSON) Full player record
#  player:name:{name_lower}     String        player_id (pointer)
#  leaderboard                  Sorted Set    member=player_id, score=score
#
#  Name lookups: GET player:name:{name} > player_id > GET player:id:{id}
#  Leaderboard:  ZREVRANGE leaderboard 0 9 WITHSCORES 

def _id_key(player_id: int) -> str:
    return f'player:id:{player_id}'

def _name_key(player_name: str) -> str:
    return f'player:name:{player_name.lower()}'


# Conversion Methods

def _player_to_json(player) -> str:
    return json.dumps({
        'player_id':    player.player_id,
        'player_name':  player.player_name,
        'player_level': player.player_level,
        'score':        player.score,
    })

def _dict_to_tuple(data: dict) -> tuple:
    """Convert a cached JSON dict back to (player_id, player_name, player_level, score)."""
    return (data['player_id'], data['player_name'], data['player_level'], data['score'])


# Cache player after write

def cachePlayer(player):
    try:
        pipe = redis_client.pipeline()
        pipe.setex(_id_key(player.player_id),     CACHE_TTL, _player_to_json(player))  # full record
        pipe.setex(_name_key(player.player_name), CACHE_TTL, player.player_id)          # name > id pointer
        pipe.zadd(LEADERBOARD_KEY, {player.player_id: player.score})                    # sorted set entry
        pipe.execute()
        print(f"[cachePlayer] '{player.player_name}' (ID {player.player_id}) cached in Redis.")
    except Exception as e:
        print(f"[cachePlayer] Redis Error: {e}")




def getCachedPlayer(player_name: str) -> tuple | None:
    # Attempt to resolve player by name from Redis.
    # Returns (player_id, player_name, player_level, score) on hit, None on miss.

    # Two-steps :
    #   1. player:name:{name}  > player_id
    #   2. player:id:{id}      > full JSON record
    # If either key is missing (partial expiry), returns None > caller falls back to MySQL.
    
    try:
        cached_id = redis_client.get(_name_key(player_name))
        if not cached_id:
            return None     # name key missing , cache miss

        cached_record = redis_client.get(_id_key(int(cached_id)))
        if not cached_record:
            return None     # name key alive but id key expired , cache miss

        print(f"[getCachedPlayer] Cache hit for '{player_name}'.")
        return _dict_to_tuple(json.loads(cached_record))
    except Exception as e:
        print(f"[getCachedPlayer] Redis Error: {e}")
        return None         # any Redis error > fall back to MySQL


def repopulatePlayer(player):
    # Repopulate player:id: and player:name: keys after a MySQL cache-miss read.
    # Does NOT touch the leaderboard sorted set , that is repopulated separately
    # only on a full leaderboard cache miss to avoid partial state.
    
    try:
        pipe = redis_client.pipeline()
        pipe.setex(_id_key(player.player_id),     CACHE_TTL, _player_to_json(player))
        pipe.setex(_name_key(player.player_name), CACHE_TTL, player.player_id)
        pipe.execute()
        print(f"[repopulatePlayer] Cache repopulated for '{player.player_name}'.")
    except Exception as e:
        print(f"[repopulatePlayer] Redis Error: {e}")


# Cache refresh after update 

def refreshCachedPlayer(player, old_name: str):
    # Refresh all Redis keys after a successful MySQL UPDATE.
    # old_name is required: if the player's name changed, the stale
    # player:name:{old_name} key must be explicitly deleted, otherwise
    # it stays alive until TTL expiry and points at the wrong record.
    
    try:
        pipe = redis_client.pipeline()
        pipe.setex(_id_key   (player.player_id),   CACHE_TTL, _player_to_json(player))  # refresh full record
        pipe.setex(_name_key (player.player_name), CACHE_TTL, player.player_id)          # new/same name pointer

        if old_name.lower() != player.player_name.lower():
            pipe.delete(_name_key(old_name))                                             # evict stale name key
        pipe.zadd(LEADERBOARD_KEY, {player.player_id: player.score})                    # update score in sorted set
        pipe.execute()
        print(f"[refreshCachedPlayer] Player ID {player.player_id} cache refreshed.")
    except Exception as e:
        print(f"[refreshCachedPlayer] Redis Error: {e}")


# Delete cache after delete

def evictPlayer(player_id: int, player_name: str):
    # """Evict all Redis keys for a player after a successful MySQL DELETE."""
    try:
        pipe = redis_client.pipeline()
        pipe.delete(_id_key(player_id))           # remove full record
        pipe.delete(_name_key(player_name))        # remove name pointer
        pipe.zrem(LEADERBOARD_KEY, player_id)      # remove from sorted set
        pipe.execute()

        print(f"[evictPlayer] Player ID {player_id} evicted from Redis.")

    except Exception as e:
        print(f"[evictPlayer] Redis Error: {e}")


#  Leaderboard cache-aside

def getCachedLeaderboard() -> list | None:
    try:
        entries = redis_client.zrevrange(LEADERBOARD_KEY, 0, -1, withscores=True)
        if not entries:
            return None

        # Batch all GET player:id: calls in one pipeline — single round trip
        pipe = redis_client.pipeline()
        for pid_str, _ in entries:
            pipe.get(_id_key(int(pid_str)))
        results = pipe.execute()

        rows = []
        for cached in results:
            if not cached:
                print("[getCachedLeaderboard] Partial cache miss — falling back to MySQL.")
                return None
            rows.append(_dict_to_tuple(json.loads(cached)))

        print("[getCachedLeaderboard] Serving leaderboard from Redis.")
        return rows
    except Exception as e:
        print(f"[getCachedLeaderboard] Redis Error: {e}")
        return None


def repopulateLeaderboard(rows: list, player_class):
    # Repopulate all Redis structures after a MySQL leaderboard cache-miss read.
    # rows: list of (player_id, player_name, player_level, score) tuples from MySQL.
    # player_class: the Player class , passed in to avoid a circular import.
    
    try:
        pipe = redis_client.pipeline()
        for pid, pname, plevel, pscore in rows:
            temp = player_class(pid, pname, plevel, pscore)
            pipe.setex(_id_key(pid),     CACHE_TTL, _player_to_json(temp))
            pipe.setex(_name_key(pname), CACHE_TTL, pid)
            pipe.zadd(LEADERBOARD_KEY, {pid: pscore})
        pipe.execute()
        print("[repopulateLeaderboard] Leaderboard repopulated in Redis.")
    except Exception as e:
        print(f"[repopulateLeaderboard] Redis Error: {e}")

def getCachedPlayerRank(player_name: str) -> int | None:
    # """1-based rank from the sorted set via ZREVRANK (0-based internally).
    # Returns None on miss or if player is not in the sorted set.
    # """
    try:
        cached_id = redis_client.get(_name_key(player_name))
        if not cached_id:
            return None
        rank_0based = redis_client.zrevrank(LEADERBOARD_KEY, int(cached_id))
        if rank_0based is None:
            return None
        print(f"[getCachedPlayerRank] Cache hit for '{player_name}'.")
        return rank_0based + 1      # convert to 1-based
    except Exception as e:
        print(f"[getCachedPlayerRank] Redis Error: {e}")
        return None


def getCachedTopTen() -> list | None:
    try:
        entries = redis_client.zrevrange(LEADERBOARD_KEY, 0, 9, withscores=True)
        if not entries:
            return None

        pipe = redis_client.pipeline()
        for pid_str, _ in entries:
            pipe.get(_id_key(int(pid_str)))
        results = pipe.execute()

        rows = []
        for cached in results:
            if not cached:
                return None
            rows.append(_dict_to_tuple(json.loads(cached)))

        print(f"[getCachedTopN] Top 10 served from Redis.")
        return rows
    except Exception as e:
        print(f"[getCachedTopN] Redis Error: {e}")
        return None

def clearCache():
    try:
        cleared = redis_client.dbsize()
        redis_client.flushdb()
        print(f"[clearCache] Flushed {cleared} key(s) from Redis db={REDIS_DB}.")
        return cleared
    
    except Exception as e:
        print(f"[clearCache] Redis Error: {e}")
        return 0