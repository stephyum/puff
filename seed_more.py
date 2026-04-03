"""
Uses Claude to generate new baking recipes and seeds them into recipes.db.
Usage: python seed_more.py
"""
import json, os, sqlite3, textwrap, time

# Load .env
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

# We want to add recipes across these categories
BATCHES = [
    ("Cookies",        ["Snickerdoodle Cookies", "Peanut Butter Cookies", "Ginger Snaps", "Raspberry Thumbprint Cookies"]),
    ("Cakes",          ["Banana Cake", "Red Velvet Cake", "Coffee Walnut Cake", "Orange Olive Oil Cake"]),
    ("Muffins",        ["Chocolate Chip Muffins", "Bran Muffins", "Lemon Poppy Seed Muffins", "Pumpkin Muffins"]),
    ("Bread",          ["Cinnamon Swirl Bread", "Zucchini Bread", "Sourdough Focaccia", "Pumpkin Bread"]),
    ("Bars & Brownies",["Lemon Bars", "Peanut Butter Bars", "Blondies", "Flapjacks"]),
    ("Pies & Tarts",   ["Classic Apple Pie", "Lemon Tart", "Pecan Pie", "Strawberry Galette"]),
    ("Scones & Biscuits", ["Blueberry Scones", "Cheese Scones", "Classic Buttermilk Biscuits", "Cranberry Orange Scones"]),
    ("Cheesecakes",    ["Classic New York Cheesecake", "No-Bake Raspberry Cheesecake", "Mini Oreo Cheesecakes"]),
]

PROMPT_TEMPLATE = textwrap.dedent("""
You are a professional baker. Generate a baking recipe for: {name}.

Return a single JSON object (no markdown, no explanation) with this exact structure:
{{
  "name": "{name}",
  "category": "{category}",
  "description": "<1–2 sentence enticing description>",
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
- Temperatures always: NNN°F (NNN°C). Pan sizes: 9×5 inch / 8-inch / 9-inch etc.
- All ingredient lists must be complete.
- healthy_calories must be genuinely lower than calories.
- healthy_benefits: 3 specific, meaningful health points.
""").strip()

JSON_FIELDS = {"ingredients", "steps", "healthy_ingredients", "healthy_steps", "healthy_benefits"}
REQUIRED = ["name", "category", "description", "calories", "servings", "prep_time", "cook_time",
            "ingredients", "steps", "healthy_description", "healthy_calories",
            "healthy_ingredients", "healthy_steps", "healthy_benefits", "health_score"]

def insert_recipe(conn, r):
    # Skip duplicates
    if conn.execute("SELECT id FROM recipes WHERE name = ?", (r["name"],)).fetchone():
        print(f"  SKIP (exists): {r['name']}")
        return
    conn.execute(
        """INSERT INTO recipes
           (name, category, description, calories, servings, prep_time, cook_time,
            ingredients, steps, healthy_description, healthy_calories,
            healthy_ingredients, healthy_steps, healthy_benefits, health_score)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(json.dumps(r[f]) if f in JSON_FIELDS else r[f] for f in REQUIRED)
    )
    print(f"  ADDED: {r['name']}")

def generate_one(name, category, retries=3):
    prompt = PROMPT_TEMPLATE.format(name=name, category=category)
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
                print(f"  Retry {attempt+1}/{retries} for '{name}' in {wait}s: {e}")
                time.sleep(wait)
            else:
                raise

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    total_added = 0
    for category, names in BATCHES:
        for name in names:
            # Skip if already exists
            if conn.execute("SELECT id FROM recipes WHERE name = ?", (name,)).fetchone():
                print(f"  SKIP (exists): {name}")
                continue
            print(f"Generating: {name} [{category}]…")
            try:
                r = generate_one(name, category)
                insert_recipe(conn, r)
                conn.commit()
                total_added += 1
                time.sleep(15)  # stay under 8k tokens/min rate limit
            except Exception as e:
                print(f"  ERROR: {name}: {e}")

    conn.close()
    print(f"\nDone — {total_added} recipes added.")

if __name__ == "__main__":
    main()
