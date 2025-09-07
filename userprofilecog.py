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
    
    async def analyze_activity_patterns(self, user_id: int) -> Dict[str, Any]:
        """Analyze user activity patterns to detect anomalies.
        
        This method analyzes several patterns:
        1. Hourly activity distribution for time-based anomalies
        2. Message velocity (sudden increases in message frequency)
        3. Guild joining patterns (rapid joining of multiple servers)
        
        Args:
            user_id: The user ID to analyze
            
        Returns:
            dict: Analysis results with pattern data and anomaly flags
        """
        if not self.bot.pool:
            return {}
            
        try:
            self.logger.info(f"Analyzing activity patterns for user {user_id}")
            results = {
                "hourly_pattern": {},
                "anomalies_detected": False,
                "anomaly_types": [],
                "message_velocity": {
                    "unusual_burst": False,
                    "burst_factor": 0.0
                },
                "join_pattern": {
                    "rapid_joins": False,
                    "velocity": 0.0
                },
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            }
            
            async with self.bot.pool.acquire() as conn:
                # 1. Analyze hourly activity distribution
                rows = await conn.fetch(
                    """SELECT 
                    EXTRACT(HOUR FROM (history->>'timestamp')::timestamptz) as hour,
                    COUNT(*) as message_count
                    FROM user_profiles,
                    jsonb_array_elements(message_history) as history
                    WHERE user_id = $1
                    GROUP BY hour
                    ORDER BY hour""",
                    user_id
                )
                
                if rows:
                    # Build hourly pattern
                    hourly_counts = {}
                    total_messages = 0
                    for row in rows:
                        hour = int(row['hour'])
                        count = row['message_count']
                        hourly_counts[hour] = count
                        total_messages += count
                    
                    # Calculate expected distribution (roughly even with peak during active hours)
                    if total_messages > 0:
                        results["hourly_pattern"] = hourly_counts
                        
                        # Look for unusual concentration (>70% of activity in off-hours 0-6)
                        night_hours_count = sum(hourly_counts.get(h, 0) for h in range(0, 6))
                        night_hours_percent = night_hours_count / total_messages if total_messages > 0 else 0
                        
                        if night_hours_percent > 0.7 and total_messages > 10:
                            results["anomalies_detected"] = True
                            results["anomaly_types"].append("unusual_hours")
                
                # 2. Check for message velocity anomalies
                # Look at messages per minute in recent history
                message_rows = await conn.fetch(
                    """SELECT 
                    (history->>'timestamp')::timestamptz as msg_time
                    FROM user_profiles,
                    jsonb_array_elements(message_history) as history
                    WHERE user_id = $1
                    ORDER BY (history->>'timestamp')::timestamptz DESC
                    LIMIT 100""",
                    user_id
                )
                
                if message_rows and len(message_rows) >= 5:
                    # Group by minute and look for bursts
                    messages_by_minute = {}
                    for row in message_rows:
                        minute_key = row['msg_time'].strftime("%Y-%m-%d %H:%M")
                        if minute_key in messages_by_minute:
                            messages_by_minute[minute_key] += 1
                        else:
                            messages_by_minute[minute_key] = 1
                    
                    # Calculate average and detect bursts
                    if messages_by_minute:
                        avg_per_minute = sum(messages_by_minute.values()) / len(messages_by_minute)
                        max_per_minute = max(messages_by_minute.values())
                        burst_factor = max_per_minute / avg_per_minute if avg_per_minute > 0 else 0
                        
                        results["message_velocity"]["burst_factor"] = burst_factor
                        if burst_factor > 5:  # 5x normal rate is suspicious
                            results["message_velocity"]["unusual_burst"] = True
                            results["anomalies_detected"] = True
                            results["anomaly_types"].append("message_burst")
                
                # 3. Check guild join patterns
                profile = await self._get_user_profile(user_id)
                if profile and 'guilds' in profile:
                    guilds = json.loads(profile.get('guilds', '[]')) if isinstance(profile.get('guilds'), str) else profile.get('guilds', [])
                    if len(guilds) >= 3:  # Only meaningful with at least 3 guilds
                        # Check for rapid joins (multiple servers in short time)
                        join_times = []
                        for guild in guilds:
                            if 'joined_at' in guild:
                                try:
                                    join_time = datetime.fromisoformat(guild['joined_at'].replace('Z', '+00:00'))
                                    join_times.append(join_time)
                                except (ValueError, AttributeError):
                                    continue
                                    
                        if len(join_times) >= 3:
                            # Sort join times and calculate time between joins
                            join_times.sort()
                            time_between_joins = [(join_times[i+1] - join_times[i]).total_seconds() 
                                                for i in range(len(join_times)-1)]
                            
                            # Calculate average time between joins
                            if time_between_joins:
                                avg_time = sum(time_between_joins) / len(time_between_joins)
                                # Very rapid joining (avg < 5 minutes between joins)
                                if avg_time < 300 and len(join_times) >= 3:
                                    results["join_pattern"]["rapid_joins"] = True
                                    results["join_pattern"]["velocity"] = 300 / avg_time if avg_time > 0 else 10
                                    results["anomalies_detected"] = True
                                    results["anomaly_types"].append("rapid_joins")
            
            # Store the analysis results in the user profile
            if results["anomalies_detected"]:
                self.logger.warning(
                    f"Anomalies detected for user {user_id}: {', '.join(results['anomaly_types'])}"
                )
                
                # Update the profile with analysis results
                async with self.bot.pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE user_profiles SET 
                        activity_pattern = $1,
                        profile_updated_at = NOW()
                        WHERE user_id = $2""",
                        json.dumps(results),
                        user_id
                    )
                    
            return results
                
        except Exception as e:
            self.logger.error(f"Error analyzing activity patterns for user {user_id}: {e}")
            return {"error": str(e), "anomalies_detected": False}
    
    async def _analyze_social_connections(self, user_id: int) -> float:
        """Analyze a user's social connections to identify patterns.
        
        This method identifies connections between users, particularly focusing on
        interactions with other high-risk users.
        
        Args:
            user_id: The user ID to analyze
            
        Returns:
            float: Social risk factor (0.0-1.0)
        """
        if not self.bot.pool:
            return 0.0
            
        try:
            social_risk = 0.0
            social_connections = {}
            
            async with self.bot.pool.acquire() as conn:
                # Find other users that the target user frequently interacts with
                # Using message_history which contains guild_id to identify mutual guilds
                profile = await self._get_user_profile(user_id)
                if not profile:
                    return 0.0
                    
                message_history = json.loads(profile.get('message_history', '[]')) if isinstance(profile.get('message_history'), str) else profile.get('message_history', [])
                
                # Extract guilds this user belongs to
                user_guilds = []
                if profile.get('guilds'):
                    guilds_data = json.loads(profile.get('guilds', '[]')) if isinstance(profile.get('guilds'), str) else profile.get('guilds', [])
                    user_guilds = [g.get('guild_id') for g in guilds_data if 'guild_id' in g]
                
                if not user_guilds:
                    return 0.0
                    
                # Find users who share multiple guilds
                shared_guild_users = await conn.fetch(
                    """SELECT up.user_id, up.risk_assessment, up.risk_score,
                    jsonb_array_length(up.guilds) as guild_count,
                    (SELECT COUNT(*) FROM (
                        SELECT g->>'guild_id' as guild_id FROM jsonb_array_elements(up.guilds) g
                        INTERSECT
                        SELECT unnest($1::bigint[]) as guild_id
                    ) as shared) as shared_guilds
                    FROM user_profiles up
                    WHERE up.user_id != $2
                    AND shared_guilds > 0
                    ORDER BY shared_guilds DESC
                    LIMIT 20""",
                    user_guilds, user_id
                )
                
                # Calculate social risk based on connections to high-risk users
                total_connections = len(shared_guild_users)
                if total_connections == 0:
                    return 0.0
                    
                # Count high-risk connections
                high_risk_connections = 0
                for row in shared_guild_users:
                    risk_level = row['risk_assessment']
                    risk_score = row['risk_score'] or 0.0
                    shared_count = row['shared_guilds']
                    
                    # Add to social connections dict
                    social_connections[row['user_id']] = {
                        "risk_level": risk_level,
                        "risk_score": risk_score,
                        "shared_guilds": shared_count
                    }
                    
                    # Count users with HIGH or VERY HIGH risk, or risk score > 70
                    if risk_level in ("HIGH", "VERY HIGH") or risk_score > 70:
                        # Weight by number of shared guilds (more shared = stronger connection)
                        high_risk_connections += shared_count
                
                # Calculate social risk factor (0.0-1.0)
                if high_risk_connections > 0:
                    # Normalize based on total connections
                    max_possible = sum(row['shared_guilds'] for row in shared_guild_users)
                    social_risk = high_risk_connections / max_possible if max_possible > 0 else 0.0
                    # Cap at 1.0
                    social_risk = min(1.0, social_risk)
                    
                    # Log if significant
                    if social_risk > 0.3:
                        self.logger.info(
                            f"User {user_id} has significant social connections to high-risk users "
                            f"(social risk factor: {social_risk:.2f})"
                        )
            
            return social_risk
                
        except Exception as e:
            self.logger.error(f"Error analyzing social connections for user {user_id}: {e}")
            return 0.0
    
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
            message_history = json.loads(profile.get('message_history', '[]')) if isinstance(profile.get('message_history'), str) else profile.get('message_history', [])
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
                message_texts = [msg.get('content', '') for msg in message_history if isinstance(msg, dict) and 'content' in msg]
                messages_joined = "\n".join(message_texts)
                
                # Also analyze activity patterns
                activity_patterns = await self.analyze_activity_patterns(user.id)
                
                # Get social connections risk factor
                social_risk = await self._analyze_social_connections(user.id) 
                
                # Create a prompt for the AI with enhanced context
                system_prompt = """You are an AI risk assessment system for a Discord server. 
                Analyze the user's message history, activity patterns, and connections to assess their risk level.
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
                
                Activity Anomalies: {"Yes, " + ", ".join(activity_patterns.get("anomaly_types", [])) if activity_patterns.get("anomalies_detected", False) else "None detected"}
                
                Social Risk Factor: {social_risk:.2f} (scale 0-1, higher means more connections to high-risk users)
                
                Analyze this user's risk level. Consider:
                - Message content and tone
                - Activity patterns and anomalies
                - Social connections to high-risk users
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
                                
                                # Boost risk score based on activity anomalies
                                if activity_patterns.get("anomalies_detected", False):
                                    anomaly_types = activity_patterns.get("anomaly_types", [])
                                    if anomaly_types:
                                        risk_score += min(15, len(anomaly_types) * 5)  # Up to +15 points
                                        risk_factors.append(f"Unusual activity patterns: {', '.join(anomaly_types)}")
                                
                                # Boost risk score based on social connections
                                if social_risk > 0.3:  # Significant connections to high-risk users
                                    risk_score += min(20, social_risk * 25)  # Up to +20 points
                                    risk_factors.append(f"Significant connections to high-risk users")
                                    
                                # Cap risk score at 100
                                risk_score = min(100.0, risk_score)
                                
                                # Update risk level based on final score
                                if risk_score >= 85:
                                    risk_level = "VERY HIGH"
                                elif risk_score >= 65:
                                    risk_level = "HIGH"
                                elif risk_score >= 40:
                                    risk_level = "MEDIUM"
                                else:
                                    risk_level = "LOW"
                                    
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
