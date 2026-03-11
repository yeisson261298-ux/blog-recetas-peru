from flask import Flask, render_template, jsonify
import anthropic
import json
import os
import threading
import schedule
import time
from datetime import datetime

app = Flask(__name__)

RECIPES_FILE = "recipes.json"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Lista de recetas peruanas para generar
RECETAS_PERUANAS = [
    "Ceviche peruano", "Lomo saltado", "Ají de gallina", "Causa limeña",
    "Anticuchos", "Pollo a la brasa", "Arroz con leche peruano", "Picarones",
    "Seco de res", "Tacu tacu", "Papa a la huancaína", "Rocoto relleno",
    "Chicharrón de cerdo", "Leche de tigre", "Sopa criolla", "Carapulcra",
    "Mazamorra morada", "Turrón de doña pepa", "Escabeche de pollo",
    "Arroz con mariscos", "Chupe de camarones", "Olluquito con charqui",
    "Jalea de mariscos", "Suspiro limeño", "Pachamanca"
]

YOUTUBE_SEARCHES = {
    "Ceviche peruano": "dQw4w9WgXcQ",
    "Lomo saltado": "dQw4w9WgXcQ",
    "Ají de gallina": "dQw4w9WgXcQ",
}

def load_recipes():
    if os.path.exists(RECIPES_FILE):
        with open(RECIPES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_recipes(recipes):
    with open(RECIPES_FILE, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)

def get_youtube_search_url(recipe_name):
    query = recipe_name.replace(" ", "+") + "+receta+peruana"
    return f"https://www.youtube.com/results?search_query={query}"

def get_youtube_embed(recipe_name):
    query = recipe_name.replace(" ", "%20") + "%20receta%20peruana"
    return f"https://www.youtube.com/embed?listType=search&list={query}&autoplay=0"

def generate_recipe(recipe_name):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""Genera una receta completa y atractiva de "{recipe_name}" en formato JSON.
Responde SOLO con JSON válido, sin texto adicional ni backticks.
El JSON debe tener exactamente esta estructura:
{{
  "nombre": "nombre del plato",
  "emoji": "emoji representativo del plato",
  "descripcion": "descripción corta y apetitosa en 2 oraciones máximo",
  "tiempo": "tiempo total de preparación",
  "porciones": "número de porciones",
  "dificultad": "Fácil/Media/Difícil",
  "ingredientes": ["ingrediente 1 con cantidad", "ingrediente 2 con cantidad"],
  "pasos": ["paso 1 corto", "paso 2 corto", "paso 3 corto"],
  "tip": "un consejo secreto del chef en una oración",
  "categoria": "Entrada/Plato principal/Postre/Bebida",
  "youtube_query": "búsqueda exacta para YouTube de esta receta",
  "imagen_wiki": "nombre exacto del plato en inglés para buscar en Wikipedia"
}}
Máximo 5 ingredientes y 4 pasos. Sé conciso y visual."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    text = message.content[0].text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

def auto_generate_recipe():
    recipes = load_recipes()
    existing_names = [r["nombre"] for r in recipes]
    pending = [r for r in RECETAS_PERUANAS if r not in existing_names]
    if not pending:
        return
    recipe_name = pending[0]
    try:
        recipe = generate_recipe(recipe_name)
        recipe["fecha"] = datetime.now().strftime("%d/%m/%Y")
        recipe["id"] = len(recipes) + 1
        recipe["youtube_embed"] = f"https://www.youtube.com/results?search_query={recipe_name.replace(' ', '+')}+receta"
        recipes.insert(0, recipe)
        save_recipes(recipes)
        print(f"✅ Receta generada: {recipe_name}")
    except Exception as e:
        print(f"❌ Error generando {recipe_name}: {e}")

def run_scheduler():
    schedule.every().monday.at("08:00").do(auto_generate_recipe)
    schedule.every().thursday.at("08:00").do(auto_generate_recipe)
    while True:
        schedule.run_pending()
        time.sleep(3600)

@app.route("/")
def index():
    recipes = load_recipes()
    return render_template("index.html", recipes=recipes)

@app.route("/receta/<int:recipe_id>")
def recipe_detail(recipe_id):
    recipes = load_recipes()
    recipe = next((r for r in recipes if r.get("id") == recipe_id), None)
    if not recipe:
        return "Receta no encontrada", 404
    return render_template("recipe.html", recipe=recipe)

@app.route("/api/generate", methods=["POST"])
def api_generate():
    try:
        auto_generate_recipe()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/recipes")
def api_recipes():
    return jsonify(load_recipes())

if __name__ == "__main__":
    # Generate initial recipes if none exist
    if not os.path.exists(RECIPES_FILE) or load_recipes() == []:
        print("Generando recetas iniciales...")
        for i in range(min(6, len(RECETAS_PERUANAS))):
            try:
                recipe = generate_recipe(RECETAS_PERUANAS[i])
                recipes = load_recipes()
                recipe["fecha"] = datetime.now().strftime("%d/%m/%Y")
                recipe["id"] = len(recipes) + 1
                recipe["youtube_embed"] = f"https://www.youtube.com/results?search_query={RECETAS_PERUANAS[i].replace(' ', '+')}+receta"
                recipes.insert(0, recipe)
                save_recipes(recipes)
                print(f"✅ {RECETAS_PERUANAS[i]}")
            except Exception as e:
                print(f"❌ Error: {e}")

    # Start scheduler in background
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
