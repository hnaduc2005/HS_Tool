# Triển khai HS_Tool trên Render và Vercel

Hướng dẫn này áp dụng cho mã nguồn hiện tại. Frontend Next.js chạy trên Vercel; một **Render Web Service dạng Docker** chạy API NestJS và FastAPI trong cùng container; PostgreSQL có thể là Render Postgres hoặc cơ sở dữ liệu PostgreSQL/pgvector hiện có. Backend và AI service phải dùng cùng đường dẫn tệp: backend lưu tệp và gửi đường dẫn đó cho AI service để trích xuất/lập chỉ mục.

```text
Trình duyệt -> Vercel (frontend)
                    |
                    v
            Render Web Service (NestJS :PORT)
                 |             |
                 |             +-> FastAPI 127.0.0.1:8000
                 |                      |
                 +-------+--------------+
                         |
                  PostgreSQL + /app/storage
```

Các tệp triển khai trong repo: `Dockerfile`, `.dockerignore`, `scripts/render-start.sh`. Script khởi động chạy Prisma migration, sau đó chạy FastAPI ở loopback và NestJS ở cổng `PORT` do Render cấp. `GET /api/health` kiểm tra kết nối DB. Chỉ NestJS được Render đưa ra Internet.

## 1. Chọn cơ sở dữ liệu và nơi lưu tài liệu

**Phương án giữ dữ liệu hiện có:** dùng `DATABASE_URL` của PostgreSQL/pgvector đang chứa danh mục và các đoạn tài liệu. Nếu cơ sở dữ liệu đang dùng là Neon, nhập chính URL server đang dùng vào Render Environment; không đưa URL vào Git. Các đoạn tài liệu đã có trong DB có thể tiếp tục tìm kiếm. Tuy nhiên `documents.file_url` đang ghi đường dẫn Windows của máy cũ sẽ không dùng được để reindex/xóa tệp trên Linux. Muốn sử dụng lại chức năng đó, phải chuyển tệp nguồn lên disk Render và cập nhật đường dẫn tương ứng hoặc tải lại tài liệu qua trang quản trị.

**Phương án Render Postgres mới:** tạo database PostgreSQL 16 trên Render, đặt cùng region với Web Service. Dùng **Internal Database URL** cho biến `DATABASE_URL` của Web Service. Migration đầu tiên tạo `vector` và `pg_trgm`; Render hỗ trợ cả hai extension. Database mới chỉ có schema: cần nạp danh mục HS và tài liệu nguồn được phép sử dụng sau khi tạo admin. Render Postgres Free hiện giới hạn 1 GB và hết hạn sau 30 ngày, nên không phù hợp để giữ corpus vận hành lâu dài. [Render Postgres](https://render.com/docs/postgresql-creating-connecting), [extensions](https://render.com/docs/postgresql-extensions), [gói Free](https://render.com/docs/free).

**Lưu tệp:** đặt `DOCUMENT_STORAGE_PATH=/app/storage` và gắn **Persistent Disk** của Render vào đúng `/app/storage` nếu cần tải tài liệu và reindex bền vững. Render chỉ cho gắn disk vào dịch vụ trả phí; filesystem của dịch vụ Free mất dữ liệu khi restart, redeploy hoặc sleep. Cấu hình một instance cho service có disk. [Render Persistent Disks](https://render.com/docs/disks), [giới hạn Free](https://render.com/docs/free).

## 2. Tạo Web Service trên Render

1. Kết nối GitHub, chọn repo `hnaduc2005/HS_Tool` → **New Web Service**.
2. Chọn **Docker**; để trống **Root Directory** (gốc repo); Dockerfile Path: `./Dockerfile` (hoặc để mặc định); Docker Build Context: `.`. Để trống Docker Command/Start Command để dùng lệnh `CMD` trong Dockerfile.
3. Chọn region cùng Render Postgres nếu dùng database của Render. Chọn plan có đủ bộ nhớ cho NestJS, FastAPI và xử lý PDF/embedding. Với nhu cầu giữ tệp, chọn plan có thể gắn Persistent Disk và mount `/app/storage`.
4. Trong Environment, cấu hình các biến dưới đây. Đặt `PORT=10000` để Render và NestJS thống nhất cổng công khai ngay từ đầu; không đặt `PORT=3001`. `AI_SERVICE_URL` đã được script ấn định là `http://127.0.0.1:8000`.
5. Đặt Health Check Path là `/api/health`, bật auto deploy theo nhánh `main`, rồi tạo service. URL nhận được có dạng `https://<ten-service>.onrender.com`; API ở `/api`.

Nếu log báo `failed to read dockerfile: open Dockerfile: no such file or directory`, kiểm tra **Root Directory** của Render đang để trống và **Dockerfile Path** là `./Dockerfile`. Tệp này nằm ở gốc repo. Giá trị `frontend` chỉ dùng làm Root Directory trên Vercel. Sau khi sửa cấu hình, redeploy commit mới nhất từ `main`.

| Biến Render | Giá trị cần nhập |
| --- | --- |
| `DATABASE_URL` | Internal URL của Render Postgres cùng region, hoặc URL PostgreSQL/pgvector hiện có. |
| `PORT` | `10000` cho Web Service trên Render. |
| `AI_PROVIDER` | Nhà cung cấp chính đang dùng, ví dụ `gemini`. |
| `AI_API_KEY`, `AI_BASE_URL`, `AI_CHAT_MODEL` | Sao chép **giá trị hiện có của máy bạn** vào Render Environment; không gửi qua chat hoặc commit. |
| `AI_EMBEDDING_MODEL`, `AI_EMBEDDING_DIMENSIONS` | Model embedding đã dùng để tạo chỉ mục; kích thước phải là `1536`. |
| `AI_SERVICE_TOKEN` | Token bí mật mới, giống cho NestJS/FastAPI trong container. |
| `JWT_SECRET` | Chuỗi bí mật ngẫu nhiên dài ít nhất 32 ký tự. |
| `DOCUMENT_STORAGE_PATH` | `/app/storage`. |
| `FRONTEND_ORIGIN` | Sau khi có URL Vercel, đặt chính xác origin, ví dụ `https://hs-tool.vercel.app` (không thêm `/`). |
| `AI_FALLBACK_PROVIDER` | `openrouter` nếu muốn dự phòng chat bằng model miễn phí. |
| `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_CHAT_MODEL` | Khi dùng dự phòng, giữ model `openrouter/free` hoặc model `:free` được adapter xác minh giá bằng 0. |

Nếu chưa biết URL Vercel lúc tạo Render, đặt tạm `FRONTEND_ORIGIN` theo mặc định local rồi cập nhật sau bước 3. Dịch vụ có thể trả `/api/health` trong lúc giao diện chưa gọi API được do CORS. Chỉ thêm biến OpenRouter nếu đã cấu hình dự phòng. Embedding vẫn do nhà cung cấp chính thực hiện.

Sau khi deploy, mở `https://<ten-service>.onrender.com/api/health`. Kết quả mong đợi là `{"status":"ok"}`. Nếu deploy thất bại, xem Render logs: lỗi `DATABASE_URL`/migration, thiếu extension hoặc sai khóa AI là các trường hợp cần phân biệt. Health check chỉ kiểm tra backend và DB; thử phân loại mới xác nhận được nhà cung cấp AI và kho tài liệu. [Render Docker](https://render.com/docs/docker), [Web Services](https://render.com/docs/web-services), [Health Checks](https://render.com/docs/health-checks).

Nếu Deploys báo `Timed Out` sau `New primary port detected: 10000`, hãy kiểm tra **bản deploy mới nhất** thay vì chỉ mở URL công khai: Render có thể vẫn phục vụ bản cũ. Trong Settings, đặt **Health Check Path** là `/api/health`; đường dẫn rỗng chỉ kiểm tra TCP, không xác nhận API và DB đã sẵn sàng. Trong Environment đặt `PORT=10000`, sau đó deploy lại. Log khởi động mới in commit và cổng; nếu một trong hai tiến trình thoát, script cũng ghi tiến trình và mã lỗi. Nếu vẫn hết thời gian, đối chiếu commit trong log với commit đang deploy và xem Events/Logs của đúng lần deploy. [Render Health Checks](https://render.com/docs/health-checks), [Port binding](https://render.com/docs/web-services#port-binding).

## 3. Tạo frontend trên Vercel

1. Import cùng repo GitHub vào Vercel, chọn **Framework Preset: Next.js** và **Root Directory: `frontend`**. Chọn Node.js 22 trong Project Settings.
2. Thêm biến môi trường **Production** `NEXT_PUBLIC_API_URL=https://hs-tool.onrender.com/api` (không thêm dấu `/` cuối). Đây là URL công khai, được nhúng vào bundle trình duyệt lúc build. Không đặt API key, token nội bộ hoặc `DATABASE_URL` trên Vercel.
3. Deploy. Ghi lại domain Production `https://<ten-project>.vercel.app` hoặc domain riêng.
4. Quay lại Render, đặt `FRONTEND_ORIGIN` bằng origin chính xác vừa nhận rồi Save/Deploy. Tải lại trang Vercel và thử tra cứu.

Repo hiện ghim `pnpm@11.7.0`. Tài liệu Vercel liệt kê nhận dạng tự động đến pnpm 10; vì vậy hãy **kiểm tra build log trước khi coi deploy hoàn tất**. Trong Vercel, bật `ENABLE_EXPERIMENTAL_COREPACK=1` để Vercel dùng `packageManager` của repo, và để Vercel tự chọn Install/Build Command. Nếu build vẫn từ chối pnpm 11, cần đồng bộ dự án sang pnpm 10 và tạo lại lockfile trước khi redeploy; đừng chỉ đổi lệnh Install Command thành `pnpm install` vì Vercel có thể chọn pnpm 6. [Vercel monorepos](https://vercel.com/docs/monorepos), [package managers](https://vercel.com/docs/package-managers), [environment variables](https://vercel.com/docs/environment-variables).

`NEXT_PUBLIC_API_URL` thay đổi chỉ có tác dụng với **bản build Vercel tiếp theo**. Nếu URL vẫn là `localhost:3001`, kiểm tra biến Production, redeploy và xóa cache trình duyệt. Với Preview Deployments có domain khác, CORS hiện chỉ nhận một `FRONTEND_ORIGIN`; muốn thử preview cần đặt origin trùng domain preview hoặc bổ sung allowlist có kiểm soát trong backend.

## 4. Tạo quản trị và nạp dữ liệu

**Nếu dùng DB cũ:** đăng nhập bằng admin cũ. Đối chiếu danh mục và nguồn đã lưu. Những tệp gốc cũ có đường dẫn trên Windows cần chuyển/tải lại để reindex hoặc xóa được trên Render.

**Nếu dùng DB mới:** trên máy local, cấu hình `DATABASE_URL` bằng **External Database URL** của Render Postgres (`sslmode=require`), cùng `ADMIN_EMAIL` và `ADMIN_PASSWORD` (tối thiểu 12 ký tự) trong biến môi trường của terminal, rồi chạy:

```powershell
pnpm --dir backend prisma:generate
pnpm --dir backend admin:create
```

Lệnh `admin:create` chỉ tạo/cập nhật tài khoản quản trị, không nạp dữ liệu demo. Không dùng `db:seed` cho dữ liệu thực. Tránh ghi mật khẩu trực tiếp vào lệnh lưu trong lịch sử terminal; nhập bằng công cụ quản lý bí mật của bạn. Sau khi đăng nhập `/auth`, vào `/admin` để tải danh mục HS và tài liệu. Tệp nguồn trong `HS_AI/TL/` không nằm trên GitHub nên phải tải từ nguồn được phép sử dụng. Chờ tài liệu chuyển sang `READY` rồi thử phân loại. [Render external connection](https://render.com/docs/postgresql-creating-connecting).

## 5. Kiểm tra sau triển khai

1. Render `/api/health` trả `ok`; Render logs không có lỗi migration hoặc tiến trình AI thoát.
2. Vercel mở được giao diện; Network tab gọi đúng domain Render, không phải `localhost`.
3. Đăng ký/đăng nhập được; trang `/admin` chỉ mở bằng tài khoản quản trị.
4. Danh mục có mã thật; tài liệu nguồn có trạng thái `READY`; phân loại thử mặt hàng đã kiểm chứng trả đúng mã và nguồn.
5. Tải một tệp thử, xác nhận trích xuất; nếu gắn disk, redeploy Render rồi kiểm tra tệp và khả năng reindex vẫn còn.
6. Kiểm tra nhiều mặt hàng, phương án `CONDITIONAL`, tên hàng khai báo và thuế của từng mã.

**Giới hạn hiện tại:** cấu hình Docker này chạy hai tiến trình trong một Render instance vì luồng chia sẻ đường dẫn local. Để tách thành hai Render services, cần đổi giao thức truyền tệp hoặc dùng object storage mà cả backend và AI đọc được. Việc lập chỉ mục do backend khởi chạy trong tiến trình; deploy/restart giữa chừng có thể làm tài liệu còn `PROCESSING`, khi đó cần kiểm tra và reindex. Gói Free chỉ phù hợp demo văn bản với dữ liệu đã có trong DB; không bảo đảm lưu tệp bền vững và có thể chậm sau khi sleep.
