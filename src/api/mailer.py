"""Gửi email (xác thực tài khoản, đặt lại mật khẩu) qua SMTP.

Dùng được với mọi nhà cung cấp có SMTP — Gmail/Google Workspace, Amazon SES,
SendGrid, Mailgun, Zoho... — chỉ cần điền biến môi trường:

    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, MAIL_FROM, SMTP_TLS (starttls|ssl|none)

Chưa cấu hình SMTP thì KHÔNG gửi mà ghi nội dung thư vào log — để chạy thử trên máy
vẫn lấy được link xác thực. Bản bán phải cấu hình SMTP; /health báo trạng thái này.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage

log = logging.getLogger("numeris.mail")


@dataclass
class Mailer:
    host: str = field(default_factory=lambda: os.environ.get("SMTP_HOST", "").strip())
    port: int = field(default_factory=lambda: int(os.environ.get("SMTP_PORT", "587")))
    user: str = field(default_factory=lambda: os.environ.get("SMTP_USER", "").strip())
    password: str = field(default_factory=lambda: os.environ.get("SMTP_PASSWORD", ""))
    sender: str = field(default_factory=lambda: os.environ.get("MAIL_FROM", "").strip())
    tls: str = field(default_factory=lambda: os.environ.get("SMTP_TLS", "starttls").strip().lower())
    #: Thư đã "gửi" khi chưa cấu hình SMTP — test đọc ở đây.
    outbox: list[EmailMessage] = field(default_factory=list)

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender)

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender or "Numeris <no-reply@localhost>"
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        if not self.configured:
            self.outbox.append(message)
            log.warning("SMTP chưa cấu hình — thư KHÔNG được gửi. Gửi tới %s: %s\n%s", to, subject, body)
            return
        try:
            if self.tls == "ssl":
                server = smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=20)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=20)
            with server:
                if self.tls == "starttls":
                    server.starttls(context=ssl.create_default_context())
                if self.user:
                    server.login(self.user, self.password)
                server.send_message(message)
        except (OSError, smtplib.SMTPException):
            # Gửi lỗi không được làm hỏng yêu cầu của người dùng (thư gửi ở nền);
            # ghi lại để người vận hành thấy.
            log.exception("Gửi email tới %s thất bại", to)
