# LLM profile đặt cạnh mục `api:` của upstream

Fork cần đổi qua lại nhiều Provider cho Khâu Dịch (OpenRouter, Vertex AI…) mà không phải gõ lại key/base_url/model. Chúng tôi thêm danh sách `llm_profiles` và khóa chọn `api.profile`, đồng thời giữ nguyên mục `api:` của upstream làm **Profile custom** ngầm định (dùng khi `api.profile` trống), thay vì sửa trực tiếp cấu trúc mục `api:`. Lý do: giảm xung đột khi rebase upstream (PRD mục 7) và giữ các ô nhập API gốc trên sidebar dùng được. Mỗi profile được ghi đè `llm_support_json`, `max_workers`, `reasoning_effort`; khóa thiếu thì lấy giá trị chung.

Profile Vertex vẫn đi qua client `OpenAI` trong `ask_gpt` (endpoint `endpoints/openapi` của Vertex, token từ service account qua `google-auth`) để `ask_gpt` chỉ có một đường gọi. URL Vertex được dựng từ `vertex.project`/`location` và không đi qua `normalize_base_url`, vì hàm này đổi mọi URL chứa chuỗi `ark` sang endpoint Volcano Engine.

## Consequences

- Có hai nơi khai báo LLM: mục `api:` (Profile custom) và `llm_profiles`. Người đọc cấu hình cần biết `api.profile` quyết định nơi nào có hiệu lực.
- Cache câu trả lời LLM không xét model: đổi profile giữa chừng một video sẽ dùng lại kết quả cũ, trừ khi xóa `output/gpt_log`.
- Nếu Gemini không gọi được qua endpoint kiểu OpenAI (chưa xác minh), phải thêm nhánh `google-genai` và ADR này cần được thay thế.
