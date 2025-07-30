import threading
import numpy as np
import select 
import librosa 
from discord.sinks import RawData, RecordingException
from discord.voice_client import VoiceClient
from discord import opus
import requests
import websockets
import json
import asyncio


class CustomVoiceClient(VoiceClient):
    
    def unpack_audio(self, data):
        self.is_silence = False

        if 200 <= data[1] <= 204:
            # RTCP received.
            return None, None
        if self.paused:
            return None, None

        data = RawData(data, self)

        if data.decrypted_data == b"\xf8\xff\xfe":  # Frame of silence
            self.is_silence =True
            return None, None
    
        data_decode = self.decoder.decode(data.decrypted_data) # len(data_decode) = 3840 ở 48khz <=> 20ms
        ssrc_id = data.ssrc
        if data_decode is None:
            return ssrc_id, None

        # Chuyển từ stereo sang mono và resample từ 48kHz xuống 16kHz
        # Chuyển từ buffer sang numpy array
        pcm_array = np.frombuffer(data_decode, dtype=np.int16)

        # Chuyển từ stereo sang mono bằng cách lấy trung bình
        pcm_mono = np.mean(pcm_array.reshape(-1, 2), axis=1).astype(np.float32) / 32768.0
        pcm_resampled = librosa.resample(pcm_mono, orig_sr=48000, target_sr=16000)
        return ssrc_id, pcm_resampled 
    
    
    def recv_decoded_audio(self, data: RawData):
        pass


    def insert_buffer_tuple(self, ssrc, segment, segment_info):
        self.tuple_buffer.append((ssrc, segment, segment_info))
        
    def receive_audio_chunk(self):
        PACKET_SIZE = 32000*5*60
        out = []
        minlimit = self.min_chunk_size * self.SAMPLING_RATE
        previous_out = 0
        count_consecutive_silence = 0 # số silence liên tiếp
        count_silence = 0    # tính số silence mọi trường hợp trong 1 lần while
        segment_info = None
        len_out = 0 # cần thay đổi để lưu giá trị khi thay đổi ssrc

        if self.temp_audio_chunk is not None:
            out.append(self.temp_audio_chunk)
            self.temp_audio_chunk = None
            len_out = sum(len(x) for x in out)
            self.current_samples += len_out

        while (len_out + previous_out) < minlimit:
            ready, _, err = select.select([self.socket], [], [self.socket], 0.01)
            if not ready:
                if err:
                    print(f"Socket error: {err}")
                continue
            
            try:
                #raw_bytes = self.socket.recv(PACKET_SIZE)
                raw_bytes = self.socket.recv(4096)
            except OSError as e:
                print("loi OSError",e, flush=True)
                self.stop_recording()
                # raw_bytes = None
                continue

            ssrc_id, data_float_32 = self.unpack_audio(raw_bytes)

            if self.is_silence == True:
                count_consecutive_silence += 1 # dùng để đếm số silence liên tiếp
                count_silence += 1 # 1 frame silence = 320 samples # dùng để đém số slience liên tiếp và xen kẻ trong 1 lần xử lý
                self.current_samples += 320 
                len_out += 320

            '''
            nếu trước đó là đoạn nói và cộng thêm 0.5s silence
            còn lại thì cứ tính silence và cộng dồn current_samples, nào gặp đoạn nói chuyện thì cứ thêm vào out
            '''
            if count_consecutive_silence >= 25: 
                break

            # Handle speaker change when there is no silence between two speakers
            if self.speaker is not None and ssrc_id is not None and self.speaker != ssrc_id:
                self.temp_audio_chunk = data_float_32
                self.temp_speaker = ssrc_id
                self.speaker_changed= True
                break 
                
            if data_float_32 is None:
                continue
            
            # TH data_float_32 != None
            self.speaker = ssrc_id # silence -> continue
            out.append(data_float_32)
            len_out += len(data_float_32)
            self.current_samples += 320
            count_consecutive_silence = 0 # Handle cases with interleaved silence and sound
        
        # if not out: 
        #     return None
        if (len(out) != 0 ): 
            conc = np.concatenate(out)

            if self.is_first and len(conc) < minlimit:
                self.is_first = False
            else:
                if self.speaker_changed == True:
                    if self.triggered == False: 
                        time_start = self.current_samples -count_silence - len(conc)
                        time_end = self.current_samples 
                        segment_info = {
                            "start_time": time_start,
                            "end_time": time_end
                        }
                    elif self.triggered == True:
                        time_end = self.current_samples
                        self.triggered = False # xem lại
                        segment_info = {
                            "start_time": None,
                            "end_time": time_end
                        }
                    self.speaker_changed = False
                else: # # Handle behavior: speaker must talk for at least 1 second to be considered meaningful; otherwise, pass
                    if count_consecutive_silence >= 25 and self.triggered == False:
                        time_start = self.current_samples -count_silence - len(conc)
                        time_end = self.current_samples - 320 * 10
                        segment_info = {
                            "start_time": time_start,
                            "end_time": time_end
                        }
                    elif self.triggered == False: # non voice > 0.5 + voice 
                        time_start = self.current_samples - len(conc)- count_silence
                        self.triggered = True
                        segment_info = {
                            "start_time": time_start,
                            "end_time": None
                        }
                    # ngược lại âm thanh đã có và tiếp tục âm thanh mới, ko cần trả start, trả về end
                    elif count_consecutive_silence >= 25 and self.triggered == True:
                        time_end = self.current_samples - 320 * 10
                        self.triggered = False
                        segment_info = {
                            "start_time": None,
                            "end_time": time_end
                        }
                # default segment_info = None

                self.insert_buffer_tuple(self.speaker, conc, segment_info)

        if count_consecutive_silence  >= 25: # # Return None when silence is detected
            self.speaker = None

    async def post_audio_data_ws(self, websocket, audio_samples, ssrc_id, segment_info, buffer_offset):
        """Gửi dữ liệu âm thanh qua WebSocket"""
        audio_list = audio_samples.tolist()
        
        # Tạo JSON payload
        payload = {
            "audio": audio_list,
            "ssrc_id": ssrc_id,
            "segment_infor": segment_info,
            "buffer_offset": buffer_offset
        }
        
        # Gửi dữ liệu qua WebSocket
        await websocket.send(json.dumps(payload))
        
        # Nhận kết quả trả về
        response = await websocket.recv()
        response_data = json.loads(response)
        
        # Xử lý kết quả trả về
        if "transcription" in response_data and response_data["transcription"]:
            print(f"Transcription (WebSocket): {response_data['transcription']}", flush=True)
        
        return response_data
    
    def post_audio_data(self, api_url, audio_samples, ssrc_id, segment_info, buffer_offset):
        """Legacy HTTP POST method (giữ lại cho tương thích ngược)"""
        audio_list = audio_samples.tolist()
        
        if segment_info is not None:
            print("is not None +++", flush = True)
        else:
            print("is None +++", flush = True)
        
        response = requests.post(
            api_url,
            json={
                "audio": audio_list,
                "ssrc_id": ssrc_id,
                "segment_infor": segment_info,
                "buffer_offset": buffer_offset
            }   
        )
        
        # Trả về response để sử dụng nếu cần
        return response.json() if response.status_code == 200 else None
    
    def recv_audio(self, *args):
        self.tuple_buffer = [] 
        self.audio_buffer = []
        
        # Đọc file ngrok_url vào biến url
        with open("/home/trungnothot/Study/Thesis/audio-us-discord-bot/discord_recording_bot/ngrok_url.txt", "r") as file:
            url = file.read().strip()
        
        if self.use_websocket:
            # Thay đổi URL từ HTTP sang WebSocket
            ws_url = f"{url.replace('http', 'ws')}/ws/transcribe"
            
            # Tạo event loop riêng cho WebSocket
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Hàm xử lý WebSocket
            async def process_audio_with_websocket():
                async with websockets.connect(ws_url) as websocket:
                    print(f"Connected to WebSocket server at {ws_url}", flush=True)
                    
                    while self.recording:
                        self.receive_audio_chunk()
                        
                        if self.tuple_buffer:
                            print("độ dài tuple: ", len(self.tuple_buffer), flush=True)
                            
                            first_tuple = self.tuple_buffer[0]
                            ssrc_id, conc, inf = first_tuple
                            self.tuple_buffer = []
                            
                            # Gửi dữ liệu qua WebSocket
                            await self.post_audio_data_ws(websocket, conc, ssrc_id, inf, self.buffer_offset)
                            self.buffer_offset = self.current_samples
            
            # Chạy coroutine xử lý WebSocket
            try:
                loop.run_until_complete(process_audio_with_websocket())
            except Exception as e:
                print(f"WebSocket error: {e}", flush=True)
            finally:
                loop.close()
        else:
            # Sử dụng HTTP API như cũ
            api_url = f"{url}/transcribe"
            while self.recording:
                self.receive_audio_chunk()

                if self.tuple_buffer:
                    print("độ dài tuple: ", len(self.tuple_buffer), flush=True)
                    
                    first_tuple = self.tuple_buffer[0]
                    ssrc_id, conc, inf = first_tuple
                    self.tuple_buffer = []
                    self.post_audio_data(api_url, conc, ssrc_id, inf, self.buffer_offset)
                    self.buffer_offset = self.current_samples

    def start_recording(self, *args, sync_start: bool = True, use_websocket: bool = True):
        if not self.is_connected():
            raise RecordingException("Not connected to voice channel.")
        if self.recording:
            raise RecordingException("Already recording.")
        

        self.empty_socket()
        self.SAMPLING_RATE = 16000
        self.min_chunk_size = 0.5
        self.tuple_buffer = []
        self.current_samples = 0 # samples từ start đến stop
        self.buffer_offset = 0
        self.decoder = opus.Decoder()
        self.recording = True
        self.is_first = True 
        self.triggered = False #True: voice, False: non-voice
        self.speaker_changed = False
        self.speaker = None # None: bắt đầu câu mới;  ssrc_id : người đang nói
        self.temp_audio_chunk = None # lưu âm thanh tạm thời khi chuyển đổi người mới
        self.temp_speaker = None # lưu tạm người nói khi chuyển đổi
        self.sync_start = sync_start
        self.use_websocket = use_websocket  # Flag để chọn phương thức giao tiếp

        t = threading.Thread(
            target=self.recv_audio,
            args=(
                *args,
            ),
        )
        t.start()

    def stop_recording(self):
        """Stops the recording.
        Must be already recording.

        .. versionadded:: 2.0

        Raises
        ------
        RecordingException
            Not currently recording.
        """
        if not self.recording:
            raise RecordingException("Not currently recording audio.")
        self.recording = False
        self.paused = False

