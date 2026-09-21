"""Bộ sinh lỗi có nhãn cho Xác suất – Thống kê (MAS291).

Mỗi kiểu sai lấy từ ``probstat.mistakes`` — CÙNG hàm mà bộ chấm dùng để chẩn
đoán. Nhờ vậy giá trị "sai kiểu X" chỉ được tính ở một chỗ, không có hai công
thức lệch nhau giữa bộ sinh và bộ chấm. Cái giá là tính vòng quanh đã nói ở
``linear_algebra_errors``: tỉ lệ gán đúng mã trên dữ liệu tổng hợp chỉ chứng
minh sự nhất quán, không chứng minh năng lực với bài làm thật.
"""

from __future__ import annotations

from src.core.schema import Item
from src.data_gen.error_injector import register
from src.verify import probstat


def render(value) -> str:
    """Viết giá trị sai theo đúng cách sinh viên sẽ nhập."""
    if isinstance(value, bool):
        return "bác bỏ H0" if value else "không bác bỏ H0"
    if isinstance(value, tuple):
        return f"[{value[0]:.4f}, {value[1]:.4f}]"
    return f"{value:.6g}"


def _injector_for(code: str):
    def inject(item: Item) -> str | None:
        if item.meta.get("task") not in probstat.PROBSTAT_TASKS:
            return None
        for value, mistake in probstat.mistakes(item):
            if mistake == code:
                return render(value)
        return None

    inject.__name__ = f"inject_{code.replace('.', '_')}"
    return inject


for _code in (
    probstat.ERR_UNION_NOSUB, probstat.ERR_COND_REVERSED, probstat.ERR_JOINT_INSTEAD,
    probstat.ERR_BAYES_NONORM, probstat.ERR_CDF_PMF, probstat.ERR_OFFBYONE, probstat.ERR_TAIL,
    probstat.ERR_NOCOMB, probstat.ERR_VAR_MEAN, probstat.ERR_NOSTANDARDIZE, probstat.ERR_VAR_AS_SD,
    probstat.ERR_RATE_MEAN, probstat.ERR_VAR_N, probstat.ERR_STD_INSTEAD, probstat.ERR_Z_INSTEAD_T,
    probstat.ERR_CI_NOSQRTN, probstat.ERR_HYP_NOSQRTN, probstat.ERR_HYP_TAIL, probstat.ERR_DECISION,
    probstat.ERR_REG_SWAPPED,
):
    register(_code)(_injector_for(_code))
