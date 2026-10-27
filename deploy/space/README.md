---
title: MiniWeb
emoji: 🧩
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
startup_duration_timeout: 1h
pinned: false
short_description: 65 practice websites for web agents (read-only demo)
---

# MiniWeb demo

The 65 MiniWeb websites and the annotation tool used to build MiniWeb's 369 tasks, as a read-only demo.

- **Code:** [sparklabutah/MiniWeb](https://github.com/sparklabutah/MiniWeb)
- **Data:** [sparklabuofu/MiniWeb](https://huggingface.co/datasets/sparklabuofu/MiniWeb)

## What you can do

- **Use the sites.** Open any of the 65 websites from the start page: shop, send mail, book a flight, drag a slider.
  Your changes are visible only to you. They are dropped after an hour without activity, and whenever the Space
  restarts.
- **Explore the annotation tool** at `/annotate/`.
  - The task editor opens one of the released tasks with its instruction, primitive tags and verifier filled in.
  - The Macro Browser steps through the human demonstrations primitive by primitive.
  - The verifier page runs a task's verifier on its recorded demonstration.
  - Nothing you change in the tool is saved.

## How the demo stays fixed

- Every visitor's edits go to their own session layer, and the site tables refuse writes.
- No language model is called. The translation site answers the requests recorded in the dataset with their recorded
  translations, and translates any other text with a local NLLB model, so the same text always gets the same answer.
- On every start, the Space rebuilds its data from the Hugging Face release.

## Run it yourself

```
docker build -f deploy/space/Dockerfile -t miniweb-demo .
docker run -p 7860:7860 miniweb-demo        # then http://localhost:7860
```

Run it from a clone of the code repository. Set `MINIWEB_DEMO_MEDIA=0` to skip the 8 GB of site images.
