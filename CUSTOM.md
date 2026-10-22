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
| `tests/test_vertex_tts.py` | Test cho F9 (backend, liệt kê/lọc giọng, giọng mặc định, nhánh dispatcher) |
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
| `core/_3_2_split_meaning.py` | F7 — import + số luồng chia câu theo nghĩa lấy từ `llm_max_workers()` | 2 |
| `core/_4_2_translate.py` | F7 — import + số luồng dịch lấy từ `llm_max_workers()` | 2 |
| `core/_5_split_sub.py` | F7 — import + số luồng chia phụ đề (2 chỗ) lấy từ `llm_max_workers()` | 3 |
| `tests/test_backlog_fixes.py` | F7 — `_check_api` patch thêm `load_key`/`load_key_or` của `llm_profile`; test chia phụ đề patch `llm_max_workers` | 2 + 2 |
| `config.example.yaml` (F7) | khóa `api.profile`; mục `llm_profiles:` mẫu | 2 + 14 |
| `core/st_utils/sidebar_setting.py` (F7) | các ô nhập API gốc chuyển vào hàm lồng `custom_llm_inputs()`, chỉ gọi khi `llm_profile_setting.render()` báo đang chọn Profile custom | 5 |
| `core/_12_dub_to_vid.py` | F10: import `original_audio`; `original_volume > 0` thay track nền demucs bằng track âm thanh gốc của video | 7 |
| `api.py` | F10: field tùy chọn `original_volume` (0–1) của `POST /run`, ghi vào `config.yaml` | 3 |
| `core/st_utils/sidebar_setting.py` (F10) | gọi `original_volume_setting.render()` cuối Dubbing Settings | 2 |
| `tests/test_api.py` | F10: test `test_run_saves_original_volume` | 1 hàm |
| `core/tts_backend/tts_main.py` (F9) | import + nhánh `elif TTS_METHOD == 'vertex_tts'` | 3 |
| `core/_10_gen_audio.py` (F9) | khi `tts_method == 'vertex_tts'`, `vertex_tts.max_workers` thay toàn bộ số luồng TTS | 2 |
| `core/st_utils/tts_settings.py` (F9) | provider `"Vertex AI"` trong `PROVIDERS` (không có trong `KEY_PATHS`: xác thực bằng credential Google) | 1 |
| `core/st_utils/sidebar_setting.py` (F9) | nhãn `vertex_tts` + nhánh gọi `vertex_tts_settings.render()` | 4 |
| `requirements.txt` (F8/F9) | `google-auth` | 2 |
| `config.example.yaml` | khóa `tts_max_workers`; khóa `whisper.soniox_api_key` và ghi chú runtime; mục `soniox_tts:`; khóa `original_volume` (F10); (F9) mục `vertex:`, `vertex_tts:` và `vertex_tts` trong ghi chú `tts_method` | 3 + 12 + 3 + 20 |

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
| `max_workers` | `max_workers`. Áp dụng cho mọi bước song song của Khâu Dịch (chia câu theo nghĩa, dịch, chia phụ đề) qua `llm_max_workers()`; bước sinh audio không đổi |

- **Thứ tự tìm key:** biến môi trường ghi trong `api_key_env` → `llm_profiles.<tên>.api_key`. Không tìm thấy thì lỗi nêu tên profile và cả hai chỗ đặt key. Profile custom vẫn dùng `api.key` (máy chủ local như Ollama không cần key).
- **Đổi profile trên giao diện:** sidebar → **LLM Configuration** → ô **Profile đang dùng**. Danh sách gồm *Profile custom (mục api: gốc)* và các profile trong `llm_profiles`; dưới ô hiện Provider và model của profile đang chọn. Lựa chọn được ghi ngay vào `api.profile` và lượt dịch tiếp theo dùng profile đó. Các ô nhập API gốc (key, base_url, model, JSON mode) chỉ hiện khi chọn Profile custom; profile có tên có nút **Check API** riêng. Không có `llm_profiles` thì sidebar giữ nguyên như upstream. Thêm, sửa, xóa profile vẫn làm trong `config.yaml`.
- **Đổi profile bằng tay:** sửa `api.profile` thành tên khác trong `llm_profiles`, hoặc `''` để quay về Profile custom. Tên không có trong `llm_profiles` thì lỗi liệt kê các profile đang có.
- **Cache không phân biệt model:** câu trả lời LLM được cache theo prompt trong `output/gpt_log`. Đổi profile rồi dịch lại cùng video sẽ dùng lại kết quả cũ; xóa `output/gpt_log` nếu muốn dịch lại bằng profile mới.
- Thêm Provider mới (ví dụ `vertex` ở F8): thêm một mục vào `PROVIDERS` trong `core/utils/llm_profile.py`.

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

- Danh sách giọng lấy từ `GET https://texttospeech.googleapis.com/v1/voices?languageCode=<vertex_tts.language>`, chỉ giữ giọng có đúng mã ngôn ngữ đó; Chirp 3 HD đứng trước (ô "Chirp 3 HD voices only" bật mặc định). `voice` trống thì giao diện chọn sẵn `vi-VN-Chirp3-HD-Aoede`, không có thì giọng Chirp 3 HD đầu tiên. Danh sách được cache 1 giờ trên giao diện (theo ngôn ngữ); lỗi không bị cache.
- Thiếu credential: màn hình hiện hướng dẫn đặt `GOOGLE_APPLICATION_CREDENTIALS` và cho gõ tay tên giọng, không lỗi trang. Lỗi khác (quyền, mạng) hiện cảnh báo.
- Thanh trượt tốc độ trên giao diện: 0.7–1.3 (khoảng an toàn để khớp thời lượng phụ đề). Giá trị sửa tay ngoài khoảng này được giữ nguyên cho tới khi kéo thanh trượt.
- Nhãn trên giao diện là chữ cố định, không qua `t()`.
- Gọi REST `POST https://texttospeech.googleapis.com/v1/text:synthesize` (không dùng `google-cloud-texttospeech`), `audioEncoding: LINEAR16`: Cloud TTS trả WAV có header nên ghi thẳng ra `.wav`.
- Header `x-goog-user-project` = `vertex.project` (hoặc project của credential), nên service account cần role `serviceusage.serviceUsageConsumer`.
- Lỗi API (quota 429, giọng sai 400, credential 401/403) báo `HTTP <mã> <thông điệp>` và không tự thử lại trong backend: vòng thử lại 3 lần của `tts_main` xử lý. Lỗi 401/403 và thiếu credential/project chỉ tới mục "Setup Google Cloud".
- Quota Chirp 3 HD: 200 request/phút/project, tối đa 5.000 byte mỗi request; 4 luồng là dư.
- Credential dùng chung (`core/utils/google_credentials.py`): Application Default Credentials, scope `cloud-platform`, token được làm mới khi hết hạn, có khóa cho nhiều luồng. Đổi `GOOGLE_APPLICATION_CREDENTIALS` thì khởi động lại VideoLingo.

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

5. Đặt biến môi trường cho tiến trình VideoLingo:
   - Shell: `export GOOGLE_APPLICATION_CREDENTIALS=~/.config/videolingo/gcp-sa.json`
   - systemd: thêm vào mục `[Service]` của unit (đường dẫn tuyệt đối), rồi `systemctl daemon-reload && systemctl restart <unit>`:

     ```ini
     Environment=GOOGLE_APPLICATION_CREDENTIALS=/home/<user>/.config/videolingo/gcp-sa.json
     ```
6. Đặt `vertex.project` trong `config.yaml` (hoặc để trống để dùng project trong key JSON).

Không commit key JSON. Thu hồi key: `gcloud iam service-accounts keys list/delete --iam-account ...`.
