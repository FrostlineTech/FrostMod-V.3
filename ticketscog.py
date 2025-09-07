#the point of this cog is to allow users to open tickets for support so server admins can have thier own ticket system
#first command will be /ticketsetup which opens an interactive UI to choose what channel users go to when they open a ticket once this setup has been saved it uses the branding and posts an embed in the ticket channel where users can press a button to open a ticket
#once the button has been pressed it opens a private channel between the user and the server admin and posts an embed with the branding with buttons to close the ticket and save the ticket transcriopt to the database
#database column ticket_transcript user id of who opened the ticket, username, ticket transcript, time opened, time closed, guild id, guild name, user id of admin who closed it, admin username
#ensure that the ticket channel column gets saved to our already established Server_settings table impotently in the main file 
#create a dedicated ticket column for the rest
#ensure all commands are reigistered globally in the main file aswell as cogs 

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
from typing import Optional, List, Dict, Union
from branding import BRAND_COLOR, FOOTER_TEXT, GREEN, YELLOW, RED
import logging
import traceback
import io
import os
import asyncpg

class TicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="Create Ticket", emoji="🎫", custom_id="create_ticket")
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # Create ticket handler instance
            ticket_handler = TicketHandler(self.view.cog)
            await ticket_handler.create_ticket(interaction)
        except Exception as e:
            logging.error(f"Error in ticket button callback: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"Error creating ticket: {e}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(TicketButton())

class CloseTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="Close Ticket", emoji="🔒", custom_id="close_ticket")
    
    async def callback(self, interaction: discord.Interaction):
        ticket_handler = TicketHandler(self.view.cog)
        await ticket_handler.close_ticket(interaction)

class SaveTranscriptButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="Save Transcript", emoji="📝", custom_id="save_transcript")
    
    async def callback(self, interaction: discord.Interaction):
        ticket_handler = TicketHandler(self.view.cog)
        await ticket_handler.save_transcript(interaction)

class TicketActionsView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(CloseTicketButton())
        self.add_item(SaveTranscriptButton())

class TicketHandler:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
    
    async def create_ticket(self, interaction: discord.Interaction):
        # Check if user already has an open ticket
        async with self.bot.pool.acquire() as conn:
            existing_ticket = await conn.fetchrow(
                "SELECT ticket_id FROM tickets WHERE user_id = $1 AND guild_id = $2 AND status = 'open'",
                interaction.user.id, interaction.guild.id
            )
            
            if existing_ticket:
                return await interaction.response.send_message(
                    "You already have an open ticket. Please use that ticket instead.", 
                    ephemeral=True
                )
            
            # Get ticket channel from guild settings
            guild_settings = await conn.fetchrow(
                "SELECT ticket_channel_id FROM general_server WHERE guild_id = $1",
                interaction.guild.id
            )
            
            if not guild_settings or not guild_settings['ticket_channel_id']:
                return await interaction.response.send_message(
                    "Ticket system hasn't been set up yet. Please ask an admin to run /ticketsetup first.",
                    ephemeral=True
                )
            
            # Create private channel
            try:
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                }
                
                # Add admin permissions
                admin_role = discord.utils.get(interaction.guild.roles, name="Admin")
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                
                mod_role = discord.utils.get(interaction.guild.roles, name="Moderator")
                if mod_role:
                    overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                
                ticket_channel = await interaction.guild.create_text_channel(
                    f"ticket-{interaction.user.name}",
                    overwrites=overwrites,
                    reason=f"Ticket created by {interaction.user}"
                )
                
                # Create ticket in database
                ticket_id = await conn.fetchval(
                    """
                    INSERT INTO tickets (user_id, username, guild_id, guild_name, ticket_channel_id)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING ticket_id
                    """,
                    interaction.user.id,
                    str(interaction.user),
                    interaction.guild.id,
                    interaction.guild.name,
                    ticket_channel.id
                )
                
                # Send confirmation message
                await interaction.response.send_message(
                    f"Your ticket has been created! Go to {ticket_channel.mention}", 
                    ephemeral=True
                )
                
                # Send welcome message in ticket channel
                embed = discord.Embed(
                    title=f"Ticket #{ticket_id}",
                    description=f"Thank you for creating a ticket, {interaction.user.mention}. Support staff will be with you shortly.",
                    color=BRAND_COLOR
                )
                embed.set_footer(text=FOOTER_TEXT)
                embed.add_field(name="User", value=str(interaction.user), inline=True)
                embed.add_field(name="Created At", value=discord.utils.format_dt(datetime.datetime.now(), style="F"), inline=True)
                
                view = TicketActionsView(self.cog)
                await ticket_channel.send(embed=embed, view=view)
                
                # Mention user in ticket channel
                await ticket_channel.send(f"{interaction.user.mention} Welcome to your ticket!")
                
            except Exception as e:
                logging.error(f"Error creating ticket channel: {e}")
                traceback.print_exc()
                await interaction.response.send_message(
                    f"Error creating ticket: {str(e)}", 
                    ephemeral=True
                )
    
    async def close_ticket(self, interaction: discord.Interaction):
        try:
            # Check if this is a ticket channel
            async with self.bot.pool.acquire() as conn:
                ticket = await conn.fetchrow(
                    "SELECT * FROM tickets WHERE ticket_channel_id = $1 AND status = 'open'",
                    interaction.channel_id
                )
                
                if not ticket:
                    return await interaction.response.send_message(
                        "This doesn't appear to be an open ticket channel.", 
                        ephemeral=True
                    )
                
                # Mark ticket as closed in database
                await conn.execute(
                    """
                    UPDATE tickets 
                    SET status = 'closed', time_closed = $1, admin_id = $2, admin_username = $3
                    WHERE ticket_id = $4
                    """,
                    datetime.datetime.now(),
                    interaction.user.id,
                    str(interaction.user),
                    ticket['ticket_id']
                )
                
                # Send closing message
                embed = discord.Embed(
                    title=f"Ticket #{ticket['ticket_id']} Closed",
                    description=f"This ticket has been closed by {interaction.user.mention}.",
                    color=GREEN
                )
                embed.set_footer(text=FOOTER_TEXT)
                embed.add_field(name="Opened By", value=f"<@{ticket['user_id']}> ({ticket['username']})", inline=True)
                embed.add_field(name="Closed By", value=str(interaction.user), inline=True)
                embed.add_field(name="Closed At", value=discord.utils.format_dt(datetime.datetime.now(), style="F"), inline=True)
                
                await interaction.response.send_message(embed=embed)
                
                # Wait briefly then delete the channel
                await asyncio.sleep(5)
                await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
                
        except Exception as e:
            logging.error(f"Error closing ticket: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"Error closing ticket: {str(e)}", 
                ephemeral=True
            )
    
    async def save_transcript(self, interaction: discord.Interaction):
        try:
            # Check if this is a ticket channel
            async with self.bot.pool.acquire() as conn:
                ticket = await conn.fetchrow(
                    "SELECT * FROM tickets WHERE ticket_channel_id = $1",
                    interaction.channel_id
                )
                
                if not ticket:
                    return await interaction.response.send_message(
                        "This doesn't appear to be a ticket channel.", 
                        ephemeral=True
                    )
                
                # Fetch all messages from channel
                messages = []
                async for message in interaction.channel.history(limit=500, oldest_first=True):
                    timestamp = discord.utils.format_dt(message.created_at, style="T")
                    content = message.content or "[No text content]"
                    
                    # Handle attachments
                    if message.attachments:
                        content += "\n" + "\n".join([f"[Attachment: {a.filename}]" for a in message.attachments])
                    
                    # Handle embeds
                    if message.embeds:
                        for embed in message.embeds:
                            if embed.title:
                                content += f"\n[Embed: {embed.title}]"
                    
                    messages.append(f"[{timestamp}] {message.author}: {content}")
                
                transcript_text = "\n".join(messages)
                
                # Save transcript to database
                await conn.execute(
                    "UPDATE tickets SET ticket_transcript = $1 WHERE ticket_id = $2",
                    transcript_text,
                    ticket['ticket_id']
                )
                
                # Create file for user
                transcript_file = discord.File(
                    io.StringIO(transcript_text),
                    filename=f"ticket-{ticket['ticket_id']}-transcript.txt"
                )
                
                await interaction.response.send_message(
                    "Transcript saved to database. Here's a copy:",
                    file=transcript_file
                )
                
        except Exception as e:
            logging.error(f"Error saving transcript: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"Error saving transcript: {str(e)}", 
                ephemeral=True
            )

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("frostmod.tickets")
        
    @app_commands.command(name="ticketsetup", description="Setup the ticket system for your server")
    @app_commands.describe(channel="The channel where users can create tickets")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketsetup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        try:
            # Save ticket channel to database
            async with self.bot.pool.acquire() as conn:
                # Check if server exists in database
                server_exists = await conn.fetchrow(
                    "SELECT 1 FROM general_server WHERE guild_id = $1",
                    interaction.guild.id
                )
                
                if server_exists:
                    await conn.execute(
                        "UPDATE general_server SET ticket_channel_id = $1 WHERE guild_id = $2",
                        channel.id,
                        interaction.guild.id
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO general_server 
                        (guild_id, guild_name, ticket_channel_id) 
                        VALUES ($1, $2, $3)
                        """,
                        interaction.guild.id,
                        interaction.guild.name,
                        channel.id
                    )
                
                # Create ticket embed and button
                embed = discord.Embed(
                    title="Support Tickets",
                    description="Need assistance? Click the button below to create a support ticket and our team will help you as soon as possible.",
                    color=BRAND_COLOR
                )
                embed.set_footer(text=FOOTER_TEXT)
                
                view = TicketView(self)
                
                # Send embed to ticket channel
                await channel.send(embed=embed, view=view)
                
                await interaction.response.send_message(
                    f"Ticket system successfully set up in {channel.mention}!",
                    ephemeral=True
                )
                
        except Exception as e:
            self.log.error(f"Error in ticketsetup: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"Error setting up ticket system: {str(e)}", 
                ephemeral=True
            )
    
    @app_commands.command(name="ticketstats", description="View statistics about tickets in your server")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketstats(self, interaction: discord.Interaction):
        try:
            async with self.bot.pool.acquire() as conn:
                # Get ticket stats
                total_tickets = await conn.fetchval(
                    "SELECT COUNT(*) FROM tickets WHERE guild_id = $1",
                    interaction.guild.id
                )
                
                open_tickets = await conn.fetchval(
                    "SELECT COUNT(*) FROM tickets WHERE guild_id = $1 AND status = 'open'",
                    interaction.guild.id
                )
                
                closed_tickets = await conn.fetchval(
                    "SELECT COUNT(*) FROM tickets WHERE guild_id = $1 AND status = 'closed'",
                    interaction.guild.id
                )
                
                # Create stats embed
                embed = discord.Embed(
                    title="Ticket Statistics",
                    color=BRAND_COLOR,
                    description=f"Statistics for {interaction.guild.name}"
                )
                embed.add_field(name="Total Tickets", value=str(total_tickets), inline=True)
                embed.add_field(name="Open Tickets", value=str(open_tickets), inline=True)
                embed.add_field(name="Closed Tickets", value=str(closed_tickets), inline=True)
                embed.set_footer(text=FOOTER_TEXT)
                
                await interaction.response.send_message(embed=embed)
                
        except Exception as e:
            self.log.error(f"Error in ticketstats: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"Error fetching ticket statistics: {str(e)}", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))