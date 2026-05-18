## OpenClaw 的 Harness设计


### 一、整体架构图


OpenClaw 整体分层架构：**用户交互层、网关控制层、能力层与扩展层、底层状态存储**。

<div align=center>
    <image src="imgs/harness-1.webp" width=800>
</div>

由图可见，OpenClaw 是个 Gateway-First 的项目。

它上接多渠道入口，下连会话路由、插件扩展、记忆系统和运行时，中间是一条统一的执行主链路。

那么 OpenClaw 是如何与 LLM 协作的呢？也就是它的 Harness 层。

可以把 Harness 理解成 OpenClaw 面向 LLM 的结构化运行壳：

它负责 **组装 prompt、挂载 tools、接入 skills 和 memory、处理策略与安全限制**，再通过 Provider Adapter 与不同厂商的 LLM API 交互。

因为有 Harness，OpenClaw 才不是“直接把文本丢给模型”，而是真正具备了可扩展、可控制、可落地的 Agent 运行能力。

<div align=center>
    <image src="imgs/harness-2.webp" width=800>
</div>
&emsp;

>输入与上下文

- Harness 的原料层，包括 **用户消息/命令/会话历史/工作区文件/bootstrap 上下文**，以及插件提供的 **tools/skills** 等能力。

>Prompt装配器

- 将 system prompt、skills prompt、docs、bootstrap 文件、运行时信息等拼成最终给模型的提示词。

>模型解析与策略
- 这一层决定到底用哪个模型、什么 thinking 档位、哪个认证身份。
- 同时也处理模型 fallback、部分 hooks 对模型选择和 prompt 的干预等。

>工具与安全壳

- 限制模型可调用能力边界，避免直接乱碰系统，增强安全性。

>Agent会话与执行循环

- 这是 Agent Loop 的执行层，负责创建 Agent Session、接收流式输出、处理 Tool Call，再把工具结果回灌给模型。

>厂商适配器
- 将不同模型厂商的API调用统一封装，免除上层为每家模型重写一套运行逻辑。

>传输与认证

- 负责连上模型服务，包括HTTP、SSE、WebSocket等传输方式与认证机制。

>LLM API

- OpenClaw 的 Prompt、Tools、参数都会在这里给大模型，模型返回的内容也从这里返回。

>会话持久化与回传

- 结果落地层，把 transcript、stream delta、最终回复写回会话，并将结果继续投递到飞书、WebChat、CLI 等上层入口。

### 二、核心运行链路



消息为什么能跨渠道共享上下文？

无论消息来自CLI、WebChat还是外部渠道，最终都会落到同一条执行主线：**先找Session，再跑Agent，再决定如何回传**。

<div align=center>
    <image src="imgs/harness-3.webp" width=800>
</div>
各模块的配合如下：

- Telegram/Slack/飞书 等渠道负责接消息
- Routing 负责找到正确的 Agent 和 Session
- 编排层负责将消息组织成一次可执行任务（包括上下文整理、状态反馈等）
- Agent 负责生成内容，结合 prompt/memory/skills 等完成推理
- outbound/channel plugin 负责将结果按对应渠道返回

### 三、消息传递时序图

展示当一条消息从“收进来”到“发回去”的全过程，各个核心组件之间的交互顺序。

<div align=center>
    <image src="imgs/harness-4.webp" width=800>
</div>

OpenClaw 收到消息后，会先完成去重、顺序控制和基础校验，再结合账号、会话和话题线程，定位到正确的 Agent 和 Session。

接下来，系统会把 **正文、媒体、回复引用** 这些信息统一整理成上下文，再交给 Agent Runtime 执行。这个过程中，**策略判断、hooks、typing 状态、skills、工具调用和记忆检索** 都会参与进来。

等 Agent 产出结果后，系统再根据 replyTo 和线程关系，选择正确的投递目标，把回复发回 Telegram 等渠道。

### 四、记忆系统

OpenClaw 的记忆不是单一模块，而是由「工作区里的记忆文件」、「Agent运行时里的记忆工具」、「后台索引与检索层」三部分共同组成。

<div align=center>
    <image src="imgs/harness-5.webp" width=800>
</div>
如图所示：

- 在工作区，`MEMORY.md` 和 `memory/*.md` 是记忆本体，属于长期记忆。
- 在 Agent Runtime 中，`MEMORY.md` 直接注入上下文，只覆盖会话启动时的上下文，而 `memory/*.md` 是通过 `memory_search / memory_get` 按需读取。
- 后台还有个 Memory 索引与检索层，会把 `MEMORY.md` 和 `memory/*.md` 建成每个 agent 一份的 SQLite 索引，索引层负责 **chunk/embedding/检索**，不是记忆内容本身。

另外，关于小龙虾的人设文件（`SOUL.md / IDENTITY.md / USER.md`）等，虽然也是bootstrap persona上下文，但不在memory_search索引体系，不属于严格意义上的记忆，属于persona/identity注入。

<div align=center>
    <image src="imgs/harness-6.webp" width=800>
</div>


### 五、插件系统设计

Gateway 为中枢，插件系统是小龙虾的无限能力扩展。

下图展示了插件从“发现、加载、注册到运行时激活”的生命周期，以及Plugin SDK 如何支持不同类型的插件。

<div align=center>
    <image src="imgs/harness-7.webp" width=800>
</div>

OpenClaw 的插件不是把能力写死在主流程里。

系统会先发现插件、校验声明文件，再按配置决定哪些插件真正进入运行时。

进入运行时后，插件能力不会直接散落在系统各处，而是先汇总到“运行时激活注册表”。

- 渠道插件：负责接消息入口；
- 平台插件：负责扩展 tools、hooks、providers 和 skills；
- Gateway 注入点：负责将这些能力接到 methods、routes、services上。