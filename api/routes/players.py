from fastapi import APIRouter

from api.database import get_connection

router = APIRouter(
    prefix="/players",
    tags=["Players"]
)


@router.get("/")
def get_players():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    player_id,
                    username,
                    display_name
                FROM players
                ORDER BY player_id;
            """)

            players = cursor.fetchall()

    return [
        {
            "player_id": player[0],
            "username": player[1],
            "display_name": player[2]
        }
        for player in players
    ]
@router.get("/{player_id}")
def get_player(player_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    player_id,
                    username,
                    display_name
                FROM players
                WHERE player_id = %s;
            """, (player_id,))

            player = cursor.fetchone()

    if player is None:
        return {
            "error": "Player not found"
        }

    return {
        "player_id": player[0],
        "username": player[1],
        "display_name": player[2]
    }