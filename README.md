Customizable and robust Discord bot created to handle polls with user submission. Written in Python, powered by D<span>iscord.py<span> and MongoDB.

[Bot Invite Link](https://discord.com/api/oauth2/authorize?client_id=843879097050726430&permissions=268511296&scope=bot)
<br><br>

# Features:
- Create and manage multiple polls.
- Automatic vote counting, vote management, and customizable per-user vote limits.
- Create an entire poll with `createpoll`, or let users submit poll options with `+newpoll`
- Users can submit poll options, and per-user submission limits can be configured. 
- Automatic generation of poll using guild's emoji.
- Easy to use reaction-based interface.
- Configurable member role to control who can place poll submissions and vote on polls.
- Toggle manager permissions for non-admins to create and manage polls.

*Upcoming:*
- Managers can remove other user's submissions.
<br><br>

# How to Use:
*Normal Use:*
1. Create your poll with the command `+newpoll <poll name> <option 1> ... <option n>` (inputs are separated by quotes).
	- *example:*  `+createpoll "Favorite Color" "Red" "Green" "Blue"`
	- *optional:* set the amount of votes users can cast with `+setvotelimit <vote limit>`, default is 1 vote per user.
2. Once votes are cast, use the command `+closepoll` to end voting and output the poll results.<br><br>

*With User Submission:*
1. Create and name your poll with `+newpoll groupinput <poll name>`.
	- optional: use `+setsubmitlimit <limit>` and/or `+setvotelimit <limit>` to control how
	many times users can submit to and vote on the created poll.
2. Users can now submit poll options with `+submit <submission>`.
3. Once submissions are received, generate and open the poll to voting with `+openpoll`
4. Once all votes are cast, use `+closepoll` to end voting and output the poll results.
5. Now use `+deletepoll` to delete the closed poll.
	- *optional:* rather than delete the poll, you can instead continue submissions of poll options and/or do another round of vote collecting later.
<br><br>

# Commands:
### **Group Poll:**
*Member Commands:*
- `submit <submission>` - *Submit your choice for the current poll.*
- `unsubmit` - *Remove your submission from the current poll.*
- `submissions` - *List current poll submissions.*

*Admin/Manager Commands:*
- `newpoll <poll name> <option 1> ... <option n>` - *Create a new poll from a list of options.*
- `newpoll groupinput <poll name>` - *Create a new poll open to user submission.*
- `launchpoll` – *Launch a poll to begin vote collection.*
- `closepoll` – Close poll and count votes.
- `deletepoll` – Delete closed poll.
- `renamepoll <poll name>` - *Rename the current poll.*
- `setrole <role name>` - *Set the poll member role.*
- `unsetrole` - *Unsets poll member role.*
- `submitlimit <limit>` - *Set limit on submissions per user to a single poll.*
- `votelimit <limit>` - *Set limit on votes per user on a single poll.*
- `togglemanager <member>` - *Toggle manager permissions for a user.*

### **Misc:**
- `guide` - *Links to the how-to-use webpage.*
- `help` - *Display list of commands.*
- `help <command>` - *Get info about a particular command.*
- `ping` - *Display current ping.*
<br><br>
