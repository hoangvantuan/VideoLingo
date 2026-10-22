# CUSTOM — các thay đổi của fork `hoangvantuan/VideoLingo`

Yêu cầu và lộ trình: [`docs/PRD-custom.md`](docs/PRD-custom.md). Khi rebase lên upstream, kiểm tra các file trong bảng "Móc nối vào file lõi" trước.

## File mới (không xung đột với upstream)

| File | Mục đích |
|---|---|
| `core/asr_backend/soniox_asr.py` | F1 — runtime ASR `soniox` (Soniox async API `stt-async-v5`) |
| `tests/test_soniox_asr.py` | Test cho F1 |
| `core/tts_backend/soniox_tts.py` | F6 — phương thức lồng tiếng `soniox_tts` (Soniox TTS `tts-rt-v2`) |
| `core/st_utils/soniox_tts_settings.py` | F6 — giao diện chọn giọng (lọc theo accent/giới tính), ngôn ngữ, tốc độ |
| `tests/test_soniox_tts.py` | Test cho F6 |
| `tests/test_tts_max_workers.py` | Test giới hạn số request TTS song song |
| `core/utils/original_audio.py` | F10 — lồng tiếng kiểu Thuyết minh: đọc `original_volume`, dò track âm thanh của video, dựng bộ lọc trộn |
| `core/st_utils/original_volume_setting.py` | F10 — thanh trượt "Âm lượng gốc (Thuyết minh)" trong Dubbing Settings |
| `tests/test_original_volume.py` | Test cho F10 (lệnh FFmpeg của bước ghép video, không chạy FFmpeg thật) |
| `CUSTOM.md` | Tài liệu này |
| `docs/PRD-custom.md` | PRD của fork |

## Móc nối vào file lõi

Các dòng thêm vào đều có chú thích `# custom`.

| File | Thay đổi | Số dòng |
|---|---|---|
| `core/_2_asr.py` | thêm `"soniox"` vào danh sách runtime; kiểm tra key trước khi chuẩn bị media; nhánh `elif runtime == "soniox"` | 6 |
| `core/st_utils/sidebar_setting.py` | thêm `"soniox"` vào ô chọn runtime (nhãn cố định, không qua `t()`) và ô nhập key | 4 |
| `core/tts_backend/tts_main.py` | import + nhánh `elif TTS_METHOD == 'soniox_tts'` | 3 |
| `core/st_utils/tts_settings.py` | provider `"Soniox"` trong `PROVIDERS` và `KEY_PATHS` | 2 |
| `core/st_utils/sidebar_setting.py` (F6) | nhãn `soniox_tts` + nhánh gọi `soniox_tts_settings.render()` | 4 |
| `core/_10_gen_audio.py` | giới hạn số luồng TTS bằng `tts_max_workers` (VieNeu-TTS chỉ phục vụ 1 stream, gửi song song bị HTTP 429 `queue full`) | 1 |
| `core/_12_dub_to_vid.py` | F10: import `original_audio`; `original_volume > 0` thay track nền demucs bằng track âm thanh gốc của video | 7 |
| `api.py` | F10: field tùy chọn `original_volume` (0–1) của `POST /run`, ghi vào `config.yaml` | 3 |
| `core/st_utils/sidebar_setting.py` (F10) | gọi `original_volume_setting.render()` cuối Dubbing Settings | 2 |
| `tests/test_api.py` | F10: test `test_run_saves_original_volume` | 1 hàm |
| `config.yaml` | khóa `tts_max_workers`; khóa `whisper.soniox_api_key` và ghi chú runtime; mục `soniox_tts:`; khóa `original_volume` (F10) | 3 + 12 + 3 |

## Cấu hình F1 (Soniox)

```yaml
whisper:
  runtime: 'soniox'
  language: 'en'        # hoặc 'ja', hoặc 'auto' (gợi ý en + ja, bật nhận diện ngôn ngữ)
  soniox_api_key: ''    # để trống, đặt biến môi trường SONIOX_API_KEY
```

- Key đọc theo thứ tự: `SONIOX_API_KEY` → `whisper.soniox_api_key`.
- File âm thanh và transcription trên Soniox luôn bị xóa sau mỗi đoạn, kể cả khi lỗi.
- Cache ASR dùng nhánh chung của `transcription_cache.cache_key`, nên đổi phiên bản package local (qwen-asr, transformers, demucs…) sẽ làm mất cache Soniox. Ngược lại, đổi `MODEL` trong `soniox_asr.py` **không** tự làm mất cache — khi đổi model, xóa `.cache/asr` hoặc chấp nhận dùng kết quả cũ. Chấp nhận để không phải sửa thêm file lõi.

## Cấu hình F6 (Soniox TTS)

Chọn trên giao diện: **Dubbing Settings → TTS Provider = Soniox**, rồi chọn giọng. Hoặc sửa tay:

```yaml
tts_method: 'soniox_tts'
soniox_tts:
  api_key: ''        # để trống thì dùng SONIOX_API_KEY hoặc whisper.soniox_api_key
  voice: 'Linh'      # giọng tiếng Việt có sẵn: Linh, Mai, Huong
  language: 'vi'
  speed: 1.0         # 0.7–1.3
  model: 'tts-rt-v2'
```

- Danh sách giọng = giọng clone của project (`GET /v1/voices`, chỉ lấy giọng `ready` cho model đang dùng, nhóm accent `cloned`) + giọng có sẵn (`GET /v1/shared-voices`). Cả hai đều có phân trang; danh sách được cache 1 giờ trên giao diện, giọng mới clone sẽ hiện sau tối đa 1 giờ hoặc khi khởi động lại.
- Giọng clone được lưu vào `soniox_tts.voice` bằng ID (UUID).
- Soniox trả WAV dạng stream với kích thước RIFF/data = `0xFFFFFFFF`; `fix_wav_sizes` ghi lại kích thước thật trước khi lưu file.
- Nhãn trên giao diện là chữ cố định, không qua `t()`, nên không phải sửa file bản dịch.
- Test upstream `test_mai_sidebar_*` đọc `config.yaml` đang dùng; chúng sẽ lỗi nếu `whisper.runtime` cục bộ khác `local`. Chạy test trên `config.yaml` sạch để đánh giá đúng.

## Cấu hình F10 (Thuyết minh)

Video lồng tiếng vẫn nghe được âm thanh gốc (cả giọng gốc) ở mức nhỏ cố định, giọng Việt đè lên trên.
Chỉnh trên giao diện: **Dubbing Settings → Âm lượng gốc (Thuyết minh)**, qua `POST /run` (`original_volume`), hoặc sửa tay:

```yaml
original_volume: 0.25   # 0–1, nhân thẳng lên track âm thanh gốc; 0 = cách trộn của upstream
```

- Nguồn âm thanh gốc là track âm thanh đầu tiên của chính file video (không dùng bản audio trích cho ASR, vì bản đó không có khi đưa SRT vào thay ASR).
- `original_volume > 0`: trộn `âm thanh gốc × original_volume` + giọng lồng tiếng đã chuẩn hóa, **thay cho** track nền demucs (tránh lặp nhạc nền). `amix` dùng `normalize=0` nên giọng lồng tiếng không bị chia đôi; thời lượng theo track gốc (= video). Chạy được cả khi không bật demucs.
- `original_volume = 0` hoặc vắng khóa: lệnh trộn giống hệt upstream (có track nền demucs thì trộn, không thì chỉ giọng lồng tiếng).
- Video không có track âm thanh: chỉ xuất giọng lồng tiếng, kèm cảnh báo.
- Mặc định trong code là `0`; `config.example.yaml` của fork đặt `0.25`. Âm lượng gốc cố định suốt video; tự hạ khi có giọng Việt (sidechain ducking) chưa làm.
- Nhãn thanh trượt là chữ cố định, không qua `t()`.
