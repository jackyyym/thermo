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
db = cluster["botTesting"]

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

		submission = await sanitizeInput(ctx, submission)
		if submission == None:
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
			removed_text = db.submissions.find_one({ "poll": poll["_id"], "user": ctx.author.id })["text"]
			db.submissions.delete_one({ "poll": poll["_id"], "user": ctx.author.id })
			await ctx.send(f"Submission `{removed_text}` removed from `{poll['name']}`!")
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

	# creates a new poll from a list of options
	@commands.group(
		help = "Create a new poll from a list of quote-separated options. Use this command when you want to quickly " +
			"create a poll where you define what all the options are ahead of time. To create a poll that " +
			"allows for users to submit poll options, see the command `+newpoll <poll name>`.",
		brief = "Create a new poll from a list of options.",
		invoke_without_command = True
	)
	@commands.check(is_manager)
	async def newpoll(self, ctx, pollname, *options):

		# return if subcommand called
		if ctx.invoked_subcommand is not None:
			return

		pollname = await sanitizeInput(ctx, pollname)
		if pollname == None:
			return
		
		# sanitize list of options
		for option in options:
			option = await sanitizeInput(ctx, option)
			if option == None:
				return

		config = getConfig(ctx)
		poll = db.polls.insert_one({ 
			"guild": ctx.guild.id,
			"name": pollname,
			"submission-limit": 0,
			"vote-limit": config["vote-limit"],
			"open": False 
		})

		for option in options:
			db.submissions.insert_one({ "poll": poll.inserted_id, "user": None, "text": option })

		await generatePoll(ctx, poll.inserted_id)

	# start new poll for user submission, giving a new title
	@newpoll.command(
		help = "Creates a new poll that is open to user submission. Use this command when you want " +
			"to allow for users submit poll options. To create a poll where you define all poll options " +
			"ahead of time, see the command `+newpoll userinput <poll name> <options>`",
		brief = "Create a new poll that is open to user submission.",
		cog_name="Poll"
	)
	@commands.check(is_manager)
	async def userinput(self, ctx, *, pollname):

		pollname = await sanitizeInput(ctx, pollname)
		if pollname == None:
			return

		config = getConfig(ctx)
		db.polls.insert_one({ 
			"guild": ctx.guild.id,
			"name": pollname,
			"submission-limit": config["submission-limit"],
			"vote-limit": config["vote-limit"],
			"open": False 
		})
		await ctx.send(f"Ready to receive submissions for the poll `{pollname}`! " +
			f"Submission limit is `{config['submission-limit']}`, vote limit is `{config['vote-limit']}`.")
	
	@userinput.error
	async def userinput_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+newpoll userinput <poll name>`")

	# generates a poll from user submissions
	@commands.command(
		help = "Generates a poll from user submission to begin vote collection.",
		brief = "Open a poll to begin vote collection."
	)
	@commands.check(is_manager)
	async def launchpoll(self, ctx):

		# return if no polls exist
		# TODO: only open if the poll is not already open
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id, "open": False })
		if poll_count == 0:
			await ctx.send("No polls found!")
			return
		if poll_count == 1:
			# choose only poll
			poll_id = db.polls.find_one({ "guild": ctx.guild.id, "open": False })["_id"]
		else: 
			# choose poll to submit to
			poll_id = await choosePoll(ctx, False)
			if poll_id == None:
				return
		
		await generatePoll(ctx, poll_id)

	# count votes on open poll
	@commands.command(
		help = "Closes the poll to end vote collection, and counts the votes up.",
		brief = "Close poll and count votes."
	)
	@commands.check(is_manager)
	async def closepoll(self, ctx):
		# return if no polls exist
		poll_count = db.polls.count_documents({ "guild": ctx.guild.id, "open": True })
		if poll_count == 0:
			await ctx.send("No polls currently open!")
			return
		# prompt user to choose a closed poll
		poll_id = await choosePoll(ctx, True)
		if poll_id == None:
			return

		# acquire poll message
		poll = db.polls.find_one({ "_id": poll_id })
		poll_message = await ctx.fetch_message(poll["message"])

		# sort list of reactions by count
		results = poll_message.reactions
		results.sort(key=lambda x: x.count, reverse=True)

		# generate emoji key
		key = []
		for reaction in poll_message.reactions:
			key.append(reaction.emoji)

		# post results
		submissions = db.submissions.find({ "poll": poll_id }).sort("text")

		# generate main body of embed
		desc = ''
		used_emoji = []
		for result in results:

			# add line to embed description
			index = key.index(result.emoji)
			desc += f"{result.emoji} : **{submissions[index]['text']}** - *{result.count-1} votes*\n\n"

		embed = discord.Embed(
			title = f"{poll['name']} results:",
			description = desc,
			color = discord.Color.blue()
		)
		embed.set_footer(text=f"Requested by {ctx.author.name}")
		results_message = await ctx.send(embed=embed)

		# edit old poll
		embed = discord.Embed(
			title = f"{poll['name']}:",
			description = f"Voting has concluded! See the results [here]({results_message.jump_url})"
		)
		await poll_message.edit(embed=embed)
		await poll_message.clear_reactions()

		db.polls.update_one(
			{ "_id": poll_id },
			{ "$set": { "open": False }, "$unset": { "message": "" } }
		)


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

		pollname = await sanitizeInput(ctx, pollname)
		if pollname == None:
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

		rolename = await sanitizeInput(ctx, rolename)
		if rolename == None:
			return

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

	# sets limit on submissions per user
	@commands.command(
		help = "Set the limit on submissions to a poll per user.",
		brief = "Set limit on submissions per user."
	)
	@commands.check(is_manager)
	async def submitlimit(self, ctx, limit):

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
		await ctx.send(f"Submission limit for `{poll['name']}` set to `{limit}`!")

	@submitlimit.error
	async def submitlimit_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+setsubmitlimit <submission limit>`")
	
	# sets limit on votes per user
	@commands.command(
		help = "Set the limit on votes to a poll per user.",
		brief = "Set limit on votes per user."
	)
	@commands.check(is_manager)
	async def votelimit(self, ctx, limit):

		if not limit.isnumeric():
			await ctx.send("Vote limit needs to be a number!")
			return
		limit = int(limit)
		
		# return if no polls exist
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

		# update config
		db.polls.update_one(
			{ "_id": poll["_id"] },
			{ "$set": { "vote-limit": limit } }
		)

		# update poll if posted
		if poll["open"]:
			poll_message = await ctx.fetch_message(poll["message"])
			embed = poll_message.embeds[0]
			embed.set_footer(text=f"votes per user: {limit}")
			await poll_message.edit(embed=embed)
			
		await ctx.send(f"Vote limit for `{poll['name']}` set to `{limit}`!")

	@votelimit.error
	async def votelimit_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: `+setvotelimit <vote limit>`")

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
	help = "*Direct messages you a guide on how to use this bot.*",
	brief = "*Direct messages you a guide on how to use this bot.*"
)
async def guide(ctx):
	await ctx.author.send("Check out the guide here: https://thermobot.xyz/#how-to-use")

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
			"vote-limit": 1,
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
		title = "Choose poll:",
		description = desc,
		color = discord.Color.blue()
	)
	embed.set_footer(text=f"Requested by {ctx.author.name}")

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
		title = f"Choose submission from `{poll['name']}`:",
		description = desc,
		color = discord.Color.blue()
	)
	embed.set_footer(text=f"Requested by {ctx.author.name}")

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

# helper function to generate a poll from given poll_id
async def generatePoll(ctx, poll_id):

	# check if submissions exist
	submissions = db.submissions.find({ "poll": poll_id }).sort("text")
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
		if submission["user"] == None:
			desc += f"{emoji} : **{submission['text']}**\n\n"
		else:
			user = await bot.fetch_user(submission["user"])
			desc += f"{emoji} : **{submission['text']}** - {user.mention}\n\n"

		# add matching reaction
		await message.add_reaction(emoji)

	poll = db.polls.find_one({ "_id": poll_id })
	embed = discord.Embed(
		title = f"{poll['name']}:",
		description = desc,
		color = discord.Color.blue()
	)
	embed.set_footer(text=f"votes per user: {poll['vote-limit']}")
	await message.edit(content='', embed=embed)

	# update poll document with poll message id
	db.polls.update_one(
		{ "_id": poll_id },
		{ "$set": { "message": message.id, "open": True } }
	)

async def sanitizeInput(ctx, input):
	# cap string length
	if len(input) > 64:
		await ctx.send(f"Input too long! Limit is 64 characters, current count is `{len(input)}`")
		return None
	chunks = input.split('\n')
	return chunks[0]

# manage per user vote limits
@bot.event
async def on_raw_reaction_add(payload):

	# return if react is from bot
	if payload.user_id == 845376902876626964 or payload.user_id == 843879097050726430:
		return

	# return if reaction not on a poll
	poll = db.polls.find_one({ "message": payload.message_id, "open": True })
	if poll == None:
		return

	# count users votes in poll
	message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
	vote_count = 0
	for reaction in message.reactions:
		users = await reaction.users().flatten()
		if payload.member in users:
			vote_count += 1
	
	# voted more than maximum allowed
	if vote_count > poll["vote-limit"]:
		await payload.member.send(f"You've already reached your maximum votes on the poll `{poll['name']}`. " +
			f"The current maximum is `{poll['vote-limit']}` votes.")

		# print error message if without proper permissions to remove reaction
		if not message.channel.guild.me.guild_permissions.manage_messages:
			await message.channel.send("`Error! I need the Manage Messages permission to remove votes beyond the user vote limit.`")
		else:
			reaction = discord.utils.get(message.reactions, emoji=payload.emoji)
			await reaction.remove(payload.member)

# load cogs
bot.add_cog(Poll(bot))

# load and run token from file
token = open('test-token', 'r').read()
bot.run(token)