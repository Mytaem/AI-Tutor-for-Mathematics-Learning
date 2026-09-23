"""Bộ chấm Toán rời rạc — MAD101 (Rosen, Discrete Mathematics and Its Applications).

Phủ 7 chương theo slide của môn: logic, tập hợp và tổng, thuật toán và số học,
quy nạp và truy hồi, đếm, đồ thị, cây.

Kiểm chéo ĐỘC LẬP, giống Monte Carlo của MAS291 nhưng tự nhiên hơn nhiều:

- **Bài đếm**: công thức đóng (``C(n, k)``, ``P(n, k)``...) được đối chiếu với
  LIỆT KÊ VÉT CẠN — sinh ra thật từng hoán vị, từng tổ hợp rồi đếm.
- **Truy hồi**: công thức nghiệm được đối chiếu với TÍNH LẶP trực tiếp từ hệ
  thức truy hồi, 15 số hạng đầu.

Kiểm bằng TÍNH CHẤT khi có nhiều đáp án đúng:

- Logic: hai công thức tương đương khi và chỉ khi ``¬(A ↔ B)`` không thoả được
  (kiểm bằng bảng chân trị đầy đủ qua ``sympy.logic``) — mọi cách viết đều được nhận.
- Nghịch đảo modulo: kiểm ``a·x ≡ 1 (mod m)``, nhận mọi giá trị đồng dư.
- Nghiệm truy hồi: kiểm điều kiện đầu VÀ hệ thức truy hồi, không so với một dạng chuẩn.

Giới hạn (ghi vào báo cáo): chứng minh (quy nạp, phản chứng) không chấm tự động.
"""

from __future__ import annotations

import itertools
import math
import re

import networkx as nx
import sympy as sp
from sympy.logic.inference import satisfiable

from src.core.schema import Item, Submission, VerificationResult
from src.verify.base import Verifier
from src.verify.equivalence import EquivalenceResult, ParseError, expr_equal, parse_math

ERR_DEMORGAN = "MAD.LOGIC.DEMORGAN"
ERR_CONVERSE = "MAD.LOGIC.CONVERSE"
ERR_INVERSE = "MAD.LOGIC.INVERSE"
ERR_ORDER = "MAD.COUNT.ORDER"
ERR_REPETITION = "MAD.COUNT.REPETITION"
ERR_NOSUB = "MAD.COUNT.NOSUB"
ERR_GCD_LCM = "MAD.INT.GCD_LCM"
ERR_BASE_REVERSED = "MAD.INT.BASE_REVERSED"
ERR_SUM_OFFBYONE = "MAD.SUM.OFFBYONE"
ERR_REC_INITIAL = "MAD.REC.INITIAL"
ERR_HANDSHAKE = "MAD.GRAPH.HANDSHAKE"
ERR_EULER = "MAD.GRAPH.EULER_PATH_CIRCUIT"
ERR_UNWEIGHTED = "MAD.GRAPH.UNWEIGHTED"
ERR_CHROMATIC_BOUND = "MAD.GRAPH.CHROMATIC_BOUND"
ERR_TREE_EDGES = "MAD.TREE.EDGES"
ERR_TREE_LEAVES = "MAD.TREE.LEAVES"
ERR_MST_CYCLE = "MAD.TREE.MST_CYCLE"

DISCRETE_TASKS = {
    "logic_simplify", "logic_negate", "logic_contrapositive", "logic_tautology",
    "set_union", "sum_closed", "gcd", "lcm", "mod_pow", "mod_inverse", "to_binary",
    "recurrence", "count", "handshake", "complete_edges", "euler_circuit", "euler_path",
    "bipartite", "chromatic", "shortest_path", "tree_edges", "mary_leaves", "mst_weight",
}

N = sp.Symbol("n", integer=True, nonnegative=True)


def _ok(detail: str) -> EquivalenceResult:
    return EquivalenceResult(True, "symbolic", 1.0, detail)


def _wrong(detail: str) -> EquivalenceResult:
    return EquivalenceResult(False, "symbolic", 1.0, detail)


# --------------------------------------------------------------------------
# Logic
# --------------------------------------------------------------------------

_LOGIC_SYMBOLS = (
    ("↔", "<->"), ("⇔", "<->"), ("→", "->"), ("⇒", "->"),
    ("¬", "~"), ("∧", "&"), ("∨", "|"), ("⊕", "^"), ("!", "~"),
)
_LOGIC_WORDS = ((r"\bnot\b", "~"), (r"\band\b", "&"), (r"\bor\b", "|"), (r"\bxor\b", "^"))
_TOKEN = re.compile(r"\s*(<->|->|[~&|^()]|[A-Za-z][A-Za-z0-9_]*)")


def _tokenize(text: str) -> list[str]:
    tokens, position = [], 0
    while position < len(text):
        if text[position].isspace():
            position += 1
            continue
        match = _TOKEN.match(text, position)
        if match is None:
            raise ParseError(f"Ký tự không hợp lệ trong công thức: {text[position]!r}")
        tokens.append(match.group(1))
        position = match.end()
    return tokens


def parse_logic(text: str) -> sp.Basic:
    """Đọc công thức logic sinh viên nhập: ``¬p ∨ q``, ``p -> q``, ``~(p -> q)``, ``p <-> q``...

    Bộ phân tích đệ quy theo văn phạm, độ ưu tiên đúng quy ước logic:
    ¬ > ∧ > ⊕ > ∨ > → > ↔, trong đó → kết hợp phải. KHÔNG giao cho Python/SymPy
    tự phân tích: theo độ ưu tiên của Python, ``p >> q | r`` là ``(p → q) ∨ r``
    — ngược với quy ước của môn học.
    """
    cleaned = text.strip()
    for old, new in _LOGIC_SYMBOLS:
        cleaned = cleaned.replace(old, new)
    for pattern, new in _LOGIC_WORDS:
        cleaned = re.sub(pattern, new, cleaned, flags=re.IGNORECASE)
    tokens = _tokenize(cleaned)
    if not tokens:
        raise ParseError("Công thức rỗng")
    position = 0

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def take(expected: str | None = None) -> str:
        nonlocal position
        token = peek()
        if token is None or (expected is not None and token != expected):
            raise ParseError(f"Công thức logic {text!r} không hợp lệ gần {token!r}")
        position += 1
        return token

    def equivalence():
        left = implication()
        while peek() == "<->":
            take()
            left = sp.Equivalent(left, implication())
        return left

    def implication():
        left = disjunction()
        if peek() == "->":
            take()
            return sp.Implies(left, implication())  # kết hợp phải: p → q → r = p → (q → r)
        return left

    def binary(operator: str, constructor, operand):
        def rule():
            left = operand()
            while peek() == operator:
                take()
                left = constructor(left, operand())
            return left
        return rule

    def unary():
        if peek() == "~":
            take()
            return sp.Not(unary())
        if peek() == "(":
            take("(")
            inner = equivalence()
            take(")")
            return inner
        token = take()
        if token in {"<->", "->", "&", "|", "^", ")"}:
            raise ParseError(f"Công thức logic {text!r} thiếu mệnh đề trước {token!r}")
        if token in ("T", "True"):
            return sp.true
        if token in ("F", "False"):
            return sp.false
        return sp.Symbol(token)

    conjunction = binary("&", sp.And, unary)
    exclusive = binary("^", sp.Xor, conjunction)
    disjunction = binary("|", sp.Or, exclusive)

    result = equivalence()
    if position != len(tokens):
        raise ParseError(f"Công thức logic {text!r} thừa ký hiệu từ {tokens[position]!r}")
    return result


def logically_equivalent(a: sp.Basic, b: sp.Basic) -> bool:
    """Tương đương logic ⇔ ¬(a ↔ b) không thoả được — tức khớp trên MỌI dòng bảng chân trị."""
    return satisfiable(sp.Not(sp.Equivalent(a, b))) is False


def _is_same_implication(given: sp.Basic, formula: sp.Basic) -> bool:
    """Bài làm có phải chính mệnh đề kéo theo của đề, chỉ khác cách viết hai vế?"""
    if not (isinstance(given, sp.Implies) and isinstance(formula, sp.Implies)):
        return False
    premise, conclusion = formula.args
    antecedent, consequent = given.args
    return logically_equivalent(antecedent, premise) and logically_equivalent(consequent, conclusion)


def is_negation_normal_form(formula: sp.Basic) -> bool:
    """¬ chỉ đứng trước mệnh đề đơn, và không còn → hay ↔.

    Bài "viết lại ¬(p ∧ q) cho ¬ không đứng trước ngoặc" mà không kiểm điều này
    thì nộp lại nguyên đề ¬(p ∧ q) cũng được chấm đúng — vì nó tương đương chính nó.
    """
    for node in sp.preorder_traversal(formula):
        if isinstance(node, (sp.Implies, sp.Equivalent)):
            return False
        if isinstance(node, sp.Not) and not isinstance(node.args[0], sp.Symbol):
            return False
    return True


def logic_to_text(formula: sp.Basic) -> str:
    """Viết công thức bằng ký hiệu của giáo trình: ¬ ∧ ∨ → ↔."""
    if isinstance(formula, sp.Symbol):
        return formula.name
    if isinstance(formula, sp.Not):
        inner = logic_to_text(formula.args[0])
        return f"¬{inner}" if isinstance(formula.args[0], sp.Symbol) else f"¬({inner})"
    if isinstance(formula, sp.Implies):
        return f"({logic_to_text(formula.args[0])}) → ({logic_to_text(formula.args[1])})"
    if isinstance(formula, sp.Equivalent):
        return " ↔ ".join(f"({logic_to_text(a)})" for a in formula.args)
    symbol = {sp.And: " ∧ ", sp.Or: " ∨ ", sp.Xor: " ⊕ "}[type(formula)]
    parts = [logic_to_text(a) if isinstance(a, (sp.Symbol, sp.Not)) else f"({logic_to_text(a)})"
             for a in sorted(formula.args, key=str)]
    return symbol.join(parts)


def naive_negation(formula: sp.Basic) -> sp.Basic:
    """Phủ định "sai kiểu De Morgan": đổi dấu từng mệnh đề mà GIỮ NGUYÊN ∧/∨."""
    return formula.xreplace({s: sp.Not(s) for s in formula.atoms(sp.Symbol)})


# --------------------------------------------------------------------------
# Đếm — công thức và liệt kê vét cạn
# --------------------------------------------------------------------------

def count_formula(kind: str, m: dict) -> int:
    n, k = m.get("n"), m.get("k")
    if kind == "permutation":
        return math.perm(n, k)
    if kind == "combination":
        return math.comb(n, k)
    if kind == "repetition":
        return n**k
    if kind == "multiset":
        return math.comb(n + k - 1, k)
    if kind == "bitstrings":
        return math.comb(n, k)
    if kind == "divisible":
        a, b, limit = m["a"], m["b"], m["limit"]
        return limit // a + limit // b - limit // math.lcm(a, b)
    raise KeyError(kind)


def count_brute_force(kind: str, m: dict) -> int:
    """Đếm bằng cách SINH RA thật từng đối tượng — độc lập hoàn toàn với công thức."""
    n, k = m.get("n"), m.get("k")
    if kind == "permutation":
        return sum(1 for _ in itertools.permutations(range(n), k))
    if kind == "combination":
        return sum(1 for _ in itertools.combinations(range(n), k))
    if kind == "repetition":
        return sum(1 for _ in itertools.product(range(n), repeat=k))
    if kind == "multiset":
        return sum(1 for _ in itertools.combinations_with_replacement(range(n), k))
    if kind == "bitstrings":
        return sum(1 for bits in itertools.product((0, 1), repeat=n) if sum(bits) == k)
    if kind == "divisible":
        return sum(1 for x in range(1, m["limit"] + 1) if x % m["a"] == 0 or x % m["b"] == 0)
    raise KeyError(kind)


def count_mistakes(kind: str, m: dict) -> list[tuple[int, str]]:
    n, k = m.get("n"), m.get("k")
    if kind == "permutation":
        return [(math.comb(n, k), ERR_ORDER), (n**k, ERR_REPETITION)]
    if kind == "combination":
        return [(math.perm(n, k), ERR_ORDER), (math.comb(n + k - 1, k), ERR_REPETITION)]
    if kind == "repetition":
        return [(math.perm(n, k), ERR_REPETITION)]
    if kind == "multiset":
        return [(math.comb(n, k), ERR_REPETITION)]
    if kind == "divisible":
        return [(m["limit"] // m["a"] + m["limit"] // m["b"], ERR_NOSUB)]
    return []


# --------------------------------------------------------------------------
# Truy hồi — kiểm tính chất và tính lặp
# --------------------------------------------------------------------------

def _recurrence(item: Item):
    a = sp.Function("a")
    rhs = sp.sympify(item.meta["recurrence"], locals={"a": a, "n": N})
    initial = {int(k): sp.sympify(v) for k, v in item.meta["initial"].items()}
    return a, rhs, initial


def iterate_recurrence(item: Item, terms: int = 15) -> list[sp.Expr]:
    """Tính lặp trực tiếp từ hệ thức — không dùng công thức nghiệm nào."""
    a, rhs, initial = _recurrence(item)
    values = dict(initial)
    for index in range(max(initial) + 1, terms):
        substitution = {a(N - j): values[index - j] for j in range(1, len(initial) + 1)}
        values[index] = sp.nsimplify(rhs.subs(substitution).subs(N, index))
    return [values[i] for i in range(terms)]


# --------------------------------------------------------------------------
# Đồ thị
# --------------------------------------------------------------------------

def graph_of(item: Item) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(item.meta.get("nodes", []))
    for edge in item.meta["edges"]:
        if len(edge) == 3:
            graph.add_edge(edge[0], edge[1], weight=edge[2])
        else:
            graph.add_edge(edge[0], edge[1])
    return graph


def chromatic_number(graph: nx.Graph) -> int:
    """Vét cạn mọi cách tô màu — chỉ dùng cho đồ thị nhỏ của bài tập."""
    nodes = list(graph.nodes)
    for colors in range(1, len(nodes) + 1):
        for assignment in itertools.product(range(colors), repeat=len(nodes)):
            color = dict(zip(nodes, assignment))
            if all(color[u] != color[v] for u, v in graph.edges):
                return colors
    return len(nodes)


def odd_degree_count(graph: nx.Graph) -> int:
    return sum(1 for _, degree in graph.degree if degree % 2)


# --------------------------------------------------------------------------
# Đáp án đúng và các kiểu sai
# --------------------------------------------------------------------------

def reference(item: Item):
    """Đáp án đúng: số nguyên, biểu thức theo n, công thức logic, chuỗi nhị phân hoặc bool."""
    m, task = item.meta, item.meta["task"]
    if task == "logic_simplify":
        return parse_logic(m["formula"])
    if task == "logic_negate":
        return sp.Not(parse_logic(m["formula"]))
    if task == "logic_contrapositive":
        implication = parse_logic(m["formula"])
        return sp.Implies(sp.Not(implication.args[1]), sp.Not(implication.args[0]))
    if task == "logic_tautology":
        return satisfiable(sp.Not(parse_logic(m["formula"]))) is False
    if task == "set_union":
        sizes = m["sizes"]
        return sum(sizes["single"]) - sum(sizes["pairs"]) + sum(sizes.get("triples", []))
    if task == "sum_closed":
        k = sp.Symbol("k", integer=True)
        return sp.simplify(sp.summation(sp.sympify(m["term"], locals={"k": k}), (k, m["start"], N)))
    if task == "gcd":
        return math.gcd(m["a"], m["b"])
    if task == "lcm":
        return math.lcm(m["a"], m["b"])
    if task == "mod_pow":
        return pow(m["a"], m["b"], m["m"])
    if task == "mod_inverse":
        return pow(m["a"], -1, m["m"])
    if task == "to_binary":
        return format(m["value"], "b")
    if task == "recurrence":
        return None  # kiểm bằng tính chất, không có một dạng chuẩn
    if task == "count":
        return count_formula(m["kind"], m)
    if task == "handshake":
        return sum(m["degrees"]) // 2
    if task == "complete_edges":
        return m["n"] * (m["n"] - 1) // 2
    graph = graph_of(item) if "edges" in m else None
    if task == "euler_circuit":
        return nx.is_connected(graph) and odd_degree_count(graph) == 0
    if task == "euler_path":
        return nx.is_connected(graph) and odd_degree_count(graph) in (0, 2)
    if task == "bipartite":
        return nx.is_bipartite(graph)
    if task == "chromatic":
        return chromatic_number(graph)
    if task == "shortest_path":
        return nx.dijkstra_path_length(graph, m["source"], m["target"])
    if task == "tree_edges":
        return m["n"] - 1
    if task == "mary_leaves":
        return (m["m"] - 1) * m["internal"] + 1
    if task == "mst_weight":
        tree = nx.minimum_spanning_tree(graph)
        return int(sum(w for _, _, w in tree.edges(data="weight")))
    raise KeyError(task)


def mistakes(item: Item) -> list[tuple[object, str]]:
    m, task = item.meta, item.meta["task"]
    if task == "count":
        return count_mistakes(m["kind"], m)
    if task == "set_union":
        return [(sum(m["sizes"]["single"]), ERR_NOSUB)]
    if task == "gcd":
        return [(math.lcm(m["a"], m["b"]), ERR_GCD_LCM)]
    if task == "lcm":
        return [(math.gcd(m["a"], m["b"]), ERR_GCD_LCM)]
    if task == "to_binary":
        return [(format(m["value"], "b")[::-1], ERR_BASE_REVERSED)]
    if task == "handshake":
        return [(sum(m["degrees"]), ERR_HANDSHAKE)]
    if task == "complete_edges":
        return [(m["n"] * (m["n"] - 1), ERR_HANDSHAKE)]
    if task == "tree_edges":
        return [(m["n"], ERR_TREE_EDGES)]
    if task == "mary_leaves":
        return [(m["m"] * m["internal"], ERR_TREE_LEAVES)]
    if task == "shortest_path":
        graph = graph_of(item)
        hops = nx.shortest_path(graph, m["source"], m["target"])  # ít cạnh nhất, bỏ qua trọng số
        return [(int(sum(graph[u][v]["weight"] for u, v in zip(hops, hops[1:]))), ERR_UNWEIGHTED)]
    if task == "mst_weight":
        weights = sorted(w for *_, w in m["edges"])
        return [(sum(weights[: graph_of(item).number_of_nodes() - 1]), ERR_MST_CYCLE)]
    if task == "chromatic":
        graph = graph_of(item)
        return [(max(d for _, d in graph.degree) + 1, ERR_CHROMATIC_BOUND)]
    if task == "euler_circuit":
        graph = graph_of(item)
        if nx.is_connected(graph) and odd_degree_count(graph) == 2:
            return [(True, ERR_EULER)]  # có ĐƯỜNG Euler nhưng không có CHU TRÌNH
    if task == "sum_closed":
        return [(reference(item).subs(N, N - 1), ERR_SUM_OFFBYONE)]
    return []


def cross_check(item: Item) -> dict | None:
    """Kiểm chéo độc lập: liệt kê vét cạn cho bài đếm, tính lặp cho truy hồi."""
    m, task = item.meta, item.meta["task"]
    if task == "count":
        formula, brute = count_formula(m["kind"], m), count_brute_force(m["kind"], m)
        return {"formula": formula, "brute_force": brute, "agree": formula == brute}
    if task == "recurrence":
        closed = parse_math(item.answer_text)
        iterated = iterate_recurrence(item)
        from_formula = [sp.nsimplify(closed.subs(sp.Symbol("n"), i)) for i in range(len(iterated))]
        return {"iterated": [str(v) for v in iterated[:6]], "agree": from_formula == iterated}
    return None


# --------------------------------------------------------------------------
# Bộ chấm
# --------------------------------------------------------------------------

class DiscreteVerifier(Verifier):
    name = "discrete"

    def handles(self, item: Item) -> bool:
        return item.meta.get("task") in DISCRETE_TASKS

    def verify(self, item: Item, submission: Submission) -> VerificationResult:
        result = super().verify(item, submission)
        result.cross_check = cross_check(item)
        return result

    def check(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        if not answer.strip():
            return _wrong("Chưa có đáp án"), []
        task = item.meta["task"]
        if task.startswith("logic_") and task != "logic_tautology":
            return self._check_logic(item, answer)
        if task == "recurrence":
            return self._check_recurrence(item, answer)
        if task == "sum_closed":
            return self._check_sum(item, answer)
        if task == "to_binary":
            return self._check_binary(item, answer)
        if task == "mod_inverse":
            return self._check_mod_inverse(item, answer)

        expected = reference(item)
        if isinstance(expected, bool):
            result = self._check_boolean(answer, expected)
            if result.method == "parse_error":
                raise ParseError(result.detail)
            codes = [code for value, code in mistakes(item) if not result.equal and value is not expected]
            return result, codes

        given = parse_math(answer)
        if given.free_symbols or not given.is_number:
            return _wrong("Đáp án phải là một con số"), []
        if task == "mod_pow":
            # Nhận mọi giá trị ĐỒNG DƯ với đáp án, không chỉ số dư nhỏ nhất.
            if given.is_integer and (int(given) - expected) % item.meta["m"] == 0:
                return _ok(f"≡ {expected} (mod {item.meta['m']})"), []
            return _wrong(f"Đáp án đúng là {expected} (mod {item.meta['m']})"), []
        if expr_equal(given, sp.Integer(expected)).equal:
            return _ok(f"= {expected}"), []
        for value, code in mistakes(item):
            if value != expected and expr_equal(given, sp.sympify(value)).equal:
                return _wrong(f"Đáp án đúng là {expected}; {given} ứng với một lỗi hay gặp"), [code]
        return _wrong(f"Đáp án đúng là {expected}"), []

    # ------------------------------------------------------------------

    def _check_logic(self, item: Item, answer: str):
        given = parse_logic(answer)
        expected = reference(item)
        task, formula = item.meta["task"], parse_logic(item.meta["formula"])
        if logically_equivalent(given, expected):
            if task in ("logic_simplify", "logic_negate") and not is_negation_normal_form(given):
                return _wrong("Tương đương rồi, nhưng chưa đưa ¬ vào sát từng mệnh đề (và bỏ →, ↔) như đề yêu cầu"), []
            if task == "logic_contrapositive" and _is_same_implication(given, formula):
                # Phản đảo TƯƠNG ĐƯƠNG mệnh đề gốc, nên chép lại nguyên đề "p → q"
                # cũng đúng trên mọi dòng bảng chân trị — nhưng sinh viên chưa làm
                # gì cả. Phân biệt được vì đề yêu cầu một CÁCH VIẾT cụ thể.
                return _wrong("Đây vẫn là mệnh đề gốc; phản đảo phải đổi chỗ và phủ định hai vế"), []
            return _ok("Tương đương logic trên mọi dòng bảng chân trị"), []

        if task == "logic_contrapositive":
            p, q = formula.args
            # Mệnh đề nghịch ¬p → ¬q là phản đảo của mệnh đề đảo q → p, nên hai
            # cái TƯƠNG ĐƯƠNG LOGIC — bảng chân trị không phân biệt được. Nhưng
            # cách sinh viên VIẾT thì phân biệt được: nhìn vế trái/vế phải trước.
            if isinstance(given, sp.Implies):
                antecedent, consequent = given.args
                if logically_equivalent(antecedent, sp.Not(p)) and logically_equivalent(consequent, sp.Not(q)):
                    return _wrong("Đây là mệnh đề NGHỊCH (¬p → ¬q), không tương đương với mệnh đề gốc"), [ERR_INVERSE]
                if logically_equivalent(antecedent, q) and logically_equivalent(consequent, p):
                    return _wrong("Đây là mệnh đề ĐẢO (q → p), không tương đương với mệnh đề gốc"), [ERR_CONVERSE]
            if logically_equivalent(given, sp.Implies(q, p)):
                return _wrong("Đây là mệnh đề ĐẢO (q → p), không tương đương với mệnh đề gốc"), [ERR_CONVERSE]
            if logically_equivalent(given, sp.Implies(sp.Not(p), sp.Not(q))):
                return _wrong("Đây là mệnh đề NGHỊCH (¬p → ¬q), không tương đương với mệnh đề gốc"), [ERR_INVERSE]
        if task == "logic_negate" and isinstance(formula, sp.Implies):
            p, q = formula.args
            if logically_equivalent(given, sp.Implies(sp.Not(p), sp.Not(q))):
                return _wrong("¬(p → q) KHÔNG phải ¬p → ¬q; phủ định của p → q là p ∧ ¬q"), [ERR_INVERSE]
        if task == "logic_negate" and logically_equivalent(given, naive_negation(formula)):
            return _wrong("Phủ định từng mệnh đề mà quên đổi ∧ thành ∨ (và ngược lại) — sai De Morgan"), [ERR_DEMORGAN]
        if task == "logic_simplify" and isinstance(formula, sp.Not) and \
                logically_equivalent(given, naive_negation(formula.args[0])):
            return _wrong("Sai De Morgan: ¬(p ∧ q) là ¬p ∨ ¬q, không phải ¬p ∧ ¬q"), [ERR_DEMORGAN]
        return _wrong("Không tương đương: có một dòng bảng chân trị cho kết quả khác"), []

    def _check_recurrence(self, item: Item, answer: str):
        closed = parse_math(re.sub(r"^\s*a\s*(\(\s*n\s*\)|_?n)\s*=\s*", "", answer))
        n = sp.Symbol("n")
        a, rhs, initial = _recurrence(item)

        # Kiểm hệ thức truy hồi bằng tính lặp: so với 15 số hạng thật.
        iterated = iterate_recurrence(item)
        try:
            values = [sp.nsimplify(closed.subs(n, i)) for i in range(len(iterated))]
        except (TypeError, ValueError):
            return _wrong("Không tính được giá trị của công thức tại các n nhỏ"), []
        if values == iterated:
            return _ok("Khớp 15 số hạng đầu tính lặp trực tiếp từ hệ thức truy hồi"), []

        # Sai — thoả hệ thức nhưng lệch điều kiện đầu? (giải đúng nghiệm tổng quát, tìm sai hằng số)
        order = len(initial)
        satisfies_relation = all(
            values[i] == sp.nsimplify(rhs.subs({a(N - j): values[i - j] for j in range(1, order + 1)}).subs(N, i))
            for i in range(order, len(values))
        )
        if satisfies_relation:
            return _wrong("Thoả hệ thức truy hồi nhưng sai điều kiện đầu — kiểm tra lại các hằng số"), [ERR_REC_INITIAL]
        return _wrong(f"Không khớp dãy {', '.join(map(str, iterated[:6]))}, ..."), []

    def _check_sum(self, item: Item, answer: str):
        given = parse_math(answer).subs(sp.Symbol("n"), N)
        expected = reference(item)
        if expr_equal(given, expected).equal:
            return _ok(f"= {expected}"), []
        for value, code in mistakes(item):
            if expr_equal(given, value).equal:
                return _wrong("Lệch đúng một số hạng ở cận trên của tổng"), [code]
        return _wrong("Công thức tổng chưa đúng"), []

    def _check_binary(self, item: Item, answer: str):
        given = re.sub(r"[\s_]|^0b|\(2\)$|₂$", "", answer.strip())
        if not given or set(given) - {"0", "1"}:
            raise ParseError(f"{answer!r} không phải một số nhị phân")
        expected = reference(item)
        if given.lstrip("0") == expected:
            return _ok(f"{item.meta['value']} = {expected}₂"), []
        for value, code in mistakes(item):
            if given.lstrip("0") == str(value).lstrip("0") and str(value).lstrip("0") != expected:
                return _wrong("Các chữ số đúng nhưng viết NGƯỢC thứ tự — đọc số dư từ dưới lên"), [code]
        return _wrong(f"{item.meta['value']} = {expected}₂"), []

    def _check_mod_inverse(self, item: Item, answer: str):
        given = parse_math(answer)
        a, modulus = item.meta["a"], item.meta["m"]
        if given.is_integer and (a * int(given)) % modulus == 1:
            return _ok(f"{a}·{given} ≡ 1 (mod {modulus})"), []
        return _wrong(f"{a}·{given} không đồng dư 1 theo mod {modulus}"), []
