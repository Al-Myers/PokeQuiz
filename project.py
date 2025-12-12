# project.py
# Main file for a Pokemon based Quiz!

import mysql.connector
import getpass
import random
from datetime import datetime, timedelta # for date manipulations
from tabulate import tabulate # makes the table pretty


# connects to MySQLs
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='LOL',
    database='project'
)
cursor = conn.cursor(dictionary=True)

# --------------------------------------------------------------------
# USER INFOMATION AND AUTHENTICATION
# --------------------------------------------------------------------

# track currently logged in user
current_user = None

# authenticates a user by username/email and password
def authenticate_user(identifier, password):
    query = """
    SELECT
        u.user_id,
        u.username,
        u.email,
        u.password,
        u.role_id,
        ur.role_name
    FROM users u
    LEFT JOIN user_roles ur ON u.role_id = ur.role_id
    WHERE u.username = %s OR u.email = %s
    LIMIT 1;
    """
    cursor.execute(query, (identifier, identifier))
    row = cursor.fetchone()
    if not row:
        return None

    # Checks to make sure password matches
    stored = row.get('password') if isinstance(row, dict) else row[3]
    if stored is None:
        return None

    # In a real app, would hash and salt the passwords
    if stored != password:
        return None

    # Updates last_login
    try:
        cursor.execute("UPDATE users SET last_login = NOW() WHERE user_id = %s;", (row.get('user_id'),))
        conn.commit()
    except Exception:
        pass

    # Builds returned user dict
    return {
        'user_id': row.get('user_id'),
        'username': row.get('username'),
        'email': row.get('email'),
        'role_id': row.get('role_id'),
        'role_name': row.get('role_name'),
    }

# need to log in before doing anything else
def login_prompt():
    # Gets the user's email or username, and then password
    # Then tries to authenticate them, and if successful, sets current_user
    # else, allows retry or back out
    global current_user
    print("\n===== Log In =====")
    while True:
        identity = input("Username or email (or 'back' to cancel): ").strip()
        if identity.lower() in ('back', 'b'):
            return False
        if not identity:
            print("Please enter a username or email.")
            continue

        pwd = getpass.getpass("Password: ")
        user = authenticate_user(identity, pwd)
        if user:
            current_user = user
            print(f"Logged in as {user['username']} (role: {user.get('role_name') or 'Unknown'})")
            return True

        print("Invalid username/email or password. Try again or type 'back' to cancel.")

# goes through the steps to register a new user
def register_prompt():
    print("\n=== Register ===")
    while True:
        username = input("Username (or 'back' to cancel): ").strip()
        if username.lower() in ('back', 'b'):
            return False
        if not username:
            print("Please enter a username.")
            continue

        email = input("Email: ").strip()
        if not email:
            print("Please enter an email address.")
            continue

        pwd = getpass.getpass("Password: ")
        pwd2 = getpass.getpass("Confirm password: ")
        if pwd != pwd2:
            print("Passwords do not match. Try again.")
            continue

        # always will be role 3 at the start
        role_id = 3

        try:
            cursor.execute(
                "INSERT INTO users (username, email, password, role_id) VALUES (%s, %s, %s, %s);",
                (username, email, pwd, role_id)
            )
            conn.commit()
            new_user_id = cursor.lastrowid

            # creates a basic profile row using the username as display_name
            cursor.execute(
                "INSERT INTO user_profiles (user_id, display_name, role_id) VALUES (%s, %s, %s);",
                (new_user_id, username, role_id)
            )
            conn.commit()

            print(f"User '{username}' registered successfully. You may now log in.")
            return True

        except mysql.connector.Error as e:
            conn.rollback()
            # makes sure to catch duplicate entry errors
            msg = str(e)
            if 'Duplicate' in msg or 'duplicate' in msg or 'ER_DUP_ENTRY' in msg:
                if 'username' in msg:
                    print("That username is already taken. Choose a different username.")
                elif 'email' in msg:
                    print("That email is already registered. Use a different email or log in.")
                else:
                    print("A user with that information already exists.")
            else:
                print("Registration failed:", e)
            # allows retry

# lets the current user edit their account info
def edit_account():
    global current_user
    if not current_user:
        print("\nYou must be logged in to edit your account!!")
        return

    # Menu that will loop until they choose to go back
    while True:
        print("\n===== EDIT ACCOUNT =====")
        print("1.] Change email")
        print("2.] Edit bio")
        print("3.] Back")
        choice = input("Option: ").strip()

        if choice == "3" or choice.lower().startswith("b"):
            return

        # Lets them change email
        if choice == "1":
            new = input("New email (or 'back' to cancel): ").strip()
            if new.lower() in ("back", "b") or not new:
                continue
            try:
                # Changes the email
                cursor.execute("UPDATE users SET email = %s WHERE user_id = %s;", (new, current_user['user_id']))
                conn.commit()
                current_user['email'] = new
                print("Email updated.")
            except mysql.connector.Error as e:
                conn.rollback()
                msg = str(e).lower()
                if "duplicate" in msg or "er_dup" in msg:
                    print("Email already registered.")
                else:
                    print("Update failed:", e)

        elif choice == "2":
            new = input("New bio (leave empty to clear, or 'back' to cancel): ")
            if isinstance(new, str) and new.lower() in ("back", "b"):
                continue
            # update or insert as needed
            cursor.execute("UPDATE user_profiles SET bio = %s WHERE user_id = %s;", (new, current_user['user_id']))
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO user_profiles (user_id, display_name, role_id, bio) VALUES (%s, %s, %s, %s);",
                    (current_user['user_id'], current_user.get('username'), current_user.get('role_id', 3), new)
                )
            conn.commit()
            print("Bio updated.")

        else:
            print("Invalid option.")

# searches for profiles
def search_profiles(display_name):
    display_name = display_name.strip()
    query = """
    SELECT
        up.user_id,
        up.display_name,
        ur.role_name AS role,
        up.bio,
        up.created_at,
        up.updated_at
    FROM user_profiles up
    LEFT JOIN user_roles ur
        ON up.role_id = ur.role_id
    WHERE LOWER(up.display_name) = LOWER(%s);
    """
    cursor.execute(query, (display_name,))
    rows = cursor.fetchall()

    return rows

# to view one's own profile
def view_own_profile():
    if not current_user:
        print("\nYou must be logged in to view your profile! How did this happen????")
        return

    try:
        # get display_name for the current user
        cursor.execute("SELECT display_name FROM user_profiles WHERE user_id = %s LIMIT 1;", (current_user['user_id'],))
        dn_row = cursor.fetchone()
        display_name = None
        if dn_row:
            display_name = dn_row.get('display_name') if isinstance(dn_row, dict) else dn_row[0]
        if not display_name:
            display_name = current_user.get('username')

        # reuse search_profiles which returns the same format as the profile search
        results = search_profiles(display_name)
        if not results:
            print("\nNo profile found for your account.")
            return

        headers = ["user_id", "display_name", "role", "bio", "created_at", "updated_at"]
        rows = [[row.get(h) for h in headers] for row in results]

        print("\n===== YOUR PROFILE =====")
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    except mysql.connector.Error as e:
        print("Failed to load profile:", e)

# sets and edits user favorite pokemon
def set_favorite_pokemon(current_user, cursor, conn):
    while True:
        # displays current favorite pokemon first, if they have none then say so
        # limit one because there should only be one favorite per user
        cursor.execute("SELECT pokemon_id FROM user_favorite_pokemon WHERE user_id = %s LIMIT 1;", (current_user['user_id'],))
        row = cursor.fetchone()
        current_fav_id = row.get('pokemon_id') if row else None
        
        # get the name of the current favorite pokemon
        if current_fav_id:
            cursor.execute("SELECT name FROM pokemon WHERE pokemon_id = %s;", (current_fav_id,))
            fav_row = cursor.fetchone()
            current_fav_name = fav_row.get('name') if fav_row else "Unknown"
            print(f"Current favorite Pokemon: {current_fav_name}")
        else:
            print("You do not have a favorite Pokemon set.")

        # asks for new favorite pokemon
        new = input("New favorite Pokemon (or 'back' to cancel): ").strip()
        if new.lower() in ("back", "b") or not new:
            return
                
        try:
            # Check if the pokemon exists
            cursor.execute("SELECT pokemon_id FROM pokemon WHERE LOWER(name) = LOWER(%s) LIMIT 1;", (new,))
            poke_row = cursor.fetchone()
                    
            if not poke_row:
                print(f"Pokemon '{new}' not found in database.")
                continue
                    
            new_pokemon_id = poke_row.get('pokemon_id')
                    
            # Removes old favorite if exists and one wasnt set yet 
            if current_fav_id and current_fav_id != new_pokemon_id:
                cursor.execute("DELETE FROM user_favorite_pokemon WHERE user_id = %s;", (current_user['user_id'],))
                # Decrement old pokemon's favorite count
                cursor.execute("UPDATE pokemon_favorites_count SET favorite_count = favorite_count - 1 WHERE pokemon_id = %s;", (current_fav_id,))
                conn.commit()
                    
            # Checks if new favorite already exists for this user, It shouldn't but just in case
            cursor.execute("SELECT pokemon_id FROM user_favorite_pokemon WHERE user_id = %s AND pokemon_id = %s;", (current_user['user_id'], new_pokemon_id))
            existing = cursor.fetchone()
                    
            # Inserts new favorite if it doesn't already exist
            if not existing:
                # Insert new favorite
                cursor.execute("INSERT INTO user_favorite_pokemon (user_id, pokemon_id) VALUES (%s, %s);", (current_user['user_id'], new_pokemon_id))
                # Increment new pokemon's favorite count
                cursor.execute("INSERT INTO pokemon_favorites_count (pokemon_id, favorite_count) VALUES (%s, 1) ON DUPLICATE KEY UPDATE favorite_count = favorite_count + 1;", (new_pokemon_id,))
                conn.commit()
                print("Favorite Pokemon updated.")
                return
            else:
                # incase of duplicate
                print("This Pokemon is already your favorite.")
                return
                        
        except mysql.connector.Error as e:
            conn.rollback()
            print("Update failed:", e)
            return

# allows user to submit feedback
def submit_feedback(user_id, cursor, db):
    print("\n=== SUBMIT FEEDBACK ===")
    # can only be 250 characters max for feedback
    feedback = input("Enter your feedback (or 'back' to cancel): ").strip()
    if feedback.lower() in ("back", "b"):
        return
    if len(feedback) == 0:
        print("Feedback cannot be empty.")
        return
    if len(feedback) > 250:
        print("Feedback must be 250 characters or less.")
        return

    cursor.execute("""
        INSERT INTO user_feedback (user_id, feedback)
        VALUES (%s, %s);
    """, (user_id, feedback))
    db.commit()
    print("Thank you for your feedback!")

# --------------------------------------------------------------------
# POKEMON INFOMATION
# --------------------------------------------------------------------

# basic search function for any pokemon. Returns: ID, Name, Types, Abilities
def search_pokemon(pokemon_name):
    pokemon_name = pokemon_name.strip()

    query = """
    SELECT 
        p.pokemon_id,
        p.name AS poke_name,

        t1.type_name AS type1,
        t2.type_name AS type2,

        a1.ability_name AS ability1,
        a2.ability_name AS ability2,
        ah.ability_name AS hidden_ability

    FROM pokemon p

    LEFT JOIN pokemon_types pt 
        ON p.pokemon_id = pt.pokemon_id
    LEFT JOIN types t1 
        ON pt.slot1_type = t1.type_id
    LEFT JOIN types t2 
        ON pt.slot2_type = t2.type_id

    LEFT JOIN pokemon_abilities pa
        ON p.pokemon_id = pa.pokemon_id
    LEFT JOIN abilities a1 
        ON pa.ability1_id = a1.ability_id
    LEFT JOIN abilities a2 
        ON pa.ability2_id = a2.ability_id
    LEFT JOIN abilities ah 
        ON pa.hidden_ability_id = ah.ability_id

    WHERE LOWER(p.name) = LOWER(%s);
    """

    cursor.execute(query, (pokemon_name,))
    results = cursor.fetchall()

    return results

# search the pokemon base stats
def search_pokemon_stats(pokemon_name):
    pokemon_name = pokemon_name.strip()
    query = """
    SELECT
        p.pokemon_id,
        p.name AS poke_name,
        ps.hp,
        ps.attack,
        ps.defense,
        ps.sp_atk,
        ps.sp_def,
        ps.speed,
        ps.total
    FROM pokemon p
    LEFT JOIN pokemon_stats ps
        ON p.pokemon_id = ps.pokemon_id
    WHERE LOWER(p.name) = LOWER(%s);
    """
    cursor.execute(query, (pokemon_name,))
    return cursor.fetchall()

# --------------------------------------------------------------------
# POKEMON QUIZ FUNCTIONS
# --------------------------------------------------------------------

# view all gamemodes
def view_gamemodes():
    query = """
    SELECT
        mode_id AS id,
        mode_name AS name,
        description
    FROM game_modes
    ORDER BY mode_id;
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    headers = ["ID", "Name", "Description"]
    table = [
        [
            r.get('id'),
            r.get('name'),
            r.get('description') or ""
        ]
        for r in rows
    ]

    print("\nAvailable Gamemodes:")
    print(tabulate(table, headers=headers, tablefmt="grid"))

# the guess weight game
def guess_weight_game(user_id, cursor, db):
    print("\n===== WHICH POKEMON WEIGHS MORE? =====")

    # for the leaderboard_general
    cursor.execute("""
        SELECT mode_id 
        FROM game_modes
        WHERE mode_name = 'guess_weight';
    """)
    mode_data = cursor.fetchone()
    mode_id = mode_data["mode_id"] if mode_data else None

    # starts the game loop
    while True:
        # gets two random pokemon from mysql
        query = """
            SELECT pokemon_id, name, weight
            FROM pokemon
            ORDER BY RAND()
            LIMIT 2;
        """
        cursor.execute(query)
        pokemon = cursor.fetchall()

        p1 = pokemon[0]
        p2 = pokemon[1]

        print("\nChoose which one is heavier:")
        print("1.", p1["name"])
        print("2.", p2["name"])

        # user input
        while True:
            choice = input("Your choice (1 or 2): ").strip()
            if choice in ("1", "2"):
                break
            print("Invalid choice. Please enter 1 or 2.")

        if choice == "1":
            user_choice = p1
        else:
            user_choice = p2

        # determines the correct Pokémon
        correct_pokemon = p1 if p1["weight"] > p2["weight"] else p2

        is_correct = (user_choice["pokemon_id"] == correct_pokemon["pokemon_id"])

        if is_correct:
            print("\nCorrect! The heavier Pokémon is:", correct_pokemon["name"])
            score = 100
        else:
            print("\nWrong! The heavier Pokémon is:", correct_pokemon["name"])
            score = 0

        # puts it in the leaderboard_guess_weight
        insert_weight_query = """
            INSERT INTO leaderboard_guess_weight (
                user_id,
                pokemon1_id,
                pokemon2_id,
                user_choice_id,
                correct_pokemon_id,
                is_correct,
                score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """

        cursor.execute(insert_weight_query, (
            user_id,
            p1["pokemon_id"],
            p2["pokemon_id"],
            user_choice["pokemon_id"],
            correct_pokemon["pokemon_id"],
            is_correct,
            score
        ))
        db.commit()

        # puts it in the overall leaderboard
        if mode_id is not None:
            cursor.execute("""
                INSERT INTO leaderboard_general (
                    user_id, mode_id, score, correct, incorrect
                )
                VALUES (%s, %s, %s, %s, %s);
            """, (
                user_id,
                mode_id,
                score,
                1 if is_correct else 0,
                0 if is_correct else 1
            ))
            db.commit()

        # play again loop
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("\nExiting weight guessing game!")
            break

# the stat guessing game
def guess_stats_game(user_id, cursor, db):
    print("\n=== Guess the Pokémon From Its Stats ===")

    cursor.execute("""
        SELECT mode_id
        FROM game_modes
        WHERE mode_name = 'guess_stats';
    """)
    mode_row = cursor.fetchone()
    mode_id = mode_row["mode_id"] if mode_row else None

    # starts loop
    while True:

        # gets a random Pokémon and its stats
        query = """
            SELECT 
                p.pokemon_id,
                p.name,
                s.hp, s.attack, s.defense, s.sp_atk, s.sp_def, s.speed, s.total
            FROM pokemon p
            JOIN pokemon_stats s ON p.pokemon_id = s.pokemon_id
            ORDER BY RAND()
            LIMIT 1;
        """
        cursor.execute(query)
        row = cursor.fetchone()

        pokemon_id = row["pokemon_id"]
        pokemon_name = row["name"]

        # displays stats to player
        print("\nHere are the stats of a Pokémon:")
        stat_table = [
            ["HP", row["hp"]],
            ["Attack", row["attack"]],
            ["Defense", row["defense"]],
            ["Sp. Atk", row["sp_atk"]],
            ["Sp. Def", row["sp_def"]],
            ["Speed", row["speed"]],
            ["Total", row["total"]],
        ]

        print(tabulate(stat_table, headers=["Stat", "Value"], tablefmt="grid"))

        # playee guess
        guess = input("\nYour guess (Pokémon name): ").strip()

        is_correct = (guess.lower() == pokemon_name.lower())

        # scores
        if is_correct:
            print(f"\n Correct! The Pokémon was {pokemon_name}!")
            score = 600
        else:
            print(f"\n Wrong! The Pokémon was {pokemon_name}.")
            score = 0

        # puts it in the stat leaderboard
        cursor.execute("""
            INSERT INTO leaderboard_guess_stats (
                user_id,
                pokemon_id,
                is_correct,
                score
            )
            VALUES (%s, %s, %s, %s);
        """, (user_id, pokemon_id, is_correct, score))

        db.commit()

        # puts it in general leaderboard
        if mode_id:
            insert_general = """
                INSERT INTO leaderboard_general (
                    user_id, mode_id, score, correct, incorrect
                )
                VALUES (%s, %s, %s, %s, %s);
            """

            cursor.execute(insert_general, (
                user_id,
                mode_id,
                score,
                1 if is_correct else 0,
                0 if is_correct else 1
            ))
            db.commit()

        print("\nScore this round:", score)

        # game loop
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("\nExiting stat guessing game!")
            break

# the species guessing game
def guess_species_game(user_id, cursor, db):
    print("\n=== Guess the Pokémon from Species ===")

    cursor.execute("""
        SELECT mode_id
        FROM game_modes
        WHERE mode_name = 'guess_species';
    """)
    mode_row = cursor.fetchone()
    mode_id = mode_row["mode_id"] if mode_row else None

    # starts loop
    while True:
        # gets a random Pokémon and its species
        query = """
            SELECT 
                p.pokemon_id,
                p.name,
                p.species
            FROM pokemon p
            WHERE p.species IS NOT NULL AND p.species <> ''
            ORDER BY RAND()
            LIMIT 1;
        """
        cursor.execute(query)
        row = cursor.fetchone()

        if not row:
            print("No valid Pokémon species found in database.")
            break

        given_species = row["species"]
        correct_pokemon_id = row["pokemon_id"]

        # Get all valid pokemon for this species (for checking)
        query_valid = """
            SELECT pokemon_id, name
            FROM pokemon
            WHERE LOWER(species) = LOWER(%s);
        """
        cursor.execute(query_valid, (given_species,))
        valid_pokemon = cursor.fetchall()
        valid_ids = {p["pokemon_id"] for p in valid_pokemon}
        valid_names = {p["name"].lower() for p in valid_pokemon}

        # displays species to player
        print(f"\nSpecies: {given_species}")
        print("Name any Pokémon that belongs to this species.")

        # player guess
        guess = input("\nYour guess (Pokémon name): ").strip()

        # check if guess matches any valid pokemon for this species
        is_correct = (guess.lower() in valid_names)

        # Get the guessed pokemon_id for recording
        guessed_pokemon_id = None
        if is_correct:
            for p in valid_pokemon:
                if p["name"].lower() == guess.lower():
                    guessed_pokemon_id = p["pokemon_id"]
                    break
        else:
            # Try to find the pokemon they guessed (even if wrong)
            cursor.execute("SELECT pokemon_id FROM pokemon WHERE LOWER(name) = LOWER(%s) LIMIT 1;", (guess,))
            wrong_row = cursor.fetchone()
            if wrong_row:
                guessed_pokemon_id = wrong_row["pokemon_id"]
            else:
                guessed_pokemon_id = correct_pokemon_id  # fallback

        # scores
        if is_correct:
            print(f"\nCorrect! {guess.title()} belongs to the species '{given_species}'!")
            score = 200
        else:
            # show one correct answer
            correct_name = valid_pokemon[0]["name"]
            print(f"\nWrong! A correct answer is: {correct_name} (species: {given_species})")
            score = 0

        # puts it in the species leaderboard
        cursor.execute("""
            INSERT INTO leaderboard_guess_species (
                user_id,
                given_species,
                guessed_pokemon_id,
                is_correct,
                score
            )
            VALUES (%s, %s, %s, %s, %s);
        """, (user_id, given_species, guessed_pokemon_id, is_correct, score))

        db.commit()

        # puts it in general leaderboard
        if mode_id:
            insert_general = """
                INSERT INTO leaderboard_general (
                    user_id, mode_id, score, correct, incorrect
                )
                VALUES (%s, %s, %s, %s, %s);
            """
            cursor.execute(insert_general, (
                user_id,
                mode_id,
                score,
                1 if is_correct else 0,
                0 if is_correct else 1
            ))
            db.commit()

        print("\nScore this round:", score)

        # game loop
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("\nExiting species guessing game!")
            break

# the egg group guessing game
def guess_egg_group_game(user_id, cursor, db):
    print("\n=== Guess if Pokémon Share an Egg Group ===")

    # Load mode_id from game_modes table
    cursor.execute("""
        SELECT mode_id
        FROM game_modes
        WHERE mode_name = 'guess_egg_group';
    """)
    mode_row = cursor.fetchone()
    mode_id = mode_row["mode_id"] if mode_row else None

    # starts loop
    while True:
        # gets two random Pokémon with egg group data
        query = """
            SELECT 
                p.pokemon_id,
                p.name,
                peg.egg_group1_id,
                peg.egg_group2_id
            FROM pokemon p
            JOIN pokemon_egg_groups peg ON p.pokemon_id = peg.pokemon_id
            ORDER BY RAND()
            LIMIT 2;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        if len(rows) < 2:
            print("Not enough Pokémon with egg group data found.")
            break

        p1 = rows[0]
        p2 = rows[1]

        # Get egg group sets for both pokemon
        p1_groups = {p1["egg_group1_id"]}
        if p1["egg_group2_id"]:
            p1_groups.add(p1["egg_group2_id"])

        p2_groups = {p2["egg_group1_id"]}
        if p2["egg_group2_id"]:
            p2_groups.add(p2["egg_group2_id"])

        # Check if they share any egg group
        share_egg_group = bool(p1_groups & p2_groups)

        # Display to player
        print(f"\nPokémon 1: {p1['name']}")
        print(f"Pokémon 2: {p2['name']}")
        print("\nDo these two Pokémon share at least one egg group?")

        # Player guess
        while True:
            guess = input("Your answer (yes/no): ").strip().lower()
            if guess in ("yes", "y", "no", "n"):
                break
            print("Please enter 'yes' or 'no'.")

        user_answer = (guess in ("yes", "y"))
        is_correct = (user_answer == share_egg_group)

        # scores
        if is_correct:
            print(f"\nCorrect! They {'share' if share_egg_group else 'do not share'} an egg group.")
            score = 100
        else:
            print(f"\nWrong! They {'share' if share_egg_group else 'do not share'} an egg group.")
            score = 0

        # puts it in the egg group leaderboard
        cursor.execute("""
            INSERT INTO leaderboard_guess_egg_group (
                user_id,
                pokemon1_id,
                pokemon2_id,
                share_egg_group,
                user_answer,
                is_correct,
                score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (user_id, p1["pokemon_id"], p2["pokemon_id"], share_egg_group, user_answer, is_correct, score))

        db.commit()

        # puts it in general leaderboard
        if mode_id:
            insert_general = """
                INSERT INTO leaderboard_general (
                    user_id, mode_id, score, correct, incorrect
                )
                VALUES (%s, %s, %s, %s, %s);
            """
            cursor.execute(insert_general, (
                user_id,
                mode_id,
                score,
                1 if is_correct else 0,
                0 if is_correct else 1
            ))
            db.commit()

        print("\nScore this round:", score)

        # game loop
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("\nExiting egg group guessing game!")
            break

# the dex number guessing game
def guess_dexnum_game(user_id, cursor, db):
    print("\n=== Guess the Pokémon from Dex Number ===")

    # Load mode_id from game_modes table
    cursor.execute("""
        SELECT mode_id
        FROM game_modes
        WHERE mode_name = 'guess_dexnum';
    """)
    mode_row = cursor.fetchone()
    mode_id = mode_row["mode_id"] if mode_row else None

    # starts loop
    while True:
        # gets a random Pokémon with its dex number
        query = """
            SELECT 
                p.pokemon_id,
                p.name
            FROM pokemon p
            WHERE p.pokemon_id IS NOT NULL
            ORDER BY RAND()
            LIMIT 1;
        """
        cursor.execute(query)
        row = cursor.fetchone()

        if not row:
            print("No valid Pokémon with dex numbers found in database.")
            break

        dex_number = row["pokemon_id"]
        correct_pokemon_id = row["pokemon_id"]
        correct_pokemon_name = row["name"]

        # displays dex number to player
        print(f"\nDex Number: #{dex_number}")
        print("Name the Pokémon that has this dex number.")

        # player guess
        guess = input("\nYour guess (Pokémon name): ").strip()

        # check if guess matches the correct pokemon
        is_correct = (guess.lower() == correct_pokemon_name.lower())

        # Get the guessed pokemon_id for recording
        guessed_pokemon_id = None
        if is_correct:
            guessed_pokemon_id = correct_pokemon_id
        else:
            # Try to find the pokemon they guessed (even if wrong)
            cursor.execute("SELECT pokemon_id FROM pokemon WHERE LOWER(name) = LOWER(%s) LIMIT 1;", (guess,))
            wrong_row = cursor.fetchone()
            if wrong_row:
                guessed_pokemon_id = wrong_row["pokemon_id"]
            else:
                guessed_pokemon_id = correct_pokemon_id  # fallback

        # scores
        if is_correct:
            print(f"\nCorrect! #{dex_number} is {correct_pokemon_name}!")
            score = 300
        else:
            print(f"\nWrong! #{dex_number} is {correct_pokemon_name}.")
            score = 0

        # puts it in the dex number leaderboard
        cursor.execute("""
            INSERT INTO leaderboard_guess_dexnum (
                user_id,
                shown_dex,
                user_choice_id,
                correct_pokemon_id,
                is_correct,
                score
            )
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (user_id, dex_number, guessed_pokemon_id, correct_pokemon_id, is_correct, score))

        db.commit()

        # puts it in general leaderboard
        if mode_id:
            insert_general = """
                INSERT INTO leaderboard_general (
                    user_id, mode_id, score, correct, incorrect
                )
                VALUES (%s, %s, %s, %s, %s);
            """
            cursor.execute(insert_general, (
                user_id,
                mode_id,
                score,
                1 if is_correct else 0,
                0 if is_correct else 1
            ))
            db.commit()

        print("\nScore this round:", score)

        # game loop
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("\nExiting dex number guessing game!")
            break

# the ability guessing game
def guess_ability_game(user_id, cursor, db):
    print("\n=== Guess a Pokémon with the Given Ability ===")

    cursor.execute("""
        SELECT mode_id
        FROM game_modes
        WHERE mode_name = 'guess_ability';
    """)
    mode_row = cursor.fetchone()
    mode_id = mode_row["mode_id"] if mode_row else None

    # starts loop
    while True:
        # gets a random Pokémon and one of its abilities
        query = """
            SELECT 
                p.pokemon_id,
                pa.ability1_id,
                pa.ability2_id,
                pa.hidden_ability_id,
                a1.ability_name,
                a2.ability_name AS ability2_name,
                ah.ability_name AS hidden_ability_name
            FROM pokemon p
            JOIN pokemon_abilities pa ON p.pokemon_id = pa.pokemon_id
            JOIN abilities a1 ON pa.ability1_id = a1.ability_id
            LEFT JOIN abilities a2 ON pa.ability2_id = a2.ability_id
            LEFT JOIN abilities ah ON pa.hidden_ability_id = ah.ability_id
            ORDER BY RAND()
            LIMIT 1;
        """
        cursor.execute(query)
        row = cursor.fetchone()

        if not row:
            print("No valid Pokémon with abilities found in database.")
            break

        # pick a random ability from the pokemon's available abilities
        abilities_available = []
        if row["ability1_id"]:
            abilities_available.append(("ability1", row["ability1_id"], row["ability_name"]))
        if row["ability2_id"]:
            abilities_available.append(("ability2", row["ability2_id"], row["ability2_name"]))
        if row["hidden_ability_id"]:
            abilities_available.append(("hidden", row["hidden_ability_id"], row["hidden_ability_name"]))

        chosen = random.choice(abilities_available)
        chosen_ability_id = chosen[1]
        chosen_ability_name = chosen[2]

        # Get all pokemon with this ability
        query_valid = """
            SELECT DISTINCT p.pokemon_id, p.name
            FROM pokemon p
            JOIN pokemon_abilities pa ON p.pokemon_id = pa.pokemon_id
            WHERE pa.ability1_id = %s OR pa.ability2_id = %s OR pa.hidden_ability_id = %s;
        """
        cursor.execute(query_valid, (chosen_ability_id, chosen_ability_id, chosen_ability_id))
        valid_pokemon = cursor.fetchall()
        valid_names = {p["name"].lower() for p in valid_pokemon}
        correct_pokemon_id = row["pokemon_id"]

        # displays ability to player
        print(f"\nAbility: {chosen_ability_name}")
        print("Name any Pokémon that has this ability.")

        # player guess
        guess = input("\nYour guess (Pokémon name): ").strip()

        # check if guess matches any valid pokemon with this ability
        is_correct = (guess.lower() in valid_names)

        # Get the guessed pokemon_id for recording
        guessed_pokemon_id = None
        if is_correct:
            for p in valid_pokemon:
                if p["name"].lower() == guess.lower():
                    guessed_pokemon_id = p["pokemon_id"]
                    break
        else:
            # Try to find the pokemon they guessed (even if wrong)
            cursor.execute("SELECT pokemon_id FROM pokemon WHERE LOWER(name) = LOWER(%s) LIMIT 1;", (guess,))
            wrong_row = cursor.fetchone()
            if wrong_row:
                guessed_pokemon_id = wrong_row["pokemon_id"]
            else:
                guessed_pokemon_id = correct_pokemon_id  # fallback

        # scores
        if is_correct:
            print(f"\nCorrect! {guess.title()} has the ability '{chosen_ability_name}'!")
            score = 250
        else:
            # show one correct answer
            correct_name = valid_pokemon[0]["name"]
            print(f"\nWrong! A correct answer is: {correct_name} (ability: {chosen_ability_name})")
            score = 0

        # puts it in the ability leaderboard
        cursor.execute("""
            INSERT INTO leaderboard_guess_ability (
                user_id,
                ability_id,
                guessed_pokemon_id,
                is_correct,
                score
            )
            VALUES (%s, %s, %s, %s, %s);
        """, (user_id, chosen_ability_id, guessed_pokemon_id, is_correct, score))

        db.commit()

        # puts it in general leaderboard
        if mode_id:
            insert_general = """
                INSERT INTO leaderboard_general (
                    user_id, mode_id, score, correct, incorrect
                )
                VALUES (%s, %s, %s, %s, %s);
            """
            cursor.execute(insert_general, (
                user_id,
                mode_id,
                score,
                1 if is_correct else 0,
                0 if is_correct else 1
            ))
            db.commit()

        print("\nScore this round:", score)

        # game loop
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("\nExiting ability guessing game!")
            break

# the type guessing game
def guess_type_game(user_id, cursor, db):
    print("\n=== Guess a Pokémon with the Given Type(s) ===")

    cursor.execute("""
        SELECT mode_id
        FROM game_modes
        WHERE mode_name = 'guess_type';
    """)
    mode_row = cursor.fetchone()
    mode_id = mode_row["mode_id"] if mode_row else None

    # loop starts
    while True:
        query = """
            SELECT 
                p.pokemon_id,
                p.name,
                pt.slot1_type AS type1_id,
                pt.slot2_type AS type2_id,
                t1.type_name AS type1_name,
                t2.type_name AS type2_name
            FROM pokemon p
            JOIN pokemon_types pt ON p.pokemon_id = pt.pokemon_id
            JOIN types t1 ON pt.slot1_type = t1.type_id
            LEFT JOIN types t2 ON pt.slot2_type = t2.type_id
            ORDER BY RAND()
            LIMIT 1;
        """
        cursor.execute(query)
        row = cursor.fetchone()

        if not row:
            print("No valid Pokémon with types found in database.")
            break

        type1_id = row["type1_id"]
        type2_id = row["type2_id"]
        type1_name = row["type1_name"]
        type2_name = row["type2_name"]

        # We basically need to build the prompt differently based on whether there's a second type
        # Which is why we have the next two following if statements
        if type2_id:
            print(f"\nTypes: {type1_name} / {type2_name}")
            print("Name any Pokémon that has BOTH of these types.")
        else:
            print(f"\nType: {type1_name}")
            print("Name any Pokémon that has this type.")

        # Fetchs valid Pokémon for the typing
        if type2_id:
            cursor.execute("""
                SELECT p.pokemon_id, p.name
                FROM pokemon p
                JOIN pokemon_types pt ON p.pokemon_id = pt.pokemon_id
                WHERE (pt.slot1_type = %s AND pt.slot2_type = %s)
                   OR (pt.slot1_type = %s AND pt.slot2_type = %s);
            """, (type1_id, type2_id, type2_id, type1_id))
        else:
            cursor.execute("""
                SELECT DISTINCT p.pokemon_id, p.name
                FROM pokemon p
                JOIN pokemon_types pt ON p.pokemon_id = pt.pokemon_id
                WHERE pt.slot1_type = %s OR pt.slot2_type = %s;
            """, (type1_id, type1_id))

        valid_rows = cursor.fetchall()
        valid_names = {r["name"].lower() for r in valid_rows}

        # player guess
        guess = input("\nYour guess (Pokémon name): ").strip()
        is_correct = (guess.lower() in valid_names)

        # Gets the guessed pokemon_id for recording
        guessed_pokemon_id = None
        if is_correct:
            for r in valid_rows:
                if r["name"].lower() == guess.lower():
                    guessed_pokemon_id = r["pokemon_id"]
                    break
        else:
            cursor.execute("SELECT pokemon_id FROM pokemon WHERE LOWER(name) = LOWER(%s) LIMIT 1;", (guess,))
            wrong_row = cursor.fetchone()
            if wrong_row:
                guessed_pokemon_id = wrong_row["pokemon_id"]
            else:
                # Fallback to a valid example so we never insert NULL incase of bad data
                # Has to be different than the other quizzes because of dual types
                guessed_pokemon_id = valid_rows[0]["pokemon_id"] if valid_rows else None

        # Displays and sets the scores
        if is_correct:
            print(f"\nCorrect! {guess.title()} matches the required type(s).")
            score = 300
        else:
            show_name = valid_rows[0]["name"] if valid_rows else "N/A"
            print(f"\nWrong! An example answer: {show_name}.")
            score = 0

        # puts it in the type leaderboard
        cursor.execute("""
            INSERT INTO leaderboard_guess_type (
                user_id,
                type1_id,
                type2_id,
                guessed_pokemon_id,
                is_correct,
                score
            )
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (user_id, type1_id, type2_id, guessed_pokemon_id, is_correct, score))
        db.commit()

        # puts it in general leaderboard
        if mode_id:
            cursor.execute("""
                INSERT INTO leaderboard_general (
                    user_id, mode_id, score, correct, incorrect
                )
                VALUES (%s, %s, %s, %s, %s);
            """, (
                user_id,
                mode_id,
                score,
                1 if is_correct else 0,
                0 if is_correct else 1
            ))
            db.commit()

        print("\nScore this round:", score)

        # game loop
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("\nExiting type guessing game!")
            break

# --------------------------------------------------------------------
# LEADERBOARD FUNCTIONS
# --------------------------------------------------------------------

# All follow this function layout so I am only commenting the first one
# They are all different leaderboards for each game mode plus the general one
# With the last one showing the favorite pokemon leaderboard
def view_general_leaderboard():
    # gets the users with the highest total scores, only shows top 10
    query = """
        SELECT
            u.user_id,
            u.username,
            COUNT(lg.entry_id) AS total_games,
            COALESCE(SUM(lg.score), 0) AS total_score
        FROM leaderboard_general lg
        JOIN users u ON lg.user_id = u.user_id
        GROUP BY u.user_id, u.username
        ORDER BY total_score DESC, total_games DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    # incase there are no entries yet
    if not rows:
        print("No leaderboard entries yet.")
        return

    # builds the table for tabulate
    # tabulate makes it easy to make nice tables in the console
    headers = ["USER ID", "USERNAME", "TOTAL GAMES", "TOTAL SCORE"]
    table = [[
        r.get("user_id"),
        r.get("username"),
        r.get("total_games", 0),
        r.get("total_score", 0)
    ] for r in rows]

    # prints the table
    print(tabulate(table, headers=headers, tablefmt="grid"))

def view_guess_weight_leaderboard():
    query = """
        SELECT
            lw.weight_id,
            up.display_name AS user,
            p1.name AS pokemon1,
            p2.name AS pokemon2,
            pc.name AS user_choice,
            pc2.name AS correct_choice,
            lw.is_correct,
            lw.score,
            lw.created_at
        FROM leaderboard_guess_weight lw
        JOIN user_profiles up ON lw.user_id = up.user_id
        JOIN pokemon p1 ON lw.pokemon1_id = p1.pokemon_id
        JOIN pokemon p2 ON lw.pokemon2_id = p2.pokemon_id
        JOIN pokemon pc ON lw.user_choice_id = pc.pokemon_id
        JOIN pokemon pc2 ON lw.correct_pokemon_id = pc2.pokemon_id
        ORDER BY lw.score DESC, lw.created_at DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("No Guess-Weight entries recorded.")
        return

    headers = ["Entry ID", "Player", "Pokémon 1", "Pokémon 2",
               "Your Choice", "Correct Pokémon", "Correct?", "Score", "Date"]

    table = [[
        r["weight_id"], r["user"], r["pokemon1"], r["pokemon2"],
        r["user_choice"], r["correct_choice"], "Yes" if r["is_correct"] else "No",
        r["score"], r["created_at"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))

def view_guess_stats_leaderboard():
    query = """
        SELECT
            ls.stats_id,
            up.display_name AS user,
            p.name AS pokemon,
            ls.is_correct,
            ls.score,
            ls.created_at
        FROM leaderboard_guess_stats ls
        JOIN user_profiles up ON ls.user_id = up.user_id
        JOIN pokemon p ON ls.pokemon_id = p.pokemon_id
        ORDER BY ls.created_at DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("No Guess-Stats entries recorded.")
        return

    headers = ["Entry ID", "Player", "Pokémon", "Correct?", "Score", "Date"]
    table = [[
        r["stats_id"], r["user"], r["pokemon"],
        "Yes" if r["is_correct"] else "No", r.get("score", 0), r["created_at"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))

def view_guess_species_leaderboard():
    query = """
        SELECT
            lgs.species_guess_id,
            up.display_name AS user,
            lgs.given_species,
            p.name AS guessed_pokemon,
            lgs.is_correct,
            lgs.score,
            lgs.created_at
        FROM leaderboard_guess_species lgs
        JOIN user_profiles up ON lgs.user_id = up.user_id
        JOIN pokemon p ON lgs.guessed_pokemon_id = p.pokemon_id
        ORDER BY lgs.score DESC, lgs.created_at DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("No Guess-Species entries recorded.")
        return

    headers = ["Entry ID", "Player", "Species", "Guessed Pokémon", "Correct?", "Score", "Date"]
    table = [[
        r["species_guess_id"], r["user"], r["given_species"], r["guessed_pokemon"],
        "Yes" if r["is_correct"] else "No", r.get("score", 0), r["created_at"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))

def view_guess_egg_group_leaderboard():
    query = """
        SELECT
            leg.egg_guess_id,
            up.display_name AS user,
            p1.name AS pokemon1,
            p2.name AS pokemon2,
            leg.share_egg_group AS actual_share,
            leg.user_answer,
            leg.is_correct,
            leg.score,
            leg.created_at
        FROM leaderboard_guess_egg_group leg
        JOIN user_profiles up ON leg.user_id = up.user_id
        JOIN pokemon p1 ON leg.pokemon1_id = p1.pokemon_id
        JOIN pokemon p2 ON leg.pokemon2_id = p2.pokemon_id
        ORDER BY leg.score DESC, leg.created_at DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("No Guess-Egg-Group entries recorded.")
        return

    headers = ["Entry ID", "Player", "Pokémon 1", "Pokémon 2", "Share Group?", "User Answer", "Correct?", "Score", "Date"]
    table = [[
        r["egg_guess_id"], r["user"], r["pokemon1"], r["pokemon2"],
        "Yes" if r["actual_share"] else "No",
        "Yes" if r["user_answer"] else "No",
        "Yes" if r["is_correct"] else "No",
        r.get("score", 0), r["created_at"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))

def view_guess_dexnum_leaderboard():
    query = """
        SELECT
            lgd.guess_id,
            up.display_name AS user,
            lgd.shown_dex,
            pu.name AS user_choice,
            pc.name AS correct_pokemon,
            lgd.is_correct,
            lgd.score,
            lgd.created_at
        FROM leaderboard_guess_dexnum lgd
        JOIN user_profiles up ON lgd.user_id = up.user_id
        JOIN pokemon pu ON lgd.user_choice_id = pu.pokemon_id
        JOIN pokemon pc ON lgd.correct_pokemon_id = pc.pokemon_id
        ORDER BY lgd.score DESC, lgd.created_at DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("No Guess-Dex-Number entries recorded.")
        return

    headers = ["Entry ID", "Player", "Dex #", "User Choice", "Correct Pokémon", "Correct?", "Score", "Date"]
    table = [[
        r["guess_id"], r["user"], r["shown_dex"], r["user_choice"], r["correct_pokemon"],
        "Yes" if r["is_correct"] else "No", r.get("score", 0), r["created_at"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))

def view_guess_ability_leaderboard():
    query = """
        SELECT
            lga.ability_guess_id,
            up.display_name AS user,
            a.ability_name AS ability,
            p.name AS guessed_pokemon,
            lga.is_correct,
            lga.score,
            lga.created_at
        FROM leaderboard_guess_ability lga
        JOIN user_profiles up ON lga.user_id = up.user_id
        JOIN abilities a ON lga.ability_id = a.ability_id
        JOIN pokemon p ON lga.guessed_pokemon_id = p.pokemon_id
        ORDER BY lga.score DESC, lga.created_at DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("No Guess-Ability entries recorded.")
        return

    headers = ["Entry ID", "Player", "Ability", "Guessed Pokémon", "Correct?", "Score", "Date"]
    table = [[
        r["ability_guess_id"], r["user"], r["ability"], r["guessed_pokemon"],
        "Yes" if r["is_correct"] else "No", r.get("score", 0), r["created_at"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))

def view_guess_type_leaderboard():
    query = """
        SELECT
            lgt.type_guess_id,
            up.display_name AS user,
            t1.type_name AS type1,
            t2.type_name AS type2,
            p.name AS guessed_pokemon,
            lgt.is_correct,
            lgt.score,
            lgt.created_at
        FROM leaderboard_guess_type lgt
        JOIN user_profiles up ON lgt.user_id = up.user_id
        JOIN types t1 ON lgt.type1_id = t1.type_id
        LEFT JOIN types t2 ON lgt.type2_id = t2.type_id
        JOIN pokemon p ON lgt.guessed_pokemon_id = p.pokemon_id
        ORDER BY lgt.score DESC, lgt.created_at DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("No Guess-Type entries recorded.")
        return

    headers = ["Entry ID", "Player", "Type 1", "Type 2", "Guessed Pokémon", "Correct?", "Score", "Date"]
    table = [[
        r["type_guess_id"], 
        r["user"], 
        r["type1"], 
        r.get("type2") or "N/A",
        r["guessed_pokemon"],
        "Yes" if r["is_correct"] else "No", 
        r.get("score", 0), 
        r["created_at"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))

def view_favorite_pokemon_leaderboard():
    query = """
        SELECT
            p.pokemon_id,
            p.name,
            COUNT(ufp.user_id) AS favorite_count
        FROM user_favorite_pokemon ufp
        JOIN pokemon p ON ufp.pokemon_id = p.pokemon_id
        GROUP BY p.pokemon_id, p.name
        ORDER BY favorite_count DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("No favorite Pokémon data available.")
        return

    headers = ["Pokémon ID", "Pokémon Name", "Number of Favorites"]
    table = [[
        r["pokemon_id"], r["name"], r["favorite_count"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))

# --------------------------------------------------------------------
# MENUS
# --------------------------------------------------------------------

# Profile menu
def run_profiles_menu():
    while True:
        print("\n===== PROFILE SEARCH =====")
        term = input("What profile do you want to search? (or 'back' to return): ").strip()
        if term.lower() in ("back", "b", "menu"):
            return
        if term == "":
            print("Please enter a profile name or 'back'.")
            continue

        results = search_profiles(term)
        if not results:
            print(f"\n No profile found with the name '{term}'.")
        else:
            headers = ["user_id", "display_name", "role", "bio", "created_at", "updated_at"]
            rows = [[row.get(h) for h in headers] for row in results]
            print("\n Profiles Found:")
            print(tabulate(rows, headers=headers, tablefmt="grid"))

# Quiz menu with all game modes
def run_quiz_menu():
    while True:
        print("\n===== QUIZ MENU =====")
        print("1.] View gamemodes")
        print("2.] Play Guess Stats")
        print("3.] Play Guess Weight")
        print("4.] Play Guess Species")
        print("5.] Play Guess Egg Group")
        print("6.] Play Guess Dex Number")
        print("7.] Play Guess Ability")
        print("8.] Play Guess Type")
        print("9.] Back")

        choice = input("Option: ").strip()
        if choice == "9" or choice.lower().startswith("b"):
            return
        
        if choice == "1":
            view_gamemodes()
            continue

        if choice == "2":
            guess_stats_game(current_user['user_id'], cursor, conn)
        elif choice == "3":
            guess_weight_game(current_user['user_id'], cursor, conn)
        elif choice == "4":
            guess_species_game(current_user['user_id'], cursor, conn)
        elif choice == "5":
            guess_egg_group_game(current_user['user_id'], cursor, conn)
        elif choice == "6":
            guess_dexnum_game(current_user['user_id'], cursor, conn)
        elif choice == "7":
            guess_ability_game(current_user['user_id'], cursor, conn)
        elif choice == "8":
            guess_type_game(current_user['user_id'], cursor, conn)
        else:
            print("Invalid option.")

# Leaderboards menu for game modes
def leaderboards_menu():
    while True:
        print("\n===== LEADERBOARDS MENU =====")
        print("1.] View General Leaderboard")
        print("2.] View Guess Weight Leaderboard")
        print("3.] View Guess Stats Leaderboard")
        print("4.] View Guess Species Leaderboard")
        print("5.] View Guess Egg Group Leaderboard")
        print("6.] View Guess Dex Number Leaderboard")
        print("7.] View Guess Ability Leaderboard")
        print("8.] Back")
        choice = input("Option: ").strip()
        if choice == "8" or choice.lower().startswith("b"):
            return
        if choice == "1":
            print("\n===== GENERAL LEADERBOARD =====")
            view_general_leaderboard()
        elif choice == "2":
            print("\n===== WEIGHT LEADERBOARD =====")
            view_guess_weight_leaderboard()
        elif choice == "3":
            print("\n===== STATS LEADERBOARD =====")
            view_guess_stats_leaderboard()
        elif choice == "4":
            print("\n===== SPECIES LEADERBOARD =====")
            view_guess_species_leaderboard()
        elif choice == "5":
            print("\n===== EGG GROUP LEADERBOARD =====")
            view_guess_egg_group_leaderboard()
        elif choice == "6":
            print("\n===== DEX NUMBER LEADERBOARD =====")
            view_guess_dexnum_leaderboard()
        elif choice == "7":
            print("\n===== ABILITY LEADERBOARD =====")
            view_guess_ability_leaderboard()
        else:
            print("Invalid option.")

# Favorites and comments menu
def run_favorites_comments_menu():
    while True:
        print("\n===== FAVORITES & COMMENTS MENU =====")
        print("1.] View Favorite Pokémon Leaderboard")
        print("2.] Change Favorite Pokémon")
        print("3.] View Comments")
        print("4.] Add Comment")
        print("5.] Remove Comment")
        print("6.] View your Comments")
        print("7.] Back")
        choice = input("Enter your choice here: ").strip()
        if choice == "7" or choice.lower().startswith("b"):
            return
        if choice == "1":
            # displays the leaderboard of the top 10 favorite pokemon
            view_favorite_pokemon_leaderboard()
        elif choice == "2":
            # lets user add a favorite pokemon, they can also do this in their profile
            set_favorite_pokemon(current_user, cursor, conn)
        elif choice == "3":
            # asks what pokemon comments to view
            pokemon_name = input("Which Pokémon's comments do you want to view? (or 'back' to cancel): ").strip()
            if pokemon_name.lower() not in ("back", "b") and pokemon_name:
                view_comments(pokemon_name)
        elif choice == "4":
            add_comment(current_user['user_id'], cursor, conn)
        elif choice == "5":
            remove_comment(current_user['user_id'], cursor, conn)
        elif choice == "6":
            view_comments_by_user(current_user['user_id'], cursor)
        else:
            print("Invalid option.")

# Pokemon search menu
def run_pokemon_menu():
        # chooses mode once per entry to this sub-menu
    while True:
        print("\n===== POKÉMON SEARCH =====")
        print("What do you want to search?")
        print("1.] Pokemon Basic Info")
        print("2.] Pokemon Stats")
        print("3.] Back")
        mode = input("Option: ").strip()
        if mode == "3" or mode.lower().startswith("b"):
            return
        use_stats = (mode == "2" or mode.lower().startswith("s"))

        while True:
            term = input("\nEnter Pokémon name to search (or 'back' to return): ").strip()
            if term.lower() in ("back", "b", "menu"):
                break
            if term == "":
                print("Please enter a Pokémon name or 'back'.")
                continue

            # if stats mode is selected
            if use_stats:
                results = search_pokemon_stats(term)
                if not results:
                    print(f"\n No Pokémon stats found for '{term}'.")
                else:
                    headers = ["pokemon_id", "poke_name", "hp", "attack", "defense", "sp_atk", "sp_def", "speed", "total"]
                    rows = [[row.get(h) for h in headers] for row in results]
                    print("\n Pokémon Stats:")
                    print(tabulate(rows, headers=headers, tablefmt="grid"))
            # if it isnt selected then it is just search pokemon
            else:
                results = search_pokemon(term)
                if not results:
                    print(f"\n No Pokémon found with the name '{term}'.")
                else:
                    headers = ["ID", "Name", "Type 1", "Type 2", "Ability 1", "Ability 2", "Hidden Ability"]
                    rows = []
                    for row in results:
                        rows.append([
                            row.get('pokemon_id'),
                            row.get('poke_name'),
                            row.get('type1') or "N/A",
                            row.get('type2') or "N/A",
                            row.get('ability1') or "N/A",
                            row.get('ability2') or "N/A",
                            row.get('hidden_ability') or "N/A"
                        ])
                    print("\n Pokémon Found:")
                    print(tabulate(rows, headers=headers, tablefmt="grid"))

# --------------------------------------------------------------------
# COMMENT / FAVORITES FUNCTIONS
# --------------------------------------------------------------------

# Lets the user to view comments for a specific pokemon
def view_comments(pokemon_name):

    pokemon_name = pokemon_name.strip()
    
    # First, get the pokemon_id
    cursor.execute("SELECT pokemon_id FROM pokemon WHERE LOWER(name) = LOWER(%s) LIMIT 1;", (pokemon_name,))
    poke_row = cursor.fetchone()
    
    if not poke_row:
        print(f"Pokémon '{pokemon_name}' not found.")
        return
    
    pokemon_id = poke_row.get('pokemon_id')
    
    # Get all comments for this pokemon
    query = """
        SELECT
            pc.comment_id,
            up.display_name AS user,
            pc.comment,
            pc.created_at
        FROM pokemon_comments pc
        JOIN user_profiles up ON pc.user_id = up.user_id
        WHERE pc.pokemon_id = %s
        ORDER BY pc.created_at DESC;
    """
    
    cursor.execute(query, (pokemon_id,))
    rows = cursor.fetchall()
    
    if not rows:
        print(f"No comments found for '{pokemon_name}'.")
        return
    
    headers = ["Comment ID", "User", "Comment", "Date"]
    table = [[
        r["comment_id"],
        r["user"],
        r["comment"],
        r["created_at"]
    ] for r in rows]
    
    print(f"\n===== COMMENTS FOR {pokemon_name.upper()} =====")
    print(tabulate(table, headers=headers, tablefmt="grid"))

# Lets the user add a comment to a specific pokemon
def add_comment(user_id, cursor, db):
    print("\n=== ADD A COMMENT ===")
    # asks what pokemon to comment on
    # then lets them add a comment that isnt longer than 250 characters
    pokemon_name = input("Which Pokémon do you want to comment on? (or 'back' to cancel): ").strip()
    if pokemon_name.lower() in ("back", "b"):
        return
    
    cursor.execute("SELECT pokemon_id FROM pokemon WHERE LOWER(name) = LOWER(%s) LIMIT 1;", (pokemon_name,))
    poke_row = cursor.fetchone()

    if not poke_row:
        print(f"Pokémon '{pokemon_name}' not found.")
        return
    
    pokemon_id = poke_row.get('pokemon_id')
    comment = input("Enter your comment (max 250 characters): ").strip()

    if len(comment) == 0 or len(comment) > 250:
        print("Comment must be between 1 and 250 characters.")
        return
    
    # adds the comment to the database
    cursor.execute("""
        INSERT INTO pokemon_comments (user_id, pokemon_id, comment)
        VALUES (%s, %s, %s);
    """, (user_id, pokemon_id, comment))
    db.commit()
    print("Comment added successfully!")

# Lets the user remove one of their comments by its ID
def remove_comment(user_id, cursor, db): 

    print("\n=== REMOVE A COMMENT ===")
    # asks which comment to remove by its ID
    comment_id_input = input("Enter the Comment ID to remove (or 'back' to cancel): ").strip()

    if comment_id_input.lower() in ("back", "b"):
        return
    
    if not comment_id_input.isdigit():
        print("Invalid Comment ID.")
        return
    comment_id = int(comment_id_input)

    # Check if the comment exists and belongs to the user
    cursor.execute("""
        SELECT comment_id FROM pokemon_comments
        WHERE comment_id = %s AND user_id = %s;
    """, (comment_id, user_id))
    row = cursor.fetchone()

    if not row:
        print("Comment not found or you do not have permission to delete it.")
        return
    
    # Deletes the comment
    cursor.execute("DELETE FROM pokemon_comments WHERE comment_id = %s;", (comment_id,))
    db.commit()
    print("Comment removed successfully!")

# Lets the user view all comments they have made, mainly to get the ID for removal
def view_comments_by_user(user_id, cursor):
    print("\n=== YOUR COMMENTS ===")
    # gets all comments made by the user
    query = """
        SELECT
            pc.comment_id,
            p.name AS pokemon_name,
            pc.comment,
            pc.created_at
        FROM pokemon_comments pc
        JOIN pokemon p ON pc.pokemon_id = p.pokemon_id
        WHERE pc.user_id = %s
        ORDER BY pc.created_at DESC;
    """
    cursor.execute(query, (user_id,))
    rows = cursor.fetchall()

    if not rows:
        print("You have not made any comments yet.")
        return

    headers = ["Comment ID", "Pokémon", "Comment", "Date"]
    table = [[
        r["comment_id"],
        r["pokemon_name"],
        r["comment"],
        r["created_at"]
    ] for r in rows]

    print(tabulate(table, headers=headers, tablefmt="grid"))


# --------------------------------------------------------------------
# MAIN PROGRAM
# --------------------------------------------------------------------
def main():
    print("===== WELCOME =====")
    print("  1.] Log in")
    print("  2.] Register Account")
    print("  3.] Quit")
    print("    ")
    print("░░░░░░░░▀████▀▄▄░░░░░░░░░░░░░░▄█")
    print("░░░░░░░░░░█▀░░░░▀▀▄▄▄▄▄░░░░▄▄▀▀█")
    print("░░▄░░░░░░░░█░░░░░░░░░░▀▀▀▀▄░░▄▀")
    print("░▄▀░▀▄░░░░░░▀▄░░░░░░░░░░░░░░▀▄▀")
    print("▄▀░░░░█░░░░░█▀░░░▄█▀▄░░░░░░▄█")
    print("▀▄░░░░░▀▄░░█░░░░░▀██▀░░░░░██▄█")
    print("░▀▄░░░░▄▀░█░░░▄██▄░░░▄░░▄░░▀▀░█")
    print("░░█░░▄▀░░█░░░░▀██▀░░░░▀▀░▀▀░░▄▀")
    print("░█░░░█░░█░░░░░░▄▄░░░░░░░░░░░▄▀")

    while True:
            pre = input("\nEnter your choice here: ").strip()
            if pre == "1":
                logged_in = login_prompt()
                if logged_in:
                    break
                continue
            if pre == "2":
                registered = register_prompt()
                # forces the user to relogin after registering, i now understand why this is common lol
                if registered:
                    print("\nRegistration complete — please log in to continue.")
                    print("===== WELCOME =====")
                    print("  1.] Log in")
                    print("  2.] Register Account")
                    print("  3.] Quit")
                    print("    ")
                    print("░░░░░░░░▀████▀▄▄░░░░░░░░░░░░░░▄█")
                    print("░░░░░░░░░░█▀░░░░▀▀▄▄▄▄▄░░░░▄▄▀▀█")
                    print("░░▄░░░░░░░░█░░░░░░░░░░▀▀▀▀▄░░▄▀")
                    print("░▄▀░▀▄░░░░░░▀▄░░░░░░░░░░░░░░▀▄▀")
                    print("▄▀░░░░█░░░░░█▀░░░▄█▀▄░░░░░░▄█")
                    print("▀▄░░░░░▀▄░░█░░░░░▀██▀░░░░░██▄█")
                    print("░▀▄░░░░▄▀░█░░░▄██▄░░░▄░░▄░░▀▀░█")
                    print("░░█░░▄▀░░█░░░░▀██▀░░░░▀▀░▀▀░░▄▀")
                    print("░█░░░█░░█░░░░░░▄▄░░░░░░░░░░░▄▀")
                continue
            if pre == "3":
                print("===== EXITING PROGRAM =====")
                return
            break

    # main menu
    while True:
        print("\n===== MAIN MENU =====")
        print("Welcome to Pokequiz! Please select from the menu below.")
        print("1.] View your Profile")
        print("2.] Edit your Account")
        print("3.] Access Search")
        print("4.] Access Quizes")
        print("5.] Access Game Leaderboards")
        print("6.] Pokemon Favorites and Comments.")
        print("7.] Submit Feedback")
        print("8.] Quit")
        choice = input("\nEnter your choice here: ").strip()

        if choice == "8" or choice.lower() in ("quit", "q", "exit"):
            print("===== EXITING PROGRAM =====")
            break
        elif choice == "1":
            view_own_profile()
            continue
        elif choice == "2":
            edit_account()
            continue
        elif choice == "3":
           # users can either search pokemon or profiles
            while True:
                print("\n===== SEARCH MENU =====")
                print("1.] Pokémon Search")
                print("2.] Profile Search")
                print("3.] Back")
                s = input("Enter your choice here: ").strip()
                if s == "1":
                    run_pokemon_menu()
                    break
                if s == "2":
                    run_profiles_menu()
                    break
                if s == "3" or s.lower().startswith("b"):
                    break
                print("Invalid option.")
            continue

        elif choice == "4":
            run_quiz_menu()
            continue

        elif choice == "5":
            leaderboards_menu()
            continue

        elif choice == "6":
            run_favorites_comments_menu()
            continue
        
        elif choice == "7":
            submit_feedback(current_user['user_id'], cursor, conn)
            continue
        print("Invalid option.")



# will go through main then close connection once done
if __name__ == "__main__":
    try:
        main()
    finally:
        # closes global connection/cursor after program ends
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass