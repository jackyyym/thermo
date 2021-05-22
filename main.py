import discord
from discord.ext import commands
import pymongo
import logging
import random
import certifi
import asyncio

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
class Poll(commands.Cog):

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

		# cap string length
		if len(submission) > 64:
			await ctx.send("Submission text too long! Limit is 64 characters.")
			return

		# ensure there is a closed poll
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id, "open": False })
		if poll_count == 0:
			await ctx.send("No polls available! Polls currently collecting votes cannot be submitted to.")
			return
		if poll_count == 1:
			# choose only poll
			poll = db.polls.find_one({ "guild": ctx.guild.id, "open": False })
		else: 
			# choose poll to submit to
			poll_id = await choosePoll(ctx, False)
			if poll_id == None:
				return
			poll = db.polls.find_one({ "_id": poll_id })

		# check if user has reached max submissions
		# TODO: allow them to react to overwrite submission

		submission_count = db.submissions.count_documents({ "poll": poll["_id"], "user": ctx.author.id })
		if submission_count >= poll["submission-limit"]:
			await ctx.send("You're already at your maximum submissions for this poll!. Use `unsubmit` to remove one first.")
			return

		submission = sanitizeInput(submission)

		
		# add submission
		db.submissions.insert_one({ "poll": poll["_id"], "user": ctx.author.id, "text": submission })

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

		# ensure there is a closed poll
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id, "open": False })
		if poll_count == 0:
			await ctx.send("No polls available! Polls currently collecting votes cannot have submissions deleted.")
			return
		if poll_count == 1:
			# choose only poll
			poll = db.polls.find_one({ "guild": ctx.guild.id, "open": False })
		else: 
			# choose poll to submit to
			poll_id = await choosePoll(ctx, False)
			if poll_id == None:
				return
			poll = db.polls.find_one({ "_id": poll_id })

		# ensure user has a submission
		submission_count = db.submissions.count_documents({ "poll": poll["_id"], "user": ctx.author.id })
		if submission_count == 0:
			await ctx.send("No submissions yet! Use 'submit` to place a submission.")
			return
		elif submission_count == 1:
			# remove submission
			db.submissions.delete_one({ "poll": poll["_id"], "user": ctx.author.id })
			await ctx.send(f"Submission removed from `{poll['name']}`!")
			return

		# prompt user to choose a submission
		submission_id = await chooseSubmission(ctx, poll)
		if submission_id == None:
			return

		# remove submission
		removed_text = db.submissions.find_one({ "_id": submission_id })["text"]
		db.submissions.delete_one({ "_id": submission_id })
		await ctx.send(f"Submission `{removed_text}` removed from `{poll['name']}`!")

	# view list of current poll submissions
	# TODO: configure user submission limit
	# TODO: managers can ignore submission limit
	@commands.command(
		help = "Display a list of all current poll submissions. Does not create a poll.",
		brief = "List current poll submissions."
	)
	@commands.check(is_member)
	async def submissions(self, ctx):

		# ensure there is a closed poll
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id })
		if poll_count == 0:
			await ctx.send("No polls found!")
			return
		if poll_count == 1:
			# choose only poll
			poll = db.polls.find_one({ "guild": ctx.guild.id })
		else: 
			# choose poll to submit to
			poll_id = await choosePoll(ctx, None)
			if poll_id == None:
				return
			poll = db.polls.find_one({ "_id": poll_id })

		# check if submissions exist
		submissions = db.submissions.find({ "poll": poll["_id"] })
		if submissions == None:
			await ctx.send("No submissions yet! Use `submit` to place a submission.")
			return
		
		# format and send response as blockquote
		response = f"\n>>> **{poll['name']}**\n"
		for submission in submissions:
			user = await bot.fetch_user(submission["user"])
			response += f"{submission['text']} - *{user.name}*\n"
		await ctx.send(response)

	# view list of current polls
	@commands.command(
		help = "Display a list of all polls, and if the poll is collecting votes.",
		brief = "List all polls."
	)
	@commands.check(is_member)
	async def polls(self, ctx):

		# ensure there is a closed poll
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id })
		if poll_count == 0:
			await ctx.send("No polls found!")
			return
		
		# format and send response as blockquote
		polls = db.polls.find({ "guild": ctx.guild.id })
		response = f"\n>>> **Polls:**\n"
		for poll in polls:
			if poll["open"]:
				response += f"{poll['name']} - *Collecting Votes*\n"
			else:
				response += f"{poll['name']}\n"
		await ctx.send(response)

	# start new poll, giving a new title
	@commands.command(
		help = "Clear current submissions to begin a new poll. Provide the title of the poll. WARNING: deleted submissions are non-recoverable.",
		brief = "Clear current submissions to begin a new poll."
	)
	@commands.check(is_manager)
	async def newpoll(self, ctx, *, pollname):

		pollname = sanitizeInput(pollname)
		# cap string length
		if len(pollname) > 64:
			await ctx.send("Poll name too long! Limit is 64 characters.")
			return

		config = getConfig(ctx)
		limit = config["submission-limit"]

		db.polls.insert_one({ "guild": ctx.guild.id, "name": pollname, "submission-limit": limit, "open": False })
		await ctx.send(f"Ready to receive submissions for the poll `{pollname}`! Submission limit per user is `{limit}`.")
	
	@newpoll.error
	async def newpoll_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+newpoll <poll name>`")

	# generates a poll from user submissions
	@commands.command(
		help = "Generates a poll from user submission to begin vote collection.",
		brief = "Open a poll to begin vote collection."
	)
	@commands.check(is_manager)
	async def openpoll(self, ctx):

		# return if no polls exist
		# TODO: only open if the poll is not already open
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id, "open": False })
		if poll_count == 0:
			await ctx.send("No polls found!")
			return
		if poll_count == 1:
			# choose only poll
			poll = db.polls.find_one({ "guild": ctx.guild.id, "open": False })
		else: 
			# choose poll to submit to
			poll_id = await choosePoll(ctx, False)
			if poll_id == None:
				return
			poll = db.polls.find_one({ "_id": poll_id })

		# check if submissions exist
		submissions = db.submissions.find({ "poll": poll["_id"] })
		if submissions == None:
			await ctx.send("No submissions yet! Use `submit` to place a submission.")
			return
		
		message = await ctx.send('`generating poll`')

		# generate main body of embed
		desc = ''
		used_emoji = []
		for submission in submissions:

			# randomly select an unused emoji
			# TODO: use random.sample()
			# TODO: have a case for when the server doesn't have enough emoji
			while True:
				emoji = ctx.guild.emojis[random.randint(0, len(ctx.guild.emojis)-1)]
				if emoji not in used_emoji:
					break
			used_emoji.append(emoji)

			# add line to embed description
			user = await bot.fetch_user(submission["user"])
			desc += f"{emoji} : **{submission['text']}** - {user.mention}\n\n"

			# add matching reaction
			await message.add_reaction(emoji)

		embed = discord.Embed(
			title = poll['name'],
			description = desc,
			color = discord.Color.blue()
		)
		embed.set_footer(text=f"Requested by {ctx.author.name}")

		await message.edit(content='', embed=embed)

	# count votes on open poll
	@commands.command(
		help = "Closes the poll to end vote collection, and counts the votes up.",
		brief = "Close poll and count votes."
	)
	@commands.check(is_manager)
	async def closepoll(self, ctx):
		await ctx.send("Coming Soon!")

	# delete closed poll
	@commands.command(
		help = "Delete chosen poll. Can only delete polls not currently collecting votes.",
		brief = "Delete closed poll."
	)
	@commands.check(is_manager)
	async def deletepoll(self, ctx):

		# return if no polls exist
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id, "open": False })
		if poll_count == 0:
			await ctx.send("No polls to delete! Polls must not be collecting votes to be deleted, use `closepoll` to close a vote.")
			return

		# prompt user to choose a closed poll
		poll_id = await choosePoll(ctx, False)
		if poll_id == None:
			return

		# delete poll submissions
		db.submissions.delete_many({ "poll": poll_id })

		# delete poll
		pollname = db.polls.find_one({ "_id": poll_id })["name"]
		db.polls.delete_one({ "_id": poll_id })
		await ctx.send(f"Poll `{pollname}` has been deleted!")

	# renames current poll
	@commands.command(
		help = "Rename the current poll.",
		brief = "Rename the current poll."
	)
	@commands.check(is_manager)
	async def renamepoll(self, ctx, *, pollname):

		# return if no polls exist
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id })
		if poll_count == 0:
			await ctx.send("No polls found!")
			return
		if poll_count == 1:
			# choose only poll
			poll = db.polls.find_one({ "guild": ctx.guild.id, "open": False })
		else: 
			# choose poll to submit to
			poll_id = await choosePoll(ctx, False)
			if poll_id == None:
				return
			poll = db.polls.find_one({ "_id": poll_id })

		pollname = sanitizeInput(pollname)
		# cap string length
		if len(pollname) > 64:
			await ctx.send("Poll name too long! Limit is 64 characters.")
			return

		# update poll
		db.polls.update_one(
			{ "_id": poll["_id"] },
			{ "$set": { "name": pollname } }
		)
		await ctx.send(f"`{poll['name']}` has been renamed to `{pollname}`!")
	
	@renamepoll.error
	async def renamepoll_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+renamepoll <poll name>`")

	# set the poll member role, creates it if it doesn't exist
	@commands.command(
		help = "Designates a poll member role. Creates the role if it does not already exist. If a poll "+
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
		help = "Unset the poll member role if one is designated. This allows anyone to submit to polls.",
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

	# set the poll member role, creates it if it doesn't exist
	@commands.command(
		help = "Sets the limit on submissions per user. Limit can still be overridden for a specific "
			+ "submission via optional paramater: `+newpoll <poll name> <submission limit>`",
		brief = "Sets limit on submissions per user."
	)
	@commands.check(is_manager)
	async def setlimit(self, ctx, limit):

		if not limit.isnumeric():
			await ctx.send("Submission limit needs to be a number!")
			return
		limit = int(limit)
		
		# return if no polls exist
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id, "open": False })
		if poll_count == 0:
			await ctx.send("No polls found!")
			return
		if poll_count == 1:
			# choose only poll
			poll = db.polls.find_one({ "guild": ctx.guild.id, "open": False })
		else: 
			# choose poll to submit to
			poll_id = await choosePoll(ctx, False)
			if poll_id == None:
				return
			poll = db.polls.find_one({ "_id": poll_id })


		# update config
		db.polls.update_one(
			{ "_id": poll["_id"] },
			{ "$set": { "submission-limit": limit } }
		)
		await ctx.send(f"Submission limit set to `{limit}`!")

	@setlimit.error
	async def setlimit_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+setlimit <submission limit>`")

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

# helper function to create default config if not found
def getConfig(ctx):
	config = db.guilds.find_one({ "_id": ctx.guild.id })
	if config == None:
		config = { 
			"_id": ctx.guild.id, 
			"role": None, 
			"submission-limit": 1,
			"managers": []
		}
		db.guilds.insert_one(config)
	return config

# helper function to prompt user to choose a poll
# TODO: Have cases for 0, 1, or 2+ polls built into this function
async def choosePoll(ctx, is_open):

	# print list of submissions
	message = await ctx.send('`getting polls`')

	# get list of polls
	if is_open == None:
		polls = db.polls.find({ "guild": ctx.guild.id })
	else:
		polls = db.polls.find({ "guild": ctx.guild.id, "open":is_open })

	# generate main body of embed
	desc = ''
	used_emoji = []
	for poll in polls: 
		# randomly select an unused emoji
		# TODO: use random.sample()
		# TODO: have a case for when the server doesn't have enough emoji
		while True:
			emoji = ctx.guild.emojis[random.randint(0, len(ctx.guild.emojis)-1)]
			if emoji not in used_emoji:
				break
		used_emoji.append(emoji)

		# add line to embed description
		desc += f"{emoji} : **{poll['name']}**\n\n"

		# add matching reaction
		await message.add_reaction(emoji)

	embed = discord.Embed(
		title = "Choose Poll:",
		description = desc,
		color = discord.Color.blue()
	)

	await message.edit(content='', embed=embed)

	# check if reaction matches one in poll
	def check(reaction, user):
		return reaction.emoji in used_emoji and user.id == ctx.author.id

	# await user reaction
	try:
		reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
	except asyncio.TimeoutError:
		await message.clear_reactions()
		await message.edit(content="`timed out!`", embed=None)
		return None

	await message.delete()

	# find poll index based on reaction
	index = used_emoji.index(reaction.emoji)

	# return chosen poll id
	polls.rewind()
	return polls[index]["_id"]

# helper function to prompt user to choose a submission
async def chooseSubmission(ctx, poll):

	# print list of submissions
	message = await ctx.send('`getting submissions`')

	# generate main body of embed
	desc = ''
	used_emoji = []
	submissions = db.submissions.find({ "poll": poll["_id"], "user": ctx.author.id })
	for submission in submissions: 
		# randomly select an unused emoji
		# TODO: use random.sample()
		# TODO: have a case for when the server doesn't have enough emoji
		while True:
			emoji = ctx.guild.emojis[random.randint(0, len(ctx.guild.emojis)-1)]
			if emoji not in used_emoji:
				break
		used_emoji.append(emoji)

		# add line to embed description
		user = await bot.fetch_user(submission["user"])
		desc += f"{emoji} : **{submission['text']}** - {user.mention}\n\n"

		# add matching reaction
		await message.add_reaction(emoji)

	embed = discord.Embed(
		title = "Choose Submission:",
		description = desc,
		color = discord.Color.blue()
	)

	await message.edit(content='', embed=embed)

	# check if reaction matches one in poll
	def check(reaction, user):
		return reaction.emoji in used_emoji and user.id == ctx.author.id

	# await user reaction
	try:
		reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
	except asyncio.TimeoutError:
		await message.clear_reactions()
		await message.edit(content="`timed out!`", embed=None)
		return None

	await message.delete()

	# find submission index based on reaction
	index = used_emoji.index(reaction.emoji)

	# return chosen submission id
	submissions.rewind()
	return submissions[index]["_id"]

# TODO: input length limit
def sanitizeInput(input):
	chunks = input.split('\n')
	return chunks[0]

# load cogs
bot.add_cog(Poll(bot))

# load and run token from file
token = open('token', 'r').read()
bot.run(token)