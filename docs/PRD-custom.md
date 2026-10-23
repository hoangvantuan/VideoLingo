# PRD — VideoLingo Custom (fork `hoangvantuan/VideoLingo`)

| | |
|---|---|
| Phiên bản | 0.2 |
| Ngày | 2026-10-22 |
| Người sở hữu | tuanhv |
| Repo | `git@github.com:hoangvantuan/VideoLingo.git`, nhánh `custom` |
| Upstream | `Huanshere/VideoLingo`, gốc tại `01f8434` (v3.1.1 + 1 bản sửa lỗi) |
| Nơi triển khai | server `pc` (`~/projects/VideoLingo`) |

**Thay đổi so với 0.1:**
- Bỏ phần tích hợp n8n (F5 cũ). VideoLingo chạy độc lập, không so sánh với `youtubetts`.
- Ngôn ngữ nguồn chính là **tiếng Anh và tiếng Nhật**.
- Dịch bằng LLM qua **OpenRouter**.
- Đầu ra cần **cả phụ đề lẫn lồng tiếng**.
- Không nhân bản giọng người nói gốc.
- Lượng xử lý chưa biết, sẽ đo trong quá trình chạy (F5 mới).

---

## 1. Bối cảnh

VideoLingo nhận một video (file hoặc link YouTube) và chạy lần lượt các bước:
1. ASR: nhận dạng lời nói thành văn bản.
2. Chia câu.
3. Dịch bằng LLM.
4. Tạo và căn thời gian phụ đề, có thể burn thẳng vào video.
5. Lồng tiếng bằng TTS.

Bản gốc nhắm tới máy có GPU NVIDIA và dịch sang tiếng Trung là chính. Máy `pc` của tôi không đáp ứng điều kiện đó.

**Hiện trạng server `pc` (đã kiểm tra 2026-10-21):**

| Hạng mục | Giá trị | Ảnh hưởng |
|---|---|---|
| OS | Ubuntu 24.04.5 | Phù hợp |
| CPU | 2× Xeon E5-2682 v4 (64 luồng, AVX2, không có VNNI) | Nhiều luồng nhưng mỗi nhân yếu |
| RAM / Disk | 62 GB / còn trống 161 GB | Đủ dùng |
| GPU | GT 620 (Fermi), chưa có driver | **Không dùng được để tăng tốc AI.** Toàn bộ pipeline phải chạy CPU hoặc gọi cloud |
| Dịch vụ đang chạy | VieNeu-TTS (`:8000`, `:7860`), n8n, Postgres, Redis, paseo-hub | Cổng 8000 đã bị chiếm; VieNeu-TTS tận dụng được |
| Truy cập | Tailscale `100.123.116.92` | Đủ an toàn để mở giao diện web nội bộ |

## 2. Mục tiêu

| # | Mục tiêu | Thước đo thành công |
|---|---|---|
| G1 | Chạy ổn định trên `pc` dù không có GPU | Video 10 phút hoàn tất từ đầu đến cuối mà không phải can thiệp tay |
| G2 | ASR nhanh và rẻ nhờ **Soniox** cho video tiếng Anh và tiếng Nhật | Bước ASR của video 10 phút xong dưới 2 phút, chi phí khoảng $0.10 cho mỗi giờ âm thanh |
| G3 | Đầu ra là **phụ đề song ngữ cộng lồng tiếng Việt** | Giọng VieNeu-TTS chạy local, không tốn phí TTS |
| G4 | **Vẫn đồng bộ được upstream** | Mỗi lần rebase lên release mới có ≤ 3 file xung đột, giải quyết trong dưới 30 phút |
| G5 | Có số liệu để đánh giá năng lực xử lý | Mỗi job ghi lại thời gian của từng bước và chi phí |

### Ngoài phạm vi (Non-goals)
- Không hỗ trợ GPU và không tối ưu cho GPU.
- Không tích hợp n8n hay workflow tự động bên ngoài, không so sánh với `youtubetts`.
- Không nhân bản giọng người nói gốc, không gán giọng riêng cho từng người nói.
- Không viết lại giao diện Streamlit, không làm hệ thống nhiều người dùng hay phân quyền.
- Không sửa logic lõi của các bước chia câu, dịch và căn phụ đề, trừ khi có lỗi riêng với tiếng Việt hoặc tiếng Nhật.
- Không mở dịch vụ ra Internet công cộng.

## 3. Người dùng và tình huống sử dụng

- **Người dùng chính:** tôi (tuanhv), một người dùng duy nhất, dùng giao diện web Streamlit qua Tailscale.
- **UC1:** dán link YouTube hoặc tải file **tiếng Anh** lên, nhận video có phụ đề song ngữ Anh–Việt và lồng tiếng Việt.
- **UC2:** như UC1 nhưng nguồn là **tiếng Nhật**, phụ đề song ngữ Nhật–Việt.
- **UC3:** video bằng ngôn ngữ khác (không giới hạn): chạy được nhờ chế độ tự nhận diện ngôn ngữ, nhưng chất lượng không được cam kết như tiếng Anh và tiếng Nhật.

## 4. Yêu cầu chức năng

### F1. ASR runtime `soniox` — **P0**
- File mới `core/asr_backend/soniox_asr.py`, hàm `transcribe_audio_soniox(raw_audio, vocal_audio, start, end)` có cùng chữ ký với các backend hiện có.
- Luồng gọi API: `POST /v1/files` → `POST /v1/transcriptions` → hỏi trạng thái đến khi `completed` → `GET /v1/transcriptions/{id}/transcript`.
- Cấu hình khi tạo job:
  - `model: stt-async-v5`, `enable_speaker_diarization: true`.
  - Nếu `whisper.language` là một mã cụ thể (`en`, `ja`…), dùng `language_hints: [mã đó]`.
  - Nếu `whisper.language` là `auto`, dùng `language_hints: ["en", "ja"]` và bật `enable_language_identification: true`. Ngôn ngữ chiếm đa số trong các token trở thành `language`, và được ghi vào `whisper.detected_language`.
- **Gộp token thành từ, tùy theo ngôn ngữ:**
  - Ngôn ngữ có dấu cách (en…): token bắt đầu bằng dấu cách thì mở từ mới.
  - Ngôn ngữ không dấu cách (ja, zh, theo `language_split_without_space` của upstream): **mỗi token là một đơn vị**. Không ghép dấu cách khi nối văn bản, để khớp với cách chia câu tiếng Nhật của upstream.
- Đổi `start_ms`/`end_ms` sang giây rồi cộng thêm offset `start` của đoạn.
- Cắt segment khi khoảng lặng lớn hơn 1 giây hoặc khi đổi người nói, theo cùng logic với `elev2whisper`.
- Trả về `{"segments":[{"text","start","end","words":[{"word","start","end"}]}], "language": ...}`.
- **Luôn xóa** file và transcription trên Soniox sau khi lấy kết quả, kể cả khi bị lỗi (dùng `finally`).
- Thử lại khi gặp HTTP 429 hoặc 5xx. Có timeout cho việc chờ kết quả.
- Không cần ForcedAligner, không tải model Qwen.
- Đọc key theo thứ tự: biến môi trường `SONIOX_API_KEY`, sau đó mới tới `whisper.soniox_api_key`.

**Tiêu chí chấp nhận:**
- Với clip 2 phút tiếng Anh và clip 2 phút tiếng Nhật, phụ đề lệch so với lời nói không quá 300 ms khi kiểm tra bằng mắt.
- Câu tiếng Nhật không bị chèn dấu cách thừa.
- Tìm trên dashboard Soniox thì không còn file nào sót lại.

### F2. Dịch bằng OpenRouter — **P0, chỉ cấu hình**
```yaml
api:
  key: ''                                    # đọc từ biến môi trường, không commit
  base_url: 'https://openrouter.ai/api/v1'
  model: '<chọn ở M0>'
  llm_support_json: false                    # chỉ bật nếu model hỗ trợ JSON mode trên OpenRouter
target_language: 'Tiếng Việt'
```
- **Chọn model ở M0:** chạy cùng một clip tiếng Anh và một clip tiếng Nhật qua 2–3 model ứng viên trên OpenRouter. So sánh chất lượng dịch, tỷ lệ lỗi JSON (`output/gpt_log/error.json`) và chi phí, rồi chốt một model mặc định.
- Giữ `max_workers` mặc định vì đây là API cloud. Nếu OpenRouter trả HTTP 429 thì giảm xuống.
- Bảng thuật ngữ `custom_terms.xlsx` cho các lĩnh vực hay xử lý (P1).

### F3. Lồng tiếng bằng VieNeu-TTS — **P0, chỉ cấu hình**
VieNeu-TTS đã có endpoint **tương thích OpenAI** (`POST /v1/audio/speech`), nên chỉ cần dùng backend `openai_tts` có sẵn và chỉnh cấu hình:
```yaml
tts_method: 'openai_tts'
openai_tts:
  api_key: 'local'                      # VieNeu không kiểm tra key, nhưng VideoLingo yêu cầu không để trống
  base_url: 'http://127.0.0.1:8000/v1'
  model: 'vieneu-v3-turbo'
  voice: 'Ngọc Huyền'                   # lấy từ GET /v1/voices
```
- Chỉ dùng giọng có sẵn (preset), không nhân bản giọng.
- VieNeu báo `max_streams: 1` và chạy CPU với RTF khoảng 0.5 hoặc chậm hơn trên Broadwell. Vì vậy **phải chạy TTS tuần tự, 1 luồng**.
- **Không** dùng `precision=int8` của VieNeu vì CPU không có VNNI, âm thanh sẽ bị méo.

**Tiêu chí chấp nhận:** lồng tiếng xong clip 2 phút, giọng nghe rõ, không bị cắt chữ và không có đoạn chồng tiếng nặng.

### F4. Chạy như dịch vụ trên `pc` — **P0**
- Cài trực tiếp bằng `uv run start.py`. Bộ cài tự chọn PyTorch bản CPU. Máy chưa có `uv`, cần cài trước.
- Tắt Demucs mặc định (`demucs: false`) vì chạy CPU rất chậm. Chỉ bật cho video có nhạc nền lớn.
- Unit systemd user `videolingo-web`: Streamlit chạy tại `100.123.116.92:8501`, chỉ truy cập được qua Tailscale, tự khởi động lại khi bị lỗi.
- Không bật HTTP API. Nếu sau này cần thì dùng **cổng 8010** để tránh cổng 8000 của VieNeu.
- Đặt secret (`SONIOX_API_KEY`, OpenRouter key) trong `~/.config/videolingo/env` (quyền 600). **Không commit** `config.yaml` có chứa key.
- Burn phụ đề bằng libx264 trên CPU, **tắt** `h264_nvenc` (chỉ dành cho GPU NVIDIA).

### F5. Đo năng lực xử lý và chi phí — **P1**
Lượng xử lý chưa biết, nên cần số liệu để đánh giá:
- Mỗi job ghi một dòng vào `output/log/usage.jsonl` (lưu ngoài thư mục output của từng job để không bị xóa). Các trường gồm:
  - Thông tin video: thời lượng và ngôn ngữ nguồn.
  - Thời gian từng bước: ASR, dịch, phụ đề, TTS, ghép.
  - Chi phí: số phút âm thanh đã gửi Soniox, số token và chi phí OpenRouter (lấy từ trường `usage` trong phản hồi).
- Viết một script tổng hợp nhỏ để tính:
  - Trung bình số phút xử lý cho mỗi phút video.
  - Chi phí cho mỗi giờ video.
  - Bước nào là nút cổ chai.
- Mục tiêu: sau khoảng 10 video có đủ số liệu để quyết định có cần nâng cấp phần cứng hoặc đổi TTS hay không.

### F7. LLM profile — **P0**
Spec: issue #1. Quyết định: `docs/adr/0001-llm-profiles.md`.
- Khai báo nhiều **LLM profile** có tên trong `llm_profiles` (Provider, model, cách lấy key, tùy chọn ghi đè `llm_support_json`, `max_workers`, `reasoning_effort`). Chọn **Profile đang dùng** bằng `api.profile`.
- `api.profile` trống thì dùng **Profile custom** (mục `api:` gốc), chạy y như trước. Khóa ghi đè thiếu thì lấy giá trị chung.
- Key của profile: biến môi trường trước, rồi tới key trong profile. Thiếu profile hoặc thiếu key thì báo lỗi rõ ràng.
- Số luồng Khâu Dịch (chia câu, dịch, chia phụ đề) theo `max_workers` của Profile đang dùng. Sidebar có ô chọn Profile đang dùng, hiện Provider và model.
- Cấu hình chi tiết: `CUSTOM.md` mục "Cấu hình F7".

### F8. Provider Vertex cho Khâu Dịch — **P0**
- Profile `provider: vertex` gọi Gemini qua endpoint tương thích OpenAI của Vertex AI, xác thực bằng service account (`GOOGLE_APPLICATION_CREDENTIALS`), token tự làm mới.
- URL dựng từ `vertex.project` / `vertex.location_llm` (mặc định `global`), không qua `normalize_base_url`.
- Profile có sẵn: `gemini-lite` (`google/gemini-3.5-flash-lite`) và `gemini-flash` (`google/gemini-3.8-flash`, `reasoning_effort: low`). JSON mode bật.

### F9. Lồng tiếng bằng Vertex (`vertex_tts`) — **P1**
- Phương thức lồng tiếng mới dùng Cloud Text-to-Speech (REST `text:synthesize`), credential Google dùng chung với F8.
- Chọn giọng `vi-VN` trên Dubbing Settings, mặc định nhóm Chirp 3 HD; tốc độ đọc trong khoảng an toàn; audio WAV (LINEAR16).
- `vertex_tts.max_workers` (mặc định 4) thay số luồng Khâu Lồng tiếng khi dùng `vertex_tts`.

### F10. Lồng tiếng kiểu Thuyết minh — **P1**
- Video lồng tiếng giữ âm thanh gốc (cả giọng gốc) ở mức nhỏ cố định, giọng Việt đè lên trên.
- Khóa `original_volume` (0–1, nhân thẳng lên track âm thanh của file video). Chỉnh qua `config.yaml`, field `original_volume` của `POST /run`, hoặc thanh trượt trong Dubbing Settings. Mặc định trong code `0` = hành vi upstream; config của fork đặt `0.25`.
- `original_volume > 0` thay track nền demucs bằng âm thanh gốc (tránh lặp nhạc nền); video không có track âm thanh thì chỉ xuất giọng lồng tiếng, kèm cảnh báo.
- Ngoài phạm vi: tự hạ âm thanh gốc khi giọng Việt đang nói (sidechain ducking), chuẩn hóa loudness riêng cho track gốc.

**Tiêu chí chấp nhận:** ở `0.25` nghe được giọng gốc nhỏ dưới giọng Việt; giọng lồng tiếng giữ mức đã chuẩn hóa; `original_volume = 0` cho lệnh trộn giống hệt trước.

## 5. Yêu cầu phi chức năng

| Mã | Yêu cầu |
|---|---|
| N1 | **Dễ đồng bộ upstream:** tính năng mới để ở file mới. Sửa file lõi thì chỉ thêm "móc nối" ngắn (dưới 10 dòng mỗi file) và ghi lại trong `CUSTOM.md` |
| N2 | **Bảo mật:** chỉ nghe trên IP Tailscale hoặc `127.0.0.1`. Không để secret trong git: key nằm trong `.env` (bị ignore), `config.yaml` được track và chỉ chứa tham chiếu `${VAR}` (#21, #22; test `tests/test_tracked_config.py`) |
| N3 | **Quyền riêng tư:** âm thanh gửi lên Soniox được xóa ngay sau khi xử lý xong. Nội dung nhạy cảm thì dùng ASR local (Qwen 0.6B) và chấp nhận chạy chậm |
| N4 | **Tài nguyên:** VideoLingo không được làm treo các dịch vụ đang chạy (VieNeu-TTS, n8n, Postgres). Giới hạn CPU qua systemd (`CPUQuota`) nếu cần |
| N5 | **Khả năng khôi phục:** chạy lại job thì dùng lại cache ASR và LLM có sẵn của upstream, không phải gọi lại API |

## 6. Kiến trúc tóm tắt

```
YouTube/file ──► VideoLingo (pc, CPU, Streamlit :8501 qua Tailscale)
                  ├─ ASR ───────► Soniox API (cloud)            [F1]
                  ├─ Dịch ──────► LLM profile                   [F7]
                  │                 ├─ OpenRouter (cloud)       [F2]
                  │                 └─ Vertex AI Gemini (cloud) [F8]
                  ├─ Phụ đề ────► ffmpeg libx264 (local)
                  ├─ TTS ───────► VieNeu-TTS :8000 (local)      [F3]
                  │             │ Soniox TTS (cloud)            [F6]
                  │             └ Vertex AI Cloud TTS (cloud)   [F9]
                  └─ Log ───────► output/log/usage.jsonl        [F5]
```

## 7. Chiến lược fork và đồng bộ

- `main` = bản sao của `upstream/main`, không commit vào nhánh này. `custom` = `main` + các commit tùy biến, mỗi tính năng một commit.
- Remote `upstream` đã bị chặn push.
- Lịch đồng bộ: theo **tag release** của upstream:
  ```bash
  git fetch upstream --tags
  git checkout main && git merge --ff-only upstream/main && git push origin main
  git checkout custom && git rebase main
  ```
- Sau mỗi lần rebase, chạy lại các clip kiểm thử ở mục 9.
- Tính năng nào có ích chung (ví dụ backend Soniox) thì gửi PR lên upstream để bớt phần phải tự duy trì.

**Bảng các file lõi bị sửa (cập nhật trong `CUSTOM.md`):**

| File | Thay đổi | Rủi ro xung đột |
|---|---|---|
| `core/_2_asr.py` | thêm `"soniox"` vào danh sách runtime và một nhánh `elif` | Trung bình, upstream sửa file này thường xuyên |
| `config.yaml` | thêm khóa `whisper.soniox_api_key` | Thấp |
| `core/st_utils/sidebar_setting.py` | (tùy chọn) thêm Soniox vào ô chọn | Trung bình. Có thể bỏ qua vì đã chỉnh được qua config |
| Điểm ghi log của F5 | chưa xác định. Ưu tiên bọc ngoài các hàm (wrapper) hoặc thêm vào cuối pipeline để hạn chế sửa nhiều file | Sẽ đánh giá khi thiết kế F5 |

## 8. Lộ trình

| Giai đoạn | Nội dung | Đầu ra |
|---|---|---|
| M0 | Cài `uv` và bản gốc ở chế độ CPU. Cấu hình OpenRouter, chạy thử 2–3 model để chọn model dịch. Đo thời gian ASR local với Qwen 0.6B làm baseline | Model mặc định + số liệu baseline |
| M1 | F1 Soniox (en + ja) + `CUSTOM.md` | Commit trên `custom`, 2 clip kiểm thử đạt yêu cầu |
| M2 | F3 VieNeu (chỉ cấu hình) | Video có phụ đề và lồng tiếng Việt đầu tiên |
| M3 | F4 systemd + secret + giới hạn tài nguyên | Dịch vụ tự khởi động lại, truy cập được qua Tailscale |
| M4 | F5 ghi log và tổng hợp, chạy khoảng 10 video thật | Báo cáo năng lực xử lý và chi phí |
| M5 | (tùy chọn) PR backend Soniox lên upstream | |

## 9. Kiểm thử chấp nhận

1. **Tiếng Anh**, clip 2 phút nói rõ: Soniox → OpenRouter → phụ đề song ngữ đã burn → lồng tiếng VieNeu.
2. **Tiếng Nhật**, clip 2 phút: như trên. Kiểm tra câu không bị chèn dấu cách thừa và câu phụ đề được chia hợp lý.
3. Clip có nhạc nền và hai người nói: kiểm tra phần nhận biết người nói và khả năng cắt segment.
4. Clip có ngôn ngữ nguồn là `auto`: nhận diện đúng tiếng Anh hoặc tiếng Nhật.
5. Chạy lại clip 1: phải dùng lại cache, không gọi Soniox hay OpenRouter thêm lần nào.
6. Sau mỗi lần rebase lên upstream: chạy lại clip 1 và 2.

## 10. Rủi ro

| Rủi ro | Biện pháp giảm thiểu |
|---|---|
| Upstream refactor mạnh `_2_asr.py` | Giữ phần móc nối thật nhỏ, gửi PR lên upstream |
| Token tiếng Nhật của Soniox không khớp với cách chia câu tiếng Nhật của upstream | Kiểm thử 2 ở M1, chỉnh lại logic gộp token |
| VieNeu chạy chậm trên CPU Broadwell, TTS thành nút cổ chai | Đo bằng F5. Nếu chậm, chuyển sang `v3nano` hoặc Edge TTS |
| Model OpenRouter trả JSON sai định dạng | Chọn model ở M0 theo tỷ lệ lỗi JSON, xem `output/gpt_log/error.json` |
| Tranh tài nguyên với các dịch vụ khác trên `pc` | `CPUQuota`, mỗi lần chỉ 1 job |

## 11. Câu hỏi mở

1. Model OpenRouter cụ thể: sẽ chốt sau khi chạy thử ở M0.
2. Lượng xử lý thực tế: sẽ đánh giá sau M4 dựa trên số liệu của F5.
3. Tự chuyển sang LLM profile khác khi Profile đang dùng lỗi hoặc bị giới hạn (429), theo một chuỗi fallback: chưa làm ở F7–F9, cân nhắc sau khi có số liệu lỗi thực tế.
