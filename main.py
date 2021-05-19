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

# cog for poll commands
class GroupPoll(commands.Cog, name="Group Poll"):

	# check if user is a poll manager or admin
	# TODO: move output to dedicated error function for checks
	async def is_manager(ctx):

		# return true if its me
		if ctx.author.id == 177512809469313033:
			return True

		# load guild json
		data = readData(ctx.guild.id)

		# return false if user is non a manager nor admin
		if ctx.author.id not in data["config"]["managers"] and not ctx.author.guild_permissions.administrator:
			await ctx.send("Only managers and admins can use this command.")
			return False
		else:
			return True

	# check if user has member role
	async def is_member(ctx):

		# load guild json
		data = readData(ctx.guild.id)

		# check if member role is set
		if "memberrole" not in data["config"]:
			return True
		role = ctx.guild.get_role(data["config"]["memberrole"])

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

		# load guild json
		data = readData(ctx.guild.id)

		# ensure this is users first submission
		# TODO: allow them to react to overwrite submission
		for item in data["submissions"]:
			if item["user"] == ctx.author.id:
				await ctx.send("You've already made a submission! Use `unsubmit` to remove it first.")
				return
		
		# add submission to data, write to file
		data["submissions"].append({"submission":submission, "user":ctx.author.id})
		writeData(ctx.guild.id, data)

		await ctx.send(f"Submitted to poll `{data['pollname']}`! Use `submissions` to see a list of submissions.")

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
				await ctx.send(f"Submission removed from `{data['pollname']}`! Use `submit` to place a new submission")
			else:
				await ctx.send("Submission not found!")
				return
		
		# write to file
		writeData(ctx.guild.id, data)

	# view list of current poll submissions
	# TODO: configure user submission limit
	# TODO: managers can ignore submission limit
	@commands.command(
		help = "Display a list of all current poll submissions. Does not create a poll.",
		brief = "List current poll submissions."
	)
	@commands.check(is_member)
	async def submissions(self, ctx):

		# load guild json
		data = readData(ctx.guild.id)

		# return if no submissions yet
		if len(data["submissions"]) == 0:
			await ctx.send("No submissions yet! Use `submit` to place a submission.")
			return

		# format and send response as blockquote
		response = f"\n>>> *{data['pollname']}*\n"
		for item in data["submissions"]:
			user = await bot.fetch_user(item["user"])
			response += f"{item['submission']} - {user.name}\n"
		await ctx.send(response)

	# creates a poll from user submissions
	@commands.command(
		help = "Create a poll from user submissions. Does not delete submissions.",
		brief = "Create a poll from user submissions."
	)
	@commands.check(is_manager)
	async def createpoll(self, ctx):

		# load guild json
		data = readData(ctx.guild.id)
		
		message = await ctx.send('`generating poll`')

		# load title from data, generic if none
		try:
			pollname = f"{data['pollname']}:"
		except:
			pollname = "Poll:"

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
			desc += f"{emoji} : **{item['submission']}** - {user.mention}\n\n"

			# add matching reaction
			await message.add_reaction(emoji)

		embed = discord.Embed(
			title = pollname,
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

		# load guild json
		data = readData(ctx.guild.id)

		# set title and clear submissions
		data["pollname"] = pollname
		data["submissions"] = []

		# write to file
		writeData(ctx.guild.id, data)

		await ctx.send(f"Ready to recieve submissions for the poll `{pollname}`! Previous submissions have been deleted.")
	
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
		data = readData(ctx.guild.id)
		data["pollname"] = pollname
		writeData(ctx.guild.id, data)
		await ctx.send(f"Ready to recieve submissions for the poll `{pollname}`! Previous submissions have been deleted.")
	
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

		data["config"]["memberrole"] = role.id
		writeData(ctx.guild.id, data)

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

		# load guild json
		data = readData(ctx.guild.id)

		# check if member role is set
		if "memberrole" not in data["config"]:
			await ctx.send("Poll member role not set!")
			return

		# check if member role exists in guild
		role = discord.utils.get(ctx.guild.roles, id=data["config"]["memberrole"])
		if role == None:
			await ctx.send("Could not find the poll member role!")
			return

		data["config"].pop("memberrole")
		writeData(ctx.guild.id, data)

		await ctx.send(f"The poll member role has been unset! Anyone can submit to polls now.")

	# toggle manager permissions for a user
	@commands.command(	
		help = "Toggle manager permissions for a user. Managers can use commands to create and delete polls.",
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

# load cogs
bot.add_cog(GroupPoll(bot))

# load and run token from file
token = open('token', 'r').read()
bot.run(token)