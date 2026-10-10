# Rà soát luồng hiểu mặt hàng và phân loại HS

Ngày cập nhật: 10/10/2026.

## Trình tự

1. Đọc toàn bộ mô tả: tên kỹ thuật, quan hệ máy hoàn chỉnh/bộ phận/bộ hàng, phủ định, số và đơn vị. Số model không xác nhận công suất, điện áp, số pha hoặc cơ cấu.
2. Truy xuất định nghĩa và điều khoản loại trừ tương ứng; dùng nghĩa đó xác định mặt hàng trước khi giả định thông tin thiếu.
3. Ghi dữ kiện có câu trích từ mô tả; định nghĩa phải có câu trích và ID nguồn thực tế. Phân biệt chất liệu từng món, công thức đã khai/phần còn thiếu, bao bì kín khí/đóng gói bán lẻ.
4. Đối chiếu nội dung nhóm, chú giải phần/chương và Quy tắc 1. Xét các quy tắc về hàng chưa hoàn chỉnh, hỗn hợp hoặc bộ hàng khi trường hợp đó cần.
5. Tra đủ nhánh danh mục. Gợi ý mã của AI chỉ phục vụ tìm kiếm; giữ các mã cùng nhánh trước khi giới hạn danh sách. So sánh phân nhóm cùng cấp và toàn bộ điều kiện nhánh cha theo Quy tắc 6.
6. Tự trả lời câu hỏi ngắn. Chỉ giả định thuộc tính chưa khai quyết định mã, giữ nguyên mặt hàng, cơ cấu và dữ kiện đã biết.
7. Kiểm tra mã tám số có trong danh mục, điều kiện nhánh, dữ kiện, nguồn và thứ tự ưu tiên. Loại phương án đổi loại hàng hoặc giả định lại thông tin đã khai.
8. Lưu và hiển thị nghĩa mặt hàng, dữ kiện, câu hỏi, cách chọn mã và nguồn. Khi đủ điều kiện, trả một mã hoàn tất; không tạo mặt hàng khác để ép số lượng đề xuất.

## Sai sót đã sửa

- Crochet từng bị coi là dệt kim phẳng hoặc được thêm phương án dệt kim phẳng bằng cách giả định lại cơ cấu. Dùng định nghĩa máy dệt móc tại mục (C)(7) của chú giải 84.47. Nguồn dệt kim phẳng phục vụ so sánh, không chứng minh nghĩa crochet.
- Inverter từng bị đưa sang máy biến áp điện môi lỏng. Phân biệt máy biến đổi điện tĩnh, biến áp, cuộn cảm và chấn lưu trước khi xét mã quốc gia.
- Van từng được đưa vào nhánh van cổng chỉ từ đường kính. Kiểm tra đồng thời chức năng, cấu tạo, cách vận hành, vị trí/đơn vị đo và chất liệu.
- Cắt danh sách sớm có thể làm mất mã không chạy điện hoặc nhánh quốc gia nằm cuối danh mục. Tra trực tiếp họ hàng nhận diện từ tên máy, giữ đại diện các nhánh và mở rộng gợi ý tám số ra các mã cùng phân nhóm.
- Bước hiểu công thức có thể loại nhánh thịt lợn trước khi xét phần còn thiếu. Khi công thức chưa đủ 100%, giữ các nhánh cạnh tranh và chỉ thay đổi phần tỷ lệ chưa khai.
- Chuỗi con nam trong từ tiếng Anh ornamental từng tạo thông tin giới tính sai. Kiểm tra từ độc lập thay cho chuỗi con.

Ưu tiên Loại khác đuôi 90 khi thiếu chất liệu chỉ áp dụng trong nhánh phù hợp có mã đó. Không tạo mã 90 và không bỏ qua chức năng, cơ cấu, dẫn động hoặc ngưỡng quốc gia.

## Chuẩn hóa tài liệu

- Chuẩn hóa biểu diễn tra cứu của **6.694 đoạn**; sửa ngữ cảnh chương/nhóm của **64 đoạn**.
- Đối chiếu bản sao ban đầu: nội dung nguồn, ID đoạn/tài liệu, số trang và thứ tự đoạn giữ nguyên.
- Unicode NFC, loại ký tự mềm/ẩn, nối khoảng trắng PDF, bỏ dòng số trang khỏi biểu diễn tra cứu. Giữ số liệu, đơn vị, ký hiệu và phủ định.
- Nội dung tạo embedding có ngữ cảnh phần/chương/nhóm/mục/quy tắc. Câu nhắc đến nhóm khác không tự đổi ngữ cảnh cấu trúc.
- Ba tài liệu thực có **6.454 đoạn có nội dung tra cứu**. **238 đoạn chỉ có dấu trang** được giữ và bỏ qua khi tạo embedding. Loại tài liệu demo khỏi tra cứu pháp lý.
- Tài liệu nhập mới dùng cùng quy trình, tách đoạn ưu tiên ranh giới câu/đoạn và giữ đơn vị như cm³.

Bản sao gốc: `.logs/legal-normalization/backup-20261008T164020Z.json.gz`.

Báo cáo toàn vẹn và số embedding hiện tại: `.logs/legal-normalization/integrity-audit.json`; cập nhật bằng `python scripts/audit_legal_corpus.py`.

Tạo chỉ mục qua Gemini đã cấu hình theo quyền gửi ba tài liệu mà người dùng đã cho phép. `python scripts/normalize_legal_corpus.py --embed-only` tiếp tục các đoạn còn thiếu, lưu từng đợt và tuân thủ thời gian chờ API. Chỉ coi bước này hoàn tất khi báo cáo ghi `remaining_embeddings: 0`.

## Kiểm chứng

- Kiểm tra Python: định nghĩa, câu trích, công suất/đơn vị, phần công thức còn thiếu, thuộc tính từng món, điều kiện nhánh và thời gian chờ quota.
- Kiểm tra backend: danh mục, mã cùng nhánh, ngưỡng quốc gia, nguồn và lưu kết quả.
- API và phần hiển thị dùng kết quả thực, đồng thời đọc lại kết quả đã lưu.
- Mẫu `COMPUTERIZED CROCHET MACHINE / POWER: 1.5KW` đã trả **84479010**, trạng thái COMPLETED, không thêm dệt kim phẳng. Tệp kiểm chứng: `.logs/verified-meaning-first/crochet-machine-result.json`.
- Máy: `.logs/verified-meaning-first`. Bộ quà, motor, van, inverter, kệ TV và thực phẩm: `.logs/verified-meaning-regression`.

Phạm vi xác minh là các lỗi tái hiện và các trường hợp trong bộ kiểm tra; kết quả ngoài phạm vi đó tiếp tục qua bước hiểu nghĩa, tra cứu và kiểm tra nguồn. Bộ kiểm tra này không chứng minh mọi mặt hàng HS đều phân loại đúng.

## Thông tin khai báo tên hàng

- Bổ sung sáu trường: tên tiếng Việt, thành phần/chất liệu, công dụng/thông số, model/code, nhãn hiệu/xuất xứ, tình trạng. Giữ lựa chọn tình trạng chưa khai theo mặc định.
- Ghép tên theo dữ kiện đã khai, đánh dấu trường thiếu, nhắc tên chung hoặc chỉ tiếng Anh; không lấy giả định HS làm dữ kiện của tên khai báo.
- Đối chiếu tên chứng từ chuyên ngành do người dùng nhập; không gửi tên chứng từ đó vào AI và không tự xác minh chứng từ hay phạm vi kiểm tra chuyên ngành.
- Lưu biểu mẫu, bản nháp và kết quả đối chiếu cùng phân tích. Phục hồi mô tả gốc để không nối lặp trường khi tra cứu lại. Tổng dữ kiện đưa vào AI tối đa 2.000 ký tự; không cắt mất thông số khi vượt giới hạn.
- Chặn tỷ lệ tình trạng “mới 100%” và phần trăm trong metadata khỏi phép tính công thức thực phẩm; không nối lặp thành phần đã có trong mô tả.
- Sau thay đổi: **192 kiểm thử Python, 40 kiểm thử backend**, kiểm tra TypeScript và render React đạt. API thật với trường khai báo trả crochet **84479010**, lưu/đọc lại đủ biểu mẫu, giữ lựa chọn đã qua sử dụng và không tự điền chất liệu thiếu. Tệp kiểm chứng: `.logs/verified-declaration/crochet-machine-result.json`.

### Sửa lỗi servo và tự đề xuất tên hàng (09/10/2026)

- Tái hiện mô tả servo có model xuống dòng và dòng số lượng/giá trên Invoice. Bước hiểu mặt hàng nhận đúng động cơ; mô hình trả đủ năm phương án nhưng đặt thuộc tính công suất là `power_range`. Bộ kiểm tra chỉ nhận `power`, nên loại toàn bộ phương án và lưu INSUFFICIENT_EVIDENCE dù vẫn có chú giải và bước pháp lý hợp lệ.
- Dùng cùng bộ chuẩn hóa thuộc tính cho dữ kiện đã khai, thông tin còn thiếu và giả định. `power_range`, `rated_power`, `output_power`, `phase_count` và các tên tương đương quy về thuộc tính vật lý chuẩn. Các tên có phạm vi từng món vẫn giữ phạm vi. Chuẩn hóa cách viết mã có dấu chấm trước khi kiểm tra nhận diện. Không cho phép dùng tên tương đương để giả định lại công suất đã biết hoặc đổi mặt hàng.
- Tên hàng tự tạo từ sản phẩm nhập vào; model, nhãn hiệu, thông số có đơn vị và điều khiển bằng máy tính được lấy từ mô tả. Tên theo từng giả định HS được ghi riêng, kèm điều kiện áp dụng. Các trường chưa khai nằm ngoài câu tên đề xuất. Biểu mẫu bổ sung là tùy chọn; không tự xác nhận xuất xứ hay tình trạng mới.
- API thật không nhập biểu mẫu: servo trả CONDITIONAL với **85015119, 85015219, 85015229, 85015239, 85015390**; crochet trả COMPLETED **84479010**. Cả hai có bốn nguồn, tên hàng và kết quả đọc lại khớp dữ liệu đã lưu. Tệp kiểm chứng: `.logs/verified-automatic-declaration/servo-invoice-result.json` và `crochet-machine-result.json`.
- Bộ Python đạt 195 bài trước bài bổ sung về cách viết mã; 14 bài kiểm tra hiểu nghĩa và servo, gồm bài bổ sung đó, đều đạt. Tổng hiện tại 196 bài. Backend 44 bài đạt; 19 bài khai báo đạt lại sau khi hoàn thiện nhãn thông số. TypeScript và render React các kết quả thực đạt.

## Giấy trang trí phủ PU và trình bày kết quả (10/10/2026)

### Nguyên nhân và cách sửa

- Tái hiện các kết quả đã lưu không có mã hợp lệ: bước hiểu mặt hàng suy rộng PU sang giấy phủ plastic và giữ các yêu cầu về tẩy trắng/dạng cuộn dù đang phân tích sai nhánh. Mô hình có thể trả mã trong văn bản nhưng đặt trong phương án có `assumptions: []`; bước kiểm tra phương án loại dòng đó, dẫn đến không có kết quả.
- Đọc đồng thời hàng nhập là giấy trang trí, lớp xử lý bề mặt PU, khổ 1270MM và công dụng dán giả vân gỗ lên ván. Giữ vai trò vật liệu, hoa văn và bề mặt sử dụng riêng. Đối chiếu mục (D) về giấy trang trí bề mặt, nội dung 48.11 và các nhánh quốc gia; không quy tất cả tên PU thành một loại hàng.
- Khi khổ đã vượt cả giới hạn cuộn và tờ của nhánh kích thước nhỏ, không đòi thêm dạng cuộn/tờ để phân biệt cùng một mã. Không thêm điều kiện tẩy trắng hoặc ngưỡng 150g/m² của nhánh giấy phủ plastic vào nhánh giấy trang trí. Giữ nguyên `30G~45G`, không biến ký hiệu G thành đơn vị g/m² đã được xác nhận.
- Chỉ hoàn tất khi mã tám số có trong danh mục và truy xuất được nội dung nhóm, mục giấy trang trí, Quy tắc 1 và Quy tắc 6. Các mô tả khai rõ phủ màng plastic, tự dính, dán tường, phủ sàn, cắt hình khác hoặc lớp plastic vượt một nửa tổng độ dày đi qua nhánh phù hợp; không kế thừa mã của ca giấy trang trí.
- Schema và lời nhắc thống nhất `assumed_attributes`; chỉ dùng thuộc tính còn thiếu có thể làm đổi mã. Kết quả đủ điều kiện có `hypotheses: []`, `missing_information: []`. Nhánh inverter giữ kiểu biến đổi đã khai ngoài giả định; chỉ giả định điều kiện công dụng/nhánh chuyên biệt còn thiếu, và hoàn tất khi đã đủ dữ kiện.
- Bước tra cứu bổ sung giữ phương án và danh mục đầu tiên khi lượt phân tích tiếp theo không còn đề xuất dùng được. Mã dễ nhầm có thể thuộc nhánh đã loại: kiểm tra chúng trong danh mục gốc để giải thích, giữ tách biệt với mã được phép đề xuất.
- Tên khai báo giữ lớp phủ, khổ, quy cách và công dụng lấy từ câu đã nhập; ghi `Không nhãn hiệu` khi người dùng khai rõ. Loại phần chất liệu lặp ngay trong tên, giữ tình trạng mới đã khai, không tự bổ sung model hoặc xuất xứ.

### Hiển thị

- Mã đề xuất lớn, nằm đầu thẻ kết quả. Trường hợp đủ thông tin hiển thị tên hàng, thuế đúng mã, lý do có nguồn và mã dễ nhầm; không có thẻ giả định.
- Trường hợp thiếu thông tin hiển thị từng thẻ phương án: mã, phần giả định, lý do, tên hàng theo phương án và thuế tương ứng. Dữ kiện đã khai nằm ở phần chung. Không dùng một thuế suất của phương án đầu cho các mã còn lại.
- Bộ phân loại riêng hiển thị đủ từng mặt hàng và thuế từng mã. Khi nhiều phương án dùng cùng mã, tên khai báo được ghép theo đúng nhãn/điều kiện của phương án đó.
- Bỏ bảng ngang dài và phần kết quả trùng trên trang chính. Câu hỏi ngắn, chi tiết danh mục, sáu nhóm tên hàng, chứng từ và nguồn dài có thể mở khi cần; bấm số nguồn sẽ mở phần trích dẫn.
- Phản hồi vẫn dùng được cả khi phân loại có điều kiện; mỗi lần tra cứu mới xóa mã sửa và thông báo phản hồi của lượt trước.

### Kiểm chứng

- **227 kiểm thử Python, 47 kiểm thử backend, 7 kiểm thử hiển thị đạt**. Backend build, TypeScript frontend và biên dịch CSS đạt. React render đạt với giấy PU, biến thể xuống dòng, crochet, servo, bộ quà, inverter, van và thực phẩm.
- Kiểm tra tại chỗ xuyên suốt bằng danh mục và nội dung nguồn đã chụp từ DB, với câu trả lời AI cố tình sai: hai biến thể giấy PU trả `COMPLETED / 48119099`, không có giả định hay thuộc tính HS còn thiếu; có bốn nguồn và các mã dễ nhầm `48115999`, `48119049` kèm lý do. Tên hàng giữ đủ PU, 1270MM, 30G~45G, công dụng, không nhãn hiệu và mới 100%.
- Tệp kiểm chứng: `.logs/verified-paper-local/paper-result.json`, `paper-multiline-result.json`; các bản render có đuôi `-view.html`. Script `verify-paper-local.py` và `verify-paper-local.cjs` sử dụng dữ liệu đã chụp, không gọi AI từ xa, không ghi vào DB. Đây là kiểm tra tại chỗ, không phải xác minh API đang chạy.
- Dịch vụ AI đã được khởi động lại với bản sửa; frontend, backend và kiểm tra sẵn sàng của AI đều đạt. Kiểm tra qua API thật trả `COMPLETED / 48119099`, không có giả định hay thuộc tính HS còn thiếu, có bốn nguồn, tên hàng giữ đủ dữ kiện và thuế khớp mã. Đọc lại DB xác nhận phân tích đã lưu khớp kết quả trả về. ID: `71be3299-d34a-4e65-a1ff-06d5b5210967`; tệp `.logs/verified-paper-live/paper-result.json`, script `.logs/verify-paper-live.py`.
- Công cụ trình duyệt không khởi tạo được trong phiên này; kiểm tra hiển thị dùng React render và TypeScript, chưa có kiểm tra ảnh chụp/tương tác trình duyệt thực.

## Phân tích nhiều mặt hàng (10/10/2026)

- Thêm bước nhận diện danh sách trước phân loại, hỗ trợ tối đa 10 mặt hàng, tổng 20.000 ký tự và từng món 2.000 ký tự. Tách theo nghĩa toàn mô tả: thông số/model nhiều dòng đi cùng một món, bộ quà tặng được giữ nguyên để xét quy tắc HS. Không phân loại chung các món độc lập thành một mã.
- Kiểm tra các đoạn do AI trả về khớp nguyên văn, theo thứ tự và bao phủ toàn mô tả; không chấp nhận bỏ sót hay tự thêm số liệu. Thông tin chung chỉ được lặp cho mọi món khi có chỉ dấu khai chung rõ ràng. Trường hợp không kiểm chứng được cách tách hoặc vượt giới hạn cần sửa danh sách; giữ nguyên mô tả, không cắt bỏ phần cuối. Cho phép các tên ngắn như `Vớ`, `Áo` qua luồng phân tích.
- Có trình sửa danh sách để thêm/xóa, điều chỉnh mô tả và khai thông tin riêng. Biểu mẫu một mặt hàng không tự sao chép chất liệu/model/nhãn hiệu sang các món khác. Tài liệu sản phẩm được đọc tối đa 20.000 ký tự, vượt giới hạn báo lỗi thay vì cắt ở 1.600 ký tự như trước.
- Kết quả xuất hiện lần lượt trong thẻ riêng, tiêu đề có tên, mã và trạng thái; thẻ đầu mở sẵn, các thẻ còn lại thu gọn. Nút mở/thu gọn từng thẻ và toàn bộ, tiến độ xử lý, thử lại riêng món lỗi. Một món lỗi không ngăn các món còn lại. Mỗi món có thuế, tên khai báo, nguồn và phản hồi riêng; ID trích dẫn và trường biểu mẫu không trùng nhau.
- Lưu từng phân tích qua quy trình hiện có, giữ kiểm tra danh mục/nguồn/quyền truy cập. Có liên kết mở lại cả danh sách đã lưu. Tiêu đề thẻ dùng cùng bộ xác định trạng thái/mã với nội dung, kể cả dữ liệu cũ có trạng thái hoàn tất nhưng vẫn chứa giả định.
- API thật tách giấy PU và crochet đúng hai mô tả, giữ đủ thông số; trả lần lượt `COMPLETED / 48119099` và `COMPLETED / 84479010`, không thêm giả định. Đọc lại DB khớp phân tích. Bộ quà caravat/vớ và máy crochet nhiều dòng giữ nguyên một sản phẩm. Kiểm tra thông tin chung `Tất cả hàng mới 100%` giữ đúng trên hai món mà không trộn model PU-500/V-300. Trang danh sách trả HTTP 200.
- Kiểm chứng tại `.logs/verified-product-batch`: `prepared-items.json`, `paper-result.json` (ID `df47304b-0452-47a6-9a4d-61358430c52f`), `crochet-result.json` (ID `97d9c0be-e0b7-44f3-8912-f9566223bb2b`), `shared-items.json` và bản render `batch-view.html`. Script `.logs/verify-batch-live.py`, `.logs/check-batch-ready.py`, `.logs/render-batch-ui.cjs`.
- Bộ Python toàn phần 237 bài đạt trước bài bổ sung về danh sách quá 10 món; 9 bài tách danh sách, gồm bài bổ sung, đạt. Backend 50 bài và frontend 11 bài đạt; TypeScript frontend, backend build và render hai kết quả thực đạt. Công cụ Browser vẫn không khởi tạo được, nên chưa kiểm tra tương tác/ảnh chụp trong trình duyệt thực.

### Sửa nhận diện 10 dòng invoice inverter/servo

- Lượt thử đầu tiên bằng API nhận đúng 10 dòng, nên lỗi báo một mặt hàng không tái hiện ổn định. Rà soát thấy hai luồng có thể gộp sai: bước tách dựa vào AI có thể nhận cả danh sách là một món hoặc giữ một ô khi kiểm tra đoạn thất bại; khi dán danh sách vào một thẻ sửa đã mở, nút phân tích gửi nguyên thẻ và bỏ qua nhận diện lại.
- Thêm tách trực tiếp các dòng invoice đánh số tăng dần, có model hoặc cột số lượng/đơn giá/thành tiền. Giữ nguyên toàn bộ nội dung từng dòng và thứ tự; các tên hàng giống nhau và model lặp vẫn là các mục riêng. Các mục thông số, thành phần của bộ hoặc dữ kiện khai chung tiếp tục qua bước hiểu nghĩa; không tự tách chỉ vì có số thứ tự. `SET` trong cột số lượng không xác lập bộ bán lẻ, các số trong model và giá không xác nhận công suất.
- Trình sửa nhận diện lại danh sách có đánh số trước khi phân tích. Mô tả chưa tách được ghi là nội dung cần kiểm tra, không xác nhận số mặt hàng bằng số ô. Thông tin bổ sung chưa gán vẫn được giữ để tránh sao chép model/chất liệu sang mọi món. Tiêu đề kết quả có thêm model; tên model loại cột số lượng và giá khỏi invoice cùng dòng.
- Kiểm tra đúng dữ liệu người dùng: **4 inverter + 6 servo = 10 mặt hàng**, cả ô nhập chính và ô sửa. Luồng frontend thực gọi API phân tích lần lượt và lưu 10 ID riêng; cả 10 có đề xuất hợp lệ và nguồn, model giữ đúng từng món, đọc lại DB khớp kết quả. Mỗi inverter có 2 phương án (ưu tiên `85044090`), mỗi motor có 5 phương án; thông số điện cần phân biệt chưa được suy ra từ model.
- **243 bài Python, 51 bài backend, 14 bài frontend đạt**; TypeScript frontend và backend build đạt. Tệp mẫu `ai-service/tests/fixtures/invoice-ten-products.txt`; kiểm chứng `.logs/verified-ten-invoice/prepared-items.json`, `item-1-result.json` đến `item-10-result.json`, `batch-state.json` và `batch-view.html`. Script `.logs/verify-ten-invoice-live.cjs` dùng hàm xử lý danh sách của frontend với API thật; `.logs/render-ten-invoice-ui.cjs` kiểm tra 10 thẻ, model từng tiêu đề và ID/đích nguồn riêng. Chưa có kiểm tra thao tác hoặc ảnh chụp trình duyệt thực.

## Dự phòng OpenRouter miễn phí

- OpenRouter thay DeepSeek làm dự phòng đang dùng. Chat chính trả HTTP 429 chuyển sang OpenRouter; áp dụng cùng quy trình hiểu nghĩa, phân tích, kiểm tra mã và nguồn. Gemini được thử lại sau thời gian chờ quota; một lượt phân tích giữ nguyên nhà cung cấp đã chuyển.
- Chỉ lấy model `openrouter/free` hoặc `:free` có toàn bộ giá bằng 0, xác minh hỗ trợ JSON, cập nhật danh sách mỗi 5 phút. Mỗi yêu cầu giới hạn giá prompt/completion/request/image bằng 0; không dùng model trả phí khi free hết quota.
- Embedding vẫn dùng Gemini. Không trộn mô hình vector; worker đang giữ lịch tự tiếp tục do người dùng chọn.
- 190 kiểm thử Python đạt, gồm chuyển quota, thời gian thử lại, giữ đầu vào, sửa JSON, chặn model trả phí/giá thiếu/phí theo request và giữ embedding ở nhà cung cấp chính.
- API OpenRouter thật xác thực HTTP 200; tìm thấy 16 model/tuyến miễn phí. Phép thử giả lập quota Gemini gọi chat thành công bằng `liquid/lfm-2.5-2.6b:free`, chi phí API báo **0**. Tệp danh sách: `.logs/openrouter-free-models.json`.
- Người dùng đã cho phép gửi mô tả sản phẩm và các đoạn trích cần thiết của 3 tài liệu pháp lý sang OpenRouter để phân tích khi Gemini hết quota. Ứng dụng đã khởi động lại với cấu hình dự phòng mới.
- Phân loại thực với lỗi quota Gemini giả lập: crochet trả **84479010**, COMPLETED, bốn ID nguồn thực; OpenRouter dùng `nvidia/nemotron-3-super-120b-a12b:free`, chi phí trả về **0**. Phép thử dùng cùng bước hiểu nghĩa, truy xuất DB và kiểm tra phân loại; không ghi thêm lịch sử tra cứu. Báo cáo: `.logs/openrouter-free-classification.json` và `.logs/openrouter-fallback-verification.json`.
