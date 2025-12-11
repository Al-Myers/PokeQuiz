SELECT * FROM pokemon_data_staging;
SELECT * FROM abilities;
SELECT * FROM egg_groups;
SELECT * FROM growth_rates;
SELECT * FROM pokemon;
SELECT * FROM pokemon_egg_groups;
SELECT * FROM pokemon_stats;
SELECT * FROM pokemon_types;
SELECT * FROM special_groups;
SELECT * FROM types;
SELECT * FROM user_profiles;
SELECT * FROM user_roles;
SELECT * FROM users;
SELECT * FROM leaderboard_guess_weight;
SELECT * FROM leaderboard_guess_stats;
SELECT * FROM leaderboard_general;

-- ----------------------------------------------------------------------------------
-- CREATION OF TABLES
-- ----------------------------------------------------------------------------------

-- -------------------------------------
-- NON-POKEMON (USERS AND APP)
-- -------------------------------------

-- Table to hold users
CREATE TABLE users (
    user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role_id INT NOT NULL DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL DEFAULT NULL,
    status ENUM('active', 'inactive', 'banned') DEFAULT 'active',

    CONSTRAINT fk_user_role
        FOREIGN KEY (role_id)
        REFERENCES user_roles(role_id)
);

INSERT INTO users (username, email, password, role_id)
SELECT
    'Admin',
    'Admin@mail.com',
    'password',   
    r.role_id
FROM user_roles r
WHERE r.role_name = 'Admin';

INSERT INTO users (username, email, password)
VALUES (
    'JohnDoe',
    'JohnDoe@mail.com',
    'password1'   
);

SELECT * FROM users;

-- Table to hold user roles ( Admin, Normal )
CREATE TABLE user_roles (
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL
);

INSERT INTO user_roles (role_name) VALUES -- it was having a dup problem >:/
('Admin'),
('Mod'),
('Normal User');

SELECT * FROM user_roles;

-- Table for user roles
CREATE TABLE user_roles (
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    PRIMARY KEY(user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (role_id) REFERENCES roles(role_id)
);

-- Table to hold the Profile
CREATE TABLE user_profiles (
    profile_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,

    display_name VARCHAR(100) NOT NULL,
    role_id INT NOT NULL,  

    bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_profile_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_profile_role
        FOREIGN KEY (role_id)
        REFERENCES user_roles(role_id)
);

INSERT INTO user_profiles (user_id, display_name, role_id)
SELECT
    u.user_id,
    u.username AS display_name,
    u.role_id
FROM users u
WHERE u.username = 'Admin';

UPDATE user_profiles
SET bio = 'This is an admin account!'
WHERE user_id = 1;

INSERT INTO user_profiles (user_id, display_name, role_id, bio)
SELECT
    u.user_id,
    u.username AS display_name,
    u.role_id,
    'This is a test account!'
FROM users u
WHERE u.username = 'JohnDoe';

SELECT * FROM user_profiles;

-- Table to hold the sessions
CREATE TABLE sessions (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logout_time TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- -------------------------------------
-- POKEMON TABLES
-- -------------------------------------

-- main pokemon table
CREATE TABLE pokemon (
    pokemon_id INT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    generation INT,
    species VARCHAR(50),
    height DOUBLE,
    weight DOUBLE,
    base_exp INT,
    catch_rate INT,
    base_friendship INT,
    egg_cycles INT,
    growth_rate_id INT,
    special_group_id INT,
    FOREIGN KEY (growth_rate_id) REFERENCES growth_rates(growth_rate_id),
    FOREIGN KEY (special_group_id) REFERENCES special_groups(special_group_id)
);
    
INSERT INTO pokemon (
    pokemon_id, name, generation, species, height, weight,
    base_exp, catch_rate, base_friendship, egg_cycles,
    growth_rate_id, special_group_id
)
SELECT
    CAST(dexnum AS UNSIGNED),
    name,
    CAST(generation AS UNSIGNED),
    species,
    CAST(height AS DECIMAL(3,1)),
    CAST(weight AS DECIMAL(5,1)),
    CAST(base_exp AS UNSIGNED),
    CAST(catch_rate AS UNSIGNED),
    CAST(base_friendship AS UNSIGNED),
    CAST(egg_cycles AS UNSIGNED),
    gr.growth_rate_id,
    sg.special_group_id
FROM pokemon_data_staging pds
LEFT JOIN growth_rates gr ON pds.growth_rate = gr.growth_rate_name
LEFT JOIN special_groups sg ON pds.special_group = sg.special_group_name
ON DUPLICATE KEY UPDATE name = pds.name;

SELECT * FROM pokemon;

-- Table to store core stats and EV yields
CREATE TABLE pokemon_stats (
    pokemon_id INT PRIMARY KEY,
    hp INT,
    attack INT,
    defense INT,
    sp_atk INT,
    sp_def INT,
    speed INT,
    total INT,
    ev_yield VARCHAR(50),
    FOREIGN KEY(pokemon_id) REFERENCES pokemon(pokemon_id)
);

INSERT INTO pokemon_stats (
    pokemon_id, hp, attack, defense, sp_atk, sp_def, speed, total, ev_yield
)
SELECT
    CAST(dexnum AS UNSIGNED),
    CAST(hp AS UNSIGNED),
    CAST(attack AS UNSIGNED),
    CAST(defense AS UNSIGNED),
    CAST(sp_atk AS UNSIGNED),
    CAST(sp_def AS UNSIGNED),
    CAST(speed AS UNSIGNED),
    CAST(total AS UNSIGNED),
    ev_yield
FROM pokemon_data_staging;

SELECT * FROM pokemon_stats;

-- Table for pokemon types
CREATE TABLE types (
    type_id INT AUTO_INCREMENT PRIMARY KEY,
    type_name VARCHAR(50) UNIQUE NOT NULL
);

INSERT INTO types (type_name)
SELECT DISTINCT type1
FROM pokemon_data_staging
WHERE type1 <> '' AND type1 IS NOT NULL
UNION
SELECT DISTINCT type2
FROM pokemon_data_staging
WHERE type2 <> '' AND type2 IS NOT NULL;

SELECT * FROM types;

-- Table for POKEMON'S types
-- uses the type ID from above to have two slots
-- SLOT 1 = first type
-- SLOT 2 = second type, IF there is one
CREATE TABLE pokemon_types (
    pokemon_id INT NOT NULL,
    slot1_type INT NOT NULL,
    slot2_type INT DEFAULT NULL,
    PRIMARY KEY (pokemon_id),
    FOREIGN KEY (pokemon_id) REFERENCES pokemon(pokemon_id),
    FOREIGN KEY (slot1_type) REFERENCES types(type_id),
    FOREIGN KEY (slot2_type) REFERENCES types(type_id)
);

INSERT INTO pokemon_types (pokemon_id, slot1_type, slot2_type)
SELECT
    CAST(p.dexnum AS UNSIGNED) AS pokemon_id,
    t1.type_id AS slot1_type,
    t2.type_id AS slot2_type
FROM pokemon_data_staging p
-- Join for the first type
JOIN types t1 ON p.type1 = t1.type_name
-- Left join for the second type (may be NULL)
LEFT JOIN types t2 ON p.type2 = t2.type_name;


SELECT * FROM pokemon_types;

-- Table for the pokemon abilities
CREATE TABLE abilities (
    ability_id INT AUTO_INCREMENT PRIMARY KEY,
    ability_name VARCHAR(100) UNIQUE NOT NULL
);

SELECT * FROM abilities;

INSERT INTO abilities (ability_name)
SELECT DISTINCT ability1
FROM pokemon_data_staging
WHERE ability1 <> '' AND ability1 IS NOT NULL
UNION
SELECT DISTINCT ability2
FROM pokemon_data_staging
WHERE ability2 <> '' AND ability2 IS NOT NULL
UNION
SELECT DISTINCT hidden_ability
FROM pokemon_data_staging
WHERE hidden_ability <> '' AND hidden_ability IS NOT NULL;

CREATE TABLE pokemon_abilities (
    pokemon_id INT PRIMARY KEY,
    ability1_id INT NOT NULL,
    ability2_id INT,
    hidden_ability_id INT,
    FOREIGN KEY (pokemon_id) REFERENCES pokemon(pokemon_id),
    FOREIGN KEY (ability1_id) REFERENCES abilities(ability_id),
    FOREIGN KEY (ability2_id) REFERENCES abilities(ability_id),
    FOREIGN KEY (hidden_ability_id) REFERENCES abilities(ability_id)
);

INSERT INTO pokemon_abilities (pokemon_id, ability1_id, ability2_id, hidden_ability_id)
SELECT
    CAST(p.dexnum AS UNSIGNED),
    a1.ability_id,
    a2.ability_id,
    ah.ability_id
FROM pokemon_data_staging p
LEFT JOIN abilities a1 ON TRIM(p.ability1) = a1.ability_name
LEFT JOIN abilities a2 ON TRIM(p.ability2) = a2.ability_name
LEFT JOIN abilities ah ON TRIM(p.hidden_ability) = ah.ability_name;

SELECT * FROM pokemon_abilities;
-- Table for Egg Groups
CREATE TABLE egg_groups (
    egg_group_id INT AUTO_INCREMENT PRIMARY KEY,
    egg_group_name VARCHAR(50) UNIQUE NOT NULL
);

INSERT INTO egg_groups (egg_group_name) VALUES -- it was having a dup problem >:/
('Amorphous'),
('Bug'),
('Ditto'),
('Dragon'),
('Fairy'),
('Field'),
('Flying'),
('Grass'),
('Human-Like'),
('Mineral'),
('Monster'),
('Undiscovered'),
('Water 1'),
('Water 2'),
('Water 3');

SELECT * FROM egg_groups;

-- Table for POKEMON's egg group
CREATE TABLE pokemon_egg_groups (
    pokemon_id INT PRIMARY KEY,
    egg_group1_id INT NOT NULL,
    egg_group2_id INT NULL,
    FOREIGN KEY (pokemon_id) REFERENCES pokemon(pokemon_id),
    FOREIGN KEY (egg_group1_id) REFERENCES egg_groups(egg_group_id),
    FOREIGN KEY (egg_group2_id) REFERENCES egg_groups(egg_group_id)
);

INSERT INTO pokemon_egg_groups (pokemon_id, egg_group1_id, egg_group2_id)
SELECT
    CAST(p.dexnum AS UNSIGNED) AS pokemon_id,
    eg1.egg_group_id,
    eg2.egg_group_id
FROM pokemon_data_staging p
JOIN egg_groups eg1 ON p.egg_group1 = eg1.egg_group_name
LEFT JOIN egg_groups eg2 ON p.egg_group2 = eg2.egg_group_name;

SELECT * FROM pokemon_egg_groups;

-- Table for Growth Rates
CREATE TABLE growth_rates (
    growth_rate_id INT AUTO_INCREMENT PRIMARY KEY,
    growth_rate_name VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO growth_rates (growth_rate_name)
SELECT DISTINCT growth_rate
FROM pokemon_data_staging
WHERE growth_rate <> '' AND growth_rate IS NOT NULL;

SELECT * FROM growth_rates;


-- table for the special group (aka legendary and etc)
CREATE TABLE special_groups (
    special_group_id INT AUTO_INCREMENT PRIMARY KEY,
    special_group_name VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO special_groups (special_group_name)
SELECT DISTINCT special_group
FROM pokemon_data_staging
WHERE special_group IS NOT NULL AND special_group <> ''
ON DUPLICATE KEY UPDATE special_group_name = special_group_name;

SELECT * FROM special_groups;

-- -------------------------------------
-- LEADERBOARADS
-- -------------------------------------

CREATE TABLE game_modes (
    mode_id INT AUTO_INCREMENT PRIMARY KEY,
    mode_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

INSERT INTO game_modes (mode_name, description) VALUES
('guess_stats', 'Identify a Pokémon from its stats'),
('guess_weight', 'Choose which Pokémon weighs more'),
('guess_dexnum', 'Guess the Pokémon based on its Pokédex number'),
('guess_ability', 'Guess a Pokémon that has the shown ability'),
('guess_egg_group', 'Guess whether two Pokémon share an egg group'),
('guess_type', 'Guess a Pokémon that matches the given type'),
('guess_species', 'Guess a Pokémon that matches the given species');

SELECT * FROM game_modes;

CREATE TABLE leaderboard_general (
    entry_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    mode_id INT NOT NULL,
    score INT NOT NULL,
    correct INT DEFAULT 0,
    incorrect INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (mode_id) REFERENCES game_modes(mode_id)
);

CREATE TABLE leaderboard_guess_stats (
    stats_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    pokemon_id INT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    score INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (pokemon_id) REFERENCES pokemon(pokemon_id)
);


CREATE TABLE leaderboard_guess_weight (
    weight_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    pokemon1_id INT NOT NULL,
    pokemon2_id INT NOT NULL,
    user_choice_id INT NOT NULL,
    correct_pokemon_id INT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    score INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (pokemon1_id) REFERENCES pokemon(pokemon_id),
    FOREIGN KEY (pokemon2_id) REFERENCES pokemon(pokemon_id),
    FOREIGN KEY (user_choice_id) REFERENCES pokemon(pokemon_id),
    FOREIGN KEY (correct_pokemon_id) REFERENCES pokemon(pokemon_id)
);




-- TO DO LIST [ HAVE 17, 26. SO NEED 9 BULLET POINTS ]
-- 1. Leaderboard for Guessing a pokemon from it's dex number
CREATE TABLE leaderboard_guess_dexnum (
    guess_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    shown_dex INT NOT NULL,             
    user_choice_id INT NOT NULL,    
    correct_pokemon_id INT NOT NULL,    
    is_correct BOOLEAN NOT NULL,
    score INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (user_choice_id) REFERENCES pokemon(pokemon_id),
    FOREIGN KEY (correct_pokemon_id) REFERENCES pokemon(pokemon_id)
);

-- 2. Leaderboard for Guessing a pokemon who corresponds to an ability
CREATE TABLE leaderboard_guess_ability (
    ability_guess_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    ability_id INT NOT NULL,
    guessed_pokemon_id INT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    score INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(ability_id) REFERENCES abilities(ability_id),
    FOREIGN KEY(guessed_pokemon_id) REFERENCES pokemon(pokemon_id)
);

-- 3. Leaderboard for Guessing if two pokemon share the same egg groups
CREATE TABLE leaderboard_guess_egg_group (
    egg_guess_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    pokemon1_id INT NOT NULL,
    pokemon2_id INT NOT NULL,
    share_egg_group BOOLEAN NOT NULL,    
    user_answer BOOLEAN NOT NULL,        
    is_correct BOOLEAN NOT NULL,
    score INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(pokemon1_id) REFERENCES pokemon(pokemon_id),
    FOREIGN KEY(pokemon2_id) REFERENCES pokemon(pokemon_id)
);

-- 4. Table to store Pokemon and how many people favorite them, POKEMON ID, NUMBER OF FAVORITES
CREATE TABLE pokemon_favorites_count (
    pokemon_id INT PRIMARY KEY,
    favorite_count INT NOT NULL DEFAULT 0,

    FOREIGN KEY(pokemon_id) REFERENCES pokemon(pokemon_id)
);

SELECT * FROM pokemon_favorites_count;

-- 5. Table to store user's favorite pokemon, USER ID, POKEMON ID
CREATE TABLE user_favorite_pokemon (
    user_id BIGINT NOT NULL,
    pokemon_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, pokemon_id),

    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(pokemon_id) REFERENCES pokemon(pokemon_id)
);

-- 6. Table to allow users to create comments on pokemon: USER ID, COMMENT ID, POKEMON ID, COMMENT 
CREATE TABLE pokemon_comments (
    comment_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    pokemon_id INT NOT NULL,
    comment VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(pokemon_id) REFERENCES pokemon(pokemon_id)
);

INSERT INTO pokemon_comments (user_id, pokemon_id, comment)
VALUES (4, 25, 'I love pikachu!!!');

SELECT * FROM pokemon_comments;

-- 7. Leaderboard for Guessing a pokemon who corresponds to a random type
		-- Have it look for a random pokemon, grab it's type, then accept any other pokemon that have that typing
CREATE TABLE leaderboard_guess_type (
    type_guess_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    type1_id INT NOT NULL,
    type2_id INT,
    guessed_pokemon_id INT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    score INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(type1_id) REFERENCES types(type_id),
    FOREIGN KEY(type2_id) REFERENCES types(type_id),
    FOREIGN KEY(guessed_pokemon_id) REFERENCES pokemon(pokemon_id)
);
	
-- 8. Leaderboard for guessing a pokemon based on the species given.
		-- Have it look for a random pokemon, grab it's species, then accept any other pokemon with the species
	CREATE TABLE leaderboard_guess_species (
    species_guess_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    given_species VARCHAR(50) NOT NULL,
    guessed_pokemon_id INT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    score INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(guessed_pokemon_id) REFERENCES pokemon(pokemon_id)
);
        
-- 9.Table to store feedback given from users: FEEDBACK ID, USER ID, FEEDBACK, TIME CREATED
CREATE TABLE user_feedback (
    feedback_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    feedback VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

INSERT INTO user_feedback (user_id, feedback)
VALUES (4, 'I love PIKACHU!!!!!');