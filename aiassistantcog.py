"""
AI Assistant Cog for FrostMod

This module provides an advanced AI-powered help assistant that can answer
server-specific questions by leveraging the existing AI infrastructure
and dynamically gathering context about the server.

Features:
- Context-aware responses based on server rules, FAQs, and settings
- Command history tracking for better assistance
- Integration with existing AI moderation services
"""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT, GREEN, YELLOW, RED


class ServerContextCache:
    """Cache server context information for better AI responses."""
    
    def __init__(self):
        self.cache = {}  # guild_id -> context_data
        self.max_age_hours = 1  # Refresh cache after this many hours
        
    def get(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get cached context for a guild if available and not expired."""
        if guild_id in self.cache:
            context = self.cache[guild_id]
            # Check if cache is still valid
            age = (datetime.now(timezone.utc) - context["timestamp"]).total_seconds() / 3600
            if age < self.max_age_hours:
                return context["data"]
        return None
        
    def set(self, guild_id: int, context_data: Dict[str, Any]):
        """Cache context data for a guild."""
        self.cache[guild_id] = {
            "data": context_data,
            "timestamp": datetime.now(timezone.utc)
        }


class AskModal(discord.ui.Modal, title="Ask the Assistant"):
    """Modal for entering a question to the AI assistant."""
    
    question = discord.ui.TextInput(
        label="Your Question",
        style=discord.TextStyle.paragraph,
        placeholder="What would you like to know about the server?",
        required=True,
        max_length=1000
    )
    
    def __init__(self, cog, **kwargs):
        super().__init__(**kwargs)
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process the submitted question."""
        await interaction.response.defer(thinking=True)
        
        question = str(self.question)
        await self.cog._process_question(interaction, question)


class AIAssistant(commands.Cog):
    """AI-powered assistant for answering server-specific questions."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('aiassistant')
        self.context_cache = ServerContextCache()
        self.recent_questions = {}  # guild_id -> list of recent questions
        self.max_recent_questions = 10  # Per guild
        self.logger.info("AI Assistant cog initialized")
        
    @app_commands.command(name="ask", description="Ask the AI assistant a question about the server")
    @app_commands.guild_only()
    async def ask_cmd(self, interaction: discord.Interaction):
        """Ask the AI assistant a question about this server."""
        # Show modal to get the question
        modal = AskModal(self)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="askabout", description="Ask about a specific topic")
    @app_commands.guild_only()
    @app_commands.choices(topic=[
        app_commands.Choice(name="Rules", value="rules"),
        app_commands.Choice(name="Commands", value="commands"),
        app_commands.Choice(name="Moderation", value="moderation"),
        app_commands.Choice(name="Roles", value="roles"),
        app_commands.Choice(name="Events", value="events"),
    ])
    async def askabout_cmd(self, interaction: discord.Interaction, topic: str, question: str):
        """Ask about a specific topic."""
        await interaction.response.defer(thinking=True)
        
        # Add topic context to the question
        enhanced_question = f"[Topic: {topic}] {question}"
        await self._process_question(interaction, enhanced_question)
    
    async def _process_question(self, interaction: discord.Interaction, question: str):
        """Process a question and provide an AI-powered response."""
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
            
        # Check for AI moderation cog which provides the AI service
        ai_mod_cog = self.bot.get_cog('AIModeration')
        if not ai_mod_cog or not ai_mod_cog.enabled:
            await interaction.followup.send(
                "The AI assistance service is currently unavailable. Please try again later.", 
                ephemeral=True
            )
            return
        
        # Track this question for context in future questions
        self._add_recent_question(guild.id, interaction.user.id, question)
        
        try:
            # Get server context (rules, channels, etc.)
            server_context = await self._get_server_context(guild)
            
            # Get recent questions from this user in this server for context
            recent_questions = self._get_recent_questions(guild.id, interaction.user.id)
            recent_context = ""
            if recent_questions:
                recent_context = "Recent questions you've asked:\n" + "\n".join(
                    f"- {q}" for q in recent_questions[-3:] if q != question
                )
            
            # Create a prompt for the AI that includes server context
            system_prompt = f"""You are an AI assistant for the Discord server '{guild.name}'.
            
            Use the following information about the server to answer the user's question:
            
            {server_context}
            
            If the user asks about something not covered in the server information, say you don't have that specific information.
            
            Be concise, helpful and friendly. Format your response in Markdown when appropriate.
            """
            
            user_prompt = f"{question}"
            if recent_context:
                user_prompt = f"{recent_context}\n\nNew question: {question}"
            
            # Use the AI service to get a response
            _, _, response = await ai_mod_cog.analyze_message(
                message_content=user_prompt,
                guild_id=guild.id,
                debug_mode=True,
                system_override=system_prompt,
                response_format="text"  # Request regular text, not JSON
            )
            
            # Create response embed
            embed = discord.Embed(
                title=f"Answer to: {question[:100] + ('...' if len(question) > 100 else '')}",
                description=response,
                color=BRAND_COLOR
            )
            
            # Add information about what data was used
            context_sources = []
            if server_context:
                if "Rules" in server_context:
                    context_sources.append("Server Rules")
                if "Channels" in server_context:
                    context_sources.append("Channel Structure")
                if "Roles" in server_context:
                    context_sources.append("Server Roles")
                
            if context_sources:
                embed.add_field(
                    name="Sources Used", 
                    value=", ".join(context_sources),
                    inline=False
                )
            
            embed.set_footer(text=f"{FOOTER_TEXT}")
            
            await interaction.followup.send(embed=embed)
            self.logger.info(f"Answered question for {interaction.user.name} in {guild.name}: {question[:50]}...")
            
        except Exception as e:
            self.logger.error(f"Error processing question: {e}")
            await interaction.followup.send(
                "Sorry, I encountered an error while processing your question. Please try again later.",
                ephemeral=True
            )
    
    async def _get_server_context(self, guild: discord.Guild) -> str:
        """Get context about the server for informed AI responses."""
        # Check cache first
        cached_context = self.context_cache.get(guild.id)
        if cached_context:
            self.logger.debug(f"Using cached context for guild {guild.id}")
            return cached_context
            
        self.logger.info(f"Building server context for guild {guild.id} ({guild.name})")
        
        context_parts = []
        
        # 1. Get server rules if available
        try:
            # First check for auto-published rules
            rules_channel_id = guild.rules_channel and guild.rules_channel.id
            if rules_channel_id:
                rules_channel = guild.rules_channel
                async for message in rules_channel.history(limit=10):
                    if message.author == guild.me:
                        continue  # Skip bot's own messages
                    if message.content:
                        context_parts.append(f"Rules:\n{message.content[:1000]}")
                        break
        except Exception as e:
            self.logger.error(f"Error getting rules: {e}")
        
        # 2. Get channel structure for navigation context
        try:
            channel_info = []
            # Add categories and their channels
            for category in guild.categories:
                cat_channels = []
                for channel in category.channels:
                    if isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).view_channel:
                        topic = f": {channel.topic}" if channel.topic else ""
                        cat_channels.append(f"#{channel.name}{topic}")
                
                if cat_channels:
                    channel_info.append(f"Category '{category.name}':\n" + "\n".join(cat_channels))
            
            # Add uncategorized channels
            uncat_channels = []
            for channel in guild.text_channels:
                if channel.category is None and channel.permissions_for(guild.me).view_channel:
                    topic = f": {channel.topic}" if channel.topic else ""
                    uncat_channels.append(f"#{channel.name}{topic}")
                    
            if uncat_channels:
                channel_info.append("Uncategorized channels:\n" + "\n".join(uncat_channels))
                
            if channel_info:
                context_parts.append("Channels:\n" + "\n".join(channel_info))
        except Exception as e:
            self.logger.error(f"Error getting channel structure: {e}")
            
        # 3. Get role information
        try:
            role_info = []
            for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
                if role.name != "@everyone" and not role.is_bot_managed():
                    members_count = len(role.members)
                    if members_count > 0:
                        role_info.append(f"{role.name}: {members_count} members")
            
            if role_info:
                context_parts.append("Roles:\n" + "\n".join(role_info[:15]))  # Limit to top 15 roles
        except Exception as e:
            self.logger.error(f"Error getting role information: {e}")
            
        # Combine all context
        combined_context = "\n\n".join(context_parts)
        
        # Truncate if too long
        if len(combined_context) > 4000:
            combined_context = combined_context[:4000] + "...[additional context omitted]"
        
        # Cache the context
        self.context_cache.set(guild.id, combined_context)
        
        return combined_context
        
    def _add_recent_question(self, guild_id: int, user_id: int, question: str):
        """Track recent questions for conversation context."""
        # Initialize guild entry if needed
        if guild_id not in self.recent_questions:
            self.recent_questions[guild_id] = {}
            
        # Initialize user entry if needed
        if user_id not in self.recent_questions[guild_id]:
            self.recent_questions[guild_id][user_id] = []
            
        # Add question and limit the list size
        questions = self.recent_questions[guild_id][user_id]
        questions.append(question)
        if len(questions) > self.max_recent_questions:
            self.recent_questions[guild_id][user_id] = questions[-self.max_recent_questions:]
    
    def _get_recent_questions(self, guild_id: int, user_id: int) -> List[str]:
        """Get recent questions asked by this user in this guild."""
        if guild_id in self.recent_questions and user_id in self.recent_questions[guild_id]:
            return self.recent_questions[guild_id][user_id]
        return []


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AIAssistant(bot))
