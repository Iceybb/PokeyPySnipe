#!/usr/bin/python
import argparse
import logging
import time
import sys
from custom_exceptions import GeneralPogoException

from api import PokeAuthSession
from location import Location

from pokedex import pokedex
from inventory import items

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
def findBestPokemon(session,args):
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
        logging.info(pokedex[pokemonBest.pokemon_data.pokemon_id] + " appears to be the rarest Pokemon @ location. Let's catch him!")
    else:
        logging.info("Sorry charlie, no Pokemon here. Enter a new location.")
        doSnipe(session,args)
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
            logging.info("Pokemon fleed - possible soft ban.")
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


def doSnipe(session,args):
    if session:
	
        if args.zslocation:
            snipeLoc = args.zslocation
        else:
            snipeLoc = raw_input('Please paste target location (format is lat,lng)!: ')
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
            pokeMon = findBestPokemon(session,args)
            
            if pokeMon == None:
                session.setCoordinates(prevLatitude,prevLongitude)
                return
			
			#Encounter pokemon
            remoteEncounter = session.encounterPokemon(pokeMon)
            time.sleep(2) 
            
						
			#move back home to capture
            session.setCoordinates(prevLatitude,prevLongitude)
			
			#Wait for move to complete
            time.sleep(2)
            
            snipe = snipeABitch(session, pokeMon, remoteEncounter)
            if snipe.status != 3:
                logging.info("Heres what we caught:\n")
                for pokez in session.getInventory().party:
                    if pokez.id == snipe.captured_pokemon_id:
                        logging.info(pokez)
                    
            #logging.critical(snipe.captured_pokemon_id)
            if args.zslocation == False:
                reDo = raw_input('Shall we do this again(yes or no)?')
                if reDo.upper() == "YES":
                    doSnipe(session,args)
    else:
        logging.critical('Session not created successfully')

		
if __name__ == '__main__':
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
	
    doSnipe(session,args)
	

