"""
Enhanced Risk Assessment Module for FrostMod

This module extends the user profiling system by providing advanced risk
assessment capabilities beyond the basic AI-driven analysis.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Any, Optional

import discord


class RiskAnalyzer:
    """Advanced risk assessment for user activity."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('riskassessment')
        self.thresholds = {
            'message_burst': 5.0,    # Messages per minute threshold
            'night_activity': 0.7,   # % of messages during night hours (0-6)
            'rapid_joins': 300.0,    # Seconds between guild joins
            'social_risk': 0.3,      # Connection to risky users
            'content_variability': 0.8  # Similarity threshold
        }
    
    async def get_enhanced_risk_assessment(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive risk assessment combining multiple factors.
        
        Args:
            user_id: The user ID to analyze
            
        Returns:
            dict: Comprehensive risk assessment results
        """
        if not self.bot.pool:
            return {
                "risk_level": "UNKNOWN",
                "risk_score": 0.0,
                "risk_factors": [],
                "additional_data": {}
            }
            
        try:
            # Fetch user profile data
            async with self.bot.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM user_profiles WHERE user_id = $1",
                    user_id
                )
                
                if not row:
                    return {
                        "risk_level": "UNKNOWN",
                        "risk_score": 0.0,
                        "risk_factors": [],
                        "additional_data": {}
                    }
                
                profile = dict(row)
                
            # Get basic risk assessment data
            risk_level = profile.get('risk_assessment', 'UNKNOWN')
            risk_score = float(profile.get('risk_score', 0.0))
            risk_factors = json.loads(profile.get('risk_factors', '[]'))
            
            # Start building enhanced assessment
            additional_data = {}
            
            # 1. Analyze message patterns for content variability
            message_history = json.loads(profile.get('message_history', '[]'))
            message_content_variability = await self._analyze_content_variability(message_history)
            additional_data['content_variability'] = message_content_variability
            
            # 2. Check for shared IP addresses with known risky users
            # Note: This would require additional data collection not shown here
            # This is just a placeholder for the concept
            shared_ips = await self._check_shared_ip_addresses(user_id)
            additional_data['shared_ips'] = shared_ips
            
            # 3. Account creation clustering
            account_clustering = await self._analyze_account_creation_clustering(user_id)
            additional_data['account_clustering'] = account_clustering
            
            # 4. Enhance the risk score based on additional factors
            updated_risk = await self._calculate_enhanced_risk(
                risk_score, risk_factors, additional_data
            )
            
            return {
                "risk_level": updated_risk['risk_level'],
                "risk_score": updated_risk['risk_score'],
                "risk_factors": updated_risk['risk_factors'],
                "additional_data": additional_data
            }
                
        except Exception as e:
            self.logger.error(f"Error in enhanced risk assessment for user {user_id}: {e}")
            return {
                "risk_level": "ERROR",
                "risk_score": 0.0,
                "risk_factors": ["Error during analysis"],
                "additional_data": {"error": str(e)}
            }
    
    async def _analyze_content_variability(self, message_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze message content for suspicious repetition or templated spam.
        
        Returns:
            dict: Content variability analysis results
        """
        if not message_history or len(message_history) < 5:
            return {"score": 0.0, "suspicious": False}
            
        try:
            # Extract message texts
            messages = [msg.get('content', '') for msg in message_history 
                       if isinstance(msg, dict) and 'content' in msg]
            
            if not messages or len(messages) < 5:
                return {"score": 0.0, "suspicious": False}
                
            # Calculate average message length
            avg_length = sum(len(msg) for msg in messages) / len(messages)
            
            # Look for high similarity between messages (simplified approach)
            # A more sophisticated approach would use NLP similarity metrics
            unique_messages = set(messages)
            unique_ratio = len(unique_messages) / len(messages)
            
            # Detect unusual repetition
            suspicious = unique_ratio < 0.4 and len(messages) >= 8  # More than 60% repetition in 8+ messages
            
            return {
                "score": 1.0 - unique_ratio,  # Higher score means more repetition
                "suspicious": suspicious,
                "unique_ratio": unique_ratio,
                "message_count": len(messages),
                "avg_length": avg_length
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing content variability: {e}")
            return {"score": 0.0, "suspicious": False}
    
    async def _check_shared_ip_addresses(self, user_id: int) -> Dict[str, Any]:
        """Check if user shares IP addresses with known risky users.
        
        Note: This is a placeholder implementation and would require
        additional data collection not shown here.
        
        Returns:
            dict: Shared IP analysis results
        """
        # Placeholder implementation
        return {
            "shared_ips_found": False,
            "shared_with_count": 0,
            "high_risk_shared": 0
        }
    
    async def _analyze_account_creation_clustering(self, user_id: int) -> Dict[str, Any]:
        """Analyze if the account was created in a cluster with other suspicious accounts.
        
        Returns:
            dict: Account clustering analysis results
        """
        try:
            # Get user's account creation time
            user = await self.bot.fetch_user(user_id)
            if not user:
                return {"suspicious_cluster": False}
                
            creation_time = user.created_at
            
            # Look for other accounts created within a short time window
            # This is a simplified approach for demonstration
            window_start = creation_time - timedelta(minutes=30)
            window_end = creation_time + timedelta(minutes=30)
            
            # Search for accounts created in this window with similar patterns
            async with self.bot.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT user_id, risk_assessment, risk_score 
                    FROM user_profiles 
                    WHERE user_id IN (
                        -- This would ideally reference a table with account creation times
                        -- For this example, we're just using a placeholder query
                        SELECT user_id FROM user_profiles 
                        WHERE user_id != $1
                        LIMIT 5
                    )""",
                    user_id
                )
                
                # Count high-risk accounts
                high_risk_count = sum(1 for row in rows 
                                    if row['risk_assessment'] in ('HIGH', 'VERY HIGH'))
                
                return {
                    "suspicious_cluster": high_risk_count >= 2,
                    "cluster_size": len(rows),
                    "high_risk_in_cluster": high_risk_count
                }
                
        except Exception as e:
            self.logger.error(f"Error analyzing account clustering: {e}")
            return {"suspicious_cluster": False}
    
    async def _calculate_enhanced_risk(
        self, base_score: float, base_factors: List[str], additional_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate enhanced risk score using base assessment and additional factors.
        
        Returns:
            dict: Updated risk assessment
        """
        # Start with base score and factors
        risk_score = base_score
        risk_factors = base_factors.copy() if base_factors else []
        
        # Adjust for content variability
        content_var = additional_data.get('content_variability', {})
        if content_var.get('suspicious', False):
            risk_score += 10.0
            risk_factors.append("Suspicious message repetition pattern")
        
        # Adjust for shared IPs
        shared_ips = additional_data.get('shared_ips', {})
        if shared_ips.get('high_risk_shared', 0) > 0:
            risk_score += 15.0
            risk_factors.append("Shares connection with known high-risk accounts")
            
        # Adjust for account creation clustering
        clustering = additional_data.get('account_clustering', {})
        if clustering.get('suspicious_cluster', False):
            risk_score += 20.0
            risk_factors.append("Account created in suspicious cluster")
        
        # Cap risk score at 100
        risk_score = min(100.0, risk_score)
        
        # Determine risk level based on final score
        risk_level = "LOW"
        if risk_score >= 85:
            risk_level = "VERY HIGH"
        elif risk_score >= 65:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
            
        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors
        }


async def apply_risk_assessment(bot, user_id: int) -> Dict[str, Any]:
    """Helper function to apply enhanced risk assessment."""
    analyzer = RiskAnalyzer(bot)
    return await analyzer.get_enhanced_risk_assessment(user_id)
