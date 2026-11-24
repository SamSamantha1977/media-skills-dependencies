---
name: video2x-video
description: Resize video Lanczos, interpolation temporelle FFmpeg directe, compression H264 par CRF, et amelioration RealESRGAN via Video2X quand le GPU et les moteurs natifs sont disponibles. Python portable.
---
# Video2X-Video — édition OpenAI légère

## Quand l'utiliser
Agrandir, réduire ou fluidifier une vidéo ; multiplier les images par seconde ×2 ou ×4 ; convertir en MP4 H.264 ; compresser sous une limite ; améliorer par RealESRGAN si l'environnement le permet.

## Exécution
Python 3.11+ standard ; FFmpeg et FFprobe sont nécessaires pour traiter la vidéo. Pas de PowerShell.

```bash
python scripts/dependencies.py --check
python scripts/run.py --src clip.mp4 --mode interpolate --interpolate 2
python scripts/run.py --src clip.mp4 --mode interpolate --interpolate 4
python scripts/run.py --src clip.mp4 --mode resize --scale 0.5
python scripts/run.py --src clip.mp4 --mode compress --target-mb 20 --crf 17 --max-crf 30 --strict
python scripts/run.py --src clip.mp4 --mode enhance --scale 2 --model realesrgan-plus
```

## Routage
- `resize` : FFmpeg Lanczos, sans IA.
- `interpolate` : FFmpeg `minterpolate`, jamais RIFE. FPS ×2 par défaut, ×4 possible ; FPS, durée, nombre d'images et audio contrôlés par FFprobe.
- `compress` : encodeur H.264 CRF ; la règle JPEG `strict x,y` de l'autre skill ne s'applique pas aux vidéos.
- `enhance` : Video2X + RealESRGAN + GPU Vulkan et modèles adaptés. Non garanti dans les conteneurs ChatGPT ; si absent, refuser cette fonction, sans fausse réussite.
- Préserver l'entrée, ne pas écraser sans `--force` et sauvegarde BCCE. `--dry-run` annonce les destinations.

## Dépendances
Rechercher d'abord FFmpeg/FFprobe dans le système et les variables `FFMPEG_BIN` et `FFPROBE_BIN`, puis le sous-dossier `.runtime` du skill. Le téléchargement n'est possible que depuis une archive GitHub release publiée, avec URL HTTPS autorisée et SHA-256 vérifié, via `scripts/dependencies.py`. Si les assets ne sont pas publiés, le manifeste indique clairement ce blocage.

Consulter `references/RUNTIME.md` avant toute installation. Ne jamais présumer d'un accès GPU, de droits d'installation ni d'accès réseau en conteneur OpenAI. Vidéos source et sortie exclusivement dans les chemins accessibles au runtime.

## Indépendance
Aucune dépendance à Upscayl-Image, aucun chemin MINIPC codé en dur et aucune donnée personnelle embarquée. Le seul SKILL.md de cette archive est celui-ci. Les scripts Python sont appelables sans autre skill.
