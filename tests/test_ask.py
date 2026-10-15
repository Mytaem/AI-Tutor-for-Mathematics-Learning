"""Test hỏi đáp lý thuyết.

Điều đáng canh ở đây không phải "trả lời hay hay dở" mà là **không bịa**: câu hỏi
ngoài phạm vi phải bị từ chối thẳng, câu trả lời phải luôn kèm nguồn, và khi model
chết thì vẫn phải trả về đoạn giáo trình chứ không im lặng.

Chạy trên kho giả nhỏ để không phụ thuộc giáo trình thật lẫn model embedding.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import build_service, create_app  # noqa: E402
from src.api.db import Store  # noqa: E402
from src.core.config import AppConfig  # noqa: E402
from src.llm.client import LLMError, LLMResponse  # noqa: E402
from src.rag.ask import MIN_SIMILARITY, OUT_OF_SCOPE, answer_question, build_messages  # noqa: E402
from src.rag.chunking import Chunk, ChunkType  # noqa: E402
from src.rag.store import RagIndex  # noqa: E402


@dataclass
class FakeEncoder:
    """Bộ mã hoá giả: câu nào chứa 'euler' thì gần đoạn về Euler, còn lại thì xa."""

    model_name: str = "fake"

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            near = 1.0 if "euler" in text.lower() else 0.0
            vectors.append([near, 1.0 - near])
        return np.array(vectors, dtype=float)


@dataclass
class FakeClient:
    """Client giả — trả lời cố định, hoặc ném lỗi để thử đường dự phòng."""

    reply: str = "Chu trình Euler là chu trình đi qua mỗi cạnh đúng một lần."
    fail: bool = False
    calls: list[list[dict]] = field(default_factory=list)

    def chat(self, messages, **options) -> LLMResponse:
        self.calls.append(list(messages))
        if self.fail:
            raise LLMError("model chết")
        return LLMResponse(text=self.reply, backend="fake")


@pytest.fixture
def index() -> RagIndex:
    chunks = [
        # Có nhãn chương: cần nó để phép kiểm "chương đã có tài liệu chưa" hoạt
        # động. Kho không mang nhãn chương thì hệ thống cố ý KHÔNG kết luận gì.
        Chunk(text="An Euler circuit is a circuit that uses every edge exactly once.",
              chunk_type=ChunkType.DEFINITION, subject="MAD101",
              chapter="Chapter 6: Graph Theory", source="rosen.pdf", page=10),
        Chunk(text="Bài tập: tìm chu trình Euler của đồ thị sau.",
              chunk_type=ChunkType.EXERCISE, subject="MAD101", source="baitap.pdf"),
        Chunk(text="Quên kiểm tra bậc lẻ khi xét chu trình Euler.",
              chunk_type=ChunkType.PITFALL, subject="MAD101", source="taxonomy:MAD.GRAPH.EULER"),
    ]
    encoder = FakeEncoder()
    embeddings = encoder.encode([c.text for c in chunks])
    return RagIndex(chunks, embeddings=embeddings, encoder=encoder)


class TestScope:
    def test_cau_hoi_ngoai_pham_vi_bi_tu_choi(self, index: RagIndex) -> None:
        answer = answer_question("cách nấu phở bò ngon", index)
        assert answer.in_scope is False
        assert answer.text == OUT_OF_SCOPE
        assert answer.sources == []

    def test_cau_hoi_trong_pham_vi_co_nguon(self, index: RagIndex) -> None:
        answer = answer_question("Euler circuit là gì", index)
        assert answer.in_scope is True
        assert answer.sources and "rosen.pdf" in answer.sources[0]

    def test_nguong_lay_theo_do_tuong_dong_that(self, index: RagIndex) -> None:
        """Không dùng điểm RRF: RRF chỉ là hàm của thứ hạng nên câu nào cũng gần nhau."""
        assert index.best_similarity("Euler circuit") >= MIN_SIMILARITY
        assert index.best_similarity("nấu phở") < MIN_SIMILARITY

    def test_kho_chua_co_embedding_thi_khong_chan(self) -> None:
        """Không có thang tương đồng thì thà trả lời hơi lạc còn hơn từ chối tất."""
        plain = RagIndex([Chunk(text="Chu trình Euler đi qua mỗi cạnh đúng một lần.",
                                chunk_type=ChunkType.DEFINITION, subject="MAD101")])
        assert answer_question("chu trình Euler", plain).in_scope is True


class TestChuongChuaCoTaiLieu:
    """Chương không có tài liệu thì phải NÓI THẲNG, không trả đoạn chương khác.

    Đây là lỗi làm một buổi demo thất bại: hỏi "khoảng tin cậy là gì?", kho
    MAS291 không có chương đó, hệ thống trả về một đoạn của chương Xác suất —
    trôi chảy, đúng môn, sai chủ đề. Với gia sư thì đó là hành vi tệ nhất, vì
    người học không có cách nào biết mà đề phòng.
    """

    @pytest.fixture
    def thieu_chuong(self) -> RagIndex:
        """Kho MAS291 CÓ chương Xác suất nhưng KHÔNG có chương Khoảng tin cậy.

        Phải dựng đúng tình huống đó: chương khác có nhãn hẳn hoi mới chứng tỏ
        việc gắn nhãn hoạt động, và sự vắng mặt của chương này là thật.
        """
        chunks = [
            Chunk(text="The probability of an event E is the ratio of favourable outcomes.",
                  chunk_type=ChunkType.DEFINITION, subject="MAS291",
                  chapter="Chapter 2: Probability", source="02_probability.pdf", page=18),
        ]
        encoder = FakeEncoder()
        return RagIndex(chunks, embeddings=encoder.encode([c.text for c in chunks]),
                        encoder=encoder)

    def test_noi_thang_la_chua_co_tai_lieu(self, thieu_chuong: RagIndex) -> None:
        answer = answer_question("Khoảng tin cậy là gì?", thieu_chuong, subject="MAS291")
        assert "chưa có tài liệu" in answer.text.lower()
        assert answer.sources == []

    def test_khong_phai_la_ngoai_pham_vi(self, thieu_chuong: RagIndex) -> None:
        """Phân biệt hẳn hai ca: lỗi ở dữ liệu của hệ thống, không phải người hỏi sai."""
        answer = answer_question("Khoảng tin cậy là gì?", thieu_chuong, subject="MAS291")
        assert answer.in_scope is True
        assert answer.text != OUT_OF_SCOPE

    def test_chuong_co_tai_lieu_trong_cung_kho_thi_khong_tu_choi(
        self, thieu_chuong: RagIndex
    ) -> None:
        """Cùng kho đó, chương Xác suất có tài liệu nên không được từ chối."""
        answer = answer_question("Xác suất có điều kiện là gì?", thieu_chuong, subject="MAS291")
        assert "chưa có tài liệu" not in answer.text.lower()

    def test_chuong_co_tai_lieu_thi_tra_loi_binh_thuong(self, index: RagIndex) -> None:
        answer = answer_question("Euler circuit là gì", index, subject="MAD101")
        assert "chưa có tài liệu" not in answer.text.lower()
        assert answer.sources


class TestThieuBoMaHoa:
    """Kho CÓ vector nhưng máy thiếu model embedding — lỗi CẤU HÌNH.

    Ca này rất dễ gặp khi chuyển hệ thống sang máy khác: người ta copy
    `data/rag_index/` sang (nhanh hơn dựng lại 40 phút) nhưng quên
    `ollama pull bge-m3`. Kho lưu vector của các ĐOẠN, còn CÂU HỎI thì phải mã
    hoá tại chỗ mỗi lần tra.

    Hai điều phải đúng, và điều thứ hai mới là điều quan trọng:
      1. Không được sập 500 — phải nói ra việc cần làm.
      2. Không được âm thầm rơi về BM25. Đo được: ở chế độ đó cơ chế từ chối
         câu hỏi ngoài phạm vi TẮT HOÀN TOÀN (3/3 câu lạc đề vẫn được trả lời)
         và tỉ lệ trả lời sai chủ đề nhảy lên 32%. Chạy lặng lẽ ở chế độ tệ hơn
         là kiểu hỏng khó phát hiện nhất.
    """

    @pytest.fixture
    def kho_thieu_encoder(self) -> RagIndex:
        from src.rag.store import OllamaEncoder

        chunks = [
            Chunk(text="A confidence interval is a range of plausible values.",
                  chunk_type=ChunkType.DEFINITION, subject="MAS291",
                  chapter="Chapter 8: Confidence Intervals", source="x.pdf"),
        ]
        return RagIndex(chunks,
                        embeddings=np.ones((1, 8), dtype=float),
                        encoder=OllamaEncoder("model-khong-ton-tai-trong-test"))

    def test_noi_ro_viec_can_lam_thay_vi_sap(self, kho_thieu_encoder: RagIndex) -> None:
        answer = answer_question("Khoảng tin cậy là gì?", kho_thieu_encoder, subject="MAS291")
        assert "ollama pull bge-m3" in answer.text
        assert answer.sources == []

    def test_khong_am_tham_tra_loi_bang_bm25(self, kho_thieu_encoder: RagIndex) -> None:
        """Có đoạn khớp từ khoá, nhưng vẫn KHÔNG được trả nó ra như một câu trả lời."""
        answer = answer_question("confidence interval", kho_thieu_encoder, subject="MAS291")
        assert answer.in_scope is False
        assert "A confidence interval is a range" not in answer.text


class TestMoRongTruyVan:
    def test_cau_tieng_viet_duoc_noi_thuat_ngu_tieng_anh(self, index: RagIndex) -> None:
        """Câu hỏi thuần Việt phải tìm được đoạn tiếng Anh.

        Kho giả chỉ chứa câu tiếng Anh "An Euler circuit is…". Không mở rộng
        truy vấn thì "chu trình Euler" không khớp từ nào — chính khoảng cách
        40% / 100% đo được ở EXP-4b.
        """
        answer = answer_question("Chu trình Euler là gì?", index, subject="MAD101")
        assert answer.sources and "rosen.pdf" in answer.sources[0]


class TestSources:
    def test_khong_lay_de_bai_va_bay_lam_nguon(self, index: RagIndex) -> None:
        """Trả lời lý thuyết mà trích đề bài hoặc bảng bẫy thì vừa lạc vừa lộ bài."""
        answer = answer_question("Euler circuit là gì", index, top_k=5)
        joined = " ".join(answer.sources)
        assert "baitap.pdf" not in joined and "taxonomy" not in joined

    def test_prompt_chi_chua_doan_trich(self, index: RagIndex) -> None:
        client = FakeClient()
        answer_question("Euler circuit là gì", index, client=client)
        content = client.calls[0][1]["content"]
        assert "ĐOẠN TRÍCH GIÁO TRÌNH" in content
        assert "every edge exactly once" in content

    def test_he_thong_cam_bia_them(self, index: RagIndex) -> None:
        hits = index.search("Euler circuit", top_k=1, subject="MAD101")
        system = build_messages("Euler circuit là gì", hits)[0]["content"]
        assert "không bịa" in system.lower() or "KHÔNG bịa" in system


class TestFallback:
    def test_khong_co_model_van_tra_ve_doan_trich(self, index: RagIndex) -> None:
        answer = answer_question("Euler circuit là gì", index, client=None)
        assert "every edge exactly once" in answer.text
        assert answer.used_llm is False

    def test_model_chet_thi_van_tra_ve_doan_trich(self, index: RagIndex) -> None:
        answer = answer_question("Euler circuit là gì", index, client=FakeClient(fail=True))
        assert "every edge exactly once" in answer.text
        assert answer.used_llm is False

    def test_chua_dung_kho_thi_bao_ro(self) -> None:
        assert "build_rag_index" in answer_question("bất kỳ", None).text


class TestEndpoint:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(create_app(build_service(AppConfig(), store=Store(":memory:"))))

    def test_cau_hoi_rong_bi_tu_choi(self, client: TestClient) -> None:
        assert client.post("/ask", json={"question": "   "}).status_code == 422

    def test_tra_ve_dung_dinh_dang(self, client: TestClient) -> None:
        body = client.post("/ask", json={"question": "Chu trình Euler là gì?"}).json()
        assert set(body) == {"answer", "sources", "in_scope", "used_llm"}
        assert body["answer"].strip()
