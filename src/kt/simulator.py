"""Học sinh mô phỏng — nguồn dữ liệu để thử vòng lặp thích ứng khi chưa có người dùng thật.

Vì sao cần: DKT/SAKT đòi hàng chục nghìn lượt tương tác, còn bộ chọn bài thì phải
so sánh được bốn chiến lược trên CÙNG một quần thể người học. Chờ người dùng thật
thì không bao giờ đủ, mà thiếu số liệu này thì Gate 3 không có gì để báo cáo.

Mô hình sinh dữ liệu (ghi rõ trong báo cáo, đây là GIẢ ĐỊNH chứ không phải sự thật):

- Mỗi học sinh có một vector **năng lực ẩn** θ theo từng kỹ năng, khởi tạo từ độ
  sâu trong đồ thị tiên quyết — kỹ năng càng sâu thì ban đầu càng yếu, đúng như
  người học thật vào lớp.
- Xác suất làm đúng theo kiểu IRT: ``σ(θ_kỹ_năng − b_bài)``, rồi chèn **slip**
  (biết mà vẫn sai) và **guess** (không biết mà đúng). Bài nhiều kỹ năng thì phải
  qua được kỹ năng YẾU NHẤT — mô phỏng việc một mắt xích hỏng là hỏng cả bài.
- Học sau mỗi lần làm: làm đúng thì θ tăng ít (củng cố), làm sai mà có gợi ý thì
  θ tăng NHIỀU hơn (học từ lỗi) — đây chính là giả thiết sư phạm mà hệ thống đặt
  cược vào, nên EXP-6 phải báo cáo kết quả ở cả hai mức ``learn_from_hint``.

Hạn chế phải nói thẳng, và nó THIÊN VỊ cho DKT chứ không phải cho BKT: mỗi học
sinh ở đây có một năng lực NỀN dùng chung cho mọi kỹ năng, cộng thêm nhiễu riêng
từng kỹ năng. Mô hình nào chia sẻ được thông tin giữa các kỹ năng (DKT, SAKT) sẽ
đoán được ngay từ vài lượt đầu rằng người này khá hay yếu; BKT về cấu trúc không
làm được điều đó vì mỗi kỹ năng một biến độc lập. Vì vậy khoảng cách AUC đo trên
dữ liệu mô phỏng là chặn TRÊN, không được dùng để tuyên bố DKT tốt hơn BKT ngoài
đời — so sánh đó phải làm trên dữ liệu công khai (ASSISTments) hoặc log người thật.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from src.core.schema import Item, Skill
from src.kt.bkt import BKTTracker
from src.kt.coldstart import make_tracker, skill_depths
from src.kt.selector import SelectorWeights, select_next, select_random

#: Mốc coi là đã thành thạo một kỹ năng — dùng cho tiêu chí "bao nhiêu bài thì thạo".
MASTERY_THRESHOLD = 0.85


@dataclass
class StudentProfile:
    """Tham số sinh một học sinh ảo."""

    ability_mean: float = -0.1      # hơi âm: đa số vào học là chưa biết
    ability_sd: float = 1.0
    slip: float = 0.10              # biết mà vẫn sai (bất cẩn)
    guess: float = 0.15             # không biết mà đúng (đoán, trắc nghiệm)
    #: Ba tốc độ học dưới đây được hiệu chỉnh theo một tiêu chí ĐỘC LẬP với mọi
    #: chiến lược chọn bài: một người học trung bình phải thạo được một kỹ năng
    #: sau khoảng 6-10 lượt luyện, đúng khoảng mà tài liệu ITS hay báo cáo. Tuyệt
    #: đối không chỉnh chúng cho tới khi chiến lược mình thích thắng — làm thế thì
    #: EXP-6 chỉ còn là một lời tự khen.
    learn_correct: float = 0.60     # θ tăng khi làm đúng
    learn_from_hint: float = 0.90   # θ tăng khi làm sai NHƯNG được gợi ý
    learn_no_hint: float = 0.20     # θ tăng khi làm sai và chỉ được báo "sai"
    depth_penalty: float = 0.25     # mỗi bậc sâu trong DAG tiên quyết trừ bấy nhiêu θ


@dataclass
class Interaction:
    """Một lượt làm bài — đúng định dạng mà DKT/SAKT cần."""

    student_id: str
    step: int
    item_id: str
    skill_id: str
    correct: bool
    p_correct: float          # xác suất thật lúc sinh (chỉ dùng để phân tích, không cho mô hình thấy)
    ability: float            # năng lực ẩn tại thời điểm đó


@dataclass
class SimulatedStudent:
    """Một học sinh ảo: năng lực ẩn theo kỹ năng, có học sau mỗi lần làm bài."""

    student_id: str
    ability: dict[str, float]
    profile: StudentProfile = field(default_factory=StudentProfile)

    def probability_correct(self, item: Item) -> float:
        """Xác suất làm đúng — quyết định bởi kỹ năng YẾU NHẤT của bài."""
        if not item.skills:
            return 0.5
        weakest = min(self.ability.get(skill, 0.0) for skill in item.skills)
        latent = _sigmoid(weakest - _difficulty_logit(item.difficulty))
        return self.profile.guess + (1 - self.profile.slip - self.profile.guess) * latent

    def attempt(self, item: Item, rng: random.Random) -> tuple[bool, float]:
        probability = self.probability_correct(item)
        return rng.random() < probability, probability

    def learn(self, item: Item, correct: bool, *, with_hint: bool) -> None:
        """Cập nhật năng lực ẩn sau một lượt.

        Mức tăng giảm dần khi đã giỏi (``1 − σ(θ)``): người đã thạo thì làm thêm
        một bài gần như không tiến thêm, còn người mới học thì tiến nhanh.
        """
        if correct:
            gain = self.profile.learn_correct
        else:
            gain = self.profile.learn_from_hint if with_hint else self.profile.learn_no_hint
        for skill in item.skills:
            current = self.ability.get(skill, 0.0)
            self.ability[skill] = current + gain * (1 - _sigmoid(current))

    def mastered(self, skill_ids: list[str]) -> list[str]:
        return [s for s in skill_ids if _sigmoid(self.ability.get(s, 0.0)) >= MASTERY_THRESHOLD]


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(value, 30.0), -30.0)))


def _difficulty_logit(difficulty: float) -> float:
    """Đổi độ khó trong [0, 1] sang thang logit: 0.5 là trung bình, 0.9 là rất khó."""
    clamped = min(max(difficulty, 0.02), 0.98)
    return math.log(clamped / (1 - clamped)) * 2.0


# --------------------------------------------------------------------------
# Sinh quần thể
# --------------------------------------------------------------------------

def make_student(
    student_id: str,
    skills: dict[str, Skill],
    rng: random.Random,
    profile: StudentProfile | None = None,
) -> SimulatedStudent:
    """Một học sinh ảo, năng lực ban đầu giảm dần theo độ sâu trong DAG tiên quyết."""
    profile = profile or StudentProfile()
    depths = skill_depths(skills)
    base = rng.gauss(profile.ability_mean, profile.ability_sd)   # năng lực chung của người này
    ability = {
        skill_id: base - profile.depth_penalty * depths.get(skill_id, 0) + rng.gauss(0, 0.4)
        for skill_id in skills
    }
    return SimulatedStudent(student_id, ability, profile)


def make_cohort(
    count: int,
    skills: dict[str, Skill],
    seed: int = 20260923,
    profile: StudentProfile | None = None,
) -> list[SimulatedStudent]:
    rng = random.Random(seed)
    return [make_student(f"sim-{index:04d}", skills, rng, profile) for index in range(count)]


# --------------------------------------------------------------------------
# Chạy một phiên luyện tập
# --------------------------------------------------------------------------

#: Các chiến lược chọn bài đem so ở EXP-6.
STRATEGIES = ("random", "sequential", "weakest", "zpd", "zpd_coverage")

#: Bộ trọng số của chiến lược "chỉ nhắm kỹ năng yếu nhất".
WEAKEST_ONLY = SelectorWeights(weak_skill=1.0, zpd=0.0, prerequisite=0.0, repetition_penalty=3.0)

#: ZPD cộng tiêu chí phủ kỹ năng — sinh ra sau khi EXP-6 cho thấy ZPD thuần đào
#: sâu một kỹ năng và bỏ quên cả chương.
#:
#: Trọng số 6 chọn từ bảng quét trên chương đồ thị MAD101 (60 học sinh × 60 lượt):
#: 0 → thạo 1.2 kỹ năng, đúng 76%; 1.5 → 1.9; 3 → 2.1; 6 → 2.8; 12 → 3.3, đúng 69%.
#: Càng nặng thì càng phủ rộng nhưng càng mất tính "vừa sức", tới mức hoá ra quay
#: vòng đều như dạy theo thứ tự giáo trình. 6 là chỗ còn giữ được cả hai.
ZPD_COVERAGE = SelectorWeights(coverage=6.0)


def _pick_item(
    strategy: str,
    items: list[Item],
    tracker: BKTTracker,
    skills: dict[str, Skill],
    seen: set[str],
    step: int,
    rng: random.Random,
    practised: dict[str, int],
) -> Item | None:
    if not items:
        return None
    if strategy == "random":
        return select_random(items, rng)
    if strategy == "sequential":
        return items[step % len(items)]          # theo thứ tự giáo trình
    if strategy == "weakest":
        # Chỉ nhìn kỹ năng yếu nhất, bỏ qua chuyện bài có vừa sức hay không —
        # baseline "tham lam", để thấy phần đóng góp riêng của tiêu chí ZPD.
        return select_next(items, tracker, skills, seen, WEAKEST_ONLY)
    if strategy == "zpd_coverage":
        return select_next(items, tracker, skills, seen, ZPD_COVERAGE, practised)
    return select_next(items, tracker, skills, seen)


@dataclass
class SessionResult:
    """Kết quả một phiên luyện tập của một học sinh."""

    student_id: str
    strategy: str
    interactions: list[Interaction]
    mastered_skills: int
    steps_to_mastery: int | None      # số bài để đạt ngưỡng thành thạo mục tiêu
    accuracy: float
    longest_wrong_streak: int         # chỉ số "chán nản": sai liên tiếp bao nhiêu bài


def run_session(
    student: SimulatedStudent,
    items: list[Item],
    skills: dict[str, Skill],
    strategy: str = "zpd",
    steps: int = 40,
    seed: int = 0,
    with_hint: bool = True,
    mastery_target: int | None = None,
) -> SessionResult:
    """Cho một học sinh ảo luyện ``steps`` bài theo một chiến lược chọn bài.

    Hệ thống chỉ được nhìn thấy ĐÚNG/SAI (qua ``BKTTracker``), không bao giờ thấy
    năng lực ẩn — nếu không thì so sánh các chiến lược trở nên vô nghĩa.
    """
    rng = random.Random(seed)
    tracker = make_tracker(skills)
    interactions: list[Interaction] = []
    seen: set[str] = set()
    correct_count = 0
    streak = worst_streak = 0
    steps_to_mastery: int | None = None
    target = mastery_target if mastery_target is not None else max(1, len(skills) // 2)

    practised: dict[str, int] = {}

    attempted = 0
    for step in range(steps):
        item = _pick_item(strategy, items, tracker, skills, seen, step, rng, practised)
        if item is None:
            break
        attempted += 1

        correct, probability = student.attempt(item, rng)
        for skill in item.skills:
            interactions.append(Interaction(
                student_id=student.student_id, step=step, item_id=item.item_id, skill_id=skill,
                correct=correct, p_correct=probability, ability=student.ability.get(skill, 0.0),
            ))

        tracker.observe(item.skills, correct)
        student.learn(item, correct, with_hint=with_hint)
        seen.add(item.item_id)
        for skill in item.skills:
            practised[skill] = practised.get(skill, 0) + 1

        correct_count += int(correct)
        streak = 0 if correct else streak + 1
        worst_streak = max(worst_streak, streak)

        if steps_to_mastery is None and len(student.mastered(list(skills))) >= target:
            steps_to_mastery = step + 1

    return SessionResult(
        student_id=student.student_id,
        strategy=strategy,
        interactions=interactions,
        mastered_skills=len(student.mastered(list(skills))),
        steps_to_mastery=steps_to_mastery,
        # Chia cho số lượt ĐÃ LÀM, không phải min(số lượt, số đề). Bản cũ cho ra
        # tỉ lệ đúng 212% ở chương chỉ có 20 đề mà luyện 60 lượt — bộ chọn vẫn cho
        # làm lại đề cũ khi hết đề mới, nên số lượt vượt xa số đề.
        accuracy=correct_count / max(1, attempted),
        longest_wrong_streak=worst_streak,
    )


def simulate_cohort(
    items: list[Item],
    skills: dict[str, Skill],
    students: int = 50,
    strategy: str = "zpd",
    steps: int = 40,
    seed: int = 20260923,
    with_hint: bool = True,
    profile: StudentProfile | None = None,
) -> list[SessionResult]:
    """Chạy cả một lớp học sinh ảo — mỗi người một seed riêng để tái lập được."""
    cohort = make_cohort(students, skills, seed=seed, profile=profile)
    return [
        run_session(student, items, skills, strategy=strategy, steps=steps,
                    seed=seed + index, with_hint=with_hint)
        for index, student in enumerate(cohort)
    ]


def to_sequences(results: list[SessionResult]) -> list[list[tuple[str, int]]]:
    """Đổi sang định dạng DKT/SAKT: mỗi học sinh một chuỗi (mã kỹ năng, đúng/sai)."""
    return [
        [(step.skill_id, int(step.correct)) for step in result.interactions]
        for result in results
        if result.interactions
    ]
