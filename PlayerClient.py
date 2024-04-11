import os
import json
from dotenv import load_dotenv

import random
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
    print(msg.topic + " : " + msg.payload.decode())
    players = game_vars['players']
    if msg.topic.endswith('game_state'):
      (_, lobby, player, _) = msg.topic.split('/')
      if player in players.keys():
        players[player]['game_data'] = json.loads(msg.payload)
        if players[player]['type'] == 'user':
          update_position(player, json.loads(msg.payload))
    elif msg.topic.endswith('scores'):
      game_vars['scores'] = json.loads(msg.payload)
    elif msg.topic.endswith('chat'):
      (_, _, team, _) = msg.topic.split('/')
      update_chat(team, json.loads(msg.payload))
      display_chat(team)
    elif msg.topic.endswith('players'):
      game_vars['players'] = json.loads(msg.payload)
    elif msg.topic.endswith('current_player'):
       game_vars['currentPlayer'] = msg.payload.decode()
    elif msg.topic.endswith('teams'):
      game_vars['teams'] = json.loads(msg.payload)
    elif msg.topic.endswith('teams'):
      updates = json.loads(msg.payload)
      for client_id, state in updates.items(): 
        update_client_state(client_id, state)

def sync_current_player(player):
  game_vars['currentPlayer'] = player

def set_current_player(player):
  game_vars['currentPlayer'] = player
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/current_player", player)
    
def set_players():
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/players", game_vars['players'])
  
def sync_players(players : dict):
  pass
  # for player, info in players.items():
  #   if game_vars['players'] in keys():
  
def update_position(player, game_data):
  players = game_vars['players']
  marker = {
    'free'  : '__',
    'walls' : '[]',
    'oob' : 'XX',
    'coin1' : '$1',
    'coin2' : '$2',
    'coin3' : '$3',
    'enemyPositions' : 'Enemy'
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
  game_vars['players'][player]['map'] = game_map 
  game_vars['players'][player]['map_updated'] = True


def show_map(player):
  print(f"\n{player}'s map:")
  for row in game_vars['players'][player]['map']:
      print('\t'.join(row))
      
      
def init_client():
  load_dotenv(dotenv_path='./credentials.env')

  broker_address = os.environ.get('BROKER_ADDRESS')
  broker_port = int(os.environ.get('BROKER_PORT'))
  username = os.environ.get('USER_NAME')
  password = os.environ.get('PASSWORD')
  
  random.seed(time.time_ns())
  client_id = str(random.randint(0, 100000))
  game_vars['client_id'] = client_id

  client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id="", userdata=None, protocol=paho.MQTTv5)
  
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

  lobby_name = game_vars['lobby_name']
  client.subscribe(f"games/{lobby_name}/lobby")
  client.subscribe(f'games/{lobby_name}/+/game_state')
  client.subscribe(f'games/{lobby_name}/scores')
  client.subscribe(f'games/{lobby_name}/current_player')
  client.subscribe(f'games/{lobby_name}/teams')
  client.subscribe(f'games/{lobby_name}/client_states')
  
  game_vars['client'] = client
  
def title_screen():
  update_client_state(game_vars['client_id'], 'title')
  print(f"\n\n------------------------\nWELCOME TO THE GAME\n\nPress enter to start!\n------------------------")
  input()
  
# Sets up a game
def run_lobby():
  update_client_state(game_vars['client_id'], 'lobby')
  while True:
    choice = input(f"Please select one of the following\n[U] Create User\n[B] Create Bot \n[S] Start Game\n")
    if choice == "U":
      create_user()
    elif choice == "B":
      team = input(f"\nWhat team should the bot Player{len(game_vars['players']) + 1} be on?\n")
      create_bot(team)
    elif choice == "S":
      update_client_state(game_vars['client_id'], 'ready')
      print(f'\nWaiting for all lobbies to ready up!')
      while not all_synced('ready'):
        pass
      return

def update_teams():
  for player_name, player_info in game_vars['players'].items():
    team = player_info['team']
    if team not in game_vars['teams'].keys():
      game_vars['teams'][team] = [player_name]
      game_vars['client'].subscribe(f"games/{game_vars['lobby_name']}/{team}/chat")
    elif player_name not in game_vars['teams'][team]:
      game_vars['teams'][team].append(player_name)
  sync_teams()

def sync_teams():
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/teams", json.dumps(game_vars['teams']))
  
def set_order():
  game_vars['player_order'] = []
  for team in game_vars['teams'].values():
    for player_name in team:
      game_vars['player_order'].append(player_name)

  set_current_player(game_vars['player_order'][0])
# Starts a game

def start_game():
  print(f"\n\nGAME STARTED!")
  set_order()
  time.sleep(1) # Wait a second to resolve game start
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/start", "START")
  
def find_next_player():
  pass    
  
def send_chat(player, message):
  player_team = game_vars['players'][player]['team']
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{game_vars['players'][player]['team']}/chat", json.dumps({player_team : f"{player} : {message}"}))
  
  
def update_chat(team, message):
  for team, chat in message.items():
    if team == game_vars['players'][game_vars['currentPlayer']]['team']:
      for player_name in game_vars['teams'][team]:
        game_vars['players'][player_name]['chat'].insert(0, chat)
  
      
def display_chat(team):
  currentPlayer = game_vars['currentPlayer']
  players = game_vars['players']
  if team == players[currentPlayer]['team']:
    while len(players[currentPlayer]['chat']) != 0:
      print(f"\nNEW CHAT from {players[currentPlayer]['chat'].pop()}")
  
    
# Adding new bots
def create_bot(team) -> str:
  players = game_vars['players']
  name = f"Player{len(players) + 1}"
  game_vars['players'][name] = {
    'type' : 'bot',
    'map_updated' : False,
    'team' : team,
    'chat' : list()
  }
  game_vars['client'].publish("new_game", json.dumps({'lobby_name':game_vars['lobby_name'],
                                        'team_name': team,
                                        'player_name' : name}))
  update_teams()
  return name


# Adding new users
def create_user() -> str:
  name = input("Enter your name: ")
  team = input(f"Hi {name}, enter your team's name: ")
  game_vars['players'][name] = {
    'type' : 'user',
    'map_updated' : False,
    'team' : team,
    'chat' : list(),
    'local' : True
    }
  game_vars['client'].publish("new_game", json.dumps({'lobby_name':game_vars['lobby_name'],
                                        'team_name': team,
                                        'player_name' : name}))
  update_teams()
  return name


# Allow a user to make a move
def user_move(name):
  move = None
  players = game_vars['players']
  while not players[name]['map_updated']:
    pass
  show_map(name)
  print(f"\n{name}, what move do you want to make? (UP/DOWN/LEFT/RIGHT)\nOr, enter 'C:' followed by a message to send a message to your team")
  while move not in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
    display_chat(players[name]['team'])
    move = input()
    if move.startswith('C:'):
      send_chat(name, move[2:])
      time.sleep(1)
    elif move not in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
      print(f"Uh-oh! {move} is an invalid move. Please enter a valid one!")
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{name}/move", move)
  players[name]['map_updated'] = False


# Allow a bot to make a move
def bot_move(name):
  move = 'DOWN'
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{name}/move", move)
  game_vars['players'][name]['map_updated'] = False
  
  
def show_scoreboard():
  score_str = f"\nSCOREBOARD:"
  for team, score in game_vars['scores'].items():
    score_str += f"\nTeam {team} : ${score}"
  print(score_str)


game_vars = {
  'players' : {}, 
  'currentPlayer' : None, 
  'lobby_name' : 'TestLobby', 
  'client' : None, 
  'scores' : {},
  'state' : 'setup',
  'player_order' : [],
  'teams' : {},
  'client_id' : None,
  'client_states' : {}
  }


def take_turn():
  player_name = game_vars['currentPlayer']
  time.sleep(1)
  show_scoreboard()
  print(player_name)
  
  print()
  print("-----------------------------------")
  print(f"{player_name}'s turn!")
  if player_name in game_vars['players'].keys():
    current_player = game_vars['players'][player_name]
    print(current_player)
    if current_player['type'] == 'bot':
      bot_move(player_name)
    else:
      user_move(player_name)
    set_current_player(find_next_player())
  else:
    print(f"Waiting for {player_name} to take their turn!")
    while(game_vars['currentPlayer'] == player_name):
      pass
    # wait for other user to take their turn
  print(f"{player_name}'s turn is over!")
  

def find_next_player() -> str:
  for i in range(0, len(game_vars['player_order'])):
    if game_vars['player_order'][i] == game_vars['currentPlayer']:
      next_player = game_vars['player_order'][(i + 1) % len(game_vars['player_order'])]
      return next_player
    

def update_client_state(client_id, state):
  game_vars['client_states'][client_id] = state
  if client_id == game_vars['client_id']:
    game_vars['client'].publish(f"games/{game_vars['lobby_name']}/client_states", json.dumps({client_id : state}))

def all_synced(state) -> bool:
  synced = all([client_state == state for client_state in game_vars['client_states'].values()])
  return synced

if __name__ == '__main__':
  init_client()
  game_vars['client'].loop_start()
  title_screen()
  run_lobby()    
  while not all_synced('ready'):
    pass
  start_game()
  game_over = False
  while not game_over:
    take_turn()
  game_vars['client'].loop_end()
    
            


