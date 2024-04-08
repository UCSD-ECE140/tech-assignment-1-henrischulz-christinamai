import os
import json
from dotenv import load_dotenv

import paho.mqtt.client as paho
from paho import mqtt
import time


# setting callbacks for different events to see if it works, print the message etc.
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


# with this callback you can see if your publish was successful
def on_publish(client, userdata, mid, properties=None):
    """
        Prints mid to stdout to reassure a successful publish ( used as callback for publish )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param properties: can be used in MQTTv5, but is optional
    """
    pass
    # print("mid: " + str(mid))


# print which topic was subscribed to
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    """
        Prints a reassurance for successfully subscribing
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param granted_qos: this is the qos that you declare when subscribing, use the same one for publishing
        :param properties: can be used in MQTTv5, but is optional
    """
    pass
    # print("Subscribed: " + str(mid) + " " + str(granted_qos))


# print message, useful for checking if it was successful
def on_message(client, userdata, msg):
    """
        Prints a mqtt message to stdout ( used as callback for subscribe )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param msg: the message with topic and payload
    """
    # print("message: " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    if msg.topic.endswith('game_state'):
      (_, lobby, player, _) = msg.topic.split('/')
      if players[player]['type'] == 'user':
        update_position(player, json.loads(msg.payload))

def update_position(player, game_data):
  
  marker = {
    'free'  : '__',
    'walls' : 'XX',
    'oob' : 'XX',
    'coin1' : '$1',
    'coin2' : '$2',
    'coin3' : '$3',
  }
  
  top_left =  [i-2 for i in game_data['currentPosition']]
  
  game_map = [[None for i in range(0,5)] for i in range(0,5)]
  for i in range(0,5):
    for j in range(0,5):
      if top_left[0] + i in range(0,10) and top_left[1] + j in range(0,10):
        game_map[i][j] = marker['free']
      else:
        game_map[i][j] = marker['oob']
  
  def update_map(loc : list[2], entity : str):
    game_map[loc[0] - top_left[0]][loc[1] - top_left[1]] = marker[entity] if entity in marker.keys() else entity.capitalize()

  for entity, locs in dict.items(game_data):
    if entity == 'teammateNames':
      continue
    elif entity == 'teammatePositions':
      for i in range(0, len(locs)):
        update_map(locs[i], game_data['teammateNames'][i])
    elif entity == 'currentPosition':
      update_map(locs, player)
    else:  
      for loc in locs:
        update_map(loc, entity)
  players[player]['map'] = game_map 
  players[player]['map_updated'] = True

players = {}

def show_map(player):
  print(f"\n{player}'s map:")
  for row in players[player]['map']:
      print('\t'.join(row))

if __name__ == '__main__':
    load_dotenv(dotenv_path='./credentials.env')
    
    broker_address = os.environ.get('BROKER_ADDRESS')
    broker_port = int(os.environ.get('BROKER_PORT'))
    username = os.environ.get('USER_NAME')
    password = os.environ.get('PASSWORD')

    client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id="Player1", userdata=None, protocol=paho.MQTTv5)
    
    # enable TLS for secure connection
    client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    # set username and password
    client.username_pw_set(username, password)
    # connect to HiveMQ Cloud on port 8883 (default for MQTT)
    client.connect(broker_address, broker_port)

    # setting callbacks, use separate functions like above for better visibility
    client.on_subscribe = on_subscribe # Can comment out to not print when subscribing to new topics
    client.on_message = on_message
    client.on_publish = on_publish # Can comment out to not print when publishing to topics

    lobby_name = "TestLobby"
    player_2 = "Player2"
    player_3 = "Player3"

    client.subscribe(f"games/{lobby_name}/lobby")
    client.subscribe(f'games/{lobby_name}/+/game_state')
    client.subscribe(f'games/{lobby_name}/scores')
    
    # Startup display
    print(f"\n\n------------------------\nWELCOME TO THE GAME\n\nPress enter to start!\n------------------------")
    input()
    
    # Adding new bots
    def create_bot(team) -> str:
      name = f"Player{len(players) + 1}"
      players[name] = {
        'type' : 'bot',
        'map_updated' : False,
        'team' : team
      }
      client.publish("new_game", json.dumps({'lobby_name':lobby_name,
                                            'team_name': team,
                                            'player_name' : name}))
      return name
        
    # Adding new users
    def create_user() -> str:
      name = input("Enter your name: ")
      team = input(f"Hi {name}, enter your team's name: ")
      players[name] = {
        'type' : 'user',
        'map_updated' : False,
        'team' : team
        }
      client.publish("new_game", json.dumps({'lobby_name':lobby_name,
                                            'team_name': team,
                                            'player_name' : name}))
      return name
    
    # Allow a user to make a move
    def user_move(name):
      move = None
      while not players[name]['map_updated']:
        pass
      show_map(name)
      while move not in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
        move = input(f"\n{name}, what move do you want to make? (UP/DOWN/LEFT/RIGHT)\n")
        if move not in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
          print(f"Uh-oh! {move} is an invalid move. Please enter a valid one!")
      client.publish(f"games/{lobby_name}/{name}/move", move)
      players[name]['map_updated'] = False
      
    # Allow a bot to make a move
    def bot_move(name):
      move = 'DOWN'
      client.publish(f"games/{lobby_name}/{name}/move", move)
      players[name]['map_updated'] = False
    
    # Creates two user-controlled players
    create_user()
    create_user()

    time.sleep(1) # Wait a second to resolve game start
    client.publish(f"games/{lobby_name}/start", "START")
      
    game_over = False
    client.loop_start()
    
    while not game_over:
      for player, info in dict.items(players):
        print(f"\n{player}'s turn!")
        if info['type'] == 'bot':
          bot_move(player)
        else:
          user_move(player)
        print(f"{player}'s turn is over")

    client.loop_stop()
      


