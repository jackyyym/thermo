import discord
from discord.ext import commands
import logging
import random
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
bot.help_command = commands.MinimalHelpCommand()

@bot.event
async def on_ready():
	activity = discord.Activity(type=discord.ActivityType.listening, name=f"{config['prefix']}help")
	await bot.change_presence(activity=activity)

# cog for movie poll commands
class MovieNight(commands.Cog, name="Movie Night"):

	# submit choice for movie poll
	@commands.command(	
		help = "Submit your choice for the movie poll. Recommended format: Movie-Title (Year)",
		brief = "Submit your choice for the movie poll."
	)
	async def submit(self, ctx, *, submission):

		# search data for correct guild
		curr_guild = findGuild(ctx)

		# if guild not found, return
		if (curr_guild == None):
			await ctx.send("Guild not found! Try `newpoll` to create a new poll")
			return

		# ensure this is users first submission
		# TODO: allow them to react to overwrite submission
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
	@commands.command(	
		help = "Display a list of all current movie submissions. Does not create a poll.",
		brief = "List current movie submissions"
	)
	async def submissions(self, ctx):

		# search data for correct guild
		curr_guild = findGuild(ctx)
		if (curr_guild == None):
			await ctx.send("Guild not found!")
			return

		# format and send response as blockquote
		# TODO: actually display username
		response = "\n>>> "
		for item in curr_guild["submissions"]:
			user = await bot.fetch_user(item["user"])
			response += f"{item['movie']} - {user.mention}\n"
		await ctx.send(response)

	# creates a poll from submitted movies
	@commands.command(	
		help = "Creates a poll from user-submitted movies. Does not delete submissions.",
		brief = "Create a poll from submitted movies"
	)
	async def createpoll(self, ctx):

		# search data for correct guild
		curr_guild = findGuild(ctx)
		if (curr_guild == None):
			await ctx.send("Guild not found!")
			return
		
		message = await ctx.send('`generating poll`')

		# generate main body of embed
		desc = ''
		used_emoji = []
		for item in curr_guild["submissions"]:

			# randomly select an unused emoji
			while True:
				emoji = bot.emojis[random.randint(0, len(bot.emojis)-1)]
				if emoji not in used_emoji:
					break
			used_emoji.append(emoji)

			# add line to embed description
			user = await bot.fetch_user(item["user"])
			desc += f"{emoji} : **{item['movie']}** - {user.mention}\n\n"

			# add matching reaction
			await message.add_reaction(emoji)

		embed = discord.Embed(
			title = 'Movie Night Poll!',
			description = desc,
			color = discord.Color.blue()
		)

		embed.set_footer(text=f"Requested by {ctx.author.name}")

		await message.edit(content='', embed=embed)

	# deletes previous submissions to start new poll
	# TODO: configure who can use this command
	@commands.command(	
		help = "Clear current submissions to begin a new poll. WARNING: deleted submissions are non-recoverable.",
		brief = "Clear current submissions to begin a new poll"
	)
	async def newpoll(self, ctx):

		# search data for correct guild
		curr_guild = findGuild(ctx)

		# if guild not found, add it to data. otherwise delete submissions
		if (curr_guild == None):
			data["guilds"].append({"guildID":ctx.message.guild.id, "submissions":[]})
		else:
			curr_guild["submissions"] = []

		# write to json
		with open('data.json', 'w') as f:
			json.dump(data, f, indent=4)
		await ctx.send("Ready to recieve submissions for a new poll! Previous submissions have been deleted.")

# MISC COMMANDS
@bot.command(
	help = "Displays current latency",
	brief = "Ping Pong!"
)
async def ping(ctx):
	await ctx.send(f"pong! {round(bot.latency * 1000)}ms")


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

# load cogs
bot.add_cog(MovieNight(bot))

# load and run token from file
token = open('token', 'r').read()
bot.run(token)