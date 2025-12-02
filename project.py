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

    stored = row.get('password') if isinstance(row, dict) else row[3]
    if stored is None:
        return None

    if stored != password:
        return None

    # updates last_login
    try:
        cursor.execute("UPDATE users SET last_login = NOW() WHERE user_id = %s;", (row.get('user_id'),))
        conn.commit()
    except Exception:
        pass

    # builds returned user dict
    return {
        'user_id': row.get('user_id'),
        'username': row.get('username'),
        'email': row.get('email'),
        'role_id': row.get('role_id'),
        'role_name': row.get('role_name'),
    }

# need to log in before doing anything else
def login_prompt():
    global current_user
    print("\n===== Log In =====")
    while True:
        ident = input("Username or email (or 'back' to cancel): ").strip()
        if ident.lower() in ('back', 'b'):
            return False
        if not ident:
            print("Please enter a username or email.")
            continue

        pwd = getpass.getpass("Password: ")
        user = authenticate_user(ident, pwd)
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

    while True:
        print("\n===== EDIT ACCOUNT =====")
        print("1.] Change email")
        print("2.] Edit bio")
        print("3.] Back")
        choice = input("Option: ").strip()

        if choice == "3" or choice.lower().startswith("b"):
            return

        if choice == "1":
            new = input("New email (or 'back' to cancel): ").strip()
            if new.lower() in ("back", "b") or not new:
                continue
            try:
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

    # -----------------------------------------------------
    # Load mode_id from game_modes table
    # -----------------------------------------------------
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

# --------------------------------------------------------------------
# LEADERBOARD FUNCTIONS
# --------------------------------------------------------------------

def view_general_leaderboard():
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

    if not rows:
        print("No leaderboard entries yet.")
        return

    headers = ["USER ID", "USERNAME", "TOTAL GAMES", "TOTAL SCORE"]
    table = [[
        r.get("user_id"),
        r.get("username"),
        r.get("total_games", 0),
        r.get("total_score", 0)
    ] for r in rows]

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

# --------------------------------------------------------------------
# MENUS
# --------------------------------------------------------------------

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

def run_quiz_menu():
    while True:
        print("\n===== QUIZ MENU =====")
        print("1.] View gamemodes")
        print("2.] Play Guess Stats")
        print("3.] Play Guess Weight")
        print("4.] Back")

        choice = input("Option: ").strip()
        if choice == "4" or choice.lower().startswith("b"):
            return
        
        if choice == "1":
            view_gamemodes()
            continue

        if choice == "2":
            guess_stats_game(current_user['user_id'], cursor, conn)

        if choice == "3":
            guess_weight_game(current_user['user_id'], cursor, conn)

def leaderboards_menu():
    while True:
        print("\n===== LEADERBOARDS MENU =====")
        print("1.] View General Leaderboard")
        print("2.] View Guess Weight Leaderboard")
        print("3.] View Guess Stats Leaderboard")
        print("4.] Back")
        choice = input("Option: ").strip()
        if choice == "4" or choice.lower().startswith("b"):
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
        else:
            print("Invalid option.")


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
                login_prompt()
                break
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
        print("5.] Access Leaderboards")
        print("6.] Quit")
        choice = input("\nEnter your choice here: ").strip()

        if choice == "6" or choice.lower() in ("quit", "q", "exit"):
            print("===== EXITING PROGRAM =====")
            break

        if choice == "1":
            view_own_profile()
            continue

        if choice == "2":
            edit_account()
            continue

        if choice == "3":
           # users can either search pokemon or profiles
            while True:
                print("\n===== SEARCH MENU =====")
                print("1.] Pokémon Search")
                print("2.] Profile Search")
                print("3.] Back")
                s = input("Option: ").strip()
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

        if choice == "4":
            run_quiz_menu()
            continue

        if choice == "5":
            leaderboards_menu()
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