import RPi.GPIO as GPIO
import time

# 사용할 GPIO 핀 번호 설정 (BCM 모드 기준 25번)
LED_PIN = 23

# GPIO 초기 설정
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

print("=== 5V COB LED 스트립 제어 프로그램 ===")
print("1: LED 켜기 | 0: LED 끄기 | q: 프로그램 종료")
print("---------------------------------------")

try:
    while True:
        command = input("명령을 입력하세요 (1/0/q): ").strip().lower()
        
        if command == '1':
            GPIO.output(LED_PIN, GPIO.LOW)
            print("💡 LED 조명이 켜졌습니다.")
        elif command == '0':
            GPIO.output(LED_PIN, GPIO.HIGH)
            print("🌑 LED 조명이 꺼졌습니다.")
        elif command == 'q':
            print("👋 프로그램을 종료합니다.")
            break
        else:
            print("❌ 잘못된 입력입니다. 1, 0, q 중 하나를 입력하세요.")

except KeyboardInterrupt:
    print("\n강제 종료되었습니다.")

finally:
    # GPIO 설정 초기화 (라즈베리파이 보호를 위해 필수)
    GPIO.cleanup()