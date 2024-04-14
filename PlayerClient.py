import os
import json
from dotenv import load_dotenv

import random
import paho.mqtt.client as paho
from paho import mqtt
import time


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
  'client_states' : {},
  'game_over' : False, 
  'active_room' : None
  }

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
    # print(msg.topic + " : " + msg.payload.decode())
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
      player = msg.payload.decode()
      if player != game_vars['currentPlayer']:
        print(f"It is now {player}'s turn!\nIf you are {player}, enter '?' to take your turn!")
        game_vars['currentPlayer'] = player
    elif msg.topic.endswith('teams'):
      game_vars['teams'] = json.loads(msg.payload)
      display_lobby()
    elif msg.topic.endswith('client_states'):
      updates = json.loads(msg.payload)
      for client_id, state in updates.items(): 
        update_client_state(client_id, state)
    elif msg.payload.decode().startswith('Game Over'):
      game_vars['game_over'] = True

def display_lobby():
  print(f"\n----TEAMS----")
  for team, names in game_vars['teams'].items():
    print(f"Team {team}: {", ".join(names)}")
  print()
    
def set_players():
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/players", game_vars['players'], qos=2)
  
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
    display_lobby()
    choice = input(f"Please select one of the following\n[U] Create User\n[B] Create Bot \n[S] Start Game\n")
    if choice == "U":
      create_user()
    elif choice == "B":
      team = input(f"\nWhat team should the bot Player{sum([len(team) for team in game_vars['teams'].values()]) + 1} be on?\n")
      create_bot(team)
    elif choice == "S":
      update_client_state(game_vars['client_id'], 'ready')
      print(f'\nWaiting for all lobbies to ready up!')
      while not all_synced('ready'):
        time.sleep(1)
        print(game_vars['client_states'])
      return

def update_teams():
  for player_name, player_info in game_vars['players'].items():
    team = player_info['team']
    if team not in game_vars['teams'].keys():
      game_vars['teams'][team] = [player_name]
    elif player_name not in game_vars['teams'][team]:
      game_vars['teams'][team].append(player_name)
  sync_teams()

def sync_teams():
  for team in game_vars['teams'].keys():
    game_vars['client'].subscribe(f"games/{game_vars['lobby_name']}/{team}/chat")
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/teams", json.dumps(game_vars['teams']), qos=2)
  
def set_order():
  game_vars['player_order'] = []
  for team in game_vars['teams'].values():
    for player_name in team:
      game_vars['player_order'].append(player_name)

  set_current_player(game_vars['player_order'][0])

def set_current_player(player):
  game_vars['currentPlayer'] = player
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/current_player", player, qos=2)

def start_game():
  print(f"\n\nGAME STARTED!")
  set_order()
  time.sleep(1) # Wait a second to resolve game start
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/start", "START", qos=2) 
  
def send_chat(player, message):
  player_team = game_vars['players'][player]['team']
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{game_vars['players'][player]['team']}/chat", json.dumps({player_team : f"{player} : {message}"}),qos=2)

def send_anonymous_chat(team, message):
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{team}/chat", json.dumps({team : f"Anonymous : {message}"}),qos=2)

def update_chat(team, message):
  for team, chat in message.items():
    for player_name in game_vars['players'].keys():
      if game_vars['players'][player_name]['team'] == team:
        game_vars['players'][player_name]['chat'].insert(0, chat)
            
      
def display_chat(team):
  currentPlayer = game_vars['currentPlayer']
  players = game_vars['players']
  
  if (currentPlayer in players.keys() and team == players[currentPlayer]['team']):
    while len(players[currentPlayer]['chat']) != 0:
      print(f"\nNEW CHAT from {players[currentPlayer]['chat'].pop()}")  
  elif game_vars['active_room'] == team:
    messages = []
    for player_name in game_vars['teams'][team]:
      if player_name in players.keys():
        message = ""
        try:
          while True:
            message = players[player_name]['chat'].pop()
            if message not in messages:
              messages.append(message)
        except IndexError:
          pass
    if messages == []:
      print(f"\nThere are no players on this computer on that team.\nStop trying to cheat!")
    else:
      for message in messages:
        print(f"\nNEW CHAT from {message}")


# Adding new users
def create_user() -> str:
  name = input("Enter your name: ")
  
  if any([name in names for names in game_vars['teams'].values()]):
    print("Sorry! That name is already taken")
    return None
  team = input(f"Hi {name}, enter your team's name: ")
  game_vars['players'][name] = {
    'type' : 'user',
    'map_updated' : False,
    'team' : team,
    'chat' : list(),
    }
  game_vars['client'].publish("new_game", json.dumps({'lobby_name':game_vars['lobby_name'],
                                        'team_name': team,
                                        'player_name' : name}), qos=2)
  update_teams()
  return name

# Adding new bots
def create_bot(team) -> str:
  name = f"Player{sum([len(team) for team in game_vars['teams'].values()]) + 1}"
  game_vars['players'][name] = {
    'type' : 'bot',
    'map_updated' : False,
    'team' : team,
    'chat' : list()
  }
  game_vars['client'].publish("new_game", json.dumps({'lobby_name':game_vars['lobby_name'],
                                        'team_name': team,
                                        'player_name' : name}), qos=2)
  update_teams()
  return name


def take_turn():
  player_name = game_vars['currentPlayer']
  time.sleep(1)
  show_scoreboard()
  
  print()
  print("-----------------------------------")
  print(f"{player_name}'s turn!")
  if player_name in game_vars['players'].keys():
    current_player = game_vars['players'][player_name]
    if current_player['type'] == 'bot':
      bot_move(player_name)
    else:
      user_move(player_name)
    set_current_player(find_next_player())
  else:
    print(f"Waiting for {player_name} to take their turn!")
    while(game_vars['currentPlayer'] == player_name):
      enter_chat_room()
    # wait for other user to take their turn
  # print(f"{player_name}'s turn is over!")

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
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{name}/move", move, qos=2)
  players[name]['map_updated'] = False


# Allow a bot to make a move
def bot_move(name):
  move = 'DOWN'
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{name}/move", move, qos=2)
  game_vars['players'][name]['map_updated'] = False
  
  
def show_scoreboard():
  score_str = f"\nSCOREBOARD:"
  for team, score in game_vars['scores'].items():
    score_str += f"\nTeam {team} : ${score}"
  print(score_str)
  

def find_next_player() -> str:
  for i in range(0, len(game_vars['player_order'])):
    if game_vars['player_order'][i] == game_vars['currentPlayer']:
      next_player = game_vars['player_order'][(i + 1) % len(game_vars['player_order'])]
      return next_player
    

def update_client_state(client_id, state):
  state_change = game_vars['client_states'][client_id] != state if client_id in game_vars['client_states'].keys() else True
  game_vars['client_states'][client_id] = state
  if state_change:
    for client, state in game_vars['client_states'].items():
      game_vars['client'].publish(f"games/{game_vars['lobby_name']}/client_states", json.dumps({client : state}), qos=2)


def all_synced(state) -> bool:
  synced = all([client_state == state for client_state in game_vars['client_states'].values()])
  return synced

def end_game():
  update_client_state(game_vars['client_id'], 'game_over')
  print(f"\n------------------\n     GAME OVER")
  result = {k : v for k, v in sorted(game_vars['scores'].items(), key= lambda x: x[1])}
  rank = 1
  for team, score in result.items():
    print(f"{rank}. {team} : {score}")
      


def enter_chat_room():
  choice = None
  while choice != '?':
    print(f"Select one of the following: \nEnter C:[Team Name] to enter a chat room for that team\nEnter [Team Name]:[Message] to send a chat to the designated team.")
    choice = input()
    if choice.startswith("C:"):
      team = choice[2:]
      if team in game_vars['teams'].keys():
        game_vars['active_room'] = team
        print(f"Chat room open for Team {team}")
        display_chat(game_vars['active_room'])
      else:
        print(f"{team} is not a valid team!")
    elif choice != '?':
      team = choice[:choice.find(":")]
      message = choice[choice.find(":")+1:]
      send_anonymous_chat(team, message)
  if(game_vars['active_room'] != None):
    game_vars['active_room'] = None
    print("Chat rooms closed")
    
  
if __name__ == '__main__':
  init_client()
  game_vars['client'].loop_start()
  title_screen()
  run_lobby()    
  start_game()
  while not game_vars['game_over']:
    take_turn()
  end_game()
  game_vars['client'].loop_end()
    
            


