"""Cây nội dung học: môn → chương → bài → dạng bài.

Người học chọn dần từ rộng xuống hẹp, và mỗi tầng phải nói được "ở đây có bao
nhiêu đề" — nếu không họ sẽ chọn vào một nhánh rỗng rồi tưởng hệ thống hỏng.

Bốn tầng đều KHÔNG phải trường riêng trên đề, mà suy ra từ dữ liệu đã có:

    chương    trên KỸ NĂNG (``Skill.chapter``), còn đề thì mang kỹ năng
    bài       chính là kỹ năng (``Skill``)
    dạng bài  ``item.meta["template"]``, tên hiện lấy ``item.meta["method"]``

Suy theo hướng đó nên không phải gán tay cho 4.955 đề, và một đề nhiều kỹ năng
thì tự thuộc nhiều chương — đúng thực tế chứ không phải lỗi.

Tên chương trong ``data/skills`` là tiếng Anh vì lấy nguyên từ giáo trình. Bảng
dưới đây dịch sang tiếng Việt để hiện cho người học. Cố ý KHÔNG dịch ở frontend:
web và bot Telegram phải gọi cùng một tên, nếu không sinh viên dùng hai kênh sẽ
thấy hai danh sách khác nhau.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.core.itembank import ItemBank
from src.core.schema import Item

#: (môn, chương trong dữ liệu) -> tên hiện cho người học.
CHAPTER_NAMES_VI: dict[tuple[str, str], str] = {
    ("MAE101", "Limits"): "Giới hạn và liên tục",
    ("MAE101", "Derivatives"): "Đạo hàm và ứng dụng",
    ("MAE101", "Integration"): "Tích phân",
    ("MAE101", "Systems of Linear Equations"): "Hệ phương trình tuyến tính",
    ("MAE101", "Matrix Algebra"): "Đại số ma trận",
    ("MAE101", "Determinants and Diagonalization"): "Định thức và chéo hoá",
    ("MAE101", "Vector Spaces"): "Không gian vector",

    ("MAD101", "Ch1 Logics & Proofs"): "Logic và phép chứng minh",
    ("MAD101", "Ch2 Sets, Functions, Sequences & Sums"): "Tập hợp, hàm, dãy và tổng",
    ("MAD101", "Ch3 Algorithms & Integers"): "Thuật toán và số nguyên",
    ("MAD101", "Ch4 Induction & Recursion"): "Quy nạp và đệ quy",
    ("MAD101", "Ch5 Counting"): "Tổ hợp",
    ("MAD101", "Ch6 Graph Theory"): "Lý thuyết đồ thị",
    ("MAD101", "Ch7 Trees"): "Cây",

    ("MAI391", "Ch3 Analytic Geometry"): "Hình học giải tích",
    ("MAI391", "Ch4 Matrix Decompositions"): "Phân tích ma trận",
    ("MAI391", "Ch5 Vector Calculus"): "Giải tích vector",
    ("MAI391", "Ch6 Probability"): "Xác suất",
    ("MAI391", "Ch7 Continuous Optimization"): "Tối ưu liên tục",
    ("MAI391", "Ch9 Linear Regression"): "Hồi quy tuyến tính",
    ("MAI391", "Ch10 PCA"): "Phân tích thành phần chính (PCA)",
    ("MAI391", "Ch12 SVM"): "Máy vector hỗ trợ (SVM)",

    ("MAS291", "Ch2 Probability"): "Xác suất",
    ("MAS291", "Ch3 Discrete RVs"): "Biến ngẫu nhiên rời rạc",
    ("MAS291", "Ch4 Continuous RVs"): "Biến ngẫu nhiên liên tục",
    ("MAS291", "Ch6 Descriptive Statistics"): "Thống kê mô tả",
    ("MAS291", "Ch8 Statistical Intervals"): "Khoảng tin cậy",
    ("MAS291", "Ch9 Hypothesis Tests"): "Kiểm định giả thuyết",
    ("MAS291", "Ch10 Two Samples"): "So sánh hai mẫu",
    ("MAS291", "Ch11 Regression"): "Hồi quy",
}

#: MAE101 không đánh số chương, nên thứ tự phải nói rõ theo trình tự dạy.
#: Ba môn còn lại có tiền tố "Ch<số>" nên sắp được bằng chính con số đó.
MAE101_ORDER = [
    "Limits",
    "Derivatives",
    "Integration",
    "Systems of Linear Equations",
    "Matrix Algebra",
    "Determinants and Diagonalization",
    "Vector Spaces",
]

#: Tên dạng bài cho các đề CHÉP TAY — chúng chỉ có ``task`` chứ không có
#: ``method``, vì không sinh ra từ bộ sinh đề. Thiếu bảng này thì danh sách
#: dạng bài hiện ra 17 mã trần kiểu ``reg_slope`` giữa các tên tiếng Việt.
TASK_NAMES_VI: dict[str, str] = {
    "chain": "Quy tắc hàm hợp",
    "correlation": "Hệ số tương quan",
    "count": "Đếm bằng chỉnh hợp, tổ hợp",
    "euler_circuit": "Chu trình Euler",
    "euler_path": "Đường đi Euler",
    "expectation": "Kỳ vọng",
    "gradient": "Gradient",
    "inverse": "Ma trận nghịch đảo",
    "median": "Trung vị",
    "recurrence": "Hệ thức truy hồi",
    "reg_intercept": "Hệ số chặn của đường hồi quy",
    "reg_slope": "Hệ số góc của đường hồi quy",
    "sample_mean": "Trung bình mẫu",
    "sample_var": "Phương sai mẫu",
    "t_stat": "Thống kê t",
    "variance": "Phương sai",
    "z_stat": "Thống kê z",
}

_CH_NUMBER = re.compile(r"^Ch(\d+)")


@dataclass(frozen=True)
class Topic:
    """Dạng bài — tầng hẹp nhất. Ví dụ: "Thuật toán Euclid"."""

    topic_id: str             #: item.meta["template"], dùng làm khoá khi gọi API
    name_vi: str              #: item.meta["method"], tên người đọc được
    items: int


@dataclass(frozen=True)
class Lesson:
    """Bài — chính là một kỹ năng trong bảng kỹ năng."""

    skill_id: str
    name_vi: str
    items: int
    topics: tuple[Topic, ...] = ()


@dataclass(frozen=True)
class Chapter:
    """Một chương, kèm đủ số liệu để hiện lên danh sách chọn."""

    chapter: str              #: tên trong dữ liệu, dùng làm khoá khi gọi API
    name_vi: str              #: tên hiện cho người học
    skill_ids: tuple[str, ...]
    items: int
    lessons: tuple[Lesson, ...] = ()

    @property
    def skills(self) -> int:
        return len(self.skill_ids)


def display_name(subject: str, chapter: str) -> str:
    """Tên tiếng Việt; chưa dịch thì trả nguyên tên gốc chứ không để trống."""
    name = CHAPTER_NAMES_VI.get((subject, chapter))
    if name:
        return name
    # Bỏ tiền tố "Ch5 " cho gọn, nhưng vẫn giữ nội dung để không mất thông tin.
    return _CH_NUMBER.sub("", chapter).strip(" -–") or chapter


def sort_key(subject: str, chapter: str) -> tuple[int, str]:
    match = _CH_NUMBER.match(chapter)
    if match:
        return (int(match.group(1)), chapter)
    if subject == "MAE101" and chapter in MAE101_ORDER:
        return (MAE101_ORDER.index(chapter), chapter)
    return (999, chapter)


def subject_of(bank: ItemBank) -> str:
    """Mã môn của một ngân hàng đề.

    ``ItemBank`` không giữ trường môn, nhưng mọi kỹ năng trong nó đều thuộc
    cùng một môn — đọc từ đó thay vì bắt mọi chỗ gọi phải truyền thêm tham số.
    """
    for skill in bank.skills.values():
        return skill.subject.value if hasattr(skill.subject, "value") else str(skill.subject)
    return ""


def topic_of(item: Item) -> tuple[str, str] | None:
    """``(mã dạng bài, tên tiếng Việt)`` của một đề, hoặc None nếu đề không ghi.

    Tên có thể là chuỗi RỖNG: đề chép tay có ``task`` nhưng không có ``method``.
    Trả rỗng chứ không lấy mã làm tên, để chỗ gom nhóm còn cơ hội tìm được một
    đề khác cùng dạng CÓ tên tử tế. Bản đầu lấy mã làm tên ngay tại đây, và vì
    đề chép tay đứng trước trong danh sách, cả danh sách dạng bài hiện ra toàn
    mã trần kiểu ``logic_negate``.

    Đề không có cả ``template`` lẫn ``task`` thì trả None, không bịa một dạng
    "khác" — gom đề chép tay vào một rọ vô nghĩa thì thà đừng hiện.
    """
    topic_id = item.meta.get("template") or item.meta.get("task")
    if not topic_id:
        return None
    return str(topic_id), str(item.meta.get("method") or "")


def lessons_of(bank: ItemBank, items: list[Item], chapter: str | None = None) -> list[Lesson]:
    """Các bài (kỹ năng) của một chương, kèm dạng bài bên trong từng bài."""
    wanted = skills_in_chapter(bank, chapter) if chapter else set(bank.skills)

    per_skill: dict[str, list[Item]] = {sid: [] for sid in sorted(wanted)}
    for item in items:
        for skill_id in item.skills:
            if skill_id in per_skill:
                per_skill[skill_id].append(item)

    lessons: list[Lesson] = []
    for skill_id, own in per_skill.items():
        counts: dict[str, int] = {}
        names: dict[str, str] = {}
        for item in own:
            found = topic_of(item)
            if not found:
                continue
            topic_id, name = found
            counts[topic_id] = counts.get(topic_id, 0) + 1
            # Chỉ nhận tên KHÁC RỖNG, và nhận cái đầu tiên tìm được: một đề
            # trong nhóm có tên tử tế là đủ đặt tên cho cả nhóm.
            if name and topic_id not in names:
                names[topic_id] = name

        topics = tuple(
            Topic(
                topic_id=tid,
                name_vi=names.get(tid) or TASK_NAMES_VI.get(tid) or tid,
                items=count,
            )
            for tid, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        lessons.append(
            Lesson(
                skill_id=skill_id,
                name_vi=bank.skills[skill_id].name_vi,
                items=len(own),
                topics=topics,
            )
        )
    return lessons


def chapters_of(
    bank: ItemBank, items: list[Item] | None = None, *, deep: bool = False
) -> list[Chapter]:
    """Các chương của một môn, kèm số kỹ năng và số đề, theo thứ tự dạy.

    ``deep=True`` thì gắn luôn bài và dạng bài bên trong — dùng khi trả cả cây
    cho giao diện trong MỘT lời gọi, đỡ phải gọi vòng theo từng chương.
    """
    subject = subject_of(bank)
    pool = items if items is not None else list(bank.items.values())

    by_chapter: dict[str, set[str]] = {}
    for skill_id, skill in bank.skills.items():
        by_chapter.setdefault(skill.chapter, set()).add(skill_id)

    counts: dict[str, int] = {name: 0 for name in by_chapter}
    for item in pool:
        # Một đề nhiều kỹ năng thì đếm vào mọi chương nó chạm tới — cố ý, vì
        # người học chọn chương nào cũng phải thấy đề đó là đề của mình.
        for chapter in {
            bank.skills[s].chapter for s in item.skills if s in bank.skills
        }:
            counts[chapter] = counts.get(chapter, 0) + 1

    return [
        Chapter(
            chapter=name,
            name_vi=display_name(subject, name),
            skill_ids=tuple(sorted(skill_ids)),
            items=counts.get(name, 0),
            lessons=tuple(lessons_of(bank, pool, name)) if deep else (),
        )
        for name, skill_ids in sorted(by_chapter.items(), key=lambda kv: sort_key(subject, kv[0]))
    ]


def skills_in_chapter(bank: ItemBank, chapter: str) -> set[str]:
    return {sid for sid, skill in bank.skills.items() if skill.chapter == chapter}


def filter_items(
    bank: ItemBank,
    items: list[Item],
    chapter: str | None = None,
    skill: str | None = None,
    topic: str | None = None,
) -> list[Item]:
    """Thu hẹp dần theo chương, rồi bài, rồi dạng bài.

    Ba bộ lọc cộng dồn với nhau (AND). Bộ lọc nào để trống thì bỏ qua, nên cùng
    một hàm dùng được cho cả "cả môn" lẫn "đúng một dạng bài".
    """
    out = items
    if chapter:
        wanted = skills_in_chapter(bank, chapter)
        out = [item for item in out if wanted.intersection(item.skills)]
    if skill:
        out = [item for item in out if skill in item.skills]
    if topic:
        out = [item for item in out if (found := topic_of(item)) and found[0] == topic]
    return out
