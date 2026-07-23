import unittest

from app.main import create_app


class OpenApiTestCase(unittest.TestCase):
    """验证首版核心接口已注册到 FastAPI。"""

    def test_required_routes_are_registered(self) -> None:
        """认证、项目和工作流关键路由必须出现在 OpenAPI 中。"""
        paths = create_app().openapi()["paths"]
        required = {
            "/auth/register",
            "/auth/login",
            "/auth/refresh",
            "/auth/logout",
            "/auth/me",
            "/projects/create",
            "/projects/search",
            "/projects/detail",
            "/workflow/nodes/save-result",
            "/workflow/nodes/advance",
        }
        self.assertFalse(required.difference(paths))


if __name__ == "__main__":
    unittest.main()
