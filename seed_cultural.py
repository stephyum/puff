"""
Generates culturally diverse baking recipes using Claude and seeds them into recipes.db.
Usage: python seed_cultural.py
"""
import json, os, sqlite3, textwrap, time

_env = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env):
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

import anthropic

DB_PATH   = os.path.join(os.path.dirname(__file__), "recipes.db")
ai_client = anthropic.Anthropic()

CULTURAL_RECIPES = [
    # France
    ("French Madeleines",          "French"),
    ("Tarte Tatin",                "French"),
    ("Crème Brûlée",              "French"),
    ("Financiers",                 "French"),
    # Italy
    ("Tiramisu",                   "Italian"),
    ("Biscotti",                   "Italian"),
    ("Panna Cotta",                "Italian"),
    # Japan
    ("Japanese Cheesecake",        "Japanese"),
    ("Matcha Roll Cake",           "Japanese"),
    ("Dorayaki",                   "Japanese"),
    # Middle East
    ("Baklava",                    "Middle Eastern"),
    ("Basbousa",                   "Middle Eastern"),
    ("Ma'amoul",                   "Middle Eastern"),
    # Germany
    ("Black Forest Cake",          "German"),
    ("Apfelstrudel",               "German"),
    ("Berliner Doughnuts",         "German"),
    # Mexico
    ("Tres Leches Cake",           "Mexican"),
    ("Conchas",                    "Mexican"),
    ("Churros",                    "Mexican"),
    # UK & Ireland
    ("Victoria Sponge",            "British"),
    ("Sticky Toffee Pudding",      "British"),
    ("Welsh Cakes",                "British"),
    # Sweden & Scandinavia
    ("Swedish Kanelbullar",        "Scandinavian"),
    ("Norwegian Skillingsboller",  "Scandinavian"),
    # China
    ("Hong Kong Egg Tarts",        "Chinese"),
    ("Pineapple Buns",             "Chinese"),
    # Korea
    ("Hotteok",                    "Korean"),
    # Brazil
    ("Pão de Queijo",              "Brazilian"),
    ("Brigadeiro Cake",            "Brazilian"),
    # India
    ("Gulab Jamun",                "Indian"),
    ("Mysore Pak",                 "Indian"),
    # Morocco
    ("Moroccan Sellou",            "Moroccan"),
    ("Briouat",                    "Moroccan"),
    # Greece
    ("Baklava Cheesecake",         "Greek"),
    ("Melomakarona",               "Greek"),
]

PROMPT = textwrap.dedent("""
You are a professional baker with expertise in world cuisines. Generate an authentic {origin} baking recipe for: {name}.

Return a single JSON object (no markdown, no explanation) with this exact structure:
{{
  "name": "{name}",
  "category": "{origin} Baking",
  "description": "<1–2 sentence enticing description that mentions the cultural origin>",
  "calories": <integer per serving>,
  "servings": <integer>,
  "prep_time": <integer minutes>,
  "cook_time": <integer minutes>,
  "ingredients": [
    {{"us": "<amount unit ingredient>", "metric": "<amount unit ingredient>"}}
  ],
  "steps": ["<step 1 — temps as 350°F (175°C)>", "..."],
  "healthy_description": "<1 sentence — what makes the healthy version better>",
  "healthy_calories": <integer — must be lower than calories>,
  "healthy_ingredients": [
    {{
      "us": "<amount unit ingredient>",
      "metric": "<amount unit ingredient>",
      "swap": <true|false>,
      "swap_from_us": "<original — only if swap=true, else null>",
      "swap_from_metric": "<original — only if swap=true, else null>",
      "swap_reason": "<short phrase — only if swap=true, else null>"
    }}
  ],
  "healthy_steps": ["<step 1>", "..."],
  "healthy_benefits": ["<benefit 1>", "<benefit 2>", "<benefit 3>"],
  "health_score": <integer 1–10>
}}

Rules:
- Be authentic to the {origin} tradition.
- Temperatures always: NNN°F (NNN°C). Pan sizes: 9×5 inch / 8-inch / 9-inch etc.
- All ingredient lists must be complete and authentic.
- healthy_calories must be genuinely lower than calories.
- healthy_benefits: 3 specific, meaningful health points.
""").strip()

JSON_FIELDS = {"ingredients", "steps", "healthy_ingredients", "healthy_steps", "healthy_benefits"}
REQUIRED = ["name", "category", "description", "calories", "servings", "prep_time", "cook_time",
            "ingredients", "steps", "healthy_description", "healthy_calories",
            "healthy_ingredients", "healthy_steps", "healthy_benefits", "health_score"]

def insert_recipe(conn, r):
    if conn.execute("SELECT id FROM recipes WHERE name = ?", (r["name"],)).fetchone():
        print(f"  SKIP (exists): {r['name']}")
        return False
    conn.execute(
        """INSERT INTO recipes
           (name, category, description, calories, servings, prep_time, cook_time,
            ingredients, steps, healthy_description, healthy_calories,
            healthy_ingredients, healthy_steps, healthy_benefits, health_score)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(json.dumps(r[f]) if f in JSON_FIELDS else r[f] for f in REQUIRED)
    )
    print(f"  ADDED: {r['name']}")
    return True

def generate(name, origin, retries=3):
    prompt = PROMPT.format(name=name, origin=origin)
    for attempt in range(retries):
        try:
            msg = ai_client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = next(b.text for b in msg.content if b.type == "text").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as e:
            if attempt < retries - 1:
                wait = 30 * (attempt + 1)
                print(f"  Retry {attempt+1} for '{name}' in {wait}s ({e})")
                time.sleep(wait)
            else:
                raise

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # Ensure photo_url column exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(recipes)").fetchall()]
    if "photo_url" not in cols:
        conn.execute("ALTER TABLE recipes ADD COLUMN photo_url TEXT")
        conn.commit()

    total = 0
    for name, origin in CULTURAL_RECIPES:
        if conn.execute("SELECT id FROM recipes WHERE name = ?", (name,)).fetchone():
            print(f"  SKIP (exists): {name}")
            continue
        print(f"Generating: {name} [{origin}]…")
        try:
            r = generate(name, origin)
            if insert_recipe(conn, r):
                conn.commit()
                total += 1
            time.sleep(15)
        except Exception as e:
            print(f"  ERROR: {name}: {e}")

    conn.close()
    print(f"\nDone — {total} cultural recipes added.")

if __name__ == "__main__":
    main()
