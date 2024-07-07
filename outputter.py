class StandardOutputter:
    def __init__(self, message):
        self.message = message
        self.output_message = None
        self.are_reactions = False

    async def send(self, *args, **kwargs):
        self.output_message = await self.message.channel.send(*args, **kwargs)

    def can_edit(self):
        return self.output_message

    async def edit(self, *args, **kwargs):
        await self.output_message.edit(*args, **kwargs)

    async def delete(self):
        if self.output_message:
            await self.output_message.delete()
            self.output_message = None

    async def clear_reactions(self):
        if self.are_reactions:
            await self.message.clear_reactions()
            self.are_reactions = False

    async def add_reaction(self, reaction):
        self.are_reactions = True
        await self.message.add_reaction(reaction)


class InteractionOutputter:
    def __init__(self, interaction):
        self.interaction = interaction

    async def edit(self, *args, **kwargs):
        # we are editing the original defer message
        await self.interaction.edit_original_response(*args, **kwargs)

    def can_edit(self):
        return True

    async def delete(self):
        pass
