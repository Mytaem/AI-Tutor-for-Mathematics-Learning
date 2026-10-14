"""EXP-4b — chất lượng hỏi đáp lý thuyết, đo trên bộ câu hỏi ĐỘC LẬP.

    python scripts/exp4b_ask_quality.py                # cấu hình hiện tại
    python scripts/exp4b_ask_quality.py --no-glossary  # tắt mở rộng truy vấn
    python scripts/exp4b_ask_quality.py --compare      # chạy cả hai rồi so

**Vì sao cần một thí nghiệm riêng, không dùng EXP-4.** EXP-4 sinh câu hỏi từ
``skill.name_vi`` và tính nhãn đúng bằng ``skill.name_en``. Từ điển thuật ngữ
cũng suy ra từ đúng cặp ``name_vi → name_en`` đó. Dùng EXP-4 để đo từ điển là
**đo vòng tròn**: truy vấn được dịch thành đúng cái nhãn mình đang tìm, Recall
sẽ vọt lên gần 1 mà không nói gì về chất lượng thật. Con số đó không được phép
trích vào báo cáo.

Bộ câu hỏi ở đây viết TAY, diễn đạt theo cách sinh viên thật sẽ hỏi, và từ khoá
chấp nhận được cũng viết tay — không lấy từ bảng kỹ năng.

Bốn kết cục, và phân biệt chúng mới là điểm chính:

    ĐƯỢC       trả lời và đúng chủ đề
    NÓI THẬT   chương chưa có tài liệu, hệ thống nói thẳng — tính là ĐẠT
    TRẢ BỪA    trả lời trôi chảy nhưng sai chủ đề — tệ nhất, vì người học không
               có cách nào biết mà đề phòng
    CHẶN OAN   câu hỏi trong chương trình mà bị trả "ngoài phạm vi"

Gộp "nói thật" vào ĐẠT là có chủ ý: với một gia sư, thừa nhận không có tài liệu
là hành vi ĐÚNG, còn trả lời cho có mới là lỗi.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402

#: (môn, câu hỏi, từ khoá chấp nhận được, chương có tài liệu hay không)
#:
#: ``False`` ở cột cuối = chương này kho CHƯA có tài liệu, nên kết cục đúng là
#: hệ thống nói thẳng ra. Bốn câu MAS291 cuối rơi vào nhóm đó vì kho thiếu
#: chương 6, 8, 9, 11 — xem `scripts/rag_coverage.py`.
QUESTIONS: list[tuple[str, str, list[str], bool]] = [
    ("MAD101", "Chu trình Euler là gì?", ["euler"], True),
    ("MAD101", "Đồ thị hai phía là gì?", ["bipartite", "two-color", "2-color", "two color"], True),
    ("MAD101", "Nguyên lý bù trừ dùng khi nào?", ["inclusion", "exclusion"], True),
    ("MAD101", "Cây khung nhỏ nhất là gì?", ["spanning tree"], True),
    ("MAD101", "Luật De Morgan phát biểu thế nào?", ["de morgan"], True),
    ("MAD101", "Nguyên lý chuồng bồ câu nói gì?", ["pigeonhole"], True),
    ("MAD101", "Thuật toán Euclid tìm gì?", ["euclid", "gcd", "greatest common"], True),
    ("MAE101", "Tích phân từng phần là gì?", ["by parts"], True),
    ("MAE101", "Quy tắc hàm hợp là gì?", ["chain rule"], True),
    ("MAE101", "Định nghĩa đạo hàm", ["derivative"], True),
    ("MAE101", "Ma trận nghịch đảo tính thế nào?", ["inverse"], True),
    ("MAE101", "Định thức của ma trận là gì?", ["determinant"], True),
    ("MAE101", "Dạng vô định 0/0 xử lý thế nào?",
     ["indeterminate", "l'hôpital", "lhopital", "l’hôpital", "hospital"], True),
    ("MAE101", "Trị riêng của ma trận là gì?", ["eigenvalue", "eigenvector"], True),
    ("MAI391", "Phân tích SVD là gì?", ["singular value"], True),
    ("MAI391", "Gradient là gì?", ["gradient"], True),
    ("MAI391", "Tích vô hướng là gì?", ["inner product", "dot product"], True),
    ("MAI391", "Phép chiếu trực giao là gì?", ["projection"], True),
    ("MAS291", "Phân phối chuẩn có tính chất gì?", ["normal"], True),
    ("MAS291", "Xác suất có điều kiện là gì?", ["conditional probability"], True),
    ("MAS291", "Định lý Bayes phát biểu thế nào?", ["bayes"], True),
    # Bảy câu dưới thuộc các chương MAS291 từng KHÔNG có tài liệu nào. Sau khi
    # nạp OpenStax *Introductory Statistics 2e* (xem docs/nguon-tai-lieu.md),
    # chúng phải được trả lời thật, không còn là "chưa có tài liệu".
    ("MAS291", "Khoảng tin cậy là gì?", ["confidence interval"], True),
    ("MAS291", "p-value nghĩa là gì?", ["p-value", "p value"], True),
    ("MAS291", "Hồi quy tuyến tính là gì?", ["regression"], True),
    ("MAS291", "Thống kê mô tả gồm những gì?",
     ["descriptive statistic", "mean", "median", "standard deviation"], True),
    ("MAS291", "Định lý giới hạn trung tâm nói gì?", ["central limit"], True),
    ("MAS291", "Phân phối nhị thức dùng khi nào?", ["binomial"], True),
    ("MAS291", "Khi nào dùng kiểm định t thay vì z?",
     ["t-distribution", "t distribution", "student", "degrees of freedom"], True),
]

#: Câu hỏi NGOÀI bốn môn — hệ thống phải từ chối, không được đoán.
OUT_OF_SCOPE = [
    ("MAD101", "Cách nấu phở bò ngon"),
    ("MAE101", "Messi ghi được bao nhiêu bàn"),
    ("MAS291", "Thời tiết Quy Nhơn hôm nay thế nào"),
]


def run(index, use_glossary: bool) -> dict:
    from src.rag import glossary
    from src.rag.ask import answer_question

    # Tắt từ điển bằng cách cho nó trả về rỗng. Làm ở đây chứ không thêm tham
    # số vào `answer_question`: đường chạy khi đo phải là ĐÚNG đường chạy thật,
    # không phải một nhánh riêng chỉ dùng cho thí nghiệm.
    original = glossary.english_terms
    if not use_glossary:
        glossary.english_terms = lambda question: []

    try:
        buckets: dict[str, list[str]] = {"good": [], "honest": [], "wrong": [], "false_refusal": []}
        for subject, question, keywords, has_material in QUESTIONS:
            answer = answer_question(question, index, subject=subject)
            haystack = " ".join((answer.text + " " + " ".join(answer.passages)).split()).lower()
            said_no_material = "chưa có tài liệu" in answer.text.lower()
            label = f"{subject}: «{question}»"

            if not has_material:
                buckets["honest" if said_no_material else "wrong"].append(label)
            elif said_no_material or not answer.in_scope:
                buckets["false_refusal"].append(label)
            elif any(keyword in haystack for keyword in keywords):
                buckets["good"].append(label)
            else:
                buckets["wrong"].append(label)

        refused = [
            f"{subject}: «{question}»"
            for subject, question in OUT_OF_SCOPE
            if answer_question(question, index, subject=subject).in_scope
        ]
    finally:
        glossary.english_terms = original

    total = len(QUESTIONS)
    return {
        "n": total,
        "good": len(buckets["good"]),
        "honest_no_material": len(buckets["honest"]),
        "usable_rate": (len(buckets["good"]) + len(buckets["honest"])) / total,
        "wrong_topic": len(buckets["wrong"]),
        "false_refusal": len(buckets["false_refusal"]),
        "out_of_scope_leaked": len(refused),
        "details": {key: value for key, value in buckets.items() if value},
        "out_of_scope_leaked_list": refused,
    }


def show(name: str, result: dict) -> None:
    print(f"\n--- {name} ({result['n']} câu hỏi trong chương trình) ---")
    print(f"  trả lời đúng chủ đề          {result['good']:>3}  {result['good']/result['n']:.0%}")
    print(f"  nói thật 'chưa có tài liệu'  {result['honest_no_material']:>3}"
          f"  {result['honest_no_material']/result['n']:.0%}")
    print(f"  => ĐẠT                       {result['good']+result['honest_no_material']:>3}"
          f"  {result['usable_rate']:.0%}")
    print(f"  TRẢ BỪA (sai chủ đề)         {result['wrong_topic']:>3}"
          f"  {result['wrong_topic']/result['n']:.0%}")
    print(f"  chặn oan                     {result['false_refusal']:>3}"
          f"  {result['false_refusal']/result['n']:.0%}")
    print(f"  câu ngoài phạm vi bị trả lời {result['out_of_scope_leaked']:>3} "
          f"/ {len(OUT_OF_SCOPE)}")
    for label in result["details"].get("wrong", [])[:6]:
        print(f"     trả bừa: {label}")
    for label in result["details"].get("false_refusal", [])[:6]:
        print(f"     chặn oan: {label}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-glossary", action="store_true",
                        help="tắt mở rộng truy vấn bằng từ điển thuật ngữ")
    parser.add_argument("--compare", action="store_true", help="chạy cả hai cấu hình rồi so")
    parser.add_argument("--out", type=Path, default=ROOT / "experiments" / "exp4" / "ask_quality.json")
    args = parser.parse_args()

    from src.rag.hint_retriever import load_index

    index = load_index()
    if index is None:
        print("Chưa dựng kho giáo trình — chạy scripts/build_rag_index.py trước.")
        raise SystemExit(1)

    print(f"Kho: {len(index.chunks)} đoạn | loại bỏ vì là mục lục/chỉ mục: {len(index.boilerplate)}")

    results = {}
    if args.compare:
        results["không từ điển"] = run(index, use_glossary=False)
        results["có từ điển"] = run(index, use_glossary=True)
    else:
        name = "không từ điển" if args.no_glossary else "có từ điển"
        results[name] = run(index, use_glossary=not args.no_glossary)

    for name, result in results.items():
        show(name, result)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {args.out}")


if __name__ == "__main__":
    main()
