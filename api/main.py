from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from api.database import get_connection
from datetime import datetime, date

# To run, use this command: uvicorn api.main:app --reload
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
def get_player(
    player_id: int
    ):
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
def create_player(
    player: PlayerCreate
    ):
    with get_connection() as conn:
        with conn.cursor() as cur:
            existing_player = cur.execute("SELECT * FROM players WHERE discord_user_id = %s", (player.discord_user_id,)).fetchone()
            if existing_player:
                raise HTTPException(status_code=409, detail="Player already exists")            
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

#Find player via discord user id endpoint
@app.get('/players/discord/{discord_user_id}')
def get_player_by_discord_id(
    discord_user_id: int
    ):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM players WHERE discord_user_id = %s", (discord_user_id,))
            player = cur.fetchone()
            if player:
                return {"player": player}
            else:
                raise HTTPException(status_code=404, detail="Player not found")

# Update player IGN endpoint
@app.patch('/players/discord/{discord_user_id}/ign')
def update_player_ign(
    discord_user_id: int, 
    ign: str
    ):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE players SET ign = %s, updated_at = CURRENT_TIMESTAMP WHERE discord_user_id = %s", (ign, discord_user_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Player not found")
            conn.commit()
            return {"message": "Player IGN updated successfully"}

# Update player status endpoint
@app.patch('/players/discord/{discord_user_id}/status')
def update_player_status(
    discord_user_id: int,
    status: str
    ):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status_id FROM player_statuses WHERE status_name = %s", (status.upper(),))
            status_id = cur.fetchone()
            if not status_id:
                raise HTTPException(status_code=400, detail="Invalid player status")
            cur.execute("UPDATE players SET status_id = %s, updated_at = CURRENT_TIMESTAMP WHERE discord_user_id = %s", (status_id[0], discord_user_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Player not found")
            conn.commit()
            return {"message": "Player status updated successfully"}



# Team related endpoints
@app.get('/teams')
def get_teams():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM teams")
            teams = cur.fetchall()
            return {"teams": teams}

@app.get('/teams/{team_id}')
def get_team(
    team_id: int
    ):
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
def create_team(
    team: TeamCreate
    ):
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

# Checks team management
@app.get("/teams/discord/{discord_role_id}/management/{discord_user_id}")
def check_team_management(
    discord_role_id: int,
    discord_user_id: int
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    teams.manager_id,
                    teams.assistant_manager_id,
                    players.player_id
                FROM teams
                JOIN players
                    ON players.discord_user_id = %s
                WHERE teams.discord_role_id = %s
                """,
                (discord_user_id, discord_role_id)
            )

            result = cur.fetchone()

            if not result:
                return {
                    "is_manager": False,
                    "is_assistant_manager": False
                }

            manager_id = result[0]
            assistant_manager_id = result[1]
            player_id = result[2]

            return {
                "is_manager": player_id == manager_id,
                "is_assistant_manager": player_id == assistant_manager_id
            }

# Update team assistant manager endpoint
@app.patch("/teams/discord/{discord_role_id}/assistant_manager")
def update_assistant_manager(
    discord_role_id: int,
    assistant_manager_id: int
):
    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT assistant_manager_id
                FROM teams
                WHERE discord_role_id = %s
                """,
                (discord_role_id,)
            )

            team = cur.fetchone()

            if not team:
                raise HTTPException(
                    status_code=404,
                    detail="Team not found"
                )

            if team[0] is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Team already has an assistant manager"
                )

            cur.execute(
                """
                UPDATE teams
                SET assistant_manager_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_role_id = %s
                """,
                (assistant_manager_id, discord_role_id)
            )

            conn.commit()

    return {"message": "Assistant manager added"}

# Remove team assistant manager endpoint
@app.patch("/teams/discord/{discord_role_id}/assistant_manager/remove")
def remove_assistant_manager(
    discord_role_id: int
    ):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Find the current assistant manager
            cur.execute(
                """
                SELECT players.discord_user_id
                FROM teams
                JOIN players
                    ON teams.assistant_manager_id = players.player_id
                WHERE teams.discord_role_id = %s
                """,
                (discord_role_id,)
            )

            assistant_manager = cur.fetchone()

            if not assistant_manager:
                raise HTTPException(
                    status_code=404,
                    detail="Team or assistant manager not found"
                )

            # Remove assistant manager from team
            cur.execute(
                """
                UPDATE teams
                SET assistant_manager_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_role_id = %s
                """,
                (discord_role_id,)
            )

            conn.commit()

    return {
        "message": "Assistant manager removed",
        "discord_user_id": assistant_manager[0]
    }

# Update team manager endpoint
@app.patch("/teams/discord/{discord_role_id}/manager")
def update_team_manager(
    discord_role_id: int,
    manager_id: int
):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Find the current manager's Discord ID
            cur.execute(
                """
                SELECT players.discord_user_id
                FROM teams
                JOIN players
                    ON teams.manager_id = players.player_id
                WHERE teams.discord_role_id = %s
                """,
                (discord_role_id,)
            )

            old_manager = cur.fetchone()

            if not old_manager:
                raise HTTPException(
                    status_code=404,
                    detail="Team or current manager not found"
                )

            # Make sure the new manager exists
            cur.execute(
                """
                SELECT player_id
                FROM players
                WHERE player_id = %s
                """,
                (manager_id,)
            )

            if not cur.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail="New manager is not a registered player"
                )

            # Update manager
            cur.execute(
                """
                UPDATE teams
                SET manager_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_role_id = %s
                """,
                (manager_id, discord_role_id)
            )

            conn.commit()

    return {
        "message": "Manager updated",
        "old_manager_discord_id": old_manager[0]
    }

# Remove team manager endpoint
@app.patch("/teams/discord/{discord_role_id}/manager/remove")
def remove_team_manager(discord_role_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Find current manager
            cur.execute(
                """
                SELECT players.discord_user_id
                FROM teams
                JOIN players
                    ON teams.manager_id = players.player_id
                WHERE teams.discord_role_id = %s
                """,
                (discord_role_id,)
            )

            manager = cur.fetchone()

            if not manager:
                raise HTTPException(
                    status_code=404,
                    detail="Team or manager not found"
                )

            # Remove manager from the team
            cur.execute(
                """
                UPDATE teams
                SET manager_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_role_id = %s
                """,
                (discord_role_id,)
            )

            conn.commit()

    return {
        "message": "Manager removed",
        "discord_user_id": manager[0]
    }

# Update team status endpoint
@app.patch('/teams/discord/{discord_role_id}/status')
def update_team_status(discord_role_id: int, status: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status_id FROM team_statuses WHERE status_name = %s", (status.upper(),))
            status_id = cur.fetchone()
            if not status_id:
                raise HTTPException(status_code=400, detail="Invalid team status")
            cur.execute("UPDATE teams SET status_id = %s, updated_at = CURRENT_TIMESTAMP WHERE discord_role_id = %s", (status_id[0], discord_role_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Team not found")
            conn.commit()
            return {"message": "Team status updated successfully"}

# Update team color endpoint
@app.patch('/teams/discord/{discord_role_id}/color')
def update_team_color(discord_role_id: int, primary_color: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE teams SET primary_color = %s, updated_at = CURRENT_TIMESTAMP WHERE discord_role_id = %s", (primary_color, discord_role_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Team not found")
            conn.commit()
            return {"message": "Team color updated successfully"}

# Update team logo endpoint
@app.patch('/teams/discord/{discord_role_id}/logo')
def update_team_logo(discord_role_id: int, logo_url: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE teams SET logo_url = %s, updated_at = CURRENT_TIMESTAMP WHERE discord_role_id = %s", (logo_url, discord_role_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Team not found")
            conn.commit()
            return {"message": "Team logo updated successfully"}

# Update team name endpoint
@app.patch('/teams/discord/{discord_role_id}/team_name')
def update_team_name(discord_role_id: int, team_name: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE teams SET team_name = %s, updated_at = CURRENT_TIMESTAMP WHERE discord_role_id = %s", (team_name, discord_role_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Team not found")
            conn.commit()
            return {"message": "Team name updated successfully"}

# Update team acronym endpoint
@app.patch('/teams/discord/{discord_role_id}/team_acronym')
def update_team_acronym(discord_role_id: int, team_acronym: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE teams SET team_acronym = %s, updated_at = CURRENT_TIMESTAMP WHERE discord_role_id = %s", (team_acronym, discord_role_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Team not found")
            conn.commit()
            return {"message": "Team acronym updated successfully"}



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



# Season Related endpoints

# Retrieve seasons
@app.get("/seasons")
def get_seasons():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    season_id,
                    season_name,
                    start_date,
                    end_date,
                    free_agent_start,
                    free_agent_end
                FROM seasons
                ORDER BY start_date DESC
                """
            )

            seasons = cur.fetchall()

    return {
        "seasons": seasons
    }

class SeasonCreate(BaseModel):
    season_name: str
    start_date: date
    end_date: date
    free_agent_start: date | None = None
    free_agent_end: date | None = None

# Creates a season
@app.post("/seasons")
def create_season(season: SeasonCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:

            if season.end_date < season.start_date:
                raise HTTPException(
                    status_code=400,
                    detail="Season end date cannot be before start date"
                )

            if (
                season.free_agent_start is not None
                and season.free_agent_end is not None
            ):
                if season.free_agent_end < season.free_agent_start:
                    raise HTTPException(
                        status_code=400,
                        detail="Free agent end date cannot be before free agent start date"
                    )

                if (
                    season.free_agent_start < season.start_date
                    or season.free_agent_end > season.end_date
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="Free agent window must be inside the season dates"
                    )

            cur.execute(
                """
                INSERT INTO seasons (
                    season_name,
                    start_date,
                    end_date,
                    free_agent_start,
                    free_agent_end
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING season_id
                """,
                (
                    season.season_name,
                    season.start_date,
                    season.end_date,
                    season.free_agent_start,
                    season.free_agent_end
                )
            )

            season_id = cur.fetchone()[0]
            conn.commit()

    return {
        "season_id": season_id,
        "message": "Season created successfully"
    }

class SeasonDatesUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    free_agent_start: date | None = None
    free_agent_end: date | None = None

# Sets start and end dates
@app.patch("/seasons/{season_id}/dates")
def update_season_dates(
    season_id: int,
    start_date: date,
    end_date: date
):
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="Season end date cannot be before start date"
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE seasons
                SET start_date = %s,
                    end_date = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE season_id = %s
                """,
                (start_date, end_date, season_id)
            )

            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Season not found"
                )

            conn.commit()

    return {"message": "Season dates updated"}

# Sets Free Agent Week
@app.patch("/seasons/{season_id}/free_agent")
def update_free_agent_window(
    season_id: int,
    free_agent_start: date,
    free_agent_end: date
):
    if free_agent_end < free_agent_start:
        raise HTTPException(
            status_code=400,
            detail="Free agent end date cannot be before start date"
        )

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT start_date, end_date
                FROM seasons
                WHERE season_id = %s
                """,
                (season_id,)
            )

            season = cur.fetchone()

            if not season:
                raise HTTPException(
                    status_code=404,
                    detail="Season not found"
                )

            season_start = season[0]
            season_end = season[1]

            if (
                free_agent_start < season_start
                or free_agent_end > season_end
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Free agent window must fall within season dates"
                )

            cur.execute(
                """
                UPDATE seasons
                SET free_agent_start = %s,
                    free_agent_end = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE season_id = %s
                """,
                (
                    free_agent_start,
                    free_agent_end,
                    season_id
                )
            )

            conn.commit()

    return {"message": "Free agent window updated"}

