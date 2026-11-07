# Provider grok: gói SuperGrok qua Grok CLI chính hãng (ACP)

Khâu Dịch cần dùng gói SuperGrok thay vì API key tính tiền theo token, và không được làm tài khoản bị khóa. Chúng tôi thêm Provider `grok`: VideoLingo khởi chạy `grok agent stdio` (CLI chính hãng, đăng nhập sẵn bằng `grok`) và nói chuyện với nó bằng ACP (JSON-RPC qua stdio), xác thực bằng `cached_token` của CLI. Các cách khác đã bị loại: tự làm OAuth rồi gọi `api.x.ai` (phải mượn client ID của CLI, tức mạo danh), gọi `cli-chat-proxy.grok.com` (endpoint không công bố), dùng OpenCode làm trung gian. Khi cần trả theo token thì vẫn dùng được `XAI_API_KEY` với `https://api.x.ai/v1` qua Provider `openai`.

Mỗi profile được gắn một hàm `complete(prompt) -> str` (`LLMProfile.complete`). `ask_gpt` gọi hàm này thay cho client `OpenAI`, còn phần parse JSON, `valid_def` và cache vẫn dùng chung. Mỗi `(command, model, reasoning_effort)` có một tiến trình agent sống lâu, mỗi request mở một session ACP mới. Một tiến trình chạy được nhiều session song song (spike: 4 session mất 16s, 4 request tuần tự mất 38s).

Agent mặc định là coding agent. Nếu để nguyên, nó tự gọi web search mà không gửi `request_permission`, đọc `~/.claude/CLAUDE.md`, và tốn 108k input token cho một chunk 5 dòng. Vì vậy việc chặn tool nằm ở cấu hình chứ không ở bước từ chối permission:

- biến môi trường tắt việc đọc rule của Claude/Cursor, `GROK_BACKEND_SEARCH`, `GROK_WEB_FETCH`, `GROK_SESSION_SEARCH`;
- `GROK_CONFIG` chọn model và `default_reasoning_effort` (cờ `--model` không có tác dụng trên route này);
- `--agent-profile core/utils/grok_agent_profile.md` (`tools: Read`) và `_meta.systemPromptOverride` thay system prompt của coding agent, giảm input xuống khoảng 10k token;
- client khai `fs`/`terminal` = false. Nếu agent vẫn gọi tool, request bị hủy và báo `GrokToolUseError`; nếu agent xin quyền thì client từ chối.

## Consequences

- Phụ thuộc vào Grok CLI: các biến môi trường, `systemPromptOverride` và `--agent-profile` là giao diện của CLI phiên bản 1.0.x, có thể đổi khi CLI tự cập nhật. Khi đó test giả lập vẫn xanh, chỉ chạy thật mới phát hiện được.
- CLI giữ lại mọi session ACP (khoảng 80 KB mỗi request) kể cả sau `session/close`. `prune_sessions` xóa những gì CLI lưu cho thư mục làm việc riêng của VideoLingo (`<tmp>/videolingo-grok`) mà không có ghi mới quá 60 giây.
- `costUsdTicks` trong `grok usage <sessionId>` là giá quy theo giá API, chưa biết quy đổi sang hạn mức của gói thế nào. Model `-build-fast` bị tính gấp đôi vào gói.
- Sửa profile grok trên sidebar sẽ bỏ khóa `command` vì form không có ô này. Chỉ ảnh hưởng nếu đã đặt `command` khác `grok`.
