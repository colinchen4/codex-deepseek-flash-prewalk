# 兼容性与安全边界

## 支持范围

- macOS
- Windows
- Python 3.11+
- ChatGPT/Codex 桌面应用至少启动过一次
- DeepSeek 官方 Responses API
- `deepseek-flash`
- 思考程度 `max`

## 配置位置

默认 `CODEX_HOME` 为 `~/.codex`：

- Codex 配置：`$CODEX_HOME/config.toml`
- 合并模型目录：`$CODEX_HOME/models-with-deepseek.json`
- 自定义角色：`$CODEX_HOME/agents/DeepSeek.toml`（默认即 `~/.codex/agents/DeepSeek.toml`）
- 管理状态与备份：`$CODEX_HOME/codex-deepseek-subagent/`
- 系统凭据目标：`codex-deepseek-api-key`
  - macOS：Keychain
  - Windows：Credential Manager

程序不修改顶层 `model` 或顶层 `model_provider`，主任务仍使用用户原来的模型和登录方式。

## 执行面兼容性

检查和验收只使用桌面应用内置运行时，不回退到 PATH 中可能版本不同的独立 CLI。Windows Store 安装版位于受保护的 `WindowsApps` 目录；`setup`、`repair` 或 `test` 会把 `codex.exe` 与同目录 `codex-code-mode-host.exe` 一起缓存到 `$CODEX_HOME/codex-deepseek-subagent/desktop-runtime/`。只复制单个 `codex.exe` 会导致验收会话报告 code-mode host 缺失。通过 `CODEX_DESKTOP_BIN` 指定自定义路径时，同目录也必须包含 host。版本号仅作诊断；兼容性由模型目录解析、DeepSeek 直连和执行面口令验收共同决定。

父模型从桌面当前配置动态读取。管理程序会把 `features.multi_agent_v2` 设为 `false`，并把该父模型的 `multi_agent_version` 固定为 `v1`。父模型变化后运行 `repair`。

桌面 CLI ≥0.146 起，collab/spawn_agent 命名空间被限定在 ChatGPT 后端：原生 `spawn_agent(agent_type="DeepSeek")` 创建的子线程强制走 `openai` provider，自定义 `model_provider` 被忽略，非 OpenAI 模型会直接收到 model-unsupported 400。因此日常 DeepSeek 执行段统一走受管执行面——由本 Skill 管理的 `codex exec` 子进程：

```text
codex exec --skip-git-repo-check -s workspace-write -C "<workspace>" \
  -m deepseek-flash -c model_provider="deepseek" -c model_reasoning_effort="max" - < "<handoff-package>"
```

该形态在 0.144–0.154 均可用：它只依赖顶层 `model_provider` 覆盖，不经过 collab 命名空间。派发方（如 prewalk skill）从 `status` 获取缓存运行时路径并显式设置 `CODEX_HOME`。

`setup` 或 `test` 会通过桌面内置运行时创建隔离验收会话。验收证据为：受管 `codex exec` 进程以 `deepseek` provider、`deepseek-flash` 模型、`max` 思考程度运行，并返回固定口令 `NATIVE_DEEPSEEK_OK`；可以忽略口令末尾的中英文句号、问号或感叹号，但不能接受其他文本差异。

## API Key

API Key 可由用户在聊天中提供。管理程序从标准输入读取，不写入命令参数、临时文件、配置文件或测试结果。macOS 将密钥保存到 Keychain，Windows 将密钥保存到 Credential Manager。

启动 Codex 验收子进程时会从该子进程环境中移除大小写形式的 `CODEX_API_KEY`，防止它覆盖桌面 ChatGPT 登录并把父模型请求路由到错误的 Provider；不会修改用户级或系统级环境变量。

不要在最终回复、日志摘要、异常信息或测试夹具中重复 API Key。

## 配置事务

写入前创建带时间戳的备份。程序使用进程锁避免并发修改，先生成候选配置并用 TOML、JSON 解析验证，再原子替换目标文件。写入、卸载或实时测试失败时，恢复本次事务开始前的文件。

已存在但不属于本 Skill 的冲突配置不会被静默覆盖；完全兼容的现有配置可以被采用，并在结果中标记 `adopted_existing`。

## 视觉输入

DeepSeek-V4.1-Flash 原生接受图片和截图。视频仍由父 Agent 先转成文字任务包。
