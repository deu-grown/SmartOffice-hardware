import serial
import time
import requests

SERIAL_PORT = port = "/dev/ttyAMA0" # 또는 "/dev/ttyS0"
BACKEND_URL = "http://your-backend-ip:8000/data"

def get_co2_robust():
    try:
        # 설정을 약간 변경: 읽기 타임아웃을 넉넉히 줍니다.
        ser = serial.Serial(SERIAL_PORT, baudrate=9600, timeout=3)
        
        # 1. 버퍼에 쌓인 찌꺼기(에코 등)를 모두 비웁니다.
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # 2. 명령 전송
        ser.write(b"\xff\x01\x86\x00\x00\x00\x00\x00\x79")
        
        # 3. 데이터가 들어올 때까지 잠시 대기 (라즈베리파이 5는 이게 중요합니다)
        time.sleep(0.5)
        
        # 4. 넉넉하게 30바이트 정도 읽어버립니다.
        raw = ser.read(30)
        
        if not raw:
            return "No data received"

        # 5. 데이터 뭉치 안에서 ff 86 (응답 시작점)을 찾습니다.
        # find()는 가장 먼저 나타나는 위치를 알려줍니다.
        start_idx = raw.find(b"\xff\x86")
        
        if start_idx != -1 and len(raw) >= start_idx + 9:
            valid_data = raw[start_idx : start_idx + 9]
            high = valid_data[2]
            low = valid_data[3]
            co2 = (high * 256) + low
            
            # 값이 너무 터무니없지 않은지 체크 (정상 범위: 400~5000)
            if 300 < co2 < 10000:
                return co2
            else:
                return f"Out of range: {co2}"
        else:
            return f"Pattern ff86 not found. Raw: {raw.hex()}"

    except Exception as e:
        return f"Serial Error: {e}"
    finally:
        if 'ser' in locals():
            ser.close()

if __name__ == "__main__":
    while True:
        result = get_co2_robust()
        if isinstance(result, int):
            print(f"✅ 현재 CO2: {result} ppm")
            # 여기서 requests.post(...)를 호출하세요.
        else:
            print(f"❌ 실패 사유: {result}")
        
        time.sleep(5)