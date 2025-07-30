# Smart Meeting Assistant for Discord

Hệ thống trợ lý thông minh cho cuộc họp Discord với khả năng ghi âm, chuyển đổi giọng nói thành văn bản và tóm tắt nội dung.

## 🏗️ Kiến trúc hệ thống

Dự án bao gồm 4 thành phần chính:

### 1. `audio-us-backend` - Go Backend API
- **Công nghệ**: Go, Fiber framework
- **Chức năng**: 
  - API REST cho việc quản lý recordings
  - Discord OAuth authentication
  - WebSocket real-time communication
  - Database integration với PostgreSQL
- **Port**: 8080
- **Docker**: Có hỗ trợ containerization

### 2. `audio-us-discord-bot` - Python Discord Bot
- **Công nghệ**: Python, Pycord
- **Chức năng**:
  - Bot Discord để ghi âm voice channel
  - Tích hợp Whisper cho speech-to-text
  - Streaming audio processing
- **Dependencies**: pycord, whisper, ngrok

### 3. `audio-us-front-end` - Next.js Frontend
- **Công nghệ**: Next.js 15, TypeScript, Tailwind CSS
- **Chức năng**:
  - Giao diện người dùng responsive
  - Discord login integration
  - Chat room interface
  - AI agent interaction
- **Port**: 3000

### 4. `audio-us-model` - ML Model Server
- **Công nghệ**: Python, Whisper, FastAPI
- **Chức năng**:
  - Whisper model server cho speech recognition
  - Real-time audio streaming processing
  - GPU/CPU optimized containers
- **Features**: Whisper Live Kit, VAD (Voice Activity Detection)

## 🚀 Cài đặt và chạy

### Prerequisites
- Node.js 18+
- Go 1.21+
- Python 3.12+
- Docker & Docker Compose
- PostgreSQL

### Quick Start với Docker

```bash
# Clone repository
git clone <repository-url>
cd Smart-Meeting-Assistant-for-Discord

# Chạy backend với database
cd audio-us-backend
docker-compose up -d

# Chạy model server
cd ../audio-us-model
docker-compose up -d

# Chạy frontend
cd ../audio-us-front-end
npm install
npm run dev

# Chạy Discord bot
cd ../audio-us-discord-bot
pip install -r requirements.txt
python discord_recording_bot/bot.py
```

### Development Setup

#### Backend (Go)
```bash
cd audio-us-backend
go mod download
make run-dev
```

#### Frontend (Next.js)
```bash
cd audio-us-front-end
npm install
npm run dev
```

#### Discord Bot (Python)
```bash
cd audio-us-discord-bot
uv sync
uv run python discord_recording_bot/bot.py
```

#### Model Server (Python)
```bash
cd audio-us-model
uv sync
uv run python run_audio_model.py
```

## 📁 Cấu trúc thư mục

```
Smart-Meeting-Assistant-for-Discord/
├── audio-us-backend/          # Go API backend
│   ├── cmd/api/              # API handlers
│   ├── internal/             # Internal packages
│   └── deploy/               # Kubernetes configs
├── audio-us-discord-bot/     # Python Discord bot
│   ├── discord_recording_bot/ # Bot implementation
│   └── whisper_streaming_custom/ # Custom Whisper integration
├── audio-us-front-end/       # Next.js frontend
│   ├── src/app/             # App router pages
│   ├── src/components/      # React components
│   └── public/              # Static assets
└── audio-us-model/          # ML model server
    ├── whisperlivekit/      # Whisper Live Kit
    └── deploy/              # Deployment configs
```

## 🔧 Cấu hình

### Environment Variables

#### Backend (.env)
```env
DATABASE_URL=postgresql://...
DISCORD_CLIENT_ID=your_discord_client_id
DISCORD_CLIENT_SECRET=your_discord_client_secret
JWT_SECRET=your_jwt_secret
```

#### Discord Bot
```env
DISCORD_BOT_TOKEN=your_bot_token
NGROK_URL=your_ngrok_url
```

#### Frontend
```env
NEXT_PUBLIC_API_URL=http://localhost:8080
NEXT_PUBLIC_DISCORD_CLIENT_ID=your_discord_client_id
```

## 🌟 Tính năng

- ✅ **Discord Integration**: Đăng nhập qua Discord OAuth
- ✅ **Voice Recording**: Ghi âm voice channel Discord
- ✅ **Speech-to-Text**: Chuyển đổi giọng nói thành văn bản với Whisper
- ✅ **Real-time Processing**: Xử lý audio streaming real-time
- ✅ **Web Interface**: Giao diện web responsive
- ✅ **AI Assistant**: Tích hợp AI agent cho tóm tắt cuộc họp
- ✅ **Containerized**: Hỗ trợ Docker deployment

## 🚀 Deployment

### Local Development
```bash
make dev-all  # Chạy tất cả services
```

### Production
```bash
make deploy-prod  # Deploy production với Docker
```

### Kubernetes
```bash
kubectl apply -f audio-us-backend/deploy/
kubectl apply -f audio-us-model/deploy/
```

## 🤝 Contributing

1. Fork repository
2. Tạo feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing-feature`)
5. Tạo Pull Request

## 📝 License

MIT License - xem file LICENSE để biết chi tiết.

## 🔗 Links

- [Backend API Documentation](./audio-us-backend/README.md)
- [Discord Bot Setup](./audio-us-discord-bot/README.md)
- [Frontend Guide](./audio-us-front-end/README.md)
- [Model Server Guide](./audio-us-model/README.md)
