from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from api.database import get_connection
from datetime import datetime, date
from typing import Optional
import re

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

# Update a team color
@app.patch("/teams/discord/{discord_role_id}/color")
def update_team_color(
    discord_role_id: int,
    primary_color: str
):
    # Validate hex color
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", primary_color):
        raise HTTPException(
            status_code=400,
            detail="Color must be in hex format, such as #FF5733"
        )

    primary_color = primary_color.upper()

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT team_id, team_name
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

            cur.execute(
                """
                UPDATE teams
                SET
                    primary_color = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_role_id = %s
                """,
                (
                    primary_color,
                    discord_role_id
                )
            )

            conn.commit()

    return {
        "message": "Team color updated successfully",
        "team_id": team[0],
        "team_name": team[1],
        "primary_color": primary_color
    }

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
    home_score: int
    away_score: int
    screenshot_url: str


@app.post("/matches/{match_id}/games")
def create_game(match_id: int, game: GameCreate):

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Get the two teams in this match
            cur.execute(
                """
                SELECT
                    home_team_id,
                    away_team_id
                FROM matches
                WHERE match_id = %s
                """,
                (match_id,)
            )

            match = cur.fetchone()

            if not match:
                raise HTTPException(
                    status_code=404,
                    detail="Match not found"
                )

            home_team_id = match[0]
            away_team_id = match[1]

            # Determine winner from score
            if game.home_score > game.away_score:
                winner_team_id = home_team_id

            elif game.away_score > game.home_score:
                winner_team_id = away_team_id

            else:
                winner_team_id = None

            # Save game
            cur.execute(
                """
                INSERT INTO games (
                    match_id,
                    game_number,
                    winner_team_id,
                    home_score,
                    away_score,
                    screenshot_url
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    match_id,
                    game.game_number,
                    winner_team_id,
                    game.home_score,
                    game.away_score,
                    game.screenshot_url
                )
            )

            conn.commit()

    return {
        "message": "Game created successfully",
        "winner_team_id": winner_team_id
    }

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

# Gets the current season's leagues
@app.get("/leagues/current")
def get_current_leagues():
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Find the current season
            cur.execute(
                """
                SELECT season_id, season_name
                FROM seasons
                WHERE CURRENT_DATE BETWEEN start_date AND end_date
                ORDER BY start_date DESC
                LIMIT 1
                """
            )

            season = cur.fetchone()

            if not season:
                raise HTTPException(
                    status_code=404,
                    detail="There is no currently active season"
                )

            season_id = season[0]
            season_name = season[1]

            # Find leagues belonging to the current season
            cur.execute(
                """
                SELECT league_id, league_name
                FROM leagues
                WHERE season_id = %s
                ORDER BY league_id
                """,
                (season_id,)
            )

            leagues = cur.fetchall()

    return {
        "season_id": season_id,
        "season_name": season_name,
        "leagues": leagues
    }

# Set's a team's league
@app.patch("/teams/discord/{discord_role_id}/league")
def set_team_league(
    discord_role_id: int,
    league_id: int
):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # --------------------------------------------------
            # 1. Find team
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    team_id,
                    team_name
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

            team_id = team[0]
            team_name = team[1]

            # --------------------------------------------------
            # 2. Find league and its season
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    leagues.league_id,
                    leagues.league_name,
                    leagues.season_id,
                    seasons.season_name
                FROM leagues
                JOIN seasons
                    ON leagues.season_id = seasons.season_id
                WHERE leagues.league_id = %s
                """,
                (league_id,)
            )

            league = cur.fetchone()

            if not league:
                raise HTTPException(
                    status_code=404,
                    detail="League not found"
                )

            league_name = league[1]
            season_id = league[2]
            season_name = league[3]

            # --------------------------------------------------
            # 3. Make sure team is not already assigned
            #    to this season
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    team_season_id,
                    league_id
                FROM team_seasons
                WHERE team_id = %s
                  AND season_id = %s
                """,
                (
                    team_id,
                    season_id
                )
            )

            existing_assignment = cur.fetchone()

            if existing_assignment:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"{team_name} is already assigned "
                        f"to a league for {season_name}"
                    )
                )

            # --------------------------------------------------
            # 4. Check whether any CURRENT team member is
            #    already actively rostered to another team
            #    in this season
            #
            #    This prevents silently creating bad season data.
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    players.ign,
                    teams.team_name
                FROM team_memberships
                JOIN players
                    ON team_memberships.player_id = players.player_id
                JOIN roster_memberships
                    ON team_memberships.player_id =
                       roster_memberships.player_id
                JOIN teams
                    ON roster_memberships.team_id = teams.team_id
                WHERE team_memberships.team_id = %s
                  AND team_memberships.left_at IS NULL
                  AND roster_memberships.season_id = %s
                  AND roster_memberships.released_at IS NULL
                  AND roster_memberships.team_id != %s
                LIMIT 1
                """,
                (
                    team_id,
                    season_id,
                    team_id
                )
            )

            roster_conflict = cur.fetchone()

            if roster_conflict:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"{roster_conflict[0]} is already rostered to "
                        f"{roster_conflict[1]} for {season_name}"
                    )
                )

            # --------------------------------------------------
            # 5. Assign team to league / season
            # --------------------------------------------------

            cur.execute(
                """
                INSERT INTO team_seasons (
                    team_id,
                    season_id,
                    league_id
                )
                VALUES (%s, %s, %s)
                RETURNING team_season_id
                """,
                (
                    team_id,
                    season_id,
                    league_id
                )
            )

            team_season_id = cur.fetchone()[0]

            # --------------------------------------------------
            # 6. Copy CURRENT live roster into season roster
            #
            #    Anyone currently active in team_memberships
            #    now gets a roster_memberships row.
            # --------------------------------------------------

            cur.execute(
                """
                INSERT INTO roster_memberships (
                    player_id,
                    team_id,
                    season_id
                )
                SELECT
                    team_memberships.player_id,
                    team_memberships.team_id,
                    %s
                FROM team_memberships
                WHERE team_memberships.team_id = %s
                  AND team_memberships.left_at IS NULL
                ON CONFLICT DO NOTHING
                RETURNING membership_id
                """,
                (
                    season_id,
                    team_id
                )
            )

            copied_memberships = cur.fetchall()
            roster_count = len(copied_memberships)

            # --------------------------------------------------
            # 7. Commit everything together
            # --------------------------------------------------

            conn.commit()

    return {
        "message": "Team assigned to league successfully",
        "team_season_id": team_season_id,
        "team_id": team_id,
        "team_name": team_name,
        "league_id": league_id,
        "league_name": league_name,
        "season_id": season_id,
        "season_name": season_name,
        "roster_members_copied": roster_count
    }

# Updates a team's league if incorrect
@app.patch("/teams/discord/{discord_role_id}/league/update")
def update_team_league(
    discord_role_id: int,
    league_id: int
):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Find team
            cur.execute(
                """
                SELECT team_id
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

            team_id = team[0]

            # Find new league and its season
            cur.execute(
                """
                SELECT
                    leagues.season_id,
                    leagues.league_name,
                    seasons.season_name
                FROM leagues
                JOIN seasons
                    ON leagues.season_id = seasons.season_id
                WHERE leagues.league_id = %s
                """,
                (league_id,)
            )

            new_league = cur.fetchone()

            if not new_league:
                raise HTTPException(
                    status_code=404,
                    detail="League not found"
                )

            season_id = new_league[0]
            new_league_name = new_league[1]
            season_name = new_league[2]

            # Find team's existing assignment for that season
            cur.execute(
                """
                SELECT
                    team_seasons.team_season_id,
                    team_seasons.league_id,
                    leagues.league_name
                FROM team_seasons
                LEFT JOIN leagues
                    ON team_seasons.league_id = leagues.league_id
                WHERE team_seasons.team_id = %s
                  AND team_seasons.season_id = %s
                """,
                (team_id, season_id)
            )

            existing = cur.fetchone()

            if not existing:
                raise HTTPException(
                    status_code=404,
                    detail="Team is not assigned to this season"
                )

            team_season_id = existing[0]
            old_league_id = existing[1]
            old_league_name = existing[2]

            if old_league_id == league_id:
                raise HTTPException(
                    status_code=409,
                    detail="Team is already assigned to that league"
                )

            # Update league
            cur.execute(
                """
                UPDATE team_seasons
                SET league_id = %s
                WHERE team_season_id = %s
                """,
                (
                    league_id,
                    team_season_id
                )
            )

            conn.commit()

    return {
        "message": "Team league updated",
        "team_id": team_id,
        "season_id": season_id,
        "season_name": season_name,
        "old_league_id": old_league_id,
        "old_league_name": old_league_name,
        "new_league_id": league_id,
        "new_league_name": new_league_name
    }

# League Class
class LeagueCreate(BaseModel):
    league_name: str
    season_id: int

# Creates a league
@app.post("/leagues")
def create_league(league: LeagueCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Make sure season exists
            cur.execute(
                """
                SELECT season_name
                FROM seasons
                WHERE season_id = %s
                """,
                (league.season_id,)
            )

            season = cur.fetchone()

            if not season:
                raise HTTPException(
                    status_code=404,
                    detail="Season not found"
                )

            # Prevent duplicate league names within the same season
            cur.execute(
                """
                SELECT league_id
                FROM leagues
                WHERE season_id = %s
                  AND LOWER(league_name) = LOWER(%s)
                """,
                (
                    league.season_id,
                    league.league_name
                )
            )

            existing_league = cur.fetchone()

            if existing_league:
                raise HTTPException(
                    status_code=409,
                    detail="A league with that name already exists for this season"
                )

            # Create league
            cur.execute(
                """
                INSERT INTO leagues (
                    season_id,
                    league_name
                )
                VALUES (%s, %s)
                RETURNING league_id
                """,
                (
                    league.season_id,
                    league.league_name
                )
            )

            league_id = cur.fetchone()[0]
            conn.commit()

    return {
        "message": "League created successfully",
        "league_id": league_id,
        "league_name": league.league_name,
        "season_id": league.season_id,
        "season_name": season[0]
    }


# Scheduling endpoints

# Scheduling CLasses
class MatchProposalCreate(BaseModel):
    home_discord_role_id: int
    away_discord_role_id: int
    scheduled_at: datetime


class MatchTimeUpdate(BaseModel):
    scheduled_at: datetime

# Propose a Match time
@app.post("/matches/propose")
def propose_match(match: MatchProposalCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Make sure home and away teams are different
            if match.home_discord_role_id == match.away_discord_role_id:
                raise HTTPException(
                    status_code=400,
                    detail="A team cannot play itself"
                )

            # Find home team
            cur.execute(
                """
                SELECT team_id, team_name
                FROM teams
                WHERE discord_role_id = %s
                """,
                (match.home_discord_role_id,)
            )

            home_team = cur.fetchone()

            if not home_team:
                raise HTTPException(
                    status_code=404,
                    detail="Home team is not registered"
                )

            # Find away team
            cur.execute(
                """
                SELECT team_id, team_name
                FROM teams
                WHERE discord_role_id = %s
                """,
                (match.away_discord_role_id,)
            )

            away_team = cur.fetchone()

            if not away_team:
                raise HTTPException(
                    status_code=404,
                    detail="Away team is not registered"
                )

            home_team_id = home_team[0]
            home_team_name = home_team[1]

            away_team_id = away_team[0]
            away_team_name = away_team[1]

            # Find a season both teams belong to
            cur.execute(
                """
                SELECT ts1.season_id, seasons.season_name
                FROM team_seasons ts1
                JOIN team_seasons ts2
                    ON ts1.season_id = ts2.season_id
                JOIN seasons
                    ON ts1.season_id = seasons.season_id
                WHERE ts1.team_id = %s
                  AND ts2.team_id = %s
                ORDER BY seasons.start_date DESC
                LIMIT 1
                """,
                (
                    home_team_id,
                    away_team_id
                )
            )

            season = cur.fetchone()

            if not season:
                raise HTTPException(
                    status_code=400,
                    detail="These teams do not belong to the same season"
                )

            season_id = season[0]
            season_name = season[1]

            # Get PROPOSED status
            cur.execute(
                """
                SELECT status_id
                FROM match_statuses
                WHERE status_name = 'PROPOSED'
                """
            )

            proposed_status = cur.fetchone()

            if not proposed_status:
                raise HTTPException(
                    status_code=500,
                    detail="PROPOSED match status is not configured"
                )

            # Create match proposal
            cur.execute(
                """
                INSERT INTO matches (
                    season_id,
                    home_team_id,
                    away_team_id,
                    scheduled_at,
                    status_id,
                    home_approved,
                    away_approved
                )
                VALUES (%s, %s, %s, %s, %s, FALSE, FALSE)
                RETURNING match_id
                """,
                (
                    season_id,
                    home_team_id,
                    away_team_id,
                    match.scheduled_at,
                    proposed_status[0]
                )
            )

            match_id = cur.fetchone()[0]

            conn.commit()

    return {
        "match_id": match_id,
        "season_id": season_id,
        "season_name": season_name,
        "home_team_id": home_team_id,
        "home_team_name": home_team_name,
        "away_team_id": away_team_id,
        "away_team_name": away_team_name,
        "scheduled_at": match.scheduled_at
    }


# Approve a proposal
@app.patch("/matches/{match_id}/approve/{side}")
def approve_match(
    match_id: int,
    side: str
):
    if side not in ("home", "away"):
        raise HTTPException(
            status_code=400,
            detail="Side must be home or away"
        )

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Make sure match exists
            cur.execute(
                """
                SELECT home_approved, away_approved
                FROM matches
                WHERE match_id = %s
                """,
                (match_id,)
            )

            match = cur.fetchone()

            if not match:
                raise HTTPException(
                    status_code=404,
                    detail="Match not found"
                )

            if side == "home":
                cur.execute(
                    """
                    UPDATE matches
                    SET home_approved = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE match_id = %s
                    """,
                    (match_id,)
                )

            else:
                cur.execute(
                    """
                    UPDATE matches
                    SET away_approved = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE match_id = %s
                    """,
                    (match_id,)
                )

            # Check current approval state
            cur.execute(
                """
                SELECT home_approved, away_approved
                FROM matches
                WHERE match_id = %s
                """,
                (match_id,)
            )

            approval = cur.fetchone()

            home_approved = approval[0]
            away_approved = approval[1]

            scheduled = False

            # Both agreed -- make match official
            if home_approved and away_approved:

                cur.execute(
                    """
                    SELECT status_id
                    FROM match_statuses
                    WHERE status_name = 'SCHEDULED'
                    """
                )

                scheduled_status = cur.fetchone()

                if not scheduled_status:
                    raise HTTPException(
                        status_code=500,
                        detail="SCHEDULED status is not configured"
                    )

                cur.execute(
                    """
                    UPDATE matches
                    SET status_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE match_id = %s
                    """,
                    (
                        scheduled_status[0],
                        match_id
                    )
                )

                scheduled = True

            conn.commit()

    return {
        "match_id": match_id,
        "home_approved": home_approved,
        "away_approved": away_approved,
        "scheduled": scheduled
    }


# Suggest a different time
@app.patch("/matches/{match_id}/time")
def update_match_time(
    match_id: int,
    update: MatchTimeUpdate
):
    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE matches
                SET scheduled_at = %s,
                    home_approved = FALSE,
                    away_approved = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE match_id = %s
                """,
                (
                    update.scheduled_at,
                    match_id
                )
            )

            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Match not found"
                )

            conn.commit()

    return {
        "message": "Proposed match time updated",
        "scheduled_at": update.scheduled_at
    }


# Find a team's season
@app.get("/teams/discord/{discord_role_id}/current-season")
def get_team_current_season(discord_role_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    teams.team_id,
                    teams.team_name,
                    seasons.season_id,
                    seasons.season_name
                FROM teams
                JOIN team_seasons
                    ON teams.team_id = team_seasons.team_id
                JOIN seasons
                    ON team_seasons.season_id = seasons.season_id
                WHERE teams.discord_role_id = %s
                  AND CURRENT_DATE BETWEEN
                      seasons.start_date AND seasons.end_date
                ORDER BY seasons.start_date DESC
                LIMIT 1
                """,
                (discord_role_id,)
            )

            result = cur.fetchone()

            if not result:
                raise HTTPException(
                    status_code=404,
                    detail="Team is not assigned to the current season"
                )

    return {
        "team_id": result[0],
        "team_name": result[1],
        "season_id": result[2],
        "season_name": result[3]
    }

class SignPlayer(BaseModel):
    player_id: int
    team_id: int
    approved: bool = False


class ReleasePlayer(BaseModel):
    player_id: int
    team_id: int

@app.post("/roster/sign")
def sign_player(sign: SignPlayer):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # --------------------------------------------------
            # 1. Verify player exists and get status
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    players.player_id,
                    player_statuses.status_name
                FROM players
                JOIN player_statuses
                    ON players.status_id = player_statuses.status_id
                WHERE players.player_id = %s
                """,
                (sign.player_id,)
            )

            player = cur.fetchone()

            if not player:
                raise HTTPException(
                    status_code=404,
                    detail="Player not found"
                )

            player_status = player[1]

            if player_status in ("SUSPENDED", "BANNED"):
                raise HTTPException(
                    status_code=403,
                    detail=f"Player cannot be signed while status is {player_status}"
                )

            # --------------------------------------------------
            # 2. Verify team exists
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    team_id,
                    team_name,
                    discord_role_id
                FROM teams
                WHERE team_id = %s
                """,
                (sign.team_id,)
            )

            team = cur.fetchone()

            if not team:
                raise HTTPException(
                    status_code=404,
                    detail="Team not found"
                )

            team_id = team[0]
            team_name = team[1]
            team_discord_role_id = team[2]

            # --------------------------------------------------
            # 3. Make sure player is not already on a team
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    team_memberships.membership_id,
                    team_memberships.team_id,
                    teams.team_name
                FROM team_memberships
                JOIN teams
                    ON team_memberships.team_id = teams.team_id
                WHERE team_memberships.player_id = %s
                  AND team_memberships.left_at IS NULL
                """,
                (sign.player_id,)
            )

            existing_membership = cur.fetchone()

            if existing_membership:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Player is already signed to "
                        f"{existing_membership[2]}"
                    )
                )

            # --------------------------------------------------
            # 4. Determine whether team is currently assigned
            #    to a season/league
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    team_seasons.season_id,
                    team_seasons.league_id,
                    seasons.season_name,
                    seasons.start_date,
                    seasons.end_date
                FROM team_seasons
                JOIN seasons
                    ON team_seasons.season_id = seasons.season_id
                WHERE team_seasons.team_id = %s
                ORDER BY seasons.start_date DESC
                LIMIT 1
                """,
                (sign.team_id,)
            )

            season_assignment = cur.fetchone()

            season_id = None
            league_id = None
            season_name = None

            if season_assignment:
                season_id = season_assignment[0]
                league_id = season_assignment[1]
                season_name = season_assignment[2]

            # --------------------------------------------------
            # 5. If team has a season, check if player has
            #    already played this season
            #
            #    This will currently usually be False because
            #    stats/participation tracking is not populated.
            # --------------------------------------------------

            has_played = False

            if season_id is not None:
                cur.execute(
                    """
                    SELECT 1
                    FROM player_game_stats
                    JOIN games
                        ON player_game_stats.game_id = games.game_id
                    JOIN matches
                        ON games.match_id = matches.match_id
                    WHERE player_game_stats.player_id = %s
                      AND matches.season_id = %s
                    LIMIT 1
                    """,
                    (
                        sign.player_id,
                        season_id
                    )
                )

                has_played = cur.fetchone() is not None

            # --------------------------------------------------
            # 6. Free Agent Week restriction
            #
            #    Only applies if:
            #    - team has a season
            #    - player has already played that season
            # --------------------------------------------------

            if season_id is not None and has_played:
                cur.execute(
                    """
                    SELECT 1
                    FROM seasons
                    WHERE season_id = %s
                      AND CURRENT_DATE BETWEEN
                          free_agent_start AND free_agent_end
                    """,
                    (season_id,)
                )

                in_free_agent_window = cur.fetchone()

                if not in_free_agent_window:
                    raise HTTPException(
                        status_code=403,
                        detail="TRANSFER_LOCKED"
                    )

            # --------------------------------------------------
            # 7. Check for roster lock caused by match scheduling
            #
            #    Rules:
            #
            #    PROPOSED match:
            #       both teams are immediately roster locked
            #
            #    SCHEDULED match:
            #       roster locked if match is within 8 hours
            #
            #    Only applies if the team has a season.
            # --------------------------------------------------

            restricted_match = None

            if season_id is not None:
                cur.execute(
                    """
                    SELECT
                        matches.match_id,
                        matches.scheduled_at,
                        matches.home_team_id,
                        matches.away_team_id,
                        match_statuses.status_name
                    FROM matches
                    JOIN match_statuses
                        ON matches.status_id = match_statuses.status_id
                    WHERE matches.season_id = %s
                      AND (
                          matches.home_team_id = %s
                          OR matches.away_team_id = %s
                      )
                      AND (
                          match_statuses.status_name = 'PROPOSED'

                          OR

                          (
                              match_statuses.status_name = 'SCHEDULED'
                              AND matches.scheduled_at > CURRENT_TIMESTAMP
                              AND matches.scheduled_at <=
                                  CURRENT_TIMESTAMP + INTERVAL '8 hours'
                          )
                      )
                    ORDER BY matches.scheduled_at ASC
                    LIMIT 1
                    """,
                    (
                        season_id,
                        sign.team_id,
                        sign.team_id
                    )
                )

                restricted_match = cur.fetchone()

            # --------------------------------------------------
            # 8. If locked and not yet approved, return opponent
            #    info so Discord can request approval
            # --------------------------------------------------

            if restricted_match and not sign.approved:
                match_id = restricted_match[0]
                scheduled_at = restricted_match[1]
                home_team_id = restricted_match[2]
                away_team_id = restricted_match[3]
                match_status = restricted_match[4]

                if sign.team_id == home_team_id:
                    opponent_team_id = away_team_id
                else:
                    opponent_team_id = home_team_id

                cur.execute(
                    """
                    SELECT
                        team_name,
                        discord_role_id
                    FROM teams
                    WHERE team_id = %s
                    """,
                    (opponent_team_id,)
                )

                opponent = cur.fetchone()

                if not opponent:
                    raise HTTPException(
                        status_code=500,
                        detail="Opponent team could not be found"
                    )

                return {
                    "approval_required": True,
                    "match_id": match_id,
                    "scheduled_at": scheduled_at,
                    "match_status": match_status,
                    "opponent_team_id": opponent_team_id,
                    "opponent_team_name": opponent[0],
                    "opponent_discord_role_id": opponent[1],
                    "eligibility": (
                        "TRANSFER"
                        if has_played
                        else "FREE_AGENT"
                    )
                }

            # --------------------------------------------------
            # 9. Insert LIVE team membership
            #
            #    This always happens, whether offseason or season.
            # --------------------------------------------------

            cur.execute(
                """
                INSERT INTO team_memberships (
                    player_id,
                    team_id
                )
                VALUES (%s, %s)
                RETURNING membership_id
                """,
                (
                    sign.player_id,
                    sign.team_id
                )
            )

            team_membership_id = cur.fetchone()[0]

            # --------------------------------------------------
            # 10. If team belongs to a season, also create
            #     season roster history
            # --------------------------------------------------

            roster_membership_id = None

            if season_id is not None:
                cur.execute(
                    """
                    INSERT INTO roster_memberships (
                        player_id,
                        team_id,
                        season_id
                    )
                    VALUES (%s, %s, %s)
                    RETURNING membership_id
                    """,
                    (
                        sign.player_id,
                        sign.team_id,
                        season_id
                    )
                )

                roster_membership_id = cur.fetchone()[0]

            # --------------------------------------------------
            # 11. Commit everything
            # --------------------------------------------------

            conn.commit()

    # --------------------------------------------------
    # 12. Response
    # --------------------------------------------------

    return {
        "approval_required": False,
        "team_membership_id": team_membership_id,
        "roster_membership_id": roster_membership_id,
        "team_id": team_id,
        "team_name": team_name,
        "season_id": season_id,
        "season_name": season_name,
        "league_id": league_id,
        "eligibility": (
            "TRANSFER"
            if has_played
            else "FREE_AGENT"
        ),
        "message": "Player signed successfully"
    }

@app.post("/roster/release")
def release_player(release: ReleasePlayer):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # --------------------------------
            # 1. Verify player is currently
            #    on this team's live roster
            # --------------------------------

            cur.execute(
                """
                SELECT membership_id
                FROM team_memberships
                WHERE player_id = %s
                  AND team_id = %s
                  AND left_at IS NULL
                """,
                (
                    release.player_id,
                    release.team_id
                )
            )

            live_membership = cur.fetchone()

            if not live_membership:
                raise HTTPException(
                    status_code=404,
                    detail="Player is not currently signed to this team"
                )

            # --------------------------------
            # 2. Close live team membership
            # --------------------------------

            cur.execute(
                """
                UPDATE team_memberships
                SET left_at = CURRENT_TIMESTAMP
                WHERE membership_id = %s
                """,
                (live_membership[0],)
            )

            # --------------------------------
            # 3. Close any active season
            #    roster membership too
            # --------------------------------

            cur.execute(
                """
                UPDATE roster_memberships
                SET released_at = CURRENT_TIMESTAMP
                WHERE player_id = %s
                  AND team_id = %s
                  AND released_at IS NULL
                """,
                (
                    release.player_id,
                    release.team_id
                )
            )

            conn.commit()

    return {
        "message": "Player released successfully"
    }


@app.get("/teams/discord/{discord_role_id}/roster")
def get_team_roster(discord_role_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Find team and current season
            cur.execute(
                """
                SELECT
                    teams.team_id,
                    teams.team_name,
                    seasons.season_id,
                    seasons.season_name
                FROM teams
                JOIN team_seasons
                    ON teams.team_id = team_seasons.team_id
                JOIN seasons
                    ON team_seasons.season_id = seasons.season_id
                WHERE teams.discord_role_id = %s
                  AND CURRENT_DATE BETWEEN
                      seasons.start_date AND seasons.end_date
                ORDER BY seasons.start_date DESC
                LIMIT 1
                """,
                (discord_role_id,)
            )

            team = cur.fetchone()

            if not team:
                raise HTTPException(
                    status_code=404,
                    detail="Team is not assigned to the current season"
                )

            team_id = team[0]
            team_name = team[1]
            season_id = team[2]
            season_name = team[3]

            # Active roster
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
                  AND roster_memberships.season_id = %s
                  AND roster_memberships.released_at IS NULL
                ORDER BY roster_memberships.signed_at ASC
                """,
                (
                    team_id,
                    season_id
                )
            )

            roster = cur.fetchall()

    return {
        "team_id": team_id,
        "team_name": team_name,
        "season_id": season_id,
        "season_name": season_name,
        "roster": roster
    }

@app.get("/teams/discord/{discord_role_id}")
def get_team_by_discord_role(discord_role_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    team_id,
                    team_name
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

    return {
        "team_id": team[0],
        "team_name": team[1]
    }


