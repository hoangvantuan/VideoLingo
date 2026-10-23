# Nghiên cứu: tích hợp Vertex AI (LLM, STT, TTS) vào VideoLingo

Ngày truy cập mọi nguồn: **2026-10-22**. Chỉ dùng nguồn chính thức (cloud.google.com, PyPI/source `google-genai`); riêng giá Soniox lấy từ trang của chính Soniox. Mã nguồn tham chiếu: [Nguồn](#nguồn) ở cuối file. Mục nào ghi **chưa xác minh** là chưa tìm được câu trả lời trong tài liệu chính thức, cần thử thực tế.

> Lưu ý về tên gọi: tài liệu Google hiện gọi Vertex AI là **"Gemini Enterprise Agent Platform"**, và SDK `google-genai` dùng cờ `enterprise=True` (cờ cũ `vertexai=True` vẫn được nhận) [D9][X2]. File này vẫn dùng chữ "Vertex AI".

## Tóm tắt khuyến nghị

1. **LLM (dịch): làm trước, ít sửa nhất.** Dùng endpoint OpenAI-compatible của Vertex qua chính `ask_gpt` hiện có. Chỉ cần sửa `get_api_key()` để lấy access token từ ADC và tự làm mới (token sống 1 giờ) [D2]. `response_format: json_object` được hỗ trợ [D1], nên `llm_support_json: true` vẫn dùng được. Model gợi ý: `gemini-3.5-flash-lite` (rẻ) hoặc `gemini-3.8-flash` (tốt hơn, nhưng mặc định có thinking và token thinking tính như output) [P1][D6][D7]. **Cần thử trước:** danh sách model hỗ trợ Chat Completions trên trang chính thức đang bị thu gọn, nên chưa xác minh được Gemini 3.x Flash có trong đó không [D1].
2. **STT: giữ Soniox, chỉ thêm Vertex nếu cần.** Soniox async rẻ hơn khoảng 3 lần so với Gemini 3.5 Transcribe và khoảng 10 lần so với Chirp 3 [X1][P1][P2]. Nếu vẫn muốn có runtime Google, chọn **Gemini 3.5 Transcribe** (gửi bytes trực tiếp, không cần GCS, có word timestamps dạng Experimental, en/ja/zh/vi). Cần cắt audio ≤15 phút [S8]. Chirp 3 qua `BatchRecognize` bắt buộc dùng GCS bucket [S3][S4].
3. **TTS: Chirp 3 HD tiếng Việt là ứng viên tốt nhất trong thời gian trial.** Có giọng `vi-VN-Chirp3-HD-*`, miễn phí 1 triệu ký tự/tháng, sau đó $30/1M ký tự, 200 request/phút [T1][P3][T5]. Clone giọng: Instant Custom Voice cần allowlist qua sales [T2]. Gemini 3.8 Flash TTS có voice replication qua Voices API và trang không nhắc đến allowlist, nhưng đang Preview và chưa xác minh hỗ trợ tiếng Việt [T4].
4. **Trial $300 dùng được cho Gemini trên Vertex**, nhưng **không** dùng được cho Gemini API của AI Studio hay model đối tác dạng MaaS. Thời hạn 90 ngày. Trong trial không được xin tăng quota [F1][S7]. **Express mode là chương trình riêng**, không nằm trong Free Trial [D3].
5. **Chi phí ước tính cho một video 10 phút: khoảng $0,2–0,8**, tùy tổ hợp (xem [mục 4](#4-trial-300-và-chi-phí)). Với $300, giới hạn thực tế là **90 ngày** chứ không phải số tiền.
6. **Xác thực:** chạy local thì dùng ADC (`gcloud auth application-default login`). Chạy Docker thì mount file credential và đặt `GOOGLE_APPLICATION_CREDENTIALS` [A1][A2]. Dùng location `global` cho Gemini [D8].

---

## 1. LLM: Gemini trên Vertex AI

### Model và giá (Standard PayGo, mỗi 1M token, endpoint global) [P1]

| Model | Input | Output (gồm cả reasoning) | Ghi chú |
|---|---|---|---|
| `gemini-3.8-flash` | $0,75 (đến 31/12/2026) → $1,50 | $3,75 → $7,50 | Giá ưu đãi được thực hiện bằng "50% credits back on net spend". Thinking mặc định `MEDIUM`, **không** cho đặt `MINIMAL` [D6] |
| `gemini-3.7-flash` / `3.6-flash` | như 3.8 Flash | như 3.8 Flash | |
| `gemini-3.5-flash` | $1,50 | $9,00 | |
| `gemini-3.5-flash-lite` | $0,30 | $2,50 | Thinking mặc định ở mức minimal [D7] |
| `gemini-3.1-flash-lite` | $0,25 (audio $0,50) | $1,50 | |
| `gemini-2.5-flash` | $0,30 (audio $1,00) | $2,50 | |
| `gemini-2.5-flash-lite` | $0,10 (audio $0,30) | $0,40 | |
| `gemini-3.1-pro-preview` | $2,00 (≤200K) | $12,00 | |

Endpoint không phải global (regional) đắt hơn khoảng 10% với các model 3.x [P1]. Batch/Flex rẻ hơn, ví dụ 3.5 Flash input $0,75 [P1], nhưng VideoLingo gọi đồng bộ nên không áp dụng.

**Chi phí ẩn từ thinking:** bảng giá ghi output là "response and reasoning" [P1]. Với 3.8 Flash ở mức `MEDIUM`, số token output thực tế có thể gấp vài lần phần trả lời nhìn thấy. Tài liệu không nêu hệ số cụ thể; cần đo bằng `usage` trong response.

### Hai cách gọi

| | OpenAI-compatible (Chat Completions) | SDK `google-genai` |
|---|---|---|
| Base URL | `https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/endpoints/openapi` [D2] | `genai.Client(enterprise=True, project=..., location="global")` [D9][X2] |
| Tên model | `google/<model-id>` (ví dụ trong tài liệu: `google/gemini-2.0-flash-001`) [D2] | `<model-id>` |
| Xác thực | **OAuth access token** truyền vào `api_key`, mặc định sống **1 giờ**. Tài liệu có sẵn mẫu `OpenAICredentialsRefresher` tự refresh khi `not creds.valid` [D2] | ADC hoặc API key (express mode). Hai cách này loại trừ nhau [X2 `_api_client.py:740`] |
| JSON | `response_format`: `json_object` được chuyển thành `application/json`; `json_schema` được hỗ trợ trừ schema đệ quy hoàn toàn [D1] | `response_mime_type` + `response_schema`. Nếu chỉ đặt mime JSON mà không có schema thì đó chỉ là "strong hint", không đảm bảo 100% JSON hợp lệ [D5] |
| Thinking | `reasoning_effort` (low/medium/high) hoặc `extra_body.google.thinking_config` [D1] | `thinking_config` |
| Thay đổi trong VideoLingo | sửa `get_api_key()` (khoảng 15 dòng) | viết lại lớp gọi trong `ask_gpt` |

- Tài liệu chính thức khuyên dùng Chat Completions nếu code **đã** dùng thư viện OpenAI, còn code mới thì dùng Gen AI SDK [D1]. VideoLingo đã dùng `openai.OpenAI` nên đi đường OpenAI-compatible là hợp lý.
- **Chưa xác minh:** khi mở rộng danh sách "supported models" trên trang [D1] chỉ thấy "Gemini 4 Argon" và "Gemini 4 Argon Cyber Permissive". Trang vẫn có liên kết tới 3.5/3.6/3.7/3.8 Flash, nhưng chưa xác nhận được các model này dùng được qua `endpoints/openapi`. Cần gọi thử một lần.
- **Chưa xác minh:** endpoint OpenAI-compatible có nhận API key (thay cho OAuth token) không, và URL dạng `locations/global` (host `aiplatform.googleapis.com`) có chạy với `endpoints/openapi` không. Tài liệu [D2] chỉ có mẫu dạng `{location}-aiplatform`. Với DSQ, Google khuyên dùng endpoint global để giảm 429 [D8].
- Cách thử nhanh không cần sửa code: đặt `api.key` bằng kết quả của `gcloud auth application-default print-access-token` và `api.base_url` bằng URL ở trên [D2]. Cách này chỉ chạy được tối đa 1 giờ.

### Express mode API key

- Chỉ dành cho tài khoản **@gmail.com**. Người mới có free tier 90 ngày không cần thẻ. Express mode "**separate from, and not available through**, the Google Cloud Free Program" [D3].
- Với người đã dùng Google Cloud, hoặc sau khi bật billing, free tier 90 ngày bị bỏ; có thể liên kết billing account có sẵn để lấy API key [D3][D4].
- Ở free tier, express mode chỉ hỗ trợ một số model: `gemini-3-flash-preview`, `gemini-3.1-pro-preview` (RPM "Dynamic"), và `gemini-2.5-flash` / `-flash-lite` / `-pro` (10 RPM) [D3].
- Kết luận cho người dùng đang có trial $300: express là một chương trình khác. Việc API key của express khi liên kết với billing account trial có trừ vào $300 không là **chưa xác minh**. Cách chắc chắn để dùng credit là đi theo project chuẩn với ADC. Tab "existing Google Cloud user with a billing account" (API key chuẩn của Google Cloud) trên trang [D4] được tải bằng JS nên không đọc được, **chưa xác minh**.

### Quota / 429

Gemini dùng Standard PayGo với usage tier tính theo tổng chi tiêu 30 ngày gần nhất. Lỗi 429 "doesn't indicate that you've hit a fixed quota", chỉ là tranh chấp tài nguyên tạm thời; nên retry với backoff và dùng endpoint `global` [D8]. `ask_gpt` đã có `@except_handler(..., retry=5)` (`core/utils/ask_gpt.py:105`). Tài khoản mới với chi tiêu thấp nằm ở tier thấp nhất. Ngưỡng TPM của từng tier **chưa xác minh**.

### Đề xuất cắm vào lớp LLM hiện có

- `core/utils/ask_gpt.py:59` `get_api_key()`: nếu host của `api.base_url` kết thúc bằng `aiplatform.googleapis.com`, lấy token bằng `google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])`, cache credential ở cấp module và gọi `refresh()` khi `not creds.valid` (theo mẫu [D2]). Cần thêm package `google-auth`.
- `core/utils/ask_gpt.py:71` `normalize_base_url()`: URL của Vertex có chứa `/v1/` nên giữ nguyên, không bị thêm `/v1`. **Bẫy:** dòng 74 `if 'ark' in base_url` sẽ thay toàn bộ URL bằng endpoint Volcano Engine nếu **project ID chứa chuỗi "ark"** (ví dụ `spark-…`, `market-…`). Cần chọn project ID không chứa "ark", hoặc kiểm tra host trước.
- `config.yaml`: `api.base_url` là URL `endpoints/openapi`, `api.model` là `google/gemini-3.5-flash-lite` (hoặc `google/gemini-3.8-flash`), `api.key` để trống, giữ `llm_support_json: true`.

## 2. STT: Speech-to-Text v2 và Gemini

VideoLingo cần **word-level timestamps**: `process_transcription` (`core/asr_backend/audio_preprocess.py:163`) đọc `segments[].words[]` có `start`/`end`, giống output của `soniox2whisper` (`core/asr_backend/soniox_asr.py:131`). Nếu segment không có `words`, hàm này coi cả segment là một "từ" (`audio_preprocess.py:170-181`). Pipeline vẫn chạy, nhưng việc cắt câu và căn phụ đề chỉ chính xác ở mức segment. Audio được cắt thành đoạn **30 phút** (`core/asr_backend/audio_preprocess.py:126`, `target_len=30*60`). Đã có tiền lệ cắt ngắn hơn cho từng runtime: mai/openrouter dùng 120 giây (`core/_2_asr.py:75-79`).

### So sánh ba hướng

| | Chirp 3 (`chirp_3`, STT v2) | Chirp 2 (`chirp_2`) | Gemini 3.5 Transcribe (`gemini-3.5-transcribe`) |
|---|---|---|---|
| Word timestamps | **Tài liệu tự mâu thuẫn**: bảng tính năng xếp "Word-level timestamps" vào mục "Chirp 3 **doesn't support**", nhưng ô mô tả lại ghi "can be optionally enabled, which some transcription degradation is expected. Available only in Speech.Recognize and Speech.BatchRecognize". Bảng phương thức ghi BatchRecognize "up to 20 minutes with word-level timestamp enabled" [S1] → cần thử | Có, "can be optionally enabled", chất lượng/tốc độ có thể giảm nhẹ [S2] | Có (`word_timestamp=True` → `words[].start_offset/end_offset`), **Experimental**, "Degrades transcription accuracy" [S8]. Field có trong SDK 2.32.0 [X2 `types.py:6494`] |
| Độ dài audio | Recognize: ≤1 phút / 10 MB. BatchRecognize: 1 phút–1 giờ, 20 phút nếu bật word timestamps [S1][S3] | BatchRecognize tới 8 giờ [S2] | Trang model: ≤15 phút khi bật diarization/timestamps [S8]. Trang giá: "files up to 60 minutes" [P1] → khi bật timestamps thì theo **15 phút** |
| Cách gửi audio | Recognize: inline hoặc GCS. **BatchRecognize chỉ nhận GCS URI** [S3][S4] | như Chirp 3 | `Part.from_bytes` inline hoặc `gs://` [S8]. Giới hạn kích thước inline qua API **chưa xác minh** (15 phút WAV 16 kHz mono ≈ 29 MB; có thể nén FLAC/MP3) |
| en / ja / zh / vi | en-US, ja-JP, cmn-Hans-CN, vi-VN đều GA [S1] | vi-VN có cho `chirp_2` (asia-southeast1) [S6]; streaming không có vi [S2] | Có vi-VN; tự nhận diện 85+ ngôn ngữ [S8] |
| Diarization | Có ở BatchRecognize; danh sách ngôn ngữ có en, ja, cmn nhưng **không có vi-VN** [S1] | chưa xác minh | Có, tối đa 8 người, Experimental [S8] |
| Region | `us`, `eu` (multi-region) [S1] | us-central1, europe-west4, asia-southeast1 [S2] | `global`, `us`, `eu` [S8] |
| Giá | $0,016/phút (0–500K phút); Dynamic Batch $0,003/phút [P2]¹ | như Chirp 3¹ [P2] | $2/1M audio token + $12/1M text token ≈ **$0,0051/phút** [P1] |

¹ Trang giá chỉ ghi "Standard¹ models include: default, …, video, **chirp** (Speech-to-Text V2 only)", không nêu riêng `chirp_2`/`chirp_3`. Giá $0,016 và $0,003 cho Chirp 3 là suy luận, **chưa xác minh**.

- Free tier của STT: 60 phút/tháng **chỉ cho Speech-to-Text V1 API** [F1][P2]. V2 (Chirp) không có free tier trên trang giá [P2].
- Gemini 2.5/3.x (generate_content thông thường) cũng nhận audio (≤ khoảng 8,4 giờ) và có `audio_timestamp=True` [S7]. Tuy nhiên timestamp khi đó là văn bản model tự sinh, không phải trường cấu trúc theo từng từ, nên không hợp với VideoLingo. Chưa xác minh độ chính xác.

### So với Soniox (runtime hiện tại)

| | Soniox `stt-async-v5` | Gemini 3.5 Transcribe | Chirp 3 |
|---|---|---|---|
| Giá / 10 phút | ≈ $0,017 ($0,10/giờ async) [X1] | ≈ $0,05 | ≈ $0,16 (Dynamic Batch ≈ $0,03, cần GCS) |
| Word timestamps | Có (token `start_ms`/`end_ms`), đã tích hợp | Experimental | Tài liệu mâu thuẫn |
| Cần GCS | Không (upload file qua API) | Không | Có, nếu dùng BatchRecognize |

Kết luận: về chi phí và độ trưởng thành thì Vertex STT không có lợi thế so với Soniox. Chỉ nên thêm Gemini 3.5 Transcribe nếu muốn gom mọi thứ về một hóa đơn Google hoặc dùng hết credit trial.

## 3. TTS: Cloud Text-to-Speech và Gemini TTS

### Bảng tóm tắt

| Loại | Tiếng Việt | Giá (sau free tier) | Free/tháng | Ghi chú |
|---|---|---|---|---|
| Chirp 3: HD | Có (`vi-VN`, ví dụ `vi-VN-Chirp3-HD-*`) [T1][T6] | $30/1M ký tự [P3] | 1M ký tự [P3] | Region `global`. Có `speaking_rate` 0,25–2,0 [T1]. SSML giới hạn và không dùng được khi streaming [T1] |
| Neural2 | `vi-VN-Neural2-A`, `-D` [T6] | $16/1M [P3] | 1M [P3] | |
| WaveNet / Standard | `vi-VN-Wavenet-A..D`, `vi-VN-Standard-A..D` [T6] | $4/1M [P3] | 4M [P3] | |
| Instant Custom Voice (clone, Cloud TTS) | Có vi-VN trong danh sách [T2] | $60/1M [P3] | không | **"restricted to allow-listed users. To request access, contact a member of the sales team"** [T2]. Cần audio đồng ý (consent) + audio mẫu ≤10 giây [T2] |
| Gemini-TTS trên Cloud TTS API (`gemini-2.5-flash-tts`, `gemini-2.5-pro-tts`, `gemini-3.1-flash-tts-preview`) | vi-VN GA [T3] | 2.5 Flash: $0,50/1M text token + $10/1M audio token; 3.1 Flash: $1 + $20 [P3] | không | Audio 25 token/giây [P3]. Input tối đa 8.192 token [T3] |
| Gemini 3.8 Flash TTS / Flash-Lite TTS | **chưa xác minh** (130/101 ngôn ngữ, tự nhận diện; danh sách bị thu gọn) [T4] | Flash: $0,50 + $9/1M (đến 31/12/2026) → $1 + $18; Flash-Lite: $0,50 + $6 → $1 + $12 [P3] | không | **Chỉ có qua Gemini Enterprise API (`generateContent`)**, không qua Cloud TTS API [T3]. Chỉ ở location `global`. Preview [T4] |

### Liệt kê giọng

`GET https://texttospeech.googleapis.com/v1/voices?languageCode=vi-VN` trả về các giọng tổng hợp được cho ngôn ngữ đó [T6]. Có thể dùng cho bộ chọn giọng giống `core/st_utils/soniox_tts_settings.py`. Với Gemini 3.8 TTS: có 30 giọng dựng sẵn, Extended Voice Library hơn 2.000 giọng, và Voices API `list` (lọc theo loại hoặc chuỗi tìm kiếm) [T4].

### Clone giọng

- Cloud TTS Instant Custom Voice: cần allowlist qua sales. Quota 10 request/phút cho `GenerateVoiceCloningKey` và 30 request/phút cho tổng hợp bằng giọng clone [T2][T5].
- Gemini 3.8 TTS voice replication: tạo bằng `client.voices.create(type=VOICE_TYPE_REPLICATED)` từ audio mẫu + audio đồng ý. `store: true` trả về `voice_…` (hết hạn 1 năm sau lần dùng cuối); `store: false` trả về `voicekey_…` (hết hạn 7 ngày) [T4]. Trang **không nhắc** đến allowlist. Chưa xác minh có dùng được với tài khoản trial và với tiếng Việt không.

### Quota song song (liên quan `tts_max_workers`)

Cloud TTS: `Chirp3RequestsPerMinutePerProject` = 200, `Neural2…` = 1.000, `RequestsPerMinutePerProject` = 1.000, `ChirpVoiceCloning…` = 30. Mỗi request tối đa **5.000 byte** (tiếng Việt có dấu tốn nhiều byte/ký tự) [T5]. Với `max_workers: 4` (`config.yaml`), `tts_max_workers` không cần giảm vì quota. Lưu ý trial không cho xin tăng quota [F1]. Quota RPM của Gemini 3.8 TTS: **chưa xác minh**.

### Định dạng output

- Cloud TTS: `audioEncoding` gồm LINEAR16/MP3/OGG_OPUS…, `sampleRateHertz`, `speakingRate` 0,25–2,0 [T7].
- Gemini-TTS: unary hỗ trợ LINEAR16 (mặc định), ALAW, MULAW, MP3, OGG_OPUS, PCM; streaming hỗ trợ PCM… [T3].
- Gemini 3.8 TTS: mặc định WAV 16-bit PCM 24 kHz mono [T4].

Pipeline VideoLingo lưu `.wav`, nên chọn LINEAR16 là ghi thẳng ra file được.

## 4. Trial $300 và chi phí

### Phạm vi credit [F1]

- $300 dùng trong **90 ngày**, cho "products and services covered by the Free Trial program". Tài khoản trial cũng được dùng Free Tier.
- **Không** dùng được cho: Gemini API trong **AI Studio**, và "generative AI partner model … offered as a managed API (MaaS)".
- Gemini của Google trên Vertex nằm trong phạm vi credit: trang audio understanding ghi "new customers get $300 in free Google Cloud credits to explore what they can do with Gemini" [S7].
- Khi billing account còn là Free Trial thì **không được**: gắn GPU, dùng Marketplace, **xin tăng quota**. Nếu upgrade lên Paid, credit còn lại vẫn dùng được nhưng vẫn hết hạn sau 90 ngày tính từ ngày đăng ký.
- Nếu không upgrade, billing account tự đóng khi hết $300 hoặc hết 90 ngày.
- **Chưa xác minh:** giá ưu đãi của 3.8/3.7/3.6 Flash được thực hiện bằng "50% credits back on net spend" [P1]. Chưa rõ khoản hoàn này áp dụng thế nào khi chi tiêu được trả bằng credit trial. Để an toàn, nên ước tính theo giá chuẩn $1,50/$7,50.
- Free tier hàng tháng: TTS có Chirp 3 HD và Neural2 1M ký tự, WaveNet/Standard 4M ký tự [P3]. STT chỉ có 60 phút cho **V1** [F1][P2].

### Số liệu đo thực tế (video 10 phút trong `output/`)

Đo trên video hiện có trong repo, dài **605,9 giây**:

- `output/gpt_log/*.json`: **139** lần gọi LLM, **351.823** ký tự prompt và **179.833** ký tự response. Tính theo khoảng 4 ký tự/token thì được khoảng **88K token input** và **45K token output**. Đây là **cận dưới**, vì tiếng Việt thường tốn nhiều token hơn mỗi ký tự, và chưa tính token thinking.
- `output/dub.srt`: khoảng **9.349** ký tự lời thoại tiếng Việt cần TTS; `normalized_dub.wav` dài khoảng 605,7 giây.

### Ước lượng chi phí mỗi video 10 phút

| Bước | Lựa chọn | Cách tính | Chi phí |
|---|---|---|---|
| STT | Soniox async (hiện tại) | 10,1 phút × $0,10/giờ | ≈ $0,017 |
| STT | Gemini 3.5 Transcribe | 10,1 × $0,0051 | ≈ $0,05 |
| STT | Chirp 3 (Recognize/Batch) | 10,1 × $0,016 | ≈ $0,16 (Dynamic Batch ≈ $0,03) |
| Dịch | `gemini-3.5-flash-lite` | 88K × $0,30 + 45K × $2,50 | ≈ $0,14 |
| Dịch | `gemini-3.8-flash`, giá ưu đãi | 88K × $0,75 + 45K × $3,75 | ≈ $0,24 chưa tính thinking; ≈ $0,40 nếu thinking gấp đôi output (giả định) |
| Dịch | `gemini-3.8-flash`, giá chuẩn (từ 2027 hoặc không được hoàn 50%) | 88K × $1,50 + 45K × $7,50 | ≈ $0,47 chưa tính thinking; ≈ $0,80 nếu thinking gấp đôi output |
| TTS | Chirp 3 HD | 9.349 × $30/1M | ≈ $0,28, nhưng **$0** cho khoảng 100 video đầu mỗi tháng (free 1M ký tự) |
| TTS | Neural2 | 9.349 × $16/1M | ≈ $0,15 (cũng có free 1M) |
| TTS | Gemini 2.5 Flash TTS | 606 s × 25 token × $10/1M | ≈ $0,15 |
| TTS | Gemini 3.8 Flash TTS | 606 × 25 × $9/1M | ≈ $0,14 |
| TTS | Gemini 3.8 Flash-Lite TTS | 606 × 25 × $6/1M | ≈ $0,09 |

Một số tổ hợp tiêu biểu:

- **Giữ Soniox + 3.5 Flash-Lite + Chirp 3 HD (trong free tier):** ≈ **$0,16/video**.
- **Toàn Google, rẻ (3.5 Transcribe + 3.5 Flash-Lite + Chirp 3 HD trả tiền):** ≈ **$0,47/video**.
- **Toàn Google, chất lượng (Chirp 3 + 3.8 Flash có thinking + Gemini 3.8 Flash TTS):** ≈ **$0,70–1,10/video**.

Với $300, ba tổ hợp trên tương ứng khoảng 1.800 / 640 / 270–430 video. Trong thực tế, giới hạn thường là **90 ngày** trước khi dùng hết tiền. Chi phí lưu trữ GCS (nếu dùng BatchRecognize) không được tính ở đây.

## 5. Xác thực và các bước setup

| Cách | Hợp với | Ghi chú |
|---|---|---|
| ADC qua `gcloud auth application-default login` | Chạy local (Streamlit trên máy) | Credential được lưu ở file của gcloud; ADC tìm theo thứ tự: `GOOGLE_APPLICATION_CREDENTIALS` → file từ `gcloud auth application-default login` → service account gắn vào resource [A2] |
| `GOOGLE_APPLICATION_CREDENTIALS` trỏ tới file JSON | Docker | Dockerfile hiện có `WORKDIR /app`, `COPY . .` và không có `VOLUME` (`Dockerfile:14-15`). Nên mount file credential khi `docker run` (`-v …:/secrets/adc.json:ro -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/adc.json`), **không** COPY vào image. Tài liệu cảnh báo: "Service account keys create a security risk and are not recommended" [A2]. Có thể mount chính file ADC của người dùng thay cho key service account |
| API key (express) | Thử nhanh Gemini | Chỉ áp dụng cho Gemini qua SDK [D3][X2]. Không áp dụng cho STT v2/TTS theo tài liệu đã đọc. Chưa xác minh với endpoint OpenAI-compatible |

Khi đã có API key thì không cần ADC [A1]. Tuy nhiên STT/TTS/Chat Completions trong tài liệu đều dùng OAuth/ADC, nên dùng một cơ chế ADC chung cho cả ba là gọn nhất.

**Các bước setup (project chuẩn):**

1. Tạo hoặc chọn project. Nên tránh project ID có chứa "ark" (xem bẫy ở mục 1).
2. Bật API: Vertex AI / Agent Platform (`aiplatform.googleapis.com`), Cloud Text-to-Speech (`texttospeech.googleapis.com`), và nếu dùng Chirp thì Cloud Speech-to-Text (`speech.googleapis.com`).
3. Chạy `gcloud auth application-default login`.
4. Chọn location: Gemini và Gemini 3.5 Transcribe dùng `global` [D8][S8]; Chirp 3 dùng `us` hoặc `eu` [S1]; Chirp 3 HD TTS dùng `global` [T1].
5. Nếu dùng BatchRecognize thì tạo GCS bucket cùng project; service agent của Speech mặc định đọc được bucket trong cùng project [S4].

---

## Bảng giá tổng hợp

Giá USD, Standard PayGo, endpoint global, truy cập 2026-10-22.

| Dịch vụ | Đơn vị | Giá | Free/tháng | Ghi chú | Nguồn |
|---|---|---|---|---|---|
| `gemini-3.8-flash` (cả 3.7/3.6) | 1M token in / out | $0,75 / $3,75 → $1,50 / $7,50 từ 1/1/2027 | — | Ưu đãi qua "50% credits back"; output gồm reasoning | [P1] |
| `gemini-3.5-flash` | 1M token in / out | $1,50 / $9,00 | — | | [P1] |
| `gemini-3.5-flash-lite` | 1M token in / out | $0,30 / $2,50 | — | | [P1] |
| `gemini-3.1-flash-lite` | 1M token in / out | $0,25 / $1,50 | — | audio in $0,50 | [P1] |
| `gemini-2.5-flash` | 1M token in / out | $0,30 / $2,50 | — | audio in $1,00 | [P1] |
| `gemini-2.5-flash-lite` | 1M token in / out | $0,10 / $0,40 | — | audio in $0,30 | [P1] |
| `gemini-3.1-pro-preview` | 1M token in / out (≤200K) | $2,00 / $12,00 | — | | [P1] |
| Gemini 3.5 Transcribe | 1M audio token / 1M text token | $2,00 / $12,00 (≈ $0,0051/phút) | — | Bản Live: $3,50 / $21 (≈ $0,0089/phút) | [P1] |
| STT v2 Standard (gồm `chirp`) | phút | $0,016 (0–500K phút) | không (V1: 60 phút) | Chirp 3 suy luận, chưa xác minh | [P2][F1] |
| STT v2 Dynamic Batch | phút | $0,003 | — | cần GCS | [P2] |
| TTS Chirp 3: HD | 1M ký tự | $30 | 1M ký tự | | [P3] |
| TTS Instant Custom Voice | 1M ký tự | $60 | — | allowlist | [P3][T2] |
| TTS Neural2 / Polyglot | 1M ký tự | $16 | 1M ký tự | | [P3] |
| TTS WaveNet / Standard | 1M ký tự | $4 | 4M ký tự | | [P3] |
| TTS Studio | 1M ký tự | $160 | 1M ký tự | | [P3] |
| Gemini 2.5 Flash TTS | 1M text token / 1M audio token | $0,50 / $10 | — | 25 audio token/giây | [P3] |
| Gemini 2.5 Pro TTS, 3.1 Flash TTS | 1M text / audio token | $1 / $20 | — | | [P3] |
| Gemini 3.8 Flash TTS | 1M text / audio token | $0,50 / $9 → $1 / $18 từ 1/1/2027 | — | Preview, chỉ qua Gemini Enterprise API | [P3][T4] |
| Gemini 3.8 Flash-Lite TTS | 1M text / audio token | $0,50 / $6 → $1 / $12 từ 1/1/2027 | — | Preview | [P3] |
| Soniox STT async (đối chiếu) | giờ | ≈ $0,10 | — | nguồn của Soniox | [X1] |

## Điểm tích hợp trong code

Theo dạng bảng "Móc nối vào file lõi" của `CUSTOM.md`.

| File:dòng | Thay đổi dự kiến | Tính năng |
|---|---|---|
| `core/utils/ask_gpt.py:59` `get_api_key()` | Nhánh Vertex: lấy và refresh OAuth token từ ADC (cache ở cấp module) | LLM |
| `core/utils/ask_gpt.py:74` | Bẫy `'ark' in base_url`. Nên kiểm tra host Vertex trước dòng này | LLM |
| `core/utils/ask_gpt.py:116-127` | Giữ nguyên `OpenAI(...)` và `response_format`. Có thể thêm `reasoning_effort` để kiểm soát thinking | LLM |
| `core/asr_backend/vertex_asr.py` (file mới) | `transcribe_audio_vertex(raw, vocal, start, end)` trả về `{"segments":[{"text","start","end","words":[...]}], "language"}`, giống `soniox2whisper` (`core/asr_backend/soniox_asr.py:131`) | STT |
| `core/_2_asr.py:40`, `:49`, `:75-79`, `:96` | Thêm `"vertex"` vào danh sách runtime; kiểm tra credential trước khi chuẩn bị media; cắt đoạn ≤15 phút (`split_audio(..., target_len=…)`); thêm nhánh `elif` | STT |
| `core/st_utils/sidebar_setting.py:225`, `:237`, `:265` | Ô chọn runtime và ô nhập project/location | STT |
| `core/tts_backend/vertex_tts.py` (file mới) | Gọi `text:synthesize` (Chirp 3 HD) và ghi LINEAR16 ra `.wav` | TTS |
| `core/tts_backend/tts_main.py:15`, `:65` | Import và nhánh `elif TTS_METHOD == 'vertex_tts'` | TTS |
| `core/st_utils/tts_settings.py:3-19` | Thêm provider "Google Cloud" vào `PROVIDERS`. `KEY_PATHS` không cần, vì dùng ADC thay cho key | TTS |
| `core/st_utils/sidebar_setting.py:402`, `:493` | Nhãn và nhánh gọi bộ chọn giọng (`voices.list?languageCode=`) | TTS |
| `core/_10_gen_audio.py:114` | Không cần sửa: `tts_max_workers` vẫn áp dụng; quota 200 RPM của Chirp 3 dư cho 4 luồng | TTS |
| `config.yaml` | Mục mới `vertex:` (`project`, `location`, `credentials`), `tts_method: 'vertex_tts'`, mục `vertex_tts:` (`voice`, `language`, `speed`) | Chung |
| `Dockerfile` | Không cần sửa nếu mount credential lúc chạy | Chung |

Dependency mới: `google-auth` (LLM). Nếu dùng SDK thì thêm `google-genai` (bản mới nhất trên PyPI là 2.32.0 [X2]); `google-cloud-texttospeech` / `google-cloud-speech` là tùy chọn, có thể gọi REST bằng `requests` như `soniox_tts.py`.

## Câu hỏi mở cho người dùng

1. **LLM:** chọn `gemini-3.5-flash-lite` (rẻ, thinking minimal) hay `gemini-3.8-flash` (tốt hơn, có thinking, đắt hơn 2–5 lần)? Có muốn chạy thử song song với model OpenRouter hiện tại trên cùng clip (tiêu chí M0 trong PRD F2) không?
2. **STT:** có thật sự cần runtime Vertex không, khi Soniox rẻ hơn khoảng 3–10 lần và đã ổn định? Nếu có: chọn Gemini 3.5 Transcribe (không cần GCS, Experimental) hay Chirp 3 (cần GCS bucket)?
3. **TTS:** Chirp 3 HD tiếng Việt (có free tier) có thay VieNeu-TTS local không, hay chỉ là phương án dự phòng? Có cần clone giọng không? Nếu có, sẵn sàng liên hệ sales để xin allowlist Instant Custom Voice, hay thử Gemini 3.8 TTS voice replication (Preview, chưa rõ hỗ trợ tiếng Việt)?
4. **Tài khoản:** tài khoản trial có phải @gmail.com không, và có muốn upgrade lên Paid trước khi hết 90 ngày để giữ tài nguyên và được xin tăng quota không?
5. **Docker:** mount file ADC của người dùng hay tạo service account riêng có quyền tối thiểu?
6. Có chấp nhận thêm mục `vertex:` vào `config.yaml` và sửa thêm `ask_gpt.py` (file lõi, tăng rủi ro conflict khi rebase upstream) không?

---

## Nguồn

Tất cả truy cập ngày 2026-10-22.

- [P1] Vertex AI / Agent Platform pricing: https://cloud.google.com/vertex-ai/generative-ai/pricing
- [P2] Speech-to-Text pricing: https://cloud.google.com/speech-to-text/pricing
- [P3] Text-to-Speech pricing: https://cloud.google.com/text-to-speech/pricing
- [D1] Using OpenAI libraries (Chat Completions): https://cloud.google.com/vertex-ai/generative-ai/docs/migrate/openai/overview
- [D2] Chat Completions, Authenticate: https://cloud.google.com/vertex-ai/generative-ai/docs/migrate/openai/auth-and-credentials
- [D3] Express mode overview: https://cloud.google.com/vertex-ai/generative-ai/docs/start/express-mode/overview
- [D4] Get an API key: https://cloud.google.com/vertex-ai/generative-ai/docs/start/api-keys
- [D5] Structured output: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output
- [D6] Gemini 3.8 Flash: https://cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash
- [D7] Gemini 3.5 Flash-Lite: https://cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash-lite
- [D8] Standard PayGo / dynamic shared quota: https://cloud.google.com/vertex-ai/generative-ai/docs/dynamic-shared-quota
- [D9] Gen AI SDK overview: https://cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview
- [S1] Chirp 3: https://cloud.google.com/speech-to-text/v2/docs/chirp_3-model
- [S2] Chirp 2: https://cloud.google.com/speech-to-text/v2/docs/chirp_2-model
- [S3] STT quotas and limits: https://cloud.google.com/speech-to-text/v2/docs/quotas
- [S4] Batch recognize: https://cloud.google.com/speech-to-text/v2/docs/batch-recognize
- [S5] Sync recognize: https://cloud.google.com/speech-to-text/v2/docs/sync-recognize
- [S6] STT supported languages: https://cloud.google.com/speech-to-text/v2/docs/speech-to-text-supported-languages
- [S7] Gemini audio understanding: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/audio-understanding
- [S8] Gemini 3.5 Transcribe: https://cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-transcribe
- [T1] Chirp 3: HD voices: https://cloud.google.com/text-to-speech/docs/chirp3-hd
- [T2] Instant Custom Voice: https://cloud.google.com/text-to-speech/docs/chirp3-instant-custom-voice
- [T3] Gemini-TTS (Cloud TTS): https://cloud.google.com/text-to-speech/docs/gemini-tts
- [T4] Gemini 3.8 TTS (Agent Platform): https://cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/overview
- [T5] TTS quotas and limits: https://cloud.google.com/text-to-speech/quotas
- [T6] Voices list / voice types: https://cloud.google.com/text-to-speech/docs/reference/rest/v1/voices/list, https://cloud.google.com/text-to-speech/docs/list-voices-and-types
- [T7] AudioConfig: https://cloud.google.com/text-to-speech/docs/reference/rest/v1/AudioConfig
- [F1] Google Cloud Free Program (Free Trial, Free Tier): https://cloud.google.com/free/docs/free-cloud-features
- [A1] Set up ADC: https://cloud.google.com/docs/authentication/provide-credentials-adc
- [A2] How ADC works: https://cloud.google.com/docs/authentication/application-default-credentials
- [X1] Soniox pricing (trang của Soniox): https://soniox.com/pricing
- [X2] `google-genai` 2.32.0 trên PyPI, source `google/genai/client.py`, `_api_client.py`, `types.py`: https://pypi.org/project/google-genai/
