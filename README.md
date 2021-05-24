# Thermo
Customizable and robust Discord bot created to handle polls with user submission. Written in Python, powered by D<span>iscord.py<span> and MongoDB.

[Bot Invite Link](https://discord.com/api/oauth2/authorize?client_id=843879097050726430&permissions=268511296&scope=bot)
<br><br>

# Features:
- Create and manage multiple polls.
- Automatic vote counting, vote management, and customizable per-user vote limits.
- Users can submit poll options, and per-user submission limits can be configured. 
- Automatic generation of poll using guild's emoji.
- Easy to use reaction-based interface.
- Configurable member role to control who can place poll submissions and vote on polls.
- Toggle manager permissions for non-admins to create and manage polls.

*Upcoming:*
- Create an entire poll with a single `createpoll` command rather than going through the user submission process.
- Managers can remove other user's submissions.
<br><br>

# How to Use:
1. Create and name your poll with `+createpoll <poll name>`.
	- optional: use `setsubmitlimit <limit>` and/or `setvotelimit <limit>` to control how
	many times users can submit to and vote on polls.
2. Users can now submit poll options with `+submit <submission>`.
3. Once submissions are received, generate and open the poll to voting with `+openpoll`
4. Once all votes are cast, use `+closepoll` to end voting and display the top choices from the poll.
5. Now use `+deletepoll` to delete the closed poll.
	- optional: rather than deleting the poll you can continue user submission and reopen the poll at a later time.
<br><br>

# Commands:
### **Group Poll:**
*Member Commands*
- `submit <submission>` - *Submit your choice for the current poll.*
- `unsubmit` - *Remove your submission from the current poll.*
- `submissions` - *List current poll submissions.*

*Admin/Manager Commands*
- `newpoll <poll name>` - *Clear current submissions to begin a new poll.*
- `openpoll` – *Open a poll to begin vote collection.*
- `closepoll` – Close poll and count votes.
- `deletepoll` – Delete closed poll.
- `renamepoll <poll name>` - *Rename the current poll.*
- `setrole <role name>` - *Set the poll member role.*
- `unsetrole` - *Unsets poll member role.*
- `setsubmitlimit <limit>` - *Set limit on submissions per user to a single poll.*
- `setvotelimit <limit>` - *Set limit on votes per user on a single poll.*
- `togglemanager <member>` - *Toggle manager permissions for a user.*

### **Misc:**
- `ping` - *Display current ping.*
- `help` - *Display list of commands.*
- `help <command>` - *Get info about a particular command.*
<br><br>
