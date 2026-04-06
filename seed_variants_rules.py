"""
Generates vegan and gluten-free variants for all recipes using rule-based substitution.
No API calls — completely free to run.
Usage: python seed_variants_rules.py
"""
import json, os, re, sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "recipes.db")

# ── Substitution tables ────────────────────────────────────────────────────────

VEGAN_SUBS = [
    # dairy
    (r"\bbutter\b",               "vegan butter",          "plant-based alternative"),
    (r"\bunsalted butter\b",      "vegan butter",          "plant-based alternative"),
    (r"\bwhole milk\b",           "oat milk",              "dairy-free alternative"),
    (r"\bmilk\b",                 "oat milk",              "dairy-free alternative"),
    (r"\bbuttermilk\b",           "oat milk + 1 tbsp apple cider vinegar", "vegan buttermilk substitute"),
    (r"\bheavy cream\b",          "full-fat coconut cream","dairy-free alternative"),
    (r"\bwhipping cream\b",       "full-fat coconut cream","dairy-free alternative"),
    (r"\bcream cheese\b",         "vegan cream cheese",    "plant-based alternative"),
    (r"\bsour cream\b",           "coconut yogurt",        "dairy-free alternative"),
    (r"\byogurt\b",               "coconut yogurt",        "dairy-free alternative"),
    (r"\bcheddar cheese\b",       "vegan cheddar",         "plant-based alternative"),
    (r"\bparmesan\b",             "nutritional yeast",     "plant-based umami substitute"),
    (r"\bcheese\b",               "vegan cheese",          "plant-based alternative"),
    # eggs
    (r"\beggs?\b",                "flax eggs (1 tbsp ground flaxseed + 3 tbsp water per egg)", "vegan egg replacer"),
    (r"\begg yolks?\b",           "flax eggs",             "vegan egg replacer"),
    (r"\begg whites?\b",          "aquafaba (3 tbsp per egg white)", "vegan egg replacer"),
    # honey
    (r"\bhoney\b",                "maple syrup",           "vegan sweetener"),
    # gelatin
    (r"\bgelatin\b",              "agar-agar",             "plant-based gelling agent"),
]

GLUTEN_FREE_SUBS = [
    (r"\ball[- ]purpose flour\b", "gluten-free all-purpose flour blend", "certified GF flour"),
    (r"\bbread flour\b",          "gluten-free bread flour blend",       "certified GF flour"),
    (r"\bcake flour\b",           "gluten-free cake flour blend",        "certified GF flour"),
    (r"\bwhole[- ]wheat flour\b", "gluten-free oat flour",              "certified GF flour"),
    (r"\bself[- ]raising flour\b","gluten-free self-raising flour",      "certified GF flour"),
    (r"\bflour\b",                "gluten-free all-purpose flour blend", "certified GF flour"),
    (r"\brolled oats\b",          "certified gluten-free rolled oats",   "must be certified GF"),
    (r"\boats\b",                 "certified gluten-free oats",          "must be certified GF"),
    (r"\bbarley\b",               "certified GF buckwheat",              "gluten-free grain"),
    (r"\brye\b",                  "certified GF buckwheat flour",        "gluten-free alternative"),
    (r"\bregular soy sauce\b",    "tamari (GF soy sauce)",               "gluten-free soy sauce"),
    (r"\bsoy sauce\b",            "tamari (GF soy sauce)",               "gluten-free soy sauce"),
    (r"\bbaking powder\b",        "gluten-free baking powder",           "ensure GF certified"),
]

VEGAN_BENEFITS = [
    "100% plant-based — suitable for vegans and those avoiding animal products",
    "Lower in saturated fat compared to the original recipe",
    "Rich in plant-based nutrients and fiber",
]

GLUTEN_FREE_BENEFITS = [
    "Made with certified gluten-free ingredients — safe for celiac disease",
    "Uses wholesome alternative flours for a naturally lighter texture",
    "Great option for those with gluten sensitivity or wheat allergies",
]

# ── Core logic ─────────────────────────────────────────────────────────────────

def apply_subs(text, subs):
    """Apply substitution rules to a text string. Returns (new_text, swapped_bool, from, to, reason)."""
    result = text
    swap = False
    swap_from = None
    swap_reason = None
    for pattern, replacement, reason in subs:
        new = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        if new != result:
            if not swap:
                # capture first substitution for swap metadata
                swap_from = re.search(pattern, result, re.IGNORECASE).group(0)
                swap_reason = reason
            result = new
            swap = True
    return result, swap, swap_from, reason if swap else None

def make_ingredient(orig_ing, subs):
    us     = orig_ing.get("us", "")
    metric = orig_ing.get("metric", "")

    new_us, swap, from_us, reason = apply_subs(us, subs)
    new_metric, _, from_metric, _ = apply_subs(metric, subs)

    out = {
        "us":               new_us,
        "metric":           new_metric,
        "swap":             swap,
        "swap_from_us":     from_us if swap else None,
        "swap_from_metric": from_metric if swap else None,
        "swap_reason":      reason if swap else None,
    }
    return out

def make_steps(orig_steps, subs):
    new_steps = []
    for step in orig_steps:
        new_step, _, _, _ = apply_subs(step, subs)
        new_steps.append(new_step)
    return new_steps

def estimate_calorie_delta(ingredients, variant_type):
    """Rough calorie adjustment based on common swaps."""
    delta = 0
    if variant_type == "vegan":
        # coconut cream is higher cal than heavy cream; oat milk lower than whole milk
        for ing in ingredients:
            us = ing.get("us", "").lower()
            if "coconut cream" in us:
                delta += 20
            if "oat milk" in us:
                delta -= 10
    if variant_type == "gluten-free":
        # GF flours often similar; slight increase for blends
        delta += 5
    return delta

def build_variant(recipe, variant_type):
    subs = VEGAN_SUBS if variant_type == "vegan" else GLUTEN_FREE_SUBS
    label = "vegan" if variant_type == "vegan" else "gluten-free"
    benefits = VEGAN_BENEFITS if variant_type == "vegan" else GLUTEN_FREE_BENEFITS

    orig_ings  = recipe["ingredients"]
    orig_steps = recipe["steps"]

    new_ings  = [make_ingredient(i, subs) for i in orig_ings]
    new_steps = make_steps(orig_steps, subs)

    swapped = [i for i in new_ings if i["swap"]]
    if swapped:
        first_swap = swapped[0]
        swap_summary = first_swap["swap_from_us"] or ""
        swap_to = first_swap["us"] or ""
        description = (
            f"A {label} version of {recipe['name']} using plant-based swaps "
            f"such as {swap_to.split('(')[0].strip()} in place of {swap_summary}."
            if variant_type == "vegan" else
            f"A {label} version of {recipe['name']} made with certified gluten-free "
            f"ingredients, swapping {swap_summary} for {swap_to.split('(')[0].strip()}."
        )
    else:
        description = f"A {label} version of {recipe['name']} — naturally {label} with no substitutions needed."

    cal_delta = estimate_calorie_delta(new_ings, variant_type)
    calories  = max(50, recipe["calories"] + cal_delta)

    return {
        "description": description,
        "calories":    calories,
        "ingredients": new_ings,
        "steps":       new_steps,
        "benefits":    benefits,
    }

# ── Main ───────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def main():
    conn   = get_db()
    recipes = conn.execute("SELECT * FROM recipes ORDER BY id").fetchall()
    variant_types = ["vegan", "gluten-free"]
    total = len(recipes) * len(variant_types)
    done  = 0

    for row in recipes:
        r = dict(row)
        r["ingredients"] = json.loads(r["ingredients"])
        r["steps"]       = json.loads(r["steps"])

        for vtype in variant_types:
            existing = conn.execute(
                "SELECT id FROM recipe_variants WHERE recipe_id=? AND variant_type=?",
                (r["id"], vtype)
            ).fetchone()
            if existing:
                print(f"  SKIP: {r['name']} [{vtype}]")
                done += 1
                continue

            print(f"  [{done+1}/{total}] {r['name']} → {vtype}…", end=" ", flush=True)
            v = build_variant(r, vtype)
            conn.execute(
                """INSERT OR REPLACE INTO recipe_variants
                   (recipe_id, variant_type, description, calories, ingredients, steps, benefits)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (r["id"], vtype,
                 v["description"], v["calories"],
                 json.dumps(v["ingredients"]), json.dumps(v["steps"]),
                 json.dumps(v["benefits"]))
            )
            conn.commit()
            print("OK")
            done += 1

    conn.close()
    print(f"\nDone — {done}/{total} variants processed.")

if __name__ == "__main__":
    main()
