"""Dọn công thức và ngôn ngữ trong câu trả lời của model.

Bốn thứ quan sát được thật trên qwen2.5:7b-instruct khi trả lời câu hỏi lý thuyết:

1. **Ký hiệu LaTeX không nhất quán.** Cùng một model dùng cả ``\\( ... \\)``,
   ``\\[ ... \\]`` và đôi khi ``$...$`` trong các câu khác nhau. Giao diện phải
   biết trước một kiểu duy nhất mới render được, nên chuẩn hoá hết về
   ``$...$`` (trong dòng) và ``$$...$$`` (đứng riêng).

2. **Số thứ tự của prompt lọt vào câu trả lời.** Prompt yêu cầu trả lời theo thứ
   tự "(1) định nghĩa, (2) công thức, (3) điều kiện", và model chép luôn
   "(1)", "(2)" ra ngoài — câu trả lời đọc như biên bản chứ không như lời giảng.

3. **Model rơi về tiếng Trung.** Qwen là model Trung Quốc; đã bắt được câu trả
   lời chứa ``微分学，用于计算复合函数的导数`` giữa một câu tiếng Việt. Đây là lỗi
   nặng nhất trong bốn thứ: sinh viên không đọc được, và demo gặp là vỡ.

4. Có lúc model dùng thẳng ký hiệu Unicode (``λ ∈ R``, ``∑``) — **cái này tốt**,
   đọc được ngay cả khi không render, nên không đụng tới.
"""

from __future__ import annotations

import re

#: Dải chữ Hán, Hiragana, Katakana, Hangul. Dùng để phát hiện model rơi về
#: tiếng Trung/Nhật/Hàn giữa một câu trả lời tiếng Việt.
CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯＀-･]")

#: Số thứ tự đầu dòng hoặc đầu câu mà model chép lại từ prompt: "(1) ", "(2) ".
_PROMPT_NUMBERING = re.compile(r"(?:(?<=^)|(?<=[.\n]\s)|(?<=^\s))\(\s*[1-9]\s*\)\s*")


def has_cjk(text: str) -> bool:
    """Câu trả lời có lẫn chữ Trung/Nhật/Hàn không?"""
    return bool(CJK.search(text))


def cjk_ratio(text: str) -> float:
    """Tỉ lệ ký tự CJK — để phân biệt 'lẫn một từ' với 'trả lời hẳn bằng tiếng Trung'."""
    if not text:
        return 0.0
    return len(CJK.findall(text)) / len(text)


def normalise_math(text: str) -> str:
    """Đưa mọi kiểu ký hiệu LaTeX về ``$...$`` và ``$$...$$``.

    Làm ở backend chứ không ở frontend, vì cả web lẫn bot Telegram đều cần —
    để frontend tự đoán thì hai kênh sẽ hiển thị khác nhau trên cùng câu trả lời.

    Thứ tự thay quan trọng: xử lý ``\\[ \\]`` (công thức đứng riêng) TRƯỚC
    ``\\( \\)``, vì sau khi đổi dấu rồi thì không phân biệt được nữa.
    """
    out = text

    # Công thức đứng riêng: \[ ... \]  ->  $$ ... $$, và tách hẳn ra dòng riêng.
    # `\s*(.+?)\s*` đã cắt khoảng trắng BÊN TRONG dấu, nên không cần cắt thêm.
    out = re.sub(r"\\\[\s*(.+?)\s*\\\]", r"\n\n$$\1$$\n\n", out, flags=re.DOTALL)
    # Công thức trong dòng: \( ... \)  ->  $ ... $
    out = re.sub(r"\\\(\s*(.+?)\s*\\\)", r"$\1$", out, flags=re.DOTALL)

    # Gộp $$ bị bọc thêm một lớp $ do model tự viết "$$...$$" rồi ta thay lần nữa.
    out = out.replace("$$$", "$$")

    # TUYỆT ĐỐI không cắt khoảng trắng NGOÀI dấu $. Bản đầu làm vậy và biến
    # "khi \( n \) đủ lớn" thành "khi$n$đủ lớn" — chữ dính liền nhau, và vì thế
    # số thứ tự sau công thức cũng không còn đứng đầu câu để bóc ra được.
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def strip_prompt_numbering(text: str) -> str:
    """Bỏ "(1) ", "(2) " mà model chép từ prompt ra câu trả lời.

    Chỉ bỏ ở ĐẦU câu hoặc đầu dòng. Một "(2)" giữa câu có thể là nội dung thật
    (ví dụ "nghiệm (2) của phương trình"), xoá hết là làm hỏng nghĩa.
    """
    return _PROMPT_NUMBERING.sub("", text).strip()


def clean_answer(text: str) -> str:
    """Dọn một câu trả lời trước khi trả về cho người dùng."""
    return strip_prompt_numbering(normalise_math(text))
