import discord
import json
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("SECRET_HUEUE")
intents = discord.Intents.all()
client = discord.Client(intents=intents)

POINTS_UPPER_LIMIT = 1000
POINTS_LOWER_LIMIT = 0
POINTS_ADDING_RATE = 1
POINTS_SUBTRACTING_RATE = 0.02
REQUIRED_POINTS = 600

# Function that recieves a guild object and registers it in the JSON file if it was not already there
def parsing_new_guild(guild):
    with open("data.json", "r") as f:
        json_content = json.load(f)
    if str(guild.id) not in json_content.keys():
        members_dictionary = {}
        for member in guild.members:
            if member.bot == False:
                members_dictionary[member.id] = 0
        json_content[guild.id] = members_dictionary
        with open("data.json", "w") as f:
            json.dump(json_content, f)

# Function that recieves a user's voice information to detetmine whether he is being active or not
def applicable_for_point(member_voice):
    if member_voice.afk or member_voice.self_mute or member_voice.self_deaf or member_voice.mute or member_voice.deaf:
        return False
    return True

# Function that assigns and removes the "Active" rank, primarily used in point_assigner()
async def assign_ranks():
    global REQUIRED_POINTS
    with open("data.json", "r") as f:
        json_content = json.load(f)
    for guild_id in json_content:
        guild = client.get_guild(int(guild_id))
        guild_roles = guild.roles
        active_role = None
        for role in guild_roles:
            if role.name == "Active":
                active_role = role
        for member_id in json_content[guild_id]:
            member = guild.get_member(int(member_id))
            member_roles = member.roles
            roles_names = []
            for role in member.roles:
                roles_names.append(role.name)
            if json_content[guild_id][member_id] >= REQUIRED_POINTS and "Active" not in roles_names:
                await member.add_roles(active_role)
            if json_content[guild_id][member_id] < REQUIRED_POINTS and "Active" in roles_names:
                await member.remove_roles(active_role)
        
# This function runs every second to assign values to all members in all guilds
async def point_assigner():
    global POINTS_UPPER_LIMIT
    global POINTS_LOWER_LIMIT
    global POINTS_ADDING_RATE
    global POINTS_SUBTRACTING_RATE
    while True:
        with open("data.json", "r") as f:
            json_content = json.load(f)
        for guild_id in json_content:
            for member in json_content[guild_id]:
                json_content[guild_id][member] -= POINTS_SUBTRACTING_RATE/60.0
                if json_content[guild_id][member] < POINTS_LOWER_LIMIT:
                    json_content[guild_id][member] = POINTS_LOWER_LIMIT
            guild = client.get_guild(int(guild_id))
            for channel in guild.voice_channels:
                for member in channel.members:
                    if applicable_for_point(member.voice) and member.bot == False:
                        json_content[guild_id][str(member.id)] += POINTS_ADDING_RATE/60.0 + POINTS_SUBTRACTING_RATE/60.0
                        if json_content[guild_id][str(member.id)] > POINTS_UPPER_LIMIT:
                            json_content[guild_id][str(member.id)] = POINTS_UPPER_LIMIT
        with open("data.json", "w") as f:
            json.dump(json_content, f)
        await assign_ranks()
        await asyncio.sleep(1)

# This function creates the "Active" role unless if an a role with the name "Active" was already present
async def create_role(guild):
    all_roles = await guild.fetch_roles()
    for role in all_roles:
        if role.name == "Active":
            return
    role = await guild.create_role(name="Active", hoist=True)
    
# This event triggers with the bot's startup 
@client.event
async def on_ready():
    client.loop.create_task(point_assigner())
    for guild in client.guilds:
        parsing_new_guild(guild)
        await create_role(guild)

# This event triggers when the bot joins a guild
@client.event
async def on_guild_join(guild):
    parsing_new_guild(guild)
    await create_role(guild)

# This event triggers when the bot leaves a guild
@client.event
async def on_guild_remove(guild):
    with open("data.json", "r") as f:
        json_content = json.load(f)
    try: json_content.pop(str(guild.id))
    except: print("Could not pop {}'s ID from the data.json".format(guild.name))
    with open("data.json","w") as f:
        json.dump(json_content, f)

# This event triggers when a member leaves a guild
@client.event
async def on_member_remove(member):
    with open("data.json", "r") as f:
        json_content = json.load(f)
    guilds_id = str(member.guild.id)
    member_id = str(member.id)
    try: json_content[guilds_id].pop(member_id)
    except KeyError: print("Caught exception silently: could not pop '{0}' which belongs to '{1}' from the JSON file".format(member_id, str(member.name)))
    with open("data.json", "w") as f:
        json.dump(json_content, f)

# This event triggers when a member joins a guild
@client.event
async def on_member_join(member):
    with open("data.json", "r") as f:
        json_content = json.load(f)
    guilds_id = str(member.guild.id)
    member_id = str(member.id)
    json_content[guilds_id][member_id] = 0
    with open("data.json", "w") as f:
        json.dump(json_content, f)

@client.event
async def on_message(message):
    if message.content == "--help":
        global POINTS_ADDING_RATE
        global POINTS_SUBTRACTING_RATE
        global POINTS_UPPER_LIMIT
        global REQUIRED_POINTS
        await message.channel.send("""Tucker determines whether certain members of this server are being active and frequently joining or not. Based on that, an "Active" rank is awarded.
Present, unmuted, and undeafened members will obtain {0} **Active Point** every minute, while other absent members slowly lose **Active Point** at a rate of {1} every minute.
The required number of **Active Points** to achieve the "Active" rank is {2}. Though, there is an upper limit of {3} that each user may obtain.
        --mypoints : Displays the amount of **Active Points** you currently have.
        --lookup <user_id> : Displays the amount of **Active Points** the user has.
        --rates : Displays the rates at which **Active Points** are awarded/deducted.
        --add <number> <user_id> : Adds **Active Points** to the specified user.              
""".format(POINTS_ADDING_RATE, POINTS_SUBTRACTING_RATE, REQUIRED_POINTS, POINTS_UPPER_LIMIT))

    elif message.content == "--mypoints":
        with open("data.json", "r") as f:
            json_content = json.load(f)
        guild_id = str(message.author.guild.id)
        member_id = str(message.author.id)
        active_points = json_content[guild_id][member_id]
        await message.channel.send("{0}, you currently have {1}/{2} **Active Points.**".format(message.author.name, round(active_points, 3), POINTS_UPPER_LIMIT))

    elif message.content == "--rates":
        await message.channel.send("""Adding rate = {0} **Active Point**/min
Subtracting rate = {1} **Active Point**/min
Upper limit = {2} **Active Points**
Required points to obtain role = {3} **Active Points**
""".format(POINTS_ADDING_RATE, POINTS_SUBTRACTING_RATE, POINTS_UPPER_LIMIT, REQUIRED_POINTS))

    elif message.content.split(" ")[0] == "--lookup":
        if(len(message.content.split(" ")) != 2):
            await message.channel.send('Invalid command format!\nPlease follow this format "--lookup 231396915730841600".')
        else:
            with open("data.json", "r") as f:
                json_content = json.load(f)
            requested_id = message.content.split(" ")[1]
            guild_id = str(message.author.guild.id)
            if requested_id not in json_content[guild_id]:
                await message.channel.send('User code "{}" not found in the database!\nPlease follow this format "--lookup 231396915730841600".'.format(requested_id))
            else:
                active_points = json_content[guild_id][requested_id]
                await message.channel.send('{0} currently has {1} **Active Points**.'.format(message.author.guild.get_member(int(requested_id)).name, round(active_points, 3)))
    elif message.content.split(" ")[0] == "--add":
        if(len(message.content.split(" ")) != 3):
            await message.channel.send('Invalid command format!\nPlease follow this format "--add 412 231396915730841600".')
        else:
            with open("data.json", "r") as f:
                json_content = json.load(f)
            added_points = message.content.split(" ")[1]
            requested_id = message.content.split(" ")[2]
            guild_id = str(message.author.guild.id)
            if requested_id not in json_content[guild_id]:
                await message.channel.send('User code "{}" not found in the database!\nPlease follow this format "--add 412 231396915730841600".'.format(requested_id))
            else:
                try:
                    added_points = float(added_points)
                    author_permission = message.author.top_role.permissions
                    if message.author.id == message.author.guild.owner_id or author_permission.administrator == True:
                        json_content[guild_id][str(requested_id)] += added_points
                        if json_content[guild_id][str(requested_id)] > POINTS_UPPER_LIMIT: json_content[guild_id][str(requested_id)] = POINTS_UPPER_LIMIT
                        elif json_content[guild_id][str(requested_id)] < POINTS_LOWER_LIMIT: json_content[guild_id][str(requested_id)] = POINTS_LOWER_LIMIT
                        await message.channel.send('{0} now obtains {1} **Active Points**.'.format(message.author.guild.get_member(int(requested_id)).name, round(json_content[guild_id][str(requested_id)], 3)))
                        with open("data.json", "w") as f:
                            json.dump(json_content, f)
                    else:
                        await message.channel.send('{}, only administrators and server owner can use this command.'.format(message.author.name))
                except Exception as e:
                    await message.channel.send('"{}" is not a valid number!\nPlease follow this format "--add 412 231396915730841600".'.format(added_points))
                    
client.run(TOKEN)
