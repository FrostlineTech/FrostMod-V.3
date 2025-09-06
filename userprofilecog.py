"""
User Profiling and Risk Assessment Cog.

This cog maintains user profiles by monitoring:
- Message content and patterns
- Guild membership
- Activity patterns
- Previous moderation actions

It provides admins with tools to assess user risk levels based on AI analysis.
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import time
from typing import Dict, List, Optional, Tuple, Any, Union

import discord
from discord import app_commands
from discord.ext import commands, tasks

from branding import BRAND_COLOR, FOOTER_TEXT, GREEN, YELLOW, RED


class RiskLevelEmbed(discord.Embed):
    """Standardized embed for risk level results."""
    
    def __init__(self, user: discord.User, risk_level: str, risk_score: float, risk_factors: List[str]):
        """Initialize the risk level embed with user information and risk assessment."""
        # Set color based on risk level
        color = {
            "LOW": GREEN,
            "MEDIUM": YELLOW,
            "HIGH": RED,
            "VERY HIGH": discord.Color.dark_red(),
        }.get(risk_level, BRAND_COLOR)
        
        super().__init__(
            title=f"User Risk Assessment: {user.name}",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Add user information
        self.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
        
        # Add risk assessment
        self.add_field(name="Risk Level", value=f"**{risk_level}**", inline=True)
        self.add_field(name="Risk Score", value=f"{risk_score:.1f}/100", inline=True)
        
        # Add account age
        # Ensure both datetimes are timezone-aware
        utc_now = datetime.now(timezone.utc)
        account_age = utc_now - user.created_at
        account_age_str = f"{account_age.days} days"
        self.add_field(name="Account Age", value=account_age_str, inline=True)
        
        # Add risk factors if present
        if risk_factors:
            factors_text = "\n".join(f"• {factor}" for factor in risk_factors)
            self.add_field(name="Risk Factors", value=factors_text, inline=False)
        else:
            self.add_field(name="Risk Factors", value="None identified", inline=False)
            
        # Set footer
        self.set_footer(text=f"Powered by Theta AI • {FOOTER_TEXT}")
        
        # Set thumbnail to user avatar
        if user.avatar:
            self.set_thumbnail(url=user.avatar.url)


class UserProfiles(commands.Cog):
    """Cog for tracking user profiles and assessing risk levels using AI."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('userprofiles')
        self.message_cache = {}  # Cache for recent messages by user
        self.cache_size = 20  # Maximum number of messages to store per user
        
        # Configuration
        self.max_history_size = 10  # Number of messages to store in DB
        self.update_interval = 3600  # How often to update profiles (seconds)
        
        # Start background tasks
        self.profile_update_task.start()
        self.logger.info("User Profiles cog initialized")
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.profile_update_task.cancel()
    
    @tasks.loop(seconds=3600)  # Run every hour
    async def profile_update_task(self):
        """Background task to periodically update user profiles and risk assessments."""
        try:
            self.logger.info("Running scheduled profile updates")
            # Update profiles that haven't been updated in the last 24 hours
            if self.bot.pool:
                async with self.bot.pool.acquire() as conn:
                    # Find profiles needing updates
                    rows = await conn.fetch(
                        """
                        SELECT user_id FROM user_profiles 
                        WHERE profile_updated_at < NOW() - INTERVAL '24 hours'
                        LIMIT 50
                        """
                    )
                    
                    updated_count = 0
                    for row in rows:
                        user_id = row['user_id']
                        try:
                            # Fetch the user to get current information
                            user = await self.bot.fetch_user(user_id)
                            if user:
                                await self._update_risk_assessment(user)
                                updated_count += 1
                        except Exception as e:
                            self.logger.error(f"Error updating profile for user {user_id}: {e}")
                            
                    if updated_count:
                        self.logger.info(f"Updated {updated_count} user profiles")
        except Exception as e:
            self.logger.error(f"Error in profile update task: {e}")
    
    @profile_update_task.before_loop
    async def before_profile_update(self):
        """Wait until the bot is ready before starting the profile update task."""
        await self.bot.wait_until_ready()
        
    async def _get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Get a user profile from the database or create a new one if it doesn't exist."""
        if not self.bot.pool:
            return None
            
        async with self.bot.pool.acquire() as conn:
            # Try to fetch existing profile
            row = await conn.fetchrow(
                "SELECT * FROM user_profiles WHERE user_id = $1",
                user_id
            )
            
            if row:
                # Convert row to dict
                profile = dict(row)
                return profile
                
        # Return None if profile not found
        return None
    
    async def _create_or_update_profile(self, user: discord.User, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        """Create or update a user profile in the database."""
        if not self.bot.pool:
            return None
            
        try:
            async with self.bot.pool.acquire() as conn:
                # Check if profile exists
                profile = await self._get_user_profile(user.id)
                
                if profile:
                    # Update existing profile with guild info if provided
                    if guild:
                        # Get existing guilds
                        guilds = profile.get('guilds', [])
                        if not isinstance(guilds, list):
                            guilds = []
                            
                        # Check if this guild is already tracked
                        guild_exists = False
                        for g in guilds:
                            if g.get('guild_id') == guild.id:
                                guild_exists = True
                                # Update guild name if it changed
                                if g.get('guild_name') != guild.name:
                                    g['guild_name'] = guild.name
                                break
                                
                        # Add guild if not already present
                        if not guild_exists:
                            guilds.append({
                                'guild_id': guild.id,
                                'guild_name': guild.name,
                                'joined_at': datetime.now(timezone.utc).isoformat()
                            })
                            
                        # Update guild list in database
                        await conn.execute(
                            """
                            UPDATE user_profiles SET 
                            guilds = $1,
                            username = $2,
                            profile_updated_at = NOW()
                            WHERE user_id = $3
                            """,
                            json.dumps(guilds),
                            user.name,
                            user.id
                        )
                    
                    return profile
                else:
                    # Create new profile
                    guilds = []
                    if guild:
                        guilds.append({
                            'guild_id': guild.id,
                            'guild_name': guild.name,
                            'joined_at': datetime.now(timezone.utc).isoformat()
                        })
                    
                    # Insert new profile
                    await conn.execute(
                        """
                        INSERT INTO user_profiles (
                            user_id, username, guilds, 
                            created_at, profile_updated_at
                        ) VALUES ($1, $2, $3, NOW(), NOW())
                        """,
                        user.id,
                        user.name,
                        json.dumps(guilds)
                    )
                    
                    # Fetch the newly created profile
                    return await self._get_user_profile(user.id)
                    
        except Exception as e:
            self.logger.error(f"Error creating/updating profile for user {user.id}: {e}")
            return None
    
    async def _update_message_history(self, user_id: int, message_content: str, guild: discord.Guild):
        """Update a user's message history in their profile."""
        if not self.bot.pool:
            return
            
        try:
            async with self.bot.pool.acquire() as conn:
                # Get current message history
                row = await conn.fetchrow(
                    "SELECT message_history, message_count FROM user_profiles WHERE user_id = $1",
                    user_id
                )
                
                if not row:
                    # Profile doesn't exist yet
                    return
                    
                message_history = json.loads(row['message_history']) if row['message_history'] else []
                message_count = row['message_count'] or 0
                
                # Add new message to history
                new_message = {
                    'content': message_content[:200],  # Limit size
                    'guild_id': guild.id,
                    'guild_name': guild.name,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                # Keep limited history size, remove oldest if needed
                message_history.append(new_message)
                if len(message_history) > self.max_history_size:
                    message_history = message_history[-self.max_history_size:]
                
                # Update the profile
                await conn.execute(
                    """
                    UPDATE user_profiles SET 
                    message_history = $1,
                    message_count = $2,
                    last_message_content = $3,
                    last_message_guild_id = $4,
                    last_message_guild_name = $5,
                    last_message_at = NOW(),
                    profile_updated_at = NOW()
                    WHERE user_id = $6
                    """,
                    json.dumps(message_history),
                    message_count + 1,
                    message_content[:500],  # Store longer content for last message
                    guild.id,
                    guild.name,
                    user_id
                )
                
        except Exception as e:
            self.logger.error(f"Error updating message history for user {user_id}: {e}")
    
    async def _update_risk_assessment(self, user: discord.User) -> Tuple[str, float, List[str]]:
        """Update a user's risk assessment using AI analysis."""
        if not self.bot.pool:
            return "UNKNOWN", 0.0, []
            
        try:
            # Get user profile
            profile = await self._get_user_profile(user.id)
            if not profile:
                return "UNKNOWN", 0.0, []
            
            # Ensure user object has the required timezone-aware created_at attribute
            if not hasattr(user, 'created_at') or not user.created_at.tzinfo:
                self.logger.warning(f"User {user.id} has no timezone-aware created_at attribute")
                account_age_days = 0
            else:
                account_age_days = (datetime.now(timezone.utc) - user.created_at).days
                
            # Get data for AI analysis
            message_history = json.loads(profile.get('message_history', '[]'))
            message_count = profile.get('message_count', 0)
            
            # Default values
            risk_level = "LOW"  # Default risk level
            risk_score = 0.0    # Default risk score
            risk_factors = []   # Default risk factors
            
            # Check for AI service (reuse the existing AI moderation service from aimodcog)
            ai_cog = self.bot.get_cog('AIModeration')
            if ai_cog and ai_cog.enabled:
                # Start generating the risk assessment
                self.logger.info(f"Generating risk assessment for user {user.id} ({user.name})")
                
                # Extract message content for analysis
                message_texts = [msg.get('content', '') for msg in message_history]
                messages_joined = "\n".join(message_texts)
                
                # Create a prompt for the AI
                system_prompt = """You are an AI risk assessment system for a Discord server. 
                Analyze the user's message history and assess their risk level.
                Provide a risk assessment with the following components:
                1. RISK_LEVEL: One of LOW, MEDIUM, HIGH, VERY HIGH
                2. RISK_SCORE: A number from 0-100 representing risk (higher = more risky)
                3. RISK_FACTORS: A list of specific risk factors identified
                
                Respond with a JSON object containing these three fields.
                Example: {"risk_level": "LOW", "risk_score": 5.0, "risk_factors": []}
                """
                
                user_prompt = f"""
                User ID: {user.id}
                Username: {user.name}
                Account Age: {account_age_days} days
                Message Count: {message_count}
                
                Recent message samples:
                {messages_joined}
                
                Analyze this user's risk level. Consider:
                - Message content and tone
                - Suspicious patterns or behaviors
                - Signs of potential harmful activity
                
                Provide your assessment as a JSON with risk_level, risk_score, and risk_factors.
                """
                
                try:
                    # Use the AI service to get risk assessment
                    is_inappropriate, confidence, response = await ai_cog.analyze_message(
                        message_content=user_prompt,
                        guild_id=None,  # Global assessment
                        debug_mode=True,
                    )
                    
                    # Try to parse the AI response as JSON
                    self.logger.debug(f"Raw AI response for user {user.id}: {response}")
                    
                    # Extract JSON data from the response
                    import re
                    json_pattern = r'\{.*?\}'
                    json_match = re.search(json_pattern, response, re.DOTALL)
                    
                    if json_match:
                        json_str = json_match.group(0)
                        try:
                            risk_data = json.loads(json_str)
                            if isinstance(risk_data, dict):
                                risk_level = risk_data.get('risk_level', 'UNKNOWN')
                                risk_score = float(risk_data.get('risk_score', 0.0))
                                risk_factors = risk_data.get('risk_factors', [])
                                
                                # Ensure risk level is valid
                                valid_levels = ["LOW", "MEDIUM", "HIGH", "VERY HIGH", "UNKNOWN"]
                                if risk_level not in valid_levels:
                                    risk_level = "UNKNOWN"
                                    
                                # Ensure score is in valid range
                                risk_score = max(0.0, min(100.0, risk_score))
                        except (json.JSONDecodeError, ValueError) as e:
                            self.logger.error(f"Error parsing AI response for user {user.id}: {e}")
                    
                except Exception as e:
                    self.logger.error(f"Error getting risk assessment from AI for user {user.id}: {e}")
            
            # Update the profile with risk assessment
            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE user_profiles SET 
                    risk_assessment = $1,
                    risk_score = $2,
                    risk_factors = $3,
                    profile_updated_at = NOW()
                    WHERE user_id = $4
                    """,
                    risk_level,
                    risk_score,
                    json.dumps(risk_factors),
                    user.id
                )
                
            return risk_level, risk_score, risk_factors
            
        except Exception as e:
            self.logger.error(f"Error updating risk assessment for user {user.id}: {e}")
            return "UNKNOWN", 0.0, []

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track messages for user profiling."""
        # Skip bot messages, DMs
        if message.author.bot or not message.guild:
            return
            
        # Create or update user profile
        await self._create_or_update_profile(message.author, message.guild)
        
        # Update message history
        await self._update_message_history(message.author.id, message.content, message.guild)
        
        # Update user message cache
        user_id = message.author.id
        if user_id not in self.message_cache:
            self.message_cache[user_id] = []
            
        # Add message to cache and limit size
        self.message_cache[user_id].append({
            'content': message.content,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'guild_id': message.guild.id,
            'channel_id': message.channel.id
        })
        
        # Trim cache if needed
        if len(self.message_cache[user_id]) > self.cache_size:
            self.message_cache[user_id] = self.message_cache[user_id][-self.cache_size:]
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Track guild joins for user profiling."""
        if member.bot:
            return
            
        # Update profile with new guild
        await self._create_or_update_profile(member, member.guild)
        
    @app_commands.command(name="risklevel", description="Get AI-based risk assessment for a user")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def risk_level(self, interaction: discord.Interaction, user: discord.User):
        """Admin command to get the risk assessment for a user."""
        # Defer the response to allow time for processing
        await interaction.response.defer(ephemeral=True)
        
        # Check permissions
        if not interaction.user.guild_permissions.administrator and not interaction.user.guild_permissions.manage_guild:
            await interaction.followup.send("You need administrator or manage guild permissions to use this command.", ephemeral=True)
            return
            
        try:
            # Get the user's profile or create if it doesn't exist
            profile = await self._get_user_profile(user.id)
            
            if profile:
                # Check if we need to update the risk assessment (if older than 24 hours or missing)
                needs_update = (
                    profile.get('risk_assessment') == "UNKNOWN" or
                    profile.get('risk_assessment') is None or
                    'profile_updated_at' not in profile
                )
                
                # Check for update timing if profile_updated_at exists
                if not needs_update and 'profile_updated_at' in profile:
                    try:
                        # Ensure profile_updated_at is timezone-aware
                        profile_updated = profile['profile_updated_at']
                        if not profile_updated.tzinfo:
                            profile_updated = profile_updated.replace(tzinfo=timezone.utc)
                        
                        # Compare with current time
                        now = datetime.now(timezone.utc)
                        time_since_update = now - profile_updated
                        if time_since_update > timedelta(days=1):
                            needs_update = True
                    except (AttributeError, TypeError) as e:
                        # If there's any error with datetime handling, default to updating
                        self.logger.warning(f"Error comparing profile update times for user {user.id}: {e}")
                        needs_update = True
                
                if needs_update:
                    # Run risk assessment
                    risk_level, risk_score, risk_factors = await self._update_risk_assessment(user)
                else:
                    # Use existing assessment
                    risk_level = profile.get('risk_assessment', 'UNKNOWN')
                    risk_score = profile.get('risk_score', 0.0)
                    risk_factors = json.loads(profile.get('risk_factors', '[]'))
                    
                # Create and send embed with risk assessment
                embed = RiskLevelEmbed(user, risk_level, risk_score, risk_factors)
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            else:
                # Create profile and perform initial assessment
                await self._create_or_update_profile(user)
                risk_level, risk_score, risk_factors = await self._update_risk_assessment(user)
                
                # Create and send embed with risk assessment
                embed = RiskLevelEmbed(user, risk_level, risk_score, risk_factors)
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.error(f"Error getting risk level for user {user.id}: {e}")
            await interaction.followup.send(f"Error getting risk assessment: {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot):
    # Ensure the database has the necessary table
    if hasattr(bot, 'pool') and bot.pool:
        # The table creation is handled in frostmodv3.py init_db function
        pass
        
    await bot.add_cog(UserProfiles(bot))
