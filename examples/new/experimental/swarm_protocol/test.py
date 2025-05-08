"""
Swarm Protocol: A Framework for Tools, Agents, and Swarms

This module provides a high-level wrapper around FastAPI to easily define, manage,
and deploy tools, agents, and swarms as API endpoints.
"""

import inspect
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints

from loguru import logger

from fastapi import APIRouter, Body, FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, create_model

# Configure loguru logging
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    backtrace=True,
    diagnose=True,
)
logger.add(
    "logs/swarm_protocol_{time:YYYY-MM-DD}.log",
    rotation="100 MB",
    retention="14 days",
    compression="zip",
    level="DEBUG",
)

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)

# ThreadPoolExecutor for parallel task execution
MAX_WORKERS = os.cpu_count() * 2 or 4  # Default to 4 if cpu_count returns None
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


# Global registry to store all registered tools, agents and swarms
class ComponentType(str, Enum):
    TOOL = "tool"
    AGENT = "agent"
    SWARM = "swarm"


class Component:
    """Base class for all swarm protocol components (tools, agents, swarms)"""

    def __init__(
        self,
        func: Callable,
        component_type: ComponentType,
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: str = "1.0.0",
        tags: List[str] = None,
        input_model: Optional[Type[BaseModel]] = None,
    ):
        self.func = func
        self.component_type = component_type
        self.name = name or func.__name__
        self.description = (
            description
            or func.__doc__
            or f"{self.component_type.value.capitalize()} {self.name}"
        )
        self.version = version
        self.tags = tags or [component_type.value]
        self.input_model = input_model

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class SwarmProtocol:
    """
    Main class to manage the Swarm Protocol framework.
    Wraps FastAPI and provides decorators for tools, agents, and swarms.
    """

    def __init__(self, app_name: str = "Swarm Protocol API", version: str = "1.0.0"):
        self.app = FastAPI(
            title=app_name,
            description="API for tools, agents, and swarms to collaborate",
            version=version,
            # Ensure OpenAPI docs include all endpoints
            openapi_url="/openapi.json",
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # Registries for components
        self.tools: Dict[str, Component] = {}
        self.agents: Dict[str, Component] = {}
        self.swarms: Dict[str, Component] = {}

        # Create routers for each component type with explicit docs tags
        self.tool_router = APIRouter(
            prefix="/v1/tools",
            tags=["tools"],
        )
        self.agent_router = APIRouter(
            prefix="/v1/agents",
            tags=["agents"],
        )
        self.swarm_router = APIRouter(
            prefix="/v1/swarms",
            tags=["swarms"],
        )

        # Register the routers with the app
        self.app.include_router(self.tool_router)
        self.app.include_router(self.agent_router)
        self.app.include_router(self.swarm_router)

        # Add root endpoint for API info
        @self.app.get(
            "/",
            tags=["info"],
            summary="Get API information",
            response_model=Dict[str, Any],
        )
        def get_api_info():
            """
            Get information about the API including all registered components.

            Returns:
                Dict with API name, version, and registered components
            """
            return {
                "name": app_name,
                "version": version,
                "components": {
                    "tools": list(self.tools.keys()),
                    "agents": list(self.agents.keys()),
                    "swarms": list(self.swarms.keys()),
                },
                "stats": {
                    "thread_pool_workers": MAX_WORKERS,
                    "active_threads": threading.active_count(),
                    "thread_pool_tasks": (
                        len(executor._work_queue)
                        if hasattr(executor, "_work_queue")
                        else 0
                    ),
                },
            }

        # Add health check endpoint
        @self.app.get(
            "/health",
            tags=["system"],
            summary="Health check endpoint",
            response_model=Dict[str, Any],
        )
        def health_check():
            """
            Health check endpoint for monitoring systems.

            Returns:
                Dict with status and timestamp
            """
            return {
                "status": "healthy",
                "timestamp": time.time(),
                "version": version,
                "active_threads": threading.active_count(),
            }

    def _register_component(
        self,
        func: Callable,
        component_type: ComponentType,
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: str = "1.0.0",
        tags: List[str] = None,
        input_model: Optional[Type[BaseModel]] = None,
    ) -> Component:
        """
        Register a component (tool, agent, or swarm) and create its API endpoint.

        Args:
            func: The function to register
            component_type: Type of component (tool, agent, or swarm)
            name: Name of the component (defaults to function name)
            description: Description of the component (defaults to function docstring)
            version: Version of the component
            tags: Tags for OpenAPI documentation
            input_model: Optional Pydantic model for the component's input parameters

        Returns:
            The registered component
        """
        name = name or func.__name__
        component = Component(
            func=func,
            component_type=component_type,
            name=name,
            description=description,
            version=version,
            tags=tags,
            input_model=input_model,
        )

        # Store in the appropriate registry
        if component_type == ComponentType.TOOL:
            self.tools[name] = component
            router = self.tool_router
        elif component_type == ComponentType.AGENT:
            self.agents[name] = component
            router = self.agent_router
        elif component_type == ComponentType.SWARM:
            self.swarms[name] = component
            router = self.swarm_router
        else:
            raise ValueError(f"Unknown component type: {component_type}")

        # Create a Pydantic model for the function parameters if not provided
        if input_model is None:
            input_model = self._create_model_from_function(
                func, f"{name.capitalize()}Input"
            )

        # Create API endpoint with thread pool execution
        @router.post(
            f"/{name}",
            response_model=Any,
            summary=f"Execute {component_type.value} '{name}'",
            description=component.description,
            tags=component.tags,
            response_description=f"Result of executing {component_type.value} '{name}'",
        )
        async def endpoint(
            data: input_model = Body(..., description=f"Input parameters for {name}")
        ):
            request_id = f"{component_type.value}_{name}_{time.time()}"
            logger.info(
                f"[{request_id}] Received request for {component_type.value} '{name}'"
            )

            try:
                # Convert Pydantic model to dict
                params = data.dict() if hasattr(data, "dict") else data

                # Log the parameters (excluding sensitive data)
                safe_params = {
                    k: v
                    for k, v in params.items()
                    if k.lower() not in ["password", "token", "secret", "key"]
                }
                logger.debug(f"[{request_id}] Parameters: {safe_params}")

                # Execute in thread pool for better concurrency
                start_time = time.time()

                # Submit to thread pool and get future
                future = executor.submit(component, **params)

                # Wait for the result (this is a FastAPI endpoint so we're already async)
                result = future.result()

                execution_time = time.time() - start_time
                logger.info(f"[{request_id}] Completed in {execution_time:.4f}s")

                return JSONResponse(
                    content={
                        "result": result,
                        "execution_time": execution_time,
                        "request_id": request_id,
                    }
                )
            except Exception as e:
                logger.exception(
                    f"[{request_id}] Error executing {component_type.value} '{name}': {str(e)}"
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": str(e),
                        "type": type(e).__name__,
                        "request_id": request_id,
                    },
                )

        # Also create a GET endpoint for documentation/discovery
        @router.get(
            f"/{name}",
            summary=f"Get info about {component_type.value} '{name}'",
            description=f"Get detailed information about {component_type.value} '{name}'",
            tags=component.tags,
            response_model=Dict[str, Any],
            response_description=f"Metadata about {component_type.value} '{name}'",
        )
        async def get_info():
            logger.debug(f"Getting info for {component_type.value} '{name}'")
            return {
                "name": component.name,
                "type": component.component_type.value,
                "description": component.description,
                "version": component.version,
                "parameters": (
                    {
                        field_name: {
                            "type": str(
                                field.annotation.__name__
                                if hasattr(field.annotation, "__name__")
                                else field.annotation
                            ),
                            "description": field.description,
                            "required": field.required,
                            "default": (
                                str(field.default) if field.default is not ... else None
                            ),
                        }
                        for field_name, field in input_model.__fields__.items()
                    }
                    if hasattr(input_model, "__fields__")
                    else {}
                ),
                "metadata": {
                    "registered_at": time.time(),
                    "path": f"/{component_type.value}s/{name}",
                },
            }

        # For tools, also create a GET endpoint with component_id parameter
        if component_type == ComponentType.TOOL:

            @router.get(
                "/{tool_id}",
                summary="Get info about a specific tool",
                description="Get detailed information about a specific tool by its ID",
                response_model=Dict[str, Any],
                tags=["tools"],
                include_in_schema=True,  # Show in the docs
                response_description="Tool metadata",
            )
            async def get_tool_info(
                tool_id: str = Path(..., description="ID of the tool to get info about")
            ):
                logger.debug(f"Looking up tool with ID: {tool_id}")
                if tool_id == name:
                    return {
                        "name": component.name,
                        "type": "tool",
                        "description": component.description,
                        "version": component.version,
                        "metadata": {
                            "registered_at": time.time(),
                            "path": f"/v1/tools/{name}",
                        },
                    }
                raise HTTPException(
                    status_code=404, detail=f"Tool '{tool_id}' not found"
                )

        return component

    def _create_model_from_function(
        self, func: Callable, model_name: str
    ) -> Type[BaseModel]:
        """
        Create a Pydantic model from a function's type hints and docstring.

        Args:
            func: The function to create a model for
            model_name: The name to give the Pydantic model

        Returns:
            A Pydantic model class for the function's parameters
        """
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)

        # Extract parameter descriptions from docstring if available
        param_docs = {}
        if func.__doc__:
            lines = func.__doc__.split("\n")
            for i, line in enumerate(lines):
                if "Args:" in line or "Parameters:" in line:
                    for j in range(i + 1, len(lines)):
                        param_line = lines[j].strip()
                        if (
                            not param_line
                            or param_line.startswith("Returns:")
                            or param_line.startswith("Raises:")
                        ):
                            break
                        # Try to extract parameter name and description
                        if ":" in param_line:
                            param_name, param_desc = param_line.split(":", 1)
                            param_docs[param_name.strip()] = param_desc.strip()

        # Create field definitions for Pydantic model
        fields = {}
        for param_name, param in signature.parameters.items():
            # Skip 'self' parameter for class methods
            if param_name == "self":
                continue

            # Get type annotation or default to Any
            annotation = type_hints.get(param_name, Any)

            # Set default value if available
            default = ... if param.default is inspect.Parameter.empty else param.default

            # Create field with description
            description = param_docs.get(param_name, f"Parameter '{param_name}'")
            fields[param_name] = (annotation, Field(default, description=description))

        # Create and return the Pydantic model
        return create_model(model_name, **fields)

    def tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: str = "1.0.0",
        tags: List[str] = None,
        input_model: Optional[Type[BaseModel]] = None,
    ) -> Callable:
        """
        Decorator to register a function as a tool.

        Args:
            name: Name of the tool (defaults to function name)
            description: Description of the tool (defaults to function docstring)
            version: Version of the tool
            tags: Tags for OpenAPI documentation
            input_model: Optional Pydantic model for the tool's input parameters

        Returns:
            The decorated function
        """

        def decorator(func):
            self._register_component(
                func=func,
                component_type=ComponentType.TOOL,
                name=name or func.__name__,
                description=description,
                version=version,
                tags=tags,
                input_model=input_model,
            )
            return func

        return decorator

    def agent(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: str = "1.0.0",
        tags: List[str] = None,
        input_model: Optional[Type[BaseModel]] = None,
    ) -> Callable:
        """
        Decorator to register a function as an agent.

        Args:
            name: Name of the agent (defaults to function name)
            description: Description of the agent (defaults to function docstring)
            version: Version of the agent
            tags: Tags for OpenAPI documentation
            input_model: Optional Pydantic model for the agent's input parameters

        Returns:
            The decorated function
        """

        def decorator(func):
            self._register_component(
                func=func,
                component_type=ComponentType.AGENT,
                name=name or func.__name__,
                description=description,
                version=version,
                tags=tags,
                input_model=input_model,
            )
            return func

        return decorator

    def swarm(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: str = "1.0.0",
        tags: List[str] = None,
        input_model: Optional[Type[BaseModel]] = None,
    ) -> Callable:
        """
        Decorator to register a function as a swarm.

        Args:
            name: Name of the swarm (defaults to function name)
            description: Description of the swarm (defaults to function docstring)
            version: Version of the swarm
            tags: Tags for OpenAPI documentation
            input_model: Optional Pydantic model for the swarm's input parameters

        Returns:
            The decorated function
        """

        def decorator(func):
            self._register_component(
                func=func,
                component_type=ComponentType.SWARM,
                name=name or func.__name__,
                description=description,
                version=version,
                tags=tags,
                input_model=input_model,
            )
            return func

        return decorator

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        workers: int = None,
        use_gunicorn: bool = True,
        **kwargs,
    ):
        """
        Run the FastAPI application with Gunicorn (production) or Uvicorn (development).

        Args:
            host: Host IP to bind to
            port: Port to bind to
            workers: Number of worker processes (defaults to 2x CPU cores)
            use_gunicorn: Whether to use Gunicorn (production) or Uvicorn (development)
            **kwargs: Additional arguments to pass to the server
        """
        if not workers:
            workers = os.cpu_count() * 2 or 2

        # Register graceful shutdown handler
        def graceful_shutdown(*args):
            logger.info("Received shutdown signal, shutting down gracefully...")
            # Shutdown the thread pool
            logger.info("Shutting down thread pool...")
            executor.shutdown(wait=True)
            logger.info("Thread pool shutdown complete.")
            sys.exit(0)

        # Register signal handlers
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)

        if use_gunicorn:
            try:
                from gunicorn.app.base import BaseApplication

                class StandaloneApplication(BaseApplication):
                    def __init__(self, app, options=None):
                        self.options = options or {}
                        self.application = app
                        super().__init__()

                    def load_config(self):
                        config = {
                            key: value
                            for key, value in self.options.items()
                            if key in self.cfg.settings and value is not None
                        }
                        for key, value in config.items():
                            self.cfg.set(key.lower(), value)

                    def load(self):
                        return self.application

                # Configure Gunicorn options
                options = {
                    "bind": f"{host}:{port}",
                    "workers": workers,
                    "worker_class": "uvicorn.workers.UvicornWorker",
                    "timeout": 120,
                    "keepalive": 5,
                    "accesslog": "-",  # Log to stdout
                    "errorlog": "-",  # Log to stdout
                    "loglevel": "info",
                    "proc_name": "swarm_protocol",
                    "graceful_timeout": 10,
                }

                # Update with any user-provided kwargs
                options.update(kwargs)

                logger.info(
                    f"Starting Gunicorn server with {workers} workers on {host}:{port}"
                )
                logger.info(f"Thread pool has {MAX_WORKERS} worker threads")
                StandaloneApplication(self.app, options).run()

            except ImportError:
                logger.warning("Gunicorn not available, falling back to Uvicorn")
                self._run_with_uvicorn(host, port, kwargs)
        else:
            self._run_with_uvicorn(host, port, kwargs)

    def _run_with_uvicorn(self, host, port, kwargs):
        """Run with Uvicorn for development."""
        import uvicorn

        logger.info(f"Starting Uvicorn development server on {host}:{port}")
        logger.info(f"Thread pool has {MAX_WORKERS} worker threads")
        uvicorn.run(self.app, host=host, port=port, **kwargs)
