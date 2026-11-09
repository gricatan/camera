# HeadScreen

Remplace ta tête par un **cube-écran 3D animé** dans ta webcam. Le cube suit tes mouvements (rotation, inclinaison), ses yeux suivent ton regard, clignent, et sa bouche bouge quand tu parles. Tes **gestes de main** changent l'expression.

Le résultat sort dans une **caméra virtuelle** que tu peux choisir dans Discord, Teams, Zoom, OBS, Google Meet, etc.

> Fonctionne sur **Windows 10 / 11**. **Pas besoin de WSL**, de Linux, ni de savoir programmer.
> Tout tourne sur ton PC : aucune image n'est envoyée sur Internet.

---

## Installation (à faire une seule fois)

### Étape 1 — Installer Python 3.12

1. Va sur <https://www.python.org/downloads/> et télécharge une version **3.12.x** (ex. 3.12.9).
   ⚠️ Prends bien la **3.12** : les versions 3.13 et plus récentes ne marchent pas avec ce projet.
2. Lance l'installateur et **coche la case « Add python.exe to PATH »** en bas de la première fenêtre.
3. Clique sur **Install Now**.

Pour vérifier : ouvre le menu Démarrer, tape `cmd`, ouvre l'**Invite de commandes**, tape `py -3.12 --version` puis Entrée. Tu dois voir `Python 3.12.x`.

### Étape 2 — Installer OBS Studio (fournit la caméra virtuelle)

1. Va sur <https://obsproject.com> et télécharge OBS Studio pour Windows.
2. Installe-le avec les options par défaut.
3. Tu n'as **pas besoin d'ouvrir OBS** ensuite : seul son composant « caméra virtuelle » nous sert.

### Étape 3 — Télécharger le projet

Sur la page GitHub du projet :

1. Clique sur le bouton vert **Code**, puis **Download ZIP**.
2. Fais un clic droit sur le ZIP téléchargé, **Extraire tout…**, et choisis un dossier simple (ex. `C:\HeadScreen`).

> Si tu connais git : `git clone https://github.com/gricatan/camera.git`

### Étape 4 — Lancer

Dans le dossier extrait, **double-clique sur `run.bat`**.

- **Au tout premier lancement**, il télécharge et installe les composants nécessaires (plusieurs centaines de Mo). Compte quelques minutes et laisse la fenêtre noire ouverte jusqu'au bout.
- Ensuite une fenêtre d'aperçu **HeadScreen** s'ouvre avec ta webcam et le cube sur ta tête.
- Les lancements suivants sont instantanés.

Dans la fenêtre noire, tu dois voir `Caméra virtuelle active : OBS Virtual Camera`.

### Étape 5 — Utiliser dans Discord / Teams / Zoom…

1. **Laisse HeadScreen ouvert** (il doit tourner pour envoyer l'image).
2. Dans ton appli, ouvre les réglages vidéo et choisis la caméra **OBS Virtual Camera** (et non ta vraie webcam).
   - Discord : Paramètres → Voix et vidéo → Caméra.

---

## Commandes (clique d'abord sur la fenêtre d'aperçu)

| Touche | Action |
|---|---|
| `N` | Style d'avatar suivant (Neon, Pixel LED, Rétro CRT, Robot, Mignon) |
| `1` | Visage animé |
| `2` | Texte défilant |
| `3` | Pluie « Matrix » |
| `4` / `A` | Ton image perso (voir plus bas) / image suivante |
| `C` | Calibrer : regarde droit devant toi puis appuie (règle le haut/bas) |
| `B` | Afficher / cacher le cadre de l'écran |
| `Q` | Quitter |

### Gestes de la main

| Geste | Expression |
|---|---|
| 👍 Pouce levé | Content |
| ✋ Main ouverte | « HELLO » |
| ✌️ Signe V | Yeux en cœur |
| ✊ Poing | Colère |
| Main devant le visage | « ? » |

---

## Options

Tu peux ajouter des options à la suite de `run.bat`, dans l'Invite de commandes (ex. `run.bat --mirror`) :

| Option | Effet |
|---|---|
| `--mirror` | Effet miroir (comme un selfie) |
| `--text "Salut"` | Change le texte du mode `2` |
| `--camera 1` | Utilise une autre webcam (0 = la première) |
| `--no-hands` | Désactive les gestes de main (plus fluide sur un PC faible) |
| `--no-vcam` | Aperçu seulement, sans caméra virtuelle |
| `--width 640 --height 480` | Résolution plus basse = plus fluide |

---

## Mettre ton propre avatar (image)

1. Mets une image (`.png`, `.jpg`, `.webp`…) dans le dossier **`avatars/`**.
2. Dans l'aperçu, appuie sur `4` (ou `A` pour passer à l'image suivante).

Le contenu de `avatars/` n'est **jamais publié** sur GitHub : c'est volontaire, tes images restent chez toi.

---

## Ça ne marche pas ?

**Écran noir / « Image noire »**
Ta webcam est déjà utilisée par une autre appli (Discord, Teams, Zoom, l'app Caméra…). Coupe la caméra dans cette appli, relance HeadScreen, puis dans l'appli choisis **OBS Virtual Camera**.

**« OBS Virtual Camera » n'apparaît pas dans la liste de caméras**
1. Vérifie que HeadScreen tourne et affiche `Caméra virtuelle active`.
2. **Quitte complètement l'appli** (Discord : clic droit sur son icône près de l'horloge → Quitter), puis relance-la. La liste de caméras ne se met à jour qu'au démarrage.
3. Toujours rien : ouvre OBS une fois, clique sur **Démarrer la caméra virtuelle**, puis **Arrêter**, ferme OBS et redémarre l'appli.

**`Caméra virtuelle indisponible`**
OBS Studio n'est pas installé (étape 2), ou il faut redémarrer le PC après son installation.

**`py n'est pas reconnu` ou erreur sur Python 3.12**
Python 3.12 n'est pas installé, ou la case « Add python.exe to PATH » n'était pas cochée. Refais l'étape 1.

**L'installation a planté au premier lancement**
Supprime le dossier `.venv` dans le projet, vérifie ta connexion Internet, puis relance `run.bat`.

**Impossible d'ouvrir la webcam**
Windows → Paramètres → Confidentialité et sécurité → Caméra : autorise les applications de bureau à utiliser la caméra.

**Ça lagge**
Essaie `run.bat --no-hands`, ou une résolution plus basse (`--width 640 --height 480`), et ferme les autres applis gourmandes.

**Le cube ne suit pas bien / est mal placé**
Place-toi face à la caméra, bien éclairé, regarde droit devant puis appuie sur `C`.

---

## Pour les développeurs

Un seul fichier : `headscreen.py` (OpenCV + MediaPipe + pyvirtualcam). Installation manuelle :

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python headscreen.py --mirror
```
