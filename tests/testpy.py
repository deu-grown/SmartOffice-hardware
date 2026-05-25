import time
from datetime import datetime, timezone, timedelta
import board
import adafruit_dht
import json
import requests  # HTTP 요청을 보내기 위해 추가

# 1. 백엔드 서버의 API 주소를 적어주세요.
# (예: "")
BACKEND_URL = "http://192.168.1.129:8080/api/v1/sensors/logs"

dht_device = adafruit_dht.DHT22(board.D4)

KST = timezone(timedelta(hours=9))

print("Starting DHT22 and sending data to backend...")

while True:
    try:
        temp = dht_device.temperature
        humi = dht_device.humidity
        now = datetime.now(KST)
        custom_timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")

        if temp is not None and humi is not None:
            #print(f"Temp: {temp:.1f}°C, Humidity: {humi:.1f}%")

            # 전송할 데이터 딕셔너리 생성
            payload1 = {
                "zoneId": 2,
                "sensorType": "TEMPARATURE",
                "deviceId": 1,
                "value": round(temp, 2),
                "unit": "C",
                "timestamp": custom_timestamp
            }

            payload2 = {
                "zoneId": 2,
                "sensorType": "HUMIDITY",
                "deviceId": 1,
                "value": round(humi, 2),
                "unit": "%",
                "timestamp": custom_timestamp
            }


            # HTTP Header 설정 (서버에게 우리가 JSON 데이터를 보낸다고 알려줌)
            headers = {
                "Content-Type": "application/json"
            }

            try:
                # 백엔드 서버로 POST 요청 보내기 (json=payload를 쓰면 자동으로 JSON 변환되어 전송됩니다)
                response1 = requests.post(BACKEND_URL, json=payload1, headers=headers, timeout=1)
                response2 = requests.post(BACKEND_URL, json=payload2, headers=headers, timeout=1)
                
                # 성공적으로 전송되었는지 확인 (HTTP 상태 코드 200번대 확인)
                if response1.status_code in [200, 201] and response2.status_code in [200, 201]:
                    print("Status: Data sent successfully!")
                else:
                    print(f"Status: Failed to send. Server responded with {response1.status_code} and humidity is {response2.status_code}")
            
            except requests.exceptions.RequestException as e:
                # 서버가 꺼져있거나 네트워크 연결이 끊겼을 때 예외 처리
                print(f"Network Error: Could not connect to backend. ({e})")

    except RuntimeError as error:
        # DHT22 센서 일시적 리드 에러 처리
        print(f"Sensor error: {error.args[0]}")
        
    except Exception as error:
        dht_device.exit()
        raise error

    # DHT22 센서 안정성을 위해 2초 대기
    time.sleep(2.0)
