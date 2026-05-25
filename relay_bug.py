import time
from gpiozero import OutputDevice

# 솔레노이드가 연결된 GPIO 핀 번호 (GPIO 21번 / 물리 핀 40번)
RELAY_PIN = 24

try:
    print(f"[{RELAY_PIN}번 핀] 릴레이 테스트를 시작합니다.")
    print("정상 작동 시 1초 간격으로 '딸깍' 소리와 함께 모듈의 LED가 깜빡입니다.")
    print("종료하려면 Ctrl + C를 누르세요.\n")
    
    # 릴레이 객체 생성
    relay = OutputDevice(RELAY_PIN, active_high=False, initial_value=False)
    
    count = 1
    while True: 
        print(f"[{count}회차] 릴레이 ON 시도...")
        relay.on()  # 핀에 High(3.3V) 신호 공급
        time.sleep(1)
        
        print(f"[{count}회차] 릴레이 OFF 시도...")
        relay.off() # 핀에 Low(0V) 신호 공급
        time.sleep(1)
        
        count += 1

except KeyboardInterrupt:
    print("\n테스트를 종료합니다.")