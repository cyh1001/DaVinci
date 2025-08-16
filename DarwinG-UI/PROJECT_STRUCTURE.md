# DaVinci 项目目录结构

## 📁 整理后的目录结构

```
DaVinci-UI/
├── 📄 配置文件
│   ├── package.json           # 项目依赖和脚本
│   ├── pnpm-lock.yaml        # 包管理锁定文件
│   ├── tsconfig.json         # TypeScript 配置
│   ├── next.config.mjs       # Next.js 配置
│   ├── postcss.config.mjs    # PostCSS 配置
│   └── components.json       # UI 组件配置
│
├── 📁 app/                   # Next.js App Router
│   ├── layout.tsx           # 根布局组件
│   ├── page.tsx             # 主页面
│   └── api/                 # API 路由
│       ├── chat/            # 聊天相关 API
│       ├── conversations/   # 对话管理 API
│       ├── messages/        # 消息获取 API
│       ├── upload/          # 文件上传 API
│       └── stop/            # 停止生成 API
│
├── 📁 src/                  # 源代码目录 (新增)
│   ├── 📁 config/           # 配置文件
│   │   └── dynamic.tsx      # Dynamic.xyz 钱包配置
│   │
│   ├── 📁 types/            # TypeScript 类型定义
│   │   └── index.ts         # 通用类型定义
│   │
│   ├── 📁 constants/        # 常量定义
│   │   └── index.ts         # 应用常量
│   │
│   ├── 📁 hooks/            # 自定义 React Hooks
│   │   └── useLocalStorage.ts # localStorage 管理
│   │
│   ├── 📁 services/         # 服务层
│   │   └── api.ts           # API 服务封装
│   │
│
├── 📁 components/           # React 组件
│   ├── chat-bubbles.tsx    # 聊天气泡组件
│   ├── dynamic-wallet-connect.tsx # Dynamic 钱包连接
│   ├── sidebar.tsx         # 侧边栏组件
│   ├── tool-execution.tsx  # 工具执行显示
│   └── ui/                 # 基础 UI 组件
│       ├── badge.tsx
│       ├── button.tsx
│       ├── card.tsx
│       ├── dropdown-menu.tsx
│       ├── input.tsx
│       └── textarea.tsx
│
├── 📁 lib/                 # 工具库
│   ├── conversation.ts     # 对话管理工具
│   └── utils.ts           # 通用工具函数
│
├── 📁 styles/             # 样式文件
│   └── globals.css        # 全局样式
│
├── 📁 public/             # 静态资源
│   └── placeholder-*      # 占位图片
│
└── 📄 文档文件
    ├── README.md          # 项目说明
    ├── CLAUDE.md          # Claude 开发指南
    └── PROJECT_STRUCTURE.md # 项目结构说明
```

## 🔄 主要变更

### ✅ 已整理
1. **创建 `src/` 目录** - 更好的代码组织
2. **配置文件归类** - `src/config/` 目录
3. **类型定义集中** - `src/types/` 目录
4. **常量管理** - `src/constants/` 目录
5. **自定义 Hooks** - `src/hooks/` 目录
6. **服务层抽象** - `src/services/` 目录
8. **删除重复文件** - 清理了重复的 CSS 和未使用的组件

### 🎯 核心目录说明

#### `src/config/`
- 集中管理应用配置
- Dynamic.xyz 钱包配置
- 环境变量配置

#### `src/types/`
- TypeScript 类型定义
- 统一的接口规范
- 便于类型复用

#### `src/constants/`
- 应用常量定义
- API 端点配置
- 存储键名规范

#### `src/hooks/`
- 自定义 React Hooks
- 可复用的状态逻辑
- 组件间逻辑共享

#### `src/services/`
- API 服务层封装
- 统一的错误处理
- 可测试的业务逻辑


## 📋 下一步计划

1. **更新导入路径** - 所有文件使用新的目录结构
2. **添加路径别名** - 简化导入语句
3. **创建索引文件** - 统一导出接口
4. **优化构建配置** - 支持新目录结构

## 🚀 优势

- **更好的代码组织** - 按功能而不是文件类型分组
- **便于维护** - 清晰的职责分离
- **可扩展性强** - 容易添加新功能
- **团队协作友好** - 标准化的目录结构
- **构建优化** - 支持 Tree Shaking 和代码分割