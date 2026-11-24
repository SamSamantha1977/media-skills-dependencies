# Guide d'exécution — Video2X-Video

- Python >=3.11 (testé sous Python 3.11.9), bibliothèque standard pour l'interface CLI.
- FFmpeg et FFprobe nécessaires. Vérifier d'abord PATH, FFMPEG_BIN, FFPROBE_BIN ou `.runtime`.
- Si absents : installation autorisée seulement avec environnement réseau qui permet HTTPS GitHub et un manifeste de dépendances rempli avec URL et SHA-256 réels.
- `python scripts/dependencies.py --check` pour diagnostic ; `python scripts/dependencies.py --install ffmpeg` uniquement après publication des assets.
- Enhance natif nécessite Video2X RealESRGAN, modèles compatibles et GPU Vulkan. `VIDEO2X_BIN` peut désigner une installation existante.
- FFmpeg minterpolate = interpolation optique, pas IA RIFE. Qualité perceptive susceptible de déformations sur les mouvements complexes.
- Faute de GPU, les modes Resize, Interpolate et Compress restent utilisables SI FFmpeg/FFprobe sont disponibles.
- Pas de téléchargement implicite ; vérifier toute archive par SHA-256 et ne jamais suivre un lien arbitraire.
- Avant tout dépôt public de ressources lourdes, vérifier l'ensemble des licences de redistribution et notices des moteurs, modèles et binaires.
