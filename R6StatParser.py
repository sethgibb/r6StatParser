#!/usr/bin/env python3
import sys
import json
import copy
from jsonpath_ng.ext import parse

stat_dict = {}
plant_rounds = {}
disable_rounds = {}
side_round_wins = {}

final_output_dict = {}
plants_during_map_dict = {}
disables_during_map_dict = {}

def init_lists(data):
    json_expr = parse("$.stats[*]")
    players = [match.value for match in json_expr.find(data)]
    
    for player in players:
        name_expr = parse("$.username")
        name = [n.value for n in name_expr.find(player)]
        tempDict = {}
        #print(name[0])
        tempDict['ok'] = 0
        tempDict['od'] = 0
        tempDict['KOST'] = 0
        tempDict['1vX'] = 0
        tempDict['aces'] = 0
        #Sometimes we can determine who got a plant, but if more than one alive on a side its impossible without review
        tempDict['plants'] = 0
        tempDict['defuses'] = 0
        #Headshots on TK's are counted in the headshot stat, so need to adjust in the event they occur
        tempDict['headshot_adjustment'] = 0
        stat_dict[name[0]] = tempDict
    print(stat_dict)
    
def initSideRoundWins(nameOfMap):
    tempDict = {}
    tempDict[0] = {}
    tempDict[1] = {}
    tempDict[0]['Attack'] = 0
    tempDict[1]['Attack'] = 0
    tempDict[0]['Defense'] = 0
    tempDict[1]['Defense'] = 0
    tempDict[0]['Roster'] = []
    tempDict[1]['Roster'] = []
    tempDict[0]['TotalAttack'] = 0
    tempDict[1]['TotalAttack'] = 0
    tempDict[0]['TotalDefense'] = 0
    tempDict[1]['TotalDefense'] = 0
    side_round_wins[nameOfMap] = tempDict
    print(side_round_wins)

def process_round(item, roundNum, nameOfMap):
    print(f'Round Number {roundNum}')
    #start true and set false after first kill
    entryEngagement = True
    afterPlant = False
    shouldHaveDefuseEvent = False
    defuserDisabled = False
    plantTime = 0
    
    #dictionary for kill tracking, only needed for aces
    kills = {}
    
    #Dictionary for current round if recieved KOST_rounds_dict
    KOST_recieved = {}
    for username in stat_dict.keys():
        KOST_recieved[username] = False
        kills[username] = 0
        
    #Check which team won the round and wether they were attack or defence
    teams = [team for team in parse("$.teams[*]").find(item)]
    for team in teams:
        teamValue = team.value
        sideOfTeam = teamValue.get("role")
        teamIndex = team.path.index
        side_round_wins[nameOfMap][teamIndex]['Total'+sideOfTeam] += 1
        if teamValue.get("score") > teamValue.get("startingScore"):
            print(f'Team {teamIndex} won round {roundNum} on {sideOfTeam}')
            side_round_wins[nameOfMap][teamIndex][sideOfTeam] += 1
        
    #loop through players, check if dead, and if their team won.
    players = [player.value for player in parse("$.players[*]").find(item)]
    
    for player in players:
        name = player.get("username")
        isDead = [stat.value for stat in parse(f'$.stats[?(@.username = "{name}")].died').find(item)]
        teamIndex = player.get('teamIndex')
        
        #Populate roster in side_round_wins if its the first round for output purposees
        if roundNum == 1 :
            side_round_wins[nameOfMap][teamIndex]['Roster'].append(name) 
            
        #If Player survived to end of round
        if not isDead[0]:
            playersTeam = [team.value for team in parse(f'$.teams[{teamIndex}]').find(item)]
            #Check if their team won the round (I've seen both teams somehow have the "won" field be true so do this way instead)
            if playersTeam[0].get("score") > playersTeam[0].get("startingScore"):
                KOST_recieved[name] = True
    
    #setup tracker for 1vX's
    #this will setup every round, but in the event a round is played 4v5 it might catch the corner case
    team1vXTracker = []
    
    for i in range(2):
        playersOnTeam = [p.value for p in parse(f'$.players[?(@.teamIndex = {i})].username').find(item)]
        numOnTeam = len(playersOnTeam)
        team1vXTracker.append({'numPlayers' : numOnTeam, 'totalDead' : 0, 'nameOfDead' : [], 'playersOnTeam' : playersOnTeam})
    
    print(team1vXTracker)
    #Loop through all matchFeedback events
    #roundEvents = [event.value for event in parse("$.matchFeedback[*]").find(item)]
    roundEvents = [e for e in parse("$.matchFeedback[*]").find(item)]
    roundEventsList = [e.value for e in roundEvents]
    for eventFull in roundEvents:
        #print(eventFull)
        event = eventFull.value
        eventIndex = eventFull.path.index
        #print(event)
        #print(eventFull.path)
        type = event.get("type").get("name")
        
        if type == "Kill":
            #Check first to make sure its NOT a TK. need to subtract TK headshots if it occured
            killer = event.get("username")
            target = event.get("target")
            print(f'{killer} killed {target}')
            killerTeam = [p.value for p in parse(f'$[?(@.username = "{killer}")].teamIndex').find(players)]
            targetTeam = [p.value for p in parse(f'$[?(@.username = "{target}")].teamIndex').find(players)]
            #print(f'{type(killerTeam[0])} and {type(targetTeam[0])}')
            
            #1vX tracker
            #print(team1vXTracker[targetTeam[0]]['totalDead'])
            team1vXTracker[targetTeam[0]]['totalDead'] += 1
            team1vXTracker[targetTeam[0]]['nameOfDead'].append(target)
            
            if killerTeam[0] == targetTeam[0]:
                if event.get("headshot"):
                    stat_dict[killer]['headshot_adjustment'] += 1
                continue
            else:
                #If first kill, add entry stats
                if entryEngagement:
                    stat_dict[killer]['ok'] += 1
                    stat_dict[target]['od'] += 1
                    entryEngagement = False
                #Killer recieves KOST for the round
                KOST_recieved[killer] = True
                kills[killer] += 1
                
                #If we are down to last player on team and other team has at least 2 alive still
                if (team1vXTracker[targetTeam[0]]['numPlayers'] - team1vXTracker[targetTeam[0]]['totalDead']) == 1 and (team1vXTracker[killerTeam[0]]['numPlayers'] - team1vXTracker[killerTeam[0]]['totalDead']) >= 2 :
                    #Get last remaing player on targets team, and see if targets team wins the round
                    potentialClutchPlayer = [p for p in team1vXTracker[targetTeam[0]]['playersOnTeam'] if p not in team1vXTracker[targetTeam[0]]['nameOfDead']]
                    print(f'1vX chance for {potentialClutchPlayer[0]}')
                    targetTeamJson = [team.value for team in parse(f'$.teams[{targetTeam[0]}]').find(item)]
                    if targetTeamJson[0].get("score") > targetTeamJson[0].get("startingScore"):
                        print(f'1vX achieved for {potentialClutchPlayer[0]}')
                        stat_dict[potentialClutchPlayer[0]]['1vX'] += 1
                
                #check if trade - additional logic needed after defuser planted
                killEarnedAtTime = event.get("timeInSeconds")
                targetKills = [tkill.value for tkill in parse(f'$[?(@.username = "{target}")]').find(roundEventsList)]
                for tkill in targetKills:
                    targetKillEarnedAt = tkill.get("timeInSeconds")
                    if tkill.get('type').get("name") == 'Kill':
                        if not afterPlant:
                            #print(f'Target Kill at {targetKillEarnedAt} compared to death at {killEarnedAtTime}')
                            if targetKillEarnedAt > killEarnedAtTime and targetKillEarnedAt < (killEarnedAtTime+5):
                                tradedPlayer = tkill.get('target')
                                print(f'{tradedPlayer} was traded by {killer}')
                                KOST_recieved[tradedPlayer] = True
                        #If after plant, need to do some shenanigans to make sure we proper trades counted
                        elif afterPlant:
                            #if before the plant event and the kill is before 40, need to do some special processing
                            if eventIndex < plantIndex and killEarnedAtTime > 40:
                                tradeCutoffPrePlant = 45 - killEarnedAtTime
                                if targetKillEarnedAt < (plantTime+tradeCutoffPrePlant):
                                    tradedPlayer = tkill.get('target')
                                    #Print something to confirm special processing
                                    print(f'{tradedPlayer} was traded by {killer}')
                                    KOST_recieved[tradedPlayer] = True
                            elif eventIndex > plantIndex:
                                if targetKillEarnedAt > killEarnedAtTime and targetKillEarnedAt < (killEarnedAtTime+5):
                                    tradedPlayer = tkill.get('target')
                                    print(f'{tradedPlayer} was traded by {killer}')
                                    KOST_recieved[tradedPlayer] = True
        #Plant
        elif type == "DefuserPlantComplete":
            afterPlant = True
            determinedPlanter = False
            plantTime = event.get('timeInSeconds')
            plantIndex = eventIndex
            attackingTeam = [t.path.index for t in parse(f'$.teams[?(@.role = Attack)]').find(item)]
            potentialPlanters = [p for p in team1vXTracker[attackingTeam[0]]['playersOnTeam'] if p not in team1vXTracker[attackingTeam[0]]['nameOfDead']]
            if len(potentialPlanters) == 1:
                print(f'Defuser Planted with {plantTime} left. Event index is {plantIndex}. Planter has to be {potentialPlanters[0]}')
                stat_dict[potentialPlanters[0]]['plants'] += 1
                KOST_recieved[potentialPlanters[0]] = True
                determinedPlanter = True
            else:
                print(f'Defuser Planted with {plantTime} left. Event index is {plantIndex}, potentialPlanters are {potentialPlanters}')
            #Defuse disabled event are not always recorded, check if defence won here as a failsafe (means a defuse event has to occur)
            teamObject = [team.value for team in parse(f'$.teams[{attackingTeam[0]}]').find(item)]
            if teamObject[0].get('score') == teamObject[0].get('startingScore'):
                shouldHaveDefuseEvent = True
            
        #Defuse
        elif type == "DefuserDisableComplete":
            shouldHaveDefuseEvent = True
                
        #OperatorSwap currently dummy and shouldn't need to do anything with item
        elif type == "OperatorSwap":
            continue
        else:
            print(f"Unexpected event type {type}")
    
    #failsafe for if defuser disabled event not recorded for some reason (semi common occurence)
    #also moving logic down here so its not duplicated
    if shouldHaveDefuseEvent:
        defuserDisabled = True
        determinedDefuser = False
        defendingTeam = [t.path.index for t in parse(f'$.teams[?(@.role = Defense)]').find(item)]
        potentialDefusers = [p for p in team1vXTracker[defendingTeam[0]]['playersOnTeam'] if p not in team1vXTracker[defendingTeam[0]]['nameOfDead']]
        if len(potentialDefusers) == 1:
            print(f'Defuser Disabled by {potentialDefusers[0]}')
            stat_dict[potentialDefusers[0]]['defuses'] += 1
            #Likely redundant cause finishing a defuse wins the round and they almost always live if defuse completes
            KOST_recieved[potentialDefusers[0]] = True
            determinedDefuser = True
        else:
            print(f'Defuser Disabled by one of {potentialDefusers}')
            
    #check for an ace defined ONLY as 5 kills in a round (TK's already factored in above)
    for player in kills: 
        if kills[player] == 5:
            print(f'Ace achieved by {player}')
            stat_dict[player]['aces'] += 1
    
    print(f'KOST Round {KOST_recieved}')
    for player in KOST_recieved:
        if KOST_recieved[player]:
            stat_dict[player]['KOST'] += 1
    
    #For plants and defuses, the event doesn't credit the correct player, so will add event to be printed out and let stat taker know to check and credit accordingly
    #We will also include the players who did NOT get KOST in case their KOST num needs to be increased
    if afterPlant and not determinedPlanter:
        potentialKOSTlessPlanters = [p for p in potentialPlanters if not KOST_recieved[p]]
        plant_rounds[roundNum] = {'potentialPlanters':potentialPlanters, 'potentialKOSTlessPlanters':potentialKOSTlessPlanters}
    
    if defuserDisabled and not determinedDefuser:
        potentialKOSTlessDefusers = [p for p in potentialDefusers if not KOST_recieved[p]]
        disable_rounds[roundNum] = {'potentialDefusers':potentialDefusers, 'potentialKOSTlessDefusers':potentialKOSTlessDefusers}
    
    json_expr = parse("$.site")
    matches = [match.value for match in json_expr.find(item)]
    
    print(matches[0])
    print()
    print()
    return item
    
def initalizePlayerToFinalOutput(player):
        tempDict = {}
        #print(name[0])
        tempDict['ok'] = 0
        tempDict['od'] = 0
        tempDict['KOST'] = 0
        tempDict['1vX'] = 0
        tempDict['aces'] = 0
        #Sometimes we can determine who got a plant, but if more than one alive on a side its impossible without review
        tempDict['plants'] = 0
        tempDict['defuses'] = 0
        #Will represent actual headshots in the final output
        tempDict['headshots'] = 0
        final_output_dict[player] = tempDict
    
def endOfMapProcessing(json_tree, map):
    for player in stat_dict:
        playerMapStats = stat_dict[player]
        
        #if player is not yet in our final output - lets initialize it
        if player not in final_output_dict:
            initalizePlayerToFinalOutput(player)
            
        final_output_dict[player]['ok'] += stat_dict[player]['ok']
        final_output_dict[player]['od'] += stat_dict[player]['od']
        final_output_dict[player]['KOST'] += stat_dict[player]['KOST']
        final_output_dict[player]['1vX'] += stat_dict[player]['1vX']
        final_output_dict[player]['aces'] += stat_dict[player]['aces']
        #Sometimes we can determine who got a plant, but if more than one alive on a side its impossible without review
        final_output_dict[player]['plants'] += stat_dict[player]['plants']
        final_output_dict[player]['defuses'] += stat_dict[player]['defuses']
        #Headshots on TK's are counted in the headshot stat, so need to adjust in the event they occur
        headshotsJson = [h.value for h in parse(f'$.stats[?(@.username = "{player}")].headshots').find(json_tree)]
        final_output_dict[player]['headshots'] += headshotsJson[0] - stat_dict[player]['headshot_adjustment']
    
    plants_during_map_dict[map] = copy.deepcopy(plant_rounds)
    disables_during_map_dict[map] = copy.deepcopy(disable_rounds)
 
def resetRoundLists():
    stat_dict.clear()
    plant_rounds.clear()
    disable_rounds.clear()
    
def printOutput():
    #headshots = 'dummy'
    for player in final_output_dict:
        playerStats = final_output_dict[player]
        print(f'{player:25} - Rounds of KOST = {playerStats["KOST"]:2}, Headshots = {playerStats["headshots"]:2}, OK = {playerStats["ok"]:2}, OD = {playerStats["od"]:2}, 1vX = {playerStats["1vX"]:2}, Aces = {playerStats["aces"]}, Plants = {playerStats["plants"]}, Disables = {playerStats["defuses"]}')
    
    for map in plants_during_map_dict:
        currentMap = plants_during_map_dict[map]
        for round in currentMap:
            if len(currentMap[round]['potentialKOSTlessPlanters']) > 0:
                print(f'Plant occured in map {map} round {round}. One of these players planted {currentMap[round]["potentialPlanters"]}. Of these players {currentMap[round]["potentialKOSTlessPlanters"]} did not get KOST for the round yet')
            else:
                print(f'Plant occured in map {map} round {round}. One of these players planted {currentMap[round]["potentialPlanters"]}.')
    
    for map in disables_during_map_dict:
        currentMap = disables_during_map_dict[map]
        for round in currentMap:
            if len(currentMap[round]['potentialKOSTlessDefusers']) > 0:
                print(f'Defuser disable occured in map {map} round {round}. One of these players defused {currentMap[round]["potentialDefusers"]}. Of these players {currentMap[round]["potentialKOSTlessDefusers"]} did not get KOST for the round yet')
            else:
                print(f'Defuser disable occured in map {map} round {round}. One of these players defused {currentMap[round]["potentialDefusers"]}.')
                
    print()
    for map in side_round_wins:
        totalAttack = side_round_wins[map][0]['Attack'] + side_round_wins[map][1]['Attack']
        totalDefense = side_round_wins[map][0]['Defense'] + side_round_wins[map][1]['Defense']
        print(f'For {map}, attack won {totalAttack} rounds and defense won {totalDefense}')
        print(f'This roster {side_round_wins[map][0]['Roster']} won {side_round_wins[map][0]['Attack']} of {side_round_wins[map][0]['TotalAttack']} attacks and {side_round_wins[map][0]['Defense']} of {side_round_wins[map][0]['TotalDefense']} defenses')
        print(f'This roster {side_round_wins[map][1]['Roster']} won {side_round_wins[map][1]['Attack']} of {side_round_wins[map][1]['TotalAttack']} attacks and {side_round_wins[map][1]['Defense']} of {side_round_wins[map][1]['TotalDefense']} defenses')
        print()

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <json_file_1> [json_file_2...]")
        sys.exit(1)
        
    for map in range(1, len(sys.argv)):
        json_file = sys.argv[map]
        #query_expr = sys.argv[2] if len(sys.argv) > 2 else None

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Error: File '{json_file}' not found.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse JSON - {e}")
            sys.exit(1)

        init_lists(data)
        
        #Default expression
        #if not query_expr:
        query_expr = '$.rounds[*]'
        
        #if query_expr:
            #try:
        jsonpath_expr = parse(query_expr)
        matches = [match.value for match in jsonpath_expr.find(data)]

        nameOfMap = [name.value for name in parse("$.rounds[0].map.name").find(data)]
        initSideRoundWins(nameOfMap[0])
        print (nameOfMap)
        roundNum = 1
        for round in matches:
            processed = process_round(round, roundNum, nameOfMap[0])
            roundNum += 1
        
        endOfMapProcessing(data, map)
        resetRoundLists()
                #print(json.dumps(processed, ensure_ascii=False))
        #except Exception as e:
            #print(f"Error parsing JSONPath: {e}")
    #else:
        #print(json.dumps(data, indent=4, ensure_ascii=False))
    printOutput()

if __name__ == "__main__":
    main()
