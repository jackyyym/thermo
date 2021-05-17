import discord
from discord.ext import commands
import logging
import json
import os

# enable basic logging
logging.basicConfig(level=logging.INFO)

# load config.json, create if doesnt exist
if os.path.exists('config.json'):
	with open('config.json', 'r') as f:
		config = json.load(f)
else:
	print("THERMO: config.json not found, creating new config file")
	config = {"prefix": "+"}
	with open('config.json', 'w') as f:
		json.dump(config, f, indent=4)

# load data.json, create if doesnt exist
if os.path.exists('data.json'):
	with open('data.json', 'r') as f:
		data = json.load(f)
else:
	print("THERMO: data.json not found, creating new data file")
	data = {{"guilds": []}}
	with open('data.json', 'w') as f:
		json.dump(data, f, indent=4)


# load client and set prefix from config
bot = commands.Bot(command_prefix = config['prefix'])

@bot.command()
async def ping(ctx):
	await ctx.send(f"pong! {round(client.latency * 1000)}ms")

# submit choice for movie poll
@bot.command()
async def submit(ctx, *, submission):

	# search data for correct guild
	curr_guild = findGuild(ctx)

	# if guild not found, return
	# TODO: automatically add guild to JSON
	if (curr_guild == None):
		await ctx.send("Guild not found!")
		return

	# ensure this is users first submission
	for item in curr_guild["submissions"]:
		if item["user"] == ctx.author.id:
			await ctx.send("You've already made a submission! Use `unsubmit` to remove it first.")
			return
	
	# add submission to data, write to file
	curr_guild["submissions"].append({"movie":submission, "user":ctx.author.id})
	with open('data.json', 'w') as f:
		json.dump(data, f, indent=4)
	await ctx.send("Submission sucessful! Use `submissions` to see a list of submissions.")


# view list of current movie submissions
@bot.command()
async def submissions(ctx):

	# search data for correct guild
	curr_guild = findGuild(ctx)

	# if guild not found, return
	if (curr_guild == None):
		await ctx.send("Guild not found!")
		return

	# format and send response as blockquote
	response = "\n>>> "
	for _submission in curr_guild["submissions"]:
		response += f"{_submission['movie']} - {_submission['user']}\n"
	await ctx.send(response)

# helper function to find guilds data
def findGuild(ctx):

	# search data for correct guild
	curr_guild = None
	for item in data['guilds']:
		if item["guildID"] == ctx.guild.id:
			curr_guild = item
			break

	# return current guild data, None if not found
	return curr_guild


# load and run token from file
token = open('token', 'r').read()
bot.run(token)