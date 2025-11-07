import sys
import os
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from slugify import slugify

# Dossier de l'app (templates, plan_template.yaml)
if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).parent.resolve()

# Dossier où stocker les projets
if getattr(sys, "frozen", False):
    # ex : C:\Users\cyril\AppData\Local\PulseProjects
    base = Path.home() / "AppData" / "Local"
    PROJECTS_DIR = base / "PulseProjects"
else:
    PROJECTS_DIR = ROOT / "projects"

TEMPLATE_FILE = ROOT / "plan_template.yaml"

# -------------------------------------------------------------------
# Config genre LUFS + playlists + notes
# -------------------------------------------------------------------

GENRE_CONFIG = {
    "Synthwave": {
        "master_lufs": "-9 à -8 LUFS",
        "spotify_playlists": [
            "Spotify - Synthwave Outrun",
            "Spotify - Retrowave / Outrun",
            "Spotify - Electronic Rising",
        ],
        "other_playlists": [
            "Apple Music - Synthwave Essentials",
            "YouTube Music - Synthwave / Retro",
        ],
    },
    "Lofi": {
        "master_lufs": "-13 à -11 LUFS",
        "spotify_playlists": [
            "Spotify - lofi beats",
            "Spotify - lofi chill",
            "Spotify - jazz vibes (si adapté)",
        ],
        "other_playlists": [
            "Apple Music - Lo-Fi Chill",
            "YouTube Music - Lofi hip hop",
        ],
    },
    "Metal": {
        "master_lufs": "-7.5 à -6.5 LUFS",
        "spotify_playlists": [
            "Spotify - New Metal Tracks",
            "Spotify - Kickass Metal",
        ],
        "other_playlists": [
            "Apple Music - Breaking Metal",
        ],
    },
    "Chiptune": {
        "master_lufs": "-10 à -9 LUFS",
        "spotify_playlists": [
            "Spotify - 8-bit Attack",
            "Spotify - Retro Gaming",
        ],
        "other_playlists": [
            "YouTube Music - Chiptune / 8-bit",
        ],
    },
    "Symphonique": {
        "master_lufs": "-16 à -14 LUFS",
        "spotify_playlists": [
            "Spotify - Classical New Releases",
            "Spotify - Epic Classical",
        ],
        "other_playlists": [
            "Apple Music - Classical Essentials",
        ],
    },
    "Cinématique": {
        "master_lufs": "-16 à -12 LUFS",
        "spotify_playlists": [
            "Spotify - Cinematic Chill",
            "Spotify - Epic & Dramatic",
        ],
        "other_playlists": [
            "Apple Music - Cinematic Chill",
            "YouTube Music - Epic & Cinematic",
        ],
    },
}

DEFAULT_GENRE_CONFIG = {
    "master_lufs": None,
    "spotify_playlists": [],
    "other_playlists": [],
    "notes": "",
}


def get_genre_config(genre: str):
    """Retourne la config la plus pertinente en fonction du texte de genre."""
    g = (genre or "").lower()

    if "synthwave" in g:
        return GENRE_CONFIG["Synthwave"]
    if "lofi" in g or "lo-fi" in g:
        return GENRE_CONFIG["Lofi"]
    if "metal" in g:
        return GENRE_CONFIG["Metal"]
    if "chiptune" in g or "8bit" in g or "8-bit" in g:
        return GENRE_CONFIG["Chiptune"]
    if "symphon" in g:
        return GENRE_CONFIG["Symphonique"]
    if "cinéma" in g or "cinematic" in g:
        return GENRE_CONFIG["Cinématique"]

    cfg = GENRE_CONFIG.get(genre)
    if cfg:
        return cfg

    return DEFAULT_GENRE_CONFIG


# -------------------------------------------------------------------
# Template
# -------------------------------------------------------------------

def load_template():
    """
    Charge plan_template.yaml.
    Si introuvable ou cassé, renvoie un plan vide pour éviter un crash.
    """
    if not TEMPLATE_FILE.exists():
        return {"release_plan": []}

    try:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return {"release_plan": []}

    if not isinstance(data, dict):
        return {"release_plan": []}

    if "release_plan" not in data or not isinstance(data["release_plan"], list):
        data["release_plan"] = []

    return data

# -------------------------------------------------------------------
# Création de projet
# -------------------------------------------------------------------

def create_project_structure(
    slug,
    title,
    release_date,
    genre="Inconnu",
    artist="AngryTode",
    label_name="AngryTode",
    use_spotify_canvas=False,
    use_paid_ads=False,
):
    """Crée la structure d'un nouveau projet à partir du modèle fixe"""
    project_path = PROJECTS_DIR / slug
    project_path.mkdir(parents=True, exist_ok=True)

    template = load_template()
    genre_cfg = get_genre_config(genre)

    lufs_range = genre_cfg["master_lufs"]
    if lufs_range:
        master_target_str = f"{lufs_range} (TP ≤ -1 dBTP)"
    else:
        master_target_str = None

    project_yaml = {
        "title": title,
        "slug": slug,
        "artist": artist,
        "label": label_name,
        "genre": genre,
        "release_date": release_date.strftime("%Y-%m-%d"),
        "master_lufs_target": master_target_str,
        "spotify_playlists": genre_cfg["spotify_playlists"],
        "other_playlists": genre_cfg["other_playlists"],
        "use_spotify_canvas": bool(use_spotify_canvas),
        "use_paid_ads": bool(use_paid_ads),
    }

    with open(project_path / "project.yaml", "w", encoding="utf-8") as f:
        yaml.dump(project_yaml, f, allow_unicode=True)

    # -------------------------
    # plan.md
    # -------------------------
    plan_lines = [f"# {title} - Plan de sortie AngryTode\n"]
    for step in template["release_plan"]:
        plan_lines.append(f"\n## {step['title']} (J{step['day_offset']})\n")
        plan_lines.append("**Tâches :**\n")

        for raw_task in step["tasks"]:
            task = raw_task

            if isinstance(raw_task, str):
                if raw_task.startswith("[opt_spotify_canvas]"):
                    if not use_spotify_canvas:
                        continue
                    task = raw_task.replace("[opt_spotify_canvas]", "").strip()
                elif raw_task.startswith("[opt_paid_ads]"):
                    if not use_paid_ads:
                        continue
                    task = raw_task.replace("[opt_paid_ads]", "").strip()

            if "Masteriser le titre" in task and lufs_range:
                task = f"Masteriser le titre ({lufs_range}, TP ≤ -1 dBTP)"

            plan_lines.append(f"- [ ] {task}")

    (project_path / "plan.md").write_text("\n".join(plan_lines), encoding="utf-8")

    # -------------------------
    # checklist.md
    # -------------------------
    checklist_lines = ["# Checklist globale\n"]
    for step in template["release_plan"]:
        checklist_lines.append(f"### {step['title']}")

        for raw_task in step["tasks"]:
            task = raw_task

            if isinstance(raw_task, str):
                if raw_task.startswith("[opt_spotify_canvas]"):
                    if not use_spotify_canvas:
                        continue
                    task = raw_task.replace("[opt_spotify_canvas]", "").strip()
                elif raw_task.startswith("[opt_paid_ads]"):
                    if not use_paid_ads:
                        continue
                    task = raw_task.replace("[opt_paid_ads]", "").strip()

            if "Masteriser le titre" in task and lufs_range:
                task = f"Masteriser le titre ({lufs_range}, TP ≤ -1 dBTP)"

            checklist_lines.append(f"- [ ] {task}")

    (project_path / "checklist.md").write_text("\n".join(checklist_lines), encoding="utf-8")

    print(f"Projet créé : {project_path}")
    print("→ plan.md, checklist.md et project.yaml générés à partir du modèle.")



# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def cmd_new(args):
    """Mode CLI texte libre (tu peux garder la commande `python label_agent.py new "...")`"""
    user_input = " ".join(args)
    if not user_input.strip():
        print("⚠️  Merci de décrire le projet, ex : Je veux sortir Coffee Lofi, un morceau chill début décembre")
        return

    title_part = user_input.strip().split(",")[0]
    title = title_part.replace("Je veux sortir", "").strip()
    if not title:
        title = "Projet sans titre"

    slug = slugify(title)
    genre = "Inconnu"

    today = datetime.now()
    release_date = today + timedelta(days=30)

    tokens = user_input.replace(",", " ").split()
    for token in tokens:
        low = token.lower()

        if "synthwave" in low:
            genre = "Synthwave"
        elif "lofi" in low or "lo-fi" in low:
            genre = "Lofi"
        elif "chiptune" in low:
            genre = "Chiptune"

        if "décembre" in low:
            year = today.year
            release_date = datetime(year, 12, 1)
        elif "janvier" in low:
            year = today.year if today.month < 12 else today.year + 1
            release_date = datetime(year, 1, 1)
        elif token.isdigit():
            day = int(token)
            try:
                release_date = datetime(today.year, today.month, day)
            except ValueError:
                pass

    create_project_structure(slug, title, release_date, genre)


def cmd_deadline(slug):
    """Affiche la prochaine deadline à venir dans le terminal"""
    project_path = PROJECTS_DIR / slug
    yaml_file = project_path / "project.yaml"
    plan_file = TEMPLATE_FILE

    if not yaml_file.exists():
        print("Projet introuvable.")
        return

    project = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
    plan = yaml.safe_load(plan_file.read_text(encoding="utf-8"))

    release_date = datetime.strptime(project["release_date"], "%Y-%m-%d")
    today = datetime.now()
    today_offset = (today - release_date).days

    steps = sorted(plan["release_plan"], key=lambda s: s["day_offset"])
    next_step = None
    for step in steps:
        if step["day_offset"] >= today_offset:
            next_step = step
            break

    if not next_step:
        print("🎉 Toutes les étapes sont complétées !")
        return

    days_left = next_step["day_offset"] - today_offset
    print(f"\n🗓️ Prochaine deadline dans {days_left} jours ({next_step['title']}) :\n")
    for t in next_step["tasks"]:
        print(f" - [ ] {t}")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage : label_agent.py new <description du projet>")
        print("        label_agent.py deadline <slug>")
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "new":
        cmd_new(args)
    elif cmd == "deadline":
        if not args:
            print("Il faut préciser le slug du projet.")
        else:
            cmd_deadline(args[0])
    else:
        print(f"Commande inconnue : {cmd}")


if __name__ == "__main__":
    main()
