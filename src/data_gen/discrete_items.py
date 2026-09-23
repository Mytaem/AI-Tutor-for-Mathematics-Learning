"""Sinh đề MAD101 theo template có tham số.

Đáp án KHÔNG viết tay: gọi thẳng ``discrete.reference()`` — đúng hàm mà bộ chấm
dùng làm chuẩn — rồi để ``Registry.generate`` bắt verifier chấm lại bài vừa sinh.
Với bài đếm và bài truy hồi, verifier còn đối chứng bằng liệt kê vét cạn và tính
lặp, nên một template đếm viết sai công thức sẽ bị chặn ngay lúc sinh.

Đồ thị sinh ra được kiểm tính liên thông trước khi dùng: câu hỏi Euler trên đồ
thị rời rạc thì đáp án luôn "không" vì lý do tầm thường, không dạy được gì.
"""

from __future__ import annotations

import math
import random
from types import SimpleNamespace

import networkx as nx
import sympy as sp

from src.core.schema import Subject
from src.data_gen.bank_builder import Registry
from src.verify import discrete as D

MAD101 = Registry(Subject.MAD101, "MAD101")
template = MAD101.template

LETTERS = "ABCDEFGH"
SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

#: Số lần gieo lại trong MỘT lượt gọi template. Khung sinh đề chỉ cho mỗi template
#: một lượt mỗi vòng, nên template nào kén tham số (đồ thị phải có bẫy mới dùng
#: được) mà chỉ gieo một lần thì gần như không bao giờ sinh ra bài.
_TRIES = 25


def answer_of(meta: dict):
    """Đáp án chuẩn, lấy từ chính hàm tham chiếu của bộ chấm."""
    return D.reference(SimpleNamespace(meta=meta))


def yes_no(value: bool) -> str:
    return "có" if value else "không"


def draft(meta: dict, statement_vi: str, answer, answer_type: str, **extra) -> dict:
    return {"meta": meta, "statement_vi": statement_vi, "answer": answer,
            "answer_type": answer_type, **extra}


def number_draft(meta: dict, statement_vi: str, **extra) -> dict:
    return draft(meta, statement_vi, str(answer_of(meta)), "number", **extra)


# --------------------------------------------------------------------------
# Logic mệnh đề
# --------------------------------------------------------------------------

def _random_pair(rng: random.Random) -> tuple[str, str]:
    return tuple(rng.sample(["p", "q", "r", "s"], 2))


@template("logic_simplify", ["MAD.LOGIC.EQUIV"], 0.35, "Luật De Morgan")
def _logic_simplify(rng: random.Random):
    a, b = _random_pair(rng)
    connective = rng.choice(["&", "|"])
    formula = f"~({a} {connective} {b})"
    meta = {"task": "logic_simplify", "formula": formula}
    text = D.logic_to_text(D.parse_logic(formula))
    return draft(meta, f"Viết lại {text} sao cho dấu ¬ chỉ đứng trước mệnh đề đơn",
                 D.logic_to_text(sp.to_nnf(answer_of(meta), simplify=False)), "expression")


@template("logic_negate", ["MAD.LOGIC.COND", "MAD.LOGIC.EQUIV"], 0.5, "Phủ định mệnh đề kéo theo")
def _logic_negate(rng: random.Random):
    a, b = _random_pair(rng)
    formula = rng.choice([f"{a} -> {b}", f"{a} & {b}", f"{a} | {b}"])
    meta = {"task": "logic_negate", "formula": formula}
    text = D.logic_to_text(D.parse_logic(formula))
    return draft(meta, f"Tìm phủ định của {text} (không dùng →, ¬ chỉ đứng trước mệnh đề đơn)",
                 D.logic_to_text(sp.to_nnf(answer_of(meta), simplify=False)), "expression")


@template("logic_contrapositive", ["MAD.LOGIC.COND"], 0.4, "Mệnh đề phản đảo")
def _logic_contrapositive(rng: random.Random):
    a, b = _random_pair(rng)
    negate = rng.random() < 0.4
    formula = f"~{a} -> {b}" if negate else f"{a} -> {b}"
    meta = {"task": "logic_contrapositive", "formula": formula}
    text = D.logic_to_text(D.parse_logic(formula))
    return draft(meta, f"Viết mệnh đề phản đảo của {text}",
                 D.logic_to_text(answer_of(meta)), "expression")


@template("logic_tautology", ["MAD.LOGIC.EQUIV"], 0.55, "Bảng chân trị")
def _logic_tautology(rng: random.Random):
    a, b = _random_pair(rng)
    formula = rng.choice([
        f"({a} -> {b}) | ({b} -> {a})",     # hằng đúng
        f"({a} & {b}) -> {a}",              # hằng đúng
        f"{a} | ~{a}",                      # hằng đúng
        f"({a} -> {b}) & ({b} -> {a})",     # không
        f"{a} -> ({a} & {b})",              # không
    ])
    meta = {"task": "logic_tautology", "formula": formula}
    text = D.logic_to_text(D.parse_logic(formula))
    return draft(meta, f"{text} có phải là hằng đúng không?", yes_no(answer_of(meta)), "boolean")


# --------------------------------------------------------------------------
# Tập hợp, tổng, tổ hợp
# --------------------------------------------------------------------------

@template("set_union", ["MAD.SET", "MAD.COUNT.IE"], 0.35, "Nguyên lý bù trừ")
def _set_union(rng: random.Random):
    a, b = rng.randint(15, 60), rng.randint(15, 60)
    both = rng.randint(3, min(a, b) - 1)
    meta = {"task": "set_union", "sizes": {"single": [a, b], "pairs": [both]}}
    return number_draft(meta, f"|A| = {a}, |B| = {b}, |A ∩ B| = {both}. Tính |A ∪ B|")


@template("sum_closed", ["MAD.SUM"], 0.5, "Công thức tổng")
def _sum_closed(rng: random.Random):
    """Tổng có công thức đóng.

    Hệ số được gieo ngẫu nhiên chứ không chọn trong một danh sách cố định: danh
    sách 5 dạng chỉ cho 5 đề khác nhau, nên mã lỗi "lệch một số hạng" mãi không
    đủ mẫu dù sinh bao nhiêu bài đi nữa.
    """
    kind = rng.choice(["linear", "square", "geometric", "odd", "cube"])
    if kind == "linear":
        a, b = rng.randint(1, 5), rng.randint(0, 6)
        term = f"{a}*k + {b}" if b else f"{a}*k"
        description = f"({a}·1 + {b}) + ({a}·2 + {b}) + ... + ({a}n + {b})" if b else \
            f"{a}·1 + {a}·2 + ... + {a}n"
    elif kind == "square":
        a = rng.randint(1, 4)
        term, description = f"{a}*k**2", f"{a}·1² + {a}·2² + ... + {a}n²"
    elif kind == "geometric":
        ratio = rng.randint(2, 6)
        term, description = f"{ratio}**k", f"{ratio} + {ratio}² + ... + {ratio}ⁿ"
    elif kind == "odd":
        term, description = "2*k - 1", "1 + 3 + 5 + ... + (2n − 1)"
    else:
        term, description = "k**3", "1³ + 2³ + ... + n³"
    meta = {"task": "sum_closed", "term": term, "start": 1}
    return draft(meta, f"Tìm công thức đóng cho {description}",
                 sp.sstr(sp.factor(answer_of(meta))), "expression")


@template("count", ["MAD.COUNT.PERM"], 0.4, "Chỉnh hợp, tổ hợp")
def _count(rng: random.Random):
    kind = rng.choice(["permutation", "combination", "repetition", "multiset", "bitstrings"])
    n, k = rng.randint(5, 10), rng.randint(2, 4)
    meta = {"task": "count", "kind": kind, "n": n, "k": k}
    statement = {
        "permutation": f"Có bao nhiêu cách xếp {k} trong {n} người vào {k} ghế khác nhau?",
        "combination": f"Có bao nhiêu cách chọn {k} người từ {n} người (không phân biệt thứ tự)?",
        "repetition": f"Có bao nhiêu xâu độ dài {k} lập từ bảng chữ cái {n} ký tự (được lặp)?",
        "multiset": f"Có bao nhiêu cách chọn {k} quả từ {n} loại quả, mỗi loại có sẵn không hạn chế?",
        "bitstrings": f"Có bao nhiêu xâu nhị phân độ dài {n} chứa đúng {k} bit 1?",
    }[kind]
    skills = ["MAD.COUNT.COMB"] if kind in ("combination", "bitstrings", "multiset") else ["MAD.COUNT.PERM"]
    return number_draft(meta, statement, skills=skills)


@template("count_divisible", ["MAD.COUNT.IE"], 0.5, "Nguyên lý bù trừ")
def _count_divisible(rng: random.Random):
    a, b = rng.sample([2, 3, 4, 5, 6, 7], 2)
    limit = rng.choice([100, 200, 300, 500, 1000])
    meta = {"task": "count", "kind": "divisible", "a": a, "b": b, "limit": limit}
    return number_draft(meta, f"Trong các số từ 1 đến {limit}, có bao nhiêu số chia hết cho {a} hoặc {b}?")


# --------------------------------------------------------------------------
# Số học
# --------------------------------------------------------------------------

@template("gcd", ["MAD.INT.DIV"], 0.2, "Thuật toán Euclid")
def _gcd(rng: random.Random):
    a, b = rng.randint(20, 300), rng.randint(20, 300)
    if a == b:
        return None
    meta = {"task": "gcd", "a": a, "b": b}
    return number_draft(meta, f"Tìm gcd({a}, {b})")


@template("lcm", ["MAD.INT.DIV"], 0.25, "Quan hệ gcd·lcm = a·b")
def _lcm(rng: random.Random):
    a, b = rng.randint(4, 40), rng.randint(4, 40)
    if a == b:
        return None
    meta = {"task": "lcm", "a": a, "b": b}
    return number_draft(meta, f"Tìm lcm({a}, {b})")


@template("mod_pow", ["MAD.INT.MOD"], 0.55, "Luỹ thừa modulo")
def _mod_pow(rng: random.Random):
    a, b = rng.randint(2, 12), rng.choice([10, 20, 50, 100, 200])
    m = rng.choice([7, 9, 11, 13, 17])
    if math.gcd(a, m) != 1:
        return None
    meta = {"task": "mod_pow", "a": a, "b": b, "m": m}
    return number_draft(meta, f"Tính {a}{str(b).translate(SUP)} mod {m}")


@template("mod_inverse", ["MAD.INT.MOD"], 0.6, "Nghịch đảo modulo")
def _mod_inverse(rng: random.Random):
    m = rng.choice([7, 9, 11, 13, 16, 17, 26])
    a = rng.randint(2, m - 1)
    if math.gcd(a, m) != 1:
        return None
    meta = {"task": "mod_inverse", "a": a, "m": m}
    return number_draft(meta, f"Tìm nghịch đảo của {a} theo modulo {m}")


@template("to_binary", ["MAD.INT.BASE"], 0.3, "Đổi cơ số")
def _to_binary(rng: random.Random):
    value = rng.randint(9, 250)
    meta = {"task": "to_binary", "value": value}
    return draft(meta, f"Đổi {value} sang hệ nhị phân", answer_of(meta), "text")


# --------------------------------------------------------------------------
# Hệ thức truy hồi
# --------------------------------------------------------------------------

@template("recurrence", ["MAD.REC.LINEAR"], 0.65, "Giải hệ thức truy hồi tuyến tính")
def _recurrence(rng: random.Random):
    kind = rng.choice(["geometric", "affine", "second_order"])
    if kind == "geometric":
        ratio, first = rng.randint(2, 5), rng.randint(1, 6)
        meta = {"task": "recurrence", "recurrence": f"{ratio}*a(n-1)", "initial": {"0": str(first)}}
        text = f"aₙ = {ratio}aₙ₋₁, a₀ = {first}"
    elif kind == "affine":
        ratio, add = rng.randint(2, 4), rng.randint(1, 5)
        meta = {"task": "recurrence", "recurrence": f"{ratio}*a(n-1) + {add}", "initial": {"0": "0"}}
        text = f"aₙ = {ratio}aₙ₋₁ + {add}, a₀ = 0"
    else:
        # Hai nghiệm đặc trưng phân biệt cho công thức đóng gọn.
        r1, r2 = rng.sample([2, 3, 4, 5], 2)
        meta = {"task": "recurrence",
                "recurrence": f"{r1 + r2}*a(n-1) - {r1 * r2}*a(n-2)",
                "initial": {"0": "0", "1": "1"}}
        text = f"aₙ = {r1 + r2}aₙ₋₁ − {r1 * r2}aₙ₋₂, a₀ = 0, a₁ = 1"

    closed = D.iterate_recurrence  # chỉ để nhắc: verifier kiểm bằng tính lặp
    del closed
    solved = _solve_recurrence(meta)
    if solved is None:
        return None
    return draft(meta, f"Giải hệ thức {text}", sp.sstr(sp.simplify(solved)), "expression")


def _solve_recurrence(meta: dict):
    """Công thức đóng, giải bằng ``rsolve``; không giải được thì bỏ template này."""
    n = sp.Symbol("n", integer=True, nonnegative=True)
    a = sp.Function("a")
    body = sp.sympify(meta["recurrence"], locals={"a": a, "n": n})
    equation = a(n) - body
    initial = {a(int(k)): sp.sympify(v) for k, v in meta["initial"].items()}
    try:
        return sp.rsolve(equation, a(n), initial)
    except (ValueError, NotImplementedError, TypeError):
        return None


# --------------------------------------------------------------------------
# Đồ thị và cây
# --------------------------------------------------------------------------

def _random_graph(rng: random.Random, low: int = 4, high: int = 7) -> tuple[nx.Graph, list[list]]:
    """Đồ thị liên thông ngẫu nhiên, trả kèm danh sách cạnh đã đặt tên A, B, C..."""
    n = rng.randint(low, high)
    nodes = list(LETTERS[:n])
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    order = nodes[:]
    rng.shuffle(order)
    for index in range(1, n):                       # cây khung ngẫu nhiên -> chắc chắn liên thông
        graph.add_edge(order[index], rng.choice(order[:index]))
    extra = rng.randint(1, max(1, n - 2))
    for _ in range(extra):
        u, v = rng.sample(nodes, 2)
        graph.add_edge(u, v)
    return graph, [[u, v] for u, v in graph.edges()]


def _edge_text(edges: list[list]) -> str:
    return ", ".join(f"{u}{v}" for u, v in edges)


@template("handshake", ["MAD.GRAPH.BASIC"], 0.3, "Định lý bắt tay")
def _handshake(rng: random.Random):
    graph, _ = _random_graph(rng)
    degrees = sorted((d for _, d in graph.degree()), reverse=True)
    meta = {"task": "handshake", "degrees": degrees}
    return number_draft(meta, f"Đồ thị có dãy bậc {', '.join(map(str, degrees))}. Đồ thị có bao nhiêu cạnh?")


@template("complete_edges", ["MAD.GRAPH.BASIC"], 0.25, "Số cạnh của đồ thị đầy đủ")
def _complete_edges(rng: random.Random):
    n = rng.randint(4, 12)
    meta = {"task": "complete_edges", "n": n}
    return number_draft(meta, f"Đồ thị đầy đủ K{str(n).translate(SUB)} có bao nhiêu cạnh?")


@template("euler", ["MAD.GRAPH.EULER"], 0.55, "Điều kiện Euler theo bậc lẻ")
def _euler(rng: random.Random):
    graph, edges = _random_graph(rng)
    task = rng.choice(["euler_circuit", "euler_path"])
    # Bẫy của mã MAD.GRAPH.EULER_PATH_CIRCUIT là "có đường Euler nhưng KHÔNG có
    # chu trình" — chỉ tồn tại khi đồ thị có đúng 2 đỉnh bậc lẻ, nên ưu tiên
    # nhận những đồ thị đó thay vì gieo bừa.
    for _ in range(_TRIES):
        odd = sum(1 for _, degree in graph.degree() if degree % 2)
        if task != "euler_circuit" or odd in (0, 2):
            break
        graph, edges = _random_graph(rng)
    meta = {"task": task, "edges": edges}
    question = "chu trình Euler" if task == "euler_circuit" else "đường đi Euler"
    return draft(meta, f"Đồ thị có các cạnh {_edge_text(edges)}. Đồ thị có {question} không?",
                 yes_no(answer_of(meta)), "boolean")


@template("bipartite", ["MAD.GRAPH.COLOR"], 0.5, "Đồ thị hai phía ⇔ không có chu trình lẻ")
def _bipartite(rng: random.Random):
    graph, edges = _random_graph(rng)
    meta = {"task": "bipartite", "edges": edges}
    return draft(meta, f"Đồ thị có các cạnh {_edge_text(edges)}. Đây có phải đồ thị hai phía không?",
                 yes_no(answer_of(meta)), "boolean")


@template("chromatic", ["MAD.GRAPH.COLOR"], 0.65, "Sắc số")
def _chromatic(rng: random.Random):
    graph, edges = _random_graph(rng, 4, 6)
    meta = {"task": "chromatic", "edges": edges}
    return number_draft(meta, f"Đồ thị có các cạnh {_edge_text(edges)}. Tìm sắc số của đồ thị")


def _weighted_graph(rng: random.Random) -> list[list]:
    graph, edges = _random_graph(rng, 4, 6)
    return [[u, v, rng.randint(1, 9)] for u, v in edges]


def _weight_text(edges: list[list]) -> str:
    return ", ".join(f"{u}–{v}: {w}" for u, v, w in edges)


@template("shortest_path", ["MAD.GRAPH.PATH"], 0.55, "Thuật toán Dijkstra")
def _shortest_path(rng: random.Random):
    """Đường đi ngắn nhất có trọng số.

    Chỉ nhận đồ thị mà đường đi ÍT CẠNH nhất KHÁC đường rẻ nhất — đúng cái bẫy
    mã MAD.GRAPH.UNWEIGHTED mô tả. Đồ thị ngẫu nhiên thường cho hai đường trùng
    nhau, khi đó không cài được lỗi nào vào bài.
    """
    for _ in range(_TRIES):
        edges = _weighted_graph(rng)
        nodes = sorted({u for u, _, _ in edges} | {v for _, v, _ in edges})
        source, target = nodes[0], nodes[-1]
        graph = nx.Graph()
        for u, v, w in edges:
            graph.add_edge(u, v, weight=w)
        hops = nx.shortest_path(graph, source, target)
        hop_weight = sum(graph[u][v]["weight"] for u, v in zip(hops, hops[1:]))
        if hop_weight != nx.dijkstra_path_length(graph, source, target):
            break
    else:
        return None
    meta = {"task": "shortest_path", "edges": edges, "source": source, "target": target}
    return number_draft(meta, f"Đồ thị có trọng số: {_weight_text(edges)}. "
                              f"Tìm độ dài đường đi ngắn nhất từ {source} đến {target}")


@template("mst_weight", ["MAD.TREE.MST"], 0.6, "Cây khung nhỏ nhất")
def _mst_weight(rng: random.Random):
    """Cây khung nhỏ nhất.

    Chỉ nhận đồ thị mà "gom n − 1 cạnh nhẹ nhất" KHÔNG ra cây khung (vì tạo chu
    trình) — nếu hai cách trùng nhau thì bẫy MAD.TREE.MST_CYCLE không tồn tại.
    """
    for _ in range(_TRIES):
        edges = _weighted_graph(rng)
        graph = nx.Graph()
        for u, v, w in edges:
            graph.add_edge(u, v, weight=w)
        lightest = sorted(w for *_, w in edges)[: graph.number_of_nodes() - 1]
        tree = nx.minimum_spanning_tree(graph)
        if sum(lightest) != sum(w for *_, w in tree.edges(data="weight")):
            break
    else:
        return None
    meta = {"task": "mst_weight", "edges": edges}
    return number_draft(meta, f"Đồ thị có trọng số: {_weight_text(edges)}. "
                              f"Tìm tổng trọng số của cây khung nhỏ nhất")


@template("tree_edges", ["MAD.TREE.BASIC"], 0.2, "Cây n đỉnh có n − 1 cạnh")
def _tree_edges(rng: random.Random):
    n = rng.randint(6, 40)
    meta = {"task": "tree_edges", "n": n}
    return number_draft(meta, f"Một cây có {n} đỉnh thì có bao nhiêu cạnh?")


@template("mary_leaves", ["MAD.TREE.BASIC"], 0.5, "Cây m-phân đầy đủ")
def _mary_leaves(rng: random.Random):
    m, internal = rng.randint(2, 5), rng.randint(3, 12)
    meta = {"task": "mary_leaves", "m": m, "internal": internal}
    name = {2: "nhị phân", 3: "tam phân", 4: "tứ phân", 5: "ngũ phân"}[m]
    return number_draft(meta, f"Cây {name} đầy đủ có {internal} đỉnh trong. Cây có bao nhiêu lá?")


def generate(count: int, seed: int = 20260923, validate: bool = True):
    return MAD101.generate(count, seed=seed, validate=validate)


def template_ids() -> list[str]:
    return MAD101.template_ids()
