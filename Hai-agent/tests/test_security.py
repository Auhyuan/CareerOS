import unittest
from uuid import uuid4

from app.common.core.exceptions import BusinessException
from app.common.core.security import create_access_token, decode_token, hash_password, verify_password


class SecurityTestCase(unittest.TestCase):
    """验证密码哈希和 JWT 的核心安全行为。"""

    def test_password_hash_round_trip(self) -> None:
        """正确密码应通过验证，错误密码应被拒绝。"""
        encoded = hash_password("ExamplePassword123!")
        self.assertTrue(verify_password("ExamplePassword123!", encoded))
        self.assertFalse(verify_password("wrong-password", encoded))

    def test_access_token_round_trip(self) -> None:
        """Access Token 解码后应保留原始 user_id。"""
        user_id = uuid4()
        token, _, _ = create_access_token(user_id)
        claims = decode_token(token, "access")
        self.assertEqual(user_id, claims.user_id)

    def test_access_token_cannot_be_used_as_refresh_token(self) -> None:
        """Access Token 不能绕过类型校验充当 Refresh Token。"""
        token, _, _ = create_access_token(uuid4())
        with self.assertRaises(BusinessException):
            decode_token(token, "refresh")


if __name__ == "__main__":
    unittest.main()
