#!/usr/bin/python
import argparse
import logging
import time
import sys
import json

from custom_exceptions import GeneralPogoException

from api import PokeAuthSession
from location import Location

from pokedex import pokedex
from inventory import items
from flask import Flask
from flask import request
from flask import render_template
from flask import redirect, url_for
from flask import jsonify
import thread
import subprocess
import os
import sys
app = Flask(__name__)

@app.route('/_snipe_')
def remote_Snipe():
    
    #authtype = request.args.get('authtype', 0)
    #username = request.args.get('username', 0)
    #password = request.args.get('password', 0)
    #startingloc = request.args.get('startingloc', 0)
    snipecoords = request.args.get('snipecoords', 0)
    pokemonName = request.args.get('pokemonName', 0)
    doSnipe(session,args,snipecoords,pokemonName)
   
    
    #workDir = os.path.dirname(os.path.realpath(sys.argv[0]))
    #subprocess.Popen([workDir + r'\snipeparam.bat',authtype,username,password,str(startingloc),str(snipecoords)], creationflags = subprocess.CREATE_NEW_CONSOLE)
    
    return render_template('result.html')

@app.route('/')
def index():
    return render_template('dashboard.html')


@app.errorhandler(500)
def page_not_found(e):
    return render_template('result.html'), 404

def setupLogger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('Line %(lineno)d,%(filename)s - %(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)



# Get profile
def getProfile(session):
        logging.info("Printing Profile:")
        profile = session.getProfile()
        logging.info(profile)


# Grab the nearest pokemon details
def findBestPokemon(session,args,firstTry,pokemonName):
    # Get Map details and print pokemon
    logging.info("Finding Nearby Pokemon:")
    cells = session.getMapObjects()
    closest = float("Inf")
    best = -1
    pokemonBest = None
    
    latitude, longitude, _ = session.getCoordinates()
    logging.info("Current pos: %f, %f" % (latitude, longitude))
    for cell in cells.map_cells:
        # Heap in pokemon protos where we have long + lat
        pokemons = [p for p in cell.wild_pokemons] + [p for p in cell.catchable_pokemons]
        for pokemon in pokemons:
            # Normalize the ID from different protos
            pokemonId = getattr(pokemon, "pokemon_id", None)
            if not pokemonId:
                pokemonId = pokemon.pokemon_data.pokemon_id
            if pokedex[pokemonId].upper() == pokemonName.upper():
                pokemonBest = pokemon
                logging.info("Hey, we found the Pokemon you looks for!")
                break
            # Find distance to pokemon
            dist = Location.getDistance(
                latitude,
                longitude,
                pokemon.latitude,
                pokemon.longitude
            )

            # Log the pokemon found
            logging.info("Found a %s, %f meters away \n" % (
                pokedex[pokemonId],
                dist
            ))

            rarity = pokedex.getRarityById(pokemonId)
            # Greedy for rarest
            if rarity > best:
                pokemonBest = pokemon
                best = rarity
                closest = dist
            # Greedy for closest of same rarity
            elif rarity == best and dist < closest:
                pokemonBest = pokemon
                closest = dist
    if pokemonBest != None:
        if pokemonName != 'any':
            if pokemonName.upper() != str(pokedex[pokemonBest.pokemon_data.pokemon_id]).upper():
                pokemonBest = None
                logging.info("Couldn't find specific Pokemon @ this location.")
        else:
            logging.info(pokedex[pokemonBest.pokemon_data.pokemon_id] + " appears to be the rarest Pokemon @ location. Let's catch him!")
    else:
        data = [{
                'status': 'Did not find any pokemon @ given location.'
                }]
        json.dump(data, open('static/catch_data.json', 'w'))
        if firstTry == True:
            logging.info("Didn't find any, but sometimes this is a bug - let's retry.")
            pokemonBest = findBestPokemon(session,args,False,pokemonName)
        else:    
            logging.info("Sorry charlie, no Pokemon here. Enter a new location.")
        
    return pokemonBest


#Snipe!
def snipeABitch(session, pokemon, encounter, thresholdP=0.5, limit=10, delay=2):
    # Start encounter
    

    # Grab needed data from proto
    chances = encounter.capture_probability.capture_probability
    balls = encounter.capture_probability.pokeball_type
    bag = session.checkInventory().bag

    # Have we used a razz berry yet?
    berried = False

    # Make sure we aren't oer limit
    count = 0

    # Attempt catch
    while True:
        bestBall = items.UNKNOWN
        altBall = items.UNKNOWN

        # Check for balls and see if we pass
        # wanted threshold
        for i in range(len(balls)):
            if balls[i] in bag and bag[balls[i]] > 0:
                altBall = balls[i]
                if chances[i] > thresholdP:
                    bestBall = balls[i]
                    break

        # If we can't determine a ball, try a berry
        # or use a lower class ball
        if bestBall == items.UNKNOWN:
            if not berried and items.RAZZ_BERRY in bag and bag[items.RAZZ_BERRY]:
                logging.info("Using a RAZZ_BERRY")
                session.useItemCapture(items.RAZZ_BERRY, pokemon)
                berried = True
                time.sleep(delay)
                continue

            # if no alt ball, there are no balls
            elif altBall == items.UNKNOWN:
                data = [{
                'status': 'fail',
                'message': 'Out of usable balls'
                }]
                json.dump(data, open('static/catch_data.json', 'w'))
                time.sleep(1)
                raise GeneralPogoException("Out of usable balls")
                
            else:
                bestBall = altBall

        # Try to catch it!!
        logging.info("Using a %s" % items[bestBall])
        attempt = session.catchPokemon(pokemon, bestBall)
        time.sleep(delay)

        # Success or run away
        if attempt.status == 1:
            
            logging.critical("Congrats! We caught it!\n")
            return attempt
        if attempt.status == 2:
            logging.critical("Escaped ball, retry!")

        # CATCH_FLEE is bad news
        if attempt.status == 3:
            logging.info("Pokemon fled - possible soft ban.")
            return attempt

        # Only try up to x attempts
        count += 1
        if count >= limit:
            logging.info("Over catch limit")
            return None




# Do Inventory stuff
def getInventory(session):
    logging.info("Get Inventory:")
    logging.info(session.getInventory())


def doSnipe(session,args,snipeLoc,pokemonName):
    if pokemonName == "":
        pokemonName = 'any'
    if session:
	
        #if args.zslocation:
            #snipeLoc = args.zslocation
        #else:
            #snipeLoc = raw_input('Please paste target location (format is lat,lng)!: ')
        snipeLocSplit = snipeLoc.split(",")
        # General
        #getProfile(session)
        #getInventory(session)

        # Things we need GPS for
        if args.location:
			#Set up home location
            prevLatitude, prevLongitude, _ = session.getCoordinates()

            #Set up snipe location
            snipeLatitude = float(snipeLocSplit[0])
            snipeLongitude = float(snipeLocSplit[1])

			
			#move to snipe location
            session.setCoordinates(snipeLatitude,snipeLongitude)
			
			#Search snipe location for most powerful pokemon
            pokeMon = findBestPokemon(session,args,True,pokemonName)
            
            if pokeMon == None:
                session.setCoordinates(prevLatitude,prevLongitude)
                render_template("result.html")
                return
			
			#Encounter pokemon
            remoteEncounter = session.encounterPokemon(pokeMon)
            logging.info(remoteEncounter)
            time.sleep(2) 
            
						
			#move back home to capture
            session.setCoordinates(prevLatitude,prevLongitude)
            logging.info("Encountered pokemon - moving back to start location to catch.")
			#Wait for move to complete
            time.sleep(2)
            
            snipe = snipeABitch(session, pokeMon, remoteEncounter)
            if snipe.status == 3:
                data = [{
                'status': 'fail',
                'message': 'Pokemon fled'
                }]
                        
                json.dump(data, open('static/catch_data.json', 'w'))
                time.sleep(1)
            if snipe.status != 3:
                logging.info("Heres what we caught:\n")
                for pokez in session.getInventory().party:
                    if pokez.id == snipe.captured_pokemon_id:
                        logging.info(pokez)
                        
                        data = [{
                        'status': 'Success. Caught a ' + pokedex[pokez.pokemon_id] + ' CP:' + str(pokez.cp),
                        'pokemon_name': pokedex[pokez.pokemon_id],
                        'pokemon_id': pokez.pokemon_id

                               }]
                        json.dump(data, open('static/catch_data.json', 'w'))
                        time.sleep(1)
            #logging.critical(snipe.captured_pokemon_id)
            #if args.zslocation == False:
             #   reDo = raw_input('Shall we do this again(yes or no)?')
              #  if reDo.upper() == "YES":
               #     doSnipe(session,args)
    else:
        logging.critical('Session not created successfully')

		
if __name__ == '__main__':
    
    data = [{'status':'Server startup. Nothing to report.'}]
    json.dump(data, open('static/catch_data.json', 'w'))
    time.sleep(1)
    setupLogger()
    logging.debug('Logger set up')

    # Read in args
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--auth", help="Auth Service", required=True)
    parser.add_argument("-u", "--username", help="Username", required=True)
    parser.add_argument("-p", "--password", help="Password", required=True)
    parser.add_argument("-l", "--location", help="Location")
    parser.add_argument("-z", "--zslocation", help="Lat")
    parser.add_argument("-g", "--geo_key", help="GEO API Secret")
	
    args = parser.parse_args()
    logging.info(str(args.zslocation))
    # Check service
    if args.auth not in ['ptc', 'google']:
        logging.error('Invalid auth service {}'.format(args.auth))
        sys.exit(-1)

    # Create PokoAuthObject
    poko_session = PokeAuthSession(
        args.username,
        args.password,
        args.auth,
        geo_key=args.geo_key
    )

    # Authenticate with a given location
    # Location is not inherent in authentication
    # But is important to session
    if args.location:
        session = poko_session.authenticate(locationLookup=args.location)
    else:
        session = poko_session.authenticate()

    # Time to show off what we can do
    logging.info("Successfully logged in to Pokemon Go! Starting web server on port 5100.")
    app.run(host='0.0.0.0', port=5100)
    url_for('static', filename='catch_data.json')
    	
    
	
