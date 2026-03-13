import logging
import datetime
from typing import Type, Dict, Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alphora.agent.base_agent import BaseAgent

from alphora.server.quick_api.config import APIPublisherConfig
from alphora.server.quick_api.memory_pool import MemoryPool
from alphora.server.quick_api.agent_validator import validate_agent_class, validate_agent_method, AgentValidationError
from alphora.server.quick_api.background_tasks import BackgroundTaskManager
from alphora.server.quick_api.api_endpoints import create_api_router

logger = logging.getLogger(__name__)


def publish_agent_api(
        agent: BaseAgent,
        method: str,
        config: Optional[APIPublisherConfig] = None
) -> FastAPI:
    """
    Agent API发布函数
    将指定Agent类的指定方法发布为FastAPI接口

    Args:
        agent: Agent Object
        method: 要暴露的异步方法名（需接收OpenAIRequest类型参数）
        config: API发布器配置（可选）

    Returns:
        可直接运行的FastAPI实例

    Raises:
        AgentValidationError: Agent类/方法校验失败
        ValueError: 配置参数不合法
    """
    # 默认配置
    config = config or APIPublisherConfig()

    # 校验Agent类和方法
    validate_agent_class(agent)
    validate_agent_method(agent, method)

    # 创建FastAPI应用
    app = FastAPI(
        title=config.api_title.format(agent_name=agent.__class__.__name__)
        if "{agent_name}" in config.api_title
        else config.api_title,
        description=config.api_description.format(
            agent_name=agent.__class__.__name__,
            method_name=method
        ) if "{agent_name}" in config.api_description or "{method_name}" in config.api_description
        else config.api_description
    )

    # CORS中间件 - 允许前端跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 初始化核心组件
    memory_pool = MemoryPool(
        ttl=config.memory_ttl,
        max_items=config.max_memory_items
    )

    task_manager = BackgroundTaskManager()

    api_router = create_api_router(
        agent=agent,
        method_name=method,
        memory_pool=memory_pool,
        config=config
    )

    # 注册路由
    app.include_router(api_router)

    # 文件服务
    if config.sandbox_workspace:
        from alphora.server.quick_api.file_server import publish_file_server
        publish_file_server(app, config.sandbox_workspace, config.path)

    # 注册生命周期钩子
    @app.on_event("startup")
    async def startup():
        """启动钩子"""
        # 启动后台清理任务
        task_manager.start_memory_cleanup_task(
            memory_pool=memory_pool,
            interval=config.auto_clean_interval
        )

        # 打印启动信息
        _print_startup_info(agent, method, config, memory_pool)

    @app.on_event("shutdown")
    async def shutdown():
        """关闭钩子"""
        await task_manager.stop_all_tasks()
        logger.info(f"{agent.__class__.__name__} API服务已关闭")

    return app


def _print_startup_info(
        agent: BaseAgent,
        method: str,
        config: APIPublisherConfig,
        memory_pool: MemoryPool
) -> None:

    llm_instance = agent.llm
    llm_info = llm_instance.model_name if (llm_instance and hasattr(llm_instance, "model_name")) else "未配置"

    full_api_path = f"{config.path}/chat/completions"
    if config.path.endswith("/"):
        full_api_path = f"{config.path[:-1]}/chat/completions"

    startup_info = {
        "Agent基础信息": {
            "Agent类名": agent.__class__.__name__,
            "暴露方法": method,
            "LLM模型": llm_info
        },
        "API配置": {
            "基础路径": config.path,
            "完整接口路径": full_api_path,
            "请求参数类型": "OpenAIRequest",
            "支持流式响应": "是",
            "支持非流式响应": "是"
        },
        "记忆池配置": {
            "过期时间(TTL)": f"{config.memory_ttl}秒（{config.memory_ttl / 60:.1f}分钟）",
            "最大会话数": config.max_memory_items,
            "自动清理间隔": f"{config.auto_clean_interval}秒（{config.auto_clean_interval / 60:.1f}分钟）",
            "清理策略": "TTL过期清理 + LRU容量控制",
            "当前容量": memory_pool.size
        },
        "文件服务": {
            "沙箱工作目录": config.sandbox_workspace or "未配置",
            "文件接口": f"POST .../files/{{list|read|download}}, GET .../files/serve/*" if config.sandbox_workspace else "未启用",
        },
        "运行信息": {
            "启动时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        }
    }

    logger.info("=" * 90)
    logger.info(f" {agent.__class__.__name__} API服务启动成功")
    logger.info("=" * 90)
    for section, info in startup_info.items():
        for key, value in info.items():
            logger.info(f" -> {key}: {value}")
    logger.info("\n" + "=" * 90)
    logger.info(f"  对话接口: POST http://<host>:<port>{full_api_path}")
    if config.sandbox_workspace:
        file_base = full_api_path.replace('/chat/completions', '/files')
        logger.info(f"  文件列表: POST http://<host>:<port>{file_base}/list")
        logger.info(f"  文件读取: POST http://<host>:<port>{file_base}/read")
        logger.info(f"  文件下载: POST http://<host>:<port>{file_base}/download")
        logger.info(f"  静态服务: GET  http://<host>:<port>{file_base}/serve/{{path}}?sid={{session_id}}")
        logger.info(f"  沙箱目录: {config.sandbox_workspace}")
    logger.info("=" * 90)

