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
| `core/utils/llm_profile.py` | F7 — giải quyết Profile đang dùng (`api.profile` → `llm_profiles`) thành model, base_url, credential, JSON mode, `reasoning_effort` |
| `tests/test_llm_profile.py` | Test cho F7 (qua seam `ask_gpt`, client OpenAI giả) |
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
| `core/utils/ask_gpt.py` | F7 — import resolver; model, base_url, credential, JSON mode và `reasoning_effort` lấy từ Profile đang dùng; base_url chỉ qua `normalize_base_url` khi profile cho phép | 8 |
| `tests/test_backlog_fixes.py` | F7 — `_check_api` patch thêm `load_key`/`load_key_or` của `llm_profile` | 2 |
| `config.yaml` | khóa `tts_max_workers`; khóa `whisper.soniox_api_key` và ghi chú runtime; mục `soniox_tts:` | 3 + 12 |
| `config.example.yaml` (F7) | khóa `api.profile`; mục `llm_profiles:` mẫu | 2 + 14 |

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

## Cấu hình F7 (LLM profile)

Khai báo nhiều **LLM profile** có tên trong `llm_profiles` và chọn **Profile đang dùng** bằng `api.profile`. `api.profile` trống hoặc vắng thì dùng **Profile custom** (mục `api:` gốc của upstream), chạy y như trước: base_url vẫn qua chuẩn hóa, key từ `api.key`. Quyết định: [`docs/adr/0001-llm-profiles.md`](docs/adr/0001-llm-profiles.md).

```yaml
api:
  profile: 'openrouter-free'   # '' = Profile custom (mục api: này)
  key: ''                      # các khóa upstream giữ nguyên, chỉ dùng cho Profile custom
  base_url: 'https://openrouter.ai/api/v1'
  model: 'deepseek/deepseek-chat-v3.1:free'
  llm_support_json: false
max_workers: 4
llm_profiles:
  openrouter-free:
    provider: openrouter                    # openrouter có base_url mặc định https://openrouter.ai/api/v1
    model: 'deepseek/deepseek-chat-v3.1:free'
    api_key_env: 'OPENROUTER_API_KEY'       # biến môi trường chứa key, đọc trước
    api_key: ''                             # key dự phòng, nên để trống
    llm_support_json: false
    max_workers: 1
  my-proxy:
    provider: openai                        # Provider khác openrouter phải khai báo base_url
    base_url: 'https://llm.example.com/v1'
    model: 'some-thinking-model'
    api_key_env: 'MY_PROXY_API_KEY'
    reasoning_effort: low                   # giới hạn token thinking
```

Mỗi profile bắt buộc có `provider` và `model`. Các khóa ghi đè còn lại, nếu thiếu thì lấy giá trị chung:

| Khóa trong profile | Giá trị chung khi thiếu |
|---|---|
| `base_url` | base_url mặc định của Provider (`openrouter`); Provider khác thì bắt buộc |
| `llm_support_json` | `api.llm_support_json` |
| `reasoning_effort` | không gửi tham số `reasoning_effort` |
| `max_workers` | `max_workers` (số luồng theo profile được áp dụng ở #4) |

- **Thứ tự tìm key:** biến môi trường ghi trong `api_key_env` → `llm_profiles.<tên>.api_key`. Không tìm thấy thì lỗi nêu tên profile và cả hai chỗ đặt key. Profile custom vẫn dùng `api.key` (máy chủ local như Ollama không cần key).
- **Đổi profile:** sửa `api.profile` thành tên khác trong `llm_profiles`, hoặc `''` để quay về Profile custom. Tên không có trong `llm_profiles` thì lỗi liệt kê các profile đang có.
- **Cache không phân biệt model:** câu trả lời LLM được cache theo prompt trong `output/gpt_log`. Đổi profile rồi dịch lại cùng video sẽ dùng lại kết quả cũ; xóa `output/gpt_log` nếu muốn dịch lại bằng profile mới.
- Thêm Provider mới (ví dụ `vertex` ở F8): thêm một mục vào `PROVIDERS` trong `core/utils/llm_profile.py`.
