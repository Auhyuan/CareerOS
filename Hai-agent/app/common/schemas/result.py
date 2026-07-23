from typing import Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    """统一接口响应，所有接口均返回 code、msg 和 data。"""

    code: int
    msg: str
    data: T | None = None

    @classmethod
    def success(cls, data: T | None = None, msg: str = "success") -> "Result[T]":
        """创建统一成功响应。"""
        return cls(code=0, msg=msg, data=data)

    @classmethod
    def fail(cls, code: int, msg: str) -> "Result[None]":
        """创建统一失败响应。"""
        return cls(code=code, msg=msg, data=None)
