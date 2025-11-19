import mysql.connector
import getpass
from datetime import datetime, timedelta # for date manipulations
from tabulate import tabulate # makes the table pretty


# connects to MySQLs
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='LOL!',
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



# Search function for profiles. Returns all profile data for a given profile name.
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

# --------------------------------------------------------------------
# POKEMON INFOMATION
# --------------------------------------------------------------------

# Basic search function for any pokemon. Returns: ID, Name, Types, Abilities
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


# Search the pokemon base stats
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
# MENUS
# --------------------------------------------------------------------

def run_profiles_menu():

    while True:
        term = input("\nEnter profile name to search (or 'back' to return): ").strip()
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


def run_pokemon_menu():
    # chooses mode once per entry to this sub-menu
    while True:
        print("\n===== POKÉMON MENU =====")
        print("Pokémon search mode:")
        print("  1) Info (types/abilities)")
        print("  2) Stats (base stats)")
        print("  3) Back to main menu")
        mode = input("Enter your choice here: ").strip()
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
            # if stats is picked
            if use_stats:
                results = search_pokemon_stats(term)
                if not results:
                    print(f"\n No Pokémon stats found for '{term}'.")
                else:
                    headers = ["pokemon_id", "poke_name", "hp", "attack", "defense", "sp_atk", "sp_def", "speed", "total"]
                    rows = [[row.get(h) for h in headers] for row in results]
                    print("\n Pokémon Stats:")
                    print(tabulate(rows, headers=headers, tablefmt="grid"))
            # goes through the pokemon info
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
                register_prompt()
                break
            if pre == "3":
                print("===== EXITING PROGRAM =====")
                return
            break


    # Main menu 
    while True:
        # Main menu
        print("\n===== MAIN MENU =====")
        print("Welcome to Pokequiz! Please select from the menu below.")
        print("  1.] Pokémon")
        print("  2.] Profiles")
        print("  3.] Exit")
        choice = input("\nEnter your choice here: ").strip()

        if choice == "3" or choice.lower().startswith("e") or choice.lower() == "exit":
            print("===== EXITING PROGRAM =====")
            break

        if choice == "2" or choice.lower().startswith("p"):
            run_profiles_menu()
        else:
            run_pokemon_menu() 



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