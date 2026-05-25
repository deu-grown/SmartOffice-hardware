import time
from gpiozero import OutputDevice  # 라즈베리파이 GPIO 제어 라이브러리

# [설정] 솔레노이드가 연결된 릴레이 핀 번호 (GPIO 21번 / 물리 핀 40번)
# active_high=True: 신호가 High(1)일 때 릴레이 작동
# initial_value=False: 프로그램 시작 시 기본적으로 문이 열린(신호 없음) 상태로 시작
lock_relay = OutputDevice(24, active_high=False, initial_value=False)

def control_loop():
    print("==========================================")
    print("      솔레노이드 락 수동 제어 시스템      ")
    print("==========================================")
    print(" 1 : 닫기 (잠금)")
    print(" 0 : 열기 (해제)")
    print(" q : 프로그램 종료")
    print("------------------------------------------")

    while True:
        # 사용자 입력 받기
        user_input = input("명령을 입력하세요 (1/0/q): ").strip()

        if user_input == '1':
            lock_relay.on()
            print("🔒 솔레노이드 락 [닫힘/잠금]")
            
        elif user_input == '0':
            lock_relay.off()
            print("🔓 솔레노이드 락 [열림/해제]")
            
        elif user_input.lower() == 'q':
            print("프로그램을 종료합니다.")
            break
            
        else:
            print("❌ 잘못된 입력입니다. 1, 0, q 중 하나를 입력하세요.")

        # --- [추후 구현할 NFC 카드 기능 자리] ---
        # 나중에 NFC 태그 인식 기능이 완성되면 이 루프 안에 결합할 예정입니다.
        # if nfc_card_detected():
        #     card_id = read_nfc_id()
        #     if card_id == REGISTERED_CARD:
        #         lock_relay.toggle() # 현재 상태 반전 (열려있으면 닫고, 닫혀있으면 열기)
        # ----------------------------------------

if __name__ == "__main__":
    try:
        control_loop()
    except KeyboardInterrupt:
        print("\n[Ctrl+C]에 의해 프로그램이 강제 종료되었습니다.")
    finally:
        # 프로그램이 종료될 때 전원을 차단하여 솔레노이드가 과열되는 것을 방지합니다.
        lock_relay.off()
        print("안전을 위해 솔레노이드 전원을 차단하고 종료합니다.")