import os, discord, aiohttp, re
from discord import app_commands
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Bot setup
load_dotenv()

apiURL = os.getenv("API_URL")
botToken = os.getenv("DISCORD_BOT_TOKEN")

#Role IDs
adminRoleID = int(os.getenv("ADMIN_ROLE_ID"))
coAdminRoleID = int(os.getenv("CO_ADMIN_ROLE_ID"))
staffRoleID = int(os.getenv("STAFF_ROLE_ID"))
managerRoleID = int(os.getenv("MANAGER_ROLE_ID"))
asstManagerRoleID = int(os.getenv("ASST_MANAGER_ROLE_ID"))

# Role Groups
adminRoles = [adminRoleID, coAdminRoleID]
staffRoles = [adminRoleID, coAdminRoleID, staffRoleID]
managerRoles = [managerRoleID, asstManagerRoleID]

intents = discord.Intents.default()
intents.members = True
allowed_mentions = discord.AllowedMentions(
    everyone=True,
    users=True,
    roles=True,
    replied_user=True
)

client = discord.Client(intents=intents, allowed_mentions=allowed_mentions)
tree = app_commands.CommandTree(client)

# Bot login
@client.event
async def on_ready():
    synced = await tree.sync()
    print(f"Logged in as {client.user}")
    print(f"Synced {len(synced)} commands: ")

    for command in synced:
        print(f" - {command.name}")


# Ping command
@tree.command(name = "ping", description = "Tests the bot is online.")
async def ping(
    interaction: discord.Interaction
    ):

    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
            )
        return

    await interaction.response.send_message("Pong!")


# Helper definitions

# List for help command

# Checks to see if they are allowed to manage a specific team
async def can_manage_team(
    interaction: discord.Interaction,
    team_role: discord.Role,
    session: aiohttp.ClientSession
):
    # Staff can manage any team
    if any(role.id in staffRoles for role in interaction.user.roles):
        return True

    # Otherwise, verify they manage THIS specific team
    async with session.get(
        f"{apiURL}/teams/discord/{team_role.id}/management/{interaction.user.id}"
    ) as response:

        if response.status != 200:
            return False

        data = await response.json()

        return (
            data["is_manager"]
            or data["is_assistant_manager"]
        )



# Register a player command
@tree.command(name = "register", description = "Registers a player to be eligible for signing in RML.")
async def register(
    interaction: discord.Interaction, 
    ign: str
):
    await interaction.response.defer(ephemeral=True)
    payload = {
        "discord_user_id": interaction.user.id,
        "ign": ign,
        "status": "ACTIVE"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            F"{apiURL}/players",
            json = payload
        ) as response:
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                if response.status == 200:
                    await interaction.user.edit(nick=ign)

                    await interaction.followup.send(
                        f"{interaction.user.mention} with the IGN {ign} has been registered successfully.",
                        ephemeral=True
                    )
            elif response.status == 409:
                await interaction.followup.send(
                    f"{interaction.user.mention} is already registered.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"An error occurred while registering {interaction.user.mention}.",
                    ephemeral=True
                )

# Update a player's IGN command
@tree.command(name = "update_ign", description = "Updates a player's in-game name (IGN).")
async def update_ign(
    interaction: discord.Interaction, 
    member: discord.Member, 
    ign: str
):
    await interaction.response.defer(ephemeral=True)

    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
            )
        return
    
    payload = {
        "ign": ign
    }
    async with aiohttp.ClientSession() as session:
        async with session.patch(
            F"{apiURL}/players/discord/{member.id}/ign",
            params = payload
        ) as response:
            
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                if response.status == 200:
                    await member.edit(nick=ign)

                    await interaction.followup.send(
                        f"{member.mention}'s IGN has been updated to {ign}.",
                        ephemeral=True
                    )
            elif response.status == 404:
                await interaction.followup.send(
                    f"{member.mention} is not registered.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"An error occurred while updating {member.mention}'s IGN.",
                    ephemeral=True
                )

# Update a player's status command
@tree.command(name = "update_status", description = "Updates a player's status.")
async def update_status(
    interaction: discord.Interaction, 
    member: discord.Member, 
    status: str
):
    await interaction.response.defer(ephemeral=True)

    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
            )
        return
    
    payload = {
        "status": status
    }
    async with aiohttp.ClientSession() as session:
        async with session.patch(
            F"{apiURL}/players/discord/{member.id}/status",
            params = payload
        ) as response:
            
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                await interaction.followup.send(
                    f"{member.mention}'s status has been updated to {status}.",
                    ephemeral=True
                )
            elif response.status == 404:
                await interaction.followup.send(
                    f"{member.mention} is not registered.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"An error occurred while updating {member.mention}'s status.",
                    ephemeral=True
                )


# Register a team command
@tree.command(name = "register_team", description = "Registers a team to be in the league.")
async def register_team(
    interaction: discord.Interaction, 
    team_name: str, 
    logo_url: str, 
    manager: discord.Member, 
    asst_manager: discord.Member | None = None, 
    team_acronym:str = "RML", 
    primary_color: str = "#FFFFFF"
):
    await interaction.response.defer(ephemeral=True)

    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
            )
        return

    # Color validation
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", primary_color):
        await interaction.followup.send(
            "Primary color must be a hex color like #FF0000.",
            ephemeral=True
        )
        return
    primary_color = primary_color.upper()

    async with aiohttp.ClientSession() as session:
        # Check if the manager and assistant manager are registered players
        async with session.get(
            f"{apiURL}/players/discord/{manager.id}"
        ) as response:
            if response.status != 200:
                await interaction.followup.send(
                    f"Manager {manager.mention} is not registered.",
                    ephemeral=True
                )
                return
            if response.status == 200:
                data = await response.json()
        managerPlayerID = data["player"][0]

        if asst_manager:
                async with session.get(
                    f"{apiURL}/players/discord/{asst_manager.id}"
                ) as response:
                    if response.status != 200:
                        await interaction.followup.send(
                            f"Assistant Manager {asst_manager.mention} is not registered.",
                            ephemeral=True
                        )
                        return

                    if response.status == 200:
                        data = await response.json()
                asstManagerPlayerID = data["player"][0]

        # Creates the team role in Discord
        guild = interaction.guild
        role_name = f"{team_acronym} | {team_name}"
        team_role = await guild.create_role(name = role_name, color=discord.Color(int(primary_color.lstrip("#"), 16)), mentionable = True)

        # Gives the manager and assistant manager the team role
        await manager.add_roles(team_role)
        await manager.add_roles(interaction.guild.get_role(managerRoleID))
        if asst_manager:   
            await asst_manager.add_roles(team_role)
            await asst_manager.add_roles(interaction.guild.get_role(asstManagerRoleID))

        # Commits team to the database via the API
        payload = {
            "team_name": team_name,
            "discord_role_id": team_role.id,
            "manager_id": managerPlayerID,
            "assistant_manager_id": asstManagerPlayerID if asst_manager else None,
            "logo_url": logo_url,
            "primary_color": primary_color,
            "team_acronym": team_acronym
        }
        async with session.post(
            F"{apiURL}/teams",
            json = payload
        ) as response:
            
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                await interaction.followup.send(
                    f"Team {team_name} has been registered successfully with {manager.mention} as the captain.",
                    ephemeral=True
                )
            elif response.status == 409:
                await interaction.followup.send(
                    f"Team {team_name} is already registered.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"An error occurred while registering team {team_name}.",
                    ephemeral=True
                )
        # Exception handling for role creation and assignment
        if response.status != 200:
            await team_role.delete()
            asst_manager_role = interaction.guild.get_role(asstManagerRoleID)
            manager_role = interaction.guild.get_role(managerRoleID)

            if asst_manager and asst_manager_role:
                await asst_manager.remove_roles(asst_manager_role)

            if manager_role:
                await manager.remove_roles(manager_role)

# Adds an assistant manager to a team
@tree.command(name = "add_asst_manager", description = "Adds an assistant manager to a team.")
async def add_asst_manager(
    interaction: discord.Interaction,
    team_role: discord.Role,
    asst_manager: discord.Member
):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:

        # Check permissions for THIS team
        if not await can_manage_team(
            interaction,
            team_role,
            session
        ):
            await interaction.followup.send(
                "You do not have permission to manage this team.",
                ephemeral=True
            )
            return

        # Make sure assistant manager is a registered player
        async with session.get(
            f"{apiURL}/players/discord/{asst_manager.id}"
        ) as response:

            if response.status != 200:
                await interaction.followup.send(
                    f"{asst_manager.mention} is not a registered player.",
                    ephemeral=True
                )
                return

            data = await response.json()
            asst_manager_player_id = data["player"][0]

        # Update assistant manager in database
        async with session.patch(
            f"{apiURL}/teams/discord/{team_role.id}/assistant_manager",
            params={
                "assistant_manager_id": asst_manager_player_id
            }
        ) as response:

            if response.status == 200:
                pass

            elif response.status == 404:
                await interaction.followup.send(
                    f"Team {team_role.name} is not registered.",
                    ephemeral=True
                )
                return

            elif response.status == 409:
                await interaction.followup.send(
                    f"{team_role.name} already has an assistant manager. "
                    "Remove them first before adding another.",
                    ephemeral=True
                )
                return

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    f"An error occurred while adding "
                    f"{asst_manager.mention} as assistant manager.",
                    ephemeral=True
                )
                return

    # Get actual Assistant Manager role object
    asst_manager_role = interaction.guild.get_role(asstManagerRoleID)

    if not asst_manager_role:
        await interaction.followup.send(
            "The Assistant Manager Discord role could not be found.",
            ephemeral=True
        )
        return

    # Update Discord only after database succeeds
    await asst_manager.add_roles(
        team_role,
        asst_manager_role
    )

    await interaction.followup.send(
        f"{asst_manager.mention} has been added as assistant manager "
        f"for {team_role.name}.",
        ephemeral=True
    )

# Removes an assistant manager from a team
@tree.command(name = "remove_asst_manager", description = "Removes an assistant manager from a team.")
async def remove_asst_manager(
    interaction: discord.Interaction,
    team_role: discord.Role
):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:

        # Check permissions for THIS team
        if not await can_manage_team(
            interaction,
            team_role,
            session
        ):
            await interaction.followup.send(
                "You do not have permission to manage this team.",
                ephemeral=True
            )
            return

        # Remove assistant manager in database
        async with session.patch(
            f"{apiURL}/teams/discord/{team_role.id}/assistant_manager/remove"
        ) as response:

            if response.status == 200:
                data = await response.json()
                old_asst_id = data["discord_user_id"]

            elif response.status == 404:
                await interaction.followup.send(
                    "This team does not have an assistant manager.",
                    ephemeral=True
                )
                return

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while removing the assistant manager.",
                    ephemeral=True
                )
                return

    # Find old assistant manager in Discord
    old_asst_member = interaction.guild.get_member(old_asst_id)

    # Find the generic Assistant Manager role
    asst_manager_role = interaction.guild.get_role(asstManagerRoleID)

    # Remove management role
    if old_asst_member and asst_manager_role:
        await old_asst_member.remove_roles(
            asst_manager_role
        )

    await interaction.followup.send(
        f"The assistant manager for {team_role.name} has been removed.",
        ephemeral=True
    )

# Transfers manager role to another player
@tree.command(name = "update_manager", description = "Changes the manager of a team.")
async def update_manager(
    interaction: discord.Interaction,
    team_role: discord.Role,
    new_manager: discord.Member
):
    await interaction.response.defer(ephemeral=True)
    
    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    async with aiohttp.ClientSession() as session:

        # Find new manager in player database
        async with session.get(
            f"{apiURL}/players/discord/{new_manager.id}"
        ) as response:

            if response.status != 200:
                await interaction.followup.send(
                    f"{new_manager.mention} is not a registered player.",
                    ephemeral=True
                )
                return
            if response.status == 200:
                data = await response.json()
            new_manager_player_id = data["player"][0]

        # Update manager in database
        async with session.patch(
            f"{apiURL}/teams/discord/{team_role.id}/manager",
            params={
                "manager_id": new_manager_player_id
            }
        ) as response:

            if response.status == 200:
                data = await response.json()

            elif response.status == 404:
                await interaction.followup.send(
                    "The team or manager could not be found.",
                    ephemeral=True
                )
                return

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while updating the manager.",
                    ephemeral=True
                )
                return

    # Get old manager from returned Discord ID
    old_manager_id = data["old_manager_discord_id"]
    old_manager = interaction.guild.get_member(old_manager_id)

    manager_role = interaction.guild.get_role(managerRoleID)

    # Remove Manager role from old manager
    if old_manager:
        await old_manager.remove_roles(manager_role)

    # Give new manager Manager role + team role
    await new_manager.add_roles(
        manager_role,
        team_role
    )

    await interaction.followup.send(
        f"{new_manager.mention} is now the manager of {team_role.mention}.",
        ephemeral=True
    )

# Updates a team name
@tree.command(name = "update_team_name", description = "Updates a team's name.")
async def update_team_name(
    interaction: discord.Interaction, 
    team_role: discord.Role, new_team_name: str
):
    await interaction.response.defer(ephemeral=True)

    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
            )
        return
    
    async with aiohttp.ClientSession() as session:
        # Update the team name in the database via the API
        payload = {
            "team_name": new_team_name
        }
        async with session.patch(
            F"{apiURL}/teams/discord/{team_role.id}/team_name",
            params = payload
        ) as response:
            if response.status == 200:
                data = await response.json()

            # Update the Discord role name
            acronym = team_role.name.split("|")[0].strip()
            if response.status == 200:
                new_role_name = f"{acronym} | {new_team_name}"

                await team_role.edit(name=new_role_name)

                await interaction.followup.send(
                    f"The team name has been updated to {new_team_name}.",
                    ephemeral=True
                )
            elif response.status == 404:
                await interaction.followup.send(
                    f"Team {team_role.name} is not registered.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"An error occurred while updating the team name to {new_team_name}.",
                    ephemeral=True
                )

# Updates a team's acronym
@tree.command(name = "update_team_acronym", description = "Updates a team's acronym.")
async def update_team_acronym(
    interaction: discord.Interaction, 
    team_role: discord.Role, 
    new_team_acronym: str
):
    await interaction.response.defer(ephemeral=True)
    
    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
            )
        return
    
    async with aiohttp.ClientSession() as session:
        # Update the team acronym in the database via the API
        payload = {
            "team_acronym": new_team_acronym
        }
        async with session.patch(
            F"{apiURL}/teams/discord/{team_role.id}/team_acronym",
            params = payload
        ) as response:
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                team_name = team_role.name.split("|")[1].strip()

                await team_role.edit(
                    name=f"{new_team_acronym} | {team_name}"
                )

                await interaction.followup.send(
                    f"The team acronym has been updated to {new_team_acronym}.",
                    ephemeral=True
                )
            elif response.status == 404:
                await interaction.followup.send(
                    f"Team {team_role.name} is not registered.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"An error occurred while updating the team acronym to {new_team_acronym}.",
                    ephemeral=True
                )


# Updates a team's color
@tree.command(
    name="update_team_color",
    description="Updates a team's primary color."
)
@app_commands.describe(
    team_role="The team's Discord role",
    primary_color="Hex color, for example #FF5733"
)
async def update_team_color(
    interaction: discord.Interaction,
    team_role: discord.Role,
    primary_color: str
):
    await interaction.response.defer(ephemeral=True)

    # Staff only
    if not any(
        role.id in staffRoles
        for role in interaction.user.roles
    ):
        await interaction.followup.send(
            "You do not have permission to update team colors.",
            ephemeral=True
        )
        return

    # Validate hex
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", primary_color):
        await interaction.followup.send(
            "Color must be in hex format, such as `#FF5733`.",
            ephemeral=True
        )
        return

    primary_color = primary_color.upper()

    async with aiohttp.ClientSession() as session:

        async with session.patch(
            f"{apiURL}/teams/discord/{team_role.id}/color",
            params={
                "primary_color": primary_color
            }
        ) as response:

            if response.status != 200:
                try:
                    data = await response.json()
                    detail = data.get(
                        "detail",
                        "Failed to update team color."
                    )
                except Exception:
                    detail = await response.text()

                await interaction.followup.send(
                    detail,
                    ephemeral=True
                )
                return

            data = await response.json()

    # Update Discord role color only after DB succeeds
    try:
        await team_role.edit(
            color=discord.Color(
                int(primary_color.lstrip("#"), 16)
            ),
            reason=(
                f"RML team color updated by "
                f"{interaction.user}"
            )
        )

    except discord.Forbidden:
        await interaction.followup.send(
            (
                f"The database color was updated to "
                f"`{primary_color}`, but I could not change "
                f"the Discord role color. Check my Manage Roles "
                f"permission and role hierarchy."
            ),
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Team Color Updated",
        description=(
            f"{team_role.mention}'s primary color has been "
            f"updated to `{primary_color}`."
        ),
        color=discord.Color(
            int(primary_color.lstrip("#"), 16)
        )
    )

    await interaction.followup.send(
        embed=embed,
        ephemeral=True
    )

# Set a season up command
@tree.command(name = "create_season", description = "Creates a new RML season.")
async def create_season(
    interaction: discord.Interaction,
    season_name: str,
    start_date: str,
    end_date: str,
    free_agent_start: str,
    free_agent_end: str
):
    await interaction.response.defer(ephemeral=True)
    
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    payload = {
        "season_name": season_name,
        "start_date": start_date,
        "end_date": end_date,
        "free_agent_start": free_agent_start,
        "free_agent_end": free_agent_end
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{apiURL}/seasons",
            json=payload
        ) as response:

            if response.status == 200:
                data = await response.json()

                await interaction.followup.send(
                    f"Season **{season_name}** created successfully.\n"
                    f"Season ID: `{data["season_id"]}`\n"
                    f"Season: {start_date} → {end_date}\n"
                    f"Free Agent Window: {free_agent_start} → {free_agent_end}",
                    ephemeral=True
                )

            elif response.status == 400:
                data = await response.json()

                await interaction.followup.send(
                    data["detail"],
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while creating the season.",
                    ephemeral=True
                )

# Updates a season's start and end dates
@tree.command(name= "update_season_dates", description = "Updates a season's start and end dates.")
async def update_season_dates(
    interaction: discord.Interaction,
    season_id: int,
    start_date: str,
    end_date: str
):
    await interaction.response.defer(ephemeral=True)
    
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    params = {
        "start_date": start_date,
        "end_date": end_date
    }

    async with aiohttp.ClientSession() as session:
        async with session.patch(
            f"{apiURL}/seasons/{season_id}/dates",
            params=params
        ) as response:

            if response.status == 200:
                await interaction.followup.send(
                    f"Season `{season_id}` dates updated to "
                    f"{start_date} → {end_date}.",
                    ephemeral=True
                )

            elif response.status in (400, 404):
                data = await response.json()

                await interaction.followup.send(
                    data["detail"],
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while updating the season dates.",
                    ephemeral=True
                )

# Updates a season's free agent window
@tree.command(name = "set_free_agent_week", description = "Updates the free agent window for a season.")
async def set_free_agent_week(
    interaction: discord.Interaction,
    season_id: int,
    free_agent_start: str,
    free_agent_end: str
):
    await interaction.response.defer(ephemeral=True)
    
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    params = {
        "free_agent_start": free_agent_start,
        "free_agent_end": free_agent_end
    }

    async with aiohttp.ClientSession() as session:
        async with session.patch(
            f"{apiURL}/seasons/{season_id}/free_agent",
            params=params
        ) as response:

            if response.status == 200:
                await interaction.followup.send(
                    f"Season `{season_id}` free agent window updated to "
                    f"{free_agent_start} → {free_agent_end}.",
                    ephemeral=True
                )

            elif response.status in (400, 404):
                data = await response.json()

                await interaction.followup.send(
                    data["detail"],
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while updating the free agent window.",
                    ephemeral=True
                )

# Lists the Seasons to see
@tree.command(name="list_seasons",  description="Lists all RML seasons.")
async def list_seasons(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{apiURL}/seasons"
        ) as response:

            if response.status != 200:
                await interaction.followup.send(
                    "An error occurred while retrieving seasons.",
                    ephemeral=True
                )
                return

            data = await response.json()

    seasons = data["seasons"]

    if not seasons:
        await interaction.followup.send(
            "There are currently no seasons.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="RML Seasons"
    )

    for season in seasons:
        season_id = season[0]
        season_name = season[1]
        start_date = season[2]
        end_date = season[3]
        free_agent_start = season[4]
        free_agent_end = season[5]

        embed.add_field(
            name=f"{season_name} — ID: {season_id}",
            value=(
                f"**Season:** {start_date} → {end_date}\n"
                f"**Free Agent Week:** {free_agent_start} → {free_agent_end}"
            ),
            inline=False
        )

    await interaction.followup.send(
        embed=embed,
        ephemeral=True
    )

# Sets a team's league
@tree.command(name = "set_team_league", description = "Assigns a team to a league for that league's season.")
async def set_team_league(
    interaction: discord.Interaction,
    team_role: discord.Role,
    league_id: int
):
    await interaction.response.defer(ephemeral=True)
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    async with aiohttp.ClientSession() as session:
        async with session.patch(
            f"{apiURL}/teams/discord/{team_role.id}/league",
            params={"league_id": league_id}
        ) as response:

            if response.status == 200:
                data = await response.json()

                await interaction.followup.send(
                    f"{team_role.name} has been assigned to "
                    f"{data['league_name']} for {data['season_name']}.",
                    ephemeral=True
                )

            elif response.status == 404:
                data = await response.json()

                await interaction.followup.send(
                    data.get("detail", "Team or league not found."),
                    ephemeral=True
                )

            elif response.status == 409:
                data = await response.json()

                await interaction.followup.send(
                    data.get(
                        "detail",
                        "This team is already assigned for that season."
                    ),
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while assigning the team to a league.",
                    ephemeral=True
                )

# Updates a team's league if assigned incorrectly
@tree.command(name = "update_team_league", description = "Moves a team to a different league within the same season.")
async def update_team_league(
    interaction: discord.Interaction,
    team_role: discord.Role,
    new_league_id: int
):
    await interaction.response.defer(ephemeral=True)
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    async with aiohttp.ClientSession() as session:
        async with session.patch(
            f"{apiURL}/teams/discord/{team_role.id}/league/update",
            params={"league_id": new_league_id}
        ) as response:

            if response.status == 200:
                data = await response.json()

                await interaction.followup.send(
                    f"{team_role.name} has been moved from "
                    f"{data['old_league_name']} to "
                    f"{data['new_league_name']} for "
                    f"{data['season_name']}.",
                    ephemeral=True
                )

            elif response.status == 404:
                data = await response.json()

                await interaction.followup.send(
                    data.get(
                        "detail",
                        "Team, league, or season assignment not found."
                    ),
                    ephemeral=True
                )

            elif response.status == 409:
                data = await response.json()

                await interaction.followup.send(
                    data.get(
                        "detail",
                        "The team is already assigned to that league."
                    ),
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while updating the team's league.",
                    ephemeral=True
                )

# Shows the current season's league IDs
@tree.command(name = "view_leagues", description = "Displays all leagues for the current season.")
async def view_leagues(
    interaction: discord.Interaction
):
    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{apiURL}/leagues/current"
        ) as response:

            if response.status == 404:
                await interaction.followup.send(
                    "There is currently no active season.",
                    ephemeral=True
                )
                return

            if response.status != 200:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while retrieving the leagues.",
                    ephemeral=True
                )
                return

            data = await response.json()

    season_name = data["season_name"]
    leagues = data["leagues"]

    embed = discord.Embed(
        title=f"{season_name} Leagues",
        description="Current league structure for this season."
    )

    if not leagues:
        embed.add_field(
            name="No Leagues",
            value="No leagues have been created for this season yet.",
            inline=False
        )

    else:
        for league in leagues:
            league_id = league[0]
            league_name = league[1]

            embed.add_field(
                name=league_name,
                value=f"League ID: `{league_id}`",
                inline=False
            )

    await interaction.followup.send(
        embed=embed,
        ephemeral=True
    )

# Creates a league
@tree.command(name = "create_league", description = "Creates a league for a specific season.")
async def create_league(
    interaction: discord.Interaction,
    league_name: str,
    season_id: int
):
    await interaction.response.defer(ephemeral=True)
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.followup.send(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    payload = {
        "league_name": league_name,
        "season_id": season_id
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{apiURL}/leagues",
            json=payload
        ) as response:

            if response.status == 200:
                data = await response.json()

                await interaction.followup.send(
                    f"League **{league_name}** was created successfully "
                    f"for season `{season_id}`.\n"
                    f"League ID: `{data['league_id']}`",
                    ephemeral=True
                )

            elif response.status == 404:
                data = await response.json()

                await interaction.followup.send(
                    data.get("detail", "Season not found."),
                    ephemeral=True
                )

            elif response.status == 409:
                data = await response.json()

                await interaction.followup.send(
                    data.get(
                        "detail",
                        "That league already exists for this season."
                    ),
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)
                await interaction.followup.send(
                    "An error occurred while creating the league.",
                    ephemeral=True
                )


#Scheduling
def parse_eastern_time(time_string: str):
    try:
        naive_time = datetime.strptime(
            time_string,
            "%Y-%m-%d %H:%M"
        )

        eastern = ZoneInfo("America/New_York")

        return naive_time.replace(tzinfo=eastern)

    except ValueError:
        return None

class SuggestTimeModal(discord.ui.Modal):
    def __init__(
        self,
        match_id: int,
        scheduling_view
    ):
        super().__init__(
            title="Suggest Another Match Time"
        )

        self.match_id = match_id
        self.scheduling_view = scheduling_view

        self.time_input = discord.ui.TextInput(
            label="New Time (ET)",
            placeholder="YYYY-MM-DD HH:MM — Example: 2026-09-25 20:00",
            required=True
        )

        self.add_item(self.time_input)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        match_time = parse_eastern_time(
            self.time_input.value
        )

        if not match_time:
            await interaction.response.send_message(
                "Invalid time format. Use `YYYY-MM-DD HH:MM`.",
                ephemeral=True
            )
            return

        payload = {
            "scheduled_at": match_time.isoformat()
        }

        async with aiohttp.ClientSession() as session:
            async with session.patch(
                f"{apiURL}/matches/{self.match_id}/time",
                json=payload
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    print(error_text)

                    await interaction.response.send_message(
                        "An error occurred while suggesting the new time.",
                        ephemeral=True
                    )
                    return

        # Reset approval states in the View
        self.scheduling_view.home_approved = False
        self.scheduling_view.away_approved = False
        self.scheduling_view.match_time = match_time

        self.scheduling_view.update_embed()

        await interaction.response.edit_message(
            embed=self.scheduling_view.embed,
            view=self.scheduling_view
        )

class MatchSchedulingView(discord.ui.View):
    def __init__(
        self,
        match_id: int,
        home_role: discord.Role,
        away_role: discord.Role,
        match_time: datetime
    ):
        super().__init__(timeout=None)

        self.match_id = match_id

        self.home_role = home_role
        self.away_role = away_role

        self.match_time = match_time

        self.home_approved = False
        self.away_approved = False

        self.embed = None


    def update_embed(self):

        home_status = (
            "✅ Agreed"
            if self.home_approved
            else "⏳ Waiting"
        )

        away_status = (
            "✅ Agreed"
            if self.away_approved
            else "⏳ Waiting"
        )

        self.embed = discord.Embed(
            title="Match Scheduling Proposal",
            description=(
                f"{self.home_role.mention} **vs** "
                f"{self.away_role.mention}"
            )
        )

        self.embed.add_field(
            name="Proposed Time",
            value=self.match_time.strftime(
                "%Y-%m-%d %I:%M %p ET"
            ),
            inline=False
        )

        self.embed.add_field(
            name=self.home_role.name,
            value=home_status,
            inline=True
        )

        self.embed.add_field(
            name=self.away_role.name,
            value=away_status,
            inline=True
        )

        self.embed.set_footer(
            text=f"Match ID: {self.match_id}"
        )

    @discord.ui.button(
        label="Agree",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def agree(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        async with aiohttp.ClientSession() as session:

            # Does user manage home team?
            home_permission = await can_manage_team(
                interaction,
                self.home_role,
                session
            )

            # Does user manage away team?
            away_permission = await can_manage_team(
                interaction,
                self.away_role,
                session
            )

            if not home_permission and not away_permission:
                await interaction.response.send_message(
                    "You do not manage either team in this match.",
                    ephemeral=True
                )
                return

            # Staff could theoretically pass both checks because
            # can_manage_team lets staff manage everything.
            # Prefer their actual team role if possible.
            if (
                self.home_role in interaction.user.roles
                and home_permission
            ):
                side = "home"

            elif (
                self.away_role in interaction.user.roles
                and away_permission
            ):
                side = "away"

            elif home_permission and not away_permission:
                side = "home"

            elif away_permission and not home_permission:
                side = "away"

            else:
                await interaction.response.send_message(
                    "Staff managing this proposal should use an account associated "
                    "with one of the teams.",
                    ephemeral=True
                )
                return

            async with session.patch(
                f"{apiURL}/matches/{self.match_id}/approve/{side}"
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    print(error_text)

                    await interaction.response.send_message(
                        "An error occurred while approving the match.",
                        ephemeral=True
                    )
                    return

                data = await response.json()

        self.home_approved = data["home_approved"]
        self.away_approved = data["away_approved"]

        self.update_embed()

        if data["scheduled"]:
            self.embed.title = "✅ Match Scheduled"

            self.embed.add_field(
                name="Status",
                value="Both teams have agreed to the scheduled time.",
                inline=False
            )

            # Disable buttons
            for item in self.children:
                item.disabled = True

        await interaction.response.edit_message(
            embed=self.embed,
            view=self
        )

    @discord.ui.button(
        label="Suggest Different Time",
        style=discord.ButtonStyle.danger,
        emoji="❌"
    )
    async def disagree(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        async with aiohttp.ClientSession() as session:

            home_permission = await can_manage_team(
                interaction,
                self.home_role,
                session
            )

            away_permission = await can_manage_team(
                interaction,
                self.away_role,
                session
            )

            if not home_permission and not away_permission:
                await interaction.response.send_message(
                    "You do not manage either team in this match.",
                    ephemeral=True
                )
                return

        await interaction.response.send_modal(
            SuggestTimeModal(
                self.match_id,
                self
            )
        )

@tree.command(
    name="schedule_match",
    description="Proposes a match time between two teams."
)
@app_commands.describe(
    home_team="Select the home team's Discord role.",
    away_team="Select the away team's Discord role.",
    time_et="YYYY-MM-DD HH:MM — Example: 2026-09-25 20:00"
)
async def schedule_match(
    interaction: discord.Interaction,
    home_team: discord.Role,
    away_team: discord.Role,
    time_et: str
):

    # Cannot schedule team against itself
    if home_team.id == away_team.id:
        await interaction.response.send_message(
            "A team cannot be scheduled against itself.",
            ephemeral=True
        )
        return

    match_time = parse_eastern_time(time_et)

    if not match_time:
        await interaction.response.send_message(
            "Invalid time format.\n"
            "Use `YYYY-MM-DD HH:MM`, for example `2026-09-25 20:00`.",
            ephemeral=True
        )
        return

    async with aiohttp.ClientSession() as session:

        # User must manage at least one participating team,
        # or be staff.
        home_permission = await can_manage_team(
            interaction,
            home_team,
            session
        )

        away_permission = await can_manage_team(
            interaction,
            away_team,
            session
        )

        if not home_permission and not away_permission:
            await interaction.response.send_message(
                "You do not manage either selected team.",
                ephemeral=True
            )
            return

        payload = {
            "home_discord_role_id": home_team.id,
            "away_discord_role_id": away_team.id,
            "scheduled_at": match_time.isoformat()
        }

        async with session.post(
            f"{apiURL}/matches/propose",
            json=payload
        ) as response:

            if response.status != 200:
                try:
                    data = await response.json()
                    detail = data.get(
                        "detail",
                        "An error occurred while creating the match proposal."
                    )
                except Exception:
                    detail = await response.text()

                await interaction.response.send_message(
                    detail,
                    ephemeral=True
                )
                return

            data = await response.json()

    match_id = data["match_id"]

    view = MatchSchedulingView(
        match_id=match_id,
        home_role=home_team,
        away_role=away_team,
        match_time=match_time
    )

    view.update_embed()

    await interaction.response.send_message(
        content=(
            f"{home_team.mention} {away_team.mention}\n"
            "Managers: please review the proposed match time."
        ),
        embed=view.embed,
        view=view
    )




# Signings
class LateSigningApprovalView(discord.ui.View):
    def __init__(
        self,
        player: discord.Member,
        signing_team_role: discord.Role,
        opponent_team_role: discord.Role,
        player_id: int,
        team_id: int,
        eligibility: str
    ):
        super().__init__(timeout=600)

        self.player = player
        self.signing_team_role = signing_team_role
        self.opponent_team_role = opponent_team_role

        self.player_id = player_id
        self.team_id = team_id

        self.eligibility = eligibility


    @discord.ui.button(
        label="Approve Signing",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        async with aiohttp.ClientSession() as session:

            # Must manage the OPPONENT team.
            # Staff also pass can_manage_team().
            if not await can_manage_team(
                interaction,
                self.opponent_team_role,
                session
            ):
                await interaction.response.send_message(
                    "Only the opposing team's Manager or Assistant Manager "
                    "can approve this late signing.",
                    ephemeral=True
                )
                return

            payload = {
                "player_id": self.player_id,
                "team_id": self.team_id,
                "approved": True
            }

            async with session.post(
                f"{apiURL}/roster/sign",
                json=payload
            ) as response:

                if response.status != 200:
                    try:
                        data = await response.json()
                        detail = data.get(
                            "detail",
                            "Signing failed."
                        )
                    except Exception:
                        detail = await response.text()

                    await interaction.response.send_message(
                        detail,
                        ephemeral=True
                    )
                    return

                data = await response.json()

        # Database succeeded, now update Discord
        try:
            await self.player.add_roles(
                self.signing_team_role
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "The player was signed in the database, but I could not "
                "assign the Discord team role.",
                ephemeral=True
            )
            return

        # Disable button
        for item in self.children:
            item.disabled = True

        if self.eligibility == "TRANSFER":
            eligibility_text = "🟡 **Transfer — Approved**"
        else:
            eligibility_text = "🟢 **Free Agent — Approved**"

        embed = discord.Embed(
            title="✅ SIGNING",
            description=(
                f"{self.player.mention} has officially signed with "
                f"{self.signing_team_role.mention}."
            )
        )

        embed.add_field(
            name="Team",
            value=self.signing_team_role.mention,
            inline=True
        )

        embed.add_field(
            name="Player",
            value=self.player.mention,
            inline=True
        )

        embed.add_field(
            name="Eligibility",
            value=eligibility_text,
            inline=False
        )

        embed.add_field(
            name="Late Signing Approved By",
            value=interaction.user.mention,
            inline=False
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=self
        )

@tree.command(
    name="sign",
    description="Signs a registered player to a team."
)
async def sign(
    interaction: discord.Interaction,
    team_role: discord.Role,
    player: discord.Member
):

    async with aiohttp.ClientSession() as session:

        # --------------------------------
        # Permission check
        # --------------------------------

        if not await can_manage_team(
            interaction,
            team_role,
            session
        ):
            await interaction.response.send_message(
                "You do not have permission to sign players to this team.",
                ephemeral=True
            )
            return

        # --------------------------------
        # Find registered player
        # --------------------------------

        async with session.get(
            f"{apiURL}/players/discord/{player.id}"
        ) as response:

            if response.status != 200:
                await interaction.response.send_message(
                    f"{player.mention} is not registered.",
                    ephemeral=True
                )
                return

            player_data = await response.json()

        player_id = player_data["player"][0]

        # --------------------------------
        # Find team
        # --------------------------------

        async with session.get(
            f"{apiURL}/teams/discord/{team_role.id}"
        ) as response:

            if response.status != 200:
                await interaction.response.send_message(
                    "Team could not be found.",
                    ephemeral=True
                )
                return

            team_data = await response.json()

        team_id = team_data["team_id"]
        # --------------------------------
        # Attempt signing
        # --------------------------------

        payload = {
            "player_id": player_id,
            "team_id": team_id,
            "approved": False
        }

        async with session.post(
            f"{apiURL}/roster/sign",
            json=payload
        ) as response:

            # --------------------------------
            # Transfer locked
            # --------------------------------

            if response.status == 403:
                try:
                    data = await response.json()
                    detail = data.get("detail")
                except Exception:
                    detail = None

                if detail == "TRANSFER_LOCKED":
                    embed = discord.Embed(
                        title="🔒 SIGNING — TRANSFER LOCKED"
                    )

                    embed.add_field(
                        name="Team",
                        value=team_role.mention,
                        inline=True
                    )

                    embed.add_field(
                        name="Player",
                        value=player.mention,
                        inline=True
                    )

                    embed.add_field(
                        name="Eligibility",
                        value=(
                            "🔴 **Transfer Locked**\n"
                            "This player has already participated this season "
                            "and cannot change teams until Free Agent Week."
                        ),
                        inline=False
                    )

                    await interaction.response.send_message(
                        embed=embed
                    )
                    return

                await interaction.response.send_message(
                    detail or "This player is not eligible to sign.",
                    ephemeral=True
                )
                return

            # --------------------------------
            # Other API errors
            # --------------------------------

            if response.status != 200:
                try:
                    data = await response.json()
                    detail = data.get(
                        "detail",
                        "An error occurred while signing the player."
                    )
                except Exception:
                    detail = await response.text()

                await interaction.response.send_message(
                    detail,
                    ephemeral=True
                )
                return

            data = await response.json()

    # --------------------------------
    # Late signing approval required
    # --------------------------------

    if data.get("approval_required"):

        opponent_role_id = data.get(
            "opponent_discord_role_id"
        )

        if not opponent_role_id:
            await interaction.response.send_message(
                "The API could not determine the opposing team.",
                ephemeral=True
            )
            return

        opponent_role = interaction.guild.get_role(
            opponent_role_id
        )

        if not opponent_role:
            await interaction.response.send_message(
                "The opponent team's Discord role could not be found.",
                ephemeral=True
            )
            return

        eligibility = data.get(
            "eligibility",
            "FREE_AGENT"
        )

        view = LateSigningApprovalView(
            player=player,
            signing_team_role=team_role,
            opponent_team_role=opponent_role,
            player_id=player_id,
            team_id=team_id,
            eligibility=eligibility
        )

        embed = discord.Embed(
            title="⏳ SIGNING — APPROVAL REQUIRED",
            description=(
                f"{player.mention} is being signed to "
                f"{team_role.mention}, but the team has a scheduled "
                f"match within the next 8 hours."
            )
        )

        embed.add_field(
            name="Team",
            value=team_role.mention,
            inline=True
        )

        embed.add_field(
            name="Player",
            value=player.mention,
            inline=True
        )

        embed.add_field(
            name="Opponent",
            value=opponent_role.mention,
            inline=True
        )

        embed.add_field(
            name="Status",
            value=(
                "🟡 **Late Signing**\n"
                "The opposing team's Manager or Assistant Manager "
                "must approve this signing."
            ),
            inline=False
        )

        embed.set_footer(
            text=f"Match ID: {data['match_id']}"
        )

        # Public message
        await interaction.response.send_message(
            content=(
                f"{opponent_role.mention} — approval is required "
                f"for a signing by {team_role.mention}."
            ),
            embed=embed,
            view=view
        )

    # --------------------------------
    # Normal successful signing
    # --------------------------------

    try:
        await player.add_roles(
            team_role
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "The player was signed in the database, but I could not "
            "assign their Discord team role.",
            ephemeral=True
        )
        return

    eligibility = data.get(
        "eligibility",
        "FREE_AGENT"
    )

    if eligibility == "TRANSFER":
        eligibility_text = "🟡 **Transfer**"
    else:
        eligibility_text = "🟢 **Signed**"

    embed = discord.Embed(
        title="📝 SIGNING",
        description=(
            f"{player.mention} has officially signed with "
            f"{team_role.mention}."
        )
    )

    embed.add_field(
        name="Team",
        value=team_role.mention,
        inline=True
    )

    embed.add_field(
        name="Player",
        value=player.mention,
        inline=True
    )

    embed.add_field(
        name="Eligibility",
        value=eligibility_text,
        inline=False
    )

    # Public
    await interaction.response.send_message(
        embed=embed
    )


@tree.command(
    name="release",
    description="Releases a player from a team."
)
async def release(
    interaction: discord.Interaction,
    team_role: discord.Role,
    player: discord.Member
):

    async with aiohttp.ClientSession() as session:

        # --------------------------------
        # Permission check
        # --------------------------------

        if not await can_manage_team(
            interaction,
            team_role,
            session
        ):
            await interaction.response.send_message(
                "You do not have permission to release players from this team.",
                ephemeral=True
            )
            return

        # --------------------------------
        # Find player
        # --------------------------------

        async with session.get(
            f"{apiURL}/players/discord/{player.id}"
        ) as response:

            if response.status != 200:
                await interaction.response.send_message(
                    f"{player.mention} is not registered.",
                    ephemeral=True
                )
                return

            player_data = await response.json()

        player_id = player_data["player"][0]

        # --------------------------------
        # Find team
        # --------------------------------

        async with session.get(
            f"{apiURL}/teams/discord/{team_role.id}"
        ) as response:

            if response.status != 200:
                await interaction.response.send_message(
                    "Team could not be found.",
                    ephemeral=True
                )
                return

            team_data = await response.json()

        team_id = team_data["team_id"]

        # --------------------------------
        # Release
        # --------------------------------

        payload = {
            "player_id": player_id,
            "team_id": team_id,
        }

        async with session.post(
            f"{apiURL}/roster/release",
            json=payload
        ) as response:

            if response.status == 404:
                data = await response.json()

                await interaction.response.send_message(
                    data.get(
                        "detail",
                        "Player is not currently signed to this team."
                    ),
                    ephemeral=True
                )
                return

            if response.status != 200:
                error_text = await response.text()
                print(error_text)

                await interaction.response.send_message(
                    "An error occurred while releasing the player.",
                    ephemeral=True
                )
                return

    # --------------------------------
    # Remove Discord role
    # --------------------------------

    try:
        await player.remove_roles(
            team_role
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "The player was released in the database, but I could not "
            "remove their Discord team role.",
            ephemeral=True
        )
        return

    # --------------------------------
    # Public release announcement
    # --------------------------------

    embed = discord.Embed(
        title="📤 RELEASE",
        description=(
            f"{player.mention} has been released from "
            f"{team_role.mention}."
        )
    )

    embed.add_field(
        name="Team",
        value=team_role.mention,
        inline=True
    )

    embed.add_field(
        name="Player",
        value=player.mention,
        inline=True
    )

    embed.add_field(
        name="Status",
        value="⚪ **Free Agent**",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


@tree.command(
    name="view_roster",
    description="Displays a team's current roster."
)
async def view_roster(
    interaction: discord.Interaction,
    team_role: discord.Role
):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:

        async with session.get(
            f"{apiURL}/teams/discord/{team_role.id}/roster"
        ) as response:

            if response.status == 404:
                await interaction.followup.send(
                    "This team does not have a roster for the current season.",
                    ephemeral=True
                )
                return

            if response.status != 200:
                error_text = await response.text()
                print(error_text)

                await interaction.followup.send(
                    "An error occurred while retrieving the roster.",
                    ephemeral=True
                )
                return

            data = await response.json()

    roster = data["roster"]

    embed = discord.Embed(
        title=f"📋 {data['team_name']} Roster",
        description=data["season_name"]
    )

    if not roster:
        embed.add_field(
            name="Players",
            value="No players are currently signed.",
            inline=False
        )

    else:
        roster_text = ""

        for roster_player in roster:
            ign = roster_player[1]
            discord_user_id = roster_player[2]

            roster_text += (
                f"• <@{discord_user_id}> — **{ign}**\n"
            )

        embed.add_field(
            name=f"Players ({len(roster)})",
            value=roster_text,
            inline=False
        )

    await interaction.followup.send(
        embed=embed
    )









# Run the bot
client.run(botToken)