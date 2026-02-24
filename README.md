# Centre de Masse — Plateforme de Force

## Documentation technique

---

## 1. Presentation du projet

Application desktop Windows pour la visualisation en temps reel du **centre de masse** a partir d'une plateforme de force equipee de 4 capteurs (cellules de charge). L'application communique avec un microcontroleur **ESP32** via serie (USB ou Bluetooth), affiche les poids de chaque capteur, calcule et trace le centre de masse en direct, et permet l'enregistrement de sessions pour relecture ulterieure.

### Fonctionnalites principales

- Visualisation temps reel du centre de masse (canvas 2D avec grille)
- 4 capteurs : Haut-Droit, Haut-Gauche, Bas-Droit, Bas-Gauche
- Communication serie USB et Bluetooth avec auto-detection
- Enregistrement de sessions (multi-utilisateur, multi-plateforme)
- Relecture animee des sessions avec controle de vitesse
- Dashboard web local (Flask) accessible depuis d'autres appareils
- Themes clair/sombre avec persistance
- Tare et calibration des capteurs
- Mise a jour automatique depuis un serveur distant (Hostinger)
- Monitoring distant (heartbeat, stats, etat de l'app)
- Interface a onglets responsive (Capteurs / Calibration / Outils)

---

## 2. Architecture des fichiers

```
filesexe/
|-- centre_de_masse.py      # Application principale (GUI tkinter)
|-- database.py              # Couche base de donnees SQLite
|-- recorder.py              # Moteur d'enregistrement de sessions
|-- replay_window.py         # Fenetre de relecture des sessions
|-- web_dashboard.py         # Serveur web Flask (dashboard local)
|-- remote_sync.py           # Sync distante + auto-update
|-- generate_icon.py         # Utilitaire de generation d'icone
|
|-- CentredeMasse.spec       # Configuration PyInstaller
|-- build.bat                # Script de build Windows
|-- icon.ico                 # Icone de l'application
|
|-- templates/               # Templates HTML (Flask/Jinja2)
|   |-- base.html            # Template de base
|   |-- index.html           # Page d'accueil du dashboard
|   |-- replay.html          # Page de relecture web
|
|-- static/                  # Fichiers statiques web
|   |-- replay.js            # Player de relecture JavaScript
|
|-- hostinger/               # Fichiers PHP pour le serveur distant
|   |-- cm_api.php           # API monitoring + auto-update + admin
|   |-- download.php         # Page publique de telechargement
|   |-- favicon.png
|
|-- UnityForcePlatform/      # Projet Unity 3D alternatif
|   |-- SETUP.txt
|   |-- Assets/Scripts/...
|
|-- dist/                    # Sortie de build (CentredeMasse.exe)
|-- build/                   # Fichiers intermediaires PyInstaller
|-- cm_data.db               # Base de donnees SQLite
|-- cm_settings.json         # Preferences utilisateur
```

---

## 3. Pre-requis et installation (developpement)

### Python

- **Python 3.9+** (teste avec 3.9 et 3.11)
- Ajouter Python au PATH lors de l'installation

### Dependances Python

```bash
pip install pyserial flask
```

| Package    | Usage                                    |
|------------|------------------------------------------|
| `pyserial` | Communication serie USB/Bluetooth        |
| `flask`    | Dashboard web local                      |
| `tkinter`  | Interface graphique (inclus avec Python) |

### Lancement en mode developpement

```bash
cd E:\filesexe
python centre_de_masse.py
```

---

## 4. Build de l'executable (.exe)

### Pre-requis

```bash
pip install pyinstaller
```

### Methode rapide

```bash
cd E:\filesexe
build.bat
```

### Methode manuelle

```bash
pyinstaller CentredeMasse.spec --noconfirm
```

### Resultat

Le fichier `dist/CentredeMasse.exe` est genere (~20-40 MB).
C'est un **single-file** : tout est embarque (Python, DLL, templates, icone).

### Ce que contient le .exe (via le .spec)

- `centre_de_masse.py` (point d'entree)
- Modules internes : `database`, `recorder`, `replay_window`, `web_dashboard`, `remote_sync`
- Dossiers `templates/` et `static/` (pour Flask)
- `icon.ico`
- Hidden imports : `flask`, `jinja2`, `jinja2.ext`, `werkzeug`, `markupsafe`

---

## 5. Deploiement serveur (Hostinger)

### Fichiers a uploader

Uploader les fichiers du dossier `hostinger/` dans le repertoire `plancheadmin/` sur le serveur :

```
https://ibenji.fr/plancheadmin/
|-- cm_api.php           # API + page admin
|-- download.php         # Page de telechargement publique
|-- favicon.png
```

### Structure auto-creee par cm_api.php

Au premier appel, les dossiers suivants sont crees automatiquement :

```
plancheadmin/
|-- cm_data/             # Heartbeats des apps (fichiers JSON)
|   |-- .htaccess        # Protection acces direct
|-- cm_updates/          # Fichiers de mise a jour
|   |-- version.json     # {"version": 5}
|   |-- CentredeMasse.exe
```

### Endpoints de l'API

| Methode | URL                              | Auth     | Description                           |
|---------|----------------------------------|----------|---------------------------------------|
| GET     | `?action=version`                | Non      | Retourne `{version, download_url}`    |
| GET     | `?action=download`               | API Key  | Telecharge le .exe (pour auto-update) |
| GET     | `?action=public_download`        | Non      | Telecharge le .exe (page publique)    |
| GET     | `?action=installer`              | Non      | Sert le script .bat d'installation    |
| POST    | (sans action)                    | API Key  | Recoit un heartbeat JSON              |
| POST    | `?action=upload`                 | API Key  | Upload d'un nouveau .exe              |



Configuree dans :
- `cm_api.php` : `define('API_KEY', '...')`
- `centre_de_masse.py` : variable `_REMOTE_KEY`

---

## 6. Systeme de mise a jour automatique

### Fonctionnement

1. **Au demarrage** de l'app, le thread `RemoteSync` fait immediatement un check de version
2. Appel GET `cm_api.php?action=version` → reponse `{"version": 5, "download_url": "..."}`
3. Comparaison : si `server_version > APP_VERSION` → telechargement
4. Validation du fichier telecharge (taille > 100 Ko + header PE `MZ`)
5. **Popup de notification** : "Nouvelle version (vX) telechargee !"
6. Creation d'un script `.bat` qui :
   - Attend 3s que l'app se ferme
   - Supprime l'ancien .exe (avec retry)
   - Deplace le nouveau .exe
   - Attend 5s (liberation des DLL PyInstaller)
   - Relance l'application
7. L'app se ferme proprement

### Publier une nouvelle version

1. **Incrementer** `APP_VERSION` dans `centre_de_masse.py` (ex: 3 → 4)
2. **Build** : `build.bat`
3. **Upload** le nouveau `dist/CentredeMasse.exe` via la page admin `cm_api.php`
4. **Mettre a jour** le numero de version dans l'admin (doit correspondre)

> **IMPORTANT** : Le numero dans `APP_VERSION` du code Python et le numero
> dans `version.json` sur le serveur doivent etre coherents.
> Le serveur doit avoir un numero SUPERIEUR a celui embarque dans le .exe
> pour que la mise a jour se declenche.

### Checks periodiques

Apres le check initial, l'app verifie aussi toutes les **5 minutes** (5 heartbeats x 60s).

---

## 7. Communication serie (ESP32)

### Format des donnees

L'ESP32 envoie des lignes JSON a haute frequence :

```json
{"weight1": 1234, "weight2": 5678, "weight3": 9012, "weight4": 3456}
```

- Valeurs en **grammes** (entiers)
- `weight1` = Haut-Droit, `weight2` = Haut-Gauche
- `weight3` = Bas-Droit, `weight4` = Bas-Gauche

### Reponses (ESP32 → App)

```json
{"status": "tare_ok"}
{"status": "cal_ok", "sensor": 1, "scale": 0.0012, "offset": 50000}
{"status": "cal_error", "msg": "No weight detected"}
{"status": "calib_values", "off1": 50000, "sc1": 0.0012, ...}
```

### Commandes (App → ESP32)

```json
{"cmd": "tare"}
{"cmd": "cal", "sensor": 1, "weight": 1000}
{"cmd": "get_calib"}
```

### Parametres de connexion

| Parametre | Valeurs supportees        | Par defaut |
|-----------|---------------------------|------------|
| Baud rate | 9600, 115200, **921600**  | 921600     |
| Timeout   | 0.5s (lecture)            |            |

### Detection automatique

L'app detecte automatiquement les ports `ForcePlatform` (par nom, description ou fabricant).
Pour les ports Bluetooth, elle teste tous les ports BT disponibles un par un.

---

## 8. Base de donnees SQLite

### Fichier

`cm_data.db` — situe a cote du .exe (pas dans le bundle temporaire)

### Schema

```sql
users (id, name, created_at)
platforms (id, name, board_width_cm, board_height_cm, created_at)
sessions (id, user_id, platform_id, started_at, ended_at, duration_sec, sample_count, notes)
samples (id, session_id, t_ms, w0, w1, w2, w3, com_x, com_y)
```

- Mode WAL active (acces concurrent)
- Cles etrangeres actives
- Index sur `samples(session_id, t_ms)` pour la relecture rapide
- Suppression en cascade : supprimer une session supprime ses samples

### Enregistrement des sessions

- `recorder.py` utilise un buffer thread-safe de 500 samples
- Flush automatique en base quand le buffer est plein
- Flush final a l'arret de l'enregistrement

---

## 9. Dashboard web local

### Demarrage

Onglet **Outils** → bouton **DASHBOARD WEB** → le navigateur s'ouvre automatiquement.

### Acces reseau

L'URL affichee (ex: `http://192.168.1.42:5000`) est accessible depuis tout appareil
sur le meme reseau local (telephone, tablette, autre PC).

### Pages

| Route                         | Description                        |
|-------------------------------|------------------------------------|
| `/`                           | Liste des sessions avec filtres    |
| `/replay/<id>`                | Relecture animee d'une session     |
| `/api/sessions`               | API JSON : liste des sessions      |
| `/api/session/<id>`           | API JSON : details d'une session   |
| `/api/session/<id>/samples`   | API JSON : donnees d'une session   |
| `/api/platforms`              | API JSON : liste des plateformes   |
| `/api/users`                  | API JSON : liste des utilisateurs  |

---

## 10. Interface utilisateur (GUI)

### Panneau gauche (315 px, a onglets)

**Onglet Capteurs :**
- 4 cartes capteurs avec valeur en kg et barre de progression
- Poids total (encadre bleu)
- Bouton TARE

**Onglet Calibration :**
- Champ poids de reference (kg)
- Log de calibration
- 4 boutons CAL (un par capteur)
- Bouton "Lire calibration ESP"
- Affichage offset/scale de chaque capteur

**Onglet Outils :**
- Bouton Historique Sessions (ouvre la fenetre de relecture)
- Bouton Dashboard Web (demarre/arrete le serveur + ouvre le navigateur)
- Lien cliquable vers le dashboard

### Panneau droit

- Bouton Enregistrement (Demarrer / Arreter)
- Chronometre et compteur d'echantillons
- Canvas de visualisation : plateau avec grille 5 cm, 4 capteurs aux coins,
  croix du centre de masse avec trainee animee

### Barre du haut

- Titre "CENTRE DE MASSE"
- Bouton theme (soleil/lune)
- Frequence en Hz
- Statut connexion (CONNECTE / DECONNECTE / ATTENTE / TIMEOUT)

### Barre utilisateur/plateforme

- Selection utilisateur (+ ajouter / - supprimer)
- Selection plateforme (+ ajouter / - supprimer)

### Barre connexion

- Selection du port serie + baud rate
- Bouton Actualiser / Connecter / Deconnecter

---

## 11. Heartbeat et monitoring distant

L'app envoie un heartbeat toutes les **60 secondes** au serveur :

```json
{
  "app_id": "2f0f952b-5eb",
  "app_name": "PC-Bureau",
  "app_version": 3,
  "hostname": "PC-Bureau",
  "os": "Windows 10",
  "status": "online",
  "is_recording": false,
  "connected": true,
  "timestamp": "2025-02-24 14:30:00",
  "user_count": 3,
  "platform_count": 2,
  "session_count": 15,
  "sample_count": 45000,
  "total_duration_sec": 3600.5,
  "users": [...],
  "platforms": [...],
  "recent_sessions": [...]
}
```

Le dashboard admin sur `cm_api.php` affiche en temps reel :
- Nombre d'apps, apps en ligne, utilisateurs, sessions
- Cartes par application avec badges (recording, connected, version)
- Upload de nouvelles versions

---

## 12. Configuration persistante

Fichier `cm_settings.json` (a cote du .exe) :

```json
{
  "theme": "dark",
  "last_user": "Jean",
  "last_platform": "Plateforme A",
  "app_id": "2f0f952b-5eb"
}
```

Sauvegarde automatique a chaque changement de :
- Theme (clair/sombre)
- Utilisateur selectionne
- Plateforme selectionnee

---

## 13. Troubleshooting

| Probleme                            | Cause probable                          | Solution                                      |
|-------------------------------------|-----------------------------------------|-----------------------------------------------|
| "Aucun port"                        | ESP32 non branche ou pas jumele BT      | Brancher USB ou jumeler Bluetooth              |
| Connexion BT echoue                 | Mauvais port COM BT                     | L'app teste tous les ports BT automatiquement  |
| Poids a 0.000 kg                    | Pas de tare effectuee                   | Cliquer TARE sans rien sur la plateforme       |
| "Failed to load Python DLL"         | Redemarrage trop rapide apres update    | Relancer l'app manuellement                    |
| Version affichee incorrecte         | APP_VERSION pas incremente dans le code | Modifier `APP_VERSION` et rebuild              |
| Dashboard web inaccessible          | Firewall bloque le port 5000            | Autoriser le port dans le pare-feu Windows     |
| Mise a jour ne se declenche pas     | Version serveur <= version app          | Verifier version.json sur le serveur           |
| Calibration echoue                  | Pas de poids sur le capteur             | Poser le poids de reference sur le bon capteur |

---

## 14. Calcul du centre de masse

Formules utilisees avec les 4 capteurs (w0=HD, w1=HG, w2=BD, w3=BG) :

```
total = w0 + w1 + w2 + w3

X_ratio = (w0 + w2 - w1 - w3) / total    # -1 (gauche) a +1 (droite)
Y_ratio = (w2 + w3 - w0 - w1) / total    # -1 (haut) a +1 (bas)
```

- Si `total < 50g` (NEAR_ZERO_THRESHOLD) → centre au milieu (pas de bruit)
- La trainee garde les 15 dernieres positions avec fondu progressif
