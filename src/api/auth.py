"""Tài khoản người học: băm mật khẩu, kiểm định dạng, chống dò mật khẩu.

Mật khẩu băm bằng scrypt của thư viện chuẩn (không thêm phụ thuộc), mỗi tài
khoản một muối riêng, tham số lưu kèm chuỗi băm để sau này tăng độ khó mà mật
khẩu cũ vẫn kiểm được. Phiên đăng nhập là token ngẫu nhiên; cơ sở dữ liệu chỉ
giữ SHA-256 của token, nên lộ file DB cũng không dùng được phiên của ai.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import defaultdict, deque

#: N = 2^15, r = 8 -> khoảng 32 MB RAM và ~50 ms mỗi lần băm: đủ đắt để dò mật
#: khẩu hàng loạt không kinh tế, đủ rẻ để đăng nhập không thấy chậm.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**15, 8, 1
_MAXMEM = 64 * 1024 * 1024

MIN_PASSWORD = 8
MAX_PASSWORD = 128
SESSION_DAYS = 30
COOKIE_NAME = "numeris_session"

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")


class AuthError(ValueError):
    """Thông tin đăng ký/đăng nhập không hợp lệ — thông điệp hiện thẳng cho người dùng."""


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if len(email) > 254 or not _EMAIL.match(email):
        raise AuthError("Email không hợp lệ")
    return email


def check_password_rules(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Mật khẩu cần ít nhất {MIN_PASSWORD} ký tự")
    if len(password) > MAX_PASSWORD:
        raise AuthError(f"Mật khẩu tối đa {MAX_PASSWORD} ký tự")
    if password.isdigit() or password.isalpha():
        raise AuthError("Mật khẩu cần có cả chữ và số")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
                            maxmem=_MAXMEM)
    encode = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${encode(salt)}${encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r),
                                p=int(p), maxmem=_MAXMEM)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


#: Băm sẵn một mật khẩu giả: email không tồn tại vẫn tốn đúng thời gian như email
#: có thật, để không đoán được email nào đã đăng ký qua thời gian phản hồi.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_or_waste_time(password: str, stored: str | None) -> bool:
    return verify_password(password, stored if stored else _DUMMY_HASH) and stored is not None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginLimiter:
    """Giới hạn số lần đăng nhập SAI theo email và theo địa chỉ IP.

    Trong bộ nhớ, đủ cho một tiến trình API. Chạy nhiều worker thì mỗi worker
    đếm riêng — giới hạn thật sự nới ra theo số worker, vẫn chặn được dò hàng loạt.
    """

    def __init__(self, limit: int = 5, window_s: float = 15 * 60) -> None:
        self.limit, self.window = limit, window_s
        self._fails: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        bucket = self._fails[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        return bucket

    def retry_after(self, *keys: str) -> int:
        """Số giây phải chờ; 0 nghĩa là được thử."""
        now = time.monotonic()
        with self._lock:
            waits = [int(self.window - (now - b[0])) + 1 for k in keys
                     if len(b := self._recent(k, now)) >= self.limit]
        return max(waits, default=0)

    def failed(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in keys:
                self._recent(key, now).append(now)

    def succeeded(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._fails.pop(key, None)
