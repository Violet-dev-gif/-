# EducationClaw Backend (Version1)

## 快速启动

1. 创建虚拟环境并安装依赖：

```bash
pip install -r requirements.txt
```

2. 复制配置文件：

```bash
copy .env.example .env
```

3. 启动服务：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 已实现能力

- `/health`：服务健康检查。
- `/models`：模型路由状态与优先级。
- `/solve`：题目求解主链路，包含模型调度、多 Agent 协作、投票融合、答案验证、缓存与数据库落库。
- 缓存策略：优先 Redis，失败自动回退内存缓存。
- 数据库：`solve_record`、`user_profile`、`model_call_log` 三张核心表。

## 说明

- Version1 默认启用 `mock-primary` / `mock-backup`，可在环境变量中替换为真实模型。
- 可按模型名前缀接入真实模型：
  - `glm*` 使用 `GLM_BASE_URL` + `GLM_API_KEY`
  - `deepseek*` 使用 `DEEPSEEK_BASE_URL` + `DEEPSEEK_API_KEY`
  - `minimax*` / `abab*` 使用 `MINIMAX_BASE_URL` + `MINIMAX_API_KEY`
- 示例：
  - `MODEL_WHITELIST=deepseek-v3.2,glm-5.1,minimax-m2.7,mock-backup`
  - `DEFAULT_MODEL=deepseek-v3.2`
  - `FALLBACK_MODEL=glm-5.1`
- 向量检索仅保留接口，后续可对接 Milvus/pgvector。
- 联调验收清单见 `ACCEPTANCE_CHECKLIST.md`，一键冒烟见 `python scripts/smoke_test.py`。
