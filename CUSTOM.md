# CUSTOM — các thay đổi của fork `hoangvantuan/VideoLingo`

Yêu cầu và lộ trình: [`docs/PRD-custom.md`](docs/PRD-custom.md). Khi rebase lên upstream, kiểm tra các file trong bảng "Móc nối vào file lõi" trước.

## File mới (không xung đột với upstream)

| File | Mục đích |
|---|---|
| `core/asr_backend/soniox_asr.py` | F1 — runtime ASR `soniox` (Soniox async API `stt-async-v5`, qua SDK chính thức `soniox`) |
| `tests/test_soniox_asr.py` | Test cho F1 |
| `core/tts_backend/soniox_tts.py` | F6 — phương thức lồng tiếng `soniox_tts` (Soniox TTS `tts-rt-v2`, qua SDK chính thức `soniox`) |
| `core/st_utils/soniox_tts_settings.py` | F6 — giao diện chọn giọng (lọc theo accent/giới tính), ngôn ngữ, tốc độ |
| `tests/test_soniox_tts.py` | Test cho F6 |
| `core/utils/llm_profile.py` | F7 — giải quyết Profile đang dùng (`api.profile` → `llm_profiles`) thành model, base_url, credential, JSON mode, `reasoning_effort` |
| `tests/test_llm_profile.py` | Test cho F7 (qua seam `ask_gpt`, client OpenAI giả) |
| `core/utils/config_errors.py` | F7/F8 — `ConfigError`: lỗi cấu hình (profile, credential Google, 401/403), `except_handler` không thử lại |
| `tests/test_llm_max_workers.py` | Test cho F7: số luồng Khâu Dịch theo Profile đang dùng (`llm_max_workers()`) |
| `core/st_utils/llm_profile_setting.py` | F7 — ô chọn Profile đang dùng trong LLM Configuration của sidebar, hiện Provider/model, ghi `api.profile` |
| `tests/test_llm_profile_setting.py` | Test cho ô chọn profile (Streamlit `AppTest`, config giả) |
| `core/utils/original_audio.py` | F10 — lồng tiếng kiểu Thuyết minh: đọc `original_volume`, dò track âm thanh của video, dựng bộ lọc trộn |
| `core/st_utils/original_volume_setting.py` | F10 — thanh trượt "Âm lượng gốc (Thuyết minh)" trong Dubbing Settings |
| `tests/test_original_volume.py` | Test cho F10 (lệnh FFmpeg của bước ghép video, không chạy FFmpeg thật) |
| `tests/test_tts_max_workers.py` | Test giới hạn số request TTS song song (cả `vertex_tts.max_workers`) |
| `core/utils/google_credentials.py` | F8/F9 — credential Google dùng chung: `access_token()`, `auth_headers()`, `project()`, `GoogleCredentialError` |
| `tests/test_google_credentials.py` | Test credential Google dùng chung |
| `core/tts_backend/vertex_tts.py` | F9 — phương thức lồng tiếng `vertex_tts` (Cloud Text-to-Speech REST, Chirp 3 HD) |
| `core/st_utils/vertex_tts_settings.py` | F9 — giao diện chọn giọng Cloud TTS (lọc theo `vertex_tts.language`, Chirp 3 HD trước), ngôn ngữ, tốc độ |
| `tests/test_vertex_tts_settings.py` | Test cho màn hình giọng F9 (Streamlit `AppTest`, danh sách giọng giả) |
| `tests/test_consecutive_edits.py` | Test F9/F10: hai lần sửa liên tiếp ô Vertex TTS và thanh "Âm lượng gốc" đều được lưu (widget có `key=` cố định, id không đổi khi lưu) |
| `tests/test_vertex_tts.py` | Test cho F9 (backend, liệt kê/lọc giọng, giọng mặc định, nhánh dispatcher) |
| `tests/test_vertex_llm.py` | Test cho F8 (profile Vertex qua seam `ask_gpt`, client OpenAI và credential Google giả) |
| `core/st_utils/config_fields.py` | #11 — đọc khóa mới với mặc định khai báo trong code (bằng giá trị của `config.yaml` trong repo, #22), ghi khóa (kể cả mục cha) vào `config.yaml` cũ; dùng chung cho các ô cấu hình của fork |
| `tests/test_config_fields.py` | Test cho `config_fields` |
| `core/st_utils/llm_profile_editor.py` | #11 (F7/F8) — thêm/sửa/xóa profile trong `llm_profiles`, kiểm hợp lệ; ô `vertex.project`, `vertex.location_llm` |
| `tests/test_llm_profile_editor.py` | Test cho trình sửa profile (Streamlit `AppTest`, config tạm) |
| `tests/test_sidebar_custom_settings.py` | Test nghiệm thu #11: đặt mọi khóa F7–F10 từ cả sidebar trên `config.yaml` cũ |
| `core/st_utils/advanced_settings.py` | #12 — expander **Nâng cao** cuối sidebar: mọi khóa còn lại người vận hành chỉnh được (chung, ASR, phụ đề, dịch, lồng tiếng, âm thanh) |
| `tests/test_sidebar_all_settings.py` | Test nghiệm thu #12: mỗi nhóm của **Nâng cao** ghi khóa vào `config.yaml` cũ chưa có khóa đó (Streamlit `AppTest`) |
| `core/utils/env_keys.py` | #21 — key trong `.env`: nạp `.env` cạnh `config.yaml`, thay tham chiếu `${VAR}` khi đọc, giữ tham chiếu và ghi key mới vào `.env` khi ghi (`keep_references`, `set_env`, `raw`) |
| `core/st_utils/key_input.py` | #21 — ô key của sidebar: key dạng `${VAR}` hiện tên biến, không lộ giá trị; key nhập mới vào `.env` |
| `scripts/move_keys_to_env.py` | #21 — script người dùng tự chạy: chuyển key trong `config.yaml` sang `.env` (`--dry-run`, sao lưu, quyền 600) |
| `.env.example` | #21 — tên các biến key, giá trị trống |
| `tests/test_env_keys.py` | Test #21: đọc/ghi tham chiếu `${VAR}`, `.env`, `GOOGLE_APPLICATION_CREDENTIALS` |
| `tests/test_env_key_inputs.py` | Test #21: ô key của sidebar, ô key nhà cung cấp TTS, trình sửa profile (Streamlit `AppTest`) |
| `tests/test_move_keys_to_env.py` | Test #21: script chuyển key (config tạm), `config.yaml` mẫu (`tests/fixtures/config.yaml`) và `.env.example` khớp tên biến |
| `tests/test_tracked_config.py` | Test #22: `config.yaml` của repo không chứa key thật (chỉ in tên khóa); `.gitignore` track `config.yaml`, ignore `.env`, `config.backup.yaml`, `config.before-upgrade.yaml`; `tests/fixtures/config.yaml` có mọi khóa của `config.yaml` |
| `tests/fixtures/config.yaml`, `tests/template_config.py` | #22 — bản mẫu `config.yaml` mà test đọc/chép (`TEMPLATE_CONFIG`), để test không phụ thuộc `config.yaml` của người vận hành. Sửa `config.yaml` mẫu thì làm mới: `git show HEAD:config.yaml > tests/fixtures/config.yaml` |
| `scripts/upgrade_config.py` | #22 — script người dùng tự chạy: đặt giá trị của `config.yaml` đang dùng lên bản mẫu của repo (`--dry-run`, `--template`, sao lưu `config.before-upgrade.yaml` quyền 600) |
| `tests/test_upgrade_config.py` | Test #22: script nâng cấp config (file tạm) |
| `core/utils/history_folder.py` | #14 — `merge_output(destination)`: chuyển toàn bộ `output/` (kể cả `log/`, `gpt_log/`) vào thư mục history chọn sẵn, không xoá nội dung đã có ở đích |
| `tests/test_history_destination.py` | Test #14: lưu vào thư mục history chọn sẵn giữ nội dung cũ |
| `core/playlist_run.py` | #14 — Lượt chạy playlist (ADR-0002): đọc Playlist bằng yt-dlp chế độ flat (`read_playlist`), `PlaylistRun` (`create`, `start`, `pause`, `resume`, `wait`, `snapshot`), lượt chạy chung của tiến trình (`current_run()`), file trạng thái `history/<playlist>/playlist_run.json`. Adapter `ytdlp` và `plan` thay được khi test |
| `tests/test_playlist_run.py` | Test #14: module Lượt chạy playlist với yt-dlp giả, pipeline giả, thư mục tạm |
| `core/st_utils/playlist_tab.py` | #14 — tab "Playlist": ô URL và nút đọc, chọn video, phạm vi xử lý, tiến độ `n/N` và Trạng thái video tự làm mới mỗi giây, Pause/Resume, đường dẫn history của video `Xong` |
| `core/playlist_run.py`, `core/st_utils/playlist_tab.py` (#16) | Stop (`run.stop()`: video dở chuyển vào thư mục history của nó, về `Chờ`, `output/` trống, file trạng thái `interrupted`), Tiếp tục (`load_unfinished()` tìm lượt dở trong `history/` khi mở app hoặc sau crash, không tự chạy; `run.start()` chuyển phần dở từ history về `output/`, không tải lại), Kết thúc lượt chạy (`run.end()`), một lượt mỗi lúc (`RUN_UNFINISHED`) |
| `tests/test_playlist_run_stop.py` | Test #16: Stop giữa chừng, nạp lại từ file trạng thái rồi tiếp tục, crash, kết thúc lượt chạy |
| `tests/test_playlist_rerun.py` | Test #17: đọc lại Playlist đã chạy thì video `Xong` (theo video ID trong file trạng thái) được đánh dấu `done` và bỏ chọn sẵn trên tab; video `Xong` được tick lại thì làm lại vào đúng thư mục cũ; video mới không lấy trùng thư mục của video khác |
| `CUSTOM.md` | Tài liệu này |
| `docs/PRD-custom.md` | PRD của fork |

## Móc nối vào file lõi

Các dòng thêm vào đều có chú thích `# custom`.

| File | Thay đổi | Số dòng |
|---|---|---|
| `core/_2_asr.py` | thêm `"soniox"` vào danh sách runtime; kiểm tra key trước khi chuẩn bị media; nhánh `elif runtime == "soniox"` | 6 |
| `core/st_utils/sidebar_setting.py` | thêm `"soniox"` vào ô chọn runtime (nhãn cố định, không qua `t()`) và ô nhập key (ẩn ký tự; từ #21 qua `key_input`) | 5 |
| `core/tts_backend/tts_main.py` | import + nhánh `elif TTS_METHOD == 'soniox_tts'` | 3 |
| `core/st_utils/tts_settings.py` | provider `"Soniox"` trong `PROVIDERS` và `KEY_PATHS` | 2 |
| `core/st_utils/sidebar_setting.py` (F6) | nhãn `soniox_tts` + nhánh gọi `soniox_tts_settings.render()` | 4 |
| `core/_10_gen_audio.py` | giới hạn số luồng TTS bằng `tts_max_workers` (VieNeu-TTS chỉ phục vụ 1 stream, gửi song song bị HTTP 429 `queue full`) | 1 |
| `core/utils/ask_gpt.py` | F7 — import resolver; model, base_url, credential, JSON mode và `reasoning_effort` lấy từ Profile đang dùng; base_url chỉ qua `normalize_base_url` khi profile cho phép | 8 |
| `core/utils/ask_gpt.py` (F8) | lỗi 401/403 của request được nối thêm gợi ý của profile (`auth_error_hint`, Vertex chỉ tới "Setup Google Cloud") và ném lại thành `LLMAuthError` (không thử lại) | 7 |
| `core/utils/decorator.py` | F7/F8 — import `ConfigError`; `except_handler` ném thẳng `ConfigError` như `StopTask`, không thử lại 5 lần | 2 |
| `core/_3_2_split_meaning.py` | F7 — import + số luồng chia câu theo nghĩa lấy từ `llm_max_workers()` | 2 |
| `core/_4_2_translate.py` | F7 — import + số luồng dịch lấy từ `llm_max_workers()` | 2 |
| `core/_5_split_sub.py` | F7 — import + số luồng chia phụ đề (2 chỗ) lấy từ `llm_max_workers()` | 3 |
| `tests/test_backlog_fixes.py` | F7 — `_check_api` patch thêm `load_key`/`load_key_or` của `llm_profile`; test chia phụ đề patch `llm_max_workers` | 2 + 2 |
| `config.yaml` (F7) | khóa `api.profile`; mục `llm_profiles:` mẫu (cả `base_url` dạng comment) | 2 + 16 |
| `config.yaml` (F8) | profile `gemini-lite`, `gemini-flash` trong `llm_profiles:` | 13 |
| `core/st_utils/sidebar_setting.py` (F7) | các ô nhập API gốc chuyển vào hàm lồng `custom_llm_inputs()`, chỉ gọi khi `llm_profile_setting.render()` báo đang chọn Profile custom | 5 |
| `core/_12_dub_to_vid.py` | F10: import `original_audio`; `original_volume > 0` thay track nền demucs bằng track âm thanh gốc của video | 7 |
| `docs/api.md` | F10: đoạn mô tả field `original_volume` của `POST /run`, bọc trong `<!-- custom: F10 -->` … `<!-- /custom -->` | 4 + 2 |
| `api.py` | F10: field tùy chọn `original_volume` (0–1) của `POST /run`, ghi vào `config.yaml` | 3 |
| `core/st_utils/sidebar_setting.py` (F10) | gọi `original_volume_setting.render()` cuối Dubbing Settings | 2 |
| `tests/test_api.py` | F10: test `test_run_saves_original_volume` | 1 hàm |
| `core/tts_backend/tts_main.py` (F9) | import + nhánh `elif TTS_METHOD == 'vertex_tts'` | 3 |
| `core/_10_gen_audio.py` (F9) | khi `tts_method == 'vertex_tts'`, `vertex_tts.max_workers` thay toàn bộ số luồng TTS | 1 |
| `core/st_utils/tts_settings.py` (F9) | provider `"Vertex AI"` trong `PROVIDERS` (không có trong `KEY_PATHS`: xác thực bằng credential Google) | 1 |
| `core/st_utils/sidebar_setting.py` (F9) | nhãn `vertex_tts` + nhánh gọi `vertex_tts_settings.render()` | 4 |
| `core/st_utils/sidebar_setting.py` (#11) | import + gọi `llm_profile_editor.render()` cuối LLM Configuration, sau ô chọn profile | 2 |
| `core/st_utils/sidebar_setting.py` (#12) | import + gọi `advanced_settings.render()` cuối `page_setting()`, sau Dubbing Settings | 2 |
| `requirements.txt` (F8/F9) | `google-auth` | 2 |
| `requirements.txt` (F1/F6) | `soniox` (SDK chính thức, `>=2.10,<3`) | 2 |
| `core/utils/config_utils.py` (#21) | import `env_keys`; `load_key(key, resolve=True)` nạp `.env` và thay `${VAR}` (`resolve=False` đọc nguyên văn); `update_key` ghi qua `keep_references` | 5 |
| `core/st_utils/sidebar_setting.py` (#21) | import `key_input`; ô `api.key`, `whisper.elevenlabs_api_key`, `whisper.mai_openrouter_api_key`, `whisper.mai_api_key` (và ô Soniox ở trên) đi qua `key_input` thay cho `config_input`/`st.text_input` | 6 |
| `core/st_utils/tts_settings.py` (#21) | `save_settings` ghi qua `keep_references`; ô key nhà cung cấp dạng `${VAR}` đi qua `key_input`; biến chưa đặt của phương thức cùng nhà cung cấp đọc thành rỗng | 2 + 7 |
| `config.yaml` (#21) | 11 ô key thành `${VAR:-}` (tên biến chuẩn, xem `.env.example`) | 11 |
| `requirements.txt` (#21) | `python-dotenv` | 2 |
| `tests/test_fish_audio_tts.py` (#21) | `load_key` giả nhận thêm `resolve=` | 1 |
| `.gitignore` (#22) | bỏ ignore `config.yaml` (file được track lại, chỉ chứa `${VAR}`); ignore `.env.*` trừ `.env.example`, ignore `vertex-sa.json`, `config.before-upgrade.yaml` (`.env`, `config.backup.yaml` vẫn ignore) | 6 |
| `.dockerignore` (#22) | `config.yaml` không còn bị loại khỏi image (cần cho container); loại `config.backup.yaml`, `config.before-upgrade.yaml` (có thể chứa key thật) | 3 |
| `tests/test_backlog_fixes.py`, `tests/test_dependencies.py`, `tests/test_language_support.py`, `tests/test_audio_extract_quality.py`, `tests/test_pipeline_integration.py` (#22) | đọc/chép `TEMPLATE_CONFIG` (`tests/fixtures/config.yaml`) thay cho `config.yaml` của repo; test ghép phụ đề trỏ `CONFIG_PATH` vào bản mẫu | 3 + 3 + 2 + 2 + 2 |
| `config.yaml` | khóa `tts_max_workers`; khóa `whisper.soniox_api_key` và ghi chú runtime; mục `soniox_tts:`; khóa `original_volume` (F10); (F9) mục `vertex:`, `vertex_tts:` và dòng `# *Custom: also soniox_tts, vertex_tts` dưới ghi chú `tts_method` (dòng upstream giữ nguyên) | 3 + 12 + 3 + 20 |
| `core/utils/onekeycleanup.py` (#14) | import `merge_output`; `cleanup(destination=...)` chuyển `output/` vào thư mục chọn sẵn, giữ nội dung đã có (không có `destination` thì như cũ) | 4 |
| `core/pipeline.py` (#14) | `review_terminology`, `review_translation` không tạm dừng khi runner có `unattended` (Lượt chạy playlist), dù `pause_before_translate`/`pause_after_translate` đang bật | 4 |
| `st.py` (#14) | import `playlist_tab`; `main()` chia hai tab "Single video" (luồng a→b→c cũ, thụt lề vào `with`) và "Playlist" (`playlist_tab.render()`) | 1 + 9 |
| `tests/test_ui_translations.py` (#14) | `DYNAMIC_T_ARGS` thêm `core/st_utils/playlist_tab.py` (`snapshot.current_step`, `message`; key được kiểm trong `tests/test_playlist_run.py`) | 1 |
| `translations/*.json` (#14) | 26 key của tab Playlist và Lượt chạy playlist, đủ 7 ngôn ngữ | 26 × 7 |
| `translations/*.json` (#16) | 4 key Stop/Tiếp tục/Kết thúc lượt chạy của tab Playlist, đủ 7 ngôn ngữ | 4 × 7 |

## Cấu hình F1 (Soniox)

```yaml
whisper:
  runtime: 'soniox'
  language: 'en'        # hoặc 'ja', hoặc 'auto' (gợi ý en + ja, bật nhận diện ngôn ngữ)
  soniox_api_key: '${SONIOX_API_KEY}'    # key trong .env, xem "Key trong .env"
```

- Key đọc theo thứ tự: `SONIOX_API_KEY` → `whisper.soniox_api_key`.
- Gọi Soniox qua SDK Python chính thức `soniox` (sync `SonioxClient`). SDK không tự thử lại, nên backend vẫn thử lại khi lỗi kết nối, 408, 429, 5xx (tối đa 4 lần), và tự poll trạng thái thay vì `client.stt.wait()` để `check_cancel()` vẫn hủy được trong lúc chờ.
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

- Gọi Soniox qua SDK Python chính thức `soniox` (`client.tts.generate`, `client.voices.list_all` / `list_all_shared`). SDK không tự thử lại, nên backend vẫn thử lại khi lỗi kết nối, 408, 429, 5xx.
- Danh sách giọng = giọng clone của project (`GET /v1/voices`, chỉ lấy giọng `ready` cho model đang dùng, nhóm accent `cloned`) + giọng có sẵn (`GET /v1/shared-voices`). Cả hai đều có phân trang; danh sách được cache 1 giờ trên giao diện, giọng mới clone sẽ hiện sau tối đa 1 giờ hoặc khi khởi động lại.
- Giọng clone được lưu vào `soniox_tts.voice` bằng ID (UUID).
- Soniox trả WAV dạng stream với kích thước RIFF/data = `0xFFFFFFFF`; SDK trả nguyên bytes, không sửa header, nên `fix_wav_sizes` vẫn ghi lại kích thước thật trước khi lưu file.
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

**`config.yaml` đã có từ trước:** đặt trên sidebar (xem [Cấu hình trên giao diện (F7–F10)](#cấu-hình-trên-giao-diện-f7f10)) hoặc chép khóa `api.profile` và mục `llm_profiles:` (kèm comment) từ `config.yaml` của repo; key thật đặt trong biến môi trường, `api_key` để `''`. Thiếu `llm_profiles` thì ô chọn profile không hiện và Khâu Dịch dùng Profile custom.

Mỗi profile bắt buộc có `provider` và `model`. Các khóa ghi đè còn lại, nếu thiếu thì lấy giá trị chung:

| Khóa trong profile | Giá trị chung khi thiếu |
|---|---|
| `base_url` | base_url mặc định của Provider (`openrouter`); Provider khác thì bắt buộc |
| `llm_support_json` | `api.llm_support_json` |
| `reasoning_effort` | không gửi tham số `reasoning_effort` |
| `max_workers` | `max_workers`. Áp dụng cho mọi bước song song của Khâu Dịch (chia câu theo nghĩa, dịch, chia phụ đề) qua `llm_max_workers()`; bước sinh audio không đổi |

- **Thứ tự tìm key:** biến môi trường ghi trong `api_key_env` → `llm_profiles.<tên>.api_key`. Không tìm thấy thì lỗi nêu tên profile và cả hai chỗ đặt key. Profile custom vẫn dùng `api.key` (máy chủ local như Ollama không cần key).
- **Đổi profile trên giao diện:** sidebar → **LLM Configuration** → ô **Profile đang dùng**. Danh sách gồm *Profile custom (mục api: gốc)* và các profile trong `llm_profiles`; dưới ô hiện Provider và model của profile đang chọn. Lựa chọn được ghi ngay vào `api.profile` và lượt dịch tiếp theo dùng profile đó. Các ô nhập API gốc (key, base_url, model, JSON mode) chỉ hiện khi chọn Profile custom; profile có tên có nút **Check API** riêng. Không có `llm_profiles` thì ô chọn không hiện. Thêm, sửa, xóa profile: xem [Cấu hình trên giao diện (F7–F10)](#cấu-hình-trên-giao-diện-f7f10).
- **Số luồng không cần credential:** `llm_max_workers()` đọc thẳng `llm_profiles.<tên>.max_workers`, không dựng profile, nên không nạp credential Google.
- **Đổi profile bằng tay:** sửa `api.profile` thành tên khác trong `llm_profiles`, hoặc `''` để quay về Profile custom. Tên không có trong `llm_profiles` thì lỗi liệt kê các profile đang có.
- **Lỗi cấu hình không bị thử lại:** profile không có, thiếu key, thiếu credential/project Google, request bị 401/403 là `ConfigError` (`core/utils/config_errors.py`); `except_handler` ném ngay thay vì thử lại 5 lần, nên thông báo hiện một lần.
- **Cache không phân biệt model:** câu trả lời LLM được cache theo prompt trong `output/gpt_log`. Đổi profile rồi dịch lại cùng video sẽ dùng lại kết quả cũ; xóa `output/gpt_log` nếu muốn dịch lại bằng profile mới.
- Thêm Provider mới: thêm một mục vào `PROVIDERS` trong `core/utils/llm_profile.py` (như `vertex` ở F8).

## Cấu hình F8 (Vertex AI cho Khâu Dịch)

Profile `provider: vertex` dịch bằng Gemini trên Vertex AI, không cần API key: xác thực bằng credential Google dùng chung (xem [Setup Google Cloud](#setup-google-cloud)). Có sẵn hai profile:

```yaml
api:
  profile: 'gemini-lite'
llm_profiles:
  gemini-lite:
    provider: vertex
    model: 'google/gemini-3.5-flash-lite'   # tên model phải có tiền tố google/
  gemini-flash:
    provider: vertex
    model: 'google/gemini-3.8-flash'
    reasoning_effort: low                   # không đặt thì một câu ngắn tốn ~240 reasoning token
vertex:
  project: 'videolingo-512414'   # trống thì dùng project của credential
  location_llm: 'global'
```

- **`config.yaml` đã có từ trước:** chép profile `gemini-lite`, `gemini-flash` (trong `llm_profiles:`), khóa `api.profile` và mục `vertex:` từ `config.yaml` của repo, rồi đặt `vertex.project` (ví dụ `videolingo-512414`).
- Gọi endpoint tương thích OpenAI qua client `OpenAI` của `ask_gpt`: `https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/endpoints/openapi` (location khác `global` dùng host `{location}-aiplatform.googleapis.com`). URL **không** qua `normalize_base_url`, nên project chứa chuỗi `ark` vẫn đúng.
- Credential là access token của `core/utils/google_credentials.py`, lấy lại ở mỗi request và tự làm mới khi hết hạn (job dịch quá 1 giờ không lỗi).
- JSON mode bật mặc định cho Vertex (ghi đè được bằng `llm_support_json` của profile); `api.llm_support_json` không áp dụng. Profile Vertex không dùng `api_key_env`/`api_key`/`base_url`.
- Lỗi rõ ràng: thiếu `vertex.project` (và credential không có project), thiếu `GOOGLE_APPLICATION_CREDENTIALS`, hoặc request bị 401/403 (credential thiếu role `roles/aiplatform.user` hoặc `roles/serviceusage.serviceUsageConsumer`) đều báo kèm chỉ dẫn tới mục "Setup Google Cloud", và không bị thử lại (xem F7).
- Đổi profile giữa OpenRouter và Gemini trên cùng video: xóa `output/gpt_log` (cache không phân biệt model, xem F7).

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
- Mặc định trong code là `0`; `config.yaml` của fork đặt `0.25`. Âm lượng gốc cố định suốt video; tự hạ khi có giọng Việt (sidechain ducking) chưa làm.
- Nhãn thanh trượt là chữ cố định, không qua `t()`.

## Cấu hình F9 (Vertex TTS)

Chọn trên giao diện: **Dubbing Settings → TTS Provider = Vertex AI**, rồi chọn giọng và tốc độ. Hoặc sửa tay `config.yaml`:

```yaml
tts_method: 'vertex_tts'
vertex:
  project: 'videolingo-512414'  # trống thì dùng project của credential
  location_llm: 'global'        # dùng cho Provider Vertex của Khâu Dịch
vertex_tts:
  voice: ''          # trống = vi-VN-Chirp3-HD-Aoede; tên giọng Cloud TTS, ví dụ vi-VN-Chirp3-HD-Charon
  language: 'vi-VN'
  speed: 1.0         # 0.25–2.0, ngoài khoảng sẽ bị kẹp
  max_workers: 4     # thay toàn bộ max_workers / tts_max_workers khi đang dùng vertex_tts
```

- **`config.yaml` đã có từ trước:** đặt `vertex.project` và `vertex_tts.max_workers` trên giao diện (xem [Cấu hình trên giao diện (F7–F10)](#cấu-hình-trên-giao-diện-f7f10)), hoặc chép mục `vertex:` và `vertex_tts:` từ `config.yaml` của repo.
- Danh sách giọng lấy từ `GET https://texttospeech.googleapis.com/v1/voices?languageCode=<vertex_tts.language>`, chỉ giữ giọng có đúng mã ngôn ngữ đó; Chirp 3 HD đứng trước (ô "Chirp 3 HD voices only" bật mặc định). `voice` trống thì giao diện chọn sẵn `vi-VN-Chirp3-HD-Aoede`, không có thì giọng Chirp 3 HD đầu tiên, và ghi giọng đó vào `vertex_tts.voice` để giọng lồng tiếng đúng là giọng đang hiện. Danh sách được cache 1 giờ trên giao diện (theo ngôn ngữ); lỗi không bị cache.
- Thiếu credential hoặc project: màn hình hiện đúng thông báo của lỗi (đặt `GOOGLE_APPLICATION_CREDENTIALS`, hoặc đặt `vertex.project`) và cho gõ tay tên giọng, không lỗi trang. Lỗi khác (quyền, mạng) hiện cảnh báo.
- Thanh trượt tốc độ trên giao diện: 0.7–1.3 (khoảng an toàn để khớp thời lượng phụ đề). Giá trị sửa tay ngoài khoảng này được giữ nguyên cho tới khi kéo thanh trượt.
- Nhãn trên giao diện là chữ cố định, không qua `t()`.
- Gọi REST `POST https://texttospeech.googleapis.com/v1/text:synthesize` (không dùng `google-cloud-texttospeech`), `audioEncoding: LINEAR16`: Cloud TTS trả WAV có header nên ghi thẳng ra `.wav`.
- Header `x-goog-user-project` = `vertex.project` (hoặc project của credential), nên service account cần role `serviceusage.serviceUsageConsumer`.
- Lỗi API (quota 429, giọng sai 400, credential 401/403) báo `HTTP <mã> <thông điệp>` và không tự thử lại trong backend: vòng thử lại 3 lần của `tts_main` xử lý. Lỗi 401/403 và thiếu credential/project chỉ tới mục "Setup Google Cloud".
- Quota Chirp 3 HD: 200 request/phút/project, tối đa 5.000 byte mỗi request; 4 luồng là dư.
- Credential dùng chung (`core/utils/google_credentials.py`): Application Default Credentials, scope `cloud-platform`, token được làm mới khi hết hạn, có khóa cho nhiều luồng. Không tìm thấy credential thì kết quả lỗi được nhớ 30 giây (`MISSING_RETRY_SECONDS`) để sidebar không dò lại mỗi lần chạy lại. Đổi `GOOGLE_APPLICATION_CREDENTIALS` thì khởi động lại VideoLingo.

## Cấu hình trên giao diện (F7–F10)

Mọi khóa mới của F7–F10 đặt được trên sidebar, kể cả khi `config.yaml` có từ trước và chưa có các khóa đó: khóa (và mục cha như `vertex:`) được thêm vào `config.yaml` khi lưu; khóa chưa có thì ô hiện giá trị mặc định khai báo trong code (bằng giá trị của `config.yaml` trong repo). Giao diện chỉ ghi config, lượt chạy kế tiếp đọc lại như khi sửa tay.

| Khóa | Chỗ đặt trên sidebar |
|---|---|
| `api.profile` | **LLM Configuration → Profile đang dùng** (hiện khi có ít nhất một profile) |
| `llm_profiles.<tên>.*` | **LLM Configuration → Quản lý LLM profile & Vertex AI** → ô **Sửa profile**: *➕ Profile mới* hoặc tên profile, rồi **💾 Lưu profile** / **🗑 Xóa profile** (rồi **Xác nhận xóa**; **Hủy** để giữ) |
| `vertex.project`, `vertex.location_llm` | cùng chỗ, phần **Vertex AI (dùng chung cho Khâu Dịch và Lồng tiếng)**; ghi ngay khi rời ô |
| `vertex_tts.voice`, `.language`, `.speed`, `.max_workers` | **Dubbing Settings → TTS Provider = Vertex AI** (ô **Vertex parallel requests (max_workers)**, tối thiểu 1) |
| `original_volume` | **Dubbing Settings → Âm lượng gốc (Thuyết minh)** |

- **Ô của một profile:** tên, Provider (`openrouter`, `vertex`, `openai` = endpoint tương thích OpenAI), model, Base URL, biến môi trường chứa key, **API key (dự phòng)** (ô kiểu password, nên để trống), JSON mode (*Mặc định* / Bật / Tắt), số luồng, `reasoning_effort`. Ô để trống (JSON mode *Mặc định*, `reasoning_effort` *Không gửi*) không được ghi vào profile, nên giá trị chung hoặc mặc định của Provider vẫn áp dụng (Vertex mặc định bật JSON mode).
- **Kiểm hợp lệ khi lưu** (báo lỗi trên giao diện, không ghi gì): tên trống hoặc trùng profile khác, Provider không hỗ trợ (profile sửa tay với Provider lạ), model trống, `openai` thiếu Base URL, `max_workers` không phải số nguyên ≥ 1.
- **Đổi tên** profile đang dùng thì `api.profile` đổi theo. **Xóa** profile đang dùng thì `api.profile` về `''` (Profile custom).
- Sửa profile giữ nguyên thứ tự và comment của các profile khác trong `config.yaml`. Key không bao giờ được in ra màn hình hay log.
- Ví dụ dùng Vertex với `config.yaml` cũ: mở **Quản lý LLM profile & Vertex AI**, thêm profile `gemini-lite` (Provider `vertex`, model `google/gemini-3.5-flash-lite`), điền **Vertex project**, chọn `gemini-lite` ở **Profile đang dùng**; ở Dubbing Settings chọn Vertex AI, giọng, số luồng và Âm lượng gốc.
- Ô cấu hình mới của fork dùng `core/st_utils/config_fields.py`: `current(key, fallback)` (config.yaml → `fallback` khai báo ở ô) và `save(key, value)` (tạo khóa và mục cha còn thiếu). Từ #22 không đọc file nào khác ngoài `config.yaml`; test `test_the_default_of_each_widget_is_the_value_of_the_tracked_config` giữ `fallback` của mỗi ô bằng giá trị trong `config.yaml` của repo.
- Nhãn là chữ cố định, không qua `t()`.

## Đối chiếu khóa ↔ giao diện (#12)

Mọi khóa của `config.yaml` chỉnh được trên giao diện, trừ các khóa nội bộ ở cuối bảng. Khóa trong **Nâng cao** (expander cuối sidebar) ghi bằng `config_fields.save` (= `update_key(..., add_missing=True)`, tạo cả mục cha), nên chạy được với `config.yaml` cũ; khóa chưa có thì ô hiện giá trị mặc định khai báo trong code (bằng giá trị của `config.yaml` trong repo). Giao diện chỉ ghi config, mã xử lý đọc lại như khi sửa tay. Nhãn là chữ cố định, không qua `t()`, kèm tên khóa trong ngoặc.

| Khóa | Chỗ chỉnh |
|---|---|
| `display_language` | trang chính, ô **Display Language** |
| `api.*`, `llm_profiles.*`, `vertex.*` | sidebar, **LLM Configuration** (xem "Cấu hình trên giao diện (F7–F10)") |
| `target_language`, `translation_style`, `demucs`, `burn_subtitles`, `pause_before_translate`, `pause_after_translate` | sidebar, **Subtitles Settings** |
| `whisper.language`, `.runtime`, `.backend`, `.elevenlabs_api_key`, `.soniox_api_key`, `.mai_*` | sidebar, **Subtitles Settings** (theo runtime) |
| `subtitle.sub_video_subtitles`, `.dub_video_subtitles` | **Subtitles Settings**, hiện khi bật **Burn-in Subtitles** |
| `subtitle.style.*.font_name`, `.font_size`, `.font_color` | **Subtitles Settings → Subtitle Style** |
| `tts_method`, khóa API của các Provider TTS (`openai_tts.api_key`, `f5tts.302_api`, `sf_fish_tts.api_key`, `sf_cosyvoice2.api_key`, `fish_audio.api_key`, `soniox_tts.api_key`) | **Dubbing Settings → TTS Provider / Provider API Key** (ô password) |
| `sf_fish_tts.mode`, `.voice`; `openai_tts.voice`; `fish_audio.mode`, `.voice_id`; `edge_tts.voice`; `gpt_sovits.*`; `soniox_tts.voice`, `.language`, `.speed`; `vertex_tts.*`; `original_volume` | **Dubbing Settings**, theo phương thức đang chọn |
| `youtube.cookies_path` | trang chính, **Youtube Settings** cạnh ô tải video |
| `max_workers`, `tts_max_workers`, `ffmpeg_gpu`, `ytb_resolution` | **Nâng cao → Chung / hiệu năng** (`ytb_resolution` là mặc định của ô Resolution ở trang chính) |
| `whisper.qwen_model`, `whisper.qwen_engine` | **Nâng cao → ASR**, chỉ khi runtime `local` + backend `qwen` |
| `whisper.model` | **Nâng cao → ASR**, chỉ khi runtime `local` + backend `whisperx` |
| `subtitle.max_length`, `subtitle.target_multiplier`, `subtitle.style.*.outline_color`, `.outline_width`, `subtitle.style.translation.back_color`, `.margin_v` | **Nâng cao → Phụ đề** (màu sai dạng: cảnh báo, không lưu) |
| `summary_length`, `max_split_length`, `reflect_translate` | **Nâng cao → Dịch** |
| `openai_tts.base_url`, `.model` / `fish_audio.model`, `fish_audio.voices` / `soniox_tts.model` | **Nâng cao → Lồng tiếng**, khi đang chọn phương thức đó (`fish_audio.voices`: mỗi dòng `tên: ID`) |
| `speed_factor.min`, `.accept`, `.max`, `min_subtitle_duration`, `min_trim_duration`, `tolerance` | **Nâng cao → Lồng tiếng – tốc độ và thời lượng** (giữ `min ≤ accept ≤ max`) |
| `audio.raw_sample_rate`, `audio.raw_bitrate` | **Nâng cao → Âm thanh** |
| **Không đưa lên giao diện:** `model_dir`, `allowed_video_formats`, `allowed_audio_formats`, `spacy_model_map`, `language_split_with_space`, `language_split_without_space`, `whisper.detected_language` | khóa nội bộ / danh sách kỹ thuật |
| **Không đưa lên giao diện:** `sf_fish_tts.custom_name`, `sf_fish_tts.voice_id` | chương trình tự ghi khi tạo giọng nhân bản (config ghi "dont set manually") |

## Setup Google Cloud

Dùng cho Provider Vertex (Khâu Dịch) và `vertex_tts` (Khâu Lồng tiếng). Thay `PROJECT` bằng project ID (ví dụ `videolingo-512414`).

```bash
PROJECT=videolingo-512414
SA=videolingo-pc
gcloud config set project $PROJECT
# 1. Bật API
gcloud services enable aiplatform.googleapis.com texttospeech.googleapis.com
# 2. Tạo service account
gcloud iam service-accounts create $SA --display-name "VideoLingo"
# 3. Cấp 2 role (đủ cho Gemini trên Vertex và Cloud TTS)
for role in roles/aiplatform.user roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member "serviceAccount:$SA@$PROJECT.iam.gserviceaccount.com" --role $role
done
# 4. Tạo key JSON NGOÀI repo, chỉ chủ sở hữu đọc được
mkdir -p ~/.config/videolingo
gcloud iam service-accounts keys create ~/.config/videolingo/gcp-sa.json \
  --iam-account $SA@$PROJECT.iam.gserviceaccount.com
chmod 600 ~/.config/videolingo/gcp-sa.json
```

5. Đặt biến cho tiến trình VideoLingo, cách gọn nhất là một dòng trong `.env` (xem "Key trong .env"):
   `GOOGLE_APPLICATION_CREDENTIALS=/home/<user>/.config/videolingo/gcp-sa.json`. Hoặc biến môi trường:
   - Shell: `export GOOGLE_APPLICATION_CREDENTIALS=~/.config/videolingo/gcp-sa.json`
   - systemd: thêm vào mục `[Service]` của unit (đường dẫn tuyệt đối), rồi `systemctl daemon-reload && systemctl restart <unit>`:

     ```ini
     Environment=GOOGLE_APPLICATION_CREDENTIALS=/home/<user>/.config/videolingo/gcp-sa.json
     ```
6. Đặt `vertex.project` trong `config.yaml` (hoặc để trống để dùng project trong key JSON).

Không commit key JSON. Thu hồi key: `gcloud iam service-accounts keys list/delete --iam-account ...`.

## Key trong .env

Từ #21, key và secret không nằm trong `config.yaml`. `config.yaml` chỉ chứa tham chiếu `${TÊN_BIẾN}` (hoặc `${TÊN_BIẾN:-mặc định}`); giá trị nằm trong `.env` cạnh `config.yaml` (đã có trong `.gitignore`) hoặc trong biến môi trường của tiến trình. Từ #22, `config.yaml` được track lại trong git như upstream (xem [Chuyển từ config.example.yaml](#chuyển-từ-configexampleyaml)); `.env`, `.env.*` (trừ `.env.example`) và `config.backup.yaml` vẫn bị ignore. Test `tests/test_tracked_config.py` fail nếu một khóa có tên chứa `key`/`token`/`secret` (trừ `api_key_env`) trong `config.yaml` của repo không rỗng, không phải `YOUR_...` và không phải `${...}`.

Thêm khóa key mới: ghi vào `config.yaml` dạng `'${TÊN_BIẾN:-}'` và thêm `TÊN_BIẾN=` vào `.env.example`.

```yaml
api:
  key: '${LLM_API_KEY}'
whisper:
  soniox_api_key: '${SONIOX_API_KEY}'
```

```ini
# .env (quyền 600, không commit)
LLM_API_KEY=sk-...
SONIOX_API_KEY=...
GOOGLE_APPLICATION_CREDENTIALS=/home/<user>/.config/videolingo/gcp-sa.json
```

- **Thứ tự ưu tiên**: biến môi trường đã có của tiến trình → `.env` (nạp một lần với `override=False`) → giá trị sau `:-`. `${VAR}` không có mặc định mà biến chưa đặt → `MissingEnvVarError` (một `ConfigError`, không thử lại) nêu tên biến và đường dẫn `.env`, không in giá trị. Lỗi này xảy ra cả khi đọc nguyên mục chứa key (ví dụ `load_key("whisper")`), nên `config.yaml` dùng `${VAR:-}` cho các ô key tùy chọn.
- **Đọc**: `load_key`/`load_key_or` trả giá trị đã thay; `load_key(key, resolve=False)` hoặc `env_keys.raw(key)` đọc nguyên văn.
- **Ghi**: `update_key` (nên cả `config_fields.save`, `config_input`) và `tts_settings.save_settings` ghi qua `env_keys.keep_references`: tham chiếu luôn được giữ trong `config.yaml`; giá trị khác giá trị biến đang đọc được ghi vào `.env` dưới tên biến đó (tạo file quyền 600 nếu chưa có); ghi một chuỗi `${...}` mới thì đổi tham chiếu. Áp dụng cả khi ghi nguyên mục (ví dụ `llm_profiles`).
- **Sidebar**: ô key dạng `${VAR}` để trống và ghi "Lấy từ .env: VAR"; nhập key mới → `.env` cập nhật, `config.yaml` giữ `${VAR}`. Ô key chưa dùng biến vẫn ghi vào `config.yaml` như cũ (ẩn ký tự). Lưu ý: biến đã đặt sẵn trong môi trường tiến trình (systemd, shell) vẫn thắng `.env` ở lần khởi động sau.
- **Tên biến chuẩn**: xem `.env.example` (`LLM_API_KEY`, `OPENROUTER_API_KEY`, `SONIOX_API_KEY`, `ELEVENLABS_API_KEY`, `AZURE_SPEECH_KEY`, `OPENAI_TTS_API_KEY`, `API_302_KEY`, `SILICONFLOW_API_KEY`, `FISH_AUDIO_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`). `SONIOX_API_KEY` và `api_key_env` của LLM profile vẫn đọc biến môi trường trước như cũ.
- **Chuyển `config.yaml` cũ**: chạy từ thư mục gốc repo

  ```bash
  python scripts/move_keys_to_env.py --dry-run   # chỉ in tên khóa -> tên biến
  python scripts/move_keys_to_env.py
  ```

  Script chuyển mọi giá trị không rỗng của khóa có tên chứa `key`/`token`/`secret` (thêm `f5tts.302_api`), trừ khóa trỏ tên biến (`*_env`), giá trị đã là `${...}` và placeholder `YOUR_...`. Key của LLM profile dùng biến trong `api_key_env` của profile nếu có. Trước khi sửa, `config.yaml` được chép sang `config.backup.yaml` (quyền 600, chứa key thật: xóa khi đã kiểm tra xong). Biến đã có trong `.env` hoặc môi trường không bị ghi đè: cùng giá trị thì dùng lại, khác giá trị thì giữ key trong `config.yaml` và báo `SKIPPED`. Không in giá trị nào.
- **systemd/Paseo**: không cần truyền biến key hay `GOOGLE_APPLICATION_CREDENTIALS` qua `Environment=` nữa; `.env` được nạp khi đọc config lần đầu và trước khi `google_credentials` gọi `google.auth.default()`.

## Chuyển từ config.example.yaml

Trước #22, `config.yaml` không được track (chứa key thật) và một checkout mới chép `config.example.yaml` thành `config.yaml` (`ensure_config()`, `installer.py`). Từ #22, `config.yaml` được track như upstream, `config.example.yaml` bị bỏ cùng cơ chế chép. Máy đang chạy với `config.yaml` cũ (chưa track, có thể còn key) chuyển như sau, theo thứ tự:

1. **Trước khi pull/merge**: đổi tên `config.yaml` cũ, ví dụ `mv config.yaml config.local.yaml` (git từ chối ghi đè file chưa track khi checkout bản có `config.yaml`). Không commit file này.
2. Pull/merge bản có #22. `config.yaml` mới là bản mẫu của repo.
3. Đưa giá trị của mình vào: `mv config.local.yaml config.yaml` (ghi đè bản mẫu), rồi chạy `python scripts/upgrade_config.py --dry-run` và `python scripts/upgrade_config.py`: kết quả có đủ khóa, thứ tự và ghi chú của bản mẫu (`git show HEAD:config.yaml`) với giá trị của mình ở mọi khóa mình đã có; khóa mới của repo lấy giá trị mặc định (in tên: `added from the template: ...`); khóa chỉ có trong config của mình được giữ và in tên (`kept, not in the template: ...`). Script chỉ in tên khóa, không in giá trị, và chép `config.yaml` sang `config.before-upgrade.yaml` (quyền 600, bị ignore; có thể chứa key) trước khi ghi. Sau đó chạy `python scripts/move_keys_to_env.py --dry-run` và `python scripts/move_keys_to_env.py` để chuyển mọi key sang `.env` (xem [Key trong .env](#key-trong-env)).
   - `HEAD:config.yaml` chỉ là bản mẫu khi chưa commit giá trị của mình vào `config.yaml`; nếu đã commit thì truyền bản mẫu bằng `--template FILE` (ví dụ `git show origin/main:config.yaml > /tmp/template.yaml`).
   - Chạy lại `upgrade_config.py` sau mỗi lần merge làm `config.yaml` mẫu có khóa mới. `config.before-upgrade.yaml` còn từ lần trước thì script dừng, không ghi đè: kiểm tra rồi xóa file đó.
4. Chạy `pytest tests/test_tracked_config.py`: phải pass (chỉ in tên khóa còn chứa key, không in giá trị). Không pass thì chuyển hoặc xóa key ở các khóa được nêu, chạy lại.
5. Xem `git diff config.yaml`: chỉ còn giá trị cấu hình và tham chiếu `${VAR}`, không có key. Khi đó mới commit `config.yaml`.
6. Kiểm tra xong thì xóa `config.backup.yaml` và `config.before-upgrade.yaml` (có thể chứa key thật, đã bị ignore).

Test không đọc `config.yaml` của người vận hành: test cần giá trị mặc định hoặc cấu trúc mẫu đọc `tests/fixtures/config.yaml` (`tests/template_config.py`); chỉ `tests/test_tracked_config.py` đọc `config.yaml` của repo (không có key thật, và có đủ khóa của bản mẫu test). Sửa `config.yaml` mẫu thì làm mới bản mẫu test: `git show HEAD:config.yaml > tests/fixtures/config.yaml`.
