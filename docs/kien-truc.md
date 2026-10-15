# Kiến trúc và hướng dẫn bảo trì

Tài liệu này viết cho người **đọc và sửa code**. Nó trả lời ba câu: hệ thống xếp thế
nào, một lượt làm bài đi qua những đâu, và muốn thêm thứ gì thì sửa ở đâu.

Tài liệu liên quan: [huong-dan-cai-dat.md](huong-dan-cai-dat.md) để dựng máy,
[huong-dan-su-dung.md](huong-dan-su-dung.md) để biết người dùng thấy gì.

---

## 1. Ba nguyên tắc không được vi phạm

Đọc ba điều này trước khi sửa bất cứ gì. Phần lớn quyết định thiết kế trong code là hệ
quả của chúng.

### 1.1. Không kiểm chứng được thì IM LẶNG, không kết tội

`StepCheck.ok` và `final_answer_correct` đều có **ba** giá trị: `True`, `False`, và
`None` — *không đủ cơ sở kết luận*.

Một gia sư báo sinh viên làm sai trong khi thực ra máy không kiểm nổi sẽ phá huỷ lòng
tin, và đó là thứ khó lấy lại nhất. Cụ thể trong code:

- `None` **không được** cập nhật mô hình năng lực (`TutorService.submit`).
- `None` phải hiện ra giao diện là *"chưa đọc được đáp án"*, khác hẳn *"chưa đúng"*.
- `None` **không được** lọt vào tập gán nhãn lỗi thật (`label_real_errors.py` lọc theo
  `final_answer_correct = 0`, không theo `is_correct`).

Đã từng vi phạm cả ba chỗ. Triệu chứng: sinh viên viết đúng đáp án nhưng sai định dạng
thì bị tụt mức thành thạo đúng bằng làm sai (đo được 0,45 → 0,23).

### 1.2. Tầng gợi ý chỉ được đọc `VerificationResult`

Không đọc lại đầu ra thô của LLM. Nếu gợi ý có thể bịa thì việc kiểm chứng ở tầng dưới
thành vô nghĩa.

### 1.3. Đáp án không rời khỏi server trước khi sinh viên được phép thấy

API có lớp `PublicItem` riêng, **cố ý không chứa** `answer`, `integrand` và
`reference_solution_steps`. Thêm trường vào `PublicItem` thì phải tự hỏi: mở tab Network
của trình duyệt có đọc được đáp án không?

Có test quét **nhiều đề của cả 4 môn** để chốt điều này, không chỉ đề đầu tiên.

---

## 2. Bản đồ mã nguồn

```
src/
├── core/           nền chung, không phụ thuộc gì ở trên
│   ├── schema.py       Item, Submission, VerificationResult, AnswerType, HintLevel
│   ├── itembank.py     nạp đề, kỹ năng, bảng mã lỗi
│   ├── syllabus.py     cây môn → chương → bài → dạng bài
│   └── config.py        đọc cấu hình từ biến môi trường
│
├── verify/         LÕI KỸ THUẬT — kiểm chứng ký hiệu
│   ├── base.py         lớp Verifier, chuẩn hoá đáp án sinh viên
│   ├── equivalence.py  so hai biểu thức: symbolic + numeric sampling + timeout
│   ├── calculus.py     MAE101 — giới hạn, đạo hàm, tích phân
│   ├── linalg.py       đại số tuyến tính (dùng chung MAE101 + MAI391)
│   ├── mml.py          MAI391 — gradient, SVD, PCA, SVM
│   ├── probstat.py     MAS291 — có kiểm chéo Monte Carlo
│   ├── discrete.py     MAD101 — có kiểm chéo liệt kê vét cạn
│   ├── composite.py    ghép nhiều bộ chấm thành một môn
│   └── registry.py     tra bộ chấm theo môn
│
├── tutor/          tầng sư phạm
│   ├── hint_policy.py  thang 6 mức + luật leo thang
│   ├── hints.py        sinh gợi ý từ template
│   ├── llm_hints.py    sinh gợi ý bằng model
│   └── guardrail.py    chặn gợi ý làm lộ đáp án
│
├── rag/            truy xuất giáo trình
│   ├── ingest.py       đọc PDF/DOCX/PPTX
│   ├── chunking.py     chia theo CẤU TRÚC, không theo độ dài
│   ├── bm25.py         BM25 tự cài
│   ├── store.py        kho lai BM25 + dense, RRF, lọc đoạn rác
│   ├── glossary.py     từ điển thuật ngữ Việt–Anh, hai chiều
│   ├── coverage.py     chương nào thực sự có tài liệu
│   ├── hint_retriever.py  truy xuất cho gợi ý (lọc chống lộ đáp án)
│   └── ask.py          hỏi đáp lý thuyết
│
├── kt/             mô hình năng lực
│   ├── bkt.py          BKT — mặc định, giải thích được
│   ├── dkt.py / sakt.py   mạng hồi tiếp / self-attention
│   ├── dkt_tracker.py  DKT với giao diện tương thích BKT
│   ├── coldstart.py    khởi tạo từ đồ thị tiên quyết + test đầu vào
│   ├── selector.py     chọn bài theo ZPD + phủ kỹ năng
│   └── simulator.py    học sinh mô phỏng (để test vòng lặp adaptive)
│
├── data_gen/       sinh đề và sinh lỗi
│   ├── bank_builder.py    khung Registry; mọi đề phải tự chấm được mới nhận
│   ├── *_items.py         bộ sinh đề theo mảng kiến thức
│   ├── error_injector.py  biến lời giải đúng thành sai theo ĐÚNG mã lỗi
│   └── *_errors.py        bộ sinh lỗi theo môn
│
├── llm/client.py   một interface, ba backend: vLLM → Ollama → cache
├── api/            FastAPI + SQLite
└── bot/            Telegram, client mỏng gọi API
```

**Hướng phụ thuộc là một chiều**: `core` ← `verify` ← `tutor` ← `api`. `rag` và `kt`
cùng tầng với `tutor`. Đừng để `core` import gì từ tầng trên.

---

## 3. Một lượt làm bài đi qua đâu

```
POST /attempt
   │
   ├─ TutorService.submit()                         src/api/app.py
   │     │
   │     ├─ tracker = tracker_for(user, subject)    phát lại lịch sử từ DB
   │     ├─ mastery_before = min(mức của các kỹ năng của đề)
   │     │
   │     ├─ TutorEngine.submit()                    src/tutor/hints.py
   │     │     │
   │     │     ├─ normalize_student_answer()        src/verify/base.py
   │     │     │     bỏ dấu câu cuối, đổi "0,7" → "0.7" khi đề hỏi một số
   │     │     │
   │     │     ├─ Verifier.verify()                 src/verify/registry.py
   │     │     │     ├─ check_steps()   từng bước có tương đương bước trước?
   │     │     │     ├─ check()         đáp án cuối, theo answer_type
   │     │     │     └─ diagnose()      suy ra MÃ LỖI từ bản chất sai lệch
   │     │     │
   │     │     ├─ HintPolicy.next_level()           src/tutor/hint_policy.py
   │     │     └─ sinh gợi ý (template hoặc LLM) → guardrail
   │     │
   │     ├─ store.record_attempt()                  luôn ghi, kể cả khi None
   │     ├─ tracker.observe()          ⚠ CHỈ khi có kết luận (xem 1.1)
   │     └─ propagate_prerequisites()  làm đúng thì kéo tăng kỹ năng tiên quyết
   │
   └─ AttemptResponse (KHÔNG chứa đáp án)
```

Hai chỗ hay sai khi sửa:

- **`record_attempt` luôn chạy, `tracker.observe` thì không.** Bài không đọc được vẫn
  phải lưu (để cải thiện bộ đọc), nhưng không được đụng tới mô hình năng lực.
- **Chuẩn hoá đáp án đặt ở HAI chỗ**: `Verifier.verify` và `Verifier.check_final_answer`.
  Vì `CalculusVerifier` tự viết lại `verify` và gọi thẳng vào hàm sau — đặt một chỗ thì
  môn có ngân hàng đề lớn nhất lại là môn duy nhất không được chuẩn hoá.

---

## 4. Muốn thêm thứ gì thì sửa ở đâu

### 4.1. Thêm một MÔN mới

1. Thêm vào `Subject` trong `src/core/schema.py`.
2. Viết `data/skills/<môn>.json` (kỹ năng + chương + tiên quyết) và
   `data/errors/<môn>.json` (bảng mã lỗi).
3. Chọn các bộ chấm cần ghép rồi đăng ký ở `src/verify/registry.py`. Dùng lại được thì
   dùng lại — MAE101 và MAI391 chung `LinearAlgebraVerifier`.
4. Dịch tên chương sang tiếng Việt ở `CHAPTER_NAMES_VI` trong `src/core/syllabus.py`.
5. Viết `src/data_gen/<môn>_items.py` theo mẫu các file cùng loại, rồi thêm vào
   `GENERATORS` trong `scripts/build_bank.py`.

Mọi tầng phía trên chỉ gọi `verifier_for`, nên **không phải sửa tutor engine, guardrail
hay API**. Nếu port một môn mới mà phải sửa những chỗ đó thì tức là trừu tượng đang hở —
đáng dừng lại xem lại.

Có test chốt điều này: `test_syllabus.py` quét mọi môn, mọi chương, mọi bài, và đỏ nếu
còn nhánh không có đề.

### 4.2. Thêm một MÃ LỖI mới

Bốn việc, thiếu việc nào thì mã lỗi đó thành vô dụng theo cách im lặng:

1. **Khai báo** trong `data/errors/<môn>.json`: `code`, `tier`, `skill_id`, `name_vi`,
   `description_vi`, `hint_vi`.
2. **Bộ sinh lỗi** trong `src/data_gen/error_injector.py` (hoặc `*_errors.py`): hàm nhận
   `Item`, trả về chuỗi đáp án sai, hoặc `None` nếu bộ tham số này không sinh được lỗi
   đó.
3. **Luật chẩn đoán** trong verifier của môn, hàm `diagnose()`. Cách đáng tin nhất là
   **dựng lại đúng đáp án mà lỗi đó sẽ cho ra** rồi so — không so khớp mẫu trên chuỗi.
4. **Chạy lại** `python scripts/build_error_dataset.py <môn>` và xem cột *gán đúng mã*.

Thiếu việc 3 thì bộ chấm nhận ra bài sai nhưng không gọi được tên lỗi, và tỉ lệ gán
đúng mã **tụt** — đã xảy ra: thêm 8 mã lỗi mới làm MAE101 rơi từ 97,2% xuống 78,8% cho
tới khi viết đủ luật chẩn đoán.

**Một mã lỗi phải PHÂN BIỆT ĐƯỢC từ đáp án cuối.** `MAE.LIM.NOSIMPLIFY` đã bị bỏ vì ở
dạng 0/0 nó cho ra đúng `0`, trùng khít `MAE.LIM.INDET_ZERO`. Lỗi mức BƯỚC thì phải đo
qua chuỗi bước, không đo qua đáp án.

### 4.3. Thêm một DẠNG BÀI mới

Thêm một hàm có `@template(...)` trong `src/data_gen/<mảng>_items.py`:

```python
@template("ten_dang", ["MA.KY.NANG"], 0.45, "Tên tiếng Việt của dạng")
def _ten_dang(rng: random.Random):
    ...
    return draft(meta, statement_vi, answer, "number")
```

Bốn điều cần để ý:

- **`method_vi` (tham số thứ tư) là tên hiện cho người học** trong bộ chọn dạng bài.
  Thiếu nó thì giao diện hiện mã trần kiểu `logic_negate`.
- **Trả `None`** khi bộ tham số vừa gieo không dùng được (ma trận suy biến, xác suất
  > 1, thương là hằng số...). Khung sẽ gieo lại.
- **Đề phải thật sự cần kỹ năng nó khai báo.** Bài dán nhãn "quy tắc hàm hợp" mà giải
  được bằng công thức lũy thừa sẽ làm mô hình năng lực ghi nhận một kỹ năng sinh viên
  chưa hề dùng — sai lặng lẽ. `test_calculus_items.py` có test chốt điều kiện này.
- **Số phải đẹp.** Gieo tham số bừa thì đáp án ra phân số lạ và đề thành bài bấm máy.
  Cách làm: dựng ngược từ đáp án đã chọn (`(x−a)(x−b)/(x−a)`, `A = P·D·P⁻¹`).

Hàng rào duy nhất là verifier tự chấm lại đề vừa sinh — và nó đủ.

### 4.4. Thêm thuật ngữ cho phần hỏi đáp

`src/rag/glossary.py` có **hai bảng, hai chiều, hai mục đích khác nhau**:

| Bảng | Chiều | Dùng để |
|---|---|---|
| `TERMS` | Việt → Anh | mở rộng truy vấn, để BM25 khớp được vào giáo trình tiếng Anh |
| `TERM_PINS` | Anh → Việt | nhồi vào prompt, buộc model dùng đúng cách gọi tiếng Việt |

Thiếu `TERMS` thì truy xuất lệch chủ đề. Thiếu `TERM_PINS` thì truy xuất đúng mà model
dịch sai thuật ngữ — và **dịch sai nguy hiểm hơn dịch lủng củng**, vì câu vẫn đọc trôi
nên sinh viên học vào đúng cái sai.

Phần lớn `TERMS` **không phải viết tay**: 70 kỹ năng trong `data/skills` đã có cả
`name_vi` lẫn `name_en`, và `_table()` gộp chúng vào tự động.

Thêm xong thì chạy `python scripts/exp4b_ask_quality.py --compare`.

### 4.5. Thêm một ENDPOINT

Sửa `src/api/app.py`. Hai việc dễ quên:

- Nghiệp vụ đặt ở `TutorService` (không dính HTTP), route chỉ gọi và đổi lỗi thành
  `HTTPException`. Nhờ vậy test được mà không cần dựng server.
- Endpoint trả dữ liệu đề thì **phải qua `PublicItem`**, không trả `Item` thẳng.

---

## 5. Những chỗ dễ sập, và vì sao

Ghi lại để không ai sửa lại thành cũ.

| Chỗ | Chuyện gì đã xảy ra |
|---|---|
| `sp.together()` | **rút gọn phân thức**, biến `(x²+2x)/(x+2)` thành `x` và làm biến mất cấu trúc 0/0. Dùng `sp.fraction()` để tách tử/mẫu |
| `_fusion_mode` | tự chọn dense cho truy vấn tiếng Việt. Sau khi mở rộng truy vấn bằng thuật ngữ tiếng Anh thì quy tắc đó **sai** — `/ask` phải nói rõ `fusion="hybrid"` |
| CORS | thiếu `CORSMiddleware` thì web dựng ra đầy đủ mà **không nút nào chạy**, và **cả bộ test vẫn xanh** vì `TestClient` không thi hành same-origin policy |
| `setdefault` khi gom tên | chốt luôn tên đầu tiên gặp. Đề chép tay không có `method` nên cả danh sách dạng bài hiện ra mã trần |
| Nhãn chương | trong kho là tiêu đề PDF (`Graph Theory`), trong `data/skills` là `Ch6 Graph Theory`. So chuỗi thẳng thì **3 trong 4 môn báo thiếu toàn bộ** |
| Từ chối theo chương | phụ thuộc nhãn chương. Kho nạp mà quên gắn nhãn thì **mọi** câu hỏi bị trả "chưa có tài liệu" — nên chỉ kết luận thiếu khi thấy chương KHÁC có nhãn hẳn hoi |
| `capsys.disabled()` | in tiếng Việt thẳng ra console. Chạy test trong terminal cp1252 là `UnicodeEncodeError` — **bộ test đổ vì cái terminal** |
| API nạp dữ liệu | một lần lúc khởi động. Dựng lại đề mà không khởi động lại API thì `/syllabus` vẫn trả số cũ |
| Timeout SymPy | `signal.alarm` không có trên Windows. `run_with_timeout` dùng daemon thread và **bỏ mặc** thread quá hạn — đánh đổi có chủ ý, ghi rõ tại chỗ |

---

## 6. Chạy test

```bash
python -m pytest -q                       # 784 test, ~60–120 giây
python -m pytest tests/test_verify_calculus.py -q
python -m pytest -q -k "Syllabus or Admin"
set PYTHONIOENCODING=utf-8                # nếu terminal không đọc được tiếng Việt
```

Bộ test **không cần GPU, không cần mạng, không cần model**. Mọi thứ phụ thuộc bên ngoài
đều có bản giả.

Test quan trọng nhất là `tests/test_error_injector*.py`: mọi lời giải sai do
`error_injector` sinh ra **phải bị bắt đúng bước, đúng mã lỗi**, và mọi lời giải chuẩn
**phải luôn pass**.

### Viết test thế nào cho đúng tinh thần dự án

- **Chốt hành vi kèm lý do.** Docstring nói *vì sao* test này tồn tại, không nói nó làm
  gì — đọc code là biết nó làm gì.
- **Thử cả nhánh đỏ.** Script kiểm mà chỉ thử nhánh xanh thì vô dụng đúng lúc cần nhất.
- **Phép đo cũng phải bị nghi ngờ.** Đã có hai lần phép đo cho kết quả sai: một lần báo
  "3 trong 4 môn thiếu toàn bộ giáo trình" (lỗi khớp tên chương), một lần chấm model 3b
  và 7b bằng nhau trong khi 3b sai nặng về nghĩa (chỉ đếm từ khoá). **Đếm từ khoá không
  thay được đọc tay.**

---

## 7. Số liệu phải tái lập được

Mọi bảng trong báo cáo **sinh từ script, không gõ tay**:

```bash
python scripts/make_report_tables.py      # experiments/*.json → docs/results.md
```

Thêm một thí nghiệm thì thêm một hàm `table_expN()` và một dòng trong `sections`.

**Một cái bẫy về phương pháp, đáng đọc trước khi thêm phép đo mới.** EXP-4 sinh câu hỏi
từ `skill.name_vi` và tính nhãn đúng bằng `skill.name_en`; từ điển thuật ngữ cũng suy ra
từ đúng cặp đó. Dùng EXP-4 để đo từ điển là **đo vòng tròn** — truy vấn được dịch thành
đúng cái nhãn đang tìm, Recall vọt lên gần 1 mà không nói gì về chất lượng thật. Vì vậy
mới có EXP-4b với bộ câu hỏi viết tay độc lập.

Trước khi thêm một phép đo, tự hỏi: **dữ liệu đầu vào và nhãn đúng có chung nguồn gốc
không?**
