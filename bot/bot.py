import os, discord, aiohttp, re
from discord import app_commands
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

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Bot login
@client.event
async def on_ready():
    synced = await tree.sync()
    print(f'Logged in as {client.user}')
    print(f'Synced {len(synced)} commands: ')

    for command in synced:
        print(f' - {command.name}')


# Ping command
@tree.command(name = 'ping', description = 'Tests the bot is online.')
async def ping(
    interaction: discord.Interaction
    ):

    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.response.send_message(
            'You do not have permission to use this command.',
            ephemeral=True
            )
        return

    await interaction.response.send_message('Pong!')


# Helper definitions

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
@tree.command(name = 'register', description = 'Registers a player to be eligible for signing in RML.')
async def register(
    interaction: discord.Interaction, 
    ign: str):
    payload = {
        'discord_user_id': interaction.user.id,
        'ign': ign,
        'status': 'ACTIVE'
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            F"{apiURL}/players",
            json = payload
        ) as response:
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                await interaction.response.send_message(
                    f"{interaction.user.mention} with the IGN {ign} has been registered successfully.",
                    ephemeral=True
                )
            elif response.status == 409:
                await interaction.response.send_message(
                    f"{interaction.user.mention} is already registered.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"An error occurred while registering {interaction.user.mention}.",
                    ephemeral=True
                )

# Update a player's IGN command
@tree.command(name = 'update_ign', description = 'Updates a player\'s in-game name (IGN).')
async def update_ign(
    interaction: discord.Interaction, 
    member: discord.Member, 
    ign: str):
    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.response.send_message(
            'You do not have permission to use this command.',
            ephemeral=True
            )
        return
    
    payload = {
        'ign': ign
    }
    async with aiohttp.ClientSession() as session:
        async with session.patch(
            F"{apiURL}/players/discord/{member.id}/ign",
            params = payload
        ) as response:
            
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                await interaction.response.send_message(
                    f"{member.mention}'s IGN has been updated to {ign}.",
                    ephemeral=True
                )
            elif response.status == 404:
                await interaction.response.send_message(
                    f"{member.mention} is not registered.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"An error occurred while updating {member.mention}'s IGN.",
                    ephemeral=True
                )

# Update a player's status command
@tree.command(name = 'update_status', description = 'Updates a player\'s status.')
async def update_status(
    interaction: discord.Interaction, 
    member: discord.Member, 
    status: str):
    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.response.send_message(
            'You do not have permission to use this command.',
            ephemeral=True
            )
        return
    
    payload = {
        'status': status
    }
    async with aiohttp.ClientSession() as session:
        async with session.patch(
            F"{apiURL}/players/discord/{member.id}/status",
            params = payload
        ) as response:
            
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                await interaction.response.send_message(
                    f"{member.mention}'s status has been updated to {status}.",
                    ephemeral=True
                )
            elif response.status == 404:
                await interaction.response.send_message(
                    f"{member.mention} is not registered.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"An error occurred while updating {member.mention}'s status.",
                    ephemeral=True
                )


# Register a team command
@tree.command(name = 'register_team', description = 'Registers a team to be in the league.')
async def register_team(
    interaction: discord.Interaction, 
    team_name: str, 
    logo_url: str, 
    manager: discord.Member, 
    asst_manager: discord.Member | None = None, 
    team_acronym:str = "RML", 
    primary_color: str = "#FFFFFF"):
    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.response.send_message(
            'You do not have permission to use this command.',
            ephemeral=True
            )
        return

    # Color validation
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", primary_color):
        await interaction.response.send_message(
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
                await interaction.response.send_message(
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
                        await interaction.response.send_message(
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
        team_role = await guild.create_role(name = role_name, color=discord.Color(int(primary_color.lstrip('#'), 16)))

        # Gives the manager and assistant manager the team role
        await manager.add_roles(team_role)
        await manager.add_roles(interaction.guild.get_role(managerRoleID))
        if asst_manager:   
            await asst_manager.add_roles(team_role)
            await asst_manager.add_roles(interaction.guild.get_role(asstManagerRoleID))

        # Commits team to the database via the API
        payload = {
            'team_name': team_name,
            'discord_role_id': team_role.id,
            'manager_id': managerPlayerID,
            'assistant_manager_id': asstManagerPlayerID if asst_manager else None,
            'logo_url': logo_url,
            'primary_color': primary_color,
            'team_acronym': team_acronym
        }
        async with session.post(
            F"{apiURL}/teams",
            json = payload
        ) as response:
            
            if response.status == 200:
                data = await response.json()

            if response.status == 200:
                await interaction.response.send_message(
                    f"Team {team_name} has been registered successfully with {manager.mention} as the captain.",
                    ephemeral=True
                )
            elif response.status == 409:
                await interaction.response.send_message(
                    f"Team {team_name} is already registered.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
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
@tree.command(name='add_asst_manager', description='Adds an assistant manager to a team.')
async def add_asst_manager(
    interaction: discord.Interaction,
    team_role: discord.Role,
    asst_manager: discord.Member
):

    async with aiohttp.ClientSession() as session:

        # Check permissions for THIS team
        if not await can_manage_team(
            interaction,
            team_role,
            session
        ):
            await interaction.response.send_message(
                'You do not have permission to manage this team.',
                ephemeral=True
            )
            return

        # Make sure assistant manager is a registered player
        async with session.get(
            f"{apiURL}/players/discord/{asst_manager.id}"
        ) as response:

            if response.status != 200:
                await interaction.response.send_message(
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
                await interaction.response.send_message(
                    f"Team {team_role.name} is not registered.",
                    ephemeral=True
                )
                return

            elif response.status == 409:
                await interaction.response.send_message(
                    f"{team_role.name} already has an assistant manager. "
                    "Remove them first before adding another.",
                    ephemeral=True
                )
                return

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.response.send_message(
                    f"An error occurred while adding "
                    f"{asst_manager.mention} as assistant manager.",
                    ephemeral=True
                )
                return

    # Get actual Assistant Manager role object
    asst_manager_role = interaction.guild.get_role(asstManagerRoleID)

    if not asst_manager_role:
        await interaction.response.send_message(
            "The Assistant Manager Discord role could not be found.",
            ephemeral=True
        )
        return

    # Update Discord only after database succeeds
    await asst_manager.add_roles(
        team_role,
        asst_manager_role
    )

    await interaction.response.send_message(
        f"{asst_manager.mention} has been added as assistant manager "
        f"for {team_role.name}.",
        ephemeral=True
    )

# Removes an assistant manager from a team
@tree.command(name='remove_asst_manager', description='Removes an assistant manager from a team.')
async def remove_asst_manager(
    interaction: discord.Interaction,
    team_role: discord.Role
):

    async with aiohttp.ClientSession() as session:

        # Check permissions for THIS team
        if not await can_manage_team(
            interaction,
            team_role,
            session
        ):
            await interaction.response.send_message(
                'You do not have permission to manage this team.',
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
                await interaction.response.send_message(
                    "This team does not have an assistant manager.",
                    ephemeral=True
                )
                return

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.response.send_message(
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

    await interaction.response.send_message(
        f"The assistant manager for {team_role.name} has been removed.",
        ephemeral=True
    )

# Transfers manager role to another player
@tree.command(name="update_manager", description="Changes the manager of a team.")
async def update_manager(
    interaction: discord.Interaction,
    team_role: discord.Role,
    new_manager: discord.Member
):
    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.response.send_message(
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
                await interaction.response.send_message(
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
                await interaction.response.send_message(
                    "The team or manager could not be found.",
                    ephemeral=True
                )
                return

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.response.send_message(
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

    await interaction.response.send_message(
        f"{new_manager.mention} is now the manager of {team_role.mention}.",
        ephemeral=True
    )

# Updates a team name
@tree.command(name = 'update_team_name', description = 'Updates a team\'s name.')
async def update_team_name(
    interaction: discord.Interaction, 
    team_role: discord.Role, new_team_name: str):
    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.response.send_message(
            'You do not have permission to use this command.',
            ephemeral=True
            )
        return
    
    async with aiohttp.ClientSession() as session:
        # Update the team name in the database via the API
        payload = {
            'team_name': new_team_name
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

                await interaction.response.send_message(
                    f"The team name has been updated to {new_team_name}.",
                    ephemeral=True
                )
            elif response.status == 404:
                await interaction.response.send_message(
                    f"Team {team_role.name} is not registered.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"An error occurred while updating the team name to {new_team_name}.",
                    ephemeral=True
                )

# Updates a team's acronym
@tree.command(name = 'update_team_acronym', description = 'Updates a team\'s acronym.')
async def update_team_acronym(
    interaction: discord.Interaction, 
    team_role: discord.Role, 
    new_team_acronym: str):
    if not any(role.id in staffRoles for role in interaction.user.roles):
        await interaction.response.send_message(
            'You do not have permission to use this command.',
            ephemeral=True
            )
        return
    
    async with aiohttp.ClientSession() as session:
        # Update the team acronym in the database via the API
        payload = {
            'team_acronym': new_team_acronym
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

                await interaction.response.send_message(
                    f"The team acronym has been updated to {new_team_acronym}.",
                    ephemeral=True
                )
            elif response.status == 404:
                await interaction.response.send_message(
                    f"Team {team_role.name} is not registered.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"An error occurred while updating the team acronym to {new_team_acronym}.",
                    ephemeral=True
                )


# Set a season up command
@tree.command(name="create_season", description="Creates a new RML season.")
async def create_season(
    interaction: discord.Interaction,
    season_name: str,
    start_date: str,
    end_date: str,
    free_agent_start: str,
    free_agent_end: str
):
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.response.send_message(
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

                await interaction.response.send_message(
                    f"Season **{season_name}** created successfully.\n"
                    f"Season ID: `{data['season_id']}`\n"
                    f"Season: {start_date} → {end_date}\n"
                    f"Free Agent Window: {free_agent_start} → {free_agent_end}",
                    ephemeral=True
                )

            elif response.status == 400:
                data = await response.json()

                await interaction.response.send_message(
                    data["detail"],
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.response.send_message(
                    "An error occurred while creating the season.",
                    ephemeral=True
                )

# Updates a season's start and end dates
@tree.command(name="update_season_dates", description="Updates a season's start and end dates.")
async def update_season_dates(
    interaction: discord.Interaction,
    season_id: int,
    start_date: str,
    end_date: str
):
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.response.send_message(
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
                await interaction.response.send_message(
                    f"Season `{season_id}` dates updated to "
                    f"{start_date} → {end_date}.",
                    ephemeral=True
                )

            elif response.status in (400, 404):
                data = await response.json()

                await interaction.response.send_message(
                    data["detail"],
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.response.send_message(
                    "An error occurred while updating the season dates.",
                    ephemeral=True
                )

# Updates a season's free agent window
@tree.command(name="set_free_agent_week", description="Updates the free agent window for a season.")
async def set_free_agent_week(
    interaction: discord.Interaction,
    season_id: int,
    free_agent_start: str,
    free_agent_end: str
):
    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.response.send_message(
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
                await interaction.response.send_message(
                    f"Season `{season_id}` free agent window updated to "
                    f"{free_agent_start} → {free_agent_end}.",
                    ephemeral=True
                )

            elif response.status in (400, 404):
                data = await response.json()

                await interaction.response.send_message(
                    data["detail"],
                    ephemeral=True
                )

            else:
                error_text = await response.text()
                print(error_text)

                await interaction.response.send_message(
                    "An error occurred while updating the free agent window.",
                    ephemeral=True
                )

# Lists the Seasons to see
@tree.command(name="list_seasons",  description="Lists all RML seasons.")
async def list_seasons(interaction: discord.Interaction):

    if not any(role.id in adminRoles for role in interaction.user.roles):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{apiURL}/seasons"
        ) as response:

            if response.status != 200:
                await interaction.response.send_message(
                    "An error occurred while retrieving seasons.",
                    ephemeral=True
                )
                return

            data = await response.json()

    seasons = data["seasons"]

    if not seasons:
        await interaction.response.send_message(
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

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# Run the bot
client.run(botToken)