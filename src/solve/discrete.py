"""Giải từng bước MAD101 — toán rời rạc."""

from __future__ import annotations

import itertools
import math

import networkx as nx
import sympy as sp

from src.core.schema import Item
from src.solve.base import Solution, Step, show, solver
from src.verify import discrete as D


def _graph(edges, weighted: bool = False) -> nx.Graph:
    graph = nx.Graph()
    for edge in edges:
        if weighted:
            graph.add_edge(str(edge[0]), str(edge[1]), weight=edge[2])
        else:
            graph.add_edge(str(edge[0]), str(edge[1]))
    return graph


@solver("gcd")
def _gcd(item: Item) -> Solution:
    a, b = item.meta["a"], item.meta["b"]
    rows, x, y = [], max(a, b), min(a, b)
    while y:
        rows.append(f"{x} = {x // y}·{y} + {x % y}")
        x, y = y, x % y
    return Solution(theory="Thuật toán Euclid: gcd(a, b) = gcd(b, a mod b), dừng khi số dư bằng 0.",
                    formula="gcd(a, b) = gcd(b, a mod b)",
                    steps=[Step("Chia lấy dư liên tiếp theo thuật toán Euclid", "a = q·b + r", " ; ".join(rows)),
                           Step("Số dư khác 0 cuối cùng là ước chung lớn nhất", "", "", f"gcd({a}, {b}) = {x}")],
                    answer=str(x))


@solver("lcm")
def _lcm(item: Item) -> Solution:
    a, b = item.meta["a"], item.meta["b"]
    g = math.gcd(a, b)
    value = a * b // g
    return Solution(theory="Bội chung nhỏ nhất liên hệ với ước chung lớn nhất qua tích a·b.",
                    formula="lcm(a, b) = a·b / gcd(a, b)",
                    steps=[Step("Tìm gcd bằng thuật toán Euclid", "gcd(a, b) = gcd(b, a mod b)", "", f"gcd({a}, {b}) = {g}"),
                           Step("Áp dụng công thức", "lcm(a, b) = a·b / gcd(a, b)", f"{a}·{b} / {g}",
                                f"lcm({a}, {b}) = {value}")],
                    answer=str(value))


@solver("mod_pow")
def _mod_pow(item: Item) -> Solution:
    a, b, m = item.meta["a"], item.meta["b"], item.meta["m"]
    powers, value, k = [], a % m, 1
    seen = {}
    while value not in seen:
        seen[value] = k
        powers.append(f"{a}^{k} ≡ {value}")
        value, k = (value * a) % m, k + 1
    start, period = seen[value], k - seen[value]
    if start == 1 and pow(a, period, m) == 1:
        reduced = b % period or period
        work = f"chu kỳ {period}: {b} mod {period} = {b % period} ⇒ {a}^{b} ≡ {a}^{reduced}"
    else:
        reduced = b
        work = "dùng bình phương liên tiếp"
    result = pow(a, b, m)
    return Solution(theory="Luỹ thừa theo modulo lặp lại theo chu kỳ; rút gọn số mũ theo chu kỳ (hoặc định lý Fermat nhỏ).",
                    formula=f"aᵖ⁻¹ ≡ 1 (mod p) với p nguyên tố, gcd(a, p) = 1",
                    steps=[Step(f"Tính các luỹ thừa nhỏ của {a} theo mod {m} tới khi lặp lại", "", " ; ".join(powers[:8])),
                           Step("Rút gọn số mũ theo chu kỳ", "", work),
                           Step("Đọc kết quả", "", "", f"{a}^{b} mod {m} = {result}")],
                    answer=str(result))


@solver("mod_inverse")
def _mod_inverse(item: Item) -> Solution:
    a, m = item.meta["a"], item.meta["m"]
    inverse = pow(a, -1, m)
    return Solution(theory="Nghịch đảo của a theo mod m tồn tại khi gcd(a, m) = 1; tìm bằng Euclid mở rộng.",
                    formula="a·x ≡ 1 (mod m)",
                    steps=[Step("Kiểm tra gcd(a, m) = 1", "", f"gcd({a}, {m}) = {math.gcd(a, m)}"),
                           Step("Tìm x sao cho a·x ≡ 1 (mod m) bằng Euclid mở rộng", "a·x + m·y = 1",
                                f"{a}·{inverse} = {a * inverse} = {a * inverse // m}·{m} + 1"),
                           Step("Kết luận", "", "", f"{a}⁻¹ ≡ {inverse} (mod {m})")],
                    answer=str(inverse))


@solver("to_binary")
def _to_binary(item: Item) -> Solution:
    value = item.meta["value"]
    rows, n = [], value
    while n:
        rows.append(f"{n} = 2·{n // 2} + {n % 2}")
        n //= 2
    binary = bin(value)[2:]
    return Solution(theory="Đổi sang cơ số 2: chia liên tiếp cho 2, đọc các số dư từ DƯỚI lên.",
                    formula="n = 2q + r",
                    steps=[Step("Chia liên tiếp cho 2, ghi số dư", "n = 2q + r", " ; ".join(rows)),
                           Step("Đọc số dư từ dưới lên trên", "", "", f"{value} = ({binary})₂")],
                    answer=binary)


@solver("set_union")
def _set_union(item: Item) -> Solution:
    sizes = item.meta["sizes"]
    singles, pairs = sizes["single"], sizes["pairs"]
    triple = sum(sizes.get("triples", [])) or sizes.get("triple", 0)
    value = sum(singles) - sum(pairs) + triple
    formula = "|A ∪ B| = |A| + |B| − |A ∩ B|" if len(singles) == 2 else \
        "|A ∪ B ∪ C| = Σ|A| − Σ|A ∩ B| + |A ∩ B ∩ C|"
    work = " + ".join(map(str, singles)) + " − " + " − ".join(map(str, pairs)) + (f" + {triple}" if triple else "")
    return Solution(theory="Nguyên lý bù trừ: cộng các tập thì phần giao bị đếm nhiều lần, phải trừ bớt.",
                    formula=formula,
                    steps=[Step("Áp dụng nguyên lý bù trừ", formula, work, f"|hợp| = {value}")],
                    answer=str(value))


@solver("count")
def _count(item: Item) -> Solution | None:
    m = item.meta
    kind = m.get("kind")
    if kind == "divisible":
        a, b, n = m["a"], m["b"], m["limit"]
        lcm = a * b // math.gcd(a, b)
        value = n // a + n // b - n // lcm
        return Solution(theory="Đếm số chia hết cho a HOẶC b: nguyên lý bù trừ, phần chia hết cho cả hai là bội của lcm(a, b).",
                        formula="|A ∪ B| = ⌊n/a⌋ + ⌊n/b⌋ − ⌊n/lcm(a, b)⌋",
                        steps=[Step("Đếm số chia hết cho từng số", "⌊n/a⌋", "",
                                    f"⌊{n}/{a}⌋ = {n // a}, ⌊{n}/{b}⌋ = {n // b}"),
                               Step("Đếm số chia hết cho cả hai (bội của lcm)", "⌊n/lcm(a, b)⌋",
                                    f"lcm({a}, {b}) = {lcm}", f"⌊{n}/{lcm}⌋ = {n // lcm}"),
                               Step("Áp dụng nguyên lý bù trừ", "", f"{n // a} + {n // b} − {n // lcm}", str(value))],
                        answer=str(value))
    n, k = m.get("n"), m.get("k")
    if kind == "permutation":
        value = math.perm(n, k)
        return Solution(theory="Chỉnh hợp: chọn k trong n VÀ có thứ tự (ghế khác nhau).",
                        formula="A(n, k) = n! / (n − k)!",
                        steps=[Step("Nhận dạng: có thứ tự, không lặp ⇒ chỉnh hợp", "A(n, k) = n!/(n − k)!", f"n = {n}, k = {k}"),
                               Step("Tính", "", " · ".join(str(n - i) for i in range(k)), str(value))],
                        answer=str(value))
    if kind == "bitstrings":
        value = math.comb(n, k)
        return Solution(theory="Xâu nhị phân độ dài n có đúng k bit 1: chỉ cần chọn VỊ TRÍ của k bit 1.",
                        formula="C(n, k)",
                        steps=[Step("Nhận dạng: chọn k vị trí trong n để đặt bit 1, không thứ tự", "C(n, k)",
                                    f"n = {n}, k = {k}"),
                               Step("Tính tổ hợp", "C(n, k) = n!/(k!(n − k)!)", f"{n}! / ({k}!·{n - k}!)", str(value))],
                        answer=str(value))
    if kind == "combination":
        value = math.comb(n, k)
        return Solution(theory="Tổ hợp: chọn k trong n, KHÔNG quan tâm thứ tự.",
                        formula="C(n, k) = n! / (k!(n − k)!)",
                        steps=[Step("Nhận dạng: không thứ tự, không lặp ⇒ tổ hợp", "C(n, k) = n!/(k!(n − k)!)", f"n = {n}, k = {k}"),
                               Step("Tính", "", f"{n}! / ({k}!·{n - k}!)", str(value))],
                        answer=str(value))
    if kind in ("repetition", "product"):
        value = n ** k
        return Solution(theory="Mỗi vị trí chọn độc lập n cách: quy tắc nhân.", formula="nᵏ",
                        steps=[Step("Nhận dạng: có thứ tự, được lặp ⇒ quy tắc nhân", "nᵏ", f"{n}^{k}", str(value))],
                        answer=str(value))
    if kind in ("multiset", "combination_repetition"):
        value = math.comb(n + k - 1, k)
        return Solution(theory="Tổ hợp lặp: chọn k phần tử từ n loại, được lặp, không thứ tự.",
                        formula="C(n + k − 1, k)",
                        steps=[Step("Nhận dạng: không thứ tự, được lặp ⇒ tổ hợp lặp", "C(n + k − 1, k)",
                                    f"C({n + k - 1}, {k})", str(value))],
                        answer=str(value))
    return None


@solver("handshake")
def _handshake(item: Item) -> Solution:
    degrees = item.meta["degrees"]
    total = sum(degrees)
    return Solution(theory="Định lý bắt tay: mỗi cạnh góp 2 vào tổng bậc.", formula="Σ deg(v) = 2|E|",
                    steps=[Step("Cộng tất cả các bậc", "Σ deg(v)", " + ".join(map(str, degrees)), f"Σ deg = {total}"),
                           Step("Chia đôi theo định lý bắt tay", "|E| = Σ deg(v) / 2", f"{total} / 2", f"|E| = {total // 2}")],
                    answer=str(total // 2))


@solver("complete_edges")
def _complete_edges(item: Item) -> Solution:
    n = item.meta["n"]
    return Solution(theory="Đồ thị đầy đủ Kₙ: mỗi cặp đỉnh có đúng một cạnh.", formula="|E(Kₙ)| = n(n − 1)/2",
                    steps=[Step("Đếm số cặp đỉnh", "C(n, 2) = n(n − 1)/2", f"{n}·{n - 1}/2", str(n * (n - 1) // 2))],
                    answer=str(n * (n - 1) // 2))


@solver("tree_edges")
def _tree_edges(item: Item) -> Solution:
    n = item.meta["n"]
    return Solution(theory="Cây n đỉnh có đúng n − 1 cạnh (thêm cạnh nào cũng tạo chu trình).", formula="|E| = n − 1",
                    steps=[Step("Áp dụng tính chất của cây", "|E| = n − 1", f"{n} − 1", str(n - 1))],
                    answer=str(n - 1))


@solver("mary_leaves")
def _mary_leaves(item: Item) -> Solution:
    m, i = item.meta["m"], item.meta["internal"]
    total = m * i + 1
    leaves = total - i
    return Solution(theory="Cây m-phân đầy đủ có i đỉnh trong thì có n = m·i + 1 đỉnh, số lá l = n − i.",
                    formula="n = m·i + 1, l = (m − 1)·i + 1",
                    steps=[Step("Tính tổng số đỉnh", "n = m·i + 1", f"{m}·{i} + 1", f"n = {total}"),
                           Step("Trừ đi số đỉnh trong để ra số lá", "l = n − i", f"{total} − {i}", f"l = {leaves}")],
                    answer=str(leaves))


@solver("euler_circuit", "euler_path")
def _euler(item: Item) -> Solution:
    graph = _graph(item.meta["edges"])
    odd = sorted(v for v, d in graph.degree() if d % 2)
    degrees = ", ".join(f"deg({v}) = {d}" for v, d in sorted(graph.degree()))
    connected = nx.is_connected(graph)
    circuit = item.meta["task"] == "euler_circuit"
    has = connected and (len(odd) == 0 if circuit else len(odd) in (0, 2))
    rule = "mọi đỉnh bậc chẵn" if circuit else "0 hoặc 2 đỉnh bậc lẻ"
    return Solution(theory=f"Đồ thị liên thông có {'chu trình' if circuit else 'đường đi'} Euler khi và chỉ khi có {rule}.",
                    formula=f"Euler ⇔ liên thông và {rule}",
                    steps=[Step("Tính bậc của từng đỉnh", "deg(v) = số cạnh tại v", degrees),
                           Step("Đếm số đỉnh bậc lẻ và kiểm tra liên thông", "",
                                f"đỉnh bậc lẻ: {', '.join(odd) or 'không có'}; {'liên thông' if connected else 'không liên thông'}"),
                           Step("Đối chiếu điều kiện Euler", rule, "", "có" if has else "không")],
                    answer="có" if has else "không")


@solver("bipartite")
def _bipartite(item: Item) -> Solution:
    graph = _graph(item.meta["edges"])
    ok = nx.is_bipartite(graph)
    if ok:
        left, right = nx.bipartite.sets(graph) if nx.is_connected(graph) else (set(), set())
        work = f"tô màu được: {{{', '.join(sorted(left))}}} và {{{', '.join(sorted(right))}}}" if left else "tô 2 màu được"
    else:
        cycle = next((c for c in nx.cycle_basis(graph) if len(c) % 2), [])
        work = f"có chu trình độ dài lẻ: {' – '.join(cycle + cycle[:1])}"
    return Solution(theory="Đồ thị là hai phía khi và chỉ khi tô được bằng 2 màu, tức là không có chu trình độ dài lẻ.",
                    formula="hai phía ⇔ không có chu trình lẻ",
                    steps=[Step("Thử tô 2 màu xen kẽ theo các cạnh (BFS)", "hai đầu mỗi cạnh khác màu", work),
                           Step("Kết luận", "", "", "có" if ok else "không")],
                    answer="có" if ok else "không")


@solver("chromatic")
def _chromatic(item: Item) -> Solution | None:
    graph = _graph(item.meta["edges"])
    nodes = sorted(graph.nodes())
    for k in range(1, len(nodes) + 1):
        for colors in itertools.product(range(k), repeat=len(nodes)):
            coloring = dict(zip(nodes, colors))
            if all(coloring[u] != coloring[v] for u, v in graph.edges()):
                clique = max(nx.find_cliques(graph), key=len)
                return Solution(
                    theory="Sắc số là số màu ít nhất sao cho hai đỉnh kề nhau khác màu; nó ≥ kích thước clique lớn nhất.",
                    formula="χ(G) ≥ ω(G)",
                    steps=[Step("Tìm cận dưới: clique lớn nhất cần mỗi đỉnh một màu", "χ(G) ≥ ω(G)",
                                f"clique {{{', '.join(sorted(clique))}}} ⇒ χ ≥ {len(clique)}"),
                           Step(f"Chỉ ra một cách tô {k} màu hợp lệ", "",
                                ", ".join(f"{v}: màu {c + 1}" for v, c in coloring.items())),
                           Step(f"Không tô được bằng {k - 1} màu", "", "", f"χ(G) = {k}")],
                    answer=str(k))
    return None


@solver("shortest_path")
def _shortest_path(item: Item) -> Solution:
    m = item.meta
    graph = _graph(m["edges"], weighted=True)
    source, target = str(m["source"]), str(m["target"])
    distances = nx.single_source_dijkstra_path_length(graph, source)
    path = nx.dijkstra_path(graph, source, target)
    length = distances[target]
    return Solution(theory="Thuật toán Dijkstra: mỗi lượt cố định đỉnh có nhãn khoảng cách nhỏ nhất, cập nhật nhãn các đỉnh kề.",
                    formula="d(v) = min(d(v), d(u) + w(u, v))",
                    steps=[Step(f"Khởi tạo d({source}) = 0, các đỉnh khác = ∞", "", ""),
                           Step("Lần lượt cố định đỉnh có nhãn nhỏ nhất và cập nhật nhãn",
                                "d(v) = min(d(v), d(u) + w(u, v))",
                                ", ".join(f"d({v}) = {d}" for v, d in sorted(distances.items(), key=lambda kv: kv[1]))),
                           Step("Đọc đường đi và độ dài tới đích", "", " → ".join(path),
                                f"độ dài ngắn nhất = {length}")],
                    answer=str(length))


@solver("mst_weight")
def _mst_weight(item: Item) -> Solution:
    graph = _graph(item.meta["edges"], weighted=True)
    tree = nx.minimum_spanning_tree(graph, algorithm="kruskal")
    chosen = sorted(tree.edges(data="weight"), key=lambda e: e[2])
    total = sum(w for _, _, w in chosen)
    ordered = sorted(graph.edges(data="weight"), key=lambda e: e[2])
    return Solution(theory="Thuật toán Kruskal: xét cạnh theo trọng số tăng dần, nhận cạnh nếu không tạo chu trình, "
                           "dừng khi đủ n − 1 cạnh.",
                    formula="cây khung có n − 1 cạnh",
                    steps=[Step("Sắp xếp các cạnh theo trọng số tăng dần", "",
                                ", ".join(f"{u}{v}: {w}" for u, v, w in ordered)),
                           Step("Nhận lần lượt các cạnh không tạo chu trình (đủ n − 1 cạnh)", "",
                                ", ".join(f"{u}{v} ({w})" for u, v, w in chosen)),
                           Step("Cộng trọng số các cạnh đã chọn", "", " + ".join(str(w) for _, _, w in chosen),
                                f"tổng = {total}")],
                    answer=str(total))


@solver("sum_closed")
def _sum_closed(item: Item) -> Solution:
    k, n = sp.symbols("k n", integer=True, positive=True)
    term = sp.sympify(item.meta["term"], locals={"k": k})
    start = item.meta.get("start", 1)
    closed = sp.factor(sp.summation(term, (k, start, n)))
    return Solution(theory="Tách tổng thành các tổng chuẩn rồi dùng công thức Σk = n(n + 1)/2, Σ1 = n.",
                    formula="Σₖ₌₁ⁿ k = n(n + 1)/2",
                    steps=[Step("Viết dưới dạng ký hiệu tổng", "", f"Σ ({show(term)}), k chạy từ {start} đến n"),
                           Step("Tách tổng và áp công thức tổng chuẩn", "Σ(a·k + b) = a·Σk + b·Σ1",
                                f"= {show(sp.expand(sp.summation(term, (k, start, n))))}", f"= {show(closed)}")],
                    answer=sp.sstr(closed))


@solver("recurrence")
def _recurrence(item: Item) -> Solution | None:
    m = item.meta
    n = sp.Symbol("n", integer=True)
    a = sp.Function("a")
    rhs = sp.sympify(m["recurrence"], locals={"a": a, "n": n})
    initial = {a(int(key)): sp.sympify(val) for key, val in m["initial"].items()}
    closed = sp.rsolve(a(n) - rhs, a(n), initial)
    if closed is None:
        return None
    closed = sp.simplify(closed)
    check = ", ".join(f"a{i} = {show(closed.subs(n, i))}" for i in range(3))
    homogeneous = not (rhs.subs({a(n - 1): 0, a(n - 2): 0}) != 0)
    return Solution(theory="Hệ thức truy hồi tuyến tính hệ số hằng: giải phương trình đặc trưng (cộng nghiệm riêng "
                           "nếu không thuần nhất), rồi dùng điều kiện đầu tìm hằng số.",
                    formula="aₙ = c·aₙ₋₁ ⇒ aₙ = a₀·cⁿ",
                    steps=[Step("Lập phương trình đặc trưng" + ("" if homogeneous else " và tìm nghiệm riêng"),
                                "rⁿ thế vào phần thuần nhất", f"aₙ = {show(rhs).replace('a(n - 1)', 'aₙ₋₁').replace('a(n - 2)', 'aₙ₋₂')}"),
                           Step("Viết nghiệm tổng quát rồi dùng điều kiện đầu tìm hằng số", "",
                                ", ".join(f"a{key} = {val}" for key, val in m["initial"].items()), f"aₙ = {show(closed)}"),
                           Step("Kiểm tra với vài giá trị đầu", "", check, "khớp ✓")],
                    answer=sp.sstr(closed))


def _logic(item: Item):
    return D.parse_logic(item.meta["formula"])


@solver("logic_simplify", "logic_negate")
def _logic_negate(item: Item) -> Solution:
    formula = _logic(item)
    target = sp.Not(formula) if item.meta["task"] == "logic_negate" else formula
    nnf = sp.to_nnf(target, simplify=False)
    rules = "¬(A → B) ≡ A ∧ ¬B; ¬(A ∧ B) ≡ ¬A ∨ ¬B; ¬(A ∨ B) ≡ ¬A ∧ ¬B"
    steps = []
    if item.meta["task"] == "logic_negate":
        steps.append(Step("Viết phủ định của cả mệnh đề", "", f"¬({D.logic_to_text(formula)})"))
    steps += [Step("Khử phép kéo theo (nếu có)", "A → B ≡ ¬A ∨ B"),
              Step("Đẩy dấu ¬ vào trong bằng luật De Morgan", rules, "", D.logic_to_text(nnf))]
    return Solution(theory="Luật De Morgan: phủ định của 'và' là 'hoặc' các phủ định, và ngược lại.",
                    formula="¬(A ∧ B) ≡ ¬A ∨ ¬B, ¬(A ∨ B) ≡ ¬A ∧ ¬B", steps=steps,
                    answer=D.logic_to_text(nnf))


@solver("logic_contrapositive")
def _logic_contrapositive(item: Item) -> Solution:
    formula = _logic(item)
    p, q = formula.args
    contrapositive = sp.Implies(sp.Not(q), sp.Not(p))
    return Solution(theory="Mệnh đề phản đảo của A → B là ¬B → ¬A, tương đương logic với mệnh đề gốc.",
                    formula="A → B ≡ ¬B → ¬A",
                    steps=[Step("Xác định giả thiết A và kết luận B", "", f"A = {D.logic_to_text(p)}, B = {D.logic_to_text(q)}"),
                           Step("Đổi chỗ VÀ phủ định cả hai", "¬B → ¬A", "", D.logic_to_text(contrapositive))],
                    answer=D.logic_to_text(contrapositive))


@solver("logic_tautology")
def _logic_tautology(item: Item) -> Solution:
    formula = _logic(item)
    symbols = sorted(formula.free_symbols, key=str)
    rows, all_true = [], True
    for values in itertools.product([True, False], repeat=len(symbols)):
        value = bool(formula.subs(dict(zip(symbols, values))))
        all_true &= value
        rows.append(", ".join(f"{s}={'Đ' if v else 'S'}" for s, v in zip(symbols, values)) + f" → {'Đ' if value else 'S'}")
    return Solution(theory="Hằng đúng là mệnh đề đúng với MỌI cách gán giá trị chân lý.",
                    formula="lập bảng chân trị",
                    steps=[Step("Lập bảng chân trị cho mọi tổ hợp giá trị", f"{2 ** len(symbols)} dòng", " ; ".join(rows)),
                           Step("Kiểm tra cột kết quả", "", "", "mọi dòng đều đúng ⇒ hằng đúng" if all_true
                                else "có dòng sai ⇒ không phải hằng đúng")],
                    answer="có" if all_true else "không")
