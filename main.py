import discord
from discord.ext import commands
import logging
import random
import json

# enable basic logging
logging.basicConfig(level=logging.INFO)

# load client and set prefix from config
bot = commands.Bot(command_prefix = '+')
bot.help_command = commands.MinimalHelpCommand(no_category="Misc", verify_checks=False)

@bot.event
async def on_ready():
	activity = discord.Activity(type=discord.ActivityType.listening, name="+help")
	await bot.change_presence(activity=activity)

# cog for movie poll commands
class MovieNight(commands.Cog, name="Movie Night"):

	# check if user is a movie night manager or admin
	# TODO: move output to dedicated error function for checks
	async def is_manager(ctx):

		# load guild json
		data = readData(ctx.guild.id)

		# return false if user is non a manager nor admin
		if ctx.author.id not in data["config"]["managers"] and not ctx.author.guild_permissions.administrator:
			await ctx.send("Only managers and admins can use this command.")
			return False
		else:
			return True

	# check if user has member role
	async def is_movienight(ctx):

		# load guild json
		data = readData(ctx.guild.id)

		# check if movie role is set
		if "movierole" not in data["config"]:
			await ctx.send("There is no movie night role! create one with `+setrole <role name>`")
			return False
		role = ctx.guild.get_role(data["config"]["movierole"])

		# check if user has the role
		if role not in ctx.author.roles:
			await ctx.send(f"You don't have the role `{role.name}`!")
			return False
		else:
			return True

	# submit choice for movie poll
	@commands.command(
		help = "Submit your choice for the movie poll. Recommended format: Movie-Title (Year)",
		brief = "Submit your choice for the movie poll."
	)
	@commands.check(is_movienight)
	async def submit(self, ctx, *, submission):

		# load guild json
		data = readData(ctx.guild.id)

		# ensure this is users first submission
		# TODO: allow them to react to overwrite submission
		for item in data["submissions"]:
			if item["user"] == ctx.author.id:
				await ctx.send("You've already made a submission! Use `unsubmit` to remove it first.")
				return
		
		# add submission to data, write to file
		data["submissions"].append({"movie":submission, "user":ctx.author.id})
		writeData(ctx.guild.id, data)

		await ctx.send("Submission sucessful! Use `submissions` to see a list of submissions.")

	# unsubmit choice for movie poll
	@commands.command(	
		help = "Remove your submission from the poll.",
		brief = "Remove your submission from the poll."
	)
	@commands.check(is_movienight)
	async def unsubmit(self, ctx):

		# load guild json
		data = readData(ctx.guild.id)

		# return if no submissions yet
		if len(data["submissions"]) == 0:
			await ctx.send("No submissions yet! Use 'submit` to place a submission.")
			return

		# find user's submission
		for item in data["submissions"]:
			if item["user"] == ctx.author.id:
				data["submissions"].remove(item)
				await ctx.send("Submission removed! Use `submit` to place a new submission")
			else:
				await ctx.send("Submission not found!")
				return
		
		# write to file
		writeData(ctx.guild.id, data)

	# view list of current movie submissions
	@commands.command(
		help = "Display a list of all current movie submissions. Does not create a poll.",
		brief = "List current movie submissions"
	)
	@commands.check(is_movienight)
	async def submissions(self, ctx):

		# load guild json
		data = readData(ctx.guild.id)

		# return if no submissions yet
		if len(data["submissions"]) == 0:
			await ctx.send("No submissions yet! Use `submit` to place a submission.")
			return

		# format and send response as blockquote
		response = "\n>>> "
		for item in data["submissions"]:
			user = await bot.fetch_user(item["user"])
			response += f"{item['movie']} - {user.mention}\n"
		await ctx.send(response)

	# creates a poll from submitted movies
	@commands.command(
		help = "Create a poll from user-submitted movies. Does not delete submissions.",
		brief = "Create a poll from submitted movies"
	)
	@commands.check(is_manager)
	async def createpoll(self, ctx):

		# load guild json
		data = readData(ctx.guild.id)
		
		message = await ctx.send('`generating poll`')

		# generate main body of embed
		desc = ''
		used_emoji = []
		for item in data["submissions"]:

			# randomly select an unused emoji
			# TODO: have a case for when the server doesn't have enough emoji
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
	@commands.command(
		help = "Clear current submissions to begin a new poll. WARNING: deleted submissions are non-recoverable.",
		brief = "Clear current submissions to begin a new poll"
	)
	@commands.check(is_manager)
	async def newpoll(self, ctx):

		# load guild json
		data = readData(ctx.guild.id)
		data["submissions"] = []

		# write to file
		writeData(ctx.guild.id, data)

		await ctx.send("Ready to recieve submissions for a new poll! Previous submissions have been deleted.")
	
	# set the movie night member role, creates it if it doesnt exist
	@commands.command(
		help = "Set the movie night member role. Creates the role if it does not already exist.",
		brief = "Set the movie night member role."
	)
	@commands.check(is_manager)
	async def setrole(self, ctx, *, rolename):

		# load guild json
		data = readData(ctx.guild.id)

		# lookup and see if role already exists, create if not
		role = discord.utils.get(ctx.guild.roles, name=rolename)
		if role == None:
			try:
				role = await ctx.guild.create_role(name=rolename, mentionable=True)
			except discord.Forbidden:
				await ctx.send("I don't have the `Manage Roles` permission!")
				return

		data["config"]["movierole"] = role.id
		writeData(ctx.guild.id, data)

		await ctx.send(f"`{role.name}` is now the movie night role!")

	# toggle manager permissions for a user
	@commands.command(	
		help = "Toggle manager permissions for a user.",
		brief = "Toggle manager permissions for a user."
	)
	@commands.check(is_manager)
	async def togglemanager(self, ctx, member: discord.Member):

		# load guild json
		data = readData(ctx.guild.id)

		# currently not a manager
		if member.id not in data["config"]["managers"]:
			data["config"]["managers"].append(member.id)
			await ctx.send(f"`{member.name}` is now a manager!")

		# already a manager
		else:
			data["config"]["managers"].remove(member.id)
			await ctx.send(f"`{member.name}` is no longer a manager!")

		writeData(ctx.guild.id, data)

# MISC COMMANDS
@bot.command(
	help = "Displays current latency",
	brief = "Ping Pong!"
)
async def ping(ctx):
	await ctx.send(f"pong! {round(bot.latency * 1000)}ms")

# helper functions to read and write to guild json
def readData(id):
	try:
		with open(f"./data/{id}.json", "r+") as f:
			data = json.load(f)
	except IOError:
		data = {"config": {"managers":[]},"submissions": []}
	return data

def writeData(id, data):
	with open(f"./data/{id}.json", "w") as f:
		json.dump(data, f, indent=4)

# load cogs
bot.add_cog(MovieNight(bot))

# load and run token from file
token = open('./token', 'r').read()
bot.run(token)