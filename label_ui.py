from flask import Flask, render_template, request, redirect, url_for, jsonify
from pathlib import Path
from datetime import datetime, timedelta
from slugify import slugify
import yaml
import label_agent
import os
import requests
import sys


app = Flask(__name__)

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
# Utilitaires
# -------------------------------------------------------------------

FR_MONTHS_SHORT = {
    1: "janv",
    2: "févr",
    3: "mars",
    4: "avr",
    5: "mai",
    6: "juin",
    7: "juil",
    8: "août",
    9: "sept",
    10: "oct",
    11: "nov",
    12: "déc",
}

FR_MONTHS_LONG = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}

def format_date_short_fr(d):
    return f"{d.day} {FR_MONTHS_SHORT.get(d.month, '')} {d.year}"

def format_date_long_fr(d):
    return f"{d.day:02d} {FR_MONTHS_LONG.get(d.month, '')} {d.year}"

def load_yaml(path: Path):
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if data is None:
            return {}
        if not isinstance(data, dict):
            return {}
        return data


def format_days(delta: int):
    """Retourne une phrase lisible selon le décalage en jours"""
    if delta is None:
        return ""
    if delta == 0:
        return "aujourd'hui!"
    elif delta == 1:
        return "dans 1 jour"
    elif delta > 1:
        return f"dans {delta} jours"
    elif delta == -1:
        return "il y a 1 jour"
    else:
        return f"il y a {abs(delta)} jours"


def get_next_deadline(project_slug: str):
    """Calcule la prochaine étape à venir depuis le modèle YAML (par offset J-xx)"""
    project_path = PROJECTS_DIR / project_slug
    project_yaml = project_path / "project.yaml"

    if not project_yaml.exists():
        return None, None, None

    project = load_yaml(project_yaml)
    release_date_str = project.get("release_date")
    if not release_date_str:
        return None, None, None

    try:
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None, None, None

    today = datetime.now().date()
    today_offset = (today - release_date).days

    template = load_yaml(TEMPLATE_FILE)
    steps = template.get("release_plan", [])
    steps = sorted(steps, key=lambda s: s["day_offset"])

    next_step = None
    for step in steps:
        if step["day_offset"] >= today_offset:
            next_step = step
            break

    if not next_step:
        return None, None, release_date

    days_left = next_step["day_offset"] - today_offset
    return next_step, days_left, release_date


def load_checklist_status(path: Path):
    """
    Lit checklist.md et retourne un dict {texte_tâche: bool(done)}
    basé sur les lignes '- [ ] ...' ou '- [x] ...'.
    """
    status = {}
    if not path.exists():
        return status

    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            done = stripped.startswith("- [x]")
            text = stripped[5:].strip()
            status[text] = done
    return status


def parse_checklist_sections(checklist_path: Path, template_path: Path):
    """
    Parse checklist.md en sections avec offset.

    Retourne:
      sections: [
        {
          "title": "...",
          "offset": -35,
          "pos": 0-100 (optionnel),
          "tasks": [{"text": "...", "done": bool}, ...],
          "all_done": bool
        },
        ...
      ],
      min_offset, max_offset
    """
    if not checklist_path.exists():
        return [], None, None

    template = load_yaml(template_path)
    steps = template.get("release_plan", [])
    offsets_by_title = {step["title"]: step.get("day_offset") for step in steps}
    offset_values = [o for o in offsets_by_title.values() if o is not None]

    if offset_values:
        min_offset = min(offset_values)
        max_offset = max(offset_values)
    else:
        min_offset = max_offset = None

    lines = checklist_path.read_text(encoding="utf-8").splitlines()

    sections = []
    current_title = None
    current_tasks = []

    def add_section():
        nonlocal current_title, current_tasks
        if current_title is None:
            return
        offset = offsets_by_title.get(current_title)
        pos = None
        if (
            min_offset is not None
            and max_offset is not None
            and max_offset != min_offset
            and offset is not None
        ):
            pos = int(round((offset - min_offset) / (max_offset - min_offset) * 100))

        all_done = bool(current_tasks) and all(t["done"] for t in current_tasks)

        sections.append(
            {
                "title": current_title,
                "offset": offset,
                "pos": pos,
                "tasks": current_tasks,
                "all_done": all_done,
            }
        )

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("### "):
            add_section()
            current_title = stripped[4:].strip()
            current_tasks = []
            continue

        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            if current_title is None:
                continue
            done = stripped.startswith("- [x]")
            text = stripped[5:].strip()
            current_tasks.append({"text": text, "done": done})
    add_section()

    return sections, min_offset, max_offset

app.jinja_env.globals.update(
    format_days=format_days,
    datetime=datetime,
)

def build_project_context_yaml(project: dict, extra_notes: str | None = None) -> str:
    """
    Construit un YAML de contexte enrichi:
      - infos projet (project.yaml)
      - today + J-offset
      - guidance par genre (LUFS / playlists / notes)
      - notes créateur (notes.txt) -> "user_notes"
    """
    ctx = dict(project)

    today = datetime.now().date()
    ctx["today"] = today.isoformat()

    rd_str = project.get("release_date")
    j_offset = None
    if rd_str:
        try:
            rd = datetime.strptime(rd_str, "%Y-%m-%d").date()
            j_offset = (today - rd).days
        except ValueError:
            pass
    ctx["today_offset"] = j_offset

    genre = (project.get("genre") or "").strip()
    cfg = getattr(label_agent, "GENRE_CONFIG", {})
    matched_key = None
    for k in cfg.keys():
        if k.lower() in genre.lower():
            matched_key = k
            break
    if matched_key:
        g = cfg[matched_key]
        ctx["genre_guidance"] = {
            "master_lufs": g.get("master_lufs"),
            "spotify_playlists": g.get("spotify_playlists", []),
            "other_playlists": g.get("other_playlists", []),
            "genre_notes": g.get("notes", "")
        }

    if extra_notes:
        ctx["user_notes"] = extra_notes

    try:
        return yaml.safe_dump(ctx, allow_unicode=True, sort_keys=False)
    except Exception:
        return yaml.safe_dump({"project": ctx}, allow_unicode=True, sort_keys=False)

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------


@app.route("/")
def index():
    projects = []
    today = datetime.now().date()

    if PROJECTS_DIR.exists():
        for p in PROJECTS_DIR.iterdir():
            if p.is_dir() and (p / "project.yaml").exists():
                data = load_yaml(p / "project.yaml")
                if not isinstance(data, dict):
                    continue
                release_str = data.get("release_date")
                release_display = "N/A"
                sort_key = "9999-12-31"

                is_released = False
                status = "En cours"

                if release_str:
                    try:
                        rd = datetime.strptime(release_str, "%Y-%m-%d").date()
                        release_display = format_date_long_fr(rd)
                        sort_key = release_str
                        if rd <= today:
                            is_released = True
                            status = "Sortie"
                        else:
                            days_to_release = (rd - today).days
                            if days_to_release > 40:
                                status = "Programmé"
                            else:
                                status = "En cours"
                    except ValueError:
                        release_display = release_str
                        sort_key = release_str

                projects.append({
                    "slug": p.name,
                    "title": data.get("title", p.name),
                    "artist": data.get("artist", "AngryTode"),
                    "label": data.get("label", "Indépendant"),
                    "release_date": release_display,
                    "genre": data.get("genre", "N/A"),
                    "is_released": is_released,
                    "status": status,
                    "sort_key": sort_key,
                })

    projects.sort(key=lambda x: x["sort_key"])
    return render_template("index.html", projects=projects)

@app.route("/project/<slug>")
def project_detail(slug):
    root = PROJECTS_DIR / slug
    project_yaml = root / "project.yaml"
    plan_md = root / "plan.md"
    checklist_md = root / "checklist.md"
    notes_path = root / "notes.txt"

    project = load_yaml(project_yaml)
    plan_html = plan_md.read_text(encoding="utf-8") if plan_md.exists() else "_Aucun plan.md trouvé_"
    notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""

    checklist_sections, min_offset, max_offset = parse_checklist_sections(checklist_md, TEMPLATE_FILE)

    next_step, days_left, release_date = get_next_deadline(slug)
    checklist_status = load_checklist_status(checklist_md)

    if release_date and checklist_sections:
        for sec in checklist_sections:
            offset = sec.get("offset")
            if offset is not None:
                d = release_date + timedelta(days=offset)
                sec["date_obj"] = d
                sec["date_str"] = format_date_short_fr(d)
            else:
                sec["date_obj"] = None
                sec["date_str"] = None

    if next_step and checklist_sections:
        for section in checklist_sections:
            if section["title"] == next_step["title"]:
                next_step = dict(next_step)
                next_step["tasks"] = [t["text"] for t in section["tasks"]]
                break

    deadline_sections = []
    if release_date and checklist_sections:
        today = datetime.now().date()
        today_offset = (today - release_date).days

        past = []
        current_or_future = []

        for sec in checklist_sections:
            offset = sec.get("offset")
            if offset is None:
                continue
            tasks = sec.get("tasks", [])
            if not tasks:
                continue

            all_done = sec.get("all_done", False)

            if offset < today_offset:
                sec["auto_hide"] = True
                if not all_done:
                    past.append(sec)
            else:
                sec["auto_hide"] = False
                current_or_future.append(sec)

        past.sort(key=lambda s: s["offset"])
        deadline_sections = past

        if current_or_future:
            next_future = min(current_or_future, key=lambda s: s["offset"])
            deadline_sections.append(next_future)

    return render_template(
        "project.html",
        slug=slug,
        project=project,
        plan_html=plan_html,
        next_step=next_step,
        days_left=days_left,
        release_date=release_date.strftime("%d/%m/%Y") if release_date else "N/A",
        checklist_status=checklist_status,
        checklist_sections=checklist_sections,
        min_offset=min_offset,
        max_offset=max_offset,
        notes=notes,
        deadline_sections=deadline_sections,
    )

@app.route("/project/<slug>/delete", methods=["POST"])
def delete_project(slug):
    import shutil
    project_path = PROJECTS_DIR / slug
    if project_path.exists():
        shutil.rmtree(project_path)
    return redirect(url_for("index"))

@app.route("/new_project", methods=["POST"])
def new_project():
    from traceback import print_exc

    try:
        title = request.form.get("title", "").strip()
        style = request.form.get("style", "").strip()
        artist = request.form.get("artist", "").strip() or "AngryTode"
        label_name = request.form.get("label", "").strip() or "Indépendant"
        release_str = request.form.get("release_date", "").strip()
        use_spotify_canvas = bool(request.form.get("use_spotify_canvas"))
        use_paid_ads = bool(request.form.get("use_paid_ads"))

        if not title or not release_str:
            return redirect(url_for("index"))

        try:
            release_date = datetime.strptime(release_str, "%Y-%m-%d")
        except ValueError:
            return redirect(url_for("index"))

        slug = slugify(title)

        label_agent.create_project_structure(
            slug=slug,
            title=title,
            release_date=release_date,
            genre=style or "Inconnu",
            artist=artist,
            label_name=label_name,
            use_spotify_canvas=use_spotify_canvas,
            use_paid_ads=use_paid_ads,
        )

        return redirect(url_for("index"))

    except Exception as e:
        try:
            PROJECTS_DIR.mkdir(exist_ok=True)
            log_path = PROJECTS_DIR / "_pulse_error.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat()}] Erreur new_project:\n{repr(e)}\n")
                print_exc(file=f)
        except Exception:
            pass

        return redirect(url_for("index"))




@app.route("/project/<slug>/toggle_deadline_task", methods=["POST"])
def toggle_deadline_task(slug):
    task_text = request.form.get("task_text", "").strip()
    if not task_text:
        return jsonify(success=False, error="no-task-text"), 400

    root = PROJECTS_DIR / slug
    checklist_path = root / "checklist.md"

    new_done = None

    if checklist_path.exists():
        lines = checklist_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith("- [ ]") or stripped.startswith("- [x]")) and stripped[5:].strip() == task_text:
                if stripped.startswith("- [ ]"):
                    line = line.replace("- [ ]", "- [x]", 1)
                    new_done = True
                else:
                    line = line.replace("- [x]", "- [ ]", 1)
                    new_done = False
            new_lines.append(line)
        checklist_path.write_text("\n".join(new_lines), encoding="utf-8")

    if new_done is None:
        return jsonify(success=False, error="task-not-found"), 404

    updated_text = checklist_path.read_text(encoding="utf-8") if checklist_path.exists() else ""
    return jsonify(success=True, done=new_done, checklist=updated_text)


@app.route("/project/<slug>/notes", methods=["POST"])
def update_notes(slug):
    notes = request.form.get("notes", "")
    root = PROJECTS_DIR / slug
    root.mkdir(exist_ok=True)
    notes_path = root / "notes.txt"
    notes_path.write_text(notes, encoding="utf-8")
    return redirect(url_for("project_detail", slug=slug) + "#overview-tab-pane")