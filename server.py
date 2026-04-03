"""
Flask REST API for the Puff healthy baking website.
Usage: python server.py
Runs on http://localhost:8080
"""
import json, os, sqlite3, textwrap, secrets
import anthropic
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, jsonify, request, abort, send_from_directory, session
from flask_cors import CORS

# Load .env file if present
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

BASE_DIR = os.path.dirname(__file__)
DB_PATH  = os.path.join(BASE_DIR, "recipes.db")

app = Flask(__name__, static_folder=BASE_DIR)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
CORS(app, supports_credentials=True)

ai_client = anthropic.Anthropic()


# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recipe_variants (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id    INTEGER NOT NULL,
            variant_type TEXT    NOT NULL,
            description  TEXT    NOT NULL,
            calories     INTEGER NOT NULL,
            ingredients  TEXT    NOT NULL,
            steps        TEXT    NOT NULL,
            benefits     TEXT    NOT NULL,
            created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(recipe_id, variant_type)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id  INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            rating     INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment    TEXT,
            created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(recipe_id, user_id),
            FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id)   REFERENCES users(id)   ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def row_to_dict(row):
    d = dict(row)
    for key in ("ingredients", "steps", "healthy_ingredients", "healthy_steps", "healthy_benefits"):
        if key in d:
            d[key] = json.loads(d[key])
    return d


def variant_row_to_dict(row):
    d = dict(row)
    for key in ("ingredients", "steps", "benefits"):
        d[key] = json.loads(d[key])
    return d


def attach_variants(recipe_dict, conn):
    rows = conn.execute(
        "SELECT * FROM recipe_variants WHERE recipe_id = ?", (recipe_dict["id"],)
    ).fetchall()
    recipe_dict["variants"] = {r["variant_type"]: variant_row_to_dict(r) for r in rows}
    return recipe_dict


def attach_review_summary(recipe_dict, conn):
    row = conn.execute(
        "SELECT COUNT(*) as count, AVG(rating) as avg FROM reviews WHERE recipe_id = ?",
        (recipe_dict["id"],)
    ).fetchone()
    recipe_dict["review_count"] = row["count"]
    recipe_dict["avg_rating"]   = round(row["avg"], 1) if row["avg"] else None
    return recipe_dict


def current_user_id():
    return session.get("user_id")


def require_auth():
    if not current_user_id():
        abort(401, "Login required")


# ── Static files ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        abort(400, "username, email and password are required")
    if len(username) < 2:
        abort(400, "Username must be at least 2 characters")
    if "@" not in email:
        abort(400, "Invalid email address")
    if len(password) < 6:
        abort(400, "Password must be at least 6 characters")

    conn = get_db()
    if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        abort(409, "Email already registered")
    if conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
        conn.close()
        abort(409, "Username already taken")

    pw_hash = generate_password_hash(password)
    cur = conn.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, pw_hash)
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()

    session["user_id"]  = user_id
    session["username"] = username
    return jsonify({"id": user_id, "username": username, "email": email}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json(force=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        abort(400, "email and password are required")

    conn = get_db()
    row  = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        abort(401, "Invalid email or password")

    session["user_id"]  = row["id"]
    session["username"] = row["username"]
    return jsonify({"id": row["id"], "username": row["username"], "email": row["email"]})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def me():
    uid = current_user_id()
    if not uid:
        return jsonify(None)
    conn = get_db()
    row  = conn.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return jsonify(dict(row) if row else None)


# ── Reviews ────────────────────────────────────────────────────────────────────

@app.route("/api/recipes/<int:recipe_id>/reviews")
def get_reviews(recipe_id):
    conn  = get_db()
    rows  = conn.execute(
        """SELECT r.id, r.rating, r.comment, r.created_at,
                  u.username
           FROM reviews r
           JOIN users u ON u.id = r.user_id
           WHERE r.recipe_id = ?
           ORDER BY r.created_at DESC""",
        (recipe_id,)
    ).fetchall()
    # Also return the current user's review id so the UI can show edit/delete
    my_row = None
    uid = current_user_id()
    if uid:
        my_row = conn.execute(
            "SELECT id FROM reviews WHERE recipe_id = ? AND user_id = ?",
            (recipe_id, uid)
        ).fetchone()
    conn.close()
    return jsonify({
        "reviews":      [dict(r) for r in rows],
        "my_review_id": my_row["id"] if my_row else None,
    })


@app.route("/api/recipes/<int:recipe_id>/reviews", methods=["POST"])
def create_or_update_review(recipe_id):
    require_auth()
    data    = request.get_json(force=True) or {}
    rating  = data.get("rating")
    comment = (data.get("comment") or "").strip()

    if rating is None or not isinstance(rating, int) or not (1 <= rating <= 5):
        abort(400, "rating must be an integer 1–5")

    uid  = current_user_id()
    conn = get_db()
    conn.execute(
        """INSERT INTO reviews (recipe_id, user_id, rating, comment)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(recipe_id, user_id) DO UPDATE SET
             rating = excluded.rating,
             comment = excluded.comment,
             created_at = CURRENT_TIMESTAMP""",
        (recipe_id, uid, rating, comment or None)
    )
    conn.commit()
    row = conn.execute(
        """SELECT r.id, r.rating, r.comment, r.created_at, u.username
           FROM reviews r JOIN users u ON u.id = r.user_id
           WHERE r.recipe_id = ? AND r.user_id = ?""",
        (recipe_id, uid)
    ).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@app.route("/api/reviews/<int:review_id>", methods=["DELETE"])
def delete_review(review_id):
    require_auth()
    uid  = current_user_id()
    conn = get_db()
    row  = conn.execute("SELECT user_id FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not row:
        conn.close()
        abort(404, "Review not found")
    if row["user_id"] != uid:
        conn.close()
        abort(403, "Not your review")
    conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": review_id})


# ── GET /api/recipes ───────────────────────────────────────────────────────────

@app.route("/api/recipes")
def get_recipes():
    q        = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    sort     = request.args.get("sort", "name")
    order    = request.args.get("order", "asc").upper()

    allowed_sorts = {"name", "calories", "health_score", "prep_time", "cook_time"}
    if sort not in allowed_sorts:
        abort(400, f"Invalid sort. Allowed: {', '.join(allowed_sorts)}")
    if order not in ("ASC", "DESC"):
        abort(400, "order must be 'asc' or 'desc'")

    where_clauses, params = [], []
    if q:
        where_clauses.append("(name LIKE ? OR description LIKE ? OR healthy_description LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like]
    if category and category.lower() != "all":
        where_clauses.append("category = ?")
        params.append(category)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM recipes {where_sql} ORDER BY {sort} {order}", params
    ).fetchall()
    result = [attach_review_summary(attach_variants(row_to_dict(r), conn), conn) for r in rows]
    conn.close()
    return jsonify(result)


# ── GET /api/recipes/categories ───────────────────────────────────────────────

@app.route("/api/recipes/categories")
def get_categories():
    conn = get_db()
    rows = conn.execute(
        "SELECT category, COUNT(*) as count FROM recipes GROUP BY category ORDER BY category"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ── GET /api/recipes/<id> ──────────────────────────────────────────────────────

@app.route("/api/recipes/<int:recipe_id>")
def get_recipe(recipe_id):
    conn = get_db()
    row  = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if row is None:
        conn.close()
        abort(404, "Recipe not found")
    result = attach_review_summary(attach_variants(row_to_dict(row), conn), conn)
    conn.close()
    return jsonify(result)


# ── POST /api/recipes/<id>/adapt ──────────────────────────────────────────────

VARIANT_LABELS = {
    "healthy":     "healthier",
    "vegan":       "vegan",
    "gluten-free": "gluten-free",
}

def build_adapt_prompt(recipe, variant_type):
    label = VARIANT_LABELS[variant_type]
    ing_list   = "\n".join(f"  - {i.get('us', i.get('metric', ''))}" for i in recipe["ingredients"])
    steps_list = "\n".join(f"  {n+1}. {s}" for n, s in enumerate(recipe["steps"]))
    return textwrap.dedent(f"""
        You are a professional baker and nutritionist. Adapt the following recipe into a {label} version.

        ORIGINAL RECIPE: {recipe['name']}
        Category: {recipe['category']}
        Calories: {recipe['calories']} per serving  |  Servings: {recipe['servings']}

        Ingredients:
        {ing_list}

        Steps:
        {steps_list}

        Return ONLY a JSON object (no markdown, no explanation) with this exact structure:
        {{
          "description": "One sentence describing what makes this version {label}.",
          "calories": <integer — estimated calories per serving>,
          "benefits": ["benefit 1", "benefit 2", "benefit 3"],
          "ingredients": [
            {{
              "us":               "<amount + unit + ingredient in US measurements>",
              "metric":           "<amount + unit + ingredient in metric>",
              "swap":             <true if changed, false otherwise>,
              "swap_from_us":     "<original US — only when swap=true, else null>",
              "swap_from_metric": "<original metric — only when swap=true, else null>",
              "swap_reason":      "<short phrase — only when swap=true, else null>"
            }}
          ],
          "steps": ["<step 1 — temps as 350°F (175°C)>", ...]
        }}

        Rules:
        - Keep the same number of servings ({recipe['servings']}).
        - Temperatures: NNN°F (NNN°C). Pan sizes: 9×5 inch or 8-inch.
        - Include every ingredient; steps must be complete.
        {"- All ingredients must be plant-based (no meat, dairy, eggs, honey)." if variant_type == "vegan" else ""}
        {"- All ingredients must be gluten-free (no wheat, barley, rye)." if variant_type == "gluten-free" else ""}
        {"- Reduce calories, sugar, saturated fat; boost fibre and nutrients." if variant_type == "healthy" else ""}
    """).strip()


@app.route("/api/recipes/<int:recipe_id>/adapt", methods=["POST"])
def adapt_recipe(recipe_id):
    data         = request.get_json(force=True) or {}
    variant_type = (data.get("variant_type") or "").strip().lower()
    if variant_type not in VARIANT_LABELS:
        abort(400, f"variant_type must be one of: {', '.join(VARIANT_LABELS)}")

    conn = get_db()
    cached = conn.execute(
        "SELECT * FROM recipe_variants WHERE recipe_id = ? AND variant_type = ?",
        (recipe_id, variant_type)
    ).fetchone()
    if cached:
        conn.close()
        return jsonify(variant_row_to_dict(cached))

    row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if row is None:
        conn.close()
        abort(404, "Recipe not found")
    recipe = row_to_dict(row)

    prompt = build_adapt_prompt(recipe, variant_type)
    try:
        message = ai_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b.text for b in message.content if b.type == "text"]
        if not text_blocks:
            raise ValueError("No text block in Claude response")
        raw = text_blocks[0].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0].strip()
        variant = json.loads(raw)
    except Exception as e:
        conn.close()
        abort(500, f"AI adaptation failed: {e}")

    for field in ("description", "calories", "benefits", "ingredients", "steps"):
        if field not in variant:
            conn.close()
            abort(500, f"AI response missing field: {field}")

    try:
        conn.execute(
            """INSERT OR REPLACE INTO recipe_variants
               (recipe_id, variant_type, description, calories, ingredients, steps, benefits)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (recipe_id, variant_type, variant["description"], int(variant["calories"]),
             json.dumps(variant["ingredients"]), json.dumps(variant["steps"]),
             json.dumps(variant["benefits"]))
        )
        conn.commit()
        saved = conn.execute(
            "SELECT * FROM recipe_variants WHERE recipe_id = ? AND variant_type = ?",
            (recipe_id, variant_type)
        ).fetchone()
        conn.close()
        return jsonify(variant_row_to_dict(saved)), 201
    except Exception as e:
        conn.close()
        abort(500, f"Failed to save variant: {e}")


# ── POST /api/recipes ──────────────────────────────────────────────────────────

@app.route("/api/recipes", methods=["POST"])
def create_recipe():
    data = request.get_json(force=True)
    required = ["name", "category", "description", "calories", "servings",
                "prep_time", "cook_time", "ingredients", "steps",
                "healthy_description", "healthy_calories",
                "healthy_ingredients", "healthy_steps", "healthy_benefits", "health_score"]
    missing = [f for f in required if f not in data]
    if missing:
        abort(400, f"Missing fields: {', '.join(missing)}")
    json_fields = {"ingredients", "steps", "healthy_ingredients", "healthy_steps", "healthy_benefits"}
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO recipes
           (name, category, description, calories, servings, prep_time, cook_time,
            ingredients, steps, healthy_description, healthy_calories,
            healthy_ingredients, healthy_steps, healthy_benefits, health_score)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(json.dumps(data[f]) if f in json_fields else data[f] for f in required)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM recipes WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


# ── PUT /api/recipes/<id> ──────────────────────────────────────────────────────

@app.route("/api/recipes/<int:recipe_id>", methods=["PUT"])
def update_recipe(recipe_id):
    conn = get_db()
    if conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone() is None:
        conn.close()
        abort(404, "Recipe not found")
    data = request.get_json(force=True)
    json_fields = {"ingredients", "steps", "healthy_ingredients", "healthy_steps", "healthy_benefits"}
    all_fields  = ["name", "category", "description", "calories", "servings",
                   "prep_time", "cook_time", "ingredients", "steps",
                   "healthy_description", "healthy_calories",
                   "healthy_ingredients", "healthy_steps", "healthy_benefits", "health_score"]
    updates, values = [], []
    for f in all_fields:
        if f in data:
            updates.append(f"{f} = ?")
            values.append(json.dumps(data[f]) if f in json_fields else data[f])
    if not updates:
        conn.close()
        abort(400, "No valid fields provided")
    values.append(recipe_id)
    conn.execute(f"UPDATE recipes SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row))


# ── DELETE /api/recipes/<id> ───────────────────────────────────────────────────

@app.route("/api/recipes/<int:recipe_id>", methods=["DELETE"])
def delete_recipe(recipe_id):
    conn = get_db()
    if conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone() is None:
        conn.close()
        abort(404, "Recipe not found")
    conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": recipe_id})


# ── Error handlers ─────────────────────────────────────────────────────────────

@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(409)
@app.errorhandler(500)
def handle_error(e):
    return jsonify({"error": str(e)}), e.code


# Run on import (works for both direct run and gunicorn)
if os.path.exists(DB_PATH):
    ensure_tables()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"Starting server on port {port}")
    app.run(debug=debug, host="0.0.0.0", port=port)
