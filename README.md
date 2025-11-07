# PULSE – Planner de sorties

Outil Flask + pywebview pour planifier les sorties (Spotify & co).

## Installation

```bash
git clone https://github.com/MrTraille/PULSE.git
cd PULSE
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
=======
# PULSE Label Planner

Outil Flask desktop pour planifier les sorties (Spotify & co) :
- génération de plan de release depuis `plan_template.yaml`
- gestion de projets (project.yaml, plan.md, checklist.md)
- interface Flask + fenêtre desktop via pywebview