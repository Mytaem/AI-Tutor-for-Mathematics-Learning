"""Model dữ liệu dùng chung cho toàn hệ thống.

Mọi module đều trao đổi qua các model ở đây, đặc biệt là ``VerificationResult``:
tầng gia sư (chẩn đoán lỗi, sinh gợi ý) CHỈ được đọc object này, không đọc lại
đầu ra thô của LLM. Đó là cách giữ tính tin cậy của cả hệ thống — nếu gợi ý có
thể bịa, thì việc kiểm chứng bằng SymPy ở tầng dưới trở nên vô nghĩa.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Subject(str, Enum):
    MAE101 = "MAE101"   # Mathematics for Engineering
    MAD101 = "MAD101"   # Discrete Mathematics
    MAI391 = "MAI391"   # Advanced Mathematics
    MAS291 = "MAS291"   # Statistics & Probability


class AnswerType(str, Enum):
    """Quyết định hàm so sánh nào được dùng để chấm."""

    EXPRESSION = "expression"            # so sánh tương đương biểu thức
    ANTIDERIVATIVE = "antiderivative"    # chấm bằng đạo hàm ngược
    NUMBER = "number"                    # so sánh số, có dung sai
    SET = "set"                          # tập nghiệm, không quan tâm thứ tự
    MATRIX = "matrix"                    # so sánh từng phần tử
    VECTOR_DIRECTION = "vector_direction"  # vector riêng: chấp nhận bội vô hướng
    BOOLEAN = "boolean"                  # đúng/sai, tương đương logic
    LINEAR_SYSTEM = "linear_system"      # nghiệm hệ: thế ngược A·x = b, chấp nhận mọi tham số hoá
    EIGENVECTOR = "eigenvector"          # kiểm A·v = λ·v, không so với một vector chuẩn
    ODE_SOLUTION = "ode_solution"        # thế vào phương trình + đếm hằng số độc lập
    TEXT = "text"                        # chấm bằng rubric, không tự động


class ErrorTier(str, Enum):
    """Nhóm lỗi tầng 1, dùng chung cho cả 4 môn (mục A3 trong PLAN.md)."""

    CONCEPT = "E-CONCEPT"        # hiểu sai khái niệm, định nghĩa
    PROCEDURE = "E-PROCEDURE"    # sai quy trình, nhớ nhầm công thức
    COMPUTE = "E-COMPUTE"        # sai số học, sai dấu, sai đại số
    CONDITION = "E-CONDITION"    # bỏ qua điều kiện áp dụng
    INTERPRET = "E-INTERPRET"    # đọc sai đề, kết luận lạc đề
    INCOMPLETE = "E-INCOMPLETE"  # thiếu bước, thiếu trường hợp, thiếu kết luận


class Skill(BaseModel):
    """Một kỹ năng con (knowledge component) — đơn vị nhỏ nhất mà mô hình năng lực theo dõi."""

    skill_id: str
    subject: Subject
    chapter: str
    name_vi: str
    name_en: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    difficulty_base: float = 0.5
    bloom_level: str = "apply"


class ErrorCode(BaseModel):
    """Một mã lỗi cụ thể ở tầng 2.

    ``subject`` để trống với mã lỗi DÙNG CHUNG nhiều môn (``LA.*`` của đại số
    tuyến tính): mã lỗi đặt theo kiểu sai, không theo môn.
    """

    code: str
    tier: ErrorTier
    subject: Subject | None = None
    skill_id: str | None = None
    name_vi: str
    description_vi: str = ""
    hint_vi: str = ""   # câu nhắc dùng cho gợi ý mức 2 ("cảnh báo bẫy")


class SolutionStep(BaseModel):
    """Một bước trong lời giải chuẩn."""

    step: int
    expr: str                       # biểu thức ở dạng SymPy đọc được
    skill_id: str | None = None
    explain_vi: str = ""
    substitution: str | None = None  # ví dụ "u = x**2 + 1", cần cho bước đổi biến


class Item(BaseModel):
    """Một bài tập trong ngân hàng đề."""

    item_id: str
    subject: Subject
    skills: list[str] = Field(default_factory=list)
    statement_vi: str
    statement_latex: str = ""

    answer_type: AnswerType
    answer: Any = None          # đáp án chuẩn; kiểu tuỳ theo answer_type
    variable: str = "x"         # biến chính, cần cho đạo hàm/tích phân
    integrand: str | None = None  # biểu thức dưới dấu tích phân (answer_type=ANTIDERIVATIVE)
    bounds: tuple[str, str] | None = None  # cận tích phân xác định

    reference_solution_steps: list[SolutionStep] = Field(default_factory=list)
    difficulty: float = 0.5
    source: str = "generated"   # textbook | exam | generated
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def answer_text(self) -> str:
        """Đáp án ở dạng hiển thị được và NỘP LẠI được vào verifier.

        Đáp án ma trận/tập hợp lưu dạng list trong JSON; ``str()`` của list
        Python in ra cả dấu nháy (``[['3/5', '-7/10']]``) — vừa xấu khi hiện ở
        gợi ý, vừa không đọc lại được như bài làm của sinh viên.
        """

        def render(value: Any) -> str:
            if isinstance(value, (list, tuple)):
                return "[" + ", ".join(render(v) for v in value) + "]"
            return str(value)

        return "" if self.answer is None else render(self.answer)


class Submission(BaseModel):
    """Bài làm sinh viên nộp lên."""

    item_id: str
    final_answer: str | None = None
    steps: list[str] = Field(default_factory=list)  # các bước, dạng chuỗi thô
    raw_text: str = ""                               # nguyên văn, để lưu log


class StepCheck(BaseModel):
    """Kết quả kiểm tra một bước biến đổi.

    ``ok=None`` nghĩa là KHÔNG KIỂM CHỨNG ĐƯỢC, khác hẳn với ``ok=False`` là sai.
    Phân biệt này là bắt buộc: một gia sư kết tội sinh viên làm sai trong khi
    thực ra máy không đủ khả năng kiểm tra sẽ phá huỷ hoàn toàn lòng tin. Khi
    ``ok=None`` thì tầng gợi ý phải im lặng về bước đó.
    """

    step: int
    ok: bool | None
    reason: str = ""
    method: str = ""
    confidence: float = 0.0


class VerificationResult(BaseModel):
    """Đầu ra chuẩn của mọi verifier — hợp đồng giữa tầng kiểm chứng và tầng gia sư."""

    item_id: str
    is_correct: bool
    final_answer_correct: bool | None = None
    first_wrong_step: int | None = None
    step_results: list[StepCheck] = Field(default_factory=list)

    verifier_used: str = ""
    cross_check: dict[str, Any] | None = None   # ví dụ {analytic, monte_carlo, agree}
    candidate_error_codes: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    notes: list[str] = Field(default_factory=list)

    @property
    def has_unverifiable_steps(self) -> bool:
        return any(step.ok is None for step in self.step_results)
