"""
Adds photo_url column to recipes table and fetches food photos from Pexels.
Usage: python fetch_photos.py
"""
import sqlite3, os, time
import urllib.request, urllib.parse, json

DB_PATH    = os.path.join(os.path.dirname(__file__), "recipes.db")
PEXELS_KEY = "rVpEyz4DY4gmq1SsBhx5UtGiaLXUjhGjOKjoFvLXclrXtvQGFQyLQe2h"

# Words that suggest process / raw shots — skip these photos
PROCESS_KEYWORDS = {"mixing", "batter", "dough", "raw", "process", "making",
                    "hands", "bowl", "spoon", "whisk", "flour", "ingredient"}

def pexels_search(query, used_ids):
    """Return a (photo_id, url) tuple for the best unused finished-product photo."""
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
        "query": query,
        "per_page": 15,
        "orientation": "landscape",
    })
    req = urllib.request.Request(url, headers={
        "Authorization": PEXELS_KEY,
        "User-Agent": "Mozilla/5.0",
    })
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    for photo in data.get("photos", []):
        pid = photo["id"]
        if pid in used_ids:
            continue
        # Check alt text for process words
        alt = (photo.get("alt") or "").lower()
        if any(kw in alt for kw in PROCESS_KEYWORDS):
            continue
        return pid, photo["src"]["large"]
    return None, None

# Per-recipe search queries — more specific terms to get finished-product shots
RECIPE_QUERIES = {
    "Chocolate Chip Cookies":      "chocolate chip cookies plate",
    "Oatmeal Raisin Cookies":      "oatmeal raisin cookies",
    "Shortbread Cookies":          "shortbread cookies stack",
    "Snickerdoodle Cookies":       "snickerdoodle cookies",
    "Peanut Butter Cookies":       "peanut butter cookies",
    "Ginger Snaps":                "ginger snap cookies",
    "Raspberry Thumbprint Cookies":"thumbprint cookies jam",
    "Carrot Cake":                 "carrot cake slice",
    "Lemon Drizzle Cake":          "lemon drizzle cake",
    "Classic Chocolate Cake":      "chocolate layer cake slice",
    "Banana Cake":                 "banana cake dessert",
    "Red Velvet Cake":             "red velvet cake slice",
    "Coffee Walnut Cake":          "coffee walnut cake",
    "Orange Olive Oil Cake":       "orange cake dessert",
    "Banana Bread":                "banana bread loaf sliced",
    "Classic White Bread":         "white bread loaf",
    "Cinnamon Swirl Bread":        "cinnamon swirl bread sliced",
    "Zucchini Bread":              "zucchini bread loaf",
    "Sourdough Focaccia":          "focaccia bread topped",
    "Pumpkin Bread":               "pumpkin bread loaf sliced",
    "Blueberry Muffins":           "blueberry muffins basket",
    "Corn Muffins":                "corn muffins golden",
    "Chocolate Chip Muffins":      "chocolate chip muffins",
    "Bran Muffins":                "bran muffins healthy",
    "Lemon Poppy Seed Muffins":    "lemon poppy seed muffins",
    "Pumpkin Muffins":             "pumpkin muffins spiced",
    "Chocolate Brownies":          "chocolate brownies fudge",
    "Granola Bars":                "granola bars homemade",
    "Lemon Bars":                  "lemon bars powdered sugar",
    "Peanut Butter Bars":          "peanut butter bars dessert",
    "Blondies":                    "blondies bars butterscotch",
    "Flapjacks":                   "flapjacks oat bars",
    "Classic New York Cheesecake": "new york cheesecake slice",
    "No-Bake Raspberry Cheesecake":"raspberry cheesecake dessert",
    "Mini Oreo Cheesecakes":       "mini cheesecakes oreo",
    "Classic Apple Pie":           "apple pie slice",
    "Lemon Tart":                  "lemon tart dessert",
    "Pecan Pie":                   "pecan pie slice",
    "Strawberry Galette":          "strawberry galette tart",
    "Blueberry Scones":            "blueberry scones cream",
    "Cheese Scones":               "cheese scones golden",
    "Classic Buttermilk Biscuits": "buttermilk biscuits flaky",
    "Cranberry Orange Scones":     "cranberry orange scones",
    # French
    "French Madeleines":           "french madeleines cookies",
    "Tarte Tatin":                 "tarte tatin caramelized apple",
    "Crème Brûlée":               "creme brulee dessert caramelized",
    "Financiers":                  "french financiers almond cakes",
    "Canelés":                     "caneles bordeaux pastry",
    "Paris-Brest":                 "paris brest choux pastry",
    # Italian
    "Tiramisu":                    "tiramisu dessert slice",
    "Biscotti":                    "biscotti italian cookies",
    "Panna Cotta":                 "panna cotta dessert",
    "Cannoli":                     "cannoli italian pastry",
    # Japanese
    "Japanese Cheesecake":         "japanese cheesecake fluffy",
    "Matcha Roll Cake":            "matcha roll cake green tea",
    "Dorayaki":                    "dorayaki japanese pancake",
    "Mochi":                       "mochi japanese rice cake",
    "Taiyaki":                     "taiyaki fish shaped waffle",
    # Middle Eastern
    "Baklava":                     "baklava honey pastry",
    "Basbousa":                    "basbousa semolina cake",
    "Ma'amoul":                    "maamoul date cookies",
    "Knafeh":                      "knafeh cheese pastry",
    # German
    "Black Forest Cake":           "black forest cake slice",
    "Apfelstrudel":                "apple strudel slice",
    "Berliner Doughnuts":          "berliner doughnuts jam filled",
    "Bienenstich":                 "bienenstich bee sting cake",
    # Mexican
    "Tres Leches Cake":            "tres leches cake slice",
    "Conchas":                     "conchas mexican sweet bread",
    "Churros":                     "churros cinnamon sugar",
    "Pan Dulce":                   "pan dulce mexican pastry",
    # British
    "Victoria Sponge":             "victoria sponge cake",
    "Sticky Toffee Pudding":       "sticky toffee pudding dessert",
    "Welsh Cakes":                 "welsh cakes griddle",
    "Eton Mess":                   "eton mess dessert",
    # Scandinavian
    "Swedish Kanelbullar":         "kanelbullar cinnamon buns swedish",
    "Norwegian Skillingsboller":   "skillingsboller norwegian cinnamon bun",
    "Kladdkaka":                   "kladdkaka swedish sticky chocolate cake",
    # Chinese
    "Hong Kong Egg Tarts":         "hong kong egg tarts",
    "Pineapple Buns":              "pineapple buns chinese bakery",
    "Wife Cake":                   "wife cake chinese pastry",
    # Korean
    "Hotteok":                     "hotteok korean sweet pancake",
    "Bingsu":                      "bingsu korean shaved ice dessert",
    # Brazilian
    "Pão de Queijo":               "pao de queijo cheese bread",
    "Brigadeiro Cake":             "brigadeiro cake chocolate brazilian",
    "Bolo de Rolo":                "bolo de rolo roll cake",
    # Indian
    "Gulab Jamun":                 "gulab jamun syrup dessert",
    "Mysore Pak":                  "mysore pak indian sweet",
    "Nankhatai":                   "nankhatai indian shortbread cookies",
    # Moroccan
    "Moroccan Sellou":             "sellou moroccan sweet",
    "Briouat":                     "briouat moroccan pastry",
    "Chebakia":                    "chebakia moroccan sesame cookies",
    # Greek
    "Baklava Cheesecake":          "baklava cheesecake dessert",
    "Melomakarona":                "melomakarona greek christmas cookies",
    "Galaktoboureko":              "galaktoboureko greek custard pastry",
}

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Add column if needed
    cols = [r[1] for r in conn.execute("PRAGMA table_info(recipes)").fetchall()]
    if "photo_url" not in cols:
        conn.execute("ALTER TABLE recipes ADD COLUMN photo_url TEXT")
        conn.commit()

    # Collect already-used Pexels photo IDs to avoid duplicates
    # (we can't recover the ID from the URL, so just skip recipes that already have photos)
    rows = conn.execute("SELECT id, name, category FROM recipes ORDER BY id").fetchall()
    used_ids = set()
    updated  = 0

    for row in rows:
        name  = row["name"]
        query = RECIPE_QUERIES.get(name, name + " finished baked")
        print(f"  {name}…", end=" ", flush=True)
        try:
            pid, url = pexels_search(query, used_ids)
            if not pid:
                # fallback: broaden to category
                pid, url = pexels_search(row["category"] + " baked dessert", used_ids)
            if pid and url:
                used_ids.add(pid)
                conn.execute("UPDATE recipes SET photo_url = ? WHERE id = ?", (url, row["id"]))
                conn.commit()
                print("OK")
                updated += 1
            else:
                print("no unique result")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.25)

    conn.close()
    print(f"\nDone — {updated}/{len(rows)} recipes have unique photos.")

if __name__ == "__main__":
    main()
