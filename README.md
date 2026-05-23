# Discord Overlay — app native Python

Affiche les messages d'un salon Discord en overlay transparent par-dessus
toutes vos applications, en temps réel. Supporte texte, images, vidéos, audios.

```
discord-overlay/
├── bot/
│   ├── bot.py            ← Bot Discord + serveur WebSocket
│   └── requirements.txt
└── overlay/
    ├── overlay.py        ← Fenêtre overlay native (tkinter + Pillow)
    └── requirements.txt
```

---

## 1. Créer le Bot Discord

1. Aller sur https://discord.com/developers/applications
2. **New Application** → donner un nom
3. Onglet **Bot** → **Add Bot** → copier le **Token**
4. Onglet **Bot** → activer **Message Content Intent**
5. Onglet **OAuth2 → URL Generator** :
   - Scopes : `bot`
   - Bot permissions : `Read Messages/View Channels` + `Read Message History`
6. Copier l'URL générée → l'ouvrir → inviter le bot sur votre serveur

---

## 2. Récupérer l'ID du salon

Dans Discord :
- **Paramètres → Avancés → Mode développeur** (activer)
- Clic droit sur le salon → **Copier l'identifiant**

---

## 3. Configurer le bot

Ouvrir `bot/bot.py` et modifier :

```python
BOT_TOKEN  = "VOTRE_TOKEN_ICI"
CHANNEL_ID = 123456789012345678   # ID du salon (int, sans guillemets)
```

---

## 4. Installation

### Bot
```bash
cd bot
pip install -r requirements.txt
```

### Overlay
```bash
cd overlay
pip install -r requirements.txt
```

> **Windows** : tkinter est inclus dans Python.  
> **Linux** : `sudo apt install python3-tk` si absent.  
> **macOS** : Python depuis python.org inclut tkinter.

---

## 5. Lancement

Ouvrir **deux terminaux** :

**Terminal 1 — Bot Discord :**
```bash
cd bot
python bot.py
```

**Terminal 2 — Overlay :**
```bash
cd overlay
python overlay.py
```

L'overlay apparaît en bas à droite de l'écran.  
Dès qu'un message arrive dans le salon surveillé, une notification s'affiche.

---

## Fonctionnalités

| Contenu          | Comportement                                      |
|------------------|---------------------------------------------------|
| Texte            | Affiché directement dans le toast                 |
| Image            | Miniature chargée et affichée inline              |
| Vidéo / Audio    | Bouton cliquable → ouvre dans le navigateur       |
| Fichier          | Lien cliquable                                    |
| Avatar           | Chargé et affiché en cercle                       |

- **Always-on-top** : visible par-dessus toutes les fenêtres
- **Transparence** : configurable via `BG_ALPHA` dans `overlay.py`
- **Auto-disparition** : chaque toast disparaît après `TOAST_DURATION` secondes
- **Barre de progression** : indique le temps restant
- **Reconnexion auto** : l'overlay se reconnecte si le bot redémarre
- **Click-through** : (Windows) les clics traversent la fenêtre vers les apps dessous

---

## Configuration avancée (`overlay.py`)

```python
OVERLAY_WIDTH   = 420   # largeur des toasts (px)
MAX_TOASTS      = 5     # nombre max de toasts simultanés
TOAST_DURATION  = 7     # secondes avant disparition
MARGIN          = 20    # marge bord d'écran
BG_ALPHA        = 0.88  # transparence (0=invisible, 1=opaque)
```

---

## Dépannage

**"No module named tkinter"** → `sudo apt install python3-tk` (Linux)  
**L'overlay ne se connecte pas** → vérifier que le bot tourne bien et que `WS_URL` correspond  
**Aucun message reçu** → vérifier `CHANNEL_ID` et que le bot est bien dans le serveur  
**Token invalide** → régénérer le token sur le portail développeur Discord
