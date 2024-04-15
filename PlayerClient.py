import os
import json
from dotenv import load_dotenv

import random
import paho.mqtt.client as paho
from paho import mqtt
import time

# Dictionary unique to each client used to track game variables
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
    
    players = game_vars['players']
    
    if msg.topic.endswith('game_state'): # update player info
      (_, lobby, player, _) = msg.topic.split('/')
      if player in players.keys():
        players[player]['game_data'] = json.loads(msg.payload)
        update_player_pos(player, json.loads(msg.payload))
    
    elif msg.topic.endswith('scores'): # updated local scores
      game_vars['scores'] = json.loads(msg.payload)
    
    elif msg.topic.endswith('chat'): # updates chat
      (_, _, team, _) = msg.topic.split('/')
      update_chat(team, json.loads(msg.payload))
      display_chat(team)
      
    elif msg.topic.endswith('players'): # updates dict of players 
      game_vars['players'] = json.loads(msg.payload)
      
    elif msg.topic.endswith('current_player'): # updates the currently set player
      player = msg.payload.decode()
      if player != game_vars['currentPlayer']:
        print(f"It is now {player}'s turn!\nIf you are {player}, enter '?' to take your turn!")
        game_vars['currentPlayer'] = player
        
    elif msg.topic.endswith('teams'): # updates the local dict of teams
      game_vars['teams'] = json.loads(msg.payload)
      display_teams()
      
    elif msg.topic.endswith('client_states'): # updates local dictonary of client states
      updates = json.loads(msg.payload)
      for client_id, state in updates.items(): 
        update_client_state(client_id, state)
        
    elif msg.payload.decode().startswith('Game Over'): # updates whether game is over
      game_vars['game_over'] = True

def display_teams():
  """
  Displays the teams and their respective players
  """
  print(f"\n----TEAMS----")
  for team, names in game_vars['teams'].items():
    print(f"Team {team}: {", ".join(names)}")
  print()
    
def update_player_pos(player, game_data):
  marker = { # used to map items in game data to visual represenations
    'free'  : '__',
    'walls' : '[]',
    'oob' : 'XX',
    'coin1' : '$1',
    'coin2' : '$2',
    'coin3' : '$3',
    'enemyPositions' : 'Enemy'
  }
  #print(str(player) + "|" + str(game_data))
  top_left =  [i-2 for i in game_data['currentPosition']]
  
  game_map = [[None for i in range(0,5)] for i in range(0,5)] # Builds a 5x5 2-D list representing game map
  for i in range(0,5):
    for j in range(0,5):
      if top_left[0] + i in range(0,10) and top_left[1] + j in range(0,10):
        game_map[i][j] = marker['free']
      else:
        game_map[i][j] = marker['oob']
  
  def update_map(loc : list[2], entity : str):
    """
    Updates coordinate loc to match its corresponding graphic in marker
    If no graphic is found, sets the graphic to be the capitalized entity
    """
    game_map[loc[0] - top_left[0]][loc[1] - top_left[1]] = marker[entity] if entity in marker.keys() else entity.capitalize()

  for entity, locs in dict.items(game_data): # handles drawing teammates and the active player's current position on the map
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
  """
  Prints out the map for a given player
  """
  print(f"\n{player}'s map:")
  for row in game_vars['players'][player]['map']:
      print('\t'.join(row))
      
      
def init_client():
  """
  Initiliazes MQTT client and updates game_vars['client'] to contain the MQTT client
  """
  
  load_dotenv(dotenv_path='./credentials.env')

  broker_address = os.environ.get('BROKER_ADDRESS')
  broker_port = int(os.environ.get('BROKER_PORT'))
  username = os.environ.get('USER_NAME')
  password = os.environ.get('PASSWORD')
  
  # Generates random id for each client
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
  client.on_subscribe = on_subscribe
  client.on_message = on_message
  client.on_publish = on_publish
  client.enable_logger()

  # Subscribes to all default topics regarding game info
  lobby_name = game_vars['lobby_name']
  client.subscribe(f"games/{lobby_name}/lobby")
  client.subscribe(f'games/{lobby_name}/+/game_state')
  client.subscribe(f'games/{lobby_name}/scores')
  client.subscribe(f'games/{lobby_name}/current_player')
  client.subscribe(f'games/{lobby_name}/teams')
  client.subscribe(f'games/{lobby_name}/client_states')
  
  game_vars['client'] = client # Makes client accessible via game_vars['client']
  
  time.sleep(2)
  
def title_screen():
  """
  Displays a title screen then waits until user presses enter to continue
  """
  
  update_client_state(game_vars['client_id'], 'title')
  print(f"\n\n------------------------\nWELCOME TO THE GAME\n\nPress enter to start!\n------------------------")
  input()
  
# Sets up a game
def matchmaking():
  """
  Carries out matchmaking for a lobby by allowing users to create new bots and user-controlled agents
  Waits until all clients in the lobby have readied up to exit matchmaking
  """
  
  print(f"\nYou are client #{game_vars['client_id']}")
  
  while True:
    update_client_state(game_vars['client_id'], 'matchmaking')

    display_teams()
    
    choice = input(f"Please select one of the following\n[U] Create User\n[B] Create Bot \n[S] Start Game\n")
    
    if choice == "U":
      create_user()
      
    elif choice == "B":
      team = input(f"\nWhat team should the bot Player{sum([len(team) for team in game_vars['teams'].values()]) + 1} be on?\n")
      mode = input(f"\nWhat mode should this bot be? n/a or algorithm :")
      create_bot(team, mode)
      
    elif choice == "S":
      update_client_state(game_vars['client_id'], 'ready')
      print(f'\nWaiting for all clients to ready up!')
      
      while not all_synced('ready'): # Waits for all clients before exiting matchmaking
        update_client_state(game_vars['client_id'], 'ready')
        time.sleep(5)
        print(game_vars['client_states'])
      return

def update_teams():
  """
  Updates the list of current teams and players
  Notifies all other clients of updated teams and players
  """
  
  # Updates game_vars['team'] with dicts in the form of {team : [player1, player2, ...]}
  for player_name, player_info in game_vars['players'].items():
    team = player_info['team']
    
    if team not in game_vars['teams'].keys(): # creates new team and subscribes to schannel for its chat
      game_vars['teams'][team] = [player_name]
      
    elif player_name not in game_vars['teams'][team]:
      game_vars['teams'][team].append(player_name)
    topic = f"games/{game_vars['lobby_name']}/{team}/chat"
    game_vars['client'].subscribe(topic)
    
  # Syncs teams across all player clients
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/teams", json.dumps(game_vars['teams']))
  
  
def set_order():
  """
  Derives order of players from game_vars['teams'] and stores result in list at game_vars['player_order']
  Sets the current player to be the first player in that order
  """
  game_vars['player_order'] = []
  for team in game_vars['teams'].values():
    for player_name in team:
      game_vars['player_order'].append(player_name)

  set_current_player(game_vars['player_order'][0])

def set_current_player(player):
  """
  Sets the current player (the player who's turn it is)
  Notifies all clients in the lobby
  """
  game_vars['currentPlayer'] = player
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/current_player", player)

def start_game():
  """
  Sets player order, then starts a game
  """
  set_order()
  time.sleep(1) # Wait a second to resolve game start
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/start", "START")
  print(f"\n\nGAME STARTED!")

  
def send_chat(player, message):
  """
  Sends a specified message to all members on the same team as the gven player
  """
  player_team = game_vars['players'][player]['team']
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{game_vars['players'][player]['team']}/chat", json.dumps({player_team : f"{player} : {message}"}))

def send_anonymous_chat(team, message):
  """
  Send the specified mesage from an anonymous player to all members on the specified team
  """
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{team}/chat", json.dumps({team : f"Anonymous : {message}"}))

def update_chat(team, message):
  """
  Updates the chat list for each player in a specified team to contain the specified message
  """
  for team, chat in message.items():
    for player_name in game_vars['players'].keys():
      if game_vars['players'][player_name]['team'] == team:
        game_vars['players'][player_name]['chat'].insert(0, chat)
            
      
def display_chat(team):
  """
  Determines whether chat for a specified team should be displayed, then displays if needed
  """
  
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
      pass
    else:  
      for message in messages:
        print(f"\nNEW CHAT from {message}")



def create_user() -> str:
  """
  Creates a new user-controlled player in the game
  Intended to be used during matchmaking only
  Returns the name of the user
  """
  
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
                                        'player_name' : name}))
  print("player published")
  update_teams()
  return name


def create_bot(team, mode) -> str:
  """
  Creates a new bot to be added as a player to the game
  Intended to be used during matchmaking only
  Returns the name of the new bot
  """
  players = game_vars['players']
  client = game_vars['client']
  lobby_name = game_vars['lobby_name']
  
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
  update_teams()
  
  return name


def run_game():
  """
  Runs the main game loop, allowing players and bots to take their turns
  """
  player_name = game_vars['currentPlayer']
  time.sleep(1)
  show_scoreboard()
  
  print()
  print("-----------------------------------")
  print(f"{player_name}'s turn!")
  
  if player_name in game_vars['players'].keys(): # if player was set up on this client...
    current_player = game_vars['players'][player_name]
    if current_player['type'] == 'bot':
      bot_move(player_name) # make automatic move if player is a bot
    else:
      user_move(player_name) # prompt user for their own move if player is user-controlled
    set_current_player(find_next_player()) # move on to the next player
  
  else: # if player resides on another client, wait until they have taken their turn
    print(f"Waiting for {player_name} to take their turn!")
    while(game_vars['currentPlayer'] == player_name):
      wait_for_turn()

# Allow a user to make a move
def user_move(name):
  """
  Prompts a user to make their move or send a chat when it is their turn
  Only returns once a user has successfully made their move
  """
  
  move = None
  players = game_vars['players']
  
  # Waits until a player's map is updated to show their new map
  while not players[name]['map_updated']: 
    pass
  show_map(name)
  players[name]['map_updated'] = False

  
  # Displays user options
  print(f"\n{name}, what move do you want to make? (UP/DOWN/LEFT/RIGHT)\nOr, enter 'C:' followed by a message to send a message to your team")
  
  while move not in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
    display_chat(players[name]['team'])
    move = input()
    if move.startswith('C:'): # Send a chat if input is in format C:[message]
      send_chat(name, move[2:])
      time.sleep(1)
    elif move not in ['UP', 'DOWN', 'LEFT', 'RIGHT']: # Let user know they input a wrong move
      print(f"Uh-oh! {move} is an invalid move. Please enter a valid one!")
  
  # After player has selected a valid move, send it to the GameClient  
  game_vars['client'].publish(f"games/{game_vars['lobby_name']}/{name}/move", move)


# Allow a bot to make a move
def bot_move(name): 
  #print("bot: " + name)
  client = game_vars['client']
  players = game_vars['players']
  lobby_name = game_vars['lobby_name']
  
  while not players[name]['map_updated']:
    pass
  
  match players[name]["mode"]:
    case 'algorithm':
      move = 'DOWN'
      
      block = ["XX", "[]", "Enemypositions","Player"]
      for team in game_vars['teams'].values():
        for player_name in team:
          block.append(player_name)
      print(block)
        
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
  
  
def show_scoreboard():
  """
  Displays current score of teams in the game
  """
  
  score_str = f"\nSCOREBOARD:"
  for team, score in game_vars['scores'].items():
    score_str += f"\nTeam {team} : ${score}"
  print(score_str)
  

def find_next_player() -> str:
  """
  Returns the name of the player that is up next
  """
  
  for i in range(0, len(game_vars['player_order'])):
    if game_vars['player_order'][i] == game_vars['currentPlayer']:
      next_player = game_vars['player_order'][(i + 1) % len(game_vars['player_order'])]
      return next_player
    

def update_client_state(client_id, state):
  """
  Updates the current state of the client, and lets other clients know the current state of the client as well
  """
  
  state_change = game_vars['client_states'][client_id] != state if client_id in game_vars['client_states'].keys() else True
  game_vars['client_states'][client_id] = state
  if state_change:
    for client, state in game_vars['client_states'].items():
      game_vars['client'].publish(f"games/{game_vars['lobby_name']}/client_states", json.dumps({client : state}))


def all_synced(state) -> bool:
  """
  Returns whether all clients's state is equal to the given state
  """
  
  synced = all([client_state == state for client_state in game_vars['client_states'].values()])
  return synced

def end_game():
  """
  Notifies players that game is over and shows winner and final score results
  """
  
  update_client_state(game_vars['client_id'], 'game_over')
  print(f"\n------------------\n     GAME OVER")
  
  # Calculates final results
  result = {k : v for k, v in sorted(game_vars['scores'].items(), key= lambda x: x[1])} 
  
  # Displays final results
  rank = 1
  first_marked = False
  for team, score in result.items():
    if not first_marked:
      print(f"Team {team} won with ${score}!\n\nResults:")
    print(f"{rank}. {team} : ${score}")


def wait_for_turn():
  """
  Allows users to open chat rooms and send chats when it is not their turn
  To take their turn, users must enter '?'
  """
  
  choice = None
  while choice != '?':
    # Displays user options
    print(f"\nSelect one of the following: \n  Enter 'OC:[Team Name]' to enter a chat room for that team\n  Enter '[Team Name]:[Message]' to send a chat to the designated team.")
    choice = input()
    
    if choice.startswith("OC:"): # Opens a chat room if authorized
      team = choice[3:]
      if team in game_vars['teams'].keys() and any(player['team'] == team for player in game_vars['players'].values()):
        game_vars['active_room'] = team
        print(f"Chat room open for Team {team}")
        print("Enter 'C:[Message] to send a chat!")
        display_chat(game_vars['active_room'])
      elif game_vars['active_room'] != None and choice.startswith("C:"):
        send_anonymous_chat(game_vars['active_room'], choice[2:])    

          
# Main game loop  
if __name__ == '__main__':
  init_client()
  game_vars['client'].loop_start()
  title_screen()
  matchmaking()    
  start_game()
  while not game_vars['game_over']:
    run_game()
  end_game()
  game_vars['client'].loop_stop()
  
  
      


