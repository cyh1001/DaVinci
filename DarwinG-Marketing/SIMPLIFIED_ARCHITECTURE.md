# 简化Marketing Agent架构

## 核心流程

```
用户前端 -> 输入Bearer Token -> 系统存储 -> AI对话 -> MCP工具识别用户ID -> 调用对应Token -> 执行Twitter操作
```

## 系统组件

### 1. 用户Token管理
```python
# 用户提交token到前端
# 系统加密存储token并分配user_id
# AI对话时传递user_id上下文
```

### 2. 改进的MCP工具
```python
# 所有MCP工具新增user_id参数
# 根据user_id从数据库获取对应token
# 动态创建Twitter客户端实例
```

### 3. AI上下文管理
```python
# AI对话开始时设置用户上下文
# MCP工具自动获取当前用户ID
# 无需用户重复输入认证信息
```

## 技术实现

### 数据存储 (简化版)
- SQLite本地存储 (可升级到PostgreSQL)
- 用户ID -> 加密Token映射
- 基本的用户会话管理

### 安全措施
- Token AES加密存储
- 会话超时机制
- 基本的访问控制

## 优势
1. **用户友好**: 一次配置，持续使用
2. **开发简单**: 最小化架构复杂度  
3. **易扩展**: 后续可升级到完整多租户系统
4. **安全可控**: Token不暴露给AI，只在系统内部使用