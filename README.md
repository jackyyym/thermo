# Thermo
Customizable D<span>iscord.py<span> bot created to handle polls with user submission. Stores each guild's data in the `data` folder in a JSON file named by the guild's ID.
<br><br>

# Features:
- automatic generation of poll using guild's emoji
- configurable memeber role to control who can place submissions
- user submission limits
- toggleable manager permissions to use certain commants

*Upcoming:*
- Configureable user submission limits, with managers being able to ignore those limits.
- Smarter interaction with the bot via reacting to messages.
- Music bot functionality?
<br><br>

# Commands:
## Group Poll
*Member Commands:*
- **submit** \<submission> - *Submit your choice for the current poll.*
- **unsubmit** - *Remove your submission from the current poll.*
- **submissions** - *List current poll submissions.*

*Manager Commands:*
- **createpoll** - *Generate a poll from user submissions.*
- **newpoll** \<pollname> - *Clear current submissions to begin a new poll.*
- **renamepoll** \<pollname> - *Rename the current poll.*
- **setrole** \<rolename> - *Set the poll member role.*
- **unsetrole** - *Unsets poll member role.*
- **togglemanager** \<member> - *Toggle manager permissions for a user.*

## Misc:
- **ping** - *Display current ping.*
- **help** - *Display list of commands.*
- **help** \<command> - *Get info about a particular command.*
<br><br>

# JSON Data Structure:
`{guild id}.json`:
- `config` - stores configureation info
	- `managers[]` - list of current managers stored as array of user IDs 
	- `memberrole` - current poll member role; anyone can submit to polls if none exists
- `submissions[]` - array of current submissions, where each element has the structure:
	- `submission` - name of submission as a string
	- `user` - user ID of the one who submitted this entry
- `pollname` - name of current poll as a string

