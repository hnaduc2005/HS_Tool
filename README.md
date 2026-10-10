# HS_Tool — HS Atlas: AI tra cứu mã HS có căn cứ

Ứng dụng MVP tra cứu mã HS bằng luồng **mô tả sản phẩm → AI tạo hướng tìm kiếm từ đặc tính hàng → tìm mã ứng viên trong Danh mục → tìm tài liệu bằng keyword + vector → AI áp dụng quy tắc/chú giải → kiểm tra mã và trích dẫn → lưu kết quả**. Mã do AI gợi ý ở bước tìm kiếm chỉ là giả thuyết; mã kết luận phải tồn tại trong Danh mục và có phân tích pháp lý được trích dẫn. Khi chưa tìm được mã ứng viên, hệ thống vẫn phân tích các quy tắc có nguồn rồi trả `INSUFFICIENT_EVIDENCE` cùng điểm cần đối chiếu.

> **DEMO DATA:** Seed và `docs/demo-knowledge.txt` chỉ minh họa luồng. Không phải tài liệu pháp lý. Phải thay bằng danh mục HS và tài liệu chính thức đã kiểm chứng trước khi dùng thực tế. File trong `HS_AI/TL` là tài liệu người dùng cung cấp; ứng dụng không tự khẳng định hiệu lực pháp lý của chúng.

> **Dữ liệu khi clone repo:** `.env`, `HS_AI/TL/`, `storage/`, `artifacts/` và `.logs/` không được đưa lên Git. Hãy cấu hình bí mật trên máy triển khai và nạp lại tài liệu nguồn được phép sử dụng trước khi phân tích thực tế.

## Kiến trúc và công nghệ

| Thư mục | Vai trò |
| --- | --- |
| `frontend/` | Next.js, React, TypeScript, Tailwind, các UI component theo cấu trúc shadcn/ui |
| `backend/` | NestJS, Prisma, PostgreSQL; xác thực, mã HS, lịch sử, phản hồi, quản trị |
| `ai-service/` | FastAPI; trích xuất tài liệu, embedding, pgvector, RAG, AI provider |
| `docs/` | Cấu hình AI và dữ liệu demo có ghi nhãn |
| `HS_AI/TL/` | Tài liệu nguồn sẵn có của người dùng |

Hướng dẫn triển khai frontend trên Vercel và backend/AI trên Render: [docs/DEPLOY_RENDER_VERCEL.md](docs/DEPLOY_RENDER_VERCEL.md).

`document_chunks.embedding` là `vector(1536)`. pg_trgm hỗ trợ tìm keyword; truy vấn cosine pgvector hỗ trợ tìm ngữ nghĩa. Python gộp và xếp hạng kết quả, sau đó tính confidence từ ngữ nghĩa, từ khóa, khớp mã và điểm LLM. Kết quả và citation được NestJS kiểm tra lần nữa trước khi lưu.

Mỗi lượt tra cứu lưu `legalAnalysis`: dữ kiện hàng hóa, từng điều khoản có ID đoạn tài liệu, cách áp dụng, nhóm/mã đã xem xét, kết luận có điều kiện và điểm cần xác minh. Giao diện hiển thị phần này cả khi trạng thái là `INSUFFICIENT_EVIDENCE`. Chỉ tài liệu đã lập chỉ mục và còn trong cơ sở dữ liệu mới được dùng làm trích dẫn; tài liệu demo bị loại khỏi truy xuất. Nếu kho tài liệu chưa có căn cứ phù hợp, hệ thống nêu rõ khoảng trống thay vì suy diễn điều khoản.

Khi thiếu dữ kiện có thể làm thay đổi mã, hệ thống tự trả lời các câu hỏi ngắn trong `legalAnalysis.decision_questions`, đặt giả định cụ thể và trả trạng thái `CONDITIONAL`. `legalAnalysis.hypotheses` lưu tối đa sáu phương án mã 8 số, theo thứ tự ưu tiên, với chất liệu/quy cách giả định, cách áp dụng quy tắc, trích dẫn và thuế tham khảo riêng. Thiếu chất liệu hoặc thông tin sản phẩm không được dùng làm lý do dừng ở “chưa đủ căn cứ”. Với bộ nhiều mặt hàng, hệ thống xét điều kiện bộ bán lẻ, đặc tính cơ bản, Quy tắc 3(c) khi được hỗ trợ và phương án phân loại riêng; phương án riêng lưu đầy đủ các món trong `hypotheses[].items`. Các chất liệu thông dụng và nhánh thông thường được ưu tiên khi người dùng chưa nêu quy trình đặc biệt. Nếu quy tắc chỉ ra nhánh bị bỏ sót, backend đối chiếu danh mục thêm một lần rồi phân tích lại. Mọi mã và trích dẫn đều được kiểm tra trước khi lưu; giả định phải giữ nguyên dữ kiện đã khai.

Các nhánh công suất ở cấp mã 8 số được giữ riêng khi lấy mã ứng viên, kể cả khi cùng thuộc một phân nhóm 6 số. Với động cơ servo đồng bộ chưa khai công suất, hệ thống đề xuất các khoảng công suất theo danh mục và ghi rõ giả định về số pha, công dụng. Số trong model không được coi là công suất đã xác nhận. Kết quả còn giả định được lưu là `CONDITIONAL` dù mô hình AI tự đánh dấu đã hoàn tất.

Khi nhập XLSX, các dòng mô tả cấp trung gian không có mã riêng được giữ trong mô tả mã con (ví dụ nhánh “Thịt nguội” của 1602.49.11). Với danh mục đã nhập, chạy `python scripts/refresh_catalog_descriptions.py` để xem các thay đổi, rồi thêm `--apply` để bổ sung mô tả từ bảng nguồn; bản sao mô tả cũ được lưu trong `artifacts/`.

Bộ `Chu giai HS 2022 Toan tap (HQKV8).pdf` được nạp bằng `python scripts/import_legal_corpus.py` để tìm theo chương, nhóm và từ khóa, không cần tạo embedding cho toàn bộ 2.409 trang. Luồng truy xuất kết hợp các đoạn này với tìm kiếm vector và quy tắc tổng quát. Tài liệu giữ nhãn nguồn người dùng cung cấp, chưa tự khẳng định hiệu lực pháp lý hiện tại.

## Yêu cầu và tình trạng máy hiện tại

- Node.js >= 22; pnpm 11; Python >= 3.11.
- PostgreSQL 16 có extension `vector` và `pg_trgm`, hoặc Docker Compose.
- AI API Gemini REST hoặc tương thích OpenAI có chat và embedding 1536 chiều.
- Đã kiểm thử end-to-end trên máy này với Neon PostgreSQL: migration, import 14.984 mã HS, index tài liệu, phân loại qua Gemini, lịch sử và phản hồi.

## Cài đặt local

```powershell
Copy-Item .env.example .env
pnpm install
python -m pip install -r ai-service/requirements.txt
```

Sửa `.env`: `JWT_SECRET`, `AI_SERVICE_TOKEN`, `AI_API_KEY`, model và mật khẩu DB. Chạy `python verify_provider.py` từ `ai-service/` để kiểm tra API chat và embedding riêng. Nếu dùng Docker:

```powershell
docker compose up -d postgres
pnpm --dir backend prisma:generate
$dbLine = Get-Content .env | Where-Object { $_.StartsWith('DATABASE_URL=') } | Select-Object -First 1
$env:DATABASE_URL = $dbLine.Substring(13)
pnpm --dir backend db:deploy
```

Nếu dùng Neon hoặc PostgreSQL native, đặt `DATABASE_URL` trong `.env` rồi chạy ba lệnh cuối của khối trên để áp dụng migration; không cần `docker compose up`. Migration tự tạo extension. User DB cần quyền `CREATE EXTENSION`, hoặc DBA tạo extension trước.

Khởi động toàn bộ ứng dụng từ thư mục gốc bằng một lệnh:

```powershell
pnpm dev
```

Lệnh này chạy ba dịch vụ nền, ghi log vào `.logs/service-*.log` và chỉ báo sẵn sàng sau khi kiểm tra chat, embedding, cơ sở dữ liệu, kho tài liệu và API thực tế. `/health` chỉ kiểm tra tiến trình AI còn hoạt động; `/ready` (cần `AI_SERVICE_TOKEN`) kiểm tra các phụ thuộc thực tế. Khi chạy qua Codex, cả ba dịch vụ cần được khởi động trong môi trường cho phép tạo tiến trình con và kết nối HTTPS ra ngoài. Nếu API AI mất kết nối, lượt tra cứu trả lỗi dịch vụ để thử lại và không lưu thành kết quả thiếu bằng chứng.

Cũng có thể chạy các terminal riêng:

```powershell
Set-Location ai-service
python run.py
```

```powershell
pnpm dev:backend
```

```powershell
pnpm dev:frontend
```

Sau khi AI service sẵn sàng, chạy seed từ gốc:

```powershell
pnpm --dir backend db:seed
```

Mở `http://localhost:3000`. API NestJS ở `http://localhost:3001/api`. Health AI service ở `http://localhost:8000/health`.

## Biến môi trường

Xem `.env.example`. Các biến chính: `DATABASE_URL`, `AI_PROVIDER`, `AI_API_KEY`, `AI_BASE_URL`, `AI_CHAT_MODEL`, `AI_EMBEDDING_MODEL`, `AI_EMBEDDING_DIMENSIONS`, `AI_SERVICE_URL`, `AI_SERVICE_TOKEN`, `JWT_SECRET`, `DOCUMENT_STORAGE_PATH`, `FRONTEND_ORIGIN`, `NEXT_PUBLIC_API_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`. Bật OpenRouter dự phòng miễn phí khi Gemini trả HTTP 429 bằng `AI_FALLBACK_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` và `OPENROUTER_CHAT_MODEL=openrouter/free`. Model phải được xác minh giá bằng 0; mỗi request giới hạn giá bằng 0. Embedding tiếp tục dùng Gemini. Hướng dẫn chi tiết tại [docs/AI_SETUP.md](docs/AI_SETUP.md). Không commit `.env`.

## Nhập mã HS và Knowledge Base

1. Đặt `ADMIN_EMAIL` và `ADMIN_PASSWORD` trong `.env` trước khi seed. Không có mật khẩu admin mặc định. Seed chỉ tạo admin khi có cả hai biến.
2. Đăng nhập `/auth`, mở `/admin`.
3. Tab **Mã HS** nhận CSV có cột `code,description` hoặc Excel có sheet `BT2026` (cột F mã, G mô tả). File `HS_AI/TL/BIEU THUE XNK 2026.xlsx` có cấu trúc này. Hệ thống ghi tên file làm provenance; quản trị viên phải kiểm tra độ tin cậy/hiệu lực nguồn.
4. Tab **Tài liệu** nhận PDF, DOCX, XLSX, TXT tối đa 60 MB. PDF giữ số trang; Excel giữ sheet và dòng trong metadata; DOCX/TXT không có số trang đáng tin cậy.
5. Trạng thái `PROCESSING → READY` hoặc `FAILED`. Có thể reindex sau khi sửa API key/model. `.doc` cũ trong `HS_AI/TL` cần chuyển sang DOCX hoặc PDF trước khi nạp.

Storage local ở `storage/`, được `.gitignore`. Đường dẫn chỉ được AI service chấp nhận nếu nằm dưới storage root. Interface `DocumentStorage` tại `backend/src/documents/storage.ts` cho phép thay local storage bằng S3/R2 khi triển khai (AI service cũng cần adapter đọc object tương ứng).

## API và thử bằng curl

```bash
curl -X POST http://localhost:3001/api/auth/register -H 'Content-Type: application/json' -d '{"email":"user@example.com","password":"strongpassword123"}'
curl -X POST http://localhost:3001/api/auth/login -H 'Content-Type: application/json' -d '{"email":"user@example.com","password":"strongpassword123"}'
curl 'http://localhost:3001/api/hs-codes/search?q=6109'
curl -X POST http://localhost:3001/api/classification/search -H 'Content-Type: application/json' -d '{"description":"Áo thun nam 100% cotton, dệt kim"}'
curl http://localhost:3001/api/classification/<search-id>
curl http://localhost:3001/api/classification/history -H 'Authorization: Bearer <token>'
curl -X POST http://localhost:3001/api/classification/<search-id>/feedback -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"is_correct":true}'
curl -X POST http://localhost:3001/api/admin/documents -H 'Authorization: Bearer <admin-token>' -F 'title=Chú giải HS' -F 'source=Nguồn cần kiểm chứng' -F 'file=@example.pdf'
curl -X POST http://localhost:3001/api/admin/hs-codes/import -H 'Authorization: Bearer <admin-token>' -F 'file=@codes.csv'
```

Thêm: `POST /api/classification/extract` (file sản phẩm), `GET /api/hs-codes/:code`, `GET/DELETE /api/admin/documents`, `POST /api/admin/documents/:id/reindex`, `GET /api/admin/dashboard`, `/history`, `/low-confidence`, `/feedback`, `/users`, `PATCH /api/admin/users/:id/role`.

## Test

Trang tra cứu có phần **Thông tin khai báo tên hàng**: sáu nhóm thông tin, bản nháp tên hàng tiếng Việt, kiểm tra tình trạng và đối chiếu tên trên chứng từ chuyên ngành. Thông tin còn thiếu được đánh dấu, không tự chuyển giả định HS thành dữ kiện khai báo. Hướng dẫn: [docs/DECLARATION_NAMING.md](docs/DECLARATION_NAMING.md).

Trang kết quả trình bày theo mẫu: mã HS, lý do phân loại có trích dẫn, mã dễ nhầm, thuế suất và tên hàng gợi ý. Thuế suất lấy từ sheet `BT2026` của `HS_AI/TL/BIEU THUE XNK 2026.xlsx` do người dùng cung cấp; chạy `python scripts/build_tariff_rates.py` sau khi thay bảng nguồn để cập nhật dữ liệu dùng ở backend. Ô có điều kiện (ví dụ `8/10` đối với VAT) được giữ nguyên ý nghĩa điều kiện; hệ thống không tự chọn một mức khi chưa có dữ kiện. Với công thức chỉ cộng 90%, mã và thuế được trình bày có điều kiện, kèm thông tin cần xác minh.

Kết quả đủ thông tin nổi bật mã HS, tên khai báo và thuế, giải thích lựa chọn và các mã dễ nhầm; không thêm giả định. Kết quả thiếu thông tin trình bày từng thẻ phương án, chỉ giả định phần có thể làm đổi mã còn chưa khai, kèm lý do, tên hàng và thuế riêng. Bộ phân loại riêng giữ đủ từng mặt hàng; chi tiết câu hỏi và nguồn có thể mở khi cần xem. Rà soát luồng và phạm vi kiểm chứng: [docs/CLASSIFICATION_FLOW_AUDIT.md](docs/CLASSIFICATION_FLOW_AUDIT.md).

### Phân tích nhiều mặt hàng

Nhập danh sách đánh số hoặc cách nhau bằng dòng trống rồi bấm **Phân tích mã HS**. Hệ thống nhận diện từng mặt hàng và phân tích lần lượt; model/thông số nhiều dòng vẫn đi cùng đúng sản phẩm, bộ quà tặng được giữ nguyên để xét quy tắc HS. Nút **Tách / chỉnh danh sách mặt hàng** cho phép xem lại, sửa, thêm/xóa và khai thông tin riêng trước khi phân tích. Mỗi lượt tối đa 10 mặt hàng, danh sách tối đa 20.000 ký tự và mỗi mặt hàng tối đa 2.000 ký tự. Tài liệu vượt giới hạn được báo lỗi thay vì cắt bỏ các mặt hàng cuối.

Các dòng invoice đánh số, có model hoặc cột số lượng/đơn giá/thành tiền, được tách trực tiếp theo từng dòng hàng. Các model cùng tên sản phẩm vẫn là các mục riêng; `SET`/`PCS` trong cột số lượng không tự xác lập bộ bán lẻ. Nếu dán cả danh sách vào một ô trong trình sửa, hệ thống nhận diện và tách lại trước khi phân tích. Mô tả chưa tách được được đánh dấu cần kiểm tra, không xác nhận là một mặt hàng.

Kết quả có thẻ riêng, mã HS trên tiêu đề và nút mở/thu gọn từng thẻ hoặc tất cả. Mặt hàng đầu mở sẵn. Mỗi món có tên khai báo, thuế, giả định nếu thiếu thông tin, nguồn và phản hồi riêng. Nếu một món gặp lỗi, các món còn lại tiếp tục; có thể thử lại riêng món lỗi. Kết quả được lưu từng món và có liên kết mở lại cả danh sách khi tất cả đã được lưu.

```powershell
python -m pytest ai-service/tests -q -p no:cacheprovider
pnpm test
pnpm build
```

Test Python có 10 sản phẩm mẫu và kiểm tra chặn mã bịa/trích dẫn thiếu. Test có mock không thay thế kiểm thử với DB và AI API thật.

## Bảo mật, triển khai và giới hạn

Build production sau khi cấu hình DB và `.env`:

```powershell
pnpm build
pnpm --dir backend start:prod
pnpm --dir frontend start
```

Chạy AI service bằng `python run.py` từ `ai-service/` trên Windows để Psycopg dùng selector event loop. Trên Linux, có thể chạy `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Dùng reverse proxy HTTPS cho frontend/API, giữ cổng AI service trong mạng nội bộ, chạy migration `db:deploy` trước khi chuyển phiên bản, sao lưu PostgreSQL và storage định kỳ.

- API key chỉ ở server; JWT giới hạn 12 giờ; history cần đăng nhập, feedback của lượt tra cứu có chủ tài khoản chỉ chủ sở hữu được gửi; quản trị cần role `ADMIN`.
- Upload kiểm tra đuôi, magic bytes và kích thước. Nội dung tài liệu được làm sạch control characters và được coi là dữ liệu không đáng tin trong prompt.
- Rate limit hiện là 10 lượt phân loại/phút theo IP hoặc user trong **một process**. Production nhiều instance cần rate limit tập trung ở gateway/Redis.
- Bản MVP lưu token ở `sessionStorage`; production nên chuyển sang cookie HttpOnly, HTTPS, CSRF protection và quản lý phiên đầy đủ.
- Không có OCR cho PDF scan, hỗ trợ DOCX chứ không hỗ trợ `.doc`; không kiểm chứng tự động hiệu lực văn bản nguồn.
- Quá trình index chạy trong process backend sau upload; production nên dùng job queue, giới hạn số chunk/chi phí embedding và theo dõi tiến độ. Không nên đưa dịch vụ nội bộ FastAPI ra Internet.
- Trước khi production: thay demo data, xác minh danh mục HS và tài liệu, kiểm thử end-to-end với DB và provider thật, sao lưu DB/storage, cấu hình HTTPS, secrets manager, giám sát lỗi và kiểm thử tải.
