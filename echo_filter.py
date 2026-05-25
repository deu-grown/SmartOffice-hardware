import serial
import time

def get_real_co2():
    port = "/dev/serial0"
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=2)
        
        # 1. 이전 쓰레기 데이터 비우기
        ser.reset_input_buffer()
        
        # 2. 명령어 전송 (0x86: 가스 농도 읽기)
        cmd = b"\xff\x01\x86\x00\x00\x00\x00\x00\x79"
        ser.write(cmd)
        
        # 3. 넉넉하게 읽기 (에코 데이터가 섞여 들어올 것을 대비)
        # 보통 에코가 있다면 [요청문 9바이트] + [응답문 9바이트] = 총 18바이트가 들어옵니다.
        time.sleep(0.5)
        data = ser.read(20)
        
        if not data:
            return "No Data"

        # 4. 진짜 응답(FF 86)의 위치를 찾습니다.
        # 데이터 시퀀스 중 FF 86 으로 시작하는 구간을 검색
        response_start = data.find(b"\xff\x86")
        
        if response_start != -1:
            # 찾은 위치부터 9바이트가 실제 센서 응답입니다.
            actual_res = data[response_start : response_start + 9]
            
            if len(actual_res) == 9:
                high = actual_res[2]
                low = actual_res[3]
                co2 = (high * 256) + low
                return co2
            else:
                return "Incomplete Response"
        else:
            # FF 86을 못 찾았다면 에코 데이터(FF 01...)만 들어온 것임
            return f"Echo detected but no sensor response. (Raw: {data.hex()})"

    except Exception as e:
        return f"Error: {e}"
    finally:
        if 'ser' in locals(): ser.close()

if __name__ == "__main__":
    print("라즈베리파이 5 CO2 모니터링 시작 (에코 필터링 모드)")
    while True:
        result = get_real_co2()
        if isinstance(result, int):
            print(f"현재 실제 CO2 농도: {result} ppm")
        else:
            print(f"상태: {result}")
        
        time.sleep(5)