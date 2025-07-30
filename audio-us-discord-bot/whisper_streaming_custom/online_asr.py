class VACOnlineASRProcessor:
    """
    Wraps an OnlineASRProcessor with a Voice Activity Controller (VAC).
    
    It receives small chunks of audio, applies VAD (e.g. with Silero),
    and when the system detects a pause in speech (or end of an utterance)
    it finalizes the utterance immediately.
    """
    SAMPLING_RATE = 16000

    def __init__(self, online_chunk_size: float, *args, **kwargs):
        self.online_chunk_size = online_chunk_size
        self.online = OnlineASRProcessor(*args, **kwargs)

        # Load a VAD model (e.g. Silero VAD)
        import torch
        model, _ = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad")
        from .silero_vad_iterator import FixedVADIterator

        self.vac = FixedVADIterator(model)
        self.logfile = self.online.logfile
        self.init()

    def init(self):
        self.online.init()
        self.vac.reset_states()
        self.current_online_chunk_buffer_size = 0
        self.is_currently_final = False
        self.status: Optional[str] = None  # "voice" or "nonvoice"
        self.audio_buffer = np.array([], dtype=np.float32)
        self.buffer_offset = 0  # in frames

    def clear_buffer(self):
        self.buffer_offset += len(self.audio_buffer)
        self.audio_buffer = np.array([], dtype=np.float32)

    def insert_audio_chunk(self, audio: np.ndarray):
        """
        Process an incoming small audio chunk:
          - run VAD on the chunk,
          - decide whether to send the audio to the online ASR processor immediately,
          - and/or to mark the current utterance as finished.
        """
        res = self.vac(audio)
        self.audio_buffer = np.append(self.audio_buffer, audio)
        '''
        theo như hiểu ở đây:
        - buffer_offset : là tổng độ dài đã xử lý tính cả nói và im lặng, tổng số mẫu được tính trên khz í
        - current_online_chunk_buffer_size là dữ liệu có trong audio , ví dụ khi đoạn âm thanh đạt đến 1s thì sẽ không tăng lên nữa
        - buffer_offset = buffer_offer + len(audio_chunk)
            + nếu im lặng thì cứ cộng dần cho đến khi start đoạn mới 
        - chèn padding trong trừng hợp có start hoặc có end, phải lùi hoặc tiếng thời gian để 
        '''

        if res is not None:
            # VAD returned a result; adjust the frame number
            frame = list(res.values())[0] - self.buffer_offset ## thời gian start/end - trừ đi số mẫu buffer đã xủ lý
            if "start" in res and "end" not in res:
                # xảy ra khii bắt đầu đoạn có giọng nói mới
                self.status = "voice" # báo hiệu bắt đầu đoạn nói liên tục 
                send_audio = self.audio_buffer[frame:] #Trích xuất từ frame (điểm bắt đầu) đến cuối self.audio_buffer.
                self.online.init(offset=(frame + self.buffer_offset) / self.SAMPLING_RATE)
                self.online.insert_audio_chunk(send_audio) # ở đây nó sẽ sử dụng insert_audio_chunk của onlineprocessorasr, để thêm đoạn audio đã chunk + padding
                self.current_online_chunk_buffer_size += len(send_audio)
                self.clear_buffer()# audio buffer clear ở đây là audio buffer của VAC
            elif "end" in res and "start" not in res:
                # xảy ra khi kết thúc giọng nói ( do im lặng hoặc đổi người nói)
                self.status = "nonvoice" # báo hiệu bắt đầu im lặng, người nói tạm dừng
                send_audio = self.audio_buffer[:frame] # tiến vào đoạn im lặng nên giữ lại đoạn cũ 
                self.online.insert_audio_chunk(send_audio)
                self.current_online_chunk_buffer_size += len(send_audio)
                self.is_currently_final = True
                self.clear_buffer()
            else:
                # xảy ra khi đoạn có giọng nói quá ngắn thì đã nói xong
                beg = res["start"] - self.buffer_offset
                end = res["end"] - self.buffer_offset
                self.status = "nonvoice"
                send_audio = self.audio_buffer[beg:end]
                self.online.init(offset=(beg + self.buffer_offset) / self.SAMPLING_RATE)
                self.online.insert_audio_chunk(send_audio)
                self.current_online_chunk_buffer_size += len(send_audio)
                self.is_currently_final = True
                self.clear_buffer()
        else:
            '''
            Giọng nói tiếp diễn (speech_prob >= 0.5, triggered = True).
            Im lặng ngắn (speech_prob < 0.35, chưa đủ 500ms).
            Im lặng kéo dài ngoài utterance (triggered = False).
            Ý nghĩa: Chunk không thay đổi trạng thái VAD (vẫn là giọng nói hoặc im lặng).
            '''
            if self.status == "voice":
                # xảy ra 
                self.online.insert_audio_chunk(self.audio_buffer)
                self.current_online_chunk_buffer_size += len(self.audio_buffer)
                self.clear_buffer()
            else:
                # Keep 1 second worth of audio in case VAD later detects voice,
                # but trim to avoid unbounded memory usage.
                self.buffer_offset += max(0, len(self.audio_buffer) - self.SAMPLING_RATE)
                self.audio_buffer = self.audio_buffer[-self.SAMPLING_RATE:]

    def process_iter(self) -> Transcript:
        """
        Depending on the VAD status and the amount of accumulated audio,
        process the current audio chunk.
        """
        if self.is_currently_final:
            return self.finish()
        elif self.current_online_chunk_buffer_size > self.SAMPLING_RATE * self.online_chunk_size:
            self.current_online_chunk_buffer_size = 0
            return self.online.process_iter()
        else:
            logger.debug("No online update, only VAD")
            return Transcript(None, None, "")

    def finish(self) -> Transcript:
        """Finish processing by flushing any remaining text."""
        result = self.online.finish()
        self.current_online_chunk_buffer_size = 0
        self.is_currently_final = False
        return result
    
    def get_buffer(self):
        """
        Get the unvalidated buffer in string format.
        """
        return self.online.concatenate_tokens(self.online.transcript_buffer.buffer).text