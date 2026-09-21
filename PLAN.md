AI Tutor for Mathematics Learning (MAE101 / MAD101 / MAI391 / MAS291)

## Context

 Xây dựng hệ thống gia sư toán ảo cho **sinh viên đại học**, phủ 4 môn toán nền tảng (mã môn FPT University):

| Mã | Tên môn | Nội dung chính |
|---|---|---|
| MAE101 | Mathematics for Engineering | Giới hạn, đạo hàm, tích phân, ứng dụng, chuỗi |
| MAD101 | Discrete Mathematics | Logic, tập hợp, tổ hợp, số học, quan hệ, đồ thị, hệ thức truy hồi |
| MAI391 | Advanced Mathematics | Đại số tuyến tính (ma trận, định thức, trị riêng), phương trình vi phân |
| MAS291 | Statistics & Probability | Xác suất, biến ngẫu nhiên, phân phối, ước lượng, kiểm định, hồi quy |


**Đóng góp cốt lõi của đồ án (3 trụ):**
1. **Neuro-symbolic verification** — mỗi bước biến đổi và mỗi đáp án đều được kiểm chứng độc lập bằng SymPy / NetworkX / SciPy / Monte Carlo, không tin LLM.
2. **Socratic hint ladder** — gợi ý phân tầng 5 mức, không lộ đáp án sớm, dựa trên chẩn đoán *bước sai đầu tiên* và *loại lỗi*.
3. **Knowledge tracing + adaptive selection** — mô hình hóa năng lực theo ~80 kỹ năng con trên 4 môn, chọn bài tiếp theo trong vùng phát triển gần nhất.

**Kết quả kỳ vọng:** web app (FastAPI + Next.js) + Telegram bot, chạy hoàn toàn trên model mã nguồn mở local, kèm bộ số liệu thực nghiệm có baseline và ablation.

### Quyết định kiến trúc đã chốt

| Quyết định | Lựa chọn | Hệ quả lên plan |
|---|---|---|
| Phạm vi | Cả 4 môn, mỗi môn vài chương | Cần 4 verification engine riêng → Phần D là phần nặng nhất |
| LLM | Chỉ model mã nguồn mở, chạy local | Phần C (serving) trở thành rủi ro kỹ thuật số 1, phải có 3 lớp fallback |
| GPU | Colab / Kaggle free (T4 16GB) | Model tối đa ~8B ở 4-bit; train phải checkpoint liên tục |
| Sản phẩm | Web app + Telegram bot | Frontend + bot chiếm thời gian thật, chỉ làm sau khi Gate 2 xong |

---

## Kiến trúc hệ thống

```
┌─────────────┐   ┌──────────────────┐
│  Next.js    │   │  Telegram Bot    │   ← 2 kênh, chung 1 API
│  Web app    │   │  (aiogram)       │
└──────┬──────┘   └────────┬─────────┘
       └────────┬──────────┘
                ▼
     ┌──────────────────────────┐
     │   FastAPI  Orchestrator  │
     │  (session, routing, log) │
     └───┬──────┬──────┬────────┘
         │      │      │
         │      │      └──────────────────────────┐
         │      │                                 │
         ▼      ▼                                 ▼
┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ M1 Understand  │  │ M3 Tutor Engine  │  │ M5 Student Model │
│ - phân loại môn│  │ - chẩn đoán lỗi  │  │ - BKT / DKT/SAKT │
│ - nhận skill   │  │ - hint ladder 5  │  │ - mastery vector │
│ - parse LaTeX  │  │   mức            │  │        │         │
└───────┬────────┘  └────┬────────┬────┘  └────────┼─────────┘
        │                │        │                ▼
        ▼                │        ▼       ┌──────────────────┐
┌────────────────┐       │  ┌──────────┐  │ M6 Item Selector │
│ M2 Solver      │◄──────┘  │ M4 RAG   │  │ - ZPD targeting  │
│ LLM + tool-use │          │ giáo trình│  │ - Q-matrix       │
└───────┬────────┘          └──────────┘  └──────────────────┘
        ▼
┌───────────────────────────────────────────┐
│ M2b VERIFIER  (lõi neuro-symbolic)        │
│  MAE → SymPy calculus                     │
│  MAD → sympy.logic + ntheory + networkx   │
│  MAI → sympy.Matrix + dsolve/checkodesol  │
│  MAS → sympy.stats + scipy + Monte Carlo  │
└───────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────┐
│ LLM Serving: vLLM trên Kaggle + tunnel     │
│ fallback → Ollama local → cached demo mode │
└────────────────────────────────────────────┘
        │
        ▼   PostgreSQL / SQLite: users, items, attempts, hints, mastery
```

---

## Cấu trúc thư mục

```
F:\Deep learning\
├── data/
│   ├── raw/                  # giáo trình, đề thi, slide gốc (4 môn)
│   ├── items/                # ngân hàng bài tập JSONL, 1 file / môn
│   ├── skills/               # skill taxonomy + Q-matrix
│   ├── errors/               # error taxonomy + tập lỗi có nhãn
│   ├── kt/                   # ASSISTments, EdNet, log mô phỏng
│   └── sft/                  # dữ liệu fine-tune LoRA
├── src/
│   ├── core/                 # config, schema (pydantic), logging
│   ├── llm/                  # client, prompt template, tool-calling loop
│   ├── verify/
│   │   ├── base.py           # interface chung Verifier
│   │   ├── calculus.py       # MAE101
│   │   ├── discrete.py       # MAD101
│   │   ├── linalg_ode.py     # MAI391
│   │   ├── probstat.py       # MAS291
│   │   └── equivalence.py    # so sánh biểu thức: symbolic + numeric sampling
│   ├── tutor/                # chẩn đoán lỗi, hint ladder, guardrail
│   ├── rag/                  # ingest, chunk, embed, retrieve, rerank
│   ├── kt/                   # bkt.py, dkt.py, sakt.py, selector.py
│   ├── api/                  # FastAPI routes, session, DB
│   └── bot/                  # Telegram
├── notebooks/                # EDA, train KT, train LoRA, phân tích kết quả
├── experiments/              # config + kết quả từng thí nghiệm
├── web/                      # Next.js
├── tests/
└── docs/                     # đặc tả, báo cáo, slide
```

---

# PHẦN A — Đặc tả & Taxonomy (nền móng, làm trước mọi thứ)

Đây là phần quyết định chất lượng cả đồ án. Làm cẩu thả ở đây thì mọi module sau đều sai.

## A1. Chốt phạm vi chương cho từng môn

Không ôm hết syllabus. Mỗi môn chọn **3–4 chương** có tính "kiểm chứng được bằng máy" cao nhất:

| Môn | Chương chọn | Lý do |
|---|---|---|
| MAE101 | Giới hạn & liên tục; Đạo hàm & ứng dụng; Tích phân (bất định, xác định, đổi biến, từng phần) | SymPy phủ 100%, bài tập nhiều |
| MAD101 | Logic mệnh đề & vị từ; Tổ hợp (hoán vị, chỉnh hợp, tổ hợp, inclusion–exclusion); Hệ thức truy hồi; Đồ thị cơ bản (bậc, Euler, Hamilton, cây, tô màu) | Có `sympy.logic`, `rsolve`, `networkx` + brute-force đối chứng |
| MAI391 | Ma trận & hệ phương trình tuyến tính (Gauss, rref, nghịch đảo, hạng); Không gian vector (độc lập tuyến tính, cơ sở); Trị riêng & chéo hóa; ODE cấp 1 và cấp 2 hệ số hằng | `sympy.Matrix` + `dsolve` + `checkodesol` (SymPy có sẵn hàm **kiểm chứng nghiệm ODE**) |
| MAS291 | Xác suất cơ bản & Bayes; Biến ngẫu nhiên rời rạc/liên tục & phân phối chuẩn tắc; Ước lượng khoảng tin cậy; Kiểm định giả thuyết 1–2 mẫu | `scipy.stats` + **Monte Carlo** làm verifier độc lập thứ 2 |

**Loại trừ rõ ràng (ghi vào báo cáo phần Limitations):** chứng minh hình thức tự do (MAD101), chuỗi Fourier, tích phân bội, ANOVA nhiều nhân tố.

## A2. Skill taxonomy (Knowledge Component)

Mỗi môn ~15–25 skill, tổng ~70–90 skill. Schema thống nhất:

```json
{
  "skill_id": "MAE.INT.SUBST",
  "subject": "MAE101",
  "chapter": "Integration",
  "name_vi": "Tích phân bằng phương pháp đổi biến",
  "name_en": "Integration by substitution",
  "prerequisites": ["MAE.DER.CHAIN", "MAE.INT.BASIC"],
  "difficulty_base": 0.55,
  "bloom_level": "apply"
}
```

**Đầu ra A2:** `data/skills/skills.json` + **đồ thị tiên quyết (prerequisite DAG)** vẽ bằng NetworkX. Đồ thị này dùng lại ở Phần G (cold-start cho mastery) và hiển thị trên dashboard.

## A3. Error taxonomy — điểm khác biệt học thuật

Đây là thứ hội đồng sẽ hỏi. Xây bảng phân loại lỗi 2 tầng:

**Tầng 1 — nhóm lỗi (chung 4 môn):**
- `E-CONCEPT` — hiểu sai khái niệm/định nghĩa
- `E-PROCEDURE` — nhớ sai/áp dụng sai quy trình, công thức
- `E-COMPUTE` — sai số học, sai dấu, sai đại số thuần
- `E-CONDITION` — bỏ qua điều kiện áp dụng (mẫu ≠ 0, ma trận khả nghịch, giả định phân phối chuẩn, n đủ lớn)
- `E-INTERPRET` — đọc sai đề, kết luận không trả lời đúng câu hỏi
- `E-INCOMPLETE` — thiếu trường hợp, thiếu bước, thiếu kết luận

**Tầng 2 — lỗi cụ thể theo skill.** Ví dụ mẫu:

| Mã lỗi | Môn | Mô tả | Cách phát hiện tự động |
|---|---|---|---|
| `MAE.INT.SUBST.NODX` | MAE | Đổi biến nhưng quên đổi `dx` | So khớp mẫu biểu thức sau đổi biến |
| `MAE.INT.DEF.NOLIMIT` | MAE | Tích phân xác định nhưng không đổi cận | Cận trước/sau giống hệt nhau |
| `MAD.COMB.ORDER` | MAD | Dùng tổ hợp khi đề yêu cầu chỉnh hợp (nhầm có/không thứ tự) | Đáp án = C(n,k) trong khi đúng là A(n,k) |
| `MAD.LOGIC.CONVERSE` | MAD | Nhầm mệnh đề đảo với mệnh đề phản đảo | Bảng chân trị lệch đúng ở vị trí đặc trưng |
| `MAI.EIG.NORM` | MAI | Tìm đúng vector riêng nhưng sai khi chuẩn hóa / thiếu bội | So hạng của không gian riêng |
| `MAI.ODE.NOHOMO` | MAI | Giải nghiệm riêng nhưng quên nghiệm thuần nhất | `checkodesol` fail + thiếu hằng số C |
| `MAS.HYP.TAIL` | MAS | Dùng kiểm định 1 phía khi đề là 2 phía (hoặc ngược lại) | p-value lệch đúng hệ số 2 |
| `MAS.PROB.INDEP` | MAS | Giả định độc lập sai khi tính xác suất giao | Monte Carlo lệch có hệ thống |

**Cách xây:** (1) trích từ đáp án sai phổ biến trong đề thi/bài kiểm tra cũ; (2) đọc literature về misconception; (3) **sinh lỗi có chủ đích bằng code** — viết `error_injector.py` biến lời giải đúng thành lời giải sai theo đúng mã lỗi (đây là nguồn dữ liệu huấn luyện chính, nhãn sạch 100%).

**Mục tiêu:** ≥ 12 mã lỗi cụ thể / môn, tổng ≥ 50.

## A4. Tiêu chí đánh giá (chốt trước khi code)

Viết sẵn bảng này vào `docs/evaluation-protocol.md` để không bị "đánh giá cho có" về sau:

| Trục | Chỉ số | Baseline để so |
|---|---|---|
| Giải đúng | Accuracy theo môn | LLM thuần (no tool) |
| Kiểm chứng | Precision/Recall phát hiện bước sai | Rule-based đơn giản |
| Chẩn đoán lỗi | Macro-F1 phân loại mã lỗi | Prompting zero-shot |
| Chất lượng gợi ý | Rubric 4 trục (1–5) | Trả lời đáp án trực tiếp |
| Knowledge tracing | AUC, ACC | Chọn bài ngẫu nhiên |
| Người dùng | Learning gain, SUS | Nhóm đối chứng |

---

# PHẦN B — Dữ liệu

## B1. Ngân hàng bài tập (`data/items/`)

Schema mỗi item:

```json
{
  "item_id": "MAI391-EIG-0042",
  "subject": "MAI391",
  "skills": ["MAI.EIG.CHARPOLY", "MAI.EIG.VECTOR"],
  "statement_vi": "Tìm trị riêng và vector riêng của ma trận A = [[2,1],[1,2]]",
  "statement_latex": "A = \\begin{pmatrix}2&1\\\\1&2\\end{pmatrix}",
  "sympy_repr": "Matrix([[2,1],[1,2]])",
  "answer": {"eigenvalues": [1, 3], "eigenvectors": [[1,-1],[1,1]]},
  "answer_type": "set_of_pairs",
  "reference_solution_steps": [
    {"step": 1, "skill": "MAI.EIG.CHARPOLY", "expr": "det(A - lambda*I) = 0", "explain_vi": "..."},
    {"step": 2, "skill": "MAI.EIG.CHARPOLY", "expr": "lambda**2 - 4*lambda + 3 = 0", "explain_vi": "..."}
  ],
  "difficulty": 0.45,
  "source": "textbook|exam|generated",
  "verifier": "linalg_ode.verify_eigen"
}
```

**3 nguồn item:**
1. **Thủ công** — số hoá từ giáo trình + đề thi cũ. Mục tiêu 40–60 item/môn. Đây là tập **test chất lượng cao**.
2. **Sinh theo template có tham số** — `item_generator.py`: mỗi skill có 2–4 template, random hoá hệ số, dùng SymPy tự sinh luôn lời giải chuẩn theo bước. Đây là nguồn **train / KT / adaptive**, sinh được hàng nghìn item gần như miễn phí. *Đây là kỹ thuật quan trọng nhất của Phần B — hãy làm sớm.*
3. **Dataset công khai (tiếng Anh)** — MATH, GSM8K (MAE), ProofNet, các bộ linear algebra/statistics trên HuggingFace. Dùng để so sánh với literature và pretrain; **không dịch máy hàng loạt**, chỉ dịch tập nhỏ có rà soát tay.

## B2. Tập lỗi có nhãn (`data/errors/`)

- Chạy `error_injector.py` trên item đã có lời giải chuẩn → sinh `(lời giải sai, mã lỗi, vị trí bước sai)`.
- Mỗi mã lỗi ≥ 100 mẫu → tổng ~5.000+ mẫu nhãn sạch.
- Bổ sung **lỗi thật**: thu bài làm sai thật từ bạn bè/lớp (ảnh chụp hoặc gõ tay), gán nhãn tay ~200 mẫu → dùng làm **tập test thật** (quan trọng: chứng minh model không chỉ giỏi trên lỗi tổng hợp).
- Chia: train/val trên lỗi tổng hợp, test trên lỗi thật + tập tổng hợp held-out.

## B3. Kho tri thức RAG (`data/raw/` → vector store)

- Nguồn: slide giảng dạy, giáo trình, tóm tắt công thức, ví dụ mẫu — cả 4 môn.
- **Chunking theo cấu trúc, không theo độ dài cố định**: mỗi chunk = 1 định nghĩa / 1 định lý / 1 công thức / 1 ví dụ có lời giải.
- Metadata bắt buộc mỗi chunk: `{subject, chapter, skill_ids[], type: definition|theorem|formula|example|pitfall}`.
- **Bảng "bẫy thường gặp" (pitfall)** viết tay theo error taxonomy — hint mức 2 sẽ truy xuất trực tiếp từ đây.

## B4. Dữ liệu knowledge tracing (`data/kt/`)

- **Public**: ASSISTments 2009/2017, EdNet-KT1 → pretrain DKT/SAKT, báo cáo AUC so với literature.
- **Mô phỏng**: `student_simulator.py` — sinh học sinh ảo theo mô hình IRT/BKT (mỗi học sinh có vector năng lực ẩn, xác suất đúng theo `sigmoid(θ_skill − b_item)`, có slip/guess, có học tập sau mỗi lần thử). Dùng để **test vòng lặp adaptive** trước khi có người dùng thật.
- **Thật**: log từ web app + Telegram bot, thu qua Phần L.

---

# PHẦN C — LLM Serving (rủi ro kỹ thuật số 1, làm sớm)

Vì ràng buộc "chỉ open-source + Colab free", đây là chỗ dễ vỡ nhất. Thiết kế **3 lớp**, code luôn gọi qua một interface OpenAI-compatible duy nhất để đổi backend mà không sửa app.

## C1. Chọn model

| Vai trò | Model đề xuất | Ghi chú |
|---|---|---|
| Solver chính | **Qwen2.5-Math-7B-Instruct** (AWQ/GPTQ 4-bit ≈ 5.5GB) | Mạnh nhất về toán ở cỡ này, hỗ trợ tool-integrated reasoning |
| Đối thoại tiếng Việt | **Qwen2.5-7B-Instruct** hoặc **Qwen3-4B-Instruct** | Tiếng Việt tốt hơn bản Math |
| Dự phòng nhẹ | **Qwen2.5-1.5B-Instruct** / **Qwen3-1.7B** | Chạy được CPU, dùng cho demo offline |
| Embedding | **BAAI/bge-m3** hoặc **multilingual-e5-base** | Đa ngôn ngữ, tốt cho VI+EN |
| Reranker | **bge-reranker-v2-m3** | Bật nếu retrieval chưa đủ chính xác |

**Kiến trúc 2 model (khuyến nghị):** Math model lo *suy luận và sinh lời giải* (prompt tiếng Anh, chất lượng toán cao nhất) → chat model lo *diễn đạt gợi ý sang tiếng Việt sư phạm*. Tách vai trò này còn giúp ablation rõ ràng và là một điểm nói được khi bảo vệ.

## C2. Ba lớp triển khai

1. **Chính — Kaggle Notebook + vLLM + Cloudflare Tunnel.** Kaggle cho 2×T4 (30h/tuần), ổn định hơn Colab free. vLLM expose endpoint OpenAI-compatible, tunnel ra URL public, FastAPI trỏ vào URL đó qua biến môi trường.
2. **Fallback — Ollama trên máy local.** `qwen2.5:1.5b` / `qwen3:1.7b` quantized q4. Chậm trên CPU nhưng **luôn chạy**, không phụ thuộc mạng. Bắt buộc phải có cho buổi bảo vệ.
3. **Demo mode — cache.** Middleware cache mọi `(prompt hash → response)` vào SQLite trong lúc phát triển. Khi bảo vệ, bật `DEMO_MODE=1` để replay tức thì cho bộ ví dụ đã chuẩn bị. **Ghi rõ trong báo cáo là cache, không giấu.**

## C3. Interface thống nhất

`src/llm/client.py` — một lớp `LLMClient` với `generate()`, `chat()`, `tool_call()`; backend chọn bằng config (`vllm` | `ollama` | `cache`). Kèm: retry + timeout + đo latency/token để lấy số liệu hiệu năng cho báo cáo.

---

# PHẦN D — Verification Engine (lõi kỹ thuật, phần nặng nhất)

## D0. Nền chung — `verify/equivalence.py`

Hàm so sánh hai biểu thức, dùng cho cả 4 môn, theo thứ tự thử:
1. `simplify(a - b) == 0`
2. `a.equals(b)`
3. **Numeric sampling** — thay ngẫu nhiên 20–50 bộ giá trị biến (tránh điểm kỳ dị), so sánh với dung sai. *Đây là chốt chặn quan trọng: `simplify` có thể treo hoặc trả sai với biểu thức phức tạp; sampling thì nhanh và gần như không bao giờ nhầm.*
4. So khớp theo loại đáp án: tập hợp (không thứ tự), khoảng, ma trận, phân số, có/không hằng số tích phân `C`.

Kèm: **timeout guard** (mọi lời gọi SymPy bọc trong giới hạn thời gian) và chuẩn hoá LaTeX ↔ SymPy (`parse_latex`, có sửa tay các ký hiệu tiếng Việt hay gặp).

## D1. `verify/calculus.py` — MAE101
- Giới hạn: `limit()` kể cả một phía, `oo`; phát hiện dạng vô định.
- Đạo hàm: `diff()`, kiểm tra từng quy tắc (tích, thương, chuỗi) có áp dụng đúng không.
- Tích phân: **so sánh bằng đạo hàm ngược** (`diff(student_answer) == integrand`) — mạnh hơn so khớp biểu thức, tự động chấp nhận mọi dạng tương đương; kiểm tra sự có mặt của `+C`.
- Tích phân xác định: kiểm tra đổi cận khi đổi biến.
- Kiểm tra bước: mỗi bước `expr_i` phải tương đương `expr_{i+1}` theo D0.

## D2. `verify/discrete.py` — MAD101
- **Logic**: `sympy.logic` — bảng chân trị, `satisfiable()`, tương đương qua `simplify_logic`. Kiểm tra chuyển đổi (De Morgan, đảo/phản đảo) đúng hay không.
- **Tổ hợp**: tính công thức đóng bằng SymPy **và** brute-force liệt kê với n nhỏ (`itertools`) → hai kết quả phải khớp. Đây là verifier độc lập rất thuyết phục.
- **Số học**: `sympy.ntheory` — gcd, nghịch đảo modulo, CRT, kiểm tra nguyên tố.
- **Truy hồi**: `rsolve()` giải nghiệm đóng + đối chứng bằng tính lặp n bước đầu.
- **Đồ thị**: `networkx` — bậc, liên thông, Euler/Hamilton, cây khung nhỏ nhất, số màu, đẳng cấu.
- **Chứng minh**: không verify tự động được → kiểm tra *cấu trúc* (quy nạp có đủ cơ sở + bước quy nạp? phản chứng có nêu giả thiết phản chứng?) + chấm rubric. Nêu thẳng đây là giới hạn.

## D3. `verify/linalg_ode.py` — MAI391
- Ma trận: `rref()`, `det()`, `inv()`, `rank()`, `nullspace()`, `columnspace()`.
- Hệ tuyến tính: `linsolve()`; kiểm tra nghiệm bằng **thế ngược** `A*x - b == 0` (đáng tin hơn so khớp dạng nghiệm).
- Độc lập tuyến tính / cơ sở: qua hạng ma trận.
- Trị riêng: `eigenvals()`, `eigenvects()`, `diagonalize()`; kiểm tra vector riêng bằng `A*v - λ*v == 0` (chấp nhận mọi bội vô hướng).
- **ODE**: `dsolve()` + **`checkodesol()`** — SymPy có sẵn hàm kiểm chứng nghiệm ODE, dùng nó thay vì so khớp chuỗi. Kiểm tra đủ hằng số tự do, kiểm tra điều kiện đầu.
- Kiểm tra bước Gauss: mỗi phép biến đổi sơ cấp có hợp lệ không (hoán vị hàng / nhân hằng ≠ 0 / cộng bội hàng).

## D4. `verify/probstat.py` — MAS291
- Xác suất: `sympy.stats` (`P`, `E`, `variance`, `density`) cho phần ký hiệu.
- Phân phối & kiểm định: `scipy.stats` — pdf/cdf/ppf, t-test, chi-square, z-test, khoảng tin cậy, hồi quy tuyến tính.
- **Monte Carlo verifier** — mô phỏng 10⁵–10⁶ lần để kiểm tra độc lập kết quả xác suất; so sánh với dung sai theo sai số chuẩn. *Điểm nhấn: hai verifier độc lập về bản chất (giải tích + mô phỏng) đồng thuận thì độ tin cậy rất cao.*
- **Kiểm tra điều kiện áp dụng** (đặc sản lỗi MAS291): n đủ lớn chưa? biết σ hay không (z hay t)? mẫu độc lập hay ghép cặp? 1 phía hay 2 phía? → sinh trực tiếp mã lỗi `E-CONDITION`.
- So sánh số: dung sai tương đối, có tính tới việc sinh viên làm tròn khi tra bảng.

## D5. Đầu ra chuẩn của Verifier

```json
{
  "item_id": "...",
  "is_correct": false,
  "first_wrong_step": 3,
  "step_results": [{"step": 1, "ok": true}, {"step": 2, "ok": true}, {"step": 3, "ok": false, "reason": "..."}],
  "final_answer_correct": false,
  "verifier_used": "probstat.hypothesis_test",
  "cross_check": {"analytic": 0.0384, "monte_carlo": 0.0381, "agree": true},
  "candidate_error_codes": ["MAS.HYP.TAIL"],
  "confidence": 0.91
}
```

Module sau (chẩn đoán lỗi, hint) **chỉ đọc object này**, không đọc lại raw LLM output → giữ được tính tin cậy toàn hệ thống.

---

# PHẦN E — RAG

- **Ingest**: PDF/slide → text (PyMuPDF), công thức giữ dạng LaTeX; chunk theo cấu trúc (B3).
- **Index**: FAISS hoặc Chroma; **hybrid search** = BM25 + dense embedding (bge-m3), hợp nhất bằng RRF. Toán có nhiều ký hiệu nên BM25 đóng góp thật, không phải làm cho có.
- **Lọc theo metadata**: truy vấn luôn kèm `subject` và `skill_ids` đang làm → thu hẹp không gian tìm, giảm mạnh nhiễu chéo môn.
- **Rerank** (tuỳ chọn): bge-reranker-v2-m3 trên top-20 → top-3.
- **Đánh giá riêng cho RAG**: tự tạo 100 cặp `(câu hỏi, chunk đúng)` → đo Recall@k, MRR. So 3 cấu hình: dense / BM25 / hybrid+rerank. **Đây là một bảng số liệu độc lập cho báo cáo.**

---

# PHẦN F — Tutor Engine (module sư phạm)

## F1. Chẩn đoán lỗi (2 tầng)

1. **Tầng symbolic** (nhanh, chắc chắn): Verifier chỉ ra bước sai đầu tiên + mã lỗi ứng viên qua luật so khớp mẫu.
2. **Tầng neural** (khi tầng 1 không kết luận được): phân loại mã lỗi bằng LLM prompting, và **bằng model fine-tune LoRA** (Phần H) → so sánh hai cách, đây chính là một thí nghiệm của đồ án.

Kết quả hợp nhất bằng luật ưu tiên: symbolic thắng khi confidence cao; neural chỉ lấp khoảng trống.

## F2. Hint ladder 5 mức

| Mức | Tên | Nội dung | Nguồn |
|---|---|---|---|
| 0 | Khơi gợi | "Em thử nói xem bài này cho gì và hỏi gì?" | Template |
| 1 | Nhắc khái niệm | Định nghĩa/công thức liên quan skill đang vướng | RAG (`type=definition/formula`) |
| 2 | Cảnh báo bẫy | "Chú ý: khi đổi biến thì `dx` cũng phải đổi" | RAG (`type=pitfall`) theo mã lỗi |
| 3 | Chỉ bước sai | "Bước 3 của em chưa đúng. Em kiểm tra lại dấu khi chuyển vế" | Verifier `first_wrong_step` |
| 4 | Sửa & giải thích | Sửa đúng bước đó + giải thích tại sao sai | LLM + Verifier |
| 5 | Lời giải đầy đủ | Toàn bộ lời giải theo bước | `reference_solution_steps` |

**Chính sách leo thang** (`hint_policy.py`, phải viết thành luật rõ ràng để ablation được):
- Mặc định vào mức 1 (hoặc 0 nếu chưa làm gì).
- Chỉ leo 1 mức mỗi lượt.
- Leo khi: sinh viên xin thêm, hoặc thử lại sai 2 lần liên tiếp cùng loại lỗi.
- **Không bao giờ nhảy thẳng mức 5** trừ khi yêu cầu rõ ràng 2 lần.
- Nếu mastery của skill đó cao → bắt đầu ở mức thấp hơn (giả định chỉ lỗi bất cẩn); nếu thấp → cho phép vào thẳng mức 1–2.

## F3. Guardrail

- **Chống lộ đáp án**: sau khi LLM sinh hint, chạy bộ kiểm tra — trích mọi biểu thức toán trong hint, nếu tương đương đáp án cuối (dùng D0) và mức hint < 4 → **từ chối, sinh lại**. Đây là kiểm tra tự động, đo được, và là một chỉ số trong bảng đánh giá.
- **Chống ảo giác**: mọi công thức trong hint mức 1–2 phải trích được từ chunk RAG (kèm nguồn).
- **Giọng điệu**: tiếng Việt, xưng hô phù hợp sinh viên, khích lệ, ≤ 4 câu cho mức 0–3.
- **Ngoài phạm vi**: câu hỏi không thuộc 4 môn/chương đã chốt → trả lời lịch sự là ngoài phạm vi, không cố đoán.

## F4. Quản lý hội thoại

State machine mỗi phiên: `PRESENT_ITEM → AWAIT_ATTEMPT → VERIFY → (CORRECT → NEXT_ITEM | WRONG → HINT_LEVEL_k) → AWAIT_RETRY → ...`
Lưu đầy đủ vào DB: item, attempt, verifier output, hint level, timestamp, mã lỗi. **Đây chính là dữ liệu cho Phần G và Phần L — thiết kế bảng đúng ngay từ đầu, đừng sửa sau.**

---

# PHẦN G — Student Model & Adaptive Selection

## G1. Ba mô hình, tăng dần độ phức tạp

1. **BKT** (baseline, giải thích được): 4 tham số/skill (`p_init, p_learn, p_slip, p_guess`), fit bằng EM. Ưu điểm: hiển thị được "mức thành thạo" cho người dùng hiểu.
2. **DKT** (LSTM/GRU, PyTorch): input = chuỗi `(skill_id, correct)` one-hot/embedding, output = xác suất đúng cho mọi skill ở bước kế.
3. **SAKT / AKT** (self-attention): bản mạnh hơn, so sánh với DKT.

**Quy trình huấn luyện thực tế với Colab free:**
- Pretrain trên ASSISTments/EdNet → báo cáo AUC, đối chiếu literature (chứng minh cài đặt đúng).
- Fine-tune / hiệu chỉnh trên log mô phỏng (B4) theo skill taxonomy của 4 môn.
- Cold-start cho người dùng mới: khởi tạo mastery từ **prerequisite DAG** (A2) + bài test đầu vào ngắn (5–8 câu adaptive).
- Checkpoint sau mỗi epoch vào Google Drive (Colab ngắt phiên bất ngờ).

**Lưu ý trung thực cho báo cáo:** số log người dùng thật sẽ nhỏ, không đủ train DKT từ đầu. Hãy nói rõ chiến lược là *pretrain trên public + mô phỏng*, và đánh giá adaptive loop chủ yếu trên học sinh mô phỏng. Đây là hạn chế hợp lý và hội đồng chấp nhận được — che giấu mới là vấn đề.

## G2. Bộ chọn bài (`selector.py`)

Điểm số cho mỗi item ứng viên:

```
score(item) = w1 · (1 − mastery_trung_bình_các_skill_của_item)      # ưu tiên skill yếu
            + w2 · ZPD(p_đúng_dự_đoán)                              # đỉnh tại p ≈ 0.75
            + w3 · sẵn_sàng_tiên_quyết(item)                        # từ DAG
            − w4 · phạt_lặp_lại(item)                               # tránh nhàm
```

Với `ZPD(p) = exp(−((p − 0.75)²) / 0.02)`.

**So sánh 4 chiến lược** (kết quả này là một bảng chính trong báo cáo): ngẫu nhiên / theo thứ tự giáo trình / chỉ skill yếu nhất / ZPD đầy đủ. Đo trên học sinh mô phỏng: số bài cần để đạt mastery ngưỡng, tỉ lệ đúng trung bình, mức độ chán (chuỗi sai liên tiếp).

---

# PHẦN H — Fine-tune LoRA (nâng chất lượng model nhỏ)

Với ràng buộc Colab free, đây là phần "deep learning tự làm" rõ nét nhất của đồ án.

## H1. Hai task fine-tune

**Task 1 — Phân loại mã lỗi** (ưu tiên cao, dễ thắng):
- Input: đề bài + lời giải sinh viên; Output: mã lỗi + vị trí bước sai.
- Data: ~5.000 mẫu từ B2.
- Base: Qwen2.5-1.5B/3B-Instruct, QLoRA 4-bit, r=16, batch nhỏ + gradient accumulation.
- So với: prompting zero-shot và few-shot trên chính model đó và trên model 7B. **Kỳ vọng: model 1.5B fine-tuned thắng model 7B prompting — đây là kết quả đẹp để bảo vệ.**

**Task 2 — Sinh hint tiếng Việt sư phạm** (nếu còn thời gian):
- Data: cặp `(ngữ cảnh lỗi → hint mức k)`; nguồn: viết tay ~300 mẫu chất lượng cao + chưng cất từ model 7B rồi lọc bằng guardrail F3.
- Đánh giá bằng rubric + LLM-as-judge.

## H2. Kỷ luật huấn luyện trên Colab/Kaggle free

- Dùng **Kaggle** cho các lần train dài (30h/tuần, ít ngắt hơn Colab).
- `save_steps` ngắn, checkpoint ra Drive/Kaggle dataset, script tự resume.
- Ghi mọi run bằng **W&B** hoặc MLflow — hội đồng thích thấy learning curve.
- Chạy ablation với seed cố định; báo cáo cả mean ± std nếu chạy được ≥ 3 seed.

---

# PHẦN I — Backend (FastAPI)

## I1. Schema DB

`users`, `sessions`, `items`, `skills`, `attempts` (item_id, user_id, raw_input, verifier_json, is_correct, ts), `hints` (attempt_id, level, text, source, leaked_flag), `mastery` (user_id, skill_id, value, updated_at), `feedback` (rating, comment).

## I2. Endpoints chính

| Method | Path | Chức năng |
|---|---|---|
| POST | `/session/start` | tạo phiên, chọn môn, chạy test đầu vào |
| GET | `/item/next` | selector trả bài kế tiếp |
| POST | `/attempt` | nhận bài làm → verifier → chẩn đoán lỗi → cập nhật mastery |
| POST | `/hint` | trả hint theo chính sách leo thang |
| POST | `/ask` | hỏi tự do về lý thuyết (RAG) |
| GET | `/progress` | mastery vector + lịch sử cho dashboard |
| GET | `/health` | trạng thái LLM backend đang dùng (vllm/ollama/cache) |

## I3. Lưu ý kỹ thuật

- Mọi lời gọi LLM và SymPy đều **async + timeout**; SymPy chạy trong process pool để timeout thật sự cắt được.
- Rate limit theo user (model local chậm, phải xếp hàng).
- Log có `request_id` xuyên suốt để debug và để xuất dữ liệu phân tích.

---

# PHẦN J — Frontend (Next.js)

- **Trang luyện tập**: đề bài render KaTeX; ô nhập hỗ trợ LaTeX (MathLive hoặc MathQuill) + nhập text thường; hint hiện dần theo mức (nút "Gợi ý thêm"); feedback đúng/sai có highlight **đúng bước sai**.
- **Trang tiến độ**: radar chart / heatmap mastery theo skill; đồ thị tiên quyết tô màu theo mức thành thạo; lịch sử lỗi hay mắc nhất.
- **Trang hỏi đáp lý thuyết**: chat RAG có trích dẫn nguồn.
- **Trang admin (nhẹ)**: xem log, xuất CSV cho phân tích.
- Khi dùng biểu đồ, giữ bảng màu nhất quán, có nhãn trục và chú giải rõ ràng — dashboard này sẽ lên slide bảo vệ.

---

# PHẦN K — Telegram Bot

Chọn Telegram thay vì Discord: API đơn giản hơn, render ảnh/công thức tiện, sinh viên Việt Nam dễ tham gia → **thu được người dùng thật cho Phần L**.

- Thư viện: `aiogram` (async, hợp với FastAPI).
- Lệnh: `/start`, `/subject`, `/practice`, `/hint`, `/progress`, `/explain <khái niệm>`, `/stop`.
- Công thức: render LaTeX → PNG (matplotlib hoặc `latex2png`) rồi gửi ảnh; kèm cả text để copy.
- Nhận ảnh bài làm viết tay → **để sau** (nằm trong "nếu còn sức", cần OCR toán như pix2tex/Nougat).
- Bot chỉ là **client mỏng** gọi API ở Phần I — không nhân bản logic. Nhờ vậy mọi log từ bot và web nằm chung một bảng, phân tích chung được.

---

# PHẦN L — Đánh giá & Thực nghiệm

## L1. Đánh giá offline (bắt buộc, làm được không cần người dùng)

| Thí nghiệm | Cấu hình so sánh | Chỉ số |
|---|---|---|
| **EXP-1** Độ chính xác giải toán | (a) LLM thuần (b) LLM + CoT (c) LLM + SymPy tool (d) + self-consistency k=5 | Accuracy theo từng môn |
| **EXP-2** Chất lượng verifier | verifier vs nhãn tay trên 200 bài làm thật | Precision/Recall/F1 phát hiện bước sai |
| **EXP-3** Phân loại lỗi | zero-shot / few-shot / LoRA-1.5B / LoRA-3B / 7B prompting | Macro-F1, per-class F1 |
| **EXP-4** RAG | dense / BM25 / hybrid+rerank | Recall@k, MRR |
| **EXP-5** Knowledge tracing | BKT / DKT / SAKT trên ASSISTments + mô phỏng | AUC, ACC |
| **EXP-6** Chiến lược chọn bài | random / tuần tự / skill yếu nhất / ZPD | Số bài đến mastery, tỉ lệ đúng TB |
| **EXP-7** Ablation toàn hệ | −SymPy / −RAG / −hint ladder / −KT | Accuracy + điểm rubric |
| **EXP-8** Chống lộ đáp án | có/không guardrail F3 | % hint bị rò đáp án (đo tự động) |

## L2. Đánh giá chất lượng hint

- **Rubric 4 trục, thang 1–5**: đúng về toán / không lộ đáp án / phù hợp sư phạm / tiếng Việt tự nhiên.
- **LLM-as-judge** chấm toàn bộ (dùng model mạnh làm giám khảo là chấp nhận được — giám khảo không phải sản phẩm; ghi rõ trong báo cáo).
- **Người chấm**: bạn + 1–2 người nữa chấm tay 100–150 mẫu → báo cáo **Cohen's kappa** giữa người với người và giữa người với LLM-judge. Con số này làm phần đánh giá đáng tin hẳn lên.

## L3. Thực nghiệm người dùng thật (quy mô nhỏ nhưng làm nghiêm túc)

- **Người tham gia**: 12–20 sinh viên đang/đã học các môn này, tuyển qua lớp và Telegram.
- **Thiết kế**: pre-test (8–10 câu) → 3–4 phiên luyện với hệ thống → post-test tương đương độ khó.
- **Nhóm đối chứng (A/B)**: nhóm A dùng hint ladder đầy đủ; nhóm B chỉ nhận đáp án + lời giải. So **learning gain chuẩn hoá** `(post − pre) / (max − pre)`.
- **Khảo sát**: SUS (10 câu) + 5 câu Likert riêng về chất lượng gợi ý + 2 câu mở.
- **Định tính**: phỏng vấn 3–5 người, trích dẫn vào báo cáo.
- Ghi rõ hạn chế: cỡ mẫu nhỏ, không ngẫu nhiên hoàn toàn, thời lượng ngắn → không suy rộng.

## L4. Phân tích lỗi (đừng bỏ qua — hội đồng rất thích phần này)

Lấy 50 ca hệ thống làm sai/gợi ý kém, phân loại nguyên nhân (parse sai đề / verifier không phủ / LLM sinh sai / RAG trả nhầm chunk / chính sách hint sai mức), lập bảng tần suất, rồi nêu hướng khắc phục cụ thể.

---

# PHẦN M — Báo cáo & Bảo vệ

## M1. Cấu trúc báo cáo

1. Mở đầu — bối cảnh, vấn đề, mục tiêu, đóng góp, phạm vi
2. Cơ sở lý thuyết & công trình liên quan — ITS, knowledge tracing, LLM cho toán, tool-augmented reasoning, RAG, Socratic tutoring
3. Phân tích yêu cầu & thiết kế hệ thống — use case, kiến trúc, DB
4. Xây dựng dữ liệu — taxonomy skill/lỗi, ngân hàng bài tập, sinh lỗi, RAG corpus
5. Phương pháp — verifier, tutor engine, knowledge tracing, fine-tuning
6. Cài đặt — công nghệ, serving, giao diện, bot
7. Thực nghiệm & đánh giá — EXP-1..8, rubric, người dùng, phân tích lỗi
8. Kết luận & hướng phát triển — hạn chế trung thực + đề xuất mở rộng

## M2. Chuẩn bị bảo vệ

- Slide ~20 trang: 1 slide/đóng góp, 1 slide kiến trúc, 3–4 slide kết quả, 1 slide hạn chế.
- **Quay video demo sẵn** (3–5 phút) — không bao giờ demo live phụ thuộc tunnel/mạng.
- Bộ 6–8 ví dụ đã kiểm tra kỹ (mỗi môn 2 ví dụ: 1 đúng, 1 sai có gợi ý hay), chạy sẵn ở `DEMO_MODE`.
- Chuẩn bị trả lời 5 câu hỏi chắc chắn bị hỏi:
  1. "Khác gì ChatGPT?" → neuro-symbolic verification + hint ladder + cá nhân hóa, có số liệu ablation chứng minh.
  2. "Sao không dùng GPT-4 cho nhanh?" → ràng buộc chi phí/chủ quyền dữ liệu; và đóng góp nằm ở kiến trúc, không ở model.
  3. "Làm sao biết gợi ý tốt?" → rubric + kappa + A/B learning gain.
  4. "Dữ liệu ít thế đánh giá sao đáng tin?" → pretrain public + mô phỏng + test trên lỗi thật, và nêu rõ giới hạn.
  5. "Mở rộng sang môn khác thế nào?" → chỉ cần thêm verifier module + skill taxonomy, kiến trúc không đổi (chính là lý do thiết kế `verify/base.py`).

---

# Cổng kiểm soát (gates) — cơ chế chống vỡ kế hoạch

Bạn chọn phạm vi rộng nhất. Để không rơi vào cảnh "4 môn đều dở dang", hãy đi theo **chiều sâu trước, chiều rộng sau**, và chỉ mở gate tiếp theo khi gate trước đã xong hẳn.

**Gate 0 — Xương sống (1 môn, 1 chương)**
MAE101 / Tích phân. Có: 20 item, verifier tích phân, LLM serving chạy được, hint 3 mức, CLI đơn giản. → *Chứng minh kiến trúc chạy được end-to-end.*

**Gate 1 — Hoàn chỉnh 1 môn**
MAE101 đủ 3 chương, error taxonomy, hint ladder 5 mức + guardrail, RAG, FastAPI, web app tối giản. → *Từ đây đã đủ một đồ án bảo vệ được, dù chỉ 1 môn.*

**Gate 2 — Nhân bản sang MAI391**
Môn gần MAE nhất về công cụ. Nếu port mất ít công → thiết kế trừu tượng tốt, ghi điều này vào báo cáo như một kết quả kỹ thuật.

**Gate 3 — Knowledge tracing + adaptive**
BKT → DKT/SAKT, selector, dashboard tiến độ. Chạy EXP-5, EXP-6.

**Gate 4 — MAD101 + MAS291**
Hai môn cần verifier khác hẳn. Nếu thiếu thời gian: **giảm xuống 2 chương/môn**, hoặc để chế độ "RAG hỏi đáp lý thuyết + bài trắc nghiệm" thay vì chấm bước.

**Gate 5 — Telegram bot + fine-tune LoRA + thực nghiệm người dùng**

**Gate 6 — Báo cáo, slide, video demo**

> **Quy tắc cắt phạm vi:** nếu phải hy sinh, hãy hy sinh theo thứ tự — (1) fine-tune Task 2, (2) chấm bước chi tiết cho MAD101/MAS291 (giữ chấm đáp án cuối), (3) SAKT (giữ BKT+DKT), (4) Telegram bot. **Tuyệt đối không hy sinh:** verifier, hint ladder, và phần thực nghiệm có baseline — đó là toàn bộ giá trị học thuật.

---

## Rủi ro & xử lý

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Colab/Kaggle ngắt giữa chừng khi train | Cao | Checkpoint ngắn, auto-resume, ưu tiên Kaggle cho run dài |
| Tunnel chết, không serve được LLM khi demo | Cao | 3 lớp fallback (C2), bắt buộc test Ollama + DEMO_MODE trước ngày bảo vệ |
| Model nhỏ nói tiếng Việt kém/sai thuật ngữ | Cao | Tách 2 model (math EN → chat VI), LoRA Task 2, template ràng buộc đầu ra |
| 4 verifier quá nhiều việc | Cao | Đi theo gate; MAD/MAS có thể chỉ chấm đáp án cuối |
| `simplify` treo hoặc sai | Trung bình | Numeric sampling + timeout ở D0 |
| Parse LaTeX/đầu vào sinh viên lỗi | Trung bình | Hỗ trợ cả LaTeX và text, có bước xác nhận lại đề với người dùng |
| Không đủ người dùng thật | Trung bình | Telegram bot + tuyển trong lớp; luôn có học sinh mô phỏng làm phương án chính |
| Không đủ dữ liệu train DKT | Trung bình | Pretrain public + mô phỏng; nêu rõ trong Limitations |
| Phình phạm vi | Cao | Gate cứng; không mở gate mới khi gate cũ chưa xong |

---

## Verification — cách kiểm chứng hệ thống chạy đúng

**Unit test (`tests/`)**
- `test_equivalence.py` — 50 cặp biểu thức tương đương/không tương đương, gồm ca khó (dạng khác nhau của cùng một nguyên hàm, có/không `+C`).
- `test_verify_<subject>.py` — mỗi verifier chạy trên toàn bộ item của môn đó, **lời giải chuẩn phải luôn pass**, và **mọi lời giải lỗi do `error_injector` sinh ra phải bị bắt đúng bước, đúng mã lỗi**. Đây là test quan trọng nhất của cả dự án.
- `test_hint_policy.py` — mô phỏng chuỗi lượt, kiểm tra không leo quá 1 mức/lượt, không nhảy thẳng mức 5.
- `test_guardrail.py` — hint mức ≤ 3 không được chứa biểu thức tương đương đáp án.

**Integration test**
- Chạy `pytest` cho toàn pipeline với backend LLM ở chế độ `cache` → test chạy nhanh, tất định, không cần GPU.
- Smoke test `/health` → xác nhận backend nào đang phục vụ.

**End-to-end thủ công (làm trước mỗi gate)**
1. Khởi động: vLLM trên Kaggle → lấy URL tunnel → set env → `uvicorn` → `npm run dev`.
2. Kịch bản A (làm đúng): chọn MAE101 → nhận bài → nhập lời giải đúng → hệ thống xác nhận đúng → mastery tăng → bài kế tiếp khó hơn.
3. Kịch bản B (làm sai): nhập lời giải có lỗi `MAE.INT.SUBST.NODX` → hệ thống chỉ đúng bước 2 sai, gợi ý mức 2 nhắc "đổi `dx`", **không lộ đáp án** → sửa đúng → xác nhận.
4. Kịch bản C (xin gợi ý liên tục): bấm "Gợi ý thêm" 5 lần → kiểm tra leo đúng mức 1→2→3→4→5, không nhảy cóc.
5. Kịch bản D (hỏi lý thuyết): "Định lý giới hạn trung tâm là gì?" → RAG trả lời kèm trích dẫn đúng chương MAS291.
6. Kịch bản E (ngoài phạm vi): hỏi về tích phân bội → từ chối lịch sự.
7. Lặp 2–6 trên Telegram bot → log phải ghi chung một bảng với web.
8. Ngắt tunnel → xác nhận tự động rơi về Ollama, hệ thống vẫn trả lời (chậm hơn).

**Kiểm chứng kết quả thực nghiệm**
- Mọi số trong báo cáo phải tái lập được bằng một script trong `experiments/` với seed cố định.
- Lưu config + kết quả thô (JSON) cho từng EXP; bảng trong báo cáo sinh từ script, không gõ tay.
