# TIO.py

A Discord bot for accessing the [Try It Online](https://tio.run/) API through code blocks.

## Usage

`tio!help` sends information on what commands are supported.
`tio!langs` sends the languages supported; pass a term to search.

There are two ways to execute code. Explicit execution involves pinging the bot and sending a code block with language or an attachment:
```
@TIO.py
\`\`\`py
# the code block language is used to tell which language to execute
print("hi")
\`\`\`
```
Implicit execution is the same, but without the ping. It has no attachment support, and will ignore errors. If it annoys you, you can opt out of implicit execution with `tio!opt implicit off`.

## Hosting

To host, just make a file called `token.txt` and place the bot token in it. As the bot host, you gain access to two other commands, `tio!update` and `tio!jsk`.
`tio!update` runs `git pull` and shuts down the bot (expecting to be restarted by a process manager). `tio!jsk` is Jishaku, a collection of debugging utilities; you probably won't need this.

## Invite

You can invite the bot [here](https://discord.com/api/oauth2/authorize?client_id=709333181983096834&permissions=0&scope=bot).

It requires the permissions Read Messages and Send Messages to work, and also wants Add Reactions (for the delete and attach buttons on responses) and Attach Files (for sending long responses)
