你这个场景可以抽象成三层并发：**租户请求并发（QPS）** × **单请求内多 PDF 并发** × **每个 PDF 的内部步骤并发**（下载/解析/OCR/向量化/LLM）。在一个容器里要稳，关键是：**控制并发、隔离阻塞、按资源分池**，别让某一类任务把整个 event loop 卡死。

下面是我建议的“实战可落地”方案（偏保守但稳）。

---

## 1) 总体原则：一个容器内用“async 为主 + 线程池/进程池兜底”

* **I/O（下载 PDF、请求 OSS、调用外部 API/LLM、向量库）**：用 `asyncio` 协程并发
* **CPU 重（PDF 解析、OCR、embedding 本地算、图像处理）**：

  * 如果库是纯 Python/可能占用 GIL：用 **ProcessPool**（更稳）
  * 如果库会释放 GIL（很多 C 扩展会）：用 **ThreadPool**
* **永远别在 async 里直接跑阻塞 CPU/阻塞 I/O**（否则整个服务吞吐掉到地板）

---

## 2) 并发控制：三把 Semaphore（全局 / 每请求 / 外部依赖）

### A. 全局“服务总并发”限制（保护容器）

* 例：同时最多处理 `N` 个 PDF（跨所有租户、所有请求）
* `GLOBAL_PDF_SEM = Semaphore(N)`（N 通常 8~32，按 CPU/内存/外部限流调）

### B. 单个请求内的 PDF 并发限制（避免一个大请求吃光资源）

* `PER_REQUEST_PDF_SEM = Semaphore(k)`（k 通常 2~6）

### C. 下游依赖限流（LLM / 向量库 / OCR 服务）

* `LLM_SEM = Semaphore(m)`（m 通常 2~10，看供应商限流）
* `EMBED_SEM = Semaphore(e)` …

> 这样即使一个租户一次扔 100 个 pdf，也只会“排队”，不会把容器打挂。

---

## 3) 公平性：按租户做“隔离/配额”（避免大客户把别人挤死）

至少做到其中一种：

### 方案 1：每租户一个 Semaphore（简单好用）

* `tenant_sems[tenant_id] = Semaphore(t)`
* t 可以按套餐配置：普通租户 1~2，VIP 4~8
* 处理任何 PDF 前先 acquire tenant semaphore

### 方案 2：队列 + Worker（更像作业系统）

* 把每个 PDF 变成 job 丢进 `asyncio.Queue`
* 起固定数量的 worker 拉 job 跑（全局并发天然受控）
* 想更公平：按 tenant 做多队列 + round-robin 调度

**如果你还在早期阶段，先用方案 1**，成本低见效快。

---

## 4) 不要用“线程”来承载并发请求；用多进程承载服务

你的服务如果是 FastAPI/Starlette + Uvicorn/Gunicorn，推荐：

* **多进程 worker**（充分利用多核、隔离内存泄漏/卡死）
* 单 worker 内部用 asyncio 并发

经验值（容器内）：

* `workers = CPU 核数` 或 `CPU 核数 - 1`
* 如果每个请求很重（OCR/解析），workers 不要太多，否则内存爆

举例（Gunicorn + UvicornWorker）：

* 2 核：workers=2
* 4 核：workers=3~4
* 8 核：workers=4~8（看内存）

> “线程数很多”在 Python 下经常是幻觉收益，尤其遇到 CPU/阻塞库。

---

## 5) LangGraph/你自己的 graph：复用还是每次 build？

* **建议：每个请求 build 一次 graph（或从工厂拿一个干净实例）**
* 如果你确定 `ainvoke` 全程无共享可变状态（无全局缓存、无写同一路径临时文件），才考虑全局复用。

并发出问题最常见原因：

* 临时文件目录冲突（同名输出）
* 全局变量保存了 state
* 共享 client 非线程安全

**保险做法**：每个 PDF/每个 request 使用“隔离的工作目录”和“隔离的 state”。

---

## 6) 具体落地架构（推荐）

### 接口层（HTTP）

* 收到请求：tenant_id + pdf_urls
* 立即做校验 + 生成 request_id
* 开始并发跑 pdf（受控）
* 返回：结果列表（或异步任务 id）

### 执行层（并发策略）

* 每个 PDF：一个 coroutine
* coroutine 内部步骤：

  * 下载（async）
  * 解析（可能 run_in_executor）
  * OCR（async 或 executor）
  * embedding/LLM（async，受 `LLM_SEM` 限制）
  * 写入存储（async）

### 示例骨架（核心思想）

```python
GLOBAL_PDF_SEM = asyncio.Semaphore(16)
LLM_SEM = asyncio.Semaphore(4)
TENANT_SEM = defaultdict(lambda: asyncio.Semaphore(2))

async def handle_request(tenant_id, pdf_urls):
    per_req_sem = asyncio.Semaphore(4)

    async def run_one(url):
        async with TENANT_SEM[tenant_id], GLOBAL_PDF_SEM, per_req_sem:
            return await process_pdf(url, tenant_id)

    return await asyncio.gather(*(run_one(u) for u in pdf_urls), return_exceptions=True)

async def process_pdf(url, tenant_id):
    pdf_bytes = await download_async(url)           # async
    text = await asyncio.to_thread(parse_pdf, pdf_bytes)  # CPU/blocking -> thread
    async with LLM_SEM:
        summary = await call_llm_async(text)        # async
    return {"url": url, "summary": summary}
```

> 注意：`asyncio.to_thread` 适合轻/中度 CPU 或阻塞库；重 CPU 更建议 process pool。

---

## 7) 超重要的“保护措施”

* **超时**：每个 PDF 处理设置 timeout（比如 2~5 分钟），LLM 单次调用 30~60 秒
* **取消**：请求取消时，能 cancel 子任务（asyncio 友好）
* **背压**：队列满了就返回 429/503 或排队（别无限接）
* **限流**：按 tenant 做 rate limit（令牌桶）
* **内存控制**：PDF bytes 不要一次性全留内存（大文件用流式/落盘临时文件）

---

## 8) 给你一个“建议的默认参数”（可先跑起来再调）

假设：1 个容器，4 核 8~16GB，混合 I/O + CPU

* web workers：`3~4`
* `GLOBAL_PDF_SEM = 12~20`
* `PER_REQUEST_PDF_SEM = 3~5`
* `TENANT_SEM[普通] = 2`，`TENANT_SEM[VIP]=4`
* `LLM_SEM = 3~6`（看供应商并发限制）

---

## 9) 我需要你回答两个点，我就能给你“更准的配置”

你不回答我也能按上面跑，但要最优需要知道：

1. 每个 PDF 主要耗时在哪：**OCR/解析/LLM/embedding/下载**哪个占比最高？
2. 你容器资源：**CPU 核数、内存**大概多少？以及 LLM/embedding 有无并发限额？

你给这两个信息，我可以直接给你一套“worker 数 + sem 参数 + 线程池/进程池大小”的具体推荐值，以及在哪些步骤用 `to_thread`、哪些用 process pool。
