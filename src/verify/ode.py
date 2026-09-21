"""Bộ chấm phương trình vi phân — thành phần TUỲ CHỌN, hiện không gắn với môn nào.

Làm cho MAI391 trước khi có đề cương thật; đề cương cho thấy MAI391 (Mathematics
for Machine Learning) không dạy ODE nên các bài ODE đã rút khỏi ngân hàng đề.
Giữ lại vì đã có test đầy đủ và sẵn sàng khi mở rộng sang môn có ODE.

Kiểm tra bằng TÍNH CHẤT, không so khớp: thế nghiệm vào phương trình, rồi đếm số
hằng số ĐỘC LẬP — ``C1·eˣ + C2·eˣ`` có hai ký hiệu nhưng chỉ một hằng số độc
lập, nên không phải nghiệm tổng quát của phương trình cấp 2.
"""

from __future__ import annotations

import random
import re

import numpy as np
import sympy as sp

from src.core.schema import AnswerType, Item
from src.verify.base import Verifier
from src.verify.equivalence import EquivalenceResult, expr_equal, parse_math, tidy

ERR_ODE_NOTSOLUTION = "ODE.NOTSOLUTION"
ERR_ODE_INCOMPLETE = "ODE.INCOMPLETE"
ERR_ODE_NOHOMO = "ODE.NOHOMO"
ERR_ODE_IC = "ODE.IC"
ERR_ODE_IC_UNSOLVED = "ODE.IC.UNSOLVED"

_LEADING_FUNCTION = re.compile(r"^\s*[A-Za-z]\s*(\(\s*[A-Za-z]\s*\))?\s*=\s*")


def _is_zero(expr) -> bool:
    return expr_equal(sp.sympify(expr), sp.Integer(0)).equal


def _ok(detail: str) -> EquivalenceResult:
    return EquivalenceResult(True, "symbolic", 1.0, detail)


def _wrong(detail: str) -> EquivalenceResult:
    return EquivalenceResult(False, "symbolic", 1.0, detail)


def parse_trusted(text: str, variable: sp.Symbol, function_name: str = "y") -> sp.Expr:
    """Đọc biểu thức ODE từ NGÂN HÀNG ĐỀ.

    Dùng ``sympify`` được vì đây là dữ liệu do ta viết, không phải đầu vào của
    người dùng. Bài làm của sinh viên thì luôn đi qua ``parse_math`` có danh
    sách trắng.
    """
    return sp.sympify(text, locals={function_name: sp.Function(function_name), str(variable): variable})


class ODEVerifier(Verifier):
    """Chấm nghiệm phương trình vi phân."""

    name = "ode"
    domain = "positive"

    def handles(self, item: Item) -> bool:
        return item.answer_type is AnswerType.ODE_SOLUTION

    def check(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        if not answer.strip():
            return _wrong("Chưa có đáp án"), []
        return self._check_ode(item, answer)

    # ------------------------------------------------------------------
    # Phương trình vi phân
    # ------------------------------------------------------------------

    def _check_ode(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        x = sp.Symbol(item.variable)
        function_name = item.meta.get("func", "y")
        y = sp.Function(function_name)

        lhs = parse_trusted(item.meta["ode"], x, function_name)
        rhs = parse_trusted(item.meta.get("rhs", "0"), x, function_name)

        # Sinh viên hay viết "y = ...", đôi khi "y(x) = ...".
        candidate = parse_math(_LEADING_FUNCTION.sub("", answer, count=1))

        residual = (lhs - rhs).subs(y(x), candidate).doit()
        if not _is_zero(residual):
            return _wrong(f"Thế vào phương trình không ra 0 (còn dư {tidy(residual)})"), [ERR_ODE_NOTSOLUTION]

        constants = sorted(candidate.free_symbols - {x}, key=str)
        conditions = item.meta.get("ics") or []

        if conditions:
            if constants:
                return _wrong(
                    "Nghiệm tổng quát đúng, nhưng chưa dùng điều kiện đầu để tìm hằng số"
                ), [ERR_ODE_IC_UNSOLVED]
            for condition in conditions:
                order = int(condition.get("derivative", 0))
                at = parse_trusted(str(condition["at"]), x, function_name)
                expected = parse_trusted(str(condition["value"]), x, function_name)
                actual = sp.diff(candidate, x, order).subs(x, at)
                if not expr_equal(sp.sympify(actual), expected).equal:
                    label = function_name + "'" * order
                    return _wrong(
                        f"Thoả phương trình nhưng {label}({at}) = {tidy(actual)}, đề yêu cầu {expected}"
                    ), [ERR_ODE_IC]
            return _ok("Thoả phương trình và mọi điều kiện đầu"), []

        order = int(item.meta["order"])
        independent = self.independent_constants(candidate, constants, x)
        if independent < order:
            is_homogeneous = _is_zero(rhs)
            if not is_homogeneous and independent == 0:
                return _wrong(
                    "Đây mới là một nghiệm riêng — còn thiếu nghiệm tổng quát của phương trình thuần nhất"
                ), [ERR_ODE_NOHOMO]
            return _wrong(
                f"Phương trình cấp {order} cần {order} hằng số độc lập, bài làm mới có {independent}"
            ), [ERR_ODE_INCOMPLETE]
        return _ok(f"Thoả phương trình với {independent} hằng số độc lập — đúng nghiệm tổng quát"), []

    @staticmethod
    def independent_constants(candidate: sp.Expr, constants: list[sp.Symbol], x: sp.Symbol) -> int:
        """Số hằng số ĐỘC LẬP thật sự trong nghiệm, không chỉ số ký hiệu.

        Với phương trình có nghiệm kép như y'' − 2y' + y = 0, sinh viên hay viết
        ``C1·eˣ + C2·eˣ``: có hai ký hiệu nhưng chúng gộp được thành một, nên đó
        KHÔNG phải nghiệm tổng quát (đúng phải là ``(C1 + C2·x)·eˣ``). Đếm ký hiệu
        sẽ chấm nhầm bài này là đúng.

        Cách đếm: đạo hàm riêng của nghiệm theo từng hằng số là các hàm của x;
        số hằng số độc lập chính là số hàm độc lập tuyến tính trong số đó. Ước
        lượng bằng hạng của ma trận các giá trị tại nhiều điểm x ngẫu nhiên.
        """
        if not constants:
            return 0

        gradients = [sp.diff(candidate, c) for c in constants]
        rng = random.Random(7)
        rows: list[list[complex]] = []
        for _ in range(len(constants) + 3):
            point = {x: rng.uniform(0.2, 2.2)}
            point.update({c: rng.uniform(0.5, 1.5) for c in constants})
            try:
                rows.append([complex(g.evalf(subs=point)) for g in gradients])
            except (TypeError, ValueError):
                continue

        if not rows:
            return 0
        return int(np.linalg.matrix_rank(np.array(rows)))

