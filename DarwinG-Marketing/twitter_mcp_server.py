#!/usr/bin/env python3
"""
Twitter MCP Server using FastMCP
Provides Twitter API functionality through MCP protocol
"""

import os
from typing import Optional, List
import virtuals_tweepy
from dotenv import load_dotenv
from fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Initialize FastMCP
mcp = FastMCP("Twitter Tools")

# Initialize Twitter client
def get_twitter_client():
    game_twitter_access_token = os.environ.get("GAME_TWITTER_ACCESS_TOKEN")
    if not game_twitter_access_token:
        raise ValueError("GAME_TWITTER_ACCESS_TOKEN not found in environment variables")
    return virtuals_tweepy.Client(game_twitter_access_token=game_twitter_access_token)

@mcp.tool()
def twitter_get_me() -> str:
    """Get authenticated user information"""
    try:
        client = get_twitter_client()
        response = client.get_me()
        user_data = response.data
        return f"Authenticated as @{user_data['username']} (ID: {user_data['id']})\nName: {user_data['name']}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_create_tweet(text: str, community_id: Optional[str] = None) -> str:
    """Create a new tweet
    
    Args:
        text: Tweet text content (max 280 characters)
        community_id: Optional community ID to post in
    """
    try:
        client = get_twitter_client()
        if community_id:
            response = client.create_tweet(text=text, community_id=community_id)
        else:
            response = client.create_tweet(text=text)
        
        tweet_id = response.data['id']
        return f"Tweet created successfully!\nTweet ID: {tweet_id}\nURL: https://twitter.com/user/status/{tweet_id}"
    except Exception as e:
        return f"Error creating tweet: {str(e)}"

@mcp.tool()
def twitter_get_tweets(tweet_ids: List[str], tweet_fields: Optional[List[str]] = None) -> str:
    """Get tweets by IDs
    
    Args:
        tweet_ids: List of tweet IDs to retrieve
        tweet_fields: Additional tweet fields to include (default: ["created_at"])
    """
    try:
        client = get_twitter_client()
        if tweet_fields is None:
            tweet_fields = ["created_at"]
        
        response = client.get_tweets(tweet_ids, tweet_fields=tweet_fields)
        
        if response.data:
            result = []
            for tweet in response.data:
                result.append(f"Tweet ID: {tweet.id}\nText: {tweet.text}\nCreated: {getattr(tweet, 'created_at', 'N/A')}")
            return "\n\n".join(result)
        else:
            return "No tweets found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_get_users(user_ids: Optional[List[str]] = None, usernames: Optional[List[str]] = None, 
                     user_fields: Optional[List[str]] = None) -> str:
    """Get user information by IDs or usernames
    
    Args:
        user_ids: List of user IDs to retrieve
        usernames: List of usernames to retrieve
        user_fields: Additional user fields to include (default: ["profile_image_url", "public_metrics"])
    """
    try:
        client = get_twitter_client()
        if user_fields is None:
            user_fields = ["profile_image_url", "public_metrics"]
        
        if user_ids:
            response = client.get_users(ids=user_ids, user_fields=user_fields)
        elif usernames:
            response = client.get_users(usernames=usernames, user_fields=user_fields)
        else:
            return "Please provide either user_ids or usernames"
        
        if response.data:
            result = []
            for user in response.data:
                metrics = getattr(user, 'public_metrics', {})
                result.append(f"User: @{user.username} ({user.name})\nID: {user.id}\nFollowers: {metrics.get('followers_count', 'N/A')}")
            return "\n\n".join(result)
        else:
            return "No users found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_search_recent_tweets(query: str, max_results: int = 10, 
                                tweet_fields: Optional[List[str]] = None) -> str:
    """Search recent tweets (last 7 days)
    
    Args:
        query: Search query string
        max_results: Maximum results to return (10-100, default: 10)
        tweet_fields: Additional tweet fields to include
    """
    try:
        client = get_twitter_client()
        if tweet_fields is None:
            tweet_fields = ["created_at", "author_id", "public_metrics"]
        
        response = client.search_recent_tweets(query, max_results=max_results, tweet_fields=tweet_fields)
        
        if response.data:
            result = []
            for tweet in response.data:
                metrics = getattr(tweet, 'public_metrics', {})
                result.append(f"Tweet ID: {tweet.id}\nAuthor ID: {getattr(tweet, 'author_id', 'N/A')}\nText: {tweet.text}\nLikes: {metrics.get('like_count', 'N/A')}")
            return "\n\n".join(result)
        else:
            return "No tweets found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_get_users_tweets(user_id: str, max_results: int = 10, 
                            tweet_fields: Optional[List[str]] = None) -> str:
    """Get tweets from a specific user
    
    Args:
        user_id: User ID to get tweets from
        max_results: Maximum results to return (5-100, default: 10)
        tweet_fields: Additional tweet fields to include
    """
    try:
        client = get_twitter_client()
        if tweet_fields is None:
            tweet_fields = ["created_at", "public_metrics"]
        
        response = client.get_users_tweets(user_id, max_results=max_results, tweet_fields=tweet_fields)
        
        if response.data:
            result = []
            for tweet in response.data:
                metrics = getattr(tweet, 'public_metrics', {})
                result.append(f"Tweet ID: {tweet.id}\nCreated: {getattr(tweet, 'created_at', 'N/A')}\nText: {tweet.text}\nLikes: {metrics.get('like_count', 'N/A')}")
            return "\n\n".join(result)
        else:
            return "No tweets found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_get_users_followers(user_id: str, max_results: int = 100, 
                               user_fields: Optional[List[str]] = None) -> str:
    """Get followers of a user
    
    Args:
        user_id: User ID to get followers for
        max_results: Maximum results to return (1-1000, default: 100)
        user_fields: Additional user fields to include
    """
    try:
        client = get_twitter_client()
        if user_fields is None:
            user_fields = ["profile_image_url", "public_metrics"]
        
        response = client.get_users_followers(user_id, max_results=max_results, user_fields=user_fields)
        
        if response.data:
            result = []
            for user in response.data:
                metrics = getattr(user, 'public_metrics', {})
                result.append(f"@{user.username} ({user.name})\nFollowers: {metrics.get('followers_count', 'N/A')}")
            return f"Found {len(response.data)} followers:\n\n" + "\n\n".join(result)
        else:
            return "No followers found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_get_liked_tweets(user_id: Optional[str] = None, max_results: int = 10, 
                            tweet_fields: Optional[List[str]] = None) -> str:
    """Get tweets liked by a user
    
    Args:
        user_id: User ID to get liked tweets for (defaults to authenticated user)
        max_results: Maximum results to return (5-100, default: 10)
        tweet_fields: Additional tweet fields to include
    """
    try:
        client = get_twitter_client()
        if not user_id:
            user_id = client.get_me().data['id']
        if tweet_fields is None:
            tweet_fields = ["created_at", "author_id"]
        
        response = client.get_liked_tweets(user_id, user_auth=True, tweet_fields=tweet_fields, max_results=max_results)
        
        if response.data:
            result = []
            for tweet in response.data:
                result.append(f"Tweet ID: {tweet.id}\nCreated: {getattr(tweet, 'created_at', 'N/A')}\nAuthor ID: {getattr(tweet, 'author_id', 'N/A')}\nText: {tweet.text}")
            return "\n\n".join(result)
        else:
            return "No liked tweets found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_get_liking_users(tweet_id: str, user_fields: Optional[List[str]] = None) -> str:
    """Get users who liked a specific tweet
    
    Args:
        tweet_id: Tweet ID to get liking users for
        user_fields: Additional user fields to include
    """
    try:
        client = get_twitter_client()
        if user_fields is None:
            user_fields = ["profile_image_url", "public_metrics"]
        
        response = client.get_liking_users(tweet_id, user_fields=user_fields)
        
        if response.data:
            result = []
            for user in response.data:
                metrics = getattr(user, 'public_metrics', {})
                result.append(f"@{user.username} ({user.name})\nFollowers: {metrics.get('followers_count', 'N/A')}")
            return f"Users who liked this tweet:\n\n" + "\n\n".join(result)
        else:
            return "No liking users found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_get_retweeters(tweet_id: str, user_fields: Optional[List[str]] = None) -> str:
    """Get users who retweeted a specific tweet
    
    Args:
        tweet_id: Tweet ID to get retweeters for
        user_fields: Additional user fields to include
    """
    try:
        client = get_twitter_client()
        if user_fields is None:
            user_fields = ["profile_image_url", "public_metrics"]
        
        response = client.get_retweeters(tweet_id, user_fields=user_fields)
        
        if response.data:
            result = []
            for user in response.data:
                metrics = getattr(user, 'public_metrics', {})
                result.append(f"@{user.username} ({user.name})\nFollowers: {metrics.get('followers_count', 'N/A')}")
            return f"Users who retweeted this tweet:\n\n" + "\n\n".join(result)
        else:
            return "No retweeters found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_get_recent_tweets_count(query: str, granularity: str = "hour") -> str:
    """Get count of recent tweets matching a query
    
    Args:
        query: Search query string
        granularity: Time granularity for counts ("minute", "hour", "day", default: "hour")
    """
    try:
        client = get_twitter_client()
        response = client.get_recent_tweets_count(query, granularity=granularity)
        
        if response.data:
            result = []
            total_count = 0
            for count_data in response.data:
                start = count_data.get('start', 'N/A')
                end = count_data.get('end', 'N/A')
                tweet_count = count_data.get('tweet_count', 0)
                total_count += tweet_count
                result.append(f"Period: {start} to {end}\nTweets: {tweet_count}")
            
            return f"Tweet count for query '{query}':\nTotal: {total_count} tweets\n\nBreakdown:\n" + "\n\n".join(result)
        else:
            return "No count data found"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def twitter_get_users_mentions(user_id: str, max_results: int = 10, 
                              tweet_fields: Optional[List[str]] = None) -> str:
    """Get tweets mentioning a specific user
    
    Args:
        user_id: User ID to get mentions for
        max_results: Maximum results to return (5-100, default: 10)
        tweet_fields: Additional tweet fields to include
    """
    try:
        client = get_twitter_client()
        if tweet_fields is None:
            tweet_fields = ["created_at", "author_id"]
        
        response = client.get_users_mentions(user_id, max_results=max_results, tweet_fields=tweet_fields)
        
        if response.data:
            result = []
            for tweet in response.data:
                result.append(f"Tweet ID: {tweet.id}\nAuthor ID: {getattr(tweet, 'author_id', 'N/A')}\nCreated: {getattr(tweet, 'created_at', 'N/A')}\nText: {tweet.text}")
            return f"Mentions for user {user_id}:\n\n" + "\n\n".join(result)
        else:
            return "No mentions found"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)