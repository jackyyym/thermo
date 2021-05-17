import discord
import json

client = discord.Client()

@client.event
async def on_message(message):
	if message.author == client.user:
		return

	if message.content.startswith('+ping'):
		await message.channel.send('pong!')

token = open("token", "r").read()
client.run(token)