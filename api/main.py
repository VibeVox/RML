from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from api.database import get_connection
from datetime import datetime

app = FastAPI()

# Player related endpoints
@app.get('/')
def root():
    return {"message": "RML API is running!"}

@app.get('/players')
def get_players():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM players")
            players = cur.fetchall()
            return {"players": players}

@app.get('/players/{player_id}')
def get_player(player_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM players WHERE player_id = %s", (player_id,))
            player = cur.fetchone()
            if player:
                return {"player": player}
            else:
                raise HTTPException(status_code=404, detail="Player not found")


# Class for creating a new player
class PlayerCreate(BaseModel):
    discord_user_id: int
    ign: str
    status: str = "ACTIVE"


@app.post('/players')
def create_player(player: PlayerCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status_id FROM player_statuses WHERE status_name = %s", (player.status.upper(),))
            status = cur.fetchone()
            if not status:
                raise HTTPException(status_code=400, detail="Invalid player status")
            cur.execute(
                "INSERT INTO players (discord_user_id, ign, status_id) VALUES (%s, %s, %s) RETURNING player_id",
                (player.discord_user_id, player.ign, status[0])
            )
            new_player_id = cur.fetchone()[0]
            conn.commit()
            return {"player_id": new_player_id}


# Team related endpoints
@app.get('/teams')
def get_teams():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM teams")
            teams = cur.fetchall()
            return {"teams": teams}

@app.get('/teams/{team_id}')
def get_team(team_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM teams WHERE team_id = %s", (team_id,))
            team = cur.fetchone()
            if team:
                return {"team": team}
            else:
                raise HTTPException(status_code=404, detail="Team not found")

# Class for creating a new team
class TeamCreate(BaseModel):
    team_name: str
    team_acronym: str | None = None
    discord_role_id: int | None = None
    manager_id: int
    assistant_manager_id: int | None = None
    status: str = "PENDING"
    logo_url: str
    primary_color: str = "#FFFFFF"

@app.post('/teams')
def create_team(team: TeamCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status_id FROM team_statuses WHERE status_name = %s", (team.status.upper(),))
            status = cur.fetchone()
            if not status:
                raise HTTPException(status_code=400, detail="Invalid team status")
            cur.execute(
                "INSERT INTO teams (team_name, team_acronym, discord_role_id, manager_id, assistant_manager_id, status_id, logo_url, primary_color) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING team_id",
                (team.team_name, team.team_acronym, team.discord_role_id, team.manager_id, team.assistant_manager_id, status[0], team.logo_url, team.primary_color)
            )
            new_team_id = cur.fetchone()[0]
            conn.commit()
            return {"team_id": new_team_id}


# Roster related endpoints
@app.get('/teams/{team_id}/roster')
def get_team_roster(team_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute( 
                """
                SELECT
                    players.player_id,
                    players.ign,
                    players.discord_user_id,
                    roster_memberships.signed_at
                FROM roster_memberships
                JOIN players
                ON roster_memberships.player_id = players.player_id
                WHERE roster_memberships.team_id = %s
                AND roster_memberships.released_at IS NULL
                """, 
                (team_id,))
            roster = cur.fetchall()
            return {"roster": roster}

# Class for adding a player to a team roster
class SignPlayer(BaseModel):
    player_id: int
    team_id: int
    season_id: int
    approved: bool = False

@app.post('/roster/sign')
def sign_player(sign: SignPlayer):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check if player is already signed to a team
            cur.execute(
                "SELECT * FROM roster_memberships WHERE player_id = %s AND season_id = %s AND released_at IS NULL",
                (sign.player_id, sign.season_id)
            )
            existing_membership = cur.fetchone()
            if existing_membership:
                raise HTTPException(status_code=400, detail="Player is already signed to a team")

            #Check if player has already played this season
            cur.execute(
                """
                SELECT 1 FROM player_game_stats
                JOIN games ON player_game_stats.game_id = games.game_id
                JOIN matches ON games.match_id = matches.match_id
                WHERE player_game_stats.player_id = %s AND matches.season_id = %s
                LIMIT 1
                """,
                (sign.player_id, sign.season_id)
            )
            existing_game_stats = cur.fetchone()

            if existing_game_stats:
                cur.execute(
                    """
                    SELECT 1
                    FROM seasons
                    WHERE season_id = %s
                    AND CURRENT_DATE BETWEEN free_agent_start AND free_agent_end;
                    """,
                    (sign.season_id,)
                )
                free_agent_window = cur.fetchone()

                if not free_agent_window:
                    raise HTTPException(status_code=400, detail="Player has already played this season and is not in the free agent window")

            # Checks to see if there is a match within the 8 hour window
            cur.execute(
                """
                SELECT matches.match_id, matches.scheduled_at
                FROM matches
                JOIN match_statuses
                    ON matches.status_id = match_statuses.status_id
                WHERE matches.season_id = %s
                AND (matches.home_team_id = %s OR matches.away_team_id = %s)
                AND matches.scheduled_at > CURRENT_TIMESTAMP
                AND matches.scheduled_at <= CURRENT_TIMESTAMP + INTERVAL '8 hours'
                AND match_statuses.status_name = 'SCHEDULED'
                ORDER BY matches.scheduled_at ASC
                LIMIT 1;
                """,
                (sign.season_id, sign.team_id, sign.team_id)
            )

            upcoming_match = cur.fetchone()

            if upcoming_match and not sign.approved:
                return {
                    'approval_required': True,
                    'match_id': upcoming_match[0],
                    'scheduled_at': upcoming_match[1]
                }


                
            # Sign the player to the team
            cur.execute(
                "INSERT INTO roster_memberships (player_id, team_id, season_id) VALUES (%s, %s, %s)",
                (sign.player_id, sign.team_id, sign.season_id)
            )
            conn.commit()
            return {"message": "Player signed to team successfully"}

#Class for releasing a player from a team roster
class ReleasePlayer(BaseModel):
    player_id: int
    team_id: int
    season_id: int

@app.post('/roster/release')
def release_player(release: ReleasePlayer):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check if player is signed to the team
            cur.execute(
                "SELECT * FROM roster_memberships WHERE player_id = %s AND team_id = %s AND season_id = %s AND released_at IS NULL",
                (release.player_id, release.team_id, release.season_id)
            )
            existing_membership = cur.fetchone()
            if not existing_membership:
                raise HTTPException(status_code=400, detail="Player is not signed to this team")

            # Release the player from the team
            cur.execute(
                "UPDATE roster_memberships SET released_at = NOW() WHERE player_id = %s AND team_id = %s AND season_id = %s AND released_at IS NULL",
                (release.player_id, release.team_id, release.season_id)
            )
            conn.commit()
            return {"message": "Player released from team successfully"}

# Match related endpoints
@app.get('/matches')
def get_matches():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM matches")
            matches = cur.fetchall()
            return {"matches": matches}

@app.get('/matches/{match_id}')
def get_match(match_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM matches WHERE match_id = %s", (match_id,))
            match = cur.fetchone()
            if match:
                return {"match": match}
            else:
                raise HTTPException(status_code=404, detail="Match not found")

@app.get('/matches/{match_id}/games')
def get_match_games(match_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE match_id = %s", (match_id,))
            games = cur.fetchall()
            return {"games": games}

@app.get('/matches/{match_id}/games/{game_id}')
def get_match_game(match_id: int, game_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE match_id = %s AND game_id = %s", (match_id, game_id))
            game = cur.fetchone()
            if game:
                return {"game": game}
            else:
                raise HTTPException(status_code=404, detail="Game not found")

# Class for creating a new match
class MatchCreate(BaseModel):
    home_team_id: int
    away_team_id: int
    season_id: int
    scheduled_at: datetime
    status: str = "SCHEDULED"
@app.post('/matches')
def create_match(match: MatchCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status_id FROM match_statuses WHERE status_name = %s", (match.status.upper(),))
            status = cur.fetchone()
            if not status:
                raise HTTPException(status_code=400, detail="Invalid match status")
            cur.execute(
                "INSERT INTO matches (home_team_id, away_team_id, season_id, scheduled_at, status_id) VALUES (%s, %s, %s, %s, %s)",
                (match.home_team_id, match.away_team_id, match.season_id, match.scheduled_at, status[0])
            )
            conn.commit()
            return {"message": "Match created successfully"}

#class for creating a new game
class GameCreate(BaseModel):
    game_number: int
    winner_team_id: int
    home_score: int
    away_score: int
    screenshot_url: str

@app.post('/matches/{match_id}/games')
def create_game(match_id: int, game: GameCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO games (match_id, game_number, winner_team_id, home_score, away_score, screenshot_url) VALUES (%s, %s, %s, %s, %s, %s)",
                (match_id, game.game_number, game.winner_team_id, game.home_score, game.away_score, game.screenshot_url)
            )
            conn.commit()
            return {"message": "Game created successfully"}

# Class for creating a new player game stats
class PlayerGameStatsCreate(BaseModel):
    player_id: int
    team_id: int
    goals: int
    assists: int
    passes: int
    interceptions: int
    saves: int
    score: int
    mvp: bool = False

@app.post('/games/{game_id}/stats')
def create_player_game_stats(game_id: int, stats: PlayerGameStatsCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO player_game_stats (player_id, team_id, game_id, goals, assists, passes, interceptions, saves, score, mvp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (stats.player_id, stats.team_id, game_id, stats.goals, stats.assists, stats.passes, stats.interceptions, stats.saves, stats.score, stats.mvp)
            )
            conn.commit()
            return {"message": "Player game stats created successfully"}
        