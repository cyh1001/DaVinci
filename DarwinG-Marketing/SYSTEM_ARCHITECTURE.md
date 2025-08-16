# Marketing Agent System Architecture

## 系统概述

一个多租户的Twitter Marketing Agent系统，允许用户连接自己的Twitter账户，使用AI驱动的营销工具。

## 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   Mobile App    │    │  External APIs  │
│   (React/Vue)   │    │   (Optional)    │    │  (Webhooks)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────────────────────┼─────────────────────────────────┐
│                             API Gateway                            │
│                         (FastAPI + Auth)                           │
└─────────────────────────────────┼─────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ User Management │    │ Campaign Engine │    │ Analytics Engine│
│   & Auth        │    │ (AI Marketing)  │    │  & Reporting    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────────────────────┼─────────────────────────────────┐
│                        MCP Manager                                  │
│              (Dynamic MCP Server Instances)                        │
└─────────────────────────────────┼─────────────────────────────────┘
                                 │
┌─────────────────────────────────┼─────────────────────────────────┐
│                         Database Layer                             │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│    │   PostgreSQL │  │    Redis    │  │  Vector DB  │              │
│    │   (Main DB)  │  │   (Cache)   │  │ (AI Memory) │              │
│    └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. User Management & Authentication
- 用户注册/登录
- Twitter OAuth集成
- Token安全存储和管理
- 权限控制

### 2. MCP Manager
- 动态创建用户专属MCP服务器实例
- Token注入和管理
- 服务器生命周期管理
- 负载均衡

### 3. Campaign Engine (AI Marketing Core)
- 内容策略生成
- 自动化发布调度
- A/B测试管理
- 受众分析和定位

### 4. Analytics Engine
- 实时数据收集
- 性能分析和洞察
- ROI计算
- 报告生成

## 数据库设计

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    subscription_tier VARCHAR(50) DEFAULT 'free'
);
```

### Twitter Connections Table
```sql
CREATE TABLE twitter_connections (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    twitter_username VARCHAR(255),
    encrypted_token TEXT NOT NULL,
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
```

### Campaigns Table
```sql
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    starts_at TIMESTAMP,
    ends_at TIMESTAMP
);
```

### Campaign Analytics Table
```sql
CREATE TABLE campaign_analytics (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    metric_name VARCHAR(100),
    metric_value DECIMAL,
    recorded_at TIMESTAMP DEFAULT NOW()
);
```

## 安全考虑

1. **Token加密**: 所有Twitter tokens使用AES-256加密存储
2. **API Rate Limiting**: 防止滥用和确保公平使用
3. **数据隔离**: 用户数据完全隔离，无法交叉访问
4. **审计日志**: 记录所有重要操作
5. **HTTPS Only**: 所有通信使用TLS加密

## 部署架构

### 开发环境
- Docker Compose
- PostgreSQL + Redis
- 本地文件存储

### 生产环境
- Kubernetes集群
- 托管数据库(AWS RDS/Google Cloud SQL)
- Redis集群
- CDN + 负载均衡器

## API设计示例

```
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me

POST /api/twitter/connect
GET  /api/twitter/status
DELETE /api/twitter/disconnect

GET  /api/campaigns
POST /api/campaigns
PUT  /api/campaigns/{id}
DELETE /api/campaigns/{id}

GET  /api/analytics/dashboard
GET  /api/analytics/campaigns/{id}

POST /api/ai/generate-content
POST /api/ai/analyze-audience
POST /api/ai/optimize-timing
```