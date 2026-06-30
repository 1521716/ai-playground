# CLAUDE.md — ai-playground

> AI 辅助实验项目合集。每个子目录是一个独立项目。

---

## 项目索引

| 目录 | 说明 | 入口文件 | 关键依赖 |
|------|------|----------|----------|
| `gaokao-assistant/` | 高考志愿大学助手 | `server.py`, `index.html` | Python stdlib, DeepSeek API |

---

## gaokao-assistant 开发速查

```bash
# 启动后端（本地开发）
cd gaokao-assistant
# 设置 API Key
export DEEPSEEK_API_KEY=sk-your-key
# 启动服务器
python server.py
# 访问 http://localhost:8080
```

### 项目结构
```
gaokao-assistant/
├── index.html       # 前端（单页应用，纯原生 JS）
├── server.py        # Python 后端（http.server）
├── data.json        # 数据库（68MB，4141所大学，Git LFS）
├── convert_data.py  # CSV → JSON 转换
└── gaokao_data_collegeschat/  # 原始数据源
```

### 注意事项
- `data.json` 使用 Git LFS 管理（68MB）
- API Key 通过环境变量 `DEEPSEEK_API_KEY` 传入，**不要硬编码**
- 前端 API 地址在 `index.html` 中配置，部署时需改为实际后端 URL
