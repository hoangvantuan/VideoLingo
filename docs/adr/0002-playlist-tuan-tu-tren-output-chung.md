# Lượt chạy playlist tuần tự trên `output/` dùng chung

Pipeline đọc và ghi mọi file trung gian theo đường dẫn cố định `output/...` (khoảng 20 module trong `core/`), và đọc cài đặt trực tiếp từ `config.yaml` ở từng bước. Để có xử lý Playlist sớm, chúng tôi cho **Lượt chạy playlist** chạy **tuần tự từng video trên chính `output/`**: tải → chạy pipeline → chuyển sang `history/<tên playlist>/<số thứ tự> - <tên video>/` → video kế. Chúng tôi không tách workspace theo job, cũng không "chụp" cài đặt cho từng lượt chạy. Lý do: tận dụng được nguyên pipeline, cơ chế chạy tiếp nhờ file trung gian và cơ chế lưu vào history sẵn có, không phải sửa từng chỗ dùng `output/` hay `load_key`.

## Considered Options

- **Workspace riêng cho từng job, chạy song song**: là đích đến lâu dài, nhưng phải đổi mọi đường dẫn `output/` thành tham số. Ngoài ra còn phải giải quyết `TaskRunner._current` (cấp class), cấu hình chung, tranh chấp GPU khi ASR/Demucs chạy local và rate limit của Provider. Phần này để dành cho một effort riêng (`/wayfinder`).

## Consequences

- Mỗi lúc chỉ có một Lượt chạy playlist. Trong lúc nó chạy, chế độ 1 video trên Streamlit bị khoá, còn `api.py` từ chối bằng `409` thông qua khoá dạng file trong `output/`.
- Khi một video `Lỗi` hoặc bị Stop, file dở của nó được chuyển vào thư mục history của video đó để `output/` trống lại. Lúc chạy lại, các file được chuyển ngược về `output/`.
- Sửa cài đặt trong lúc lượt chạy đang chạy sẽ áp dụng cho các bước và video tiếp theo.
- Khi chuyển sang chạy song song, ADR này cần được thay thế.
