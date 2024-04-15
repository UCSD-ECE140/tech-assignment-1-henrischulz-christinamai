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
      players[player]['game_data'] = json.loads(msg.payload)
      if players[player]['type'] == 'user' or players[player]['type'] == 'bot':
        #print("player: " + player)
        update_position(player, json.loads(msg.payload))
        
    if msg.topic.endswith('lobby'):
      (_, lobby, _) = msg.topic.split('/')
      if(check_end_game(str(msg.payload.decode()))):
          end_game()


def update_position(player, game_data):
  marker = {
    'free'  : '__',
    'walls' : 'XX',
    'oob' : 'XX',
    'coin1' : '$1',
    'coin2' : '$2',
    'coin3' : '$3',
  }
  #print(str(player) + "|" + str(game_data))
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

def show_map(player):
  print(f"\n{player}'s map:")
  for row in players[player]['map']:
      print('\t'.join(row))
      
def init_client(client):
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

  client.subscribe(f"games/{lobby_name}/lobby")
  client.subscribe(f'games/{lobby_name}/+/game_state')
  client.subscribe(f'games/{lobby_name}/scores')
  
  return client
  

# Sets up a game
def setup_game():
  print(f"\n\n------------------------\nWELCOME TO THE GAME\n\nPress enter to start!\n------------------------")
  input()
  
  user_count = None
  while type(user_count) != int:
    user_count = input(f"\nHow many users will be playing in this game? :")
    if not user_count.isdigit():
      print(f"{user_count} is an invalid number!")
    else:
      user_count = int(user_count)
  
  bot_count = None
  while type(bot_count) != int:
    bot_count = input(f"\nHow many bots will be playing in this game? :")
    if not bot_count.isdigit():
      print(f"{bot_count} is an invalid number!")
    else:
      bot_count = int(bot_count)
  
  for i in range(0, user_count):
    create_user()
  
  for i in range(0, bot_count):
    team = input(f"\nWhat team should bot #{i+1} be on? :")
    mode = input(f"\nWhat mode should bot #{i+1} be? n/a or algorithm :")
    create_bot(team,mode)


# Starts a game
def start_game():
  print(f"\n\nGAME STARTED!")
  time.sleep(1) # Wait a second to resolve game start
  client.publish(f"games/{lobby_name}/start", "START")
  
      
# Adding new bots
def create_bot(team, mode) -> str:
  name = f"Player{len(players) + 1}"
  players[name] = {
    'type' : 'bot',
    'map_updated' : False,
    'team' : team,
    'mode' : mode, #n/a or algorithm
    'scale_up': True,
    'scale_right': True,
    'default_move': 'UP'
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
    'team' : team,
    'mode' : 'n/a'
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
  #print("bot: " + name)
  match players[name]["mode"]:
    case 'algorithm':
      move = 'DOWN'
      
      while not players[name]['map_updated']:
        pass
      
      block = ["XX","Enemypositions","Player"]
        
      top = players[name]["map"][1][2]
      bottom = players[name]["map"][3][2]
      right = players[name]["map"][2][3]
      left = players[name]["map"][2][1]
      

      if((top in block and bottom in block) or (top in block and right in block and left in block) or (bottom in block and right in block and left in block) or (top in block and left in block)):
        players[name]["scale_up"] = not players[name]["scale_up"]
      if((top in block and bottom in block and left in block) or (top in block and bottom in block and right in block)):
        players[name]["scale_right"] = not players[name]["scale_right"]
      
      if( '$' in top):
        move = 'UP'
      elif('$' in left):
        move = 'LEFT'
      elif('$' in right):
        move = 'RIGHT'
      elif('$' in bottom):
        move = "DOWN"
      elif(top not in block and players[name]["scale_up"]):
        move = "UP"
      elif(bottom not in block and not players[name]["scale_up"]):
        move = "DOWN"
      elif(right not in block and players[name]["scale_right"]):
        move = "RIGHT"
      elif(left not in block):
        move = "LEFT"
      
      show_map(name)
      print(name + " | " + move + " | " + str(players[name]["scale_up"]) + " | " + str(players[name]["scale_right"]))
      input()
      client.publish(f"games/{lobby_name}/{name}/move", move)
      players[name]['map_updated'] = False
    case _:
      move = 'DOWN'
      client.publish(f"games/{lobby_name}/{name}/move", move)
      players[name]['map_updated'] = False
  
# Check if all coins are collected for end game condition
def check_end_game(lobby_subscription_message):
  if(lobby_subscription_message == 'Game Over: All coins have been collected'):
    game_over = True
    print("game_over");
    return game_over
    
# End Lobby Game for Players
def end_game():
  client.loop_stop()
          
players = {}
lobby_name = 'TestLobby'
client: paho.Client = None

if __name__ == '__main__':
  client = init_client(client)   
  setup_game()
  start_game()
    
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

  
  
      


