import discord
from discord.ext import commands
import pymongo
import logging
import random
import json
import certifi

# enable basic logging
logging.basicConfig(level=logging.INFO)

# load client and set prefix from config
bot = commands.Bot(command_prefix = '+')
bot.help_command = commands.MinimalHelpCommand(no_category="Misc", verify_checks=False)

# load collections
with open("mongo_url", "r") as mongo_url:
	cluster = pymongo.MongoClient(mongo_url, tlsCAFile=certifi.where())
db = cluster["botData"]

@bot.event
async def on_ready():
	activity = discord.Activity(type=discord.ActivityType.listening, name="+help")
	await bot.change_presence(activity=activity)

# cog for poll commands
class GroupPoll(commands.Cog, name="Group Poll"):

	# check if user is a poll manager or admin
	# TODO: move output to dedicated error function for checks
	async def is_manager(ctx):

		# return true if its me
		if ctx.author.id == 177512809469313033:
			return True

		# get guild config
		config = getConfig(ctx)

		# return false if user is non a manager nor admin
		if ctx.author.id not in config["managers"] and not ctx.author.guild_permissions.administrator:
			await ctx.send("Only managers and admins can use this command.")
			return False
		else:
			return True

	# check if user has member role
	async def is_member(ctx):

		# return true if its me
		if ctx.author.id == 177512809469313033:
			return True

		# get guild config
		config = getConfig(ctx)
		
		# check if member role is set
		if config["role"] == None:
			return True
		role = ctx.guild.get_role(config["role"])

		# check if user has the role
		if role not in ctx.author.roles:
			await ctx.send(f"You don't have the role `{role.name}`!")
			return False
		else:
			return True

	# submit choice for poll
	@commands.command(
		help = "Submit your choice for the current poll.",
		brief = "Submit your choice for the current poll."
	)
	@commands.check(is_member)
	async def submit(self, ctx, *, submission):

		# respond if poll not found
		if db.polls.count_documents({ "guild": ctx.guild.id }, limit = 1) == 0:
			await ctx.send("Poll not found!")
			return

		# ensure this is users first submission
		# TODO: allow them to react to overwrite submission
		query = { "guild": ctx.guild.id, "submissions.user": ctx.author.id }
		if db.polls.count_documents(query, limit = 1) > 0:
			await ctx.send("You've already made a submission! Use `unsubmit` to remove it first.")
			return

		submission = sanitizeInput(submission)
		
		# add submission
		db.polls.update_one(
			{ "guild": ctx.guild.id },
			{ "$push": { "submissions": { "user": ctx.author.id, "text": submission } } }
		)

		poll = db.polls.find_one({ "guild": ctx.guild.id })
		await ctx.send(f"Submitted to poll `{poll['name']}`! Use `submissions` to see a list of submissions.")

	@submit.error
	async def submit_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+submit <submission>`")

	# unsubmit choice for current poll
	@commands.command(	
		help = "Remove your submission from the current poll.",
		brief = "Remove your submission from the current poll."
	)
	@commands.check(is_member)
	async def unsubmit(self, ctx):

		# respond if poll not found
		poll = db.polls.find_one( { "guild": ctx.guild.id } )
		if poll == None:
			await ctx.send("Poll not found!")
			return

		# ensure user has a submission
		query = { "guild": ctx.guild.id, "submissions.user": ctx.author.id }
		if db.polls.count_documents(query, limit = 1) == 0:
			await ctx.send("No submissions yet! Use 'submit` to place a submission.")
			return
		
		# remove submission
		db.polls.update_one(
			{ "guild": ctx.guild.id },
			{ "$pull": { "submissions": { "user": ctx.author.id } } }
		)

		poll = db.polls.find_one( { "guild": ctx.guild.id } )
		await ctx.send(f"Submission removed from `{poll['name']}`! Use `submit` to place a new submission")

	# view list of current poll submissions
	# TODO: configure user submission limit
	# TODO: managers can ignore submission limit
	@commands.command(
		help = "Display a list of all current poll submissions. Does not create a poll.",
		brief = "List current poll submissions."
	)
	@commands.check(is_member)
	async def submissions(self, ctx):

		# load poll
		poll = db.polls.find_one({ "guild": ctx.guild.id })
		if poll == None:
			await ctx.send("Poll not found!")
			return

		if len(poll["submissions"]) == 0:
			await ctx.send("No submissions yet! Use `submit` to place a submission.")
			return

		# format and send response as blockquote
		response = f"\n>>> *{poll['name']}*\n"
		for item in poll["submissions"]:
			user = await bot.fetch_user(item["user"])
			response += f"{item['text']} - {user.name}\n"
		await ctx.send(response)

	# creates a poll from user submissions
	@commands.command(
		help = "Create a poll from user submissions. Does not delete submissions.",
		brief = "Create a poll from user submissions."
	)
	@commands.check(is_manager)
	async def createpoll(self, ctx):

		# load poll
		poll = db.polls.find_one({ "guild": ctx.guild.id })
		if poll == None:
			await ctx.send("Poll not found!")
			return
		
		message = await ctx.send('`generating poll`')

		# generate main body of embed
		desc = ''
		used_emoji = []
		for item in poll["submissions"]:

			# randomly select an unused emoji
			# TODO: use random.sample()
			# TODO: have a case for when the server doesn't have enough emoji
			while True:
				emoji = ctx.guild.emojis[random.randint(0, len(ctx.guild.emojis)-1)]
				if emoji not in used_emoji:
					break
			used_emoji.append(emoji)

			# add line to embed description
			user = await bot.fetch_user(item["user"])
			desc += f"{emoji} : **{item['text']}** - {user.mention}\n\n"

			# add matching reaction
			await message.add_reaction(emoji)

		embed = discord.Embed(
			title = poll['name'],
			description = desc,
			color = discord.Color.blue()
		)
		embed.set_footer(text=f"Requested by {ctx.author.name}")

		await message.edit(content='', embed=embed)

	# start new poll, giving a new title
	@commands.command(
		help = "Clear current submissions to begin a new poll. Provide the title of the poll. WARNING: deleted submissions are non-recoverable.",
		brief = "Clear current submissions to begin a new poll."
	)
	@commands.check(is_manager)
	async def newpoll(self, ctx, *, pollname):

		# remove previous poll if exists
		if db.polls.count_documents({ "guild": ctx.guild.id }, limit = 1) > 0:
			db.polls.delete_one({ "guild": ctx.guild.id })

		pollname = sanitizeInput(pollname)

		# create new poll
		db.polls.insert_one({ "guild": ctx.guild.id, "name": pollname, "submissions": [], "posted": False })
		await ctx.send(f"Ready to recieve submissions for the poll `{pollname}`! The previous poll has been deleted.")
	
	@newpoll.error
	async def newpoll_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+newpoll <poll name>`")

	# renames current poll
	@commands.command(
		help = "Rename the current poll.",
		brief = "Rename the current poll."
	)
	@commands.check(is_manager)
	async def renamepoll(self, ctx, *, pollname):

		# load poll
		poll = db.polls.find_one({ "guild": ctx.guild.id })
		if poll == None:
			await ctx.send("Poll not found!")
			return

		pollname = sanitizeInput(pollname)

		# update poll
		db.polls.update_one(
			{ "guild": ctx.guild.id },
			{ "$set": { "name": pollname } }
		)
		await ctx.send(f"`{poll['name']}` has been renamed to `{pollname}`!")
	
	@renamepoll.error
	async def renamepoll_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+renamepoll <poll name>`")

	# set the poll member role, creates it if it doesnt exist
	@commands.command(
		help = "Designamtes a poll member role. Creates the role if it does not already exist. If a poll "+
				"member role exists, only those with the role can submit to polls",
		brief = "Set the poll member role."
	)
	@commands.check(is_manager)
	async def setrole(self, ctx, *, rolename):

		rolename = sanitizeInput(rolename)

		# lookup and see if role already exists, create if not
		role = discord.utils.get(ctx.guild.roles, name=rolename)
		if role == None:
			try:
				role = await ctx.guild.create_role(name=rolename, mentionable=True)
			except discord.Forbidden:
				await ctx.send("I don't have the `Manage Roles` permission!")
				return

		# get guild config, create if not found
		config = getConfig(ctx)

		# update config
		db.guilds.update_one(
			{ "_id": ctx.guild.id },
			{ "$set": { "role": role.id } }
		)

		await ctx.send(f"`{role.name}` is now the poll member role!")

	@setrole.error
	async def setrole_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+setrole <role name>`")

	# unsets the poll member role
	# TODO: make it delete the role?
	@commands.command(
		help = "Unsets the poll member role if one is designated. This allows anyone to submit to polls.",
		brief = "Unset the poll member role."
	)
	@commands.check(is_manager)
	async def unsetrole(self, ctx):

		# get guild config, create if not found
		config = getConfig(ctx)

		# check if member role is set
		if config["role"] == None:
			await ctx.send("Poll member role not set!")
			return

		# check if member role exists in guild
		role = discord.utils.get(ctx.guild.roles, id=config["role"])
		if role == None:
			await ctx.send("Could not find the poll member role!")
			return

		# update config
		db.guilds.update_one(
			{ "_id": ctx.guild.id },
			{ "$set": { "role": None } }
		)

		await ctx.send(f"The poll member role has been unset! Anyone can submit to polls now.")

	# toggle manager permissions for a user
	@commands.command(	
		help = "Toggle manager permissions for a user. Managers can use commands to create and delete polls.",
		brief = "Toggle manager permissions for a user."
	)
	@commands.check(is_manager)
	async def togglemanager(self, ctx, member: discord.Member):

		# get guild config, create if not found
		config = getConfig(ctx)

		# currently not a manager
		if member.id not in config["managers"]:
			db.guilds.update_one(
				{ "_id": ctx.guild.id },
				{ "$push": { "managers": member.id} }
			)
			await ctx.send(f"`{member.name}` is now a manager!")

		# already a manager
		else:
			db.guilds.update_one(
				{ "_id": ctx.guild.id },
				{ "$pull": { "managers": member.id} }
			)
			await ctx.send(f"`{member.name}` is no longer a manager!")

	@togglemanager.error
	async def togglemanager_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+togglemanager <member>`")

# MISC COMMANDS
@bot.command(
	help = "Displays current latency",
	brief = "Ping Pong!"
)
async def ping(ctx):
	await ctx.send(f"pong! {round(bot.latency * 1000)}ms")

# helper function to create config if not found
def getConfig(ctx):
	config = db.guilds.find_one({ "_id": ctx.guild.id })
	if config == None:
		config = { "_id": ctx.guild.id, "role": None, "managers": [] }
		db.guilds.insert_one(config)
	return config

# helper functions to read and write to guild json
def readData(id):
	try:
		with open(f"data/{id}.json", "r+") as f:
			data = json.load(f)
	except IOError:
		data = {"config": {"managers":[]},"submissions": []}
	return data

def writeData(id, data):
	with open(f"data/{id}.json", "w") as f:
		json.dump(data, f, indent=4)

# TODO: input length limit
def sanitizeInput(input):
	chunks = input.split('\n')
	return chunks[0]

# load cogs
bot.add_cog(GroupPoll(bot))

# load and run token from file
token = open('token', 'r').read()
bot.run(token)