# Version1 验收与联调清单

## 一、启动检查

- [ ] 安装依赖：`pip install -r requirements.txt`
- [ ] 配置环境：复制 `.env.example` 为 `.env`，至少确认 `MYSQL_DSN`、`REDIS_URL`
- [ ] 如需真实模型：配置 `MODEL_WHITELIST` 为 `deepseek-v3.2,glm-5.1,minimax-m2.7`（示例），并填写对应密钥与地址
- [ ] 模型前缀与变量映射正确：`deepseek* -> DEEPSEEK_*`、`glm* -> GLM_*`、`minimax* -> MINIMAX_*`
- [ ] 启动服务：`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
- [ ] 健康检查：访问 `GET /health` 返回 `status=ok`

## 二、接口联调

- [ ] `GET /models` 返回模型列表，包含默认模型与优先级
- [ ] `POST /solve` 首次请求返回 `cache_hit=false`
- [ ] 相同题目再次 `POST /solve` 返回 `cache_hit=true`
- [ ] 响应字段完整：`trace_id`、`question_type`、`answer`、`confidence`、`model_source`、`latency_ms`、`validation`、`agent_outputs`

## 三、3.2 中部层能力验收

- [ ] 模型调度层：异常时自动重试并可回退至 `fallback_model`
- [ ] 多 Agent 协作层：可看到 `parse/retrieve/solve/verify` 输出
- [ ] 数据验证层：选择题/填空题/计算题/证明题均返回 `validation` 结果与标准化答案
- [ ] `validation` 中包含：`method`、`equivalence_score`、`normalized_expected`、`normalized_actual`
- [ ] 缓存与数据库层：缓存命中生效，数据库三表存在且有落库记录

## 四、数据库核验

- [ ] `solve_record` 有 trace 与答案记录
- [ ] `model_call_log` 有每个 agent 的调用记录
- [ ] `user_profile` 的 `solved_count` 可随调用增长

## 五、前端联调

- [ ] `front.html` 默认调用 `http://127.0.0.1:8000/solve`
- [ ] 页面显示答案与元信息（trace_id、置信度、缓存命中、耗时）
- [ ] 页面显示验证详情（通过状态、验证方法、等价分、标准表达、验证说明）
- [ ] 页面显示 `parse/retrieve/solve/verify` 的 Agent 输出摘要
- [ ] 错误场景可见明确提示

## 六、快速回归脚本

执行：

先开启后端：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

然后在根目录下，新开一个窗口，启动

```bash
python -m http.server 5500
```

接着打开网址

```bash
http://127.0.0.1:5500/front.html
```

即可开始测试