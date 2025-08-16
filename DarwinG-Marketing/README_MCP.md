# Twitter MCP Tools

这个项目提供了一个完整的Twitter API MCP工具集，使用FastMCP框架构建。

## 功能列表

### 认证和用户信息
- `twitter_get_me()` - 获取当前认证用户信息

### 推特管理
- `twitter_create_tweet(text, community_id?)` - 创建新推特
- `twitter_get_tweets(tweet_ids, tweet_fields?)` - 根据ID获取推特
- `twitter_search_recent_tweets(query, max_results?, tweet_fields?)` - 搜索最近推特

### 用户管理
- `twitter_get_users(user_ids?, usernames?, user_fields?)` - 获取用户信息
- `twitter_get_users_tweets(user_id, max_results?, tweet_fields?)` - 获取用户推特
- `twitter_get_users_followers(user_id, max_results?, user_fields?)` - 获取用户关注者
- `twitter_get_users_mentions(user_id, max_results?, tweet_fields?)` - 获取用户提及

### 互动功能
- `twitter_get_liked_tweets(user_id?, max_results?, tweet_fields?)` - 获取点赞的推特
- `twitter_get_liking_users(tweet_id, user_fields?)` - 获取点赞用户
- `twitter_get_retweeters(tweet_id, user_fields?)` - 获取转推用户

### 分析工具
- `twitter_get_recent_tweets_count(query, granularity?)` - 获取推特数量统计

## 安装和配置

1. 安装依赖：
```bash
uv add fastmcp virtuals-tweepy python-dotenv
```

2. 配置环境变量（在.env文件中）：
```
GAME_TWITTER_ACCESS_TOKEN=your_actual_token_here
```

3. 运行MCP服务器：
```bash
python twitter_mcp_server.py
```

## 使用方法

### 直接运行服务器
```bash
python twitter_mcp_server.py
```

### 在Claude Code中配置
在你的Claude Code配置中添加MCP服务器：

```json
{
  "mcpServers": {
    "twitter-tools": {
      "command": "python",
      "args": ["twitter_mcp_server.py"],
      "cwd": "D:\\workspace\\DarwinG-Marketing",
      "env": {
        "GAME_TWITTER_ACCESS_TOKEN": "your_token_here"
      }
    }
  }
}
```

## 工具示例

### 创建推特
```python
# 通过MCP调用
twitter_create_tweet("Hello from MCP! 🚀")
```

### 搜索推特
```python
# 搜索包含"AI"的最新推特
twitter_search_recent_tweets("AI", max_results=20)
```

### 获取用户信息
```python
# 根据用户名获取信息
twitter_get_users(usernames=["elonmusk", "openai"])
```

### 分析推特互动
```python
# 获取某条推特的点赞用户
twitter_get_liking_users("1234567890123456789")
```

## 注意事项

1. 确保你的GAME_TWITTER_ACCESS_TOKEN是有效的
2. 某些功能需要特定的权限级别
3. API调用有速率限制
4. 所有工具都包含错误处理

## 文件结构

```
DarwinG-Marketing/
├── twitter_mcp_server.py    # 主MCP服务器文件
├── examples/                # Twitter API示例代码
├── .env                     # 环境变量配置
├── mcp_config.json         # MCP客户端配置
└── README_MCP.md           # 本说明文件
```