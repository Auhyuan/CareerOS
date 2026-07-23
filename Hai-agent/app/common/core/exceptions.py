import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.common.schemas.result import Result


logger = logging.getLogger("hai_agent.exceptions")


class BusinessException(Exception):
    """表示可预期的业务失败，并携带统一业务错误码。"""

    def __init__(self, code: int, msg: str):
        """初始化业务错误码和错误信息。"""
        self.code = code
        self.msg = msg
        super().__init__(msg)


def build_error_response(code: int, msg: str) -> JSONResponse:
    """构造统一错误响应，HTTP 状态统一保持 200。"""
    return JSONResponse(status_code=200, content=Result.fail(code, msg).model_dump(mode="json"))


def format_validation_error(errors: list[dict]) -> str:
    """把 Pydantic 参数错误整理为适合前端展示的中文信息。"""
    messages: list[str] = []
    for item in errors:
        location = ".".join(str(part) for part in item.get("loc", []))
        message = item.get("msg", "参数不合法")
        messages.append(f"{location}: {message}" if location else message)
    return "；".join(messages) if messages else "请求参数校验失败"


def register_exception_handlers(app: FastAPI) -> None:
    """为 FastAPI 注册业务、鉴权、参数校验和未知异常处理器。"""

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, error: BusinessException) -> JSONResponse:
        """处理业务代码主动抛出的异常。"""
        return build_error_response(error.code, error.msg)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, error: HTTPException) -> JSONResponse:
        """处理 FastAPI 和 Starlette 抛出的 HTTP 异常。"""
        return build_error_response(error.status_code, str(error.detail))

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, error: RequestValidationError) -> JSONResponse:
        """处理请求参数校验失败。"""
        return build_error_response(422, format_validation_error(error.errors()))

    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(request: Request, error: ValidationError) -> JSONResponse:
        """处理业务层构造 Pydantic 对象时的校验失败。"""
        return build_error_response(422, format_validation_error(error.errors()))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, error: Exception) -> JSONResponse:
        """记录未知异常完整堆栈，并返回统一错误响应。"""
        logger.exception("Hai-agent 未处理异常: path=%s", request.url.path)
        return build_error_response(500, f"服务内部错误: {error}")
