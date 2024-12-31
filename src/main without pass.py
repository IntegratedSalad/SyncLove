import machine
import esp
import network
import ssl
import ubinascii
import time
from umqtt import simple
import gc

# INPUT
# D1 (SCL) -> GPIO5
# Press to initiate
pin_input = machine.Pin(5, machine.Pin.IN, machine.Pin.PULL_UP)

# OUTPUT LED DEBUG
# D2 (SDA) -> GPIO4
pin_output = machine.Pin(4, machine.Pin.OUT, value=0)

# OUTPUT LED SETUP
# D6 (MISO) -> GPIO12
pin_output_setup = machine.Pin(12, machine.Pin.OUT, value=0)

gc.collect()
# Wi-Fi configuration
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect() # TODO: store this on device

while wlan.isconnected() == False:
  pass

# MQTT client setup
server = b"a2c31446a2f648959e80ad9cb225fb2f.s1.eu.hivemq.cloud"
port = 8883 # this port uses secure MQTT with SSL/TLS
mqtt_user = "adam1"
mqtt_pass = b'Absolutneguwno666!'
topic_pub = b'hello'
topic = "button_pressed"
topic_initiate = "initiate"
topic_respond = "respond"
topic_abandoned = "abandon"
last_message = 0
message_interval = 5
counter = 0

client_id = ubinascii.hexlify(machine.unique_id())
client = None

isResponder = False
theOtherResponded = False
isSynced = False

button_last_trigger = 0

timer_abandoned = machine.Timer(2137)
WAIT_FOR_ABANDONED_MS = 10000

pwm4 = None
pwm12 = None

def blinkLED_PWM():
    global pwm4
    pwm4 = machine.PWM(machine.Pin(4))
    pwm4.freq(2)
    pwm4.duty(50)
    
def blinkLED_SETUP_PWM():
    global pwm12
    pwm12 = machine.PWM(machine.Pin(12))
    pwm12.freq(20)
    pwm12.duty(50)
    
def Callback_send_restore(timer_obj):
    # Show animation for 10 seconds, show closing animation and restore.
    pass

def Callback_send_abandoned(timer_obj):
    """
    Send message on "abandoned" topic.
    Upon receiving, both of the devices reset data and behavior.
    """
    if not theOtherResponded:
        abandoned_message = b"Abandoned:%s" % client_id
        client.publish(topic_abandoned, abandoned_message)

def Callback_pin_Input(pin):
    global last_trigger
    if isSynced: return
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, button_last_trigger) > 50:  # 50 ms
        last_trigger = current_time
        # Real change is confirmed; read pin
        if pin.value() == 0:
            print("Button pressed")
            if not isResponder:
                initiate_msg = b"Initiating from:%s" % client_id # do not include the whitespace
                client.publish(topic_initiate, initiate_msg)
            else:
                respond_msg = b"Responding from:%s" % client_id # do not include the whitespace
                client.publish(topic_respond, respond_msg)
            
def Callback_pin_Output():
    pass

def Callback_received_msg(topic, msg):
    global theOtherResponded, pwm4, pin_output, isResponder, isSynced
    """
    Callback for received message.
    The device should act only if it received a message, not on any physical interaction.
    This is done so that if the broker stops being active, nothing will work.
    """
    topic_str = topic.decode("utf-8")
    print(f"Received {msg} on {topic}")
    decoded_msg = msg.decode("utf-8")
    isEcho = decoded_msg.split(":")[-1] == client_id.decode("utf-8")
    print("Decoded msg:")
    print(decoded_msg.split(":")[0])
    print("Client id:")
    print(decoded_msg.split(":")[-1])
    if topic_str == topic_initiate:
        # Is this message broadcasted to every device (even the sending one)? Yes
        if not isEcho: # We've received message from the other device
            print("I have to respond...")
            isResponder = True
        else:
            print("I've Initiated")
            print("I'll wait 30s...")
            timer_abandoned.init(period=WAIT_FOR_ABANDONED_MS, mode=machine.Timer.ONE_SHOT, callback=Callback_send_abandoned)
        pin_output.on()
    elif topic_str == topic_respond:
        if isEcho and isResponder:
            print("I responded")
            isResponder = False
            isSynced = True
        if not isEcho:
            print("The responder has responded")
            theOtherResponded = True
            isSynced = True
        blinkLED_PWM()
    elif topic_str == topic_abandoned:
        print("I've received an abandoned message...")
        isResponder=False
        pin_output.off()
        if pwm4 is not None:
            pwm4.deinit()
        isSynced = False

def connectMQTT():
    global pwm12
    # TODO: Indicate setting up by flashing yellow led very fast
    blinkLED_SETUP_PWM()
    client = simple.MQTTClient(client_id=ubinascii.hexlify(machine.unique_id()),server=server,port=port,user=mqtt_user,password=mqtt_pass, keepalive=7200, ssl=ssl)
    client.set_callback(Callback_received_msg)
    client.connect()
    print('Connected to MQTT Broker "%s"' % (server))
    client.subscribe(topic_initiate)
    client.subscribe(topic_respond)
    client.subscribe(topic_abandoned)
    print('Connected to %s MQTT broker, subscribed to topics: %s, %s' % (server, topic_initiate, topic_respond))
    pwm12.deinit()
    return client

def restart_and_reconnect():
    print('Failed to connect to MQTT broker. Reconnecting...')
    time.sleep(10)
    machine.reset()

# Setup before main loop
pin_input.irq(trigger=machine.Pin.IRQ_FALLING, handler=Callback_pin_Input)

client = connectMQTT()
print("client ID: %s" % client_id)

while True:
  try:
    client.check_msg()
    #if (time.time() - last_message) > message_interval:
      #msg = b'Hello #%d' % counter
      #client.publish(topic_pub, msg)
      #last_message = time.time()
      #counter += 1
  except OSError as e:
      # TODO: Add another LED indicating restarting
    restart_and_reconnect()


