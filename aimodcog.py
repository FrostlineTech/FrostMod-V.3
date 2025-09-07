#this file is used to connect to the local deepseek model look at .env for all connection values, 
#this file is also where all ai moderation features are handled ensure ai events are logged asewell in the designates logs channel analyze everything and look at the current codebase structure
#i want the ai to be able to read messages and choose to delete them and remind the user to be respectful with a 2 second message if they are rude, racist, sexist or any other form of harassment 
#register /disabletheta command to disable ai moderation per server ensure it is registered in the main file frostmodv3.py
#any new database features ensure to check the main file as we have redudancy code to create the columns if they do not exist

import os
import json
import asyncio
import logging
import time
import platform
import re
import random
import csv
import os.path
from datetime import datetime, timedelta, timezone
import psutil

import discord
import aiohttp
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT, GREEN, YELLOW, RED


class AIModSettingsView(discord.ui.View):
    """A view with interactive controls for server AI moderation settings."""
    
    def __init__(self, cog, guild_id, settings):
        super().__init__(timeout=300)  # Settings panel available for 5 minutes
        self.cog = cog
        self.guild_id = guild_id
        self.settings = settings.copy()  # Make a copy to avoid modifying the original
        self.guild_name = ""
        
        # Initialize state for temperature buttons
        self._adjust_button_states()
        
    def _adjust_button_states(self):
        """Update button states based on current settings."""
        # This will be called after initialization to set the initial state
        # and after any setting change to update button states
        pass
        
    async def on_timeout(self):
        """Disable all components when the view times out."""
        for item in self.children:
            item.disabled = True


class ChannelModSettingsView(discord.ui.View):
    """A view with interactive controls for channel-specific AI moderation settings."""
    
    def __init__(self, cog, guild_id, channel_id, settings, override_enabled=False):
        super().__init__(timeout=300)  # Settings panel available for 5 minutes
        self.cog = cog
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.settings = settings.copy()  # Make a copy to avoid modifying the original
        self.override_enabled = override_enabled
        self.guild_name = ""
        self.channel_name = ""
        
    async def on_timeout(self):
        """Disable all components when the view times out."""
        for item in self.children:
            item.disabled = True
    
    @discord.ui.button(label="Enable Override", style=discord.ButtonStyle.primary, row=0)
    async def enable_override_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable channel-specific overrides."""
        # Get current channel name for logging
        channel = interaction.guild.get_channel(self.channel_id)
        self.channel_name = channel.name if channel else f"Channel {self.channel_id}"
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        try:
            async with self.cog.bot.pool.acquire() as conn:
                # Check if entry exists
                row = await conn.fetchrow(
                    """SELECT * FROM channel_mod_settings 
                    WHERE guild_id = $1 AND channel_id = $2""",
                    self.guild_id, self.channel_id
                )
                
                if row:
                    # Update existing entry
                    await conn.execute(
                        """UPDATE channel_mod_settings 
                        SET override_enabled = true, updated_at = NOW()
                        WHERE guild_id = $1 AND channel_id = $2""",
                        self.guild_id, self.channel_id
                    )
                else:
                    # Create new entry
                    await conn.execute(
                        """INSERT INTO channel_mod_settings
                        (guild_id, channel_id, override_enabled, ai_moderation_enabled)
                        VALUES ($1, $2, true, $3)""",
                        self.guild_id, self.channel_id, self.settings["enabled"]
                    )
                
                # Update our state
                self.override_enabled = True
                
                # Update the embed to show overrides are active
                embed = interaction.message.embeds[0]
                
                for i, field in enumerate(embed.fields):
                    if field.name == "Override Status":
                        embed.set_field_at(i, name="Override Status", value="✅ Active", inline=False)
                        break
                
                # Update the UI and show success message
                await interaction.response.edit_message(embed=embed, view=self)
                await interaction.followup.send(
                    f"Channel-specific moderation settings enabled for #{self.channel_name}", 
                    ephemeral=True
                )
                
                self.cog.logger.info(
                    f"Channel overrides enabled for #{self.channel_name} in {self.guild_name} by {interaction.user.name}"
                )
                
        except Exception as e:
            self.cog.logger.error(f"Error enabling channel moderation override: {e}")
            await interaction.response.send_message("An error occurred while updating settings", ephemeral=True)
    
    @discord.ui.button(label="Disable Override", style=discord.ButtonStyle.secondary, row=0)
    async def disable_override_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable channel-specific overrides."""
        # Get current channel name for logging
        channel = interaction.guild.get_channel(self.channel_id)
        self.channel_name = channel.name if channel else f"Channel {self.channel_id}"
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        try:
            async with self.cog.bot.pool.acquire() as conn:
                # Update the settings
                await conn.execute(
                    """UPDATE channel_mod_settings 
                    SET override_enabled = false, updated_at = NOW()
                    WHERE guild_id = $1 AND channel_id = $2""",
                    self.guild_id, self.channel_id
                )
                
                # Update our state
                self.override_enabled = False
                
                # Update the embed to show overrides are inactive
                embed = interaction.message.embeds[0]
                
                for i, field in enumerate(embed.fields):
                    if field.name == "Override Status":
                        embed.set_field_at(i, name="Override Status", value="❌ Inactive", inline=False)
                        break
                
                # Get the server-wide settings to show what will apply now
                server_settings = await self.cog._get_guild_settings(self.guild_id)
                
                # Update other fields to reflect server settings
                for i, field in enumerate(embed.fields):
                    if field.name == "Moderation Status":
                        status = "Enabled" if server_settings["enabled"] else "Disabled"
                        embed.set_field_at(
                            i, 
                            name="Moderation Status",
                            value=f"{'🟢' if server_settings['enabled'] else '🔴'} **{status}**",
                            inline=True
                        )
                    elif field.name == "Temperature":
                        embed.set_field_at(
                            i,
                            name="Temperature",
                            value=f"**{server_settings['temperature']:.1f}**",
                            inline=True
                        )
                    elif field.name == "Actions":
                        embed.set_field_at(
                            i,
                            name="Actions",
                            value=(
                                f"**Low Severity:** {server_settings['low_severity_action']}\n"
                                f"**Medium Severity:** {server_settings['med_severity_action']}\n"
                                f"**High Severity:** {server_settings['high_severity_action']}"
                            ),
                            inline=False
                        )
                
                # Update the UI and show success message
                await interaction.response.edit_message(embed=embed, view=self)
                await interaction.followup.send(
                    f"Channel-specific moderation settings disabled for #{self.channel_name}", 
                    ephemeral=True
                )
                
                self.cog.logger.info(
                    f"Channel overrides disabled for #{self.channel_name} in {self.guild_name} by {interaction.user.name}"
                )
                
        except Exception as e:
            self.cog.logger.error(f"Error disabling channel moderation override: {e}")
            await interaction.response.send_message("An error occurred while updating settings", ephemeral=True)
            
    @discord.ui.button(label="Enable Moderation", style=discord.ButtonStyle.success, row=1)
    async def enable_moderation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable AI moderation for this channel."""
        # Check if override is enabled
        if not self.override_enabled:
            await interaction.response.send_message(
                "You need to enable channel overrides first before changing settings.", 
                ephemeral=True
            )
            return

        # Get channel and guild names
        channel = interaction.guild.get_channel(self.channel_id)
        self.channel_name = channel.name if channel else f"Channel {self.channel_id}"
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        try:
            # Update settings in database
            async with self.cog.bot.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE channel_mod_settings 
                    SET ai_moderation_enabled = true, updated_at = NOW()
                    WHERE guild_id = $1 AND channel_id = $2""",
                    self.guild_id, self.channel_id
                )
            
            # Update local settings
            self.settings["enabled"] = True
            
            # Update UI
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Moderation Status":
                    embed.set_field_at(i, name="Moderation Status", value="🟢 **Enabled**", inline=True)
                    break
            
            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(
                f"AI moderation enabled for #{self.channel_name}", 
                ephemeral=True
            )
            
            self.cog.logger.info(
                f"Channel AI moderation enabled for #{self.channel_name} in {self.guild_name} by {interaction.user.name}"
            )
            
        except Exception as e:
            self.cog.logger.error(f"Error enabling channel AI moderation: {e}")
            await interaction.response.send_message("An error occurred while updating settings", ephemeral=True)
    
    @discord.ui.button(label="Disable Moderation", style=discord.ButtonStyle.danger, row=1)
    async def disable_moderation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable AI moderation for this channel."""
        # Check if override is enabled
        if not self.override_enabled:
            await interaction.response.send_message(
                "You need to enable channel overrides first before changing settings.", 
                ephemeral=True
            )
            return

        # Get channel and guild names
        channel = interaction.guild.get_channel(self.channel_id)
        self.channel_name = channel.name if channel else f"Channel {self.channel_id}"
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        try:
            # Update settings in database
            async with self.cog.bot.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE channel_mod_settings 
                    SET ai_moderation_enabled = false, updated_at = NOW()
                    WHERE guild_id = $1 AND channel_id = $2""",
                    self.guild_id, self.channel_id
                )
            
            # Update local settings
            self.settings["enabled"] = False
            
            # Update UI
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Moderation Status":
                    embed.set_field_at(i, name="Moderation Status", value="🔴 **Disabled**", inline=True)
                    break
            
            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(
                f"AI moderation disabled for #{self.channel_name}", 
                ephemeral=True
            )
            
            self.cog.logger.info(
                f"Channel AI moderation disabled for #{self.channel_name} in {self.guild_name} by {interaction.user.name}"
            )
            
        except Exception as e:
            self.cog.logger.error(f"Error disabling channel AI moderation: {e}")
            await interaction.response.send_message("An error occurred while updating settings", ephemeral=True)
    
    @discord.ui.button(label="Stricter (0.2)", style=discord.ButtonStyle.secondary, row=2)
    async def stricter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set stricter moderation (lower temperature) for this channel."""
        # Check if override is enabled
        if not self.override_enabled:
            await interaction.response.send_message(
                "You need to enable channel overrides first before changing settings.", 
                ephemeral=True
            )
            return
        
        # Get channel and guild names
        channel = interaction.guild.get_channel(self.channel_id)
        self.channel_name = channel.name if channel else f"Channel {self.channel_id}"
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        try:
            # Update settings in database
            async with self.cog.bot.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE channel_mod_settings 
                    SET ai_temperature_threshold = 0.2, updated_at = NOW()
                    WHERE guild_id = $1 AND channel_id = $2""",
                    self.guild_id, self.channel_id
                )
            
            # Update local settings
            self.settings["temperature"] = 0.2
            
            # Update UI
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Temperature":
                    embed.set_field_at(i, name="Temperature", value=f"**{self.settings['temperature']:.1f}**", inline=True)
                    break
            
            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(
                f"AI moderation strictness set to 0.2 (stricter) for #{self.channel_name}", 
                ephemeral=True
            )
            
        except Exception as e:
            self.cog.logger.error(f"Error updating channel temperature: {e}")
            await interaction.response.send_message("An error occurred while updating settings", ephemeral=True)
            
    @discord.ui.button(label="Balanced (0.4)", style=discord.ButtonStyle.secondary, row=2)
    async def balanced_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set balanced moderation (medium temperature) for this channel."""
        # Check if override is enabled
        if not self.override_enabled:
            await interaction.response.send_message(
                "You need to enable channel overrides first before changing settings.", 
                ephemeral=True
            )
            return
        
        # Get channel and guild names
        channel = interaction.guild.get_channel(self.channel_id)
        self.channel_name = channel.name if channel else f"Channel {self.channel_id}"
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        try:
            # Update settings in database
            async with self.cog.bot.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE channel_mod_settings 
                    SET ai_temperature_threshold = 0.4, updated_at = NOW()
                    WHERE guild_id = $1 AND channel_id = $2""",
                    self.guild_id, self.channel_id
                )
            
            # Update local settings
            self.settings["temperature"] = 0.4
            
            # Update UI
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Temperature":
                    embed.set_field_at(i, name="Temperature", value=f"**{self.settings['temperature']:.1f}**", inline=True)
                    break
            
            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(
                f"AI moderation strictness set to 0.4 (balanced) for #{self.channel_name}", 
                ephemeral=True
            )
            
        except Exception as e:
            self.cog.logger.error(f"Error updating channel temperature: {e}")
            await interaction.response.send_message("An error occurred while updating settings", ephemeral=True)
            
    @discord.ui.button(label="Lenient (0.7)", style=discord.ButtonStyle.secondary, row=2)
    async def lenient_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set lenient moderation (higher temperature) for this channel."""
        # Check if override is enabled
        if not self.override_enabled:
            await interaction.response.send_message(
                "You need to enable channel overrides first before changing settings.", 
                ephemeral=True
            )
            return
        
        # Get channel and guild names
        channel = interaction.guild.get_channel(self.channel_id)
        self.channel_name = channel.name if channel else f"Channel {self.channel_id}"
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        try:
            # Update settings in database
            async with self.cog.bot.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE channel_mod_settings 
                    SET ai_temperature_threshold = 0.7, updated_at = NOW()
                    WHERE guild_id = $1 AND channel_id = $2""",
                    self.guild_id, self.channel_id
                )
            
            # Update local settings
            self.settings["temperature"] = 0.7
            
            # Update UI
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Temperature":
                    embed.set_field_at(i, name="Temperature", value=f"**{self.settings['temperature']:.1f}**", inline=True)
                    break
            
            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(
                f"AI moderation strictness set to 0.7 (lenient) for #{self.channel_name}", 
                ephemeral=True
            )
            
        except Exception as e:
            self.cog.logger.error(f"Error updating channel temperature: {e}")
            await interaction.response.send_message("An error occurred while updating settings", ephemeral=True)
        
        # Update database
        success = await self.cog._update_guild_setting(self.guild_id, self.guild_name, self.settings)
        
        if success:
            # Update embed
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Temperature":
                    embed.set_field_at(i, name="Temperature", value=f"**{self.settings['temperature']:.1f}**", inline=True)
            embed.set_footer(text=f"{FOOTER_TEXT} • Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
            
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send("AI moderation temperature set to 0.4 (balanced).", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to update settings. Please try again.", ephemeral=True)
            
    @discord.ui.button(label="Lenient (0.7)", style=discord.ButtonStyle.secondary, row=1)
    async def lenient_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set lenient moderation (higher temperature)."""
        # Update settings
        self.settings["temperature"] = 0.7
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        # Update database
        success = await self.cog._update_guild_setting(self.guild_id, self.guild_name, self.settings)
        
        if success:
            # Update embed
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Temperature":
                    embed.set_field_at(i, name="Temperature", value=f"**{self.settings['temperature']:.1f}**", inline=True)
            embed.set_footer(text=f"{FOOTER_TEXT} • Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
            
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send("AI moderation temperature set to 0.7 (more lenient).", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to update settings. Please try again.", ephemeral=True)
    
    @discord.ui.button(label="Test Moderation", style=discord.ButtonStyle.primary, row=2)
    async def test_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shortcut to test moderation."""
        # Show a modal to get test message
        modal = TestModerationModal(self.cog)
        await interaction.response.send_modal(modal)


class TestModerationModal(discord.ui.Modal, title="Test AI Moderation"):
    """Modal for entering a test message for moderation."""
    
    test_message = discord.ui.TextInput(
        label="Enter a message to test",
        style=discord.TextStyle.paragraph,
        placeholder="Type a message to test the AI moderation...",
        required=True,
        max_length=1000
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        # Analyze the test message
        await interaction.response.defer(ephemeral=True)
        message = str(self.test_message)
        
        # Show an analysis in progress message
        embed = discord.Embed(
            title="AI Moderation Test", 
            description="Analyzing message...",
            color=YELLOW
        )
        embed.add_field(name="Test Message", value=message, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Analyze the message using server-specific settings
        start_time = time.time()
        guild_id = interaction.guild.id if interaction.guild else None
        is_inappropriate, confidence, reason = await self.cog.analyze_message(message, guild_id=guild_id, debug_mode=True)
        end_time = time.time()
        
        # Show the result
        if is_inappropriate:
            color = RED
            result = "❌ **Violates content policy**"
        else:
            color = GREEN
            result = "✅ **Passes content policy**"
            
        embed = discord.Embed(
            title="AI Moderation Test Results", 
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Test Message", value=message, inline=False)
        embed.add_field(name="Result", value=result, inline=False)
        embed.add_field(name="Confidence", value=f"{confidence:.2%}", inline=True)
        embed.add_field(name="Analysis Time", value=f"{(end_time - start_time) * 1000:.2f}ms", inline=True)
        
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
            
        embed.add_field(
            name="Action", 
            value=f"Message would {'be deleted' if is_inappropriate and confidence > 0.75 else 'not be deleted'}.", 
            inline=False
        )
        embed.set_footer(text=f"Model: {self.cog.model} | {FOOTER_TEXT}")
        
        await interaction.edit_original_response(embed=embed)


class ModFeedbackView(discord.ui.View):
    """A view with buttons for users to provide feedback on moderation actions."""
    
    def __init__(self, cog, user_id, reason, message_content, violation_id=None):
        super().__init__(timeout=None)  # No timeout - persist until acknowledged
        self.cog = cog
        self.user_id = user_id
        self.reason = reason
        self.message_content = message_content
        self.feedback_logged = False
        self.violation_id = violation_id  # Store the violation ID to link feedback
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the affected user to use these buttons."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This feedback is for the affected user only.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Appeal", style=discord.ButtonStyle.danger, emoji="⛔")
    async def wrong_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # First disable the buttons
            for item in self.children:
                item.disabled = True
                
            # Update the message with acknowledged state
            embed = interaction.message.embeds[0]
            embed.add_field(name="Status", value="Appeal submitted", inline=False)
            embed.set_footer(text=f"{FOOTER_TEXT} • Acknowledged at {discord.utils.format_dt(datetime.utcnow())}")
            await interaction.message.edit(view=self, embed=embed)
            
            # Open appeal modal
            await interaction.response.send_modal(AppealModal(self.cog, self.message_content, self.reason, self.violation_id))
            self.cog.logger.info(f"User {interaction.user.name} ({interaction.user.id}) started appeal process for: {self.reason}")
            self.feedback_logged = True
            
            # Record acknowledgment in database
            await self.cog._record_acknowledgment(interaction.guild.id, interaction.user.id, "appealed")
            
            # Record initial feedback entry in the new feedback table
            if self.violation_id:
                try:
                    async with self.cog.bot.pool.acquire() as conn:
                        await conn.execute("""
                            INSERT INTO ai_mod_feedback 
                            (violation_id, user_id, guild_id, feedback_type, created_at)
                            VALUES ($1, $2, $3, $4, NOW())
                        """, self.violation_id, interaction.user.id, interaction.guild.id, "appeal")
                except Exception as db_error:
                    self.cog.logger.error(f"Error recording feedback in database: {db_error}")
            
        except discord.errors.HTTPException as e:
            # Handle any HTTP errors (like label length)
            self.cog.logger.error(f"Error showing appeal modal: {e}")
            try:
                # Try to send a fallback message
                await interaction.response.send_message(
                    "Sorry, there was an issue opening the appeal form. Your feedback has been recorded.", 
                    ephemeral=True
                )
            except:
                pass  # Silently fail if this also fails
    
    @discord.ui.button(label="I acknowledge", style=discord.ButtonStyle.primary, emoji="✅")
    async def understand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # First disable the buttons
            for item in self.children:
                item.disabled = True
                
            # Update the message with acknowledged state
            embed = interaction.message.embeds[0]
            embed.add_field(name="Status", value="Message acknowledged", inline=False)
            embed.set_footer(text=f"{FOOTER_TEXT} • Acknowledged at {discord.utils.format_dt(datetime.utcnow())}")
            await interaction.message.edit(view=self, embed=embed)
            
            # Send acknowledgement message
            await interaction.response.send_message(
                "Thank you for acknowledging this message. We aim to keep this community welcoming for everyone.", 
                ephemeral=True
            )
            self.cog.logger.info(f"User {interaction.user.name} ({interaction.user.id}) acknowledged moderation")
            self.feedback_logged = True
            
            # Record acknowledgment in database
            await self.cog._record_acknowledgment(interaction.guild.id, interaction.user.id, "acknowledged")
            
        except Exception as e:
            self.cog.logger.error(f"Error processing acknowledgement: {e}")


class AppealModal(discord.ui.Modal, title="Appeal Moderation Decision"):
    """Modal for submitting an appeal for a moderated message."""
    
    appeal_reason = discord.ui.TextInput(
        label="Why was this moderation incorrect?",  # Shortened label to be under 45 chars
        style=discord.TextStyle.paragraph,
        placeholder="Please explain why you think your message should not have been removed...",
        required=True,
        max_length=1000
    )
    
    def __init__(self, cog, original_message, removal_reason, violation_id=None):
        super().__init__()
        self.cog = cog
        self.original_message = original_message
        self.removal_reason = removal_reason
        self.violation_id = violation_id  # Store the violation ID to update feedback
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process the submitted appeal."""
        try:
            # Log the appeal
            user = interaction.user
            guild = interaction.guild
            channel = interaction.channel
            appeal_text = str(self.appeal_reason)
            appeal_id = f"appeal-{int(time.time())}"
            
            self.cog.logger.info(f"[{appeal_id}] New appeal from {user.name} ({user.id}) in {guild.name if guild else 'Unknown'} | Channel: {channel.name if channel else 'Unknown'}")
            
            # Update the feedback text in database if a violation ID was provided
            if self.violation_id:
                try:
                    async with self.cog.bot.pool.acquire() as conn:
                        # Update the existing feedback entry with the detailed text
                        await conn.execute("""
                            UPDATE ai_mod_feedback 
                            SET feedback_text = $1, updated_at = NOW()
                            WHERE violation_id = $2 AND user_id = $3 AND feedback_type = 'appeal'
                        """, appeal_text, self.violation_id, user.id)
                        
                        # Update guild moderation stats to count the appeal
                        await conn.execute("""
                            INSERT INTO guild_mod_stats (guild_id, appeals_received)
                            VALUES ($1, 1)
                            ON CONFLICT (guild_id) DO UPDATE
                            SET appeals_received = guild_mod_stats.appeals_received + 1,
                                updated_at = NOW()
                        """, guild.id)
                        
                except Exception as db_error:
                    self.cog.logger.error(f"Error updating feedback in database: {db_error}")
            
            # Create an embed for staff to review with a more structured layout
            embed = discord.Embed(
                title="Moderation Appeal Request",
                description=f"A user has appealed an AI moderation action and requests review.",
                color=YELLOW,
                timestamp=datetime.utcnow()
            )
            
            # User info section
            embed.add_field(
                name="User Information", 
                value=f"**Name:** {user.name}\n**ID:** {user.id}\n**Mention:** {user.mention}", 
                inline=True
            )
            
            # Context info section
            embed.add_field(
                name="Context", 
                value=f"**Channel:** {channel.mention if channel else 'Unknown'}\n**Time:** {discord.utils.format_dt(datetime.utcnow())}", 
                inline=True
            )
            
            # Message content - format with code block if it contains markdown
            if "\n" in self.original_message or "*" in self.original_message or "#" in self.original_message:
                # Format as code block for multiline or markdown content
                formatted_msg = f"```\n{self.original_message[:997] if len(self.original_message) > 1000 else self.original_message}\n```"
            else:
                # Simple format for short, plain messages
                formatted_msg = self.original_message[:1000] if len(self.original_message) <= 1000 else f"{self.original_message[:997]}..."
                
            embed.add_field(name="Original Message", value=formatted_msg, inline=False)
            embed.add_field(name="Removal Reason", value=self.removal_reason or "No specific reason provided", inline=False)
            embed.add_field(name="User's Appeal", value=appeal_text, inline=False)
            embed.add_field(name="Appeal ID", value=appeal_id, inline=True)
            embed.add_field(name="Violation ID", value=str(self.violation_id) if self.violation_id else "Unknown", inline=True)
            
            # Add thumbnail of the user's avatar
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
                
            embed.set_footer(text=f"{FOOTER_TEXT} • Appeal ID: {appeal_id}")
            
            # Try to send to logs channel if one is configured
            logs_channel = await self._get_logs_channel(guild)
            
            # Send the appeal
            if logs_channel and logs_channel.permissions_for(guild.me).send_messages:
                view = AppealReviewView(self.cog, user.id, self.original_message)
                await logs_channel.send(embed=embed, view=view)
                await interaction.response.send_message(
                    "Your appeal has been submitted to the server moderators for review. You'll be notified of their decision.", 
                    ephemeral=True
                )
                self.cog.logger.info(f"[{appeal_id}] Appeal sent to logs channel in {guild.name}")
            else:
                # No logs channel, respond to user but also log it
                self.cog.logger.warning(
                    f"[{appeal_id}] No logs channel configured for guild {guild.id if guild else 'Unknown'}, appeal not forwarded to moderators"
                )
                await interaction.response.send_message(
                    "Your feedback has been recorded. This server doesn't have a configured moderation channel, "
                    "but we've logged your concerns to help improve the moderation system.", 
                    ephemeral=True
                )
        except Exception as e:
            self.cog.logger.error(f"Error processing appeal: {e}")
            # Try to respond to the user if we haven't already
            try:
                await interaction.response.send_message(
                    "Sorry, there was an issue submitting your appeal. Your feedback has been logged.", 
                    ephemeral=True
                )
            except:
                # If we can't respond through the interaction, it might already be responded to or timed out
                pass
                
    async def _get_logs_channel(self, guild):
        """Helper method to get the logs channel for a guild."""
        if not guild or not self.cog.bot.pool:
            return None
            
        try:
            async with self.cog.bot.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT logs_channel_id FROM general_server WHERE guild_id = $1",
                    guild.id
                )
                if row and row["logs_channel_id"]:
                    return guild.get_channel(row["logs_channel_id"])
        except Exception as e:
            self.cog.logger.error(f"Error getting logs channel: {e}")
            
        return None


class AppealReviewView(discord.ui.View):
    """View for moderators to review and act on appeals."""
    
    def __init__(self, cog, user_id, original_message):
        super().__init__(timeout=None)  # No timeout for mod actions
        self.cog = cog
        self.user_id = user_id
        self.original_message = original_message
    
    @discord.ui.button(label="Approve Appeal", style=discord.ButtonStyle.success, emoji="✅")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is a moderator
        if not interaction.permissions.manage_messages and not interaction.permissions.ban_members:
            await interaction.response.send_message("You don't have permission to review appeals.", ephemeral=True)
            return
        
        # Notify the user their appeal was approved
        try:
            user = await self.cog.bot.fetch_user(self.user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="Appeal Approved",
                        description="Your recent appeal against an AI moderation action has been approved by a human moderator.",
                        color=GREEN
                    )
                    embed.add_field(name="Original Message", value=self.original_message[:1000])
                    embed.set_footer(text=f"Reviewed by: {interaction.user.name} • {FOOTER_TEXT}")
                    await user.send(embed=embed)
                except discord.Forbidden:
                    self.cog.logger.info(f"Cannot send DM to user {self.user_id}, they may have DMs disabled")
        except Exception as e:
            self.cog.logger.error(f"Error notifying user about approved appeal: {e}")
        
        # Update the appeal message
        embed = interaction.message.embeds[0]
        embed.color = GREEN
        embed.title = "Appeal Approved ✅"
        embed.add_field(name="Decision", value=f"Appeal approved by {interaction.user.mention}", inline=False)
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Deny Appeal", style=discord.ButtonStyle.danger, emoji="❌")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is a moderator
        if not interaction.permissions.manage_messages and not interaction.permissions.ban_members:
            await interaction.response.send_message("You don't have permission to review appeals.", ephemeral=True)
            return
        
        # Notify the user their appeal was denied
        try:
            user = await self.cog.bot.fetch_user(self.user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="Appeal Denied",
                        description="Your recent appeal against an AI moderation action was reviewed but denied by a human moderator.",
                        color=RED
                    )
                    embed.add_field(name="Original Message", value=self.original_message[:1000])
                    embed.add_field(name="Note", value="Please review our community guidelines to ensure your messages align with our standards.")
                    embed.set_footer(text=f"Reviewed by: {interaction.user.name} • {FOOTER_TEXT}")
                    await user.send(embed=embed)
                except discord.Forbidden:
                    self.cog.logger.info(f"Cannot send DM to user {self.user_id}, they may have DMs disabled")
        except Exception as e:
            self.cog.logger.error(f"Error notifying user about denied appeal: {e}")
        
        # Update the appeal message
        embed = interaction.message.embeds[0]
        embed.color = RED
        embed.title = "Appeal Denied ❌"
        embed.add_field(name="Decision", value=f"Appeal denied by {interaction.user.mention}", inline=False)
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)


class AIModeration(commands.Cog):
    """Cog for AI-based moderation using the local DeepSeek model.
    Provides message scanning for inappropriate content and moderation actions.
    Configurable per server with the /disabletheta command.
    """
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger('aimoderation')
        self.enabled = True  # AI moderation enabled by default
        self.model = os.getenv("Local_model", "lap2004_DeepSeek-R1-chatbot")
        self.api_url = os.getenv("AI_API_URL", "http://127.0.0.1:5000")
        self.api_path = os.getenv("ai_api_path", "/v1/chat/completions")
        self.gpu_available = False  # Will be set by hardware detection
        
        # Initialize statistics counters
        self.stats = {
            "messages_analyzed": 0,
            "messages_flagged": 0,
            "avg_inference_time": 0.0,
            "started_at": datetime.now().isoformat()
        }
        self.inference_times = []  # List to track individual inference times
        
        # Set up data export directory paths
        self.data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_data')
        self.logs_dir = os.path.join(self.data_dir, 'logs')
        
        # Initialize hardware info variables
        self.cpu_cores = 0
        self.gpu_available = False
        self.detect_hardware()
        
        if not all([self.model, self.api_url, self.api_path]):
            self.logger.warning("AI moderation configuration incomplete. Check your .env file.")
            self.enabled = False
        else:
            self.enabled = True
            # Schedule the connection check to run after the bot is ready instead of calling it directly
            self.bot.loop.create_task(self.check_connection_on_startup())
            
    def detect_hardware(self):
        """Detect available hardware for optimization purposes."""
        try:
            # Get CPU info
            self.cpu_cores = psutil.cpu_count(logical=False)
            self.memory_available = psutil.virtual_memory().total / (1024 * 1024 * 1024)  # GB
            
            # Log hardware info
            self.logger.info(f"System: {platform.system()} {platform.release()} {platform.machine()}")
            self.logger.info(f"CPU: {self.cpu_cores} physical cores")
            self.logger.info(f"Memory: {self.memory_available:.1f} GB available")
            
            # Check for NVIDIA GPU - relevant for RTX 3060 optimization
            # This is a simple check - in production you'd use libraries like nvidia-ml-py
            # or run a subprocess to check nvidia-smi
            if os.system("nvidia-smi >nul 2>&1") == 0:  # Windows-specific check
                self.gpu_available = True
                self.logger.info("NVIDIA GPU detected - optimizing for RTX 3060")
                
                # Set optimal batch size and threads for RTX 3060 with 12GB VRAM
                # Actual values would depend on the specific model and library being used
                os.environ["AI_BATCH_SIZE"] = "8"  # Optimal for RTX 3060
                os.environ["AI_NUM_THREADS"] = str(min(self.cpu_cores, 12))  # Balance with Ryzen 5 5500
                os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # Use primary GPU
            else:
                self.logger.info("No NVIDIA GPU detected, using CPU inference")
                os.environ["AI_NUM_THREADS"] = str(self.cpu_cores)  # Use all CPU cores
                
        except Exception as e:
            self.logger.error(f"Error detecting hardware: {e}")
            
    def _determine_response_level(self, content: str, reason: str, confidence: float) -> dict:
        """Determine the appropriate response level based on content type and confidence.
        
        Args:
            content: The message content
            reason: The reason provided by the AI
            confidence: The confidence score
            
        Returns:
            dict: Response level information including category, action, and warning_duration
        """
        # Default response
        response = {
            "category": "standard",
            "action": "delete",
            "warning_duration": 5  # seconds
        }
        
        # Check for extreme content that requires immediate action
        extreme_keywords = [
            "hate speech", "racism", "racist", "nazi", "threat", "threatening", "violence", 
            "sexual", "explicit", "child", "doxxing", "personal information"
        ]
        
        mild_keywords = [
            "profanity", "swear", "rude", "disrespectful", "name-calling", "mild"
        ]
        
        # Search in both the message content and reason
        combined_text = (content + " " + reason).lower()
        
        # Check for extreme content
        if any(keyword in combined_text for keyword in extreme_keywords):
            response["category"] = "extreme"
            response["warning_duration"] = 10  # longer warning for serious violations
            self.logger.warning(f"Extreme content detected: {reason}")
            return response
            
        # Check for mild content
        if any(keyword in combined_text for keyword in mild_keywords) and confidence < 0.85:
            response["category"] = "mild"
            response["warning_duration"] = 3  # shorter for mild violations
            return response
            
        # Adjust based on confidence
        if confidence > 0.9:
            response["warning_duration"] = 7  # more confident = longer warning
        
        return response
        
    def _extract_json_from_response(self, content: str) -> str:
        """Extract JSON from markdown-formatted responses.
        
        The AI model might wrap JSON in markdown code blocks or <think> tags.
        This method extracts the actual JSON content from such responses and ensures
        it has the required fields for moderation decisions.
        
        Args:
            content: The raw response from the AI service
            
        Returns:
            str: The extracted JSON string or a default JSON if extraction fails
        """
        if not content:
            return '{"inappropriate": false, "confidence": 0.0, "reason": ""}'
        
        self.logger.debug(f"Extracting JSON from: {content[:200]}")
        extraction_method = "unknown"
        json_str = None
        
        # Try multiple extraction patterns in order of preference
        
        # Pattern 1: Standard JSON object first (fastest match)
        try:
            json_obj_match = re.search(r'\{\s*"inappropriate"\s*:\s*(true|false).*?\}', content, re.DOTALL)
            if json_obj_match:
                potential_json = json_obj_match.group(0)
                # Validate if it's proper JSON
                json.loads(potential_json)
                json_str = potential_json
                extraction_method = "standard_json"
        except (json.JSONDecodeError, Exception):
            pass
            
        # Pattern 2: Check for JSON in markdown code blocks
        if not json_str:
            md_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
            md_match = re.search(md_pattern, content)
            if md_match:
                try:
                    potential_json = md_match.group(1).strip()
                    # Validate JSON
                    json.loads(potential_json)
                    json_str = potential_json
                    extraction_method = "markdown"
                except (json.JSONDecodeError, Exception):
                    pass
        
        # Pattern 3: Check for content within <think> tags
        if not json_str:
            think_pattern = r'<think>\s*([\s\S]*?)\s*(?:</think>|$)'
            think_match = re.search(think_pattern, content)
            if think_match:
                inner_content = think_match.group(1).strip()
                # Look for JSON inside think tag
                try:
                    json_inside_think = re.search(r'({\s*"[^"]+"\s*:.*?})', inner_content)
                    if json_inside_think:
                        potential_json = json_inside_think.group(1).strip()
                        # Validate JSON
                        json.loads(potential_json)
                        json_str = potential_json
                        extraction_method = "think+json"
                except (json.JSONDecodeError, Exception):
                    pass
        
        # Pattern 4: Handle malformed responses with extra data after valid JSON
        if not json_str:
            try:
                # Look for JSON-like patterns with key fields
                json_like_pattern = r'\{[^}]*"inappropriate"\s*:\s*(true|false)[^}]*\}'
                json_like_match = re.search(json_like_pattern, content)
                if json_like_match:
                    potential_json = json_like_match.group(0)
                    # Clean up and validate
                    potential_json = re.sub(r',\s*}', '}', potential_json)  # Fix trailing commas
                    json.loads(potential_json)  # Validate
                    json_str = potential_json
                    extraction_method = "json_like_pattern"
            except (json.JSONDecodeError, Exception):
                pass
                
        # If we have extracted JSON at this point, parse and validate it
        if json_str:
            try:
                result = json.loads(json_str)
                # Ensure it has all required fields or add defaults
                if "inappropriate" not in result:
                    result["inappropriate"] = False
                if "confidence" not in result:
                    result["confidence"] = 0.0
                if "reason" not in result:
                    result["reason"] = ""
                    
                self.logger.debug(f"Successfully extracted JSON using {extraction_method}")
                return json.dumps(result)
            except json.JSONDecodeError:
                self.logger.warning(f"Failed to validate JSON using {extraction_method}")
        
        # Fallback: Direct field extraction using regex for malformed responses
        self.logger.warning("Using fallback field extraction for malformed response")
        try:
            inappropriate = False
            confidence = 0.0
            reason = ""
            
            # Extract fields with patterns
            inappropriate_match = re.search(r'"?inappropriate"?\s*:\s*(true|false)', content, re.IGNORECASE)
            if inappropriate_match:
                inappropriate = inappropriate_match.group(1).lower() == 'true'
                
            confidence_match = re.search(r'"?confidence"?\s*:\s*([0-9.]+)', content)
            if confidence_match:
                confidence = min(float(confidence_match.group(1)), 1.0)  # Cap at 1.0
                
            reason_match = re.search(r'"?reason"?\s*:\s*"([^"]+)"', content)
            if reason_match:
                reason = reason_match.group(1)
            else:
                # Try alternative pattern without quotes
                alt_reason_match = re.search(r'"?reason"?\s*:\s*([^,}\n]+)', content)
                if alt_reason_match:
                    reason = alt_reason_match.group(1).strip()
            
            # Alternatively, look for indicators of inappropriate content in the response
            if not inappropriate_match and ("harmful" in content.lower() or 
                                        "profanity" in content.lower() or
                                        "offensive" in content.lower()):
                inappropriate = True
                if not reason:
                    reason = "Content contains potentially harmful material"
                if not confidence_match:
                    confidence = 0.7  # Default confidence for detected harmful content
            
            fallback_result = {
                "inappropriate": inappropriate,
                "confidence": confidence,
                "reason": reason
            }
            
            self.logger.info(f"Fallback extraction: inappropriate={inappropriate}, confidence={confidence:.2f}, reason='{reason}'")
            return json.dumps(fallback_result)
            
        except Exception as e:
            # Last resort if even regex extraction fails
            self.logger.error(f"All extraction methods failed: {e}")
            return '{"inappropriate": false, "confidence": 0.0, "reason": ""}'
        
    async def check_connection_on_startup(self):
        """Check connection to the AI service during startup with retry logic."""
        self.logger.info(f"AI moderation initialized with model: {self.model}")
        self.logger.info(f"Checking connection to AI service at {self.api_url}...")
        
        max_retries = 3
        retry_count = 0
        retry_delay = 2  # seconds
        
        while retry_count < max_retries:
            try:
                # Simple ping request to check if service is available
                full_url = f"{self.api_url}{self.api_path}"
                timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    start_time = time.time()
                    async with session.post(full_url, json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "temperature": 0.1,
                        "max_tokens": 5
                    }) as response:
                        end_time = time.time()
                        
                        # Read the response body to ensure it's valid
                        response_text = await response.text()
                        
                        if response.status == 200 and response_text:
                            ping_ms = (end_time - start_time) * 1000
                            self.connection_status = "Connected"
                            self.logger.info(f"✅ Successfully connected to AI service (latency: {ping_ms:.2f}ms)")
                            self.stats["last_connection_check"] = datetime.utcnow()
                            return True
                        else:
                            self.connection_status = "Error"
                            self.logger.error(f"❌ Failed to connect to AI service: Status {response.status}, Body: {response_text[:100]}")
                            self.stats["connection_errors"] += 1
            except asyncio.TimeoutError:
                self.logger.error(f"❌ Connection timeout to AI service (attempt {retry_count+1}/{max_retries})")
            except aiohttp.ClientError as e:
                self.logger.error(f"❌ Client error connecting to AI service: {e} (attempt {retry_count+1}/{max_retries})")
            except Exception as e:
                self.logger.error(f"❌ Error connecting to AI service: {e} (attempt {retry_count+1}/{max_retries})")
            
            # Increment retry counter
            retry_count += 1
            self.stats["connection_errors"] += 1
            
            if retry_count < max_retries:
                self.logger.info(f"Retrying connection in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        
        self.connection_status = "Error"
        self.logger.error(f"❌ Failed to connect to AI service after {max_retries} attempts")
        return False
    
    async def is_ai_moderation_enabled(self, guild_id: int, channel_id: int = None) -> bool:
        """Check if AI moderation is enabled for this guild and channel.
        
        Args:
            guild_id: The guild ID
            channel_id: Optional channel ID to check channel-specific settings
            
        Returns:
            bool: Whether AI moderation is enabled
        """
        if not self.enabled or not self.bot.pool:
            return False
            
        # First check channel overrides if channel_id is provided
        if channel_id:
            try:
                async with self.bot.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT override_enabled, ai_moderation_enabled 
                        FROM channel_mod_settings 
                        WHERE guild_id = $1 AND channel_id = $2""",
                        guild_id, channel_id
                    )
                    
                    if row and row["override_enabled"]:
                        self.logger.debug(f"Using channel-specific moderation settings for channel {channel_id}")
                        return row["ai_moderation_enabled"]
            except Exception as e:
                self.logger.error(f"Error checking channel moderation settings: {e}")
        
        # Fall back to guild settings
        async with self.bot.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT ai_moderation_enabled FROM general_server WHERE guild_id = $1",
                guild_id
            )
            
        # If no row or column doesn't exist yet, default to enabled
        if not row:
            return True
        return row["ai_moderation_enabled"] if "ai_moderation_enabled" in row else True
    
    async def log_moderation_action(self, guild: discord.Guild, user: discord.Member, 
                                   message_content: str, action: str, confidence: float):
        """Log moderation actions to the designated logs channel if available."""
        if not self.bot.pool:
            return
            
        async with self.bot.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id FROM general_server WHERE guild_id = $1",
                guild.id
            )
            
        if not row or not row["logs_channel_id"]:
            return
            
        logs_channel_id = row["logs_channel_id"]
        logs_channel = guild.get_channel(logs_channel_id) or await self.bot.fetch_channel(logs_channel_id)
        
        if not logs_channel:
            return
            
        embed = discord.Embed(
            title="AI Moderation Action", 
            color=BRAND_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=False)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Confidence", value=f"{confidence:.2%}", inline=True)
        
        # Truncate long messages
        if len(message_content) > 1024:
            message_content = message_content[:1021] + "..."
        embed.add_field(name="Message Content", value=message_content, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        
        try:
            await logs_channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to log moderation action: {e}")
            
    async def analyze_message(self, message_content: str, guild_id: int = None, channel_id: int = None, 
                           message_id: int = None, author_id: int = None, debug_mode: bool = False,
                           system_override: str = None, response_format: str = "json") -> tuple[bool, float, str]:
        """Analyze a message using the AI model to determine if it's inappropriate.
        
        Args:
            message_content: The message text to analyze
            guild_id: Optional guild ID to get server-specific settings
            channel_id: Optional channel ID for context
            message_id: Optional message ID for tracking
            author_id: Optional author ID for context
            debug_mode: If True, enables verbose logging of the AI response
            system_override: Optional custom system message to override the default moderation prompt
            response_format: Format for the response, either "json" or "text"
            
        Returns:
            tuple: (is_inappropriate, confidence, reason)
              When response_format is "json", reason contains a JSON structure
              When response_format is "text", reason contains the full text response
        """
        if not self.enabled or not message_content.strip():
            return False, 0.0, ""
        
        # Update stats
        self.stats["messages_analyzed"] += 1
        
        # Set up request_id for tracking this specific request in logs
        request_id = f"req-{int(time.time() * 1000)}-{self.stats['messages_analyzed']}"
        self.logger.info(f"[{request_id}] Analyzing message: {message_content[:50]}...")
            
        try:
            # Get server-specific settings if guild_id is provided
            settings = {"temperature": 0.3, "include_message_context": False, "context_message_count": 3}
            if guild_id is not None:
                settings = await self._get_guild_settings(guild_id)
                self.logger.debug(f"[{request_id}] Using server settings: temp={settings['temperature']}, context={settings['include_message_context']}")
            
            # Get message context if enabled
            context_messages = []
            if settings["include_message_context"] and guild_id and channel_id and message_id:
                context_messages = await self._get_message_context(guild_id, channel_id, message_id, 
                                                               settings["context_message_count"])
                self.logger.debug(f"[{request_id}] Retrieved {len(context_messages)} context messages")
            
            # Create a system prompt based on available context or use override if provided
            if system_override:
                system_content = system_override
            else:
                # Default moderation system prompt
                system_content = "You are an AI moderator for a Discord server. Your job is to analyze "
                
                if context_messages:
                    system_content += "the message in context and determine if it contains inappropriate content. "
                    system_content += "Consider the conversation context when making your determination. "
                else:
                    system_content += "the following message and determine if it contains inappropriate content. "
                    
                system_content += "Look for hate speech, harassment, racism, sexism, threats, extreme profanity, "
                system_content += "or other harmful content. Respond with a JSON object with three fields: "
                system_content += "'inappropriate' (boolean), 'confidence' (float between 0 and 1), and "
                system_content += "'reason' (brief explanation if inappropriate)."
            
            # Define the prompt for DeepSeek model
            prompt = [
                {"role": "system", "content": system_content}
            ]
            
            # Add context messages if available
            if context_messages:
                for ctx_msg in context_messages:
                    # Format the context message with author info
                    author_prefix = f"User {ctx_msg['author_id']}: " if ctx_msg.get('author_id') else "Someone: "
                    prompt.append({"role": "user", "content": f"{author_prefix}{ctx_msg['content']}"}) 
            
            # Add the message to analyze
            user_prefix = "" if not context_messages else (f"User {author_id}: " if author_id else "Current user: ")
            prompt.append({"role": "user", "content": f"{user_prefix}{message_content}"})
            
            if debug_mode:
                self.logger.debug(f"[{request_id}] Using prompt: {json.dumps(prompt)}")
                
            # Get temperature from settings
            temperature = settings.get("temperature", 0.3)
            
            # Batch processing optimization for RTX 3060
            # Smaller context size for faster inference on 12GB VRAM
            max_tokens = 50  # Just need a small response for moderation
            
            # Send request to the local API
            full_url = f"{self.api_url}{self.api_path}"
            payload = {
                "model": self.model,
                "messages": prompt,
                "temperature": temperature,  # Use server-specific temperature
                "max_tokens": max_tokens
            }
            
            # Set response format based on parameter
            if response_format == "json":
                payload["response_format"] = {"type": "json_object"}
            # For text response, don't specify a format constraint
            
            # Add hardware-specific optimization parameters if available
            if self.gpu_available:
                payload["use_gpu"] = True
                payload["batch_size"] = int(os.getenv("AI_BATCH_SIZE", "8"))  # Optimal for RTX 3060
            
            # Measure inference time for monitoring
            start_time = time.time()
            data = None
            raw_response = None
            
            # Add retry logic for transient errors
            max_retries = 2  # Maximum number of retries
            retry_count = 0
            retry_delay = 2  # Initial delay in seconds
            
            while retry_count <= max_retries:
                # Create session with configurable timeout to prevent hanging
                # Reduced from 15s to 10s to fail faster if needed for retries
                timeout = aiohttp.ClientTimeout(total=10)  
                
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        self.logger.debug(f"[{request_id}] Sending request to {full_url} (attempt {retry_count+1}/{max_retries+1})")
                        if debug_mode:
                            self.logger.debug(f"[{request_id}] Request payload: {json.dumps(payload)}")
                        
                        async with session.post(full_url, json=payload) as response:
                            if response.status != 200:
                                response_text = await response.text()
                                self.logger.error(f"[{request_id}] API request failed with status {response.status}: {response_text[:200]}")
                                
                                # Decide whether to retry based on status code
                                if response.status in [429, 500, 502, 503, 504] and retry_count < max_retries:
                                    retry_count += 1
                                    self.logger.warning(f"[{request_id}] Retrying after error {response.status} (attempt {retry_count}/{max_retries})")
                                    await asyncio.sleep(retry_delay * retry_count)  # Exponential backoff
                                    continue
                                else:
                                    self.stats["connection_errors"] += 1
                                    return False, 0.0, ""
                            
                            # Get raw response before parsing as JSON
                            raw_response = await response.text()
                            
                            if debug_mode:
                                self.logger.debug(f"[{request_id}] Raw API response: {raw_response[:500]}")
                            
                            try:
                                data = json.loads(raw_response)
                                # Success - break out of retry loop
                                break
                            except json.JSONDecodeError as json_err:
                                self.logger.error(f"[{request_id}] Failed to parse JSON response: {json_err}")
                                self.logger.error(f"[{request_id}] Raw response: {raw_response[:200]}")
                                
                                if retry_count < max_retries:
                                    retry_count += 1
                                    self.logger.warning(f"[{request_id}] Retrying after JSON parse error (attempt {retry_count}/{max_retries})")
                                    await asyncio.sleep(retry_delay * retry_count)  # Exponential backoff
                                    continue
                                else:
                                    # Last attempt failed, but we have raw_response for fallback extraction
                                    break
                                    
                except asyncio.TimeoutError:
                    self.logger.error(f"[{request_id}] Request timed out after {timeout.total} seconds")
                    if retry_count < max_retries:
                        retry_count += 1
                        self.logger.warning(f"[{request_id}] Retrying after timeout (attempt {retry_count}/{max_retries})")
                        # Reduce payload complexity for retries to help with timeouts
                        if retry_count == max_retries and len(prompt) > 2:
                            # For last retry attempt, simplify the prompt
                            self.logger.info(f"[{request_id}] Simplifying prompt for final retry attempt")
                            prompt = [prompt[0], prompt[-1]]  # Keep only system and last user message
                            payload["messages"] = prompt
                        await asyncio.sleep(retry_delay * retry_count)
                        continue
                    else:
                        self.stats["connection_errors"] += 1
                        return False, 0.0, ""
                        
                except Exception as e:
                    self.logger.error(f"[{request_id}] Request error: {str(e)}")
                    if retry_count < max_retries:
                        retry_count += 1
                        self.logger.warning(f"[{request_id}] Retrying after error (attempt {retry_count}/{max_retries})")
                        await asyncio.sleep(retry_delay * retry_count)
                        continue
                    else:
                        self.stats["connection_errors"] += 1
                        return False, 0.0, ""
            
            # If all retries failed and we couldn't get a response
            if not data and not raw_response:
                self.logger.error(f"[{request_id}] All retries failed")
                self.stats["connection_errors"] += 1
                return False, 0.0, ""
            
            # If we didn't get valid data from the API
            if not data:
                self.logger.error(f"[{request_id}] No valid data received from API")
                return False, 0.0, ""
                
            # Check if data contains the expected structure
            if "choices" not in data or not data["choices"]:
                self.logger.error(f"[{request_id}] Invalid response structure: missing 'choices' key")
                return False, 0.0, ""
            
            # Track inference performance
            end_time = time.time()
            inference_time = (end_time - start_time) * 1000  # ms
            
            # Keep track of recent inference times (last 100)
            self.inference_times.append(inference_time)
            if len(self.inference_times) > 100:
                self.inference_times.pop(0)
            
            # Update average inference time
            self.stats["avg_inference_ms"] = sum(self.inference_times) / len(self.inference_times)
            
            # Log occasional performance data
            if self.stats["messages_analyzed"] % 100 == 0:
                self.logger.info(f"AI moderation stats: {self.stats['messages_analyzed']} messages analyzed, "
                               f"avg inference: {self.stats['avg_inference_ms']:.2f}ms, "
                               f"flagged: {self.stats['messages_flagged']}")
            
            # Safely extract content
            content = ""
            try:
                if "choices" in data and data["choices"] and "message" in data["choices"][0] and "content" in data["choices"][0]["message"]:
                    content = data["choices"][0]["message"]["content"]
                    self.logger.debug(f"[{request_id}] Received AI response: {content[:100]}...")
                else:
                    self.logger.warning(f"[{request_id}] Unexpected response structure: {json.dumps(data)[:200]}")
            except Exception as e:
                self.logger.error(f"[{request_id}] Error extracting content from AI response: {e}")
            
            # Initialize default values
            is_inappropriate = False
            confidence = 0.0
            reason = ""
            
            # Process the content if available, otherwise use raw_response as fallback
            response_to_process = content or raw_response
            
            if response_to_process and response_to_process.strip():
                # Handle different response formats
                if response_format == "text":
                    # For text format, just return the raw content
                    is_inappropriate = False  # Not doing moderation
                    confidence = 1.0  # High confidence in the response itself
                    reason = response_to_process  # Return the full text response
                    
                    self.logger.debug(f"[{request_id}] Returning text response format, length: {len(reason)}")
                else:  # Default JSON processing
                    try:
                        # Use our enhanced JSON extraction method with multiple fallback strategies
                        cleaned_json = self._extract_json_from_response(response_to_process)
                        self.logger.debug(f"[{request_id}] Processed content for parsing: {cleaned_json[:100]}...")
                        
                        # Parse the cleaned JSON
                        result = json.loads(cleaned_json)
                        
                        # Extract values with safety checks and ensure all fields are present
                        is_inappropriate = result.get("inappropriate", False)
                        confidence = result.get("confidence", 0.0)
                        reason = result.get("reason", "")
                        
                        self.logger.info(f"[{request_id}] Analysis result: inappropriate={is_inappropriate}, "
                                      f"confidence={confidence:.2%}, reason='{reason}'")
                                      
                    except json.JSONDecodeError as e:
                        # This is unlikely since _extract_json_from_response already handles JSON errors,
                        # but adding as a safeguard
                        self.logger.error(f"[{request_id}] Final JSON parse error after extraction: {e}")
                        
                        # Use smart content analysis as last resort
                        is_inappropriate = any(word in response_to_process.lower() for word in 
                                            ["inappropriate", "harmful", "offensive", "profanity", 
                                             "hate speech", "violent"])
                        confidence = 0.65  # Conservative confidence for fallback
                        reason = "Content flagged by fallback detection system"
                        
                        self.logger.warning(f"[{request_id}] Using last resort fallback: inappropriate={is_inappropriate}, "
                                        f"confidence={confidence:.2%}, reason='{reason}'")
            else:
                self.logger.error(f"[{request_id}] No processable content received from AI service")
            
            # Always cap confidence at 1.0
            confidence = min(confidence, 1.0)
            
            # Update flagged count if inappropriate
            if is_inappropriate:
                self.stats["messages_flagged"] += 1
            
            return is_inappropriate, confidence, reason
                
        except Exception as e:
            self.logger.error(f"[{request_id}] Error analyzing message: {e}")
            return False, 0.0, ""
    
    @commands.Cog.listener()
    async def on_disconnect(self):
        """Handle shutdown tasks like data export."""
        self.logger.info("Bot disconnected, triggering data export")
        await self._export_all_data()
    
    @commands.Cog.listener()    
    async def on_close(self):
        """Handle close event for data export."""
        self.logger.info("Bot closing, triggering data export")
        await self._export_all_data()
        
    async def _export_all_data(self):
        """Export all data on shutdown."""
        try:
            # Create directories if they don't exist
            os.makedirs(self.data_dir, exist_ok=True)
            os.makedirs(self.logs_dir, exist_ok=True)
            
            # Export user data
            await self.export_user_data()
            
            # Export AI metrics
            self.export_ai_metrics()
            
            self.logger.info(f"Data exported to {self.data_dir}")
        except Exception as e:
            self.logger.error(f"Error during data export: {e}")
    
    async def export_user_data(self):
        """Export user profile data including risk levels to CSV."""
        # Ensure export directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Define all file paths that need to be created
        user_data_path = os.path.join(self.data_dir, 'user_profiles.csv')
        user_data_simple_path = os.path.join(self.data_dir, 'user_profiles_simple.csv')
        cross_server_path = os.path.join(self.data_dir, 'cross_server_behavior.csv')
        violations_path = os.path.join(self.data_dir, 'ai_violations.csv')
        guild_stats_path = os.path.join(self.data_dir, 'guild_mod_stats.csv')
        mod_feedback_path = os.path.join(self.data_dir, 'mod_feedback.csv')
        
        # Create empty CSV files with headers if database is not available
        if not self.bot.pool:
            self.logger.warning("Database not available - creating empty export files")
            
            # Create user_profiles.csv with headers
            with open(user_data_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['user_id', 'username', 'guilds', 'risk_level', 'risk_score', 'risk_factors', 'updated_at']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
            
            # Create user_profiles_simple.csv with headers
            with open(user_data_simple_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['user_id', 'username', 'guilds', 'risk_level', 'risk_score', 'risk_factors', 'updated_at']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
            # Create cross_server_behavior.csv with headers
            with open(cross_server_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['user_id', 'username', 'server_count', 'guilds', 'violation_count', 'risk_level']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
            # Create ai_violations.csv with headers
            with open(violations_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['violation_id', 'guild_id', 'guild_name', 'user_id', 'username', 'channel_id', 
                              'violation_type', 'confidence', 'message_content', 'has_context', 'reason', 
                              'action_taken', 'is_false_positive', 'created_at']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
            # Create guild_mod_stats.csv with headers
            with open(guild_stats_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['guild_id', 'total_messages_analyzed', 'flagged_messages', 'false_positives', 
                              'true_positives', 'appeals_received', 'appeals_accepted', 'updated_at']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
            # Create mod_feedback.csv with headers
            with open(mod_feedback_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['feedback_id', 'violation_id', 'user_id', 'guild_id', 'feedback_type', 
                              'feedback_text', 'review_status', 'created_at']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
            self.logger.info(f"Created empty export files in {self.data_dir} (database not available)")
            return
        
        # Database is available, try to export data
        try:
            async with self.bot.pool.acquire() as conn:
                # Check if user_profiles table exists
                try:
                    table_exists = await conn.fetchval(
                        """SELECT EXISTS (SELECT 1 FROM information_schema.tables 
                           WHERE table_schema = 'public' AND table_name = $1)""", 
                        "user_profiles"
                    )
                except Exception:
                    table_exists = False
                
                if not table_exists:
                    self.logger.warning("user_profiles table does not exist - creating empty files")
                    
                    # Create user_profiles.csv with headers
                    with open(user_data_path, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['user_id', 'username', 'guilds', 'risk_level', 'risk_score', 'risk_factors', 'updated_at']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                    
                    # Create user_profiles_simple.csv with headers
                    with open(user_data_simple_path, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['user_id', 'username', 'guilds', 'risk_level', 'risk_score', 'risk_factors', 'updated_at']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                    
                    self.logger.info(f"Created empty user profile files (table does not exist)")
                    return
                
                # Get all user profiles with risk data
                rows = await conn.fetch(
                    """SELECT user_id, username, guilds, risk_assessment, risk_score, risk_factors, 
                    profile_updated_at FROM user_profiles"""
                )
                
                # Create user_profiles.csv even if no data is available
                with open(user_data_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['user_id', 'username', 'guilds', 'risk_level', 'risk_score', 'risk_factors', 'updated_at']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    if rows:
                        for row in rows:
                            # Format JSON properly with triple quotes as required in examples
                            guilds_str = json.dumps(row['guilds']) if row['guilds'] else '[]'
                            risk_factors_str = json.dumps(row['risk_factors']) if row['risk_factors'] else '[]'
                            
                            writer.writerow({
                                'user_id': row['user_id'],
                                'username': row['username'],
                                'guilds': f'"""{guilds_str}"""',  # Triple-quoted JSON format
                                'risk_level': row['risk_assessment'] or 'UNKNOWN',
                                'risk_score': row['risk_score'] or 0.0,
                                'risk_factors': f'"""{risk_factors_str}"""',  # Triple-quoted JSON format
                                'updated_at': row['profile_updated_at'].isoformat() if row['profile_updated_at'] else ''
                            })
                
                # Create user_profiles_simple.csv (same format but with a different name)
                with open(user_data_simple_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['user_id', 'username', 'guilds', 'risk_level', 'risk_score', 'risk_factors', 'updated_at']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    if rows:
                        for row in rows:
                            # Format JSON properly with triple quotes as required in examples
                            guilds_str = json.dumps(row['guilds']) if row['guilds'] else '[]'
                            risk_factors_str = json.dumps(row['risk_factors']) if row['risk_factors'] else '[]'
                            
                            writer.writerow({
                                'user_id': row['user_id'],
                                'username': row['username'],
                                'guilds': f'"""{guilds_str}"""',  # Triple-quoted JSON format
                                'risk_level': row['risk_assessment'] or 'UNKNOWN',
                                'risk_score': row['risk_score'] or 0.0,
                                'risk_factors': f'"""{risk_factors_str}"""',  # Triple-quoted JSON format
                                'updated_at': row['profile_updated_at'].isoformat() if row['profile_updated_at'] else ''
                            })
                
                # Create cross_server_behavior.csv
                with open(cross_server_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['user_id', 'username', 'server_count', 'guilds', 'violation_count', 'risk_level']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    # Only export users in multiple servers
                    if rows:
                        multi_server_users = [row for row in rows if row['guilds'] and len(row['guilds']) > 1]
                        for row in multi_server_users:
                            guilds_str = json.dumps(row['guilds']) if row['guilds'] else '[]'
                            writer.writerow({
                                'user_id': row['user_id'],
                                'username': row['username'],
                                'server_count': len(row['guilds']) if row['guilds'] else 0,
                                'guilds': f'"""{guilds_str}"""',  # Triple-quoted JSON format
                                'violation_count': 0,  # Default value since we're not calculating violations here
                                'risk_level': row['risk_assessment'] or 'UNKNOWN'
                            })
                
                self.logger.info(f"Exported user data files to {self.data_dir}")
                
                # Query and export data for ai_violations.csv
                try:
                    # Check if ai_mod_violations table exists
                    violations_table_exists = await conn.fetchval(
                        """SELECT EXISTS (SELECT 1 FROM information_schema.tables 
                           WHERE table_schema = 'public' AND table_name = $1)""", 
                        "ai_mod_violations"
                    )
                    
                    if violations_table_exists:
                        # Get violation data with enhanced details
                        violations = await conn.fetch("""
                            SELECT v.violation_id, v.guild_id, g.guild_name, v.user_id, u.username, 
                            v.channel_id, v.violation_type, v.confidence, v.message_content, 
                            v.context_messages, v.reason, v.action_taken, v.is_false_positive,
                            v.confidence_categories, v.message_metadata, v.created_at
                            FROM ai_mod_violations v
                            LEFT JOIN general_server g ON v.guild_id = g.guild_id
                            LEFT JOIN user_profiles u ON v.user_id = u.user_id
                            ORDER BY v.created_at DESC
                        """)
                        
                        # Write violations to CSV
                        with open(violations_path, 'w', newline='', encoding='utf-8') as csvfile:
                            fieldnames = ['violation_id', 'guild_id', 'guild_name', 'user_id', 'username', 'channel_id', 
                                        'violation_type', 'confidence', 'message_content', 'has_context', 'reason', 
                                        'action_taken', 'is_false_positive', 'confidence_details', 'message_metadata', 'created_at']
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            writer.writeheader()
                            
                            for row in violations:
                                writer.writerow({
                                    'violation_id': row['violation_id'],
                                    'guild_id': row['guild_id'],
                                    'guild_name': row['guild_name'] or f"Unknown Guild {row['guild_id']}",
                                    'user_id': row['user_id'],
                                    'username': row['username'] or f"Unknown User {row['user_id']}",
                                    'channel_id': row['channel_id'],
                                    'violation_type': row['violation_type'],
                                    'confidence': row['confidence'],
                                    'message_content': row['message_content'],
                                    'has_context': 'Yes' if row['context_messages'] else 'No',
                                    'reason': row['reason'] or '',
                                    'action_taken': row['action_taken'],
                                    'is_false_positive': 'Yes' if row['is_false_positive'] else 
                                                       ('No' if row['is_false_positive'] is False else 'Unknown'),
                                    'confidence_details': json.dumps(row['confidence_categories']) if row['confidence_categories'] else '',
                                    'message_metadata': json.dumps(row['message_metadata']) if row['message_metadata'] else '',
                                    'created_at': row['created_at'].isoformat() if row['created_at'] else ''
                                })
                            self.logger.info(f"Exported {len(violations)} AI moderation violations to {violations_path}")
                    else:
                        # Create empty violations file with headers
                        with open(violations_path, 'w', newline='', encoding='utf-8') as csvfile:
                            fieldnames = ['violation_id', 'guild_id', 'guild_name', 'user_id', 'username', 'channel_id', 
                                        'violation_type', 'confidence', 'message_content', 'has_context', 'reason', 
                                        'action_taken', 'is_false_positive', 'confidence_details', 'message_metadata', 'created_at']
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            writer.writeheader()
                        self.logger.info(f"Created empty violations file (table does not exist)")
                except Exception as e:
                    self.logger.error(f"Error exporting violations data: {e}")
                    # Create empty file as fallback
                    with open(violations_path, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['violation_id', 'guild_id', 'guild_name', 'user_id', 'username', 'channel_id', 
                                    'violation_type', 'confidence', 'message_content', 'has_context', 'reason', 
                                    'action_taken', 'is_false_positive', 'confidence_details', 'message_metadata', 'created_at']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                
                # Query and export data for guild_mod_stats.csv
                try:
                    # Check if guild_mod_stats table exists
                    guild_stats_table_exists = await conn.fetchval(
                        """SELECT EXISTS (SELECT 1 FROM information_schema.tables 
                           WHERE table_schema = 'public' AND table_name = $1)""", 
                        "guild_mod_stats"
                    )
                    
                    if guild_stats_table_exists:
                        # Get guild statistics data
                        guild_stats = await conn.fetch("""
                            SELECT guild_id, total_messages_analyzed, flagged_messages,
                            false_positives, true_positives, appeals_received, appeals_accepted,
                            violation_categories, updated_at
                            FROM guild_mod_stats
                        """)
                        
                        # Write guild stats to CSV
                        with open(guild_stats_path, 'w', newline='', encoding='utf-8') as csvfile:
                            fieldnames = ['guild_id', 'total_messages_analyzed', 'flagged_messages',
                                        'false_positives', 'true_positives', 'appeals_received', 
                                        'appeals_accepted', 'violation_categories', 'updated_at']
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            writer.writeheader()
                            
                            for row in guild_stats:
                                writer.writerow({
                                    'guild_id': row['guild_id'],
                                    'total_messages_analyzed': row['total_messages_analyzed'],
                                    'flagged_messages': row['flagged_messages'],
                                    'false_positives': row['false_positives'],
                                    'true_positives': row['true_positives'],
                                    'appeals_received': row['appeals_received'],
                                    'appeals_accepted': row['appeals_accepted'],
                                    'violation_categories': json.dumps(row['violation_categories']) if row['violation_categories'] else '',
                                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else ''
                                })
                            self.logger.info(f"Exported {len(guild_stats)} guild moderation stats to {guild_stats_path}")
                    else:
                        # Create empty guild stats file with headers
                        with open(guild_stats_path, 'w', newline='', encoding='utf-8') as csvfile:
                            fieldnames = ['guild_id', 'total_messages_analyzed', 'flagged_messages',
                                        'false_positives', 'true_positives', 'appeals_received', 
                                        'appeals_accepted', 'violation_categories', 'updated_at']
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            writer.writeheader()
                        self.logger.info(f"Created empty guild stats file (table does not exist)")
                except Exception as e:
                    self.logger.error(f"Error exporting guild stats data: {e}")
                    # Create empty file as fallback
                    with open(guild_stats_path, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['guild_id', 'total_messages_analyzed', 'flagged_messages',
                                    'false_positives', 'true_positives', 'appeals_received', 
                                    'appeals_accepted', 'violation_categories', 'updated_at']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                
                # Query and export data for mod_feedback.csv
                try:
                    # Check if ai_mod_feedback table exists
                    feedback_table_exists = await conn.fetchval(
                        """SELECT EXISTS (SELECT 1 FROM information_schema.tables 
                           WHERE table_schema = 'public' AND table_name = $1)""", 
                        "ai_mod_feedback"
                    )
                    
                    if feedback_table_exists:
                        # Get user feedback data
                        feedback = await conn.fetch("""
                            SELECT feedback_id, violation_id, user_id, guild_id,
                            feedback_type, feedback_text, review_status, reviewer_id,
                            review_notes, created_at, updated_at
                            FROM ai_mod_feedback
                            ORDER BY created_at DESC
                        """)
                        
                        # Write feedback data to CSV
                        with open(mod_feedback_path, 'w', newline='', encoding='utf-8') as csvfile:
                            fieldnames = ['feedback_id', 'violation_id', 'user_id', 'guild_id',
                                        'feedback_type', 'feedback_text', 'review_status',
                                        'created_at', 'updated_at']
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            writer.writeheader()
                            
                            for row in feedback:
                                writer.writerow({
                                    'feedback_id': row['feedback_id'],
                                    'violation_id': row['violation_id'],
                                    'user_id': row['user_id'],
                                    'guild_id': row['guild_id'],
                                    'feedback_type': row['feedback_type'],
                                    'feedback_text': row['feedback_text'] or '',
                                    'review_status': row['review_status'],
                                    'created_at': row['created_at'].isoformat() if row['created_at'] else '',
                                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else ''
                                })
                            self.logger.info(f"Exported {len(feedback)} moderation feedback entries to {mod_feedback_path}")
                    else:
                        # Create empty feedback file with headers
                        with open(mod_feedback_path, 'w', newline='', encoding='utf-8') as csvfile:
                            fieldnames = ['feedback_id', 'violation_id', 'user_id', 'guild_id',
                                        'feedback_type', 'feedback_text', 'review_status',
                                        'created_at', 'updated_at']
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            writer.writeheader()
                        self.logger.info(f"Created empty feedback file (table does not exist)")
                except Exception as e:
                    self.logger.error(f"Error exporting feedback data: {e}")
                    # Create empty file as fallback
                    with open(mod_feedback_path, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['feedback_id', 'violation_id', 'user_id', 'guild_id',
                                    'feedback_type', 'feedback_text', 'review_status',
                                    'created_at', 'updated_at']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                    
        except Exception as e:
            self.logger.error(f"Error exporting user data: {e}")
            # Even if there's an error, create empty files as fallback
            try:
                # Create basic empty files
                with open(user_data_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['user_id', 'username', 'guilds', 'risk_level', 'risk_score', 'risk_factors', 'updated_at']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                with open(user_data_simple_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['user_id', 'username', 'guilds', 'risk_level', 'risk_score', 'risk_factors', 'updated_at']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                self.logger.info(f"Created empty user profile files after error: {e}")
            except Exception as inner_e:
                self.logger.error(f"Failed to create empty user profile files: {inner_e}")
    
    def export_ai_metrics(self):
        """Export AI moderation metrics and stats to logs directory."""
        # Ensure export directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        try:
            # Add end time and calculate duration
            self.stats['ended_at'] = datetime.now(timezone.utc).isoformat()
            
            # Ensure consistent timezone handling by making both datetimes timezone-aware
            start_time_str = self.stats.get('started_at', datetime.now(timezone.utc).isoformat())
            
            # Check if the start time has timezone info
            if 'T' in start_time_str and ('+' in start_time_str or 'Z' in start_time_str):
                # Already has timezone info
                start_time = datetime.fromisoformat(start_time_str)
            else:
                # No timezone info - assume UTC
                start_time = datetime.fromisoformat(start_time_str).replace(tzinfo=timezone.utc)
                
            # End time is already timezone-aware
            end_time = datetime.fromisoformat(self.stats['ended_at'])
            
            # Calculate duration with both timezone-aware datetimes
            duration = (end_time - start_time).total_seconds() / 3600  # hours
            self.stats['duration_hours'] = round(duration, 2)
            
            # Create metrics file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            metrics_path = os.path.join(self.logs_dir, f'ai_metrics_{timestamp}.json')
            
            # Add hardware info to stats
            self.stats['system'] = platform.system()
            self.stats['cpu_cores'] = self.cpu_cores
            self.stats['gpu_available'] = self.gpu_available
            self.stats['model'] = self.model
            
            # Calculate derived metrics
            if self.stats.get('messages_analyzed', 0) > 0:
                self.stats['flag_rate'] = round(self.stats.get('messages_flagged', 0) / self.stats['messages_analyzed'] * 100, 2)
            else:
                self.stats['flag_rate'] = 0.0
                
            # Convert any non-serializable objects (like datetime) to strings
            serializable_stats = {}
            for key, value in self.stats.items():
                # Convert datetime objects to ISO format strings
                if isinstance(value, datetime):
                    serializable_stats[key] = value.isoformat()
                else:
                    serializable_stats[key] = value
            
            # Write to JSON file
            with open(metrics_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_stats, f, indent=2)
                
            self.logger.info(f"Exported AI metrics to {metrics_path}")
            
            # Create additional metrics files based on standard naming for consistency
            violations_path = os.path.join(self.data_dir, 'ai_violations.csv')
            if not os.path.exists(violations_path):
                with open(violations_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['violation_id', 'guild_id', 'guild_name', 'user_id', 'username', 'channel_id', 
                                'violation_type', 'confidence', 'message_content', 'has_context', 'reason', 
                                'action_taken', 'is_false_positive', 'created_at']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
            # Create guild_mod_stats.csv if it doesn't exist
            guild_stats_path = os.path.join(self.data_dir, 'guild_mod_stats.csv')
            if not os.path.exists(guild_stats_path):
                with open(guild_stats_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['guild_id', 'total_messages_analyzed', 'flagged_messages', 'false_positives', 
                                'true_positives', 'appeals_received', 'appeals_accepted', 'updated_at']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                
            return metrics_path
                
        except Exception as e:
            self.logger.error(f"Error exporting AI metrics: {e}")
            
            # Create a minimal metrics file even if there's an error
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                metrics_path = os.path.join(self.logs_dir, f'ai_metrics_{timestamp}.json')
                
                minimal_stats = {
                    "messages_analyzed": 0,
                    "messages_flagged": 0,
                    "avg_inference_time": 0.0,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "last_connection_check": datetime.now(timezone.utc).isoformat(),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "duration_hours": 0.0,
                    "system": platform.system(),
                    "cpu_cores": getattr(self, 'cpu_cores', psutil.cpu_count(logical=False) or 1),
                    "gpu_available": getattr(self, 'gpu_available', False),
                    "model": getattr(self, 'model', 'unknown'),
                    "flag_rate": 0.0
                }
                
                with open(metrics_path, 'w', encoding='utf-8') as f:
                    json.dump(minimal_stats, f, indent=2)
                    
                self.logger.info(f"Created minimal metrics file after error: {metrics_path}")
                return metrics_path
                
            except Exception as inner_e:
                self.logger.error(f"Failed to create minimal metrics file: {inner_e}")
                return None
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Skip messages from bots, DMs, or empty content
        if message.author.bot or not message.guild or not message.content.strip():
            return
            
        # Check if AI moderation is enabled for this guild and channel
        if not await self.is_ai_moderation_enabled(message.guild.id, message.channel.id):
            return
        
        # Generate a debug ID for this message
        debug_id = f"msg-{message.id}"
        
        # Get guild settings
        settings = await self._get_guild_settings(message.guild.id, message.channel.id)
            
        # Step 1: Analyze the individual message
        is_inappropriate, confidence, reason = await self.analyze_message(
            message_content=message.content,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            author_id=message.author.id
        )
        
        # Step 2: If not flagged, also check message patterns (for split content evasion)
        if not is_inappropriate and len(message.content) >= 5:
            self.logger.debug(f"[{debug_id}] Individual message passed, checking message patterns")
            pattern_inappropriate, pattern_confidence, pattern_reason = await self.analyze_user_message_patterns(
                user_id=message.author.id, 
                guild_id=message.guild.id
            )
            
            # If pattern analysis found something, use those results instead
            if pattern_inappropriate and pattern_confidence > confidence:
                is_inappropriate = pattern_inappropriate
                confidence = pattern_confidence
                reason = f"Pattern detection: {pattern_reason}"
                self.logger.info(f"[{debug_id}] Pattern detection flagged content: {reason}")
        
        # Early exit if not inappropriate
        if not is_inappropriate:
            return
            
        # Log the detection regardless of action taken
        self.logger.info(f"[{debug_id}] Content flagged (confidence: {confidence:.2%}): {reason}")
        
        # Determine severity level based on confidence
        severity = "low"
        if confidence >= settings["high_severity_threshold"]:
            severity = "high"
        elif confidence >= settings["med_severity_threshold"]:
            severity = "med"
        
        # Get action for this severity level
        action = settings[f"{severity}_severity_action"]
        self.logger.debug(f"[{debug_id}] Severity: {severity}, Action: {action}, Confidence: {confidence:.2%}")
        
        # Record the violation in the database for tracking
        await self._record_violation(message.guild.id, message.author.id, message.channel.id, 
                                    severity, confidence, message.content, reason, action)
        
        # Check for rate limiting
        warning_duration = await self._check_rate_limit(message.guild.id, message.author.id, severity)
        
        # Determine what action to take
        if action == "none":
            # Just log it, take no action
            self.logger.info(f"[{debug_id}] No action taken (confidence: {confidence:.2%}): {reason}")
            return
            
        # If action is 'delete', delete the message
        if action == "delete":
            try:
                await message.delete()
                self.logger.info(f"[{debug_id}] Message deleted with confidence {confidence:.2%}: {reason}")
                
                # Log the action
                await self.log_moderation_action(
                    message.guild,
                    message.author, 
                    message.content, 
                    f"Message deleted: {reason}", 
                    confidence
                )
            except discord.Forbidden:
                self.logger.warning(f"[{debug_id}] Missing permissions to delete message in {message.guild.name}")
                # Continue to send warning even if we couldn't delete
            except Exception as e:
                self.logger.error(f"[{debug_id}] Error deleting message: {e}")
                return  # Stop if we couldn't delete the message
        
        # Send warning if action is 'warn' or 'delete'
        if action in ["warn", "delete"]:
            try:
                # Create a warning embed with detailed info
                # Determine color based on severity
                colors = {
                    "high": RED,
                    "med": YELLOW, 
                    "low": discord.Color.blue()
                }
                embed_color = colors.get(severity, YELLOW)
                
                # Create the embed
                embed = discord.Embed(
                    title="Content Policy Notice",
                    color=embed_color,
                    timestamp=datetime.utcnow()
                )
                
                # Add user mention to top of description
                description = f"{message.author.mention} Your message was {'removed' if action == 'delete' else 'flagged'}."
                
                # Use custom template if available
                if settings["warning_template"]:
                    # Replace placeholders in custom template for the embed description
                    custom_desc = settings["warning_template"]
                    custom_desc = custom_desc.replace("{user}", message.author.mention)
                    custom_desc = custom_desc.replace("{reason}", reason.lower())
                    custom_desc = custom_desc.replace("{confidence}", f"{confidence:.0%}")
                    custom_desc = custom_desc.replace("{severity}", severity)
                    embed.description = custom_desc
                else:
                    # Choose description based on available reason
                    if reason and len(reason) > 5 and reason.lower() not in ["inappropriate content", "inappropriate message"]:
                        embed.description = f"{description}\n\nReason: {reason}"
                    elif random.random() < 0.3:  # Educational message occasionally
                        embed.description = f"{description}\n\nWe aim to keep this server welcoming for everyone."
                    else:
                        embed.description = f"{description}\n\nPlease be respectful of others."
                
                # Add confidence score field
                embed.add_field(
                    name="Confidence", 
                    value=self._format_confidence_display(confidence), 
                    inline=True
                )
                
                # Add severity level field
                severity_displays = {
                    "high": "⚠️ High",
                    "med": "⚙️ Medium",
                    "low": "ℹ️ Low"
                }
                embed.add_field(
                    name="Severity", 
                    value=severity_displays.get(severity, "Medium"), 
                    inline=True
                )
                
                # Add action taken field
                action_displays = {
                    "delete": "Message Removed",
                    "warn": "Warning Only"
                }
                embed.add_field(
                    name="Action", 
                    value=action_displays.get(action, "Warning"), 
                    inline=True
                )
                
                embed.set_footer(text=f"{FOOTER_TEXT} • Click a button below to acknowledge this message")
                
                # Create feedback view with buttons
                view = ModFeedbackView(self, message.author.id, reason, message.content)
                
                # Send the warning with feedback buttons
                warning = await message.channel.send(embed=embed, view=view)
                
                # Instead of auto-deleting, we'll leave the warning until the user acknowledges it
                # through the feedback buttons. The buttons will be disabled after interaction.
                # Warning messages will persist in the channel until acknowledged.
                    
            except Exception as e:
                self.logger.error(f"[{debug_id}] Error sending warning: {e}")
                
    async def _record_violation(self, guild_id: int, user_id: int, channel_id: int, 
                              violation_type: str, confidence: float, content: str, 
                              reason: str, action: str) -> bool:
        """Record a violation in the database for tracking and analytics."""
        if not self.bot.pool:
            return False
            
        try:
            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO ai_mod_violations 
                    (guild_id, user_id, channel_id, violation_type, confidence, message_content, reason, action_taken)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    guild_id, user_id, channel_id, violation_type, confidence, content, reason, action
                )
                return True
        except Exception as e:
            self.logger.error(f"Error recording violation: {e}")
            return False
            
    def _format_confidence_display(self, confidence: float) -> str:
        """Format confidence score for user-friendly display.
        
        Args:
            confidence: The confidence score (0.0-1.0)
            
        Returns:
            str: Formatted display with visual indicators
        """
        # Format confidence as percentage
        percent = int(confidence * 100)
        
        # Add visual indicators based on confidence level
        if percent >= 90:
            return f"**{percent}%** 🔴"
        elif percent >= 75:
            return f"**{percent}%** 🟠"
        elif percent >= 60:
            return f"**{percent}%** 🟡"
        else:
            return f"**{percent}%** 🔵"
    
    async def _get_message_context(self, guild_id: int, channel_id: int, message_id: int, count: int = 3) -> list[dict]:
        """Get recent messages before the specified message for context.
        
        Args:
            guild_id: The guild ID
            channel_id: The channel ID
            message_id: The message ID to get context for
            count: Number of prior messages to retrieve
            
        Returns:
            list: List of message dictionaries with content and author_id
        """
        context_messages = []
        
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return []
                
            channel = guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return []
            
            # Get recent messages before the current one
            async for message in channel.history(limit=count+1, before=discord.Object(id=message_id)):
                # Skip bot messages
                if message.author.bot:
                    continue
                    
                # Add message to context
                context_messages.append({
                    "content": message.content,
                    "author_id": message.author.id
                })
                
                # Stop when we have enough context
                if len(context_messages) >= count:
                    break
                    
            # Reverse so they're in chronological order
            context_messages.reverse()
            
        except Exception as e:
            self.logger.error(f"Error getting message context: {e}")
            
        return context_messages
    
    async def _record_acknowledgment(self, guild_id: int, user_id: int, response_type: str) -> bool:
        """Record user acknowledgment of a moderation action.
        
        Args:
            guild_id: The guild ID
            user_id: The user ID
            response_type: The type of response ('acknowledged' or 'appealed')
            
        Returns:
            bool: True if the acknowledgment was recorded successfully
        """
        if not self.bot.pool:
            return False
            
        try:
            # First check if we need to create a new table for acknowledgments
            async with self.bot.pool.acquire() as conn:
                # Ensure the table exists (idempotent)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS ai_mod_acknowledgments (
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        response_type TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (guild_id, user_id, created_at)
                    )
                """)
                
                # Record the acknowledgment
                await conn.execute(
                    """INSERT INTO ai_mod_acknowledgments
                       (guild_id, user_id, response_type)
                       VALUES ($1, $2, $3)
                    """,
                    guild_id, user_id, response_type
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error recording acknowledgment: {e}")
            return False
    
    async def _check_rate_limit(self, guild_id: int, user_id: int, severity: str) -> int:
        """Check if user should be rate limited based on past violations.
        
        Returns:
            int: Warning duration in seconds
        """
        base_duration = 5  # Default warning duration
        
        if not self.bot.pool:
            return base_duration
            
        try:
            async with self.bot.pool.acquire() as conn:
                # Get current rate limit info
                row = await conn.fetchrow(
                    "SELECT violation_count, current_limit_duration, expires_at FROM ai_mod_rate_limits WHERE guild_id = $1 AND user_id = $2",
                    guild_id, user_id
                )
                
                now = datetime.now(timezone.utc)
                
                if row:
                    # User has previous violations
                    # Ensure we're using integer types for all database parameters
                    count = int(row["violation_count"])
                    current_duration = int(row["current_limit_duration"])
                    expires_at = row["expires_at"]
                    
                    if expires_at and expires_at > now:
                        # User is currently rate limited
                        # Increase the count and duration
                        count += 1
                        new_duration = min(current_duration * 2, 300)  # Max 5 minutes
                        
                        # Update the rate limit - explicitly cast to integers to avoid type conflicts
                        await conn.execute(
                            """
                            UPDATE ai_mod_rate_limits 
                            SET violation_count = $3::integer, 
                                last_violation_at = NOW(), 
                                current_limit_duration = $4::integer,
                                expires_at = NOW() + ($4::integer * interval '1 second')
                            WHERE guild_id = $1 AND user_id = $2
                            """,
                            guild_id, user_id, count, int(new_duration)
                        )
                        
                        return int(new_duration)
                    else:
                        # Previous rate limit expired, but increment count
                        count += 1
                        new_duration = min(current_duration, 30)  # Start with minimal increase if it expired
                        
                        # Update the rate limit - explicitly cast to integers to avoid type conflicts
                        await conn.execute(
                            """
                            UPDATE ai_mod_rate_limits 
                            SET violation_count = $3::integer, 
                                last_violation_at = NOW(), 
                                current_limit_duration = $4::integer,
                                expires_at = NOW() + ($4::integer * interval '1 second')
                            WHERE guild_id = $1 AND user_id = $2
                            """,
                            guild_id, user_id, count, int(new_duration)
                        )
                        
                        return int(new_duration)
                else:
                    # First violation for this user
                    # Severity affects initial duration
                    initial_duration = base_duration
                    if severity == "high":
                        initial_duration = 15
                    elif severity == "med":
                        initial_duration = 10
                        
                    # Create new rate limit entry - explicitly cast to integer
                    await conn.execute(
                        """
                        INSERT INTO ai_mod_rate_limits
                        (guild_id, user_id, violation_count, last_violation_at, current_limit_duration, expires_at)
                        VALUES ($1, $2, 1, NOW(), $3::integer, NOW() + ($3::integer * interval '1 second'))
                        """,
                        guild_id, user_id, int(initial_duration)
                    )
                    
                    return int(initial_duration)
                    
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {e}")
            
        return base_duration  # Default to base duration if anything fails
            
    
    @app_commands.command(name="aimod", description="Configure AI moderation settings for this server")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def aimod_settings(self, interaction: discord.Interaction):
        """Configure AI moderation settings with an interactive UI."""
        await interaction.response.defer(ephemeral=True)
        
        if not self.bot.pool:
            await interaction.followup.send("Database not configured, cannot access settings.", ephemeral=True)
            return
            
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
            
        # Get current settings
        settings = await self._get_guild_settings(guild.id)
        
        # Create settings view
        view = AIModSettingsView(self, guild.id, settings)
        
        # Create embed with settings info
        embed = discord.Embed(
            title="AI Moderation Settings",
            description="Configure how the AI moderator works in your server.",
            color=BRAND_COLOR
        )
        
        status = "Enabled" if settings["enabled"] else "Disabled"
        confidence = settings["confidence_threshold"]
        
        embed.add_field(
            name="Status", 
            value=f"{'🟢' if settings['enabled'] else '🔴'} **{status}**", 
            inline=True
        )
        embed.add_field(
            name="Confidence Threshold", 
            value=f"**{confidence*100:.0f}%**", 
            inline=True
        )
        embed.add_field(
            name="Temperature", 
            value=f"**{settings['temperature']:.1f}**", 
            inline=True
        )
        embed.add_field(
            name="Warning Duration", 
            value=f"**{settings['warning_duration']}** seconds", 
            inline=True
        )
        
        embed.set_footer(text=f"{FOOTER_TEXT} • Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
        
        # Send the settings panel
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="channelmod", description="Configure AI moderation settings for a specific channel")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def channel_mod_settings(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Configure channel-specific AI moderation settings.
        
        Args:
            channel: The channel to configure. Defaults to the current channel.
        """
        await interaction.response.defer(ephemeral=True)
        
        if not self.bot.pool:
            await interaction.followup.send("Database not configured, cannot access settings.", ephemeral=True)
            return
            
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
            
        # Default to current channel if not specified
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, (discord.TextChannel, discord.Thread)):
            await interaction.followup.send("This command can only be used with text channels.", ephemeral=True)
            return
            
        # Get current guild settings as baseline
        guild_settings = await self._get_guild_settings(guild.id)
        
        # Get any channel-specific overrides
        channel_settings = None
        override_enabled = False
        try:
            async with self.bot.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT * FROM channel_mod_settings 
                    WHERE guild_id = $1 AND channel_id = $2""",
                    guild.id, target_channel.id
                )
                if row:
                    override_enabled = row["override_enabled"]
                    # We'll use the full settings from _get_guild_settings with channel_id
        except Exception as e:
            self.logger.error(f"Error getting channel mod settings: {e}")
        
        # Get the combined/effective settings
        effective_settings = await self._get_guild_settings(guild.id, target_channel.id)
        
        # Create settings view
        view = ChannelModSettingsView(self, guild.id, target_channel.id, effective_settings, override_enabled)
        
        # Create embed with settings info
        embed = discord.Embed(
            title=f"Channel AI Moderation: #{target_channel.name}",
            description=f"Configure how the AI moderator works in {target_channel.mention}.",
            color=BRAND_COLOR
        )
        
        status = "Enabled" if effective_settings["enabled"] else "Disabled"
        
        embed.add_field(
            name="Override Status", 
            value=f"{'✅ Active' if override_enabled else '❌ Inactive'}", 
            inline=False
        )
        
        embed.add_field(
            name="Moderation Status", 
            value=f"{'🟢' if effective_settings['enabled'] else '🔴'} **{status}**", 
            inline=True
        )
        
        embed.add_field(
            name="Temperature", 
            value=f"**{effective_settings['temperature']:.1f}**", 
            inline=True
        )
        
        # Add action summary
        embed.add_field(
            name="Actions", 
            value=(
                f"**Low Severity:** {effective_settings['low_severity_action']}\n"
                f"**Medium Severity:** {effective_settings['med_severity_action']}\n"
                f"**High Severity:** {effective_settings['high_severity_action']}"
            ), 
            inline=False
        )
        
        embed.set_footer(text=f"{FOOTER_TEXT} • Click buttons below to configure")
        
        # Send the settings panel
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def _get_guild_settings(self, guild_id: int, channel_id: int = None) -> dict:
        """Get AI moderation settings for a guild, with optional channel override.
        
        Args:
            guild_id: The guild ID
            channel_id: Optional channel ID to get channel-specific settings
        
        Returns:
            dict: The moderation settings
        """
        settings = {
            "enabled": True,  # Default enabled
            "confidence_threshold": 0.75,  # Default threshold
            "warning_duration": 5,  # Default warning duration
            "temperature": 0.3,  # Default temperature (lower = stricter)
            "log_actions": True,  # Default log actions
            # Progressive response settings
            "warning_template": None,  # Custom warning template
            "low_severity_action": "warn",  # warn, delete, none
            "med_severity_action": "delete",  # warn, delete, none
            "high_severity_action": "delete",  # warn, delete, none
            "low_severity_threshold": 0.65,
            "med_severity_threshold": 0.75,
            "high_severity_threshold": 0.85,
            # Contextual learning settings
            "include_message_context": True,  # Enable context awareness by default
            "context_message_count": 3
        }
        
        if not self.bot.pool:
            return settings
            
        # First try to get channel-specific settings if provided
        if channel_id:
            try:
                async with self.bot.pool.acquire() as conn:
                    # Check for channel overrides
                    channel_row = await conn.fetchrow(
                        """
                        SELECT 
                            override_enabled,
                            ai_moderation_enabled,
                            ai_temperature_threshold,
                            ai_low_severity_action,
                            ai_med_severity_action,
                            ai_high_severity_action,
                            ai_low_severity_threshold,
                            ai_med_severity_threshold,
                            ai_high_severity_threshold
                        FROM channel_mod_settings
                        WHERE guild_id = $1 AND channel_id = $2
                        """,
                        guild_id, channel_id
                    )
                    
                    if channel_row and channel_row["override_enabled"]:
                        # Apply channel-specific overrides
                        self.logger.debug(f"Using channel-specific settings for channel {channel_id} in guild {guild_id}")
                        
                        # Override moderation flag
                        if channel_row["ai_moderation_enabled"] is not None:
                            settings["enabled"] = channel_row["ai_moderation_enabled"]
                            
                        # Override temperature
                        if channel_row["ai_temperature_threshold"] is not None:
                            settings["temperature"] = channel_row["ai_temperature_threshold"]
                            
                        # Override severity actions and thresholds
                        for severity in ["low", "med", "high"]:
                            action_key = f"ai_{severity}_severity_action"
                            threshold_key = f"ai_{severity}_severity_threshold"
                            
                            if channel_row[action_key]:
                                settings[f"{severity}_severity_action"] = channel_row[action_key]
                                
                            if channel_row[threshold_key] is not None:
                                settings[f"{severity}_severity_threshold"] = channel_row[threshold_key]
            except Exception as e:
                self.logger.error(f"Error getting channel moderation settings: {e}")
        
        try:
            async with self.bot.pool.acquire() as conn:
                # Get base guild settings (some settings will be overridden by channel settings if applicable)
                row = await conn.fetchrow(
                    """
                    SELECT 
                        ai_moderation_enabled, 
                        ai_temperature_threshold,
                        ai_warning_template,
                        ai_low_severity_action,
                        ai_med_severity_action,
                        ai_high_severity_action,
                        ai_low_severity_threshold,
                        ai_med_severity_threshold,
                        ai_high_severity_threshold,
                        ai_include_message_context,
                        ai_context_message_count
                    FROM general_server 
                    WHERE guild_id = $1
                    """,
                    guild_id
                )
                
                if row:
                    # Only apply base guild settings if we don't have channel overrides or for settings that aren't overridden
                    if not channel_id or (not hasattr(locals(), 'channel_row') or not locals().get('channel_row')):
                        # Basic settings
                        settings["enabled"] = row["ai_moderation_enabled"]
                        
                        # Temperature threshold
                        if "ai_temperature_threshold" in row and row["ai_temperature_threshold"] is not None:
                            settings["temperature"] = row["ai_temperature_threshold"]
                        
                        # Progressive response settings
                        for severity in ["low", "med", "high"]:
                            action_key = f"ai_{severity}_severity_action"
                            threshold_key = f"ai_{severity}_severity_threshold"
                            
                            if row[action_key]:
                                settings[f"{severity}_severity_action"] = row[action_key]
                                
                            if row[threshold_key] is not None:
                                settings[f"{severity}_severity_threshold"] = row[threshold_key]
                    
                    # Always apply these settings (they're not channel-specific)
                    # Custom warning template
                    if row["ai_warning_template"]:
                        settings["warning_template"] = row["ai_warning_template"]
                        
                    # Contextual learning settings
                    if row["ai_include_message_context"] is not None:
                        settings["include_message_context"] = row["ai_include_message_context"]
                        
                    if row["ai_context_message_count"] is not None:
                        settings["context_message_count"] = row["ai_context_message_count"]
                    
        except Exception as e:
            self.logger.error(f"Error getting AI moderation settings: {e}")
            
        return settings
        
    async def _update_guild_setting(self, guild_id: int, guild_name: str, settings: dict) -> bool:
        """Update AI moderation settings for a guild."""
        if not self.bot.pool:
            return False
            
        try:
            async with self.bot.pool.acquire() as conn:
                # Update settings including temperature threshold
                await conn.execute(
                    """
                    INSERT INTO general_server (guild_id, guild_name, ai_moderation_enabled, ai_temperature_threshold)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (guild_id) DO UPDATE
                    SET guild_name = EXCLUDED.guild_name,
                        ai_moderation_enabled = EXCLUDED.ai_moderation_enabled,
                        ai_temperature_threshold = EXCLUDED.ai_temperature_threshold
                    """,
                    guild_id,
                    guild_name,
                    settings["enabled"],
                    settings.get("temperature", 0.3)  # Default to 0.3 if not provided
                )
                
                # Log the configuration change
                status = "enabled" if settings["enabled"] else "disabled"
                self.logger.info(f"AI moderation {status} for guild ID: {guild_id} with temperature {settings.get('temperature', 0.3)}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating AI moderation settings: {e}")
            return False
    
    async def analyze_user_message_patterns(self, user_id: int, guild_id: int):
        """Analyze patterns in a user's recent messages to detect evasion attempts.
        
        This method combines recent messages from the same user to detect harmful content
        that might be split across multiple messages to evade detection.
        
        Args:
            user_id: The user's ID
            guild_id: The guild's ID
            
        Returns:
            tuple: (is_inappropriate, confidence, reason)
        """
        if not self.bot.pool:
            return False, 0.0, ""
            
        try:
            # Get recent messages from this user in this guild
            async with self.bot.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT history->>'content' as message_content 
                    FROM user_profiles,
                    jsonb_array_elements(message_history) as history
                    WHERE user_id = $1 
                    ORDER BY (history->>'timestamp')::timestamptz DESC LIMIT 5""",
                    user_id
                )
                
                if not rows or len(rows) < 2:
                    return False, 0.0, ""
                    
                # Combine recent messages for analysis
                combined_content = " ".join([row['message_content'] for row in rows if row['message_content']])
                
                # Skip if there's no content to analyze
                if not combined_content or len(combined_content.strip()) < 5:
                    return False, 0.0, ""
                
                self.logger.info(f"Analyzing combined message patterns for user {user_id}")
                
                # Re-analyze the combined content
                is_inappropriate, confidence, reason = await self.analyze_message(
                    message_content=combined_content,
                    guild_id=guild_id,
                    debug_mode=True
                )
                
                if is_inappropriate:
                    self.logger.warning(f"Pattern detection found split harmful content from user {user_id}: {reason}")
                
                return is_inappropriate, confidence, reason
                    
        except Exception as e:
            self.logger.error(f"Error analyzing message patterns: {e}")
            return False, 0.0, ""
    
    @app_commands.command(name="aiexplain", description="Learn about how AI moderation works")
    @app_commands.guild_only()
    async def explain_ai_moderation(self, interaction: discord.Interaction):
        """Provides an educational explanation about AI moderation."""
        # Defer the response to give us time to create a nice embed
        await interaction.response.defer(ephemeral=True)
        
        # Get the guild's settings if available
        settings = None
        if interaction.guild:
            settings = await self._get_guild_settings(interaction.guild.id)
        
        # Create an educational embed
        embed = discord.Embed(
            title="Understanding AI Moderation",
            description="FrostMod uses AI technology to help keep your server safe from harmful content. Here's how it works:",
            color=BRAND_COLOR
        )
        
        # Add general explanation section
        embed.add_field(
            name="How It Works", 
            value=(
                "When someone sends a message, our AI quickly analyzes it for harmful content like hate speech, "
                "harassment, threats, and extreme profanity. Based on the message and server settings, we may take "
                "different actions depending on the severity."
            ),
            inline=False
        )
        
        # Add confidence explanation
        embed.add_field(
            name="Confidence Score", 
            value=(
                "The AI assigns a confidence score (0-100%) to indicate how certain it is that a message violates "
                "community guidelines. Higher scores mean greater certainty."
            ),
            inline=False
        )
        
        # Add action explanation
        embed.add_field(
            name="Possible Actions", 
            value=(
                "🟢 **Low Severity**: Usually just a warning message\n"
                "🟡 **Medium Severity**: Message removal with warning\n"
                "🔴 **High Severity**: Message removal with longer-duration warning"
            ),
            inline=False
        )
        
        # Add user rights section
        embed.add_field(
            name="Your Rights", 
            value=(
                "If your message is flagged incorrectly, you can appeal by clicking the 'Appeal' button on the warning. "
                "A server moderator will review your appeal and make a final decision."
            ),
            inline=False
        )
        
        # Add user profiling section
        embed.add_field(
            name="User Profiling", 
            value=(
                "FrostMod also builds user profiles based on message patterns and activity. "
                "Administrators can use the `/risklevel` command to get AI-based risk assessments for users. "
                "This helps identify potentially problematic patterns while maintaining privacy and fairness."
            ),
            inline=False
        )
        
        # Add server-specific settings if available
        if settings:
            embed.add_field(
                name="This Server's Settings", 
                value=(
                    f"**Status**: {'Enabled' if settings['enabled'] else 'Disabled'}\n"
                    f"**Strictness**: {'High' if settings['temperature'] < 0.3 else ('Low' if settings['temperature'] > 0.5 else 'Medium')}\n"
                    f"**Context Awareness**: {'Enabled' if settings['include_message_context'] else 'Disabled'}"
                ),
                inline=False
            )
        
        # Add footer
        embed.set_footer(text=f"{FOOTER_TEXT}")
        
        # Send the educational embed
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="testmod", description="Test the AI moderation on a message")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def test_moderation(self, interaction: discord.Interaction, test_message: str):
        """Test the AI moderation system on a message.
        
        Parameters:
            test_message: The message to analyze
        """
        await interaction.response.defer(ephemeral=True)
        
        if not self.enabled:
            await interaction.followup.send("AI moderation is not properly configured.", ephemeral=True)
            return
            
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        # Check if moderation is enabled for this guild
        if not await self.is_ai_moderation_enabled(guild.id):
            await interaction.followup.send("AI moderation is disabled for this server.", ephemeral=True)
            return
            
        # Show an analysis in progress message
        embed = discord.Embed(
            title="AI Moderation Test", 
            description="Analyzing message...",
            color=YELLOW
        )
        embed.add_field(name="Test Message", value=test_message, inline=False)
        message = await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Analyze the message
        start_time = time.time()
        is_inappropriate, confidence, reason = await self.analyze_message(test_message)
        end_time = time.time()
        
        # Show the result
        if is_inappropriate:
            color = RED
            result = "❌ **Violates content policy**"
        else:
            color = GREEN
            result = "✅ **Passes content policy**"
            
        embed = discord.Embed(
            title="AI Moderation Test Results", 
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Test Message", value=test_message, inline=False)
        embed.add_field(name="Result", value=result, inline=False)
        embed.add_field(name="Confidence", value=f"{confidence:.2%}", inline=True)
        embed.add_field(name="Analysis Time", value=f"{(end_time - start_time) * 1000:.2f}ms", inline=True)
        
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
            
        embed.add_field(
            name="Action", 
            value=f"Message would {'be deleted' if is_inappropriate and confidence > 0.75 else 'not be deleted'}.", 
            inline=False
        )
        embed.set_footer(text=f"Model: {self.model} | {FOOTER_TEXT}")
        
        await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name="modstats", description="View AI moderation statistics and performance metrics")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def moderation_stats(self, interaction: discord.Interaction):
        """View AI moderation statistics and performance metrics."""
        await interaction.response.defer(ephemeral=True)
        
        if not self.enabled:
            await interaction.followup.send("AI moderation is not properly configured.", ephemeral=True)
            return
        
        # Get real-time hardware stats
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            mem_percent = mem.percent
            mem_used = mem.used / (1024 * 1024 * 1024)  # GB
            
            # Try to get GPU stats if available (simplified)
            gpu_info = "Not available"
            if self.gpu_available:
                try:
                    # This is a placeholder - in a real implementation you'd use
                    # nvidia-ml-py or a similar library to get GPU usage metrics
                    gpu_info = "RTX 3060 optimized"
                except:
                    pass
                
        except Exception as e:
            self.logger.error(f"Error getting system stats: {e}")
            cpu_percent = 0
            mem_percent = 0
            mem_used = 0
            
        # Create embed with all statistics
        embed = discord.Embed(
            title="AI Moderation System Status", 
            color=GREEN if self.connection_status == "Connected" else RED,
            timestamp=datetime.utcnow()
        )
        
        # Connection status
        embed.add_field(
            name="Connection Status", 
            value=f"{'✅ Connected' if self.connection_status == 'Connected' else '❌ Disconnected'}", 
            inline=False
        )
        
        # Basic stats
        embed.add_field(name="Model", value=self.model, inline=True)
        embed.add_field(name="Messages Analyzed", value=str(self.stats["messages_analyzed"]), inline=True)
        embed.add_field(name="Messages Flagged", value=str(self.stats["messages_flagged"]), inline=True)
        
        # Performance metrics
        embed.add_field(name="Average Inference Time", value=f"{self.stats['avg_inference_ms']:.2f}ms", inline=True)
        embed.add_field(name="Connection Errors", value=str(self.stats["connection_errors"]), inline=True)
        last_check = self.stats["last_connection_check"]
        last_check_str = discord.utils.format_dt(last_check) if last_check else "Never"
        embed.add_field(name="Last Connection Check", value=last_check_str, inline=True)
        
        # Hardware utilization
        embed.add_field(name="CPU Usage", value=f"{cpu_percent:.1f}%", inline=True)
        embed.add_field(name="Memory Usage", value=f"{mem_used:.1f}GB ({mem_percent:.1f}%)", inline=True)
        embed.add_field(name="GPU", value=gpu_info, inline=True)
        
        # Hardware details
        embed.add_field(
            name="Hardware Configuration", 
            value=f"CPU: {self.cpu_cores} cores | RAM: {self.memory_available:.1f}GB | GPU: {'Detected' if self.gpu_available else 'Not detected'}",
            inline=False
        )
        
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    # Ensure the database has the necessary column
    if hasattr(bot, 'pool') and bot.pool:
        async with bot.pool.acquire() as conn:
            await conn.execute(
                "ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_moderation_enabled BOOLEAN NOT NULL DEFAULT TRUE"
            )
    
    await bot.add_cog(AIModeration(bot))