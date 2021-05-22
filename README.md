# Thermo
Customizable Discord bot created to handle polls with user submission. Written in Python, powered by D<span>iscord.py<span> and MongoDB.

[Bot Invite Link](https://discord.com/api/oauth2/authorize?client_id=843879097050726430&permissions=268511296&scope=bot)
<br><br>

# Features:
- Create and manage multiple polls.
- Automatic generation of poll using guild's emoji.
- Configurable member role to control who can place submissions.
- Configurable user submission limits.
- Toggle manager permissions for users to use certain commands.

*Upcoming:*
- Automatic counting of votes on a poll.
- Manage how many times a user can vote on a poll.
- Managers can remove other user's submissions.
- Smarter interaction with the bot via reacting to messages.
<br><br>

# Commands:
### **Group Poll:**
*Member Commands*
- `submit <submission>` - *Submit your choice for the current poll.*
- `unsubmit` - *Remove your submission from the current poll.*
- `submissions` - *List current poll submissions.*

*Manager Commands*
- `createpoll` - *Generate a poll from user submissions.*
- `newpoll <pollname>` - *Clear current submissions to begin a new poll.*
- `renamepoll <pollname>` - *Rename the current poll.*
- `setrole <rolename>` - *Set the poll member role.*
- `unsetrole` - *Unsets poll member role.*
- `setlimit` - *Set limit on submissions per user.*
- `togglemanager <member>` - *Toggle manager permissions for a user.*

### **Misc:**
- `ping` - *Display current ping.*
- `help` - *Display list of commands.*
- `help <command>` - *Get info about a particular command.*
<br><br>
