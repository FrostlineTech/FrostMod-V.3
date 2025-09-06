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
from datetime import datetime, timedelta
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
            
    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, row=0, disabled=False)
    async def enable_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable AI moderation."""
        # Update settings
        self.settings["enabled"] = True
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        # Update database
        success = await self.cog._update_guild_setting(self.guild_id, self.guild_name, self.settings)
        
        if success:
            # Update button states
            button.disabled = True
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.label == "Disable":
                    child.disabled = False
            
            # Update embed
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Status":
                    embed.set_field_at(i, name="Status", value="🟢 **Enabled**", inline=True)
            embed.set_footer(text=f"{FOOTER_TEXT} • Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
            
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send("AI moderation has been enabled for this server.", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to update settings. Please try again.", ephemeral=True)
    
    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, row=0)
    async def disable_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable AI moderation."""
        # Update settings
        self.settings["enabled"] = False
        self.guild_name = interaction.guild.name if interaction.guild else ""
        
        # Update database
        success = await self.cog._update_guild_setting(self.guild_id, self.guild_name, self.settings)
        
        if success:
            # Update button states
            button.disabled = True
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.label == "Enable":
                    child.disabled = False
            
            # Update embed
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Status":
                    embed.set_field_at(i, name="Status", value="🔴 **Disabled**", inline=True)
            embed.set_footer(text=f"{FOOTER_TEXT} • Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
            
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send("AI moderation has been disabled for this server.", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to update settings. Please try again.", ephemeral=True)
            
    @discord.ui.button(label="Stricter (0.2)", style=discord.ButtonStyle.secondary, row=1)
    async def stricter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set stricter moderation (lower temperature)."""
        # Update settings
        self.settings["temperature"] = 0.2
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
            await interaction.followup.send("AI moderation temperature set to 0.2 (stricter).", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to update settings. Please try again.", ephemeral=True)
            
    @discord.ui.button(label="Balanced (0.4)", style=discord.ButtonStyle.secondary, row=1)
    async def balanced_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set balanced moderation (medium temperature)."""
        # Update settings
        self.settings["temperature"] = 0.4
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
    
    def __init__(self, cog, user_id, reason, message_content):
        super().__init__(timeout=None)  # No timeout - persist until acknowledged
        self.cog = cog
        self.user_id = user_id
        self.reason = reason
        self.message_content = message_content
        self.feedback_logged = False
    
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
            await interaction.response.send_modal(AppealModal(self.cog, self.message_content, self.reason))
            self.cog.logger.info(f"User {interaction.user.name} ({interaction.user.id}) started appeal process for: {self.reason}")
            self.feedback_logged = True
            
            # Record acknowledgment in database
            await self.cog._record_acknowledgment(interaction.guild.id, interaction.user.id, "appealed")
            
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
    
    def __init__(self, cog, original_message, removal_reason):
        super().__init__()
        self.cog = cog
        self.original_message = original_message
        self.removal_reason = removal_reason
    
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
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('aimoderation')
        
        # System metrics tracking
        self.inference_times = []  # Track recent inference times
        self.last_status_check = None
        self.connection_status = "Unknown"
        self.stats = {
            "messages_analyzed": 0,
            "messages_flagged": 0,
            "avg_inference_ms": 0,
            "connection_errors": 0,
            "last_connection_check": None,
        }
        
        # Load AI configuration from environment variables
        self.model = os.getenv("Local_model")
        self.api_url = os.getenv("AI_API_URL")
        self.api_path = os.getenv("ai_api_path")
        
        # Hardware detection for optimization
        self.gpu_available = False
        self.memory_available = 0
        self.cpu_cores = 0
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
    
    async def is_ai_moderation_enabled(self, guild_id: int) -> bool:
        """Check if AI moderation is enabled for this guild."""
        if not self.enabled or not self.bot.pool:
            return False
            
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
                           message_id: int = None, author_id: int = None, debug_mode: bool = False) -> tuple[bool, float, str]:
        """Analyze a message using the AI model to determine if it's inappropriate.
        
        Args:
            message_content: The message text to analyze
            guild_id: Optional guild ID to get server-specific settings
            channel_id: Optional channel ID for context
            message_id: Optional message ID for tracking
            author_id: Optional author ID for context
            debug_mode: If True, enables verbose logging of the AI response
            
        Returns:
            tuple: (is_inappropriate, confidence, reason)
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
            
            # Create a richer system prompt based on available context
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
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"}
            }
            
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
    async def on_message(self, message: discord.Message):
        # Skip messages from bots, DMs, or empty content
        if message.author.bot or not message.guild or not message.content.strip():
            return
            
        # Check if AI moderation is enabled for this guild
        if not await self.is_ai_moderation_enabled(message.guild.id):
            return
        
        # Generate a debug ID for this message
        debug_id = f"msg-{message.id}"
        
        # Get guild settings
        settings = await self._get_guild_settings(message.guild.id)
            
        # Analyze the message with server-specific settings and context
        is_inappropriate, confidence, reason = await self.analyze_message(
            message_content=message.content,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            author_id=message.author.id
        )
        
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
                
                now = datetime.utcnow()
                
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
    
    async def _get_guild_settings(self, guild_id: int) -> dict:
        """Get AI moderation settings for a guild."""
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
            
        try:
            async with self.bot.pool.acquire() as conn:
                # Try to get existing settings
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
                    # Basic settings
                    settings["enabled"] = row["ai_moderation_enabled"]
                    
                    # Temperature threshold
                    if "ai_temperature_threshold" in row and row["ai_temperature_threshold"] is not None:
                        settings["temperature"] = row["ai_temperature_threshold"]
                    
                    # Custom warning template
                    if row["ai_warning_template"]:
                        settings["warning_template"] = row["ai_warning_template"]
                        
                    # Progressive response settings
                    for severity in ["low", "med", "high"]:
                        action_key = f"ai_{severity}_severity_action"
                        threshold_key = f"ai_{severity}_severity_threshold"
                        
                        if row[action_key]:
                            settings[f"{severity}_severity_action"] = row[action_key]
                            
                        if row[threshold_key] is not None:
                            settings[f"{severity}_severity_threshold"] = row[threshold_key]
                    
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