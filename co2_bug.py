import serial
import time

def debug_co2():
    port = "/dev/ttyAMA0" # 또는 "/dev/ttyS0"
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=3)
        print(f"[{port}] 연결 시도 중...")
        
        # 데이터 요청 커맨드
        cmd = b"\xff\x01\x86\x00\x00\x00\x00\x00\x79"
        ser.write(cmd)
        
        # 응답 대기
        res = ser.read(9)
        
        if len(res) == 0:
            print("응답 없음: 센서로부터 데이터가 한 바이트도 오지 않습니다. (연결/전원 확인)")
        elif len(res) < 9:
            print(f"데이터 부족: 9바이트가 와야 하는데 {len(res)}바이트만 왔습니다. (노이즈/설정 확인)")
            print(f"받은 데이터: {res.hex()}")
        else:
            print(f"데이터 수신 성공: {res.hex()}")
            high = res[2]
            low = res[3]
            print(f"계산된 CO2: {(high * 256) + low} ppm")
            
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        if 'ser' in locals(): ser.close()

if __name__ == "__main__":
    debug_co2()