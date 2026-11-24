# Guide d'exécution — Upscayl-Image

- Python >=3.11 (testé sous Python 3.11.9) ; `pip install -r requirements.txt` uniquement si l'environnement autorise l'installation.
- Pillow : nécessaire pour resize/compress. Pas besoin de FFmpeg.
- Enhance IA : Upscayl NCNN et modèles compatibles + environnement graphique/accélérateur compatibles. Sur conteneur Linux sans GPU Vulkan : fonction non garantie.
- Télécharger un moteur lourd uniquement si une release GitHub est réellement publiée et son SHA-256 renseigné dans `references/dependencies.json`.
- Lancer `python scripts/dependencies.py --check`, puis éventuellement `python scripts/dependencies.py --install upscayl-ncnn` après autorisation de téléchargement.
- Variables possibles : UPSCAYL_BIN et UPSCAYL_MODELS. Sinon découverte sous `.runtime` après installation.
- Pour partage OpenAI Skills API : un SKILL.md et dossier scripts/references ; aucune archive Windows lourde incluse.
- Aucun accès Internet implicite. Si l'environnement interdit le réseau ou l'installation, signaler clairement l'impossibilité d'utiliser Enhance et continuer resize/compress si Pillow est présent.
- Licence et provenance des modèles devront être vérifiées avant redistribution publique des moteurs et poids IA sur le GitHub de Sam.
