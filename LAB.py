import RPi.GPIO as GPIO
import mfrc522
import signal
import time
import dropbox
import os
import sys
import picamera
import paho.mqtt.client as mqtt
import json
import MySQLdb
import urllib.request
import paho.mqtt.publish as publish

trigger_pin = 12
echo_pin = 11
LED_R = 36
LED_G = 40
LED_B = 38
GPIO.setmode(GPIO.BOARD)
GPIO.setup(26, GPIO.OUT)
GPIO.setup(LED_R, GPIO.OUT)
GPIO.setup(LED_G, GPIO.OUT)
GPIO.setup(LED_B, GPIO.OUT)
GPIO.setup(trigger_pin, GPIO.OUT)
GPIO.setup(echo_pin, GPIO.IN)
pwm = GPIO.PWM(26,523)
near_counter = 0
test_counter = 0
access = 0
gtimer = 0
bad = 0
good = 0
goodtime=0
host = "YOUR HOST ADDRESS OF MQTT BROKER"
topic1 = "iot01/rfid1"
topic2 = "iot01/rfid2"
topic3 = "iot01/BAD"#You can change the MQTT Topic if you want
auth = {'username': "", 'password': ""}
client_id = "xxx"

continue_reading = False

def end_read(signal,frame):
    global continue_reading
    print("End System.")
    GPIO.cleanup()
    pwm.stop()

def send_trigger_pulse():
    GPIO.output(trigger_pin,True)
    time.sleep(0.001)
    GPIO.output(trigger_pin,False)

def wait_for_echo(value, timeout):
    count = timeout
    while GPIO.input(echo_pin) != value and count > 0:
        count = count - 1

def get_distance():#get the distance between Ultrasonic and anything
    send_trigger_pulse()
    wait_for_echo(True, 5000)
    start = time.time()
    wait_for_echo(False, 5000)
    finish = time.time()
    pulse_len = finish - start
    distance_cm = pulse_len*17150 
    return (distance_cm)
 
 
# Hook the SIGINT
signal.signal(signal.SIGINT, end_read)
 
# Create an object of the class MFRC522
MIFAREReader = mfrc522.MFRC522()

dbx = dropbox.Dropbox("YOUR API KEY OF DROPBOX API")

camera = picamera.PiCamera()
camera.resolution = (640,480)

client = mqtt.Client()
client.username_pw_set("","")



try:
    GPIO.output(LED_R, GPIO.HIGH)
    GPIO.output(LED_G, GPIO.HIGH)
    GPIO.output(LED_B, GPIO.HIGH)
    publish.single( topic3, 0, qos = 0, hostname=host)#清除入侵人數
    while True:
        cm = get_distance()
        GPIO.output(LED_R, GPIO.HIGH)
        GPIO.output(LED_B, GPIO.HIGH)
        GPIO.output(LED_G, GPIO.HIGH)
        if cm <= 100 and good == 0:#偵測有東西在100CM內
            near_counter = near_counter + 1
            test_counter = test_counter + 1
        else :
            test_counter = test_counter + 1
            if good == 1:
                goodtime=goodtime+1
        print("cm=%f\t%d\t%d\n" %(cm,near_counter,test_counter) )
        if goodtime == 5 :#緩衝時間 讓已授權磁卡進入 5秒內超音波不感測
            good = 0
            goodtime =0
        if test_counter == 1 :#可調整 在test_counter次感測內要有near_counter次距離小於100CM
            test_counter = 0
            if near_counter >= 1 :#可調整 在test_counter次感測內要有near_counter次距離小於100CM
                near_counter = 0
                GPIO.output(LED_R, GPIO.LOW)#LED亮紅色
                ttimer = 0
                access = -1#預設為入侵者 讀取正確磁卡後才更改狀態
            # Scan for cards
                while ttimer < 20 :#在5秒內必須刷已授權的磁卡 否則觸發警報
                    (status,TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)
                    # If a card is found
                    if status == MIFAREReader.MI_OK:
                        print ("Card detected")   
                    # Get the UID of the card
                    (status,uid) = MIFAREReader.MFRC522_Anticoll()
                    # If we have the UID, continue
                    if status == MIFAREReader.MI_OK:
                    # Print UID
                        print ("Card read UID: "+str(uid[0])+","+str(uid[1])+","+str(uid[2])+","+str(uid[3])+','+str(uid[4]))  
                    # This is the default key for authentication
                        key = [0xFF,0xFF,0xFF,0xFF,0xFF,0xFF]        
                    # Select the scanned tag
                        MIFAREReader.MFRC522_SelectTag(uid)        
                    #已授權磁卡UID
                        my_uid = [185,121,204,89,85]  
                        my_uid2 = [66,186,71,30,161]
                    #Check to see if card UID read matches your card UID
                        if uid == my_uid :                #Open the Doggy Door if matching UIDs
                            print("Hello! User1!\n")
                            GPIO.output(LED_R, GPIO.HIGH)
                            GPIO.output(LED_B, GPIO.HIGH)
                            GPIO.output(LED_G, GPIO.HIGH)
                            GPIO.output(LED_G, GPIO.LOW)#USER1 LED亮綠色
                            access = 1#狀態更改為USER1
                            break
                        elif uid == my_uid2 :
                            print("Hello! User2!\n")
                            GPIO.output(LED_R, GPIO.HIGH)
                            GPIO.output(LED_B, GPIO.HIGH)
                            GPIO.output(LED_G, GPIO.HIGH)
                            GPIO.output(LED_B, GPIO.LOW)#USER2 LED亮藍色
                            access = 2#狀態更改為USER1
                            break
                        else:      #Don't open if UIDs don't match
                            print("Access Denied, YOU SHALL NOT PASS!")#磁卡錯誤即觸發警報
                            access = -1
                            break
                    ttimer = ttimer + 1
                    print(ttimer)
                    print('\n')
                    time.sleep(0.01)
                if access == -1 :#入侵者狀態
                    bad = bad + 1
                    print(bad)
                    print('\n')
                    p = '/home/pi/SPI-py/BADGUY.jpg'#照片存在樹莓派的位置 只會有一張 之前的覆蓋
                    d = '/BADGUY/BADGUY%02d.jpg' % bad#照片上傳到DROPBOX的位址 根據bad數值會有不同名稱產生
                    time.sleep(1)#PICAMERA暖機
                    camera.capture(p)
                    with open ( p , "rb") as f :
                        dbx.files_upload(f.read(), d , mute = True , mode = dropbox.files.WriteMode.overwrite)#上傳至DROPBOX
                    client.connect("YOUR HOST ADDRESS OF MQTT BROKER", 1883, 120)
                    payload = ("Warning! BADGUY %02d Invading!" % bad )
                    client.publish( "iot01/TEST" , json.dumps(payload))
                    client.disconnect()
                    publish.single ( topic3, bad, qos = 0, hostname = "YOUR HOST ADDRESS OF MQTT BROKER") #傳送入侵人數至MQTT
                    gtimer = 0
                    while gtimer <= 15 :#LED燈蜂鳴器啟動15秒
                        GPIO.output(LED_R, GPIO.LOW)
                        pwm.start(70)
                        time.sleep(0.5)
                        GPIO.output(LED_R, GPIO.HIGH)
                        pwm.stop()
                        time.sleep(0.5)
                        print("BEEP%d\n"  %gtimer)
                        gtimer = gtimer + 1
                elif access == 1 :#USER1 讀磁卡 上傳目前時間至MQTT
                    print(time.strftime("%H%M%S\n", time.localtime()))
                    payload = ( time.strftime("%H:%M:%S", time.localtime()) )
                    print(payload)
                    print("\n")
                    publish.single(topic1, payload, qos=0, hostname = host)
                    good = 1
                elif access == 2 :#USER2 讀磁卡 上傳目前時間至MQTT
                    payload = ( time.strftime("%H:%M:%S", time.localtime()) )
                    print(payload)
                    print("\n")
                    publish.single( topic2, payload, qos=0, hostname = host)
                    good = 1
            else :
                near_counter = 0
        time.sleep(0.8)
except KeyboardInterrupt:
    print('End System!')
finally:
    GPIO.cleanup()
    pwm.stop()
    client.connect( host, 1883, 120)
    payload = 0
    client.publish( "iot01/BAD", json.dumps(payload))
    client.disconnect()
