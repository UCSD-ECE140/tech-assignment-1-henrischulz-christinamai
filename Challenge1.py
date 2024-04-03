import paho.mqtt.client as paho
from paho import mqtt
from time import time
from random import randint
import threading

def on_connect(client, userdata, flags, rc, properties=None):
    """
        Prints the result of the connection with a reasoncode to stdout ( used as callback for connect )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param flags: these are response flags sent by the broker
        :param rc: stands for reasonCode, which is a code for the connection result
        :param properties: can be used in MQTTv5, but is optional
    """
    print("CONNACK received with code %s." % rc)


def on_publish(client, userdata, mid, properties=None):
    """
        Prints mid to stdout to reassure a successful publish ( used as callback for publish )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param properties: can be used in MQTTv5, but is optional
    """
    print("mid: " + str(mid))


def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    """
        Prints a reassurance for successfully subscribing
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param granted_qos: this is the qos that you declare when subscribing, use the same one for publishing
        :param properties: can be used in MQTTv5, but is optional
    """
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


def on_message(client, userdata, msg):
    """
        Prints a mqtt message to stdout ( used as callback for subscribe )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param msg: the message with topic and payload
    """
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    

def create_client(username : str, password: str, url : str = "e324eb81ab454f59936d87b3044022fc.s1.eu.hivemq.cloud", id : str = "", port : int = 8883) -> paho.Client:
  """
    Returns a newly initialized and connected client
  """
  client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id=id, userdata=None, protocol=paho.MQTTv5)
  client.on_connect = on_connect
  client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
  client.username_pw_set(username, password)
  client.connect(url, port)

  client.on_subscribe = on_subscribe
  client.on_message = on_message
  client.on_publish = on_publish
  return client

sender1 = create_client("ece140b-ta1", "ECE140bta1", id="sender-1")
sender2 = create_client("ece140b-ta1", "ECE140bta1", id = "sender-2")

receiver = create_client("ece140b-ta1", "ECE140bta1", id="receiver")
receiver.subscribe("topic-1")
receiver.subscribe("topic-2")

receiver_loop = threading.Thread(target= receiver.loop_forever, daemon=True)
receiver_loop.start()

last_post = time()
post_period = 3

try:
  while(True):
      if time() >= last_post + post_period:
        last_post = time()
        sender1.publish("topic-1", payload=randint(0, 100))
        sender2.publish("topic-2", payload=randint(0, 100))
except KeyboardInterrupt:
  print("Shutting down clients")