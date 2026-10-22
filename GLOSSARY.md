# VideoLingo Custom

Fork của VideoLingo: biến video nước ngoài thành video có phụ đề và lồng tiếng Việt, mỗi khâu chạy trên một dịch vụ bên ngoài có thể thay được.

## Khâu xử lý

**Khâu (Stage)**:
Một bước của pipeline có thể giao cho dịch vụ bên ngoài: ASR, Dịch, Lồng tiếng.
_Avoid_: step, module

**ASR**:
Khâu nhận dạng lời nói thành văn bản có timestamp từng từ.
_Avoid_: STT, transcribe (khi nói về khâu)

**Dịch**:
Khâu dùng LLM để chia câu, tóm tắt và dịch phụ đề.
_Avoid_: GPT, API (khi nói về khâu)

**Lồng tiếng**:
Khâu sinh giọng đọc tiếng Việt cho từng câu phụ đề.
_Avoid_: dubbing, TTS (khi nói về khâu)

**Thuyết minh**:
Kiểu Lồng tiếng giữ âm thanh gốc của video ở mức nhỏ cố định, giọng Việt đè lên trên.
_Avoid_: voice-over, lồng tiếng đè

**Âm lượng gốc**:
Mức âm thanh gốc giữ lại khi Thuyết minh, tính bằng tỉ lệ so với âm lượng gốc (0 = tắt Thuyết minh).
_Avoid_: background volume, ducking

## Provider

**Provider**:
Hãng cung cấp dịch vụ cho một hoặc nhiều Khâu (OpenRouter, Vertex AI, Soniox, VieNeu).
_Avoid_: vendor, backend, runtime (khi nói về hãng)

**LLM profile**:
Một cấu hình có tên cho Khâu Dịch, gồm Provider, model và cách lấy thông tin xác thực.
_Avoid_: preset, account

**Profile custom**:
LLM profile ngầm định lấy từ mục cấu hình API gốc của upstream, được dùng khi chưa chọn profile nào.
_Avoid_: legacy profile, profile mặc định

**Profile đang dùng**:
LLM profile mà Khâu Dịch sử dụng cho lần chạy hiện tại.
_Avoid_: default profile

## Playlist

**Playlist**:
Danh sách video lấy từ một URL mà yt-dlp đọc được (playlist, kênh), mỗi video nhận diện bằng video ID.
_Avoid_: danh sách phát, list

**Lượt chạy playlist**:
Một lần xử lý tuần tự các video đã chọn của một Playlist với cùng một bộ cài đặt; là đơn vị được tạm dừng, dừng và tiếp tục.
_Avoid_: job, batch, queue, hàng đợi

**Trạng thái video**:
Tình trạng của một video trong Lượt chạy playlist: Chờ, Đang chạy, Xong, Lỗi, hoặc Không khả dụng (private, đã xoá, bị chặn vùng).
_Avoid_: status, kết quả
