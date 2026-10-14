"""Test cây nội dung học: môn → chương → bài → dạng bài.

Thứ đáng canh nhất ở đây không phải con số, mà là **nhánh rỗng**. Người học tự
chọn phạm vi; chọn vào một nhánh không có đề rồi nhận về lỗi trống là kiểu hỏng
làm họ nghĩ hệ thống chết, trong khi thật ra chỉ là chọn hẹp quá.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ITEMS_DIR, ItemBank, load_items  # noqa: E402
from src.core.syllabus import (  # noqa: E402
    CHAPTER_NAMES_VI,
    chapters_of,
    display_name,
    filter_items,
    skills_in_chapter,
    subject_of,
    topic_of,
)

SUBJECTS = ("MAE101", "MAD101", "MAI391", "MAS291")


def bank_and_items(subject: str):
    bank = ItemBank.load(subject)
    items = list(bank.items.values())
    generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    if generated.exists():
        items += list(load_items(generated))
    return bank, items


@pytest.fixture(scope="module")
def trees():
    out = {}
    for subject in SUBJECTS:
        bank, items = bank_and_items(subject)
        out[subject] = (bank, items, chapters_of(bank, items, deep=True))
    return out


class TestTenGoi:
    @pytest.mark.parametrize("subject", SUBJECTS)
    def test_moi_chuong_deu_co_ten_tieng_viet(self, subject: str, trees) -> None:
        """Thiếu một dòng dịch thì chương đó hiện tên tiếng Anh giữa danh sách tiếng Việt."""
        bank, _, _ = trees[subject]
        missing = [
            chapter
            for chapter in {skill.chapter for skill in bank.skills.values()}
            if (subject, chapter) not in CHAPTER_NAMES_VI
        ]
        assert missing == [], f"{subject} chưa dịch chương: {missing}"

    def test_chua_dich_thi_van_ra_chu_gi_do(self) -> None:
        assert display_name("MAE101", "Chương Lạ") == "Chương Lạ"
        assert display_name("MAD101", "Ch9 Something New") == "Something New"

    @pytest.mark.parametrize("subject", SUBJECTS)
    def test_khong_dang_bai_nao_hien_ma_tran(self, subject: str, trees) -> None:
        """``reg_slope`` lẫn giữa các tên tiếng Việt là lỗi hiện rất rõ trên giao diện.

        Đề chép tay chỉ có ``task`` chứ không có ``method``; tên của chúng lấy
        từ bảng ``TASK_NAMES_VI``.
        """
        _, _, chapters = trees[subject]
        raw = [
            topic.topic_id
            for chapter in chapters
            for lesson in chapter.lessons
            for topic in lesson.topics
            if topic.name_vi == topic.topic_id
        ]
        assert raw == [], f"{subject} còn dạng bài chưa có tên: {sorted(set(raw))}"


class TestThuTu:
    def test_mae101_theo_trinh_tu_day(self, trees) -> None:
        """MAE101 không đánh số chương nên thứ tự phải do bảng quy định."""
        _, _, chapters = trees["MAE101"]
        names = [c.chapter for c in chapters]
        assert names.index("Limits") < names.index("Integration")
        assert names.index("Integration") < names.index("Vector Spaces")

    @pytest.mark.parametrize("subject", ["MAD101", "MAI391", "MAS291"])
    def test_chuong_co_so_thi_sap_theo_so(self, subject: str, trees) -> None:
        """Sắp theo chuỗi thì "Ch10" đứng trước "Ch2" — phải sắp theo số."""
        _, _, chapters = trees[subject]
        numbers = [int(c.chapter[2:].split()[0]) for c in chapters]
        assert numbers == sorted(numbers)


class TestDemDe:
    @pytest.mark.parametrize("subject", SUBJECTS)
    def test_so_de_cua_chuong_khop_voi_bo_loc(self, subject: str, trees) -> None:
        """Số hiện trên nút phải đúng bằng số đề bấm vào sẽ nhận được."""
        bank, items, chapters = trees[subject]
        for chapter in chapters:
            assert chapter.items == len(filter_items(bank, items, chapter=chapter.chapter))

    @pytest.mark.parametrize("subject", SUBJECTS)
    def test_so_de_cua_dang_bai_khop_voi_bo_loc(self, subject: str, trees) -> None:
        bank, items, chapters = trees[subject]
        for chapter in chapters:
            for lesson in chapter.lessons:
                for topic in lesson.topics:
                    got = filter_items(
                        bank, items,
                        chapter=chapter.chapter, skill=lesson.skill_id, topic=topic.topic_id,
                    )
                    assert topic.items == len(got), (
                        f"{subject}/{chapter.chapter}/{lesson.skill_id}/{topic.topic_id}"
                    )

    def test_de_nhieu_ky_nang_dem_vao_moi_chuong_no_cham(self, trees) -> None:
        """Tổng số đề của các bài CÓ THỂ lớn hơn số đề của chương — đúng chứ không sai.

        Một đề mang hai kỹ năng cùng chương thì chương đếm một lần, còn mỗi bài
        đếm một lần. Test này chốt hành vi đó để sau không ai "sửa" nó.
        """
        _, _, chapters = trees["MAD101"]
        logic = chapters[0]
        assert sum(l.items for l in logic.lessons) > logic.items


class TestNhanhRong:
    @pytest.mark.parametrize("subject", SUBJECTS)
    def test_khong_mon_nao_con_chuong_rong(self, subject: str, trees) -> None:
        """Mọi chương của mọi môn đều phải có đề.

        Test này từng khẳng định MAE101 có ĐÚNG hai chương rỗng (giới hạn, đạo
        hàm) — 5 kỹ năng không bài nào, nên chọn chương "Giới hạn và liên tục"
        thì không luyện được gì. `src/data_gen/calculus_items.py` bịt lỗ đó.
        Giữ test ở dạng này để nếu ai thêm chương mới mà quên thêm bộ sinh đề
        thì nó đỏ ngay, chứ không lặng lẽ thành một nhánh chết.
        """
        _, _, chapters = trees[subject]
        empty = sorted(c.chapter for c in chapters if c.items == 0)
        assert empty == [], f"{subject} còn chương không có đề: {empty}"

    @pytest.mark.parametrize("subject", SUBJECTS)
    def test_khong_bai_nao_rong(self, subject: str, trees) -> None:
        """Chương có đề mà một BÀI trong đó rỗng thì vẫn là nhánh chết."""
        _, _, chapters = trees[subject]
        empty = [
            f"{chapter.name_vi} / {lesson.name_vi}"
            for chapter in chapters
            for lesson in chapter.lessons
            if lesson.items == 0
        ]
        assert empty == [], f"{subject} còn bài không có đề: {empty}"


class TestLocCongDon:
    def test_cang_hep_cang_it_de(self, trees) -> None:
        bank, items, chapters = trees["MAD101"]
        chapter = next(c for c in chapters if c.lessons and c.lessons[0].topics)
        lesson = chapter.lessons[0]
        topic = lesson.topics[0]

        whole = len(items)
        by_chapter = len(filter_items(bank, items, chapter=chapter.chapter))
        by_skill = len(filter_items(bank, items, chapter=chapter.chapter, skill=lesson.skill_id))
        by_topic = len(filter_items(
            bank, items, chapter=chapter.chapter, skill=lesson.skill_id, topic=topic.topic_id))

        assert whole >= by_chapter >= by_skill >= by_topic >= 1

    def test_khong_loc_gi_thi_tra_nguyen(self, trees) -> None:
        bank, items, _ = trees["MAS291"]
        assert filter_items(bank, items) is items

    def test_chuong_khong_ton_tai_thi_ra_rong(self, trees) -> None:
        bank, items, _ = trees["MAS291"]
        assert filter_items(bank, items, chapter="Ch99 Không Có") == []


class TestPhuTro:
    def test_doc_duoc_ma_mon_tu_ngan_hang(self, trees) -> None:
        for subject in SUBJECTS:
            bank, _, _ = trees[subject]
            assert subject_of(bank) == subject

    def test_ky_nang_cua_chuong_khong_lan_sang_chuong_khac(self, trees) -> None:
        bank, _, chapters = trees["MAS291"]
        groups = [skills_in_chapter(bank, c.chapter) for c in chapters]
        for index, first in enumerate(groups):
            for second in groups[index + 1:]:
                assert not first & second

    def test_de_khong_ghi_dang_bai_thi_tra_none(self, trees) -> None:
        _, items, _ = trees["MAE101"]
        for item in items:
            found = topic_of(item)
            if found is None:
                assert not item.meta.get("template") and not item.meta.get("task")
