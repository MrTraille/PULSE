# PULSE – Plan de release de musiques + générateur de todolist

Outil desktop (flask + pywebview) pour planifier les sorties (Spotify etc) :
- génération de plan de release depuis `plan_template.yaml`
- gestion de projets (project.yaml, plan.md, checklist.md)
- interface Flask + fenêtre desktop via pywebview

### A venir : 
- Editer les tâches dans les projets (vous pouvez déjà le faire "manuellement" dans AppData/Local/PulseProjects/VotreProjet/checklist.md)

## 1. Version portable : 

- Télécharger la dernière version dans l’onglet **Releases** :  
  `https://github.com/MrTraille/PULSE/releases`
- Lancer le `.exe` directement.
- 
Les projets sont enregistrés ici : 
```text
C:\Users\<votre_nom>\AppData\Local\PulseProjects
```

## 2. Version dev :

```bash
git clone https://github.com/MrTraille/PULSE.git
cd PULSE
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run_desktop.py

