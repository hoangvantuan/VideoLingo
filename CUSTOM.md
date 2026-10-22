# CUSTOM — các thay đổi của fork `hoangvantuan/VideoLingo`

Yêu cầu và lộ trình: [`docs/PRD-custom.md`](docs/PRD-custom.md). Khi rebase lên upstream, kiểm tra các file trong bảng "Móc nối vào file lõi" trước.

## File mới (không xung đột với upstream)

| File | Mục đích |
|---|---|
| `core/asr_backend/soniox_asr.py` | F1 — runtime ASR `soniox` (Soniox async API `stt-async-v5`) |
| `tests/test_soniox_asr.py` | Test cho F1 |
| `CUSTOM.md` | Tài liệu này |
| `docs/PRD-custom.md` | PRD của fork |

## Móc nối vào file lõi

Các dòng thêm vào đều có chú thích `# custom`.

| File | Thay đổi | Số dòng |
|---|---|---|
| `core/_2_asr.py` | thêm `"soniox"` vào danh sách runtime; kiểm tra key trước khi chuẩn bị media; nhánh `elif runtime == "soniox"` | 6 |
| `config.yaml` | khóa `whisper.soniox_api_key` và ghi chú runtime | 3 |

## Cấu hình F1 (Soniox)

```yaml
whisper:
  runtime: 'soniox'
  language: 'en'        # hoặc 'ja', hoặc 'auto' (gợi ý en + ja, bật nhận diện ngôn ngữ)
  soniox_api_key: ''    # để trống, đặt biến môi trường SONIOX_API_KEY
```

- Key đọc theo thứ tự: `SONIOX_API_KEY` → `whisper.soniox_api_key`.
- File âm thanh và transcription trên Soniox luôn bị xóa sau mỗi đoạn, kể cả khi lỗi.
- Cache ASR dùng nhánh chung của `transcription_cache.cache_key`, nên đổi phiên bản package local (qwen-asr, transformers, demucs…) sẽ làm mất cache Soniox. Chấp nhận để không phải sửa thêm file lõi.
