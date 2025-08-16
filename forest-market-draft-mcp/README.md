# Forest Market Draft MCP

专业的 Forest Market 产品草稿管理 MCP 服务器，提供完整的多用户草稿生命周期管理，经过深度优化，代码质量达到生产级别。

## 🎯 核心优势

### 📈 高效精简
- **8个核心工具**: 从13个工具精简优化，功能更强大
- **智能合并**: 3合1的搜索工具，2合1的获取工具
- **零冗余**: 移除过度设计，保留核心业务功能

### 🔒 企业级安全
- **静态Token认证**: 支持环境变量配置，云部署安全
- **用户权限隔离**: 严格的数据访问控制，防止越权
- **参数验证**: 完整的类型检查和业务规则验证

### 🏪 Forest Market专业集成
- **完整字段支持**: 覆盖所有Forest Market字段和验证规则
- **Digital Goods智能处理**: 自动清除运输字段，符合业务逻辑
- **多链支付**: 支持7种主流加密货币支付方式
- **专业导出**: 优化的forest_market格式，直接对接上架

### 🔄 灵活的更新机制
- **三种更新模式**: 完全替换、增量添加、选择删除
- **智能合并**: 自动处理重复项，保持数据完整性
- **版本控制**: 自动版本号管理和时间戳跟踪

### 🔍 强大的搜索能力
- **统一搜索入口**: 列表、搜索、过滤、统计一体化
- **智能文本匹配**: 支持标题、描述、标签、规格全文搜索
- **多维度过滤**: 分类、状态、价格范围组合过滤
- **相关性排序**: 基于匹配度的智能排序算法

## 📦 快速开始

### 安装依赖
```bash
# 使用uv安装项目和依赖
uv sync

# 或者如果还没有uv
pip install uv
uv sync
```

### 启动服务器
```bash
# 使用默认token启动
uv run python server.py

# 使用自定义token启动
MCP_AUTH_TOKEN=your-custom-token uv run python server.py

# 或者使用安装的命令行工具
uv run draft-mcp
```

### 认证配置
服务器使用静态token认证保护API：
- 默认token: `your-secret-token-2024`
- 自定义token: 设置环境变量 `MCP_AUTH_TOKEN`
- 客户端请求需要在Header中包含: `Authorization: Bearer <token>`

### 运行测试
```bash
# 运行测试文件
uv run python test_draft_mcp.py

# 或者使用pytest（开发依赖）
uv run pytest
```

## 🛠️ MCP工具说明

### 基础管理工具 (4个)

1. **create_draft(user_id, title, ...)**
   - 创建新产品草稿，user_id为必填
   - 支持Forest Market完整字段集
   - 自动处理Digital Goods（清除运输信息）
   - 支持变体、图片、规格、多链支付等

2. **get_draft(draft_id?, user_id?, summary_only?, batch_ids?)**
   - 灵活的草稿获取工具，支持多种模式
   - 单个详情、摘要模式、批量处理
   - 用户权限验证和访问控制

3. **delete_draft(draft_id, user_id?)**
   - 永久删除草稿
   - 可选用户权限验证

4. **export_draft(draft_id, user_id?, format?)**
   - 导出草稿用于Forest Market上架
   - 支持forest_market和json格式

### 草稿更新工具 (3个)

5. **update_draft(draft_id, user_id?, **fields)**
   - 完全替换字段值（价格、标题、描述等）
   - 自动处理Digital Goods逻辑
   - 版本控制和时间戳更新

6. **add_to_draft(draft_id, user_id?, **content)**
   - 增量添加内容到数组/对象字段
   - 智能合并变体、标签、图片、规格
   - 避免重复，保持数据完整性

7. **remove_from_draft(draft_id, user_id?, **content)**
   - 选择性移除特定内容
   - 支持删除变体选项或整个变体类型
   - 精确控制删除范围

### 搜索发现工具 (1个)

8. **list_drafts(user_id?, query?, category?, condition?, min_price?, max_price?, limit?, offset?, with_stats?)**
   - 统一的列表/搜索/统计工具
   - 智能文本搜索，支持标题、描述、标签、规格
   - 多维度过滤：分类、状态、价格范围
   - 分页支持和用户统计信息
   - 相关性评分排序

## 🔧 工具选择指南

### 更新操作选择
- **修改基础字段**（价格、标题、描述）→ `update_draft`
- **添加新选项**（新的变体、标签、图片）→ `add_to_draft`  
- **删除特定内容**（移除某个标签、变体）→ `remove_from_draft`

### 查询操作选择
- **获取特定草稿**（详情/摘要）→ `get_draft`
- **搜索/列表/统计**（发现草稿）→ `list_drafts`

## 📊 数据结构

### ProductDraft
```python
{
    "draft_id": "uuid",
    "user_id": "用户ID",
    "title": "产品标题",
    "description": "产品描述",
    "price": 价格(USDT),
    "category": "Digital Goods|DEPIN|Electronics|collectibles|Fashion|Custom|other",
    "condition": "New|Used",
    "variations": [{"name": "Color", "value": "Blue"}],
    "images": ["图片URL1", "图片URL2"],
    "contact_email": "联系邮箱",
    "ship_from": "United States|Singapore|Hong Kong|South Korea|Japan",
    "ship_to": ["目的地国家列表"],
    "shipping_fees": {"United States": 15.0, "Singapore": 10.0},
    "quantity": 数量,
    "discount_type": "Fixed Amount|Percentage",
    "discount_value": 折扣值,
    "payout_methods": ["ETH (Ethereum)", "USDC (Base)", ...],
    "tags": ["标签1", "标签2"],
    "specifications": {"规格名": "规格值"},
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "version": 版本号
}
```

## 💡 使用场景

### 场景1: 多用户产品管理
```python
# 用户zyz创建草稿
draft_id = create_draft(
    title="iPhone 15 Pro",
    user_id="zyz",
    description="苹果最新旗舰手机",
    price=1299.0,
    category="Electronics"
)

# 用户zyz666无法访问zyz的草稿（权限保护）
get_draft(draft_id, user_id="zyz666")  # 返回Access denied
```

### 场景2: 智能搜索和发现
```python
# 搜索iPhone相关产品
results = search_drafts(
    query="iPhone",
    user_id="zyz",
    category="Electronics",
    min_price=1000,
    max_price=2000
)

# 找相似产品
similar = find_similar(
    draft_id="某个iPhone草稿ID",
    user_id="zyz",
    similarity_threshold=0.3
)
```

### 场景3: Digital Goods特殊处理
```python
# 创建数字商品（自动清除运输信息）
nft_draft = create_draft(
    title="NFT Collection",
    category="Digital Goods",
    ship_from="United States",  # 会被自动清空
    ship_to=["Singapore"],      # 会被自动清空
    shipping_fees={"US": 10}    # 会被自动清空
)
```

### 场景4: 用户数据统计
```python
# 获取用户所有草稿和统计
user_data = get_user_drafts("zyz")
# 返回: 总草稿数、总价值、分类分布、平均价格等
```

## 🔐 安全特性

- **用户权限隔离**: 严格的用户数据访问控制
- **输入验证**: 使用Pydantic进行严格的类型和值验证
- **错误处理**: 安全的错误信息，不泄露系统信息
- **数据完整性**: 自动备份和恢复机制

## 🌐 与Dify集成

本MCP专为Dify平台设计，支持：

1. **HTTP传输**: 通过HTTP协议与Dify通信
2. **用户标识**: 从Dify获取用户ID进行数据隔离
3. **智能工作流**: 
   - Dify获取用户输入 → MCP创建草稿
   - AI优化产品信息 → MCP更新草稿  
   - 用户确认 → MCP导出上架

## 🔧 技术栈

- **FastMCP 2.0**: 现代化MCP服务器框架 + 静态Token认证
- **Python 3.10+**: 类型安全的核心开发语言
- **Pydantic**: 严格的数据验证和序列化
- **JSON**: 轻量级本地数据存储
- **UUID**: 全局唯一标识符生成

## 📁 项目结构

```
forest-market-draft-mcp/
├── models.py           # 数据模型定义 (ProductDraft)
├── storage.py          # 数据存储管理 (JSON持久化)
├── tools.py            # 8个MCP工具实现
├── server.py           # 服务器入口 + 认证配置
├── test_draft_mcp.py   # 完整测试套件
├── drafts.json         # 数据存储文件
├── pyproject.toml      # 项目配置和依赖
├── README.md           # 完整技术文档
└── OVERVIEW.md         # 项目概览 (团队协作)
```

## 📊 项目统计

### 代码质量
- **8个核心工具** (从13个精简优化)
- **100%类型注解** (类型安全保证)
- **完整参数验证** (Pydantic严格检查)
- **统一返回格式** (Dict[str, any])
- **生产级错误处理**

### 功能覆盖
- **Forest Market字段**: 100%完整支持
- **用户权限管理**: 严格的访问控制
- **多种更新模式**: 替换/添加/删除
- **智能搜索**: 全文检索+多维度过滤
- **批量操作**: 高效的数据处理

### 安全特性
- **静态Token认证**: 环境变量配置
- **用户数据隔离**: 防止越权访问
- **参数类型检查**: 运行时安全保证
- **业务规则验证**: Digital Goods智能处理

## 🚀 部署说明

1. **本地开发**: 直接运行 `python server.py`
2. **生产环境**: 建议使用Docker或systemd管理服务
3. **云平台**: 支持Vercel、Railway等平台部署
4. **数据备份**: 定期备份 `drafts.json` 文件

## 📈 性能特性

- **快速启动**: 轻量级设计，秒级启动
- **低内存占用**: 高效的内存管理
- **并发安全**: 支持多用户并发访问
- **自动优化**: 智能搜索算法优化

## 📄 许可证

MIT License - 详见 LICENSE 文件