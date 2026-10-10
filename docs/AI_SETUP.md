# Cấu hình AI API

AI service có adapter cho API tương thích OpenAI, Gemini REST native và OpenRouter miễn phí dự phòng cho chat. Adapter DeepSeek cũ vẫn có thể cấu hình riêng. Khóa chỉ được đọc từ `.env` ở gốc project bởi backend/AI service; frontend chỉ nhận `NEXT_PUBLIC_API_URL`.

1. Tạo API key từ nhà cung cấp AI bạn chọn. Adapter OpenAI cần `POST /chat/completions` và `/embeddings`; adapter Gemini dùng `:generateContent` và `:embedContent`.
2. Sao chép `.env.example` thành `.env`, điền `AI_API_KEY`. Không đưa `.env` lên Git.
3. Đặt `AI_CHAT_MODEL` thành tên model chat có thể trả JSON.
4. Đặt `AI_EMBEDDING_MODEL` thành model embedding có đúng **1536 chiều**. Cấu trúc pgvector hiện dùng `vector(1536)`; đổi model có kích thước khác cần migration, tạo lại index và nạp lại tài liệu.
5. Với OpenAI-compatible, dùng URL kết thúc bằng `/v1` và `AI_PROVIDER=openai`. Với Gemini, dùng `AI_PROVIDER=gemini` và `AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta`.
6. Đặt `AI_SERVICE_TOKEN` thành chuỗi ngẫu nhiên chỉ dùng giữa backend và AI service; `JWT_SECRET` dài ít nhất 32 ký tự.
7. Chạy PostgreSQL + pgvector, migration, backend và AI service theo README. AI service lắng nghe cổng 8000 và chỉ nên truy cập nội bộ.
8. Nạp mã HS và tài liệu. Chỉ tài liệu ở trạng thái `READY` được tìm kiếm. Nếu tài liệu `FAILED`, xem lỗi trong `/admin` rồi lập chỉ mục lại.
9. Chạy `python verify_provider.py` từ `ai-service/` để kiểm tra riêng chat và embedding mà không in khóa hoặc nội dung phản hồi. Sau đó thử `POST /api/classification/search` theo ví dụ ở README. Kết quả chỉ có mã thuộc danh sách ứng viên và chunk trích dẫn hợp lệ; thiếu căn cứ trả `INSUFFICIENT_EVIDENCE`.
10. Khi chat chính trả HTTP 429, dùng nhà cung cấp dự phòng đã cấu hình. OpenRouter dự phòng chỉ dùng model miễn phí. Lỗi dịch vụ AI còn lại trả HTTP 503 với `AI_SERVICE_UNAVAILABLE`, không chuyển lỗi kết nối thành kết luận thiếu căn cứ pháp lý. Khi embedding tạm thời hết quota hoặc mất kết nối, tra cứu tiếp bằng văn bản chuẩn hóa và ngữ cảnh pháp lý trong DB.
11. Nếu timeout: kiểm tra kết nối nhà cung cấp, model, độ dài tài liệu; việc lập chỉ mục tài liệu lớn có thể cần nhiều phút. Gemini thử tối đa bốn lượt cho lỗi tạm thời 429/500/502/503/504 và lỗi kết nối, tuân thủ thời gian chờ API. Quota ngày đã hết được trả ngay; chat có dự phòng chuyển ngay khi nhận 429. Worker chỉ mục lưu từng đợt và tự tiếp tục theo thời gian quota mở lại đã được người dùng chọn.

Ví dụ OpenAI-compatible trong `.env`:

```dotenv
AI_PROVIDER=openai
AI_API_KEY=your-key-here
AI_BASE_URL=https://api.openai.com/v1
AI_CHAT_MODEL=gpt-4o-mini
AI_EMBEDDING_MODEL=text-embedding-3-small
AI_EMBEDDING_DIMENSIONS=1536
```

Ví dụ Gemini REST native:

```dotenv
AI_PROVIDER=gemini
AI_API_KEY=your-key-here
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
AI_CHAT_MODEL=gemini-3.5-flash-lite
AI_EMBEDDING_MODEL=gemini-embedding-001
AI_EMBEDDING_DIMENSIONS=1536
```

Gemini adapter dùng `x-goog-api-key` chỉ trong AI service. Embedding 1536 chiều của `gemini-embedding-001` được chuẩn hóa L2 trước khi lưu pgvector.

## OpenRouter miễn phí dự phòng khi Gemini hết quota chat

Thêm vào `.env` và khởi động lại AI service:

```dotenv
AI_FALLBACK_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=openrouter/free
```

Hệ thống ưu tiên Gemini. Khi nhận HTTP 429, chuyển chat sang OpenRouter cho bước tìm ứng viên, hiểu nghĩa mặt hàng, phân tích và sửa kết quả. Dùng cùng prompt và các kiểm tra dữ kiện, mã danh mục, điều kiện nhánh, nguồn trích dẫn. Giữ OpenRouter xuyên suốt lượt phân tích; các lượt mới thử lại Gemini sau thời gian chờ quota do API báo (mặc định 60 giây nếu không có thời gian chờ).

Adapter lấy danh sách `/models` và chỉ giữ `openrouter/free` hoặc biến thể `:free` có giá prompt, completion và các khoản giá khác bằng 0. Danh sách được cập nhật sau tối đa 5 phút. Model được cấu hình phải thuộc danh sách này và hỗ trợ JSON. `openrouter/free` tự chọn model miễn phí phù hợp với yêu cầu JSON. Mỗi request đặt `provider.require_parameters=true` và `provider.max_price` bằng 0 cho prompt, completion, request và image. Không thêm model trả phí, plugin tính phí hoặc tuyến auto. Nếu không có model miễn phí phù hợp hoặc OpenRouter hết quota, báo lỗi dịch vụ; không chuyển sang model trả phí hay DeepSeek.

`AI_PROVIDER`, khóa Gemini và model embedding vẫn phục vụ embedding. OpenRouter chỉ thay chat: không tạo hoặc trộn vector khác với chỉ mục Gemini. Khi hết quota embedding, ứng dụng dùng tra cứu văn bản; worker chỉ mục tiếp tục lịch chờ Gemini.

Kiểm tra từ thư mục `ai-service/`:

```powershell
python verify_provider.py --fallback
python verify_provider.py --simulate-chat-quota
```

Lệnh thứ hai giả lập quota ở chat chính rồi gọi OpenRouter thật, không thay cấu hình Gemini. Các lệnh chỉ in trạng thái, tên model thực và chi phí trả về; không in khóa hay nội dung phản hồi. HTTP 401 nghĩa là khóa không được chấp nhận; HTTP 429 nghĩa là giới hạn lượt gọi. Để tắt dự phòng, để trống `AI_FALLBACK_PROVIDER`. Khóa DeepSeek còn trong `.env` không được gọi khi chọn `AI_FALLBACK_PROVIDER=openrouter`.

Phép thử phân loại với tài liệu thực đã được người dùng cho phép: từ gốc project chạy `python scripts/verify_free_fallback.py`. Dùng mô tả crochet, danh mục đủ nhánh cha từ backend và truy xuất pháp lý trong DB; giả lập quota chat Gemini rồi xác nhận mã 84479010, nguồn thực và chi phí OpenRouter bằng 0. Không ghi thêm lịch sử tra cứu.

API và định tuyến: [Free Models Router](https://openrouter.ai/openrouter/free), [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection), [Limits](https://openrouter.ai/docs/api_reference/limits).

Không khai báo `AI_API_KEY` bằng biến `NEXT_PUBLIC_*` và không gửi khóa tới browser. Nếu nhà cung cấp không hỗ trợ `response_format: {"type":"json_object"}`, cần sửa adapter trong `ai-service/app/ai_client.py`; interface `AIProvider` giữ nguyên.
